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

    def test_single_pair_bootstrap_is_exact(self) -> None:
        for baseline, candidate in ((2.0, 3.0), (4.0, 0.0), (2.0, -1.0)):
            with self.subTest(baseline=baseline, candidate=candidate):
                ratio = candidate / baseline
                self.assertEqual(
                    statistics.paired_bootstrap_ratio([baseline], [candidate]),
                    (ratio, ratio),
                )

    def test_single_pair_preserves_parameter_validation(self) -> None:
        cases = (
            ([], [], {}, ValueError, "non-empty"),
            ([1.0], [1.0, 2.0], {}, ValueError, "equal in length"),
            ([1.0], [2.0], {"samples": 99}, ValueError, "at least 100"),
            ([1.0], [2.0], {"samples": 100.5}, TypeError, "integer"),
            ([1.0], [2.0], {"seed": []}, TypeError, ""),
            ([0.0], [2.0], {}, ValueError, "must be positive"),
            ([-1.0], [2.0], {}, ValueError, "must be positive"),
        )
        for baseline, candidate, options, error, message in cases:
            with self.subTest(baseline=baseline, options=options):
                with self.assertRaisesRegex(error, message):
                    statistics.paired_bootstrap_ratio(baseline, candidate, **options)

    def test_regression_threshold_has_five_percent_floor(self) -> None:
        self.assertEqual(statistics.regression_threshold(0.01, 0.02), 0.05)
        self.assertEqual(statistics.regression_threshold(0.07, 0.02), 0.07)


if __name__ == "__main__":
    unittest.main()
