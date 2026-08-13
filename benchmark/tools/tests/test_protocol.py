from __future__ import annotations

import json
import unittest
from pathlib import Path

import _support  # noqa: F401
from csv2bench import protocol


def artifact(revision: str | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "path": "/artifact",
        "size": 1,
        "sha256": "a" * 64,
        "mtime_ns": 1,
    }
    if revision is not None:
        value["revision"] = revision
    return value


def bundle() -> dict[str, object]:
    return {
        "kind": "source-bundle",
        "root": "/source",
        "revision": "tool-bundle",
        "sha256": "b" * 64,
        "files": [artifact()],
    }


def invocation() -> dict[str, object]:
    return {"command": ["tool"], "stdout": "", "stderr": ""}


def comparison_report() -> dict[str, object]:
    revision = "candidate"
    side = {
        "artifact": artifact(revision),
        "description": {
            "protocol": "csv2-common-v2",
            "revision": revision,
            "operations": "rows_cells",
            "sources": "buffer",
        },
        "description_invocation": invocation(),
    }
    signature = ["1", "1", "1", "1", "1", "1"]

    def launch(side_name: str, order: int) -> dict[str, object]:
        return {
            "phase": "sample",
            "round": 0,
            "order": order,
            "side": side_name,
            "command": ["driver"],
            "stdout": "result",
            "stderr": "",
            "throughput_gib_per_second": 1.0,
            "result": {
                "protocol": "csv2-common-v2",
                "revision": revision,
                "operation": "rows_cells",
                "scope": "traversal_only",
                "source": "buffer",
                "bytes": "1",
                "iterations": "1",
                "elapsed_ns": "1",
                "rows": "1",
                "cells": "1",
                "row_bytes": "1",
                "checksum": "1",
            },
        }

    case = {
        "dataset": "input.csv",
        "operation": "rows_cells",
        "source": "buffer",
        "semantic_signature": signature,
        "baseline": {"median": 1.0, "mad": 0.0, "samples": [1.0]},
        "candidate": {"median": 1.0, "mad": 0.0, "samples": [1.0]},
        "candidate_over_baseline_95pct": [1.0, 1.0],
        "measured_noise": 0.0,
        "calibration_noise": 0.0,
        "observed_noise": 0.0,
        "regression_threshold": 0.05,
        "regression": False,
        "improvement": False,
        "launches": [launch("baseline", 0), launch("candidate", 1)],
    }
    return {
        "schema": "csv2-benchmark-report-v3",
        "mode": "aa",
        "status": "completed",
        "evidence_level": "exploratory",
        "decision_eligible": False,
        "generated_at_utc": "now",
        "completed_at_utc": "later",
        "runs": 1,
        "warmups": 0,
        "iterations_per_run": 1,
        "compiler": "c++",
        "compiler_flags": "",
        "host": {
            "platform": "test",
            "node": "host",
            "machine": "x86",
            "processor": "cpu",
            "cpu_model": "cpu",
            "cpu_model_source": "test",
            "logical_cpus": 1,
            "process_affinity": None,
            "python": "3.10",
        },
        "runner": bundle(),
        "adapter_source": artifact("shared-source"),
        "baseline": side,
        "candidate": json.loads(json.dumps(side)),
        "datasets": [
            {"name": "input.csv", "path": "/input.csv", "size": 1, "sha256": "c" * 64}
        ],
        "calibration": None,
        "cases": [case],
    }


def fixed_metrics_report() -> dict[str, object]:
    return {
        "schema": "csv2-fixed-machine-metrics-v3",
        "status": "completed",
        "evidence_level": "exploratory",
        "decision_eligible": False,
        "generated_at_utc": "now",
        "completed_at_utc": "later",
        "machine": {
            "system": "test",
            "release": "1",
            "machine": "x86",
            "node": "host",
            "cpu_model": "cpu",
            "cpu_model_source": "test",
            "logical_cpus": 1,
            "process_affinity": None,
            "python": "3.10",
        },
        "compiler": "c++",
        "compiler_identity": None,
        "compiler_flags": "",
        "operation": "traversal/rows",
        "source": "buffer",
        "runs": 1,
        "artifacts": {
            "collector": bundle(),
            "executable": artifact("candidate"),
            "allocation_executable": artifact("candidate"),
            "dataset": artifact(),
        },
        "clean_build": None,
        "post_build": None,
        "verification": {
            "result": {
                "protocol": "csv2-current-v2",
                "revision": "candidate",
                "operation": "traversal/rows",
                "source": "buffer",
                "dataset": "input.csv",
                "checksum": "1",
                "bytes": "1",
                "rows": "1",
                "cells": "1",
                "allocations": "0",
                "allocated_bytes": "0",
            },
            "invocation": invocation(),
        },
        "allocations": {"count": 0, "bytes": 0, "invocation": invocation()},
        "timing": {
            "benchmark": "csv2/traversal/rows/buffer/input.csv",
            "runs": 1,
            "samples": [
                {
                    "name": "csv2/traversal/rows/buffer/input.csv",
                    "seconds": 1.0,
                    "bytes_per_second": 1.0,
                    "items_per_second": 1.0,
                }
            ],
            "bytes_per_second": {"median": 1.0, "mad": 0.0},
            "seconds": {"median": 1.0, "mad": 0.0},
        },
        "timing_invocation": invocation(),
    }


def controlled_comparison_report() -> dict[str, object]:
    report = comparison_report()
    report["evidence_level"] = "controlled"
    report["decision_eligible"] = True
    report["runs"] = 20
    report["warmups"] = 3
    report["host"]["process_affinity"] = [0]
    case = report["cases"][0]
    baseline_template = case["launches"][0]
    candidate_template = case["launches"][1]
    launches = []
    for phase, count in (("warmup", 3), ("sample", 20)):
        for round_index in range(count):
            for order, template in enumerate(
                (baseline_template, candidate_template)
                if round_index % 2 == 0
                else (candidate_template, baseline_template)
            ):
                launch = json.loads(json.dumps(template))
                launch["phase"] = phase
                launch["round"] = round_index
                launch["order"] = order
                launches.append(launch)
    case["launches"] = launches
    case["baseline"]["samples"] = [1.0] * 20
    case["candidate"]["samples"] = [1.0] * 20
    return report


def controlled_metrics_report() -> dict[str, object]:
    report = fixed_metrics_report()
    report["evidence_level"] = "controlled"
    report["decision_eligible"] = True
    report["runs"] = 20
    report["machine"]["process_affinity"] = [0]
    report["timing"]["runs"] = 20
    report["timing"]["samples"] = report["timing"]["samples"] * 20
    compiler = artifact()
    report["compiler_identity"] = {
        "artifact": compiler,
        "compile_command_matches": 1,
        "version_command": ["c++", "--version"],
        "version_stdout": "compiler version",
        "version_stderr": "",
    }
    report["artifacts"]["compiler_executable"] = json.loads(json.dumps(compiler))
    report["artifacts"]["compile_commands"] = artifact()
    report["clean_build"] = {
        "command": ["cmake", "--build", "build"],
        "seconds": 1.0,
        "stdout": "",
        "stderr": "",
    }
    report["post_build"] = invocation()
    report["pmu"] = json.loads(json.dumps(report["timing"]))
    for sample in report["pmu"]["samples"]:
        sample["pmu"] = {
            "cycles": 1.0,
            "instructions": 1.0,
            "branch-misses": 0.0,
        }
    report["pmu_invocation"] = invocation()
    report["peak_rss"] = {
        "scope": "whole_process",
        "kib": 1,
        "command": ["time"],
        "stdout": "",
        "stderr": "",
    }
    report["code_size"] = {
        "text_bytes": 1,
        "data_bytes": 1,
        "bss_bytes": 1,
        "total_bytes": 3,
        "command": ["size"],
    }
    return report


class ProtocolTests(unittest.TestCase):
    def test_completed_reports_pass_semantic_validation(self) -> None:
        protocol.validate_comparison_report(comparison_report())
        protocol.validate_fixed_metrics_report(fixed_metrics_report())
        protocol.validate_comparison_report(controlled_comparison_report())
        protocol.validate_fixed_metrics_report(controlled_metrics_report())

    def test_empty_eligible_reports_and_unknown_top_level_fields_are_rejected(self) -> None:
        comparison = comparison_report()
        comparison["evidence_level"] = "controlled"
        comparison["decision_eligible"] = True
        comparison["runs"] = 20
        comparison["warmups"] = 3
        comparison["host"]["process_affinity"] = [0]
        comparison["datasets"] = []
        comparison["cases"] = []
        with self.assertRaisesRegex(RuntimeError, "requires datasets and cases"):
            protocol.validate_comparison_report(comparison)

        metrics = fixed_metrics_report()
        metrics["unknown"] = True
        with self.assertRaisesRegex(RuntimeError, "unknown fields"):
            protocol.validate_fixed_metrics_report(metrics)

    def test_controlled_metrics_require_complete_machine_evidence(self) -> None:
        report = controlled_metrics_report()
        report["compiler_identity"] = {}
        with self.assertRaisesRegex(RuntimeError, "compiler_identity"):
            protocol.validate_fixed_metrics_report(report)

    def test_controlled_reports_reject_empty_evidence_sections(self) -> None:
        for field in ("allocations", "clean_build", "post_build", "pmu", "peak_rss", "code_size"):
            with self.subTest(field=field):
                report = controlled_metrics_report()
                report[field] = {}
                with self.assertRaises(RuntimeError):
                    protocol.validate_fixed_metrics_report(report)

        comparison = controlled_comparison_report()
        comparison["cases"][0]["baseline"] = {}
        with self.assertRaisesRegex(RuntimeError, "baseline"):
            protocol.validate_comparison_report(comparison)
        comparison = controlled_comparison_report()
        comparison["cases"][0]["launches"][0] = {}
        with self.assertRaisesRegex(RuntimeError, "launches"):
            protocol.validate_comparison_report(comparison)

    def test_schemas_close_the_top_level_and_require_controlled_evidence(self) -> None:
        schema_root = Path(__file__).resolve().parents[2] / "protocol" / "schemas"
        comparison = json.loads(
            (schema_root / "comparison-v3.schema.json").read_text(encoding="utf-8")
        )
        metrics = json.loads(
            (schema_root / "fixed-machine-v3.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(comparison["additionalProperties"])
        self.assertFalse(metrics["additionalProperties"])
        self.assertIn("runner", comparison["required"])
        self.assertIn("clean_build", metrics["required"])
        self.assertIn("post_build", metrics["required"])
        self.assertEqual(
            comparison["$defs"]["case"]["properties"]["baseline"]["$ref"],
            "#/$defs/sample_statistics",
        )
        self.assertEqual(
            metrics["properties"]["allocations"]["$ref"],
            "#/$defs/allocations",
        )
        self.assertTrue(
            any(
                "pmu" in item.get("then", {}).get("required", [])
                for item in metrics["allOf"]
            )
        )

    def test_only_completed_controlled_reports_are_decision_eligible(self) -> None:
        self.assertTrue(protocol.decision_eligible("controlled", "completed"))
        for evidence, status in (
            ("controlled", "running"),
            ("controlled", "failed"),
            ("exploratory", "completed"),
        ):
            with self.subTest(evidence=evidence, status=status):
                self.assertFalse(protocol.decision_eligible(evidence, status))

    def test_common_v2_is_accepted_and_v1_is_rejected(self) -> None:
        result = protocol.parse_common(
            "protocol=csv2-common-v2 revision=x", {"revision"}
        )
        self.assertEqual(result["revision"], "x")
        with self.assertRaisesRegex(RuntimeError, "expected csv2-common-v2"):
            protocol.parse_common(
                "protocol=csv2-common-v1 revision=x", {"revision"}
            )

    def test_current_v2_parses_exact_uint64_fields(self) -> None:
        output = (
            "protocol=csv2-current-v2 revision=r operation=traversal/rows "
            "source=buffer dataset=x.csv checksum=18446744073709551615 "
            "bytes=4 rows=1 cells=0 allocations=0 allocated_bytes=0"
        )
        result = protocol.parse_current(output)
        self.assertEqual(result["checksum"], "18446744073709551615")

    def test_current_rejects_overflow_duplicate_and_missing_fields(self) -> None:
        valid = (
            "protocol=csv2-current-v2 revision=r operation=o source=buffer dataset=x "
            "checksum=1 bytes=1 rows=1 cells=1 allocations=0 allocated_bytes=0"
        )
        with self.assertRaisesRegex(RuntimeError, "outside uint64"):
            protocol.parse_current(valid.replace("checksum=1", f"checksum={1 << 64}"))
        with self.assertRaisesRegex(RuntimeError, "duplicate key"):
            protocol.parse_current(valid + " checksum=2")
        with self.assertRaisesRegex(RuntimeError, "missing required fields: cells"):
            protocol.parse_current(valid.replace(" cells=1", ""))

    def test_non_finite_timing_values_are_rejected(self) -> None:
        for value in ("nan", "inf", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "finite and non-negative"):
                    protocol.finite_nonnegative(value, "sample")


if __name__ == "__main__":
    unittest.main()
