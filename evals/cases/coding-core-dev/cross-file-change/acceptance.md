# Acceptance

- `apply_limit(items, limit)` returns the first `limit` items and raises `ValueError` for a negative limit.
- `summarize(items)` still lists at most `DEFAULT_LIMIT` items, and `summarize(items, limit=n)` lists at most `n` items in the same format.
- `python3 -m unittest -q test_report` passes in the repository root.
- `test_report.py` is unchanged.
