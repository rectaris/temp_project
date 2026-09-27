"""Small arithmetic helpers."""


def clamp(value, low, high):
    """Return value limited to the inclusive range from low to high."""
    if value < low:
        return low
    if value > high:
        return value
    return value
