#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import importlib.util
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = Path(__file__).with_name("collect_metrics.py")
SPEC = importlib.util.spec_from_file_location("csv2_collect_metrics", MODULE_PATH)
assert SPEC and SPEC.loader
METRICS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(METRICS)

RUN_SUITE_PATH = Path(__file__).with_name("run_suite.py")
RUN_SUITE_SPEC = importlib.util.spec_from_file_location("csv2_run_suite", RUN_SUITE_PATH)
assert RUN_SUITE_SPEC and RUN_SUITE_SPEC.loader
RUN_SUITE = importlib.util.module_from_spec(RUN_SUITE_SPEC)
RUN_SUITE_SPEC.loader.exec_module(RUN_SUITE)


class CollectMetricsTests(unittest.TestCase):
    @staticmethod
    def benchmark_result(**overrides: str) -> dict[str, str]:
        result = {
            "revision": "working",
            "operation": "rows_cells",
            "source": "buffer",
            "bytes": "4",
            "iterations": "2",
            "seconds": "0.5",
            "gib_per_second": "0.1",
            "rows_per_second": "4.0",
            "cells_per_second": "8.0",
            "allocation_tracking": "unavailable",
            "allocations": "0",
            "allocated_bytes": "0",
            "hardware_counter_scope": "disabled",
            "hardware_counter_domain": "disabled",
            "hardware_counter_time_enabled": "0",
            "hardware_counter_time_running": "0",
            "cycles": "0",
            "instructions": "0",
            "branch_misses": "0",
            "rows": "2",
            "cells": "4",
            "checksum": "42",
        }
        result.update(overrides)
        if "hardware_counter_domain" not in overrides:
            result["hardware_counter_domain"] = (
                METRICS.HARDWARE_COUNTER_DOMAIN
                if result["hardware_counter_scope"] == "timed_operation"
                else "disabled"
            )
        return result

    def test_metrics_parser_rejects_duplicate_and_non_finite_fields(self) -> None:
        valid = " ".join(
            f"{name}={value}" for name, value in self.benchmark_result().items()
        )
        with self.assertRaisesRegex(RuntimeError, "duplicate key"):
            METRICS.parse_benchmark_output(valid + " checksum=8")
        parsed = METRICS.parse_benchmark_output(
            valid.replace("gib_per_second=0.1", "gib_per_second=nan")
        )
        with self.assertRaisesRegex(RuntimeError, "must be finite"):
            METRICS.numeric_result(parsed)
        missing_counter = self.benchmark_result()
        del missing_counter["cycles"]
        with self.assertRaisesRegex(RuntimeError, "missing required fields: cycles"):
            METRICS.parse_benchmark_output(
                " ".join(f"{name}={value}" for name, value in missing_counter.items())
            )

    def test_counter_command_requests_operation_scoped_tracking(self) -> None:
        args = SimpleNamespace(
            executable=Path("csv2_benchmark"),
            revision="working",
            operation="rows_cells",
            input=Path("input.csv"),
            source="buffer",
            iterations=7,
        )

        command = METRICS.benchmark_command(args, track_hardware_counters=True)

        self.assertEqual(command[-1], "--track-counters")

    def test_counter_summary_scales_each_sample_before_statistics(self) -> None:
        reference = self.benchmark_result()
        samples = [
            self.benchmark_result(
                hardware_counter_scope="timed_operation",
                hardware_counter_time_enabled="100",
                hardware_counter_time_running="100",
                cycles="1000",
                instructions="500",
                branch_misses="10",
                _command=json.dumps(["fake_benchmark", "--track-counters"]),
                _stdout="counter output",
                _stderr="",
            ),
            self.benchmark_result(
                hardware_counter_scope="timed_operation",
                hardware_counter_time_enabled="200",
                hardware_counter_time_running="100",
                cycles="600",
                instructions="300",
                branch_misses="8",
            ),
            self.benchmark_result(
                hardware_counter_scope="timed_operation",
                hardware_counter_time_enabled="100",
                hardware_counter_time_running="100",
                cycles="1100",
                instructions="550",
                branch_misses="12",
            ),
        ]

        summary = METRICS.summarize_counter_samples(
            samples, processed_bytes=100, reference=reference
        )

        self.assertEqual(summary["scope"], "timed_operation")
        self.assertEqual(summary["domain"], METRICS.HARDWARE_COUNTER_DOMAIN)
        self.assertEqual(summary["runs"], 3)
        self.assertEqual(summary["median"]["cycles"], 1100.0)
        self.assertEqual(summary["median"]["cycles_per_byte"], 11.0)
        self.assertEqual(summary["median"]["instructions_per_byte"], 5.5)
        self.assertEqual(summary["median"]["branch_misses"], 12.0)
        self.assertEqual(summary["mad"]["cycles"], 100.0)
        self.assertEqual(
            summary["samples"][0]["invocation"]["command"],
            ["fake_benchmark", "--track-counters"],
        )
        self.assertEqual(
            summary["samples"][0]["invocation"]["stdout"], "counter output"
        )

    def test_counter_summary_rejects_mixed_scope(self) -> None:
        reference = self.benchmark_result()
        sample = self.benchmark_result(
            hardware_counter_scope="whole_process",
            hardware_counter_time_enabled="1",
            hardware_counter_time_running="1",
            cycles="1",
            instructions="1",
            branch_misses="1",
        )
        with self.assertRaisesRegex(RuntimeError, "timed_operation"):
            METRICS.summarize_counter_samples(
                [sample], processed_bytes=1, reference=reference
            )

    def test_counter_summary_rejects_user_only_domain(self) -> None:
        reference = self.benchmark_result()
        sample = self.benchmark_result(
            hardware_counter_scope="timed_operation",
            hardware_counter_domain="calling_thread_user",
            hardware_counter_time_enabled="1",
            hardware_counter_time_running="1",
            cycles="1",
            instructions="1",
            branch_misses="1",
        )
        with self.assertRaisesRegex(RuntimeError, "user and kernel mode"):
            METRICS.summarize_counter_samples(
                [sample], processed_bytes=1, reference=reference
            )

    def test_counter_summary_rejects_checksum_changed_by_tracking(self) -> None:
        reference = self.benchmark_result()
        sample = self.benchmark_result(
            hardware_counter_scope="timed_operation",
            hardware_counter_time_enabled="1",
            hardware_counter_time_running="1",
            cycles="1",
            instructions="1",
            branch_misses="1",
            checksum="43",
        )
        with self.assertRaisesRegex(RuntimeError, "changed benchmark semantics"):
            METRICS.summarize_counter_samples(
                [sample], processed_bytes=1, reference=reference
            )

    def test_validator_rejects_wrong_metadata_and_negative_values(self) -> None:
        args = SimpleNamespace(
            revision="working", operation="rows_cells", source="buffer", iterations=2
        )
        METRICS.validate_benchmark_result(args, self.benchmark_result(), 4)
        with self.assertRaisesRegex(RuntimeError, "metadata mismatch for bytes"):
            METRICS.validate_benchmark_result(
                args, self.benchmark_result(bytes="5"), 4
            )
        with self.assertRaisesRegex(RuntimeError, "metadata mismatch for revision"):
            METRICS.validate_benchmark_result(
                args, self.benchmark_result(revision="other"), 4
            )
        with self.assertRaisesRegex(RuntimeError, "non-negative"):
            METRICS.validate_benchmark_result(
                args, self.benchmark_result(rows="-1"), 4
            )
        with self.assertRaisesRegex(RuntimeError, "uint64"):
            METRICS.validate_benchmark_result(
                args, self.benchmark_result(rows=str(1 << 64)), 4
            )

    def test_validator_enforces_tracking_contracts(self) -> None:
        args = SimpleNamespace(
            revision="working", operation="rows_cells", source="buffer", iterations=2
        )
        allocation = self.benchmark_result(allocation_tracking="available")
        METRICS.validate_benchmark_result(
            args, allocation, 4, track_allocations=True
        )
        with self.assertRaisesRegex(RuntimeError, "allocation tracking mismatch"):
            METRICS.validate_benchmark_result(args, allocation, 4)
        with self.assertRaisesRegex(RuntimeError, "unavailable allocation tracking"):
            METRICS.validate_benchmark_result(
                args, self.benchmark_result(allocations="1"), 4
            )

        counters = self.benchmark_result(
            hardware_counter_scope="timed_operation",
            hardware_counter_time_enabled="2",
            hardware_counter_time_running="1",
            cycles="10",
            instructions="8",
            branch_misses="1",
        )
        METRICS.validate_benchmark_result(
            args, counters, 4, track_hardware_counters=True
        )
        with self.assertRaisesRegex(RuntimeError, "counter scope mismatch"):
            METRICS.validate_benchmark_result(args, counters, 4)

    def test_peak_rss_retains_command_output_and_validated_result(self) -> None:
        output = " ".join(
            f"{name}={value}" for name, value in self.benchmark_result().items()
        )
        args = SimpleNamespace(
            executable=Path("fake_benchmark"),
            revision="working",
            operation="rows_cells",
            input=Path("input.csv"),
            source="buffer",
            iterations=2,
        )

        def fake_run(command: list[str], **options: object) -> SimpleNamespace:
            environment = options.get("env")
            self.assertIsInstance(environment, dict)
            assert isinstance(environment, dict)
            self.assertEqual(environment["LC_ALL"], "C")
            report_path = Path(command[command.index("-o") + 1])
            report_path.write_text(
                "Maximum resident set size (kbytes): 123\n", encoding="utf-8"
            )
            return SimpleNamespace(returncode=0, stdout=output + "\n", stderr="note\n")

        with (
            mock.patch.object(METRICS.Path, "is_file", return_value=True),
            mock.patch.object(METRICS.subprocess, "run", side_effect=fake_run),
        ):
            result = METRICS.collect_peak_rss(
                args, expected_bytes=4, reference=self.benchmark_result()
            )

        self.assertEqual(result["kib"], 123)
        self.assertEqual(result["stdout"], output)
        self.assertEqual(result["stderr"], "note")
        self.assertIn("fake_benchmark", result["command"])
        self.assertEqual(result["environment"], {"LC_ALL": "C"})

    def test_clean_build_retains_cwd_command_and_raw_output(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="built\n", stderr="note\n")
        with (
            mock.patch.object(METRICS.subprocess, "run", return_value=completed),
            mock.patch.object(METRICS.time, "perf_counter", side_effect=(1.0, 2.5)),
        ):
            result = METRICS.time_build("builder --clean")

        self.assertEqual(result["command"], ["builder", "--clean"])
        self.assertEqual(result["cwd"], str(Path.cwd().resolve()))
        self.assertEqual(result["seconds"], 1.5)
        self.assertEqual(result["stdout"], "built")
        self.assertEqual(result["stderr"], "note")

    def test_code_size_uses_stable_locale_and_retains_raw_output(self) -> None:
        completed = SimpleNamespace(
            stdout="text data bss dec hex filename\n10 2 3 15 f benchmark\n",
            stderr="note\n",
        )
        with (
            mock.patch.object(METRICS, "require_tool", return_value="size"),
            mock.patch.object(
                METRICS.subprocess, "run", return_value=completed
            ) as run,
        ):
            result = METRICS.collect_code_size(Path("benchmark"))

        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")
        self.assertEqual(result["environment"], {"LC_ALL": "C"})
        self.assertEqual(result["command"], ["size", "--format=berkeley", "benchmark"])
        self.assertEqual(result["stdout"], completed.stdout.rstrip("\n"))
        self.assertEqual(result["stderr"], "note")

    def test_fake_output_round_trip_retains_command_and_stdout(self) -> None:
        output = " ".join(
            f"{name}={value}" for name, value in self.benchmark_result().items()
        )
        args = SimpleNamespace(
            executable=Path("fake_benchmark"),
            revision="working",
            operation="rows_cells",
            input=Path("input.csv"),
            source="buffer",
            iterations=2,
        )
        completed = SimpleNamespace(returncode=0, stdout=output + "\n", stderr="warning\n")
        with mock.patch.object(METRICS.subprocess, "run", return_value=completed):
            result = METRICS.run_benchmark(args)

        self.assertEqual(result["bytes"], "4")
        self.assertEqual(
            json.loads(result["_command"]),
            [
                "fake_benchmark",
                "--operation",
                "rows_cells",
                "--input",
                "input.csv",
                "--source",
                "buffer",
                "--iterations",
                "2",
            ],
        )
        self.assertEqual(result["_stdout"], output)
        self.assertEqual(result["_stderr"], "warning")

    def test_main_builds_before_hashing_or_measuring_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            executable = root / "benchmark"
            allocation_executable = root / "benchmark_allocations"
            executable.write_bytes(b"old normal")
            allocation_executable.write_bytes(b"old allocations")
            dataset = root / "data.csv"
            dataset.write_bytes(b"a,b\n")
            output = root / "report.json"
            events: list[str] = []
            real_artifact_metadata = METRICS.artifact_metadata

            def fake_build(_: str) -> dict[str, object]:
                events.append("build")
                executable.write_bytes(b"new normal")
                allocation_executable.write_bytes(b"new allocations")
                return {
                    "command": ["builder", "--clean"],
                    "cwd": str(Path.cwd().resolve()),
                    "seconds": 1.0,
                    "stdout": "built",
                    "stderr": "",
                }

            def record_artifact(
                path: Path, revision: str | None = None
            ) -> dict[str, object]:
                if path in (executable, allocation_executable):
                    events.append(f"hash:{path.name}")
                return real_artifact_metadata(path, revision)

            def fake_benchmark(
                args: SimpleNamespace,
                track_allocations: bool = False,
                track_hardware_counters: bool = False,
                executable: Path | None = None,
            ) -> dict[str, str]:
                del args, track_hardware_counters, executable
                events.append("measure")
                return self.benchmark_result(
                    bytes="4",
                    iterations="1",
                    allocation_tracking=(
                        "available" if track_allocations else "unavailable"
                    ),
                )

            arguments = [
                "collect_metrics.py",
                "--executable",
                str(executable),
                "--allocation-executable",
                str(allocation_executable),
                "--revision",
                "working",
                "--compiler",
                "g++",
                "--compiler-flags=-O3",
                "--operation",
                "rows_cells",
                "--input",
                str(dataset),
                "--iterations",
                "1",
                "--build-command",
                "builder --clean",
                "--skip-counters",
                "--skip-rss",
                "--skip-size",
                "--output",
                str(output),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(METRICS, "time_build", side_effect=fake_build),
                mock.patch.object(
                    METRICS, "artifact_metadata", side_effect=record_artifact
                ),
                mock.patch.object(
                    METRICS, "run_benchmark", side_effect=fake_benchmark
                ),
            ):
                METRICS.main()

            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(events[0], "build")
        self.assertLess(events.index("build"), events.index("measure"))
        self.assertLess(events.index("build"), events.index("hash:benchmark"))
        self.assertEqual(
            report["executable"]["sha256"],
            hashlib.sha256(b"new normal").hexdigest(),
        )

    def test_main_revalidates_provenance_after_measurement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "benchmark"
            allocation_executable = root / "benchmark_allocations"
            executable.write_bytes(b"normal")
            allocation_executable.write_bytes(b"allocations")
            dataset = root / "data.csv"
            dataset.write_bytes(b"a,b\n")
            output = root / "report.json"
            calls = 0

            def fake_benchmark(
                args: SimpleNamespace,
                track_allocations: bool = False,
                track_hardware_counters: bool = False,
                executable: Path | None = None,
            ) -> dict[str, str]:
                nonlocal calls
                del args, track_hardware_counters, executable
                calls += 1
                if calls == 2:
                    dataset.write_bytes(b"x,y\n")
                return self.benchmark_result(
                    bytes="4",
                    iterations="1",
                    allocation_tracking=(
                        "available" if track_allocations else "unavailable"
                    ),
                )

            arguments = [
                "collect_metrics.py",
                "--executable",
                str(executable),
                "--allocation-executable",
                str(allocation_executable),
                "--revision",
                "working",
                "--compiler",
                "g++",
                "--compiler-flags=-O3",
                "--operation",
                "rows_cells",
                "--input",
                str(dataset),
                "--iterations",
                "1",
                "--skip-counters",
                "--skip-rss",
                "--skip-size",
                "--output",
                str(output),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    METRICS, "run_benchmark", side_effect=fake_benchmark
                ),
                self.assertRaisesRegex(RuntimeError, "dataset changed"),
            ):
                METRICS.main()

            self.assertFalse(output.exists())


class RunSuiteTests(unittest.TestCase):
    @staticmethod
    def driver_description() -> dict[str, str]:
        return {
            "protocol": "csv2-common-v1",
            "revision": "same",
            "operations": "rows_cells,legacy_mmap_rows_cells",
            "sources": "buffer,mmap",
            "prepared_scope": "traversal_only",
            "legacy_scope": "mmap_and_traversal",
        }

    def test_case_alternates_order_and_retains_raw_samples(self) -> None:
        calls: list[str] = []

        def fake_invoke(
            executable: Path,
            operation: str,
            dataset: Path,
            source: str,
            iterations: int,
        ) -> dict[str, str]:
            calls.append(executable.name)
            elapsed = "1500000000" if executable.name == "candidate" else "3000000000"
            return {
                "protocol": "csv2-common-v1",
                "revision": executable.name,
                "operation": operation,
                "scope": "traversal_only",
                "source": source,
                "bytes": "1073741824",
                "iterations": str(iterations),
                "elapsed_ns": elapsed,
                "rows": "9",
                "cells": "18",
                "row_bytes": "27",
                "checksum": "7",
                "_command": json.dumps([executable.name, "--operation", operation]),
                "_stdout": "raw result",
                "_stderr": "",
            }

        case = RUN_SUITE.measure_case(
            Path("baseline"),
            Path("candidate"),
            "rows_cells",
            Path("data.csv"),
            "buffer",
            runs=4,
            iterations=3,
            warmups=0,
            invoke_fn=fake_invoke,
            expected_bytes=1073741824,
        )

        self.assertEqual(
            calls,
            ["baseline", "candidate", "candidate", "baseline"] * 2,
        )
        self.assertEqual(case["baseline"]["samples"], [1.0] * 4)
        self.assertEqual(case["candidate"]["samples"], [2.0] * 4)
        self.assertEqual(
            case["launches"][0]["command"],
            ["baseline", "--operation", "rows_cells"],
        )
        self.assertTrue(case["improvement"])
        self.assertFalse(case["regression"])

    def test_case_rejects_checksum_mismatch(self) -> None:
        def mismatched_invoke(
            executable: Path,
            operation: str,
            dataset: Path,
            source: str,
            iterations: int,
        ) -> dict[str, str]:
            checksum = "1" if executable.name == "baseline" else "2"
            return {
                "protocol": "csv2-common-v1",
                "revision": executable.name,
                "operation": operation,
                "scope": "traversal_only",
                "source": source,
                "bytes": "1073741824",
                "iterations": str(iterations),
                "elapsed_ns": "1000000000",
                "rows": "1",
                "cells": "1",
                "row_bytes": "1",
                "checksum": checksum,
            }

        with self.assertRaisesRegex(RuntimeError, "semantic mismatch"):
            RUN_SUITE.measure_case(
                Path("baseline"),
                Path("candidate"),
                "rows_cells",
                Path("data.csv"),
                "buffer",
                runs=1,
                iterations=1,
                warmups=0,
                invoke_fn=mismatched_invoke,
                expected_bytes=1073741824,
            )

    def test_case_rejects_matching_but_incorrect_reported_byte_counts(self) -> None:
        def wrong_bytes_invoke(
            executable: Path,
            operation: str,
            dataset: Path,
            source: str,
            iterations: int,
        ) -> dict[str, str]:
            return {
                "protocol": "csv2-common-v1",
                "revision": executable.name,
                "operation": operation,
                "scope": "traversal_only",
                "source": source,
                "bytes": "5",
                "iterations": str(iterations),
                "elapsed_ns": "100",
                "rows": "1",
                "cells": "2",
                "row_bytes": "3",
                "checksum": "9",
            }

        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "data.csv"
            dataset.write_bytes(b"a,b\n")
            with self.assertRaisesRegex(RuntimeError, "byte count"):
                RUN_SUITE.measure_case(
                    Path("baseline"),
                    Path("candidate"),
                    "rows_cells",
                    dataset,
                    "buffer",
                    runs=1,
                    iterations=1,
                    warmups=0,
                    invoke_fn=wrong_bytes_invoke,
                )

    def test_artifact_metadata_records_content_hash_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "benchmark"
            artifact.write_bytes(b"exact benchmark bytes")

            metadata = RUN_SUITE.artifact_metadata(artifact, "9504e0b")

        self.assertEqual(metadata["revision"], "9504e0b")
        self.assertEqual(
            metadata["sha256"],
            "0e921757b199370c81bc9ecbfee3439f2d7f47bcac94f497cdc5afdfe8829a9c",
        )

    def test_artifact_verifier_rejects_content_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "benchmark"
            artifact.write_bytes(b"before")
            metadata = RUN_SUITE.artifact_metadata(artifact, "working")
            RUN_SUITE.verify_artifact_unchanged(metadata, "candidate")
            artifact.write_bytes(b"after!")
            with self.assertRaisesRegex(RuntimeError, "candidate changed"):
                RUN_SUITE.verify_artifact_unchanged(metadata, "candidate")

    def test_parser_rejects_incomplete_or_multiline_results(self) -> None:
        valid = (
            "protocol=csv2-common-v1 revision=base operation=rows_cells "
            "scope=traversal_only source=buffer bytes=1 iterations=1 elapsed_ns=1 "
            "rows=1 cells=1 row_bytes=1 checksum=1"
        )
        with self.assertRaisesRegex(RuntimeError, "exactly one result line"):
            RUN_SUITE.parse_output(valid + "\nextra=3")
        with self.assertRaisesRegex(RuntimeError, "required fields"):
            RUN_SUITE.parse_output("checksum=1")
        with self.assertRaisesRegex(RuntimeError, "duplicate key"):
            RUN_SUITE.parse_output(valid + " checksum=2")

    def test_result_rejects_revision_drift_and_invalid_checksum(self) -> None:
        result = {
            "protocol": "csv2-common-v1",
            "revision": "candidate",
            "operation": "rows_cells",
            "scope": "traversal_only",
            "source": "buffer",
            "bytes": "4",
            "iterations": "1",
            "elapsed_ns": "8",
            "rows": "1",
            "cells": "2",
            "row_bytes": "3",
            "checksum": "9",
        }
        with self.assertRaises(TypeError):
            RUN_SUITE.validate_result(result, "rows_cells", "buffer", 1)
        with self.assertRaisesRegex(RuntimeError, "revision changed"):
            RUN_SUITE.validate_result(
                result,
                "rows_cells",
                "buffer",
                1,
                expected_bytes=4,
                expected_revision="other",
            )
        result["checksum"] = "nan"
        with self.assertRaisesRegex(RuntimeError, "must be integers"):
            RUN_SUITE.validate_result(
                result, "rows_cells", "buffer", 1, expected_bytes=4
            )
        result["checksum"] = "9"
        result["rows"] = str(1 << 64)
        with self.assertRaisesRegex(RuntimeError, "valid range"):
            RUN_SUITE.validate_result(
                result, "rows_cells", "buffer", 1, expected_bytes=4
            )
        result["rows"] = "1"
        with self.assertRaisesRegex(RuntimeError, "byte count"):
            RUN_SUITE.validate_result(
                result, "rows_cells", "buffer", 1, expected_bytes=5
            )

    def test_calibration_requires_exact_candidate_and_dataset(self) -> None:
        context = {
            "compiler": "g++ 14",
            "compiler_flags": "-O3",
            "runs": 20,
            "iterations_per_run": 2,
            "warmups": 3,
            "host": {
                "platform": "host",
                "node": "node",
                "machine": "x86_64",
                "processor": "cpu",
                "cpu_model": "model",
                "cpu_model_source": "test fixture",
                "logical_cpus": 8,
                "python": "3.12",
            },
            "runner": {"sha256": "runner"},
            "adapter_source": {"sha256": "adapter"},
            "candidate": {"artifact": {"sha256": "candidate"}},
            "datasets": [{"name": "data.csv", "size": 4, "sha256": "data"}],
        }
        calibration = json.loads(json.dumps(context))
        RUN_SUITE.validate_calibration_context(calibration, context)
        calibration["runs"] = 21
        with self.assertRaisesRegex(RuntimeError, "runs"):
            RUN_SUITE.validate_calibration_context(calibration, context)
        calibration["runs"] = 20
        calibration["candidate"]["artifact"]["sha256"] = "different"
        with self.assertRaisesRegex(RuntimeError, "candidate executable"):
            RUN_SUITE.validate_calibration_context(calibration, context)

    def test_calibration_rejects_duplicate_or_non_finite_noise(self) -> None:
        case = {
            "dataset": "data.csv",
            "operation": "rows_cells",
            "source": "buffer",
            "observed_noise": 0.01,
        }
        report = {
            "schema": "csv2-benchmark-report-v2",
            "mode": "aa",
            "status": "completed",
            "baseline": {"artifact": {"sha256": "same"}},
            "candidate": {"artifact": {"sha256": "same"}},
            "cases": [case, dict(case)],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "duplicate cases"):
                RUN_SUITE.load_calibration(path)

            report["cases"] = [{**case, "observed_noise": float("nan")}]
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "finite"):
                RUN_SUITE.load_calibration(path)

    def test_selection_rejects_empty_and_duplicates(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            RUN_SUITE.selected("", ("one", "two"))
        with self.assertRaisesRegex(ValueError, "empty entries"):
            RUN_SUITE.selected("one,,two", ("one", "two"))
        with self.assertRaisesRegex(ValueError, "duplicates"):
            RUN_SUITE.selected("one,one", ("one", "two"))

    def test_legacy_operation_rejects_buffer_only_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.write_bytes(b"same executable")
            candidate.write_bytes(b"same executable")
            datasets = root / "datasets"
            datasets.mkdir()
            (datasets / "data.csv").write_text("a,b\n", encoding="utf-8")
            output = root / "report.json"
            arguments = [
                "run_suite.py",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--baseline-revision",
                "same",
                "--candidate-revision",
                "same",
                "--datasets",
                str(datasets),
                "--runs",
                "20",
                "--operations",
                "legacy_mmap_rows_cells",
                "--sources",
                "buffer",
                "--files",
                "data.csv",
                "--mode",
                "aa",
                "--compiler",
                "g++",
                "--compiler-flags=-O3",
                "--output",
                str(output),
            ]
            stderr = io.StringIO()
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    RUN_SUITE, "describe", return_value=self.driver_description()
                ),
                mock.patch.object(RUN_SUITE, "measure_case", return_value={}),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit),
            ):
                RUN_SUITE.main()

        self.assertIn("legacy_mmap_rows_cells requires source mmap", stderr.getvalue())

    def test_calibration_must_be_completed(self) -> None:
        report = {
            "schema": "csv2-benchmark-report-v2",
            "mode": "aa",
            "status": "running",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "completed"):
                RUN_SUITE.load_calibration(path)

    def test_host_metadata_records_cpu_identity_source(self) -> None:
        host = RUN_SUITE.host_metadata()

        self.assertIn("node", host)
        self.assertTrue(host["cpu_model"])
        self.assertTrue(host["cpu_model_source"])

    def test_report_checkpoints_running_then_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.write_bytes(b"same executable")
            candidate.write_bytes(b"same executable")
            datasets = root / "datasets"
            datasets.mkdir()
            (datasets / "data.csv").write_text("a,b\n", encoding="utf-8")
            output = root / "report.json"
            states: list[str] = []
            real_write_report = RUN_SUITE.write_report

            def record_write(path: Path, report: dict[str, object]) -> None:
                states.append(str(report["status"]))
                real_write_report(path, report)

            arguments = [
                "run_suite.py",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--baseline-revision",
                "same",
                "--candidate-revision",
                "same",
                "--datasets",
                str(datasets),
                "--runs",
                "20",
                "--warmups",
                "0",
                "--iterations",
                "1",
                "--operations",
                "rows_cells",
                "--sources",
                "buffer",
                "--files",
                "data.csv",
                "--mode",
                "aa",
                "--compiler",
                "g++",
                "--compiler-flags=-O3",
                "--output",
                str(output),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    RUN_SUITE, "describe", return_value=self.driver_description()
                ),
                mock.patch.object(RUN_SUITE, "measure_case", return_value={}),
                mock.patch.object(RUN_SUITE, "write_report", side_effect=record_write),
            ):
                RUN_SUITE.main()

            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(states[0], "running")
        self.assertEqual(states[-1], "completed")
        self.assertEqual(report["status"], "completed")

    def test_report_checkpoints_failed_measurement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.write_bytes(b"same executable")
            candidate.write_bytes(b"same executable")
            datasets = root / "datasets"
            datasets.mkdir()
            (datasets / "data.csv").write_text("a,b\n", encoding="utf-8")
            output = root / "report.json"
            states: list[str] = []
            real_write_report = RUN_SUITE.write_report

            def record_write(path: Path, report: dict[str, object]) -> None:
                states.append(str(report["status"]))
                real_write_report(path, report)

            arguments = [
                "run_suite.py",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--baseline-revision",
                "same",
                "--candidate-revision",
                "same",
                "--datasets",
                str(datasets),
                "--runs",
                "20",
                "--operations",
                "rows_cells",
                "--sources",
                "buffer",
                "--files",
                "data.csv",
                "--mode",
                "aa",
                "--compiler",
                "g++",
                "--compiler-flags=-O3",
                "--output",
                str(output),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    RUN_SUITE, "describe", return_value=self.driver_description()
                ),
                mock.patch.object(
                    RUN_SUITE,
                    "measure_case",
                    side_effect=RuntimeError("synthetic failure"),
                ),
                mock.patch.object(RUN_SUITE, "write_report", side_effect=record_write),
                self.assertRaisesRegex(RuntimeError, "synthetic failure"),
            ):
                RUN_SUITE.main()

            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(states[0], "running")
        self.assertEqual(states[-1], "failed")
        self.assertEqual(report["status"], "failed")

    def test_report_checkpoints_failed_calibration_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.write_bytes(b"same executable")
            candidate.write_bytes(b"same executable")
            datasets = root / "datasets"
            datasets.mkdir()
            (datasets / "data.csv").write_text("a,b\n", encoding="utf-8")
            calibration = root / "calibration.json"
            calibration.write_text("{}", encoding="utf-8")
            output = root / "report.json"
            states: list[str] = []
            real_write_report = RUN_SUITE.write_report

            def record_write(path: Path, report: dict[str, object]) -> None:
                states.append(str(report["status"]))
                real_write_report(path, report)

            arguments = [
                "run_suite.py",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--baseline-revision",
                "same",
                "--candidate-revision",
                "same",
                "--datasets",
                str(datasets),
                "--runs",
                "20",
                "--operations",
                "rows_cells",
                "--sources",
                "buffer",
                "--files",
                "data.csv",
                "--mode",
                "compare",
                "--calibration",
                str(calibration),
                "--compiler",
                "g++",
                "--compiler-flags=-O3",
                "--output",
                str(output),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    RUN_SUITE, "describe", return_value=self.driver_description()
                ),
                mock.patch.object(
                    RUN_SUITE,
                    "load_calibration",
                    return_value=(
                        {},
                        {"path": str(calibration), "sha256": "calibration"},
                        {},
                    ),
                ),
                mock.patch.object(
                    RUN_SUITE,
                    "validate_calibration_context",
                    side_effect=RuntimeError("context mismatch"),
                ),
                mock.patch.object(RUN_SUITE, "write_report", side_effect=record_write),
                self.assertRaisesRegex(RuntimeError, "context mismatch"),
            ):
                RUN_SUITE.main()

            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(states, ["running", "failed"])
        self.assertEqual(report["status"], "failed")

    def test_invoke_runs_a_fake_executable_and_parses_its_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake_benchmark.py"
            script.write_text(
                "import sys\n"
                "print('protocol=csv2-common-v1 revision=fake operation=rows_cells "
                "scope=traversal_only source=buffer bytes=4 iterations=2 elapsed_ns=8 "
                "rows=2 cells=4 row_bytes=4 checksum=9')\n"
                "print('diagnostic', file=sys.stderr)\n",
                encoding="utf-8",
            )
            result = RUN_SUITE.invoke(
                (Path(sys.executable), script),
                "rows_cells",
                Path("input.csv"),
                "buffer",
                2,
            )

        self.assertEqual(result["checksum"], "9")
        self.assertEqual(
            json.loads(result["_command"]),
            [
                sys.executable,
                str(script),
                "--operation",
                "rows_cells",
                "--input",
                "input.csv",
                "--source",
                "buffer",
                "--iterations",
                "2",
            ],
        )
        self.assertEqual(result["_stderr"], "diagnostic")


if __name__ == "__main__":
    unittest.main()
