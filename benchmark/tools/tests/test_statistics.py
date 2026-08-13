from __future__ import annotations

import unittest

import _support  # noqa: F401
from csv2bench import statistics


class StatisticsTests(unittest.TestCase):
    def test_median_and_mad(self) -> None:
        self.assertEqual(statistics.median_mad([1.0, 2.0, 100.0]), (2.0, 1.0))

    def test_paired_bootstrap_is_deterministic(self) -> None:
        first = statistics.paired_bootstrap_ratio(
            [10.0, 11.0, 9.0], [9.0, 10.0, 8.0], samples=1000
        )
        second = statistics.paired_bootstrap_ratio(
            [10.0, 11.0, 9.0], [9.0, 10.0, 8.0], samples=1000
        )
        self.assertEqual(first, second)
        self.assertLess(first[1], 1.0)

    def test_paired_bootstrap_rejects_invalid_samples(self) -> None:
        with self.assertRaisesRegex(ValueError, "equal in length"):
            statistics.paired_bootstrap_ratio([1.0], [1.0, 2.0])
        with self.assertRaisesRegex(ValueError, "baseline samples"):
            statistics.paired_bootstrap_ratio([0.0], [1.0], samples=100)

    def test_regression_threshold_has_five_percent_floor(self) -> None:
        self.assertEqual(statistics.regression_threshold(0.01, 0.02), 0.05)
        self.assertEqual(statistics.regression_threshold(0.07, 0.02), 0.07)


if __name__ == "__main__":
    unittest.main()
