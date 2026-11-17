
import time


# 1. MERGE SORT
def merge_sort(seats, key="seat_number"):
    if len(seats) <= 1:
        return seats.copy()

    middle = len(seats) // 2

    left = merge_sort(seats[:middle], key)
    right = merge_sort(seats[middle:], key)

    return merge(left, right, key)


def merge(left, right, key):
    result = []
    i = 0
    j = 0

    while i < len(left) and j < len(right):
        if left[i][key] <= right[j][key]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])

    return result


# 2. BINARY SEARCH
# The seats must be sorted by seat_number.
def binary_search(seats, target):
    low = 0
    high = len(seats) - 1

    while low <= high:
        middle = (low + high) // 2
        current = seats[middle]["seat_number"]

        if current == target:
            return seats[middle]
        elif current < target:
            low = middle + 1
        else:
            high = middle - 1

    return None


# 3. GREEDY SEAT ALLOCATION
# Choose the cheapest available seat in the preferred row.
# If that row is full, choose the cheapest available seat overall.
def greedy_allocate(seats, preferred_row=None):
    available = [
        seat for seat in seats
        if seat["status"] == "Available"
    ]

    if preferred_row is not None:
        preferred = [
            seat for seat in available
            if seat["row"] == preferred_row
        ]

        if preferred:
            available = preferred

    if not available:
        return None

    chosen_seat = min(
        available,
        key=lambda seat: (seat["price"], seat["seat_number"])
    )

    return chosen_seat


# 4. TEST THE ALGORITHMS
if __name__ == "__main__":
    seats = [
        {"seat_number": 5, "row": "A",
         "price": 300, "status": "Available"},
        {"seat_number": 2, "row": "A",
         "price": 200, "status": "Booked"},
        {"seat_number": 8, "row": "B",
         "price": 150, "status": "Available"},
        {"seat_number": 1, "row": "A",
         "price": 250, "status": "Available"},
        {"seat_number": 4, "row": "B",
         "price": 200, "status": "Available"}
    ]

    print("SMART EVENT SEAT ALLOCATION SYSTEM")
    print("-" * 40)

    # Test Merge Sort
    sorted_seats = merge_sort(seats)
    print("\n1. Seats sorted by seat number:")
    for seat in sorted_seats:
        print(seat)

    # Test Binary Search
    result = binary_search(sorted_seats, 4)
    print("\n2. Binary Search for seat 4:")
    print(result if result else "Seat not found")

    # Test Greedy Algorithm
    chosen = greedy_allocate(seats, preferred_row="A")
    print("\n3. Greedy Seat Allocation:")
    print(chosen if chosen else "No seats available")

    # Measure sorting time
    start = time.perf_counter()
    merge_sort(seats)
    end = time.perf_counter()

    print("\n4. Merge Sort execution time:")
    print(f"{end - start:.8f} seconds")
