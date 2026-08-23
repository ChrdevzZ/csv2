from __future__ import annotations

import json
import unittest
from pathlib import Path

import _support  # noqa: F401
from _schema_subset import ValidationError as SchemaValidationError
from _schema_subset import validate as validate_schema
from csv2bench import builds, protocol


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
    member = artifact()
    member["path"] = "artifact"
    return {
        "kind": "source-bundle",
        "root": "/source",
        "revision": "tool-bundle",
        "sha256": "b" * 64,
        "files": [member],
    }


def fixed_metrics_manifest(*, owned: bool = False) -> dict[str, object]:
    identities = {
        "collector": bundle(),
        "executable": artifact("candidate"),
        "allocation_executable": artifact("candidate"),
        "dataset": artifact(),
    }
    if owned:
        identities["compiler_executable"] = artifact()
        identities["compile_commands"] = artifact()
    return {
        "schema": "csv2-artifact-manifest-v3",
        "kind": "fixed-metrics",
        "report": artifact(),
        "inputs": {
            "artifacts": identities,
            "build": "c" * 64 if owned else None,
        },
    }


def evidence_bundle() -> dict[str, object]:
    checks = {
        "artifact_manifests": True,
        "calibration": True,
        "revisions": True,
        "source_tree": True,
        "compiler": True,
        "machine": True,
        "datasets": True,
        "corpus": True,
        "semantic_binding": True,
    }
    artifacts = {
        name: artifact()
        for name in (
            "calibration_report",
            "calibration_manifest",
            "comparison_report",
            "comparison_manifest",
            "fixed_metrics_report",
            "fixed_metrics_manifest",
            "corpus_manifest",
        )
    }
    component = {
        "schema": "csv2-benchmark-report-v5",
        "revision": "d" * 40,
        "build_digest": "a" * 64,
        "controlled_complete": False,
    }
    return {
        "schema": "csv2-performance-evidence-bundle-v2",
        "status": "completed",
        "evidence_level": "exploratory",
        "decision_eligible": False,
        "generated_at_utc": "now",
        "completed_at_utc": "later",
        "baseline_revision": "c" * 40,
        "candidate_revision": "d" * 40,
        "source_tree": "e" * 40,
        "compiler_sha256": "f" * 64,
        "machine": {
            "node": "host",
            "machine": "x86",
            "cpu_model": "cpu",
            "logical_cpus": 1,
            "process_affinity": [0],
            "python": "3.10",
        },
        "datasets": [{"name": "input.csv", "size": 1, "sha256": "b" * 64}],
        "comparison_binding": {
            "dataset": "input.csv",
            "semantic_case_id": "csv2.traversal.rows-cells.v1",
            "scope": "traversal_only",
            "source": "buffer",
            "byte_basis": "input_corpus",
        },
        "components": {
            "calibration": json.loads(json.dumps(component)),
            "comparison": json.loads(json.dumps(component)),
            "fixed_metrics": {
                **component,
                "schema": "csv2-fixed-machine-metrics-v5",
            },
        },
        "checks": checks,
        "artifacts": artifacts,
        "finalizer": bundle(),
    }


def evidence_manifest() -> dict[str, object]:
    report = evidence_bundle()
    return {
        "schema": "csv2-artifact-manifest-v3",
        "kind": "evidence-bundle",
        "report": artifact(),
        "inputs": {**report["artifacts"], "finalizer": report["finalizer"]},
    }


def invocation() -> dict[str, object]:
    return {"command": ["tool"], "stdout": "", "stderr": ""}


def comparison_report() -> dict[str, object]:
    revision = "candidate"
    side = {
        "artifact": artifact(revision),
        "build": None,
        "description": {
            "protocol": "csv2-common-v4",
            "revision": revision,
            "operations": "rows_cells",
            "sources": "buffer",
            "operation_contracts": (
                "rows_cells:traversal_only:buffer:"
                "csv2.traversal.rows-cells.v1:input_corpus"
            ),
        },
        "description_invocation": invocation(),
    }
    signature = ["1", "1", "1", "1", "1", "1"]

    throughput = 1_000_000_000.0 / float(1024**3)

    def launch(side_name: str, order: int) -> dict[str, object]:
        result = {
            "protocol": "csv2-common-v4",
            "revision": revision,
            "operation": "rows_cells",
            "scope": "traversal_only",
            "source": "buffer",
            "semantic_case_id": "csv2.traversal.rows-cells.v1",
            "byte_basis": "input_corpus",
            "bytes": "1",
            "iterations": "1",
            "elapsed_ns": "1",
            "rows": "1",
            "cells": "1",
            "row_bytes": "1",
            "checksum": "1",
            "timed_reader_steps": "2",
        }
        return {
            "phase": "sample",
            "round": 0,
            "order": order,
            "side": side_name,
            "command": ["driver"],
            "stdout": " ".join(f"{key}={value}" for key, value in result.items()),
            "stderr": "",
            "throughput_gib_per_second": throughput,
            "result": result,
        }

    case = {
        "dataset": "input.csv",
        "operation": "rows_cells",
        "source": "buffer",
        "semantic_case_id": "csv2.traversal.rows-cells.v1",
        "scope": "traversal_only",
        "byte_basis": "input_corpus",
        "semantic_signature": signature,
        "baseline": {"median": throughput, "mad": 0.0, "samples": [throughput]},
        "candidate": {"median": throughput, "mad": 0.0, "samples": [throughput]},
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
        "schema": "csv2-benchmark-report-v5",
        "artifact_mode": "external",
        "mode": "aa",
        "status": "completed",
        "evidence_level": "exploratory",
        "controlled_complete": False,
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
        "schema": "csv2-fixed-machine-metrics-v5",
        "artifact_mode": "external",
        "build": None,
        "status": "completed",
        "evidence_level": "exploratory",
        "controlled_complete": False,
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
        "operation": "traversal/rows-cells",
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
        "comparison_binding": {
            "dataset": "input.csv",
            "semantic_case_id": "csv2.traversal.rows-cells.v1",
            "scope": "traversal_only",
            "source": "buffer",
            "byte_basis": "input_corpus",
        },
        "verification": {
            "result": {
                "protocol": "csv2-current-v3",
                "revision": "candidate",
                "operation": "traversal/rows-cells",
                "source": "buffer",
                "dataset": "input.csv",
                "semantic_case_id": "csv2.traversal.rows-cells.v1",
                "scope": "traversal_only",
                "byte_basis": "input_corpus",
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
            "benchmark": "csv2/traversal/rows-cells/buffer/input.csv",
            "runs": 1,
            "samples": [
                {
                    "name": "csv2/traversal/rows-cells/buffer/input.csv",
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
    revision = "d" * 40
    adapter_commit = "e" * 40
    adapter_sha256 = "f" * 64
    for side_name in ("baseline", "candidate"):
        side = report[side_name]
        side["artifact"]["revision"] = revision
        side["description"]["revision"] = revision
    for launch in report["cases"][0]["launches"]:
        launch["result"]["revision"] = revision
        launch["stdout"] = " ".join(
            f"{key}={value}" for key, value in launch["result"].items()
        )
    report["adapter_source"] = artifact(adapter_commit)
    report["adapter_source"]["sha256"] = adapter_sha256
    report["artifact_mode"] = "owned"
    report["evidence_level"] = "controlled"
    report["controlled_complete"] = True
    report["decision_eligible"] = False
    report["compiler_flags"] = "-std=c++11 -O3 -DNDEBUG"
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
    sample = baseline_template["throughput_gib_per_second"]
    case["baseline"]["samples"] = [sample] * 20
    case["candidate"]["samples"] = [sample] * 20

    def git_export(
        root: str, commit: str, selection: str, path: str, sha256: str
    ) -> dict[str, object]:
        value: dict[str, object] = {
            "schema": "csv2-git-export-v1",
            "repository": "/repository",
            "reference": commit,
            "commit": commit,
            "tree": "a" * 40,
            "selections": [selection],
            "root": root,
            "files": [
                {
                    "mode": "100644",
                    "type": "blob",
                    "oid": "b" * 40,
                    "path": path,
                    "size": 1,
                    "sha256": sha256,
                }
            ],
        }
        value["digest"] = builds.document_digest(value)
        return value

    adapter_export = git_export(
        "/adapter",
        adapter_commit,
        "benchmark/compare/common_driver.cpp",
        "benchmark/compare/common_driver.cpp",
        adapter_sha256,
    )
    for side_name in ("baseline", "candidate"):
        output = json.loads(json.dumps(report[side_name]["artifact"]))
        build: dict[str, object] = {
            "schema": "csv2-benchmark-build-v1",
            "kind": "common-driver",
            "generated_at_utc": "now",
            "revision": revision,
            "header_export": git_export(
                f"/{side_name}-headers",
                revision,
                "include",
                "include/csv2/reader.hpp",
                "c" * 64,
            ),
            "adapter_export": adapter_export,
            "compiler": {
                "artifact": artifact(),
                "version": {
                    "command": ["c++", "--version"],
                    "returncode": 0,
                    "stdout": "compiler version",
                    "stderr": "",
                },
            },
            "compiler_flags": ["-std=c++11", "-O3", "-DNDEBUG"],
            "argv": [
                "/artifact",
                "-I/source",
                "adapter.cpp",
                "-o",
                f"/{side_name}",
                f"-D{revision}",
            ],
            "normalized_argv": [
                "/artifact",
                "-I{include_root}",
                "{adapter_source}",
                "-o",
                "{output}",
                "-D{revision}",
            ],
            "build_log": {"returncode": 0, "stdout": "", "stderr": ""},
            "output": output,
        }
        build["identity_digest"] = builds.common_build_identity_digest(build)
        build["digest"] = builds.document_digest(build)
        report[side_name]["build"] = build
    return report


def controlled_metrics_report() -> dict[str, object]:
    report = fixed_metrics_report()
    report["evidence_level"] = "controlled"
    report["controlled_complete"] = True
    report["decision_eligible"] = False
    report["artifact_mode"] = "owned"
    report["runs"] = 20
    report["compiler_flags"] = "-O3 -DNDEBUG"
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
    source: dict[str, object] = {
        "schema": "csv2-git-export-v1",
        "repository": "/repository",
        "reference": "candidate",
        "commit": "d" * 40,
        "tree": "a" * 40,
        "selections": ["<full-tree>"],
        "root": "/source",
        "files": [
            {
                "mode": "100644",
                "type": "blob",
                "oid": "b" * 40,
                "path": "CMakeLists.txt",
                "size": 1,
                "sha256": "c" * 64,
            }
        ],
    }
    source["digest"] = builds.document_digest(source)
    tool = {
        "artifact": artifact(),
        "version": {
            "command": ["tool", "--version"],
            "returncode": 0,
            "stdout": "version",
            "stderr": "",
        },
    }
    target_summaries = {
        name: {
            "sources": sorted(builds.CURRENT_SOURCES),
            "compile_fragments": "-O3 -DNDEBUG -std=c++23",
            "defines": [f'CSV2_BENCHMARK_REVISION=\\"{"d" * 40}\\"'],
            "includes": ["/source/include"],
            "artifact": report["artifacts"][artifact_name]["path"],
        }
        for name, artifact_name in (
            ("csv2_benchmark", "executable"),
            ("csv2_benchmark_allocations", "allocation_executable"),
        )
    }
    current_build: dict[str, object] = {
        "schema": "csv2-benchmark-build-v1",
        "kind": "current-tree",
        "generated_at_utc": "now",
        "revision": "d" * 40,
        "source_export": source,
        "compiler": tool,
        "compiler_flags": ["-O3", "-DNDEBUG"],
        "cmake": json.loads(json.dumps(tool)),
        "ninja": json.loads(json.dumps(tool)),
        "configure_argv": [
            "cmake", "-S", "/source", "-B", "/build", "/compiler", "d" * 40,
            "-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG",
        ],
        "normalized_configure_argv": [
            "cmake", "-S", "{source_root}", "-B", "{build_root}",
            "{compiler}", "{revision}",
            "-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG",
        ],
        "build_argv": ["cmake", "--build", "/build"],
        "configure_log": {"returncode": 0, "seconds": 1.0, "stdout": "", "stderr": ""},
        "build_log": {"returncode": 0, "seconds": 1.0, "stdout": "", "stderr": ""},
        "file_api": {
            "compiler": "/compiler",
            "targets": target_summaries,
            "link_commands": {
                "csv2_benchmark": ["c++ -o csv2_benchmark"],
                "csv2_benchmark_allocations": ["c++ -o csv2_benchmark_allocations"],
            },
        },
        "compile_commands": report["artifacts"]["compile_commands"],
        "targets": {
            "csv2_benchmark": report["artifacts"]["executable"],
            "csv2_benchmark_allocations": report["artifacts"]["allocation_executable"],
        },
        "corpus_manifest": artifact(),
        "source_root": "/source",
        "build_root": "/build",
    }
    for value in current_build["targets"].values():
        value["revision"] = "d" * 40
    report["artifacts"]["executable"]["revision"] = "d" * 40
    report["artifacts"]["allocation_executable"]["revision"] = "d" * 40
    report["verification"]["result"]["revision"] = "d" * 40
    current_build["identity_digest"] = builds.current_build_identity_digest(current_build)
    current_build["digest"] = builds.document_digest(current_build)
    report["build"] = current_build
    return report


class ProtocolTests(unittest.TestCase):
    def test_comparison_rejects_mutated_derived_truth(self) -> None:
        mutations = {
            "baseline median": lambda report: report["cases"][0]["baseline"].update(
                median=2.0
            ),
            "launch throughput": lambda report: report["cases"][0]["launches"][0].update(
                throughput_gib_per_second=2.0
            ),
            "raw stdout": lambda report: report["cases"][0]["launches"][0].update(
                stdout=report["cases"][0]["launches"][0]["stdout"].replace(
                    "checksum=1", "checksum=2"
                )
            ),
            "launch order": lambda report: report["cases"][0]["launches"][0].update(
                order=1
            ),
            "verdict": lambda report: report["cases"][0].update(regression=True),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                report = comparison_report()
                mutate(report)
                with self.assertRaises(RuntimeError):
                    protocol.validate_comparison_report(report)

    def test_comparison_mode_requires_distinct_revisions(self) -> None:
        report = comparison_report()
        report["mode"] = "compare"
        with self.assertRaisesRegex(RuntimeError, "different revisions"):
            protocol.validate_comparison_report(report)

    def test_fixed_metrics_rejects_mutated_timing_summary(self) -> None:
        report = fixed_metrics_report()
        report["timing"]["bytes_per_second"]["median"] = 2.0
        with self.assertRaisesRegex(RuntimeError, "median"):
            protocol.validate_fixed_metrics_report(report)

    def test_completed_reports_pass_semantic_validation(self) -> None:
        protocol.validate_comparison_report(comparison_report())
        protocol.validate_fixed_metrics_report(fixed_metrics_report())
        controlled_comparison = controlled_comparison_report()
        for side in ("baseline", "candidate"):
            build = controlled_comparison[side]["build"]
            build["compiler"]["artifact"]["revision"] = "compiler"
            build.pop("digest")
            build["digest"] = builds.document_digest(build)
        protocol.validate_comparison_report(controlled_comparison)
        protocol.validate_fixed_metrics_report(controlled_metrics_report())
        protocol.validate_evidence_bundle(evidence_bundle())

    def test_empty_eligible_reports_and_unknown_top_level_fields_are_rejected(self) -> None:
        comparison = controlled_comparison_report()
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

    def test_owned_current_build_rejects_provenance_drift(self) -> None:
        mutations = (
            (
                "revision",
                lambda report: report["build"].update(revision="e" * 40),
            ),
            (
                "source set",
                lambda report: report["build"]["file_api"]["targets"][
                    "csv2_benchmark"
                ]["sources"].pop(),
            ),
            (
                "link command",
                lambda report: report["build"]["file_api"]["link_commands"].update(
                    csv2_benchmark=[]
                ),
            ),
            (
                "normalized configure",
                lambda report: report["build"]["normalized_configure_argv"].__setitem__(
                    2, "/wrong-source"
                ),
            ),
            (
                "compiler flags",
                lambda report: report["build"]["compiler_flags"].append("-fno-inline"),
            ),
            (
                "compiler",
                lambda report: report["build"]["compiler"]["artifact"].update(
                    sha256="0" * 64
                ),
            ),
            (
                "output",
                lambda report: report["build"]["targets"]["csv2_benchmark"].update(
                    sha256="0" * 64
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                report = controlled_metrics_report()
                mutate(report)
                with self.assertRaises(RuntimeError):
                    protocol.validate_fixed_metrics_report(report)

        report = controlled_metrics_report()
        report["compiler_flags"] = "-O0"
        with self.assertRaisesRegex(RuntimeError, "compiler_flags differ"):
            protocol.validate_fixed_metrics_report(report)

        comparison = controlled_comparison_report()
        comparison["compiler_flags"] = "-O0"
        with self.assertRaisesRegex(RuntimeError, "compiler_flags differ"):
            protocol.validate_comparison_report(comparison)

    def test_v4_component_reports_are_explicitly_rejected(self) -> None:
        comparison = comparison_report()
        comparison["schema"] = "csv2-benchmark-report-v4"
        with self.assertRaisesRegex(RuntimeError, "unsupported schema"):
            protocol.validate_comparison_report(comparison)
        metrics = fixed_metrics_report()
        metrics["schema"] = "csv2-fixed-machine-metrics-v4"
        with self.assertRaisesRegex(RuntimeError, "unsupported schema"):
            protocol.validate_fixed_metrics_report(metrics)

    def test_artifact_manifest_v3_rejects_old_or_incomplete_inputs(self) -> None:
        manifest = {
            "schema": "csv2-artifact-manifest-v3",
            "kind": "comparison",
            "report": artifact(),
            "inputs": {
                "baseline": artifact("base"),
                "candidate": artifact("candidate"),
                "datasets": [artifact()],
                "builds": {"baseline": "a" * 64, "candidate": "b" * 64},
            },
        }
        protocol.validate_artifact_manifest(manifest)
        schema_root = Path(__file__).resolve().parents[2] / "protocol" / "schemas"
        schema = json.loads(
            (schema_root / "artifact-manifest-v3.schema.json").read_text(
                encoding="utf-8"
            )
        )
        validate_schema(manifest, schema)
        protocol.validate_artifact_manifest(evidence_manifest())
        validate_schema(evidence_manifest(), schema)
        manifest["schema"] = "csv2-artifact-manifest-v2"
        with self.assertRaisesRegex(RuntimeError, "unsupported schema"):
            protocol.validate_artifact_manifest(manifest)

    def test_fixed_metrics_artifact_manifest_is_closed_and_complete(self) -> None:
        schema_root = Path(__file__).resolve().parents[2] / "protocol" / "schemas"
        schema = json.loads(
            (schema_root / "artifact-manifest-v3.schema.json").read_text(
                encoding="utf-8"
            )
        )
        for owned in (False, True):
            with self.subTest(owned=owned):
                manifest = fixed_metrics_manifest(owned=owned)
                protocol.validate_artifact_manifest(manifest)
                validate_schema(manifest, schema)

        structural_mutations = {
            "unknown input": lambda value: value["inputs"].__setitem__(
                "unexpected", True
            ),
            "empty artifacts": lambda value: value["inputs"].__setitem__(
                "artifacts", {}
            ),
            "missing collector": lambda value: value["inputs"]["artifacts"].pop(
                "collector"
            ),
            "unknown artifact": lambda value: value["inputs"]["artifacts"].__setitem__(
                "unexpected", artifact()
            ),
            "invalid digest": lambda value: value["inputs"]["artifacts"][
                "dataset"
            ].__setitem__("sha256", "not-a-digest"),
            "compiler without commands": lambda value: value["inputs"][
                "artifacts"
            ].__setitem__("compiler_executable", artifact()),
        }
        for label, mutate in structural_mutations.items():
            with self.subTest(label=label):
                manifest = fixed_metrics_manifest()
                mutate(manifest)
                with self.assertRaises(RuntimeError):
                    protocol.validate_artifact_manifest(manifest)
                with self.assertRaises(SchemaValidationError):
                    validate_schema(manifest, schema)

        manifest = fixed_metrics_manifest()
        manifest["inputs"]["artifacts"]["allocation_executable"]["revision"] = "other"
        with self.assertRaisesRegex(RuntimeError, "revisions are inconsistent"):
            protocol.validate_artifact_manifest(manifest)

        manifest = fixed_metrics_manifest()
        manifest["inputs"]["build"] = "c" * 64
        with self.assertRaisesRegex(RuntimeError, "requires compiler artifacts"):
            protocol.validate_artifact_manifest(manifest)
        with self.assertRaises(SchemaValidationError):
            validate_schema(manifest, schema)

    def test_comparison_uses_declared_operation_contracts(self) -> None:
        report = comparison_report()
        report["candidate"]["description"]["operation_contracts"] = (
            "rows_cells:writer_only:buffer:"
            "csv2.traversal.rows-cells.v1:input_corpus"
        )
        with self.assertRaisesRegex(RuntimeError, "scope differs"):
            protocol.validate_comparison_report(report)

        report = comparison_report()
        del report["cases"][0]["launches"][0]["result"]["timed_reader_steps"]
        with self.assertRaisesRegex(RuntimeError, "timed_reader_steps"):
            protocol.validate_comparison_report(report)

    def test_semantic_bindings_are_closed_and_derived_from_wires(self) -> None:
        report = comparison_report()
        report["cases"][0]["semantic_case_id"] = "csv2.other.v1"
        with self.assertRaisesRegex(RuntimeError, "semantic_case_id"):
            protocol.validate_comparison_report(report)

        report = comparison_report()
        report["cases"][0]["launches"][0]["result"]["byte_basis"] = "output"
        with self.assertRaisesRegex(RuntimeError, "byte basis"):
            protocol.validate_comparison_report(report)

        metrics = fixed_metrics_report()
        metrics["comparison_binding"]["scope"] = "writer_only"
        with self.assertRaisesRegex(RuntimeError, "binding differs"):
            protocol.validate_fixed_metrics_report(metrics)

    def test_schemas_close_the_top_level_and_require_controlled_evidence(self) -> None:
        schema_root = Path(__file__).resolve().parents[2] / "protocol" / "schemas"
        comparison = json.loads(
            (schema_root / "comparison-v5.schema.json").read_text(encoding="utf-8")
        )
        metrics = json.loads(
            (schema_root / "fixed-machine-v5.schema.json").read_text(encoding="utf-8")
        )
        build = json.loads(
            (schema_root / "build-v1.schema.json").read_text(encoding="utf-8")
        )
        artifact_manifest = json.loads(
            (schema_root / "artifact-manifest-v3.schema.json").read_text(encoding="utf-8")
        )
        evidence = json.loads(
            (schema_root / "evidence-bundle-v2.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(comparison["additionalProperties"])
        self.assertFalse(metrics["additionalProperties"])
        self.assertEqual(len(build["oneOf"]), 2)
        self.assertFalse(build["$defs"]["common_driver"]["additionalProperties"])
        self.assertFalse(build["$defs"]["current_tree"]["additionalProperties"])
        self.assertFalse(artifact_manifest["additionalProperties"])
        self.assertEqual(len(artifact_manifest["oneOf"]), 3)
        self.assertFalse(evidence["additionalProperties"])
        self.assertEqual(
            evidence["properties"]["schema"]["const"],
            "csv2-performance-evidence-bundle-v2",
        )
        validate_schema(evidence_bundle(), evidence)
        controlled_bundle = evidence_bundle()
        controlled_bundle["evidence_level"] = "controlled"
        controlled_bundle["decision_eligible"] = True
        for component in controlled_bundle["components"].values():
            component["controlled_complete"] = True
        validate_schema(controlled_bundle, evidence)
        invalid_bundle = evidence_bundle()
        invalid_bundle["decision_eligible"] = True
        with self.assertRaises(SchemaValidationError):
            validate_schema(invalid_bundle, evidence)
        incomplete_controlled = evidence_bundle()
        incomplete_controlled["evidence_level"] = "controlled"
        incomplete_controlled["decision_eligible"] = True
        with self.assertRaises(SchemaValidationError):
            validate_schema(incomplete_controlled, evidence)
        self.assertFalse(
            artifact_manifest["$defs"]["fixed_metrics_inputs"][
                "additionalProperties"
            ]
        )
        self.assertFalse(
            artifact_manifest["$defs"]["fixed_metrics_artifacts"][
                "additionalProperties"
            ]
        )
        self.assertEqual(
            artifact_manifest["$defs"]["fixed_metrics_artifacts"][
                "dependentRequired"
            ]["compiler_executable"],
            ["compile_commands"],
        )
        self.assertEqual(comparison["properties"]["schema"]["const"], "csv2-benchmark-report-v5")
        self.assertEqual(metrics["properties"]["schema"]["const"], "csv2-fixed-machine-metrics-v5")
        self.assertEqual(
            build["$defs"]["current_tree"]["properties"]["schema"]["const"],
            "csv2-benchmark-build-v1",
        )
        self.assertIn("compiler_flags", build["$defs"]["current_tree"]["required"])
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

    def test_only_completed_owned_controlled_reports_are_component_complete(self) -> None:
        self.assertTrue(protocol.controlled_complete("controlled", "completed"))
        for evidence, status in (
            ("controlled", "running"),
            ("controlled", "failed"),
            ("exploratory", "completed"),
        ):
            with self.subTest(evidence=evidence, status=status):
                self.assertFalse(protocol.controlled_complete(evidence, status))

    def test_component_reports_cannot_claim_final_decision_eligibility(self) -> None:
        for validator, report in (
            (protocol.validate_comparison_report, controlled_comparison_report()),
            (protocol.validate_fixed_metrics_report, controlled_metrics_report()),
        ):
            with self.subTest(schema=report["schema"]):
                report["decision_eligible"] = True
                with self.assertRaisesRegex(RuntimeError, "cannot claim final"):
                    validator(report)

        bundle_value = evidence_bundle()
        bundle_value["components"]["comparison"]["revision"] = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "differs from the candidate"):
            protocol.validate_evidence_bundle(bundle_value)

        old_bundle = evidence_bundle()
        old_bundle["schema"] = "csv2-performance-evidence-bundle-v1"
        with self.assertRaisesRegex(RuntimeError, "unsupported schema"):
            protocol.validate_evidence_bundle(old_bundle)

        bundle_value = evidence_bundle()
        bundle_value["components"]["comparison"]["build_digest"] = "e" * 64
        with self.assertRaisesRegex(RuntimeError, "candidate builds differ"):
            protocol.validate_evidence_bundle(bundle_value)

        for unsafe in ("../artifact", "C:/artifact", r"..\artifact", "/artifact"):
            with self.subTest(path=unsafe):
                bundle_value = evidence_bundle()
                bundle_value["finalizer"]["files"][0]["path"] = unsafe
                with self.assertRaisesRegex(RuntimeError, "safe relative path"):
                    protocol.validate_evidence_bundle(bundle_value)

    def test_common_v4_is_accepted_and_v3_is_rejected(self) -> None:
        result = protocol.parse_common(
            "protocol=csv2-common-v4 revision=x", {"revision"}
        )
        self.assertEqual(result["revision"], "x")
        with self.assertRaisesRegex(RuntimeError, "expected csv2-common-v4"):
            protocol.parse_common(
                "protocol=csv2-common-v3 revision=x", {"revision"}
            )

    def test_operation_contracts_are_strict_and_self_describing(self) -> None:
        contracts = protocol.parse_operation_contracts(
            "rows_cells:traversal_only:buffer+mmap:"
            "csv2.traversal.rows-cells.v1:input_corpus;"
            "writer_raw_direct:writer_only:buffer:"
            "csv2.writer.raw-direct.v1:input_corpus"
        )
        self.assertEqual(contracts["rows_cells"][0], "traversal_only")
        self.assertEqual(contracts["rows_cells"][1], frozenset({"buffer", "mmap"}))
        with self.assertRaisesRegex(RuntimeError, "duplicate operation contract"):
            protocol.parse_operation_contracts(
                "rows_cells:traversal_only:buffer:csv2.rows.v1:input_corpus;"
                "rows_cells:traversal_only:mmap:csv2.rows.v1:input_corpus"
            )
        with self.assertRaisesRegex(RuntimeError, "unsupported operation scope"):
            protocol.parse_operation_contracts(
                "rows_cells:guessed:buffer:csv2.rows.v1:input_corpus"
            )

    def test_current_v3_parses_exact_uint64_fields(self) -> None:
        output = (
            "protocol=csv2-current-v3 revision=r operation=traversal/rows "
            "source=buffer dataset=x.csv semantic_case_id=csv2.traversal.rows.v1 "
            "scope=traversal_only byte_basis=input_corpus "
            "checksum=18446744073709551615 "
            "bytes=4 rows=1 cells=0 allocations=0 allocated_bytes=0"
        )
        result = protocol.parse_current(output)
        self.assertEqual(result["checksum"], "18446744073709551615")
        with self.assertRaisesRegex(RuntimeError, "expected csv2-current-v3"):
            protocol.parse_current(output.replace("csv2-current-v3", "csv2-current-v2"))

    def test_current_rejects_overflow_duplicate_and_missing_fields(self) -> None:
        valid = (
            "protocol=csv2-current-v3 revision=r operation=o source=buffer dataset=x "
            "semantic_case_id=csv2.o.v1 scope=source_only byte_basis=input_corpus "
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
