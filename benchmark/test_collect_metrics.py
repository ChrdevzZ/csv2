#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).with_name("collect_metrics.py")
SPEC = importlib.util.spec_from_file_location("csv2_collect_metrics", MODULE_PATH)
assert SPEC and SPEC.loader
METRICS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(METRICS)


class CollectMetricsTests(unittest.TestCase):
    def test_counter_command_requests_operation_scoped_tracking(self) -> None:
        args = SimpleNamespace(
            executable=Path("csv2_benchmark"),
            operation="rows_cells",
            input=Path("input.csv"),
            source="buffer",
            iterations=7,
        )

        command = METRICS.benchmark_command(args, track_hardware_counters=True)

        self.assertEqual(command[-1], "--track-counters")

    def test_counter_summary_scales_each_sample_before_statistics(self) -> None:
        samples = [
            {
                "hardware_counter_scope": "timed_operation",
                "hardware_counter_time_enabled": "100",
                "hardware_counter_time_running": "100",
                "cycles": "1000",
                "instructions": "500",
                "branch_misses": "10",
                "checksum": "42",
            },
            {
                "hardware_counter_scope": "timed_operation",
                "hardware_counter_time_enabled": "200",
                "hardware_counter_time_running": "100",
                "cycles": "600",
                "instructions": "300",
                "branch_misses": "8",
                "checksum": "42",
            },
            {
                "hardware_counter_scope": "timed_operation",
                "hardware_counter_time_enabled": "100",
                "hardware_counter_time_running": "100",
                "cycles": "1100",
                "instructions": "550",
                "branch_misses": "12",
                "checksum": "42",
            },
        ]

        summary = METRICS.summarize_counter_samples(
            samples, processed_bytes=100, expected_checksum="42"
        )

        self.assertEqual(summary["scope"], "timed_operation")
        self.assertEqual(summary["runs"], 3)
        self.assertEqual(summary["median"]["cycles"], 1100.0)
        self.assertEqual(summary["median"]["cycles_per_byte"], 11.0)
        self.assertEqual(summary["median"]["instructions_per_byte"], 5.5)
        self.assertEqual(summary["median"]["branch_misses"], 12.0)
        self.assertEqual(summary["mad"]["cycles"], 100.0)

    def test_counter_summary_rejects_mixed_scope(self) -> None:
        sample = {
            "hardware_counter_scope": "whole_process",
            "hardware_counter_time_enabled": "1",
            "hardware_counter_time_running": "1",
            "cycles": "1",
            "instructions": "1",
            "branch_misses": "1",
            "checksum": "1",
        }
        with self.assertRaisesRegex(RuntimeError, "timed_operation"):
            METRICS.summarize_counter_samples(
                [sample], processed_bytes=1, expected_checksum="1"
            )

    def test_counter_summary_rejects_checksum_changed_by_tracking(self) -> None:
        sample = {
            "hardware_counter_scope": "timed_operation",
            "hardware_counter_time_enabled": "1",
            "hardware_counter_time_running": "1",
            "cycles": "1",
            "instructions": "1",
            "branch_misses": "1",
            "checksum": "changed",
        }
        with self.assertRaisesRegex(RuntimeError, "benchmark checksum"):
            METRICS.summarize_counter_samples(
                [sample], processed_bytes=1, expected_checksum="baseline"
            )


if __name__ == "__main__":
    unittest.main()
