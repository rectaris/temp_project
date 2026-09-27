# Fix the upper bound of clamp

`clamp(value, low, high)` in `calc.py` should return a value limited to the inclusive range from `low` to `high`.
A value above `high` is currently returned unchanged.
Make `clamp` return `high` for such a value, and keep its behavior for every other value.
