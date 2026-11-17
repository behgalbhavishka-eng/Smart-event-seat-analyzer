
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import uuid
import os
import re

app = Flask(__name__)
app.secret_key = "smart-seat-demo-key"

DB_FILE = os.path.join(os.path.dirname(__file__), "seats.db")

PRICES = {"A": 300, "B": 250, "C": 200, "D": 150}


def connect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    conn = connect_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS seats (
            seat_number INTEGER PRIMARY KEY,
            seat_row TEXT,
            price INTEGER,
            status TEXT DEFAULT 'Available',
            customer_name TEXT,
            email TEXT,
            booking_id TEXT
        )
    """)

    # Store cancellation history separately.
    # Existing seats and bookings are preserved.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cancellation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT,
            seat_number INTEGER,
            seat_row TEXT,
            customer_name TEXT,
            email TEXT,
            price INTEGER,
            cancelled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(seats)").fetchall()
    }

    required = {
        "seat_row": "TEXT",
        "price": "INTEGER DEFAULT 0",
        "status": "TEXT DEFAULT 'Available'",
        "customer_name": "TEXT",
        "email": "TEXT",
        "booking_id": "TEXT"
    }

    for column, definition in required.items():
        if column not in columns:
            conn.execute(
                f"ALTER TABLE seats ADD COLUMN {column} {definition}"
            )

    rows = conn.execute("SELECT * FROM seats").fetchall()

    for seat in rows:
        number = str(seat["seat_number"])
        row_name = seat["seat_row"]

        if not row_name:
            match = re.match(r"^([A-D])", number.upper())

            if match:
                row_name = match.group(1)
            else:
                try:
                    numeric_id = int(number)
                except ValueError:
                    numeric_id = 1

                row_name = "ABCD"[min((numeric_id - 1) // 10, 3)]

        price = seat["price"]
        if price is None or price == 0:
            price = PRICES.get(row_name, 150)

        status = (
            "Booked"
            if str(seat["status"] or "").lower() == "booked"
            else "Available"
        )

        conn.execute("""
            UPDATE seats
            SET seat_row = ?, price = ?, status = ?
            WHERE seat_number = ?
        """, (row_name, price, status, seat["seat_number"]))

    count = conn.execute(
        "SELECT COUNT(*) FROM seats"
    ).fetchone()[0]

    if count == 0:
        for number in range(1, 41):
            row_name = "ABCD"[(number - 1) // 10]

            conn.execute("""
                INSERT INTO seats
                    (seat_number, seat_row, price, status)
                VALUES (?, ?, ?, 'Available')
            """, (number, row_name, PRICES[row_name]))

    conn.commit()
    conn.close()


def get_seats():
    conn = connect_db()
    rows = conn.execute("SELECT * FROM seats").fetchall()
    conn.close()

    seats = [dict(row) for row in rows]

    def sort_number(seat):
        match = re.search(r"\d+", str(seat["seat_number"]))
        return int(match.group()) if match else 0

    seats.sort(key=lambda s: (str(s["seat_row"]), sort_number(s)))

    row_counts = {}

    for seat in seats:
        row_name = str(seat["seat_row"])
        row_counts[row_name] = row_counts.get(row_name, 0) + 1

        stored_number = str(seat["seat_number"])

        if re.fullmatch(r"[A-Da-d]\d+", stored_number):
            seat["seat_label"] = stored_number.upper()
        else:
            seat["seat_label"] = f"{row_name}{row_counts[row_name]}"

        seat["status"] = (
            "Booked"
            if str(seat["status"]).lower() == "booked"
            else "Available"
        )

    return seats


def get_dashboard_data():
    seats = get_seats()

    bookings = [
        seat for seat in seats
        if seat["status"] == "Booked"
    ]

    available = [
        seat for seat in seats
        if seat["status"] == "Available"
    ]

    total = len(seats)
    booked_count = len(bookings)
    available_count = len(available)

    revenue = sum(
        float(seat["price"] or 0)
        for seat in bookings
    )

    # Count recorded cancellations.
    conn = connect_db()
    cancelled_count = conn.execute(
        "SELECT COUNT(*) FROM cancellation_history"
    ).fetchone()[0]
    conn.close()

    booked_percent = (
        round(booked_count * 100 / total)
        if total else 0
    )

    available_percent = (
        round(available_count * 100 / total)
        if total else 0
    )

    # Data used by the doughnut chart.
    status_chart = {
        "labels": [
            "Available Seats",
            "Booked Seats",
            "Cancelled Bookings"
        ],
        "values": [
            available_count,
            booked_count,
            cancelled_count
        ]
    }

    return {
        "seats": seats,
        "bookings": bookings,
        "total_seats": total,
        "booked_seats": booked_count,
        "available_seats": available_count,
        "cancelled_seats": cancelled_count,
        "revenue": revenue,
        "booked_percent": booked_percent,
        "available_percent": available_percent,
        "status_chart": status_chart
    }


@app.route("/")
def home():
    data = get_dashboard_data()

    ticket_id = request.args.get("ticket")
    ticket = None

    if ticket_id:
        conn = connect_db()

        ticket_row = conn.execute("""
            SELECT * FROM seats
            WHERE booking_id = ?
        """, (ticket_id,)).fetchone()

        conn.close()

        if ticket_row:
            ticket = dict(ticket_row)

            for seat in data["seats"]:
                if str(seat["seat_number"]) == str(
                    ticket["seat_number"]
                ):
                    ticket["seat_label"] = seat["seat_label"]
                    break

    return render_template(
        "index.html",
        **data,
        ticket=ticket
    )


@app.route("/book", methods=["POST"])
def book():
    name = request.form.get("customer_name", "").strip()
    email = request.form.get("email", "").strip()
    seat_number = request.form.get("seat_number", "").strip()

    if not name or not email or not seat_number:
        flash("Please complete all booking details.", "error")
        return redirect(url_for("home"))

    conn = connect_db()

    seat = conn.execute("""
        SELECT * FROM seats
        WHERE CAST(seat_number AS TEXT) = ?
    """, (seat_number,)).fetchone()

    if not seat:
        conn.close()
        flash("Please select a valid seat.", "error")
        return redirect(url_for("home"))

    if str(seat["status"]).lower() != "available":
        conn.close()
        flash("Sorry, that seat is already booked.", "error")
        return redirect(url_for("home"))

    booking_id = "BK-" + uuid.uuid4().hex[:8].upper()

    result = conn.execute("""
        UPDATE seats
        SET status = 'Booked',
            customer_name = ?,
            email = ?,
            booking_id = ?
        WHERE CAST(seat_number AS TEXT) = ?
          AND LOWER(status) = 'available'
    """, (name, email, booking_id, seat_number))

    conn.commit()
    conn.close()

    if result.rowcount == 1:
        return redirect(url_for("home", ticket=booking_id))

    flash(
        "The seat was just booked. Please choose another.",
        "error"
    )
    return redirect(url_for("home"))


@app.route("/cancel/<booking_id>", methods=["POST"])
def cancel(booking_id):
    conn = connect_db()

    try:
        # Find the booking before clearing its details.
        seat = conn.execute("""
            SELECT * FROM seats
            WHERE booking_id = ?
              AND LOWER(status) = 'booked'
        """, (booking_id,)).fetchone()

        if seat is None:
            conn.rollback()
            flash("Booking could not be found.", "error")
            return redirect(url_for("home"))

        # Save a record of the cancelled booking.
        conn.execute("""
            INSERT INTO cancellation_history (
                booking_id,
                seat_number,
                seat_row,
                customer_name,
                email,
                price
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            seat["booking_id"],
            seat["seat_number"],
            seat["seat_row"],
            seat["customer_name"],
            seat["email"],
            seat["price"]
        ))

        # Make the seat available again.
        conn.execute("""
            UPDATE seats
            SET status = 'Available',
                customer_name = NULL,
                email = NULL,
                booking_id = NULL
            WHERE booking_id = ?
        """, (booking_id,))

        conn.commit()
        flash("Booking cancelled successfully.", "success")

    except sqlite3.Error:
        conn.rollback()
        flash("Cancellation failed. Please try again.", "error")

    finally:
        conn.close()

    return redirect(url_for("home"))


@app.route("/suggest", methods=["POST"])
def suggest():
    preferred_row = request.form.get(
        "preferred_row", ""
    ).strip().upper()

    data = get_dashboard_data()

    available = [
        seat for seat in data["seats"]
        if seat["status"] == "Available"
        and (
            not preferred_row
            or seat["seat_row"] == preferred_row
        )
    ]

    suggestion = None

    if available:
        chosen = available[0]
        suggestion = (
            f"Recommended seat: {chosen['seat_label']} "
            f"— ₹{chosen['price']}"
        )
    else:
        suggestion = (
            "No available seats in that row. "
            "Try another row."
        )

    return render_template(
        "index.html",
        **data,
        ticket=None,
        suggestion=suggestion
    )


if __name__ == "__main__":
    initialize_db()
    app.run(debug=True)
