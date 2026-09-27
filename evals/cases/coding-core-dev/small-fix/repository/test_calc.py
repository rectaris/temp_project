import unittest

from calc import clamp


class ClampTest(unittest.TestCase):
    def test_below_range_returns_low(self):
        self.assertEqual(clamp(-5, 0, 10), 0)

    def test_inside_range_returns_value(self):
        self.assertEqual(clamp(4, 0, 10), 4)

    def test_above_range_returns_high(self):
        self.assertEqual(clamp(15, 0, 10), 10)

    def test_bounds_are_inclusive(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
