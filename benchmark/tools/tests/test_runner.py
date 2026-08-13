from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import _support  # noqa: F401
from csv2bench import runner


def result(revision: str, elapsed: int = 100) -> dict[str, str]:
    return {
        "protocol": "csv2-common-v3",
        "revision": revision,
        "operation": "rows_cells",
        "scope": "traversal_only",
        "source": "buffer",
        "bytes": "4",
        "iterations": "1",
        "elapsed_ns": str(elapsed),
        "rows": "1",
        "cells": "2",
        "row_bytes": "3",
        "checksum": "42",
        "timed_reader_steps": "3",
    }


class RunnerTests(unittest.TestCase):
    def test_parser_rejects_old_common_protocol(self) -> None:
        line = " ".join(f"{key}={value}" for key, value in result("x").items())
        self.assertEqual(runner.parse_output(line)["revision"], "x")
        with self.assertRaisesRegex(RuntimeError, "unsupported benchmark protocol"):
            runner.parse_output(line.replace("csv2-common-v3", "csv2-common-v2"))

    def test_selection_rejects_unknown_duplicate_and_empty_entries(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown"):
            runner.selected("missing", ("one", "two"))
        with self.assertRaisesRegex(ValueError, "duplicates"):
            runner.selected("one,one", ("one", "two"))
        with self.assertRaisesRegex(ValueError, "empty"):
            runner.selected("one,", ("one", "two"))

    def test_measurement_alternates_launch_order_and_preserves_semantics(self) -> None:
        launches: list[str] = []

        def invoke(executable, operation, dataset, source, iterations):
            side = str(executable)
            launches.append(side)
            return result("base" if side == "base" else "candidate", 100)

        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "data.csv"
            dataset.write_bytes(b"a,b\n")
            case = runner.measure_case(
                Path("base"),
                Path("candidate"),
                "rows_cells",
                dataset,
                "buffer",
                runs=2,
                iterations=1,
                warmups=0,
                expected_scope="traversal_only",
                calibration_noise=0.0,
                baseline_revision="base",
                candidate_revision="candidate",
                invoke_fn=invoke,
            )
        self.assertEqual(launches, ["base", "candidate", "candidate", "base"])
        self.assertFalse(case["regression"])

    def test_writer_only_result_rejects_timed_reader_work(self) -> None:
        writer_result = result("candidate")
        writer_result.update(
            operation="writer_raw_direct",
            scope="writer_only",
            timed_reader_steps="1",
        )
        with self.assertRaisesRegex(RuntimeError, "Reader state"):
            runner.validate_result(
                writer_result,
                "writer_raw_direct",
                "buffer",
                1,
                expected_scope="writer_only",
                expected_bytes=4,
                expected_revision="candidate",
            )

    def test_calibration_rejects_v3_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(
                json.dumps(
                    {"schema": "csv2-benchmark-report-v3", "mode": "aa", "status": "completed"}
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "completed A/A"):
                runner.load_calibration(path)

    def test_calibration_runs_full_semantic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "csv2-benchmark-report-v4",
                        "mode": "aa",
                        "status": "completed",
                    }
                ),
                encoding="utf-8",
            )
            with unittest.mock.patch.object(
                runner.wire,
                "validate_comparison_report",
                side_effect=RuntimeError("incomplete controlled evidence"),
            ) as validator:
                with self.assertRaisesRegex(RuntimeError, "incomplete controlled evidence"):
                    runner.load_calibration(path)
            validator.assert_called_once()

    def test_calibration_rejects_affinity_mismatch(self) -> None:
        calibration = {
            "artifact_mode": "external",
            "compiler": "c++",
            "compiler_flags": "-O3",
            "runs": 20,
            "iterations_per_run": 10,
            "warmups": 3,
            "host": {
                "platform": "linux",
                "node": "host",
                "machine": "x86_64",
                "processor": "cpu",
                "cpu_model": "model",
                "cpu_model_source": "test",
                "logical_cpus": 2,
                "process_affinity": [0],
                "python": "3.10",
            },
            "runner": {"sha256": "runner"},
            "adapter_source": {"sha256": "adapter"},
            "candidate": {"artifact": {"sha256": "candidate"}},
            "datasets": [],
        }
        current = json.loads(json.dumps(calibration))
        current["host"]["process_affinity"] = [1]
        with self.assertRaisesRegex(RuntimeError, "process_affinity"):
            runner.validate_calibration_context(calibration, current)

    def test_calibration_rejects_tool_bundle_drift(self) -> None:
        calibration = {
            "artifact_mode": "external",
            "compiler": "c++",
            "compiler_flags": "-O3",
            "runs": 20,
            "iterations_per_run": 10,
            "warmups": 3,
            "host": {
                "platform": "linux",
                "node": "host",
                "machine": "x86_64",
                "processor": "cpu",
                "cpu_model": "model",
                "cpu_model_source": "test",
                "logical_cpus": 2,
                "process_affinity": [0],
                "python": "3.10",
            },
            "runner": {"sha256": "old-tool-bundle"},
            "adapter_source": {"sha256": "adapter"},
            "candidate": {"artifact": {"sha256": "candidate"}},
            "datasets": [],
        }
        current = json.loads(json.dumps(calibration))
        current["runner"]["sha256"] = "new-tool-bundle"
        with self.assertRaisesRegex(RuntimeError, "runner.sha256"):
            runner.validate_calibration_context(calibration, current)


if __name__ == "__main__":
    unittest.main()
