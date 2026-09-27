"""Plain-text report helpers."""

from limits import apply_limit


def summarize(items):
    """Return a one-line summary of the leading items and the total count."""
    items = list(items)
    shown = apply_limit(items)
    return f"{len(items)} items: " + ", ".join(str(item) for item in shown)
