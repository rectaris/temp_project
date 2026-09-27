import unittest

from limits import DEFAULT_LIMIT, apply_limit
from report import summarize


class ApplyLimitTest(unittest.TestCase):
    def test_keeps_the_leading_items(self):
        self.assertEqual(apply_limit([1, 2, 3, 4], 2), [1, 2])

    def test_zero_limit_keeps_nothing(self):
        self.assertEqual(apply_limit([1, 2], 0), [])

    def test_negative_limit_is_refused(self):
        with self.assertRaises(ValueError):
            apply_limit([1, 2], -1)


class SummarizeTest(unittest.TestCase):
    def test_default_limit_is_unchanged(self):
        items = list(range(DEFAULT_LIMIT + 2))
        shown = ", ".join(str(item) for item in items[:DEFAULT_LIMIT])
        self.assertEqual(summarize(items), f"{len(items)} items: {shown}")

    def test_explicit_limit(self):
        self.assertEqual(summarize(["a", "b", "c", "d", "e", "f"], limit=5), "6 items: a, b, c, d, e")

    def test_limit_above_count_lists_everything(self):
        self.assertEqual(summarize(["a", "b"], limit=5), "2 items: a, b")


if __name__ == "__main__":
    unittest.main()
