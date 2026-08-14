from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import _support  # noqa: F401
from csv2bench import metrics


class MetricsTests(unittest.TestCase):
    def test_collector_bundle_covers_entry_point_and_imported_helpers(self) -> None:
        benchmark_root = Path(metrics.__file__).resolve().parents[2]
        names = {
            path.relative_to(benchmark_root).as_posix()
            for path in metrics.collector_source_paths()
        }
        self.assertIn("collect_metrics.py", names)
        self.assertIn("tools/csv2bench/artifacts.py", names)
        self.assertIn("tools/csv2bench/statistics.py", names)

    def test_verify_command_uses_current_v2_cli(self) -> None:
        command = metrics.verify_command(
            Path("bench"), "traversal/rows", Path("input.csv"), "buffer"
        )
        self.assertEqual(command[-1], "--csv2-verify")
        self.assertIn("--csv2-operation", command)
        self.assertNotIn("--operation", command)

    def test_verification_rejects_revision_mismatch(self) -> None:
        with unittest.mock.patch.object(
            metrics,
            "run",
            return_value=unittest.mock.Mock(
                stdout=(
                    "protocol=csv2-current-v2 revision=other operation=traversal/rows "
                    "source=buffer dataset=x.csv checksum=1 bytes=1 rows=1 cells=0 "
                    "allocations=0 allocated_bytes=0\n"
                ),
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "revision"):
                metrics.verify(
                    Path("bench"), "traversal/rows", Path("input.csv"), "buffer", "expected"
                )

    def test_timing_command_binds_operation_source_and_json(self) -> None:
        command = metrics.timing_command(
            Path("bench"),
            "writer/raw-direct",
            Path("input.csv"),
            "buffer",
            Path("result.json"),
            20,
            "0.5s",
            0.1,
        )
        self.assertIn("--benchmark_repetitions=20", command)
        self.assertIn("--benchmark_out_format=json", command)
        self.assertTrue(any("writer/raw-direct" in value for value in command))

    def test_timing_report_requires_exact_iteration_count(self) -> None:
        document = {
            "benchmarks": [
                {
                    "name": "csv2/traversal/rows/buffer/x.csv",
                    "run_type": "iteration",
                    "real_time": 10,
                    "time_unit": "ns",
                    "bytes_per_second": 100,
                    "items_per_second": 10,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            parsed = metrics.parse_timing_report(path, 1)
            self.assertEqual(parsed["runs"], 1)
            with self.assertRaisesRegex(RuntimeError, "expected 2"):
                metrics.parse_timing_report(path, 2)

    def test_timing_report_rejects_mixed_benchmark_names(self) -> None:
        records = []
        for name in ("one", "two"):
            records.append(
                {
                    "name": name,
                    "real_time": 1,
                    "time_unit": "ns",
                    "bytes_per_second": 1,
                    "items_per_second": 1,
                }
            )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps({"benchmarks": records}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exactly one benchmark"):
                metrics.parse_timing_report(path, 2)

    def test_timing_report_rejects_skipped_or_error_samples(self) -> None:
        for marker in ({"error_occurred": True, "error_message": "read failed"},
                       {"skipped": True}):
            record = {
                "name": "csv2/source/file-read/file/x.csv",
                "run_type": "iteration",
                "real_time": 1,
                "time_unit": "ns",
                "bytes_per_second": 1,
                "items_per_second": 1,
                **marker,
            }
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "result.json"
                path.write_text(json.dumps({"benchmarks": [record]}), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "failed or skipped"):
                    metrics.parse_timing_report(path, 1)

    def test_controlled_timing_requires_every_pmu_counter(self) -> None:
        document = {
            "benchmarks": [
                {
                    "name": "csv2/traversal/rows/buffer/x.csv",
                    "real_time": 1,
                    "time_unit": "ns",
                    "bytes_per_second": 1,
                    "items_per_second": 1,
                    "cycles": 1,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "missing required PMU counters"):
                metrics.parse_timing_report(path, 1, require_pmu=True)

    def test_affinity_parser_is_strict_and_canonical(self) -> None:
        self.assertEqual(metrics.parse_affinity("2,0,2"), [0, 2])
        for value in ("", "-1", "x"):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    metrics.parse_affinity(value)

    def test_compile_commands_bind_the_declared_compiler(self) -> None:
        compiler = Path(__import__("sys").executable).resolve()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compile_commands.json"
            path.write_text(
                json.dumps([{"arguments": [str(compiler), "-c", "source.cpp"]}]),
                encoding="utf-8",
            )
            self.assertEqual(metrics.validate_compile_commands(path, compiler), 1)
            path.write_text(
                json.dumps([{"arguments": [str(path), "-c", "source.cpp"]}]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "declared compiler"):
                metrics.validate_compile_commands(path, compiler)


if __name__ == "__main__":
    unittest.main()
