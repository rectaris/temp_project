# Make the report item limit configurable

`report.summarize(items)` always lists at most `limits.DEFAULT_LIMIT` items, because `limits.apply_limit(items)` hard-codes that limit.

- Change `limits.apply_limit` to take the limit as a second argument, `apply_limit(items, limit)`. It keeps the first `limit` items and refuses a negative limit with `ValueError`.
- Give `report.summarize` an optional keyword argument `limit` that defaults to `limits.DEFAULT_LIMIT`, and pass it to `apply_limit`.
- Keep the summary format unchanged.
