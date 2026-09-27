"""Item limits shared by the report helpers."""

DEFAULT_LIMIT = 3


def apply_limit(items):
    """Return the first DEFAULT_LIMIT items."""
    return list(items)[:DEFAULT_LIMIT]
