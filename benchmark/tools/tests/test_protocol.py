from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import _support  # noqa: F401
from _schema_subset import ValidationError as SchemaValidationError
from _schema_subset import validate as validate_schema
from csv2bench import builds, derivation, metrics, protocol


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


def machine_profile() -> dict[str, object]:
    return {
        "artifact": artifact(),
        "digest": "a" * 64,
        "profile": {
            "schema": "csv2-machine-profile-v1",
            "id": "test-machine",
            "system": "Linux",
            "architecture": "x86",
            "cpu_model": "cpu",
            "logical_cpus": 1,
            "allowed_affinity": [0],
            "kernel_release": "1",
            "governor": "performance",
            "turbo_boost": "disabled",
        },
        "observation": {
            "system": "Linux",
            "architecture": "x86",
            "cpu_model": "cpu",
            "logical_cpus": 1,
            "process_affinity": [0],
            "kernel_release": "1",
            "governor": "performance",
            "turbo_boost": "disabled",
        },
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
        "schema": "csv2-artifact-manifest-v4",
        "kind": "fixed-metrics",
        "report": artifact(),
        "inputs": {
            "artifacts": identities,
            "build": "c" * 64 if owned else None,
            "machine_profile": None,
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
        "machine_profile": True,
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
        "schema": "csv2-benchmark-report-v7",
        "revision": "d" * 40,
        "build_digest": "a" * 64,
        "controlled_complete": False,
    }
    return {
        "schema": "csv2-performance-evidence-bundle-v4",
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
        "machine_profile": None,
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
                "schema": "csv2-fixed-machine-metrics-v8",
            },
        },
        "checks": checks,
        "artifacts": artifacts,
        "finalizer": bundle(),
    }


def evidence_manifest() -> dict[str, object]:
    report = evidence_bundle()
    return {
        "schema": "csv2-artifact-manifest-v4",
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
            "protocol": "csv2-common-v5",
            "revision": revision,
            "instrumentation": "none",
            "capabilities": "legacy-reader,legacy-writer",
            "operations": "rows_cells",
            "sources": "buffer",
            "operation_contracts": (
                "rows_cells:traversal_only:buffer:"
                "csv2.traversal.rows-cells.v1:input_corpus"
            ),
        },
    }
    side["description_invocation"] = {
        "command": ["/artifact", "--describe"],
        "stdout": " ".join(f"{key}={value}" for key, value in side["description"].items()),
        "stderr": "",
    }
    signature = ["1", "1", "1", "1", "1", "1"]

    throughput = 1_000_000_000.0 / float(1024**3)

    def launch(side_name: str, order: int) -> dict[str, object]:
        result = {
            "protocol": "csv2-common-v5",
            "revision": revision,
            "instrumentation": "none",
            "capabilities": "legacy-reader,legacy-writer",
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
            "timed_reader_steps": "0",
            "timed_checksum_mix_calls": "0",
        }
        return {
            "phase": "sample",
            "round": 0,
            "order": order,
            "side": side_name,
            "command": ["/artifact", "--operation", "rows_cells", "--input", "/input.csv",
                        "--source", "buffer", "--iterations", "1"],
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
        "schema": "csv2-benchmark-report-v7",
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
        "machine_profile": None,
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
    report = {
        "schema": "csv2-fixed-machine-metrics-v8",
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
        "machine_profile": None,
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
                "protocol": "csv2-current-v4",
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

    report["artifacts"]["dataset"]["path"] = "/input.csv"
    bind_metrics_invocations(report)
    return report


def bind_metrics_invocations(report):
    """Build authentic saved invocations for synthetic complete-report fixtures."""
    result = report["verification"]["result"]
    for key, artifact_key in (("verification", "executable"), ("allocations", "allocation_executable")):
        wire = dict(result)
        if key == "allocations":
            wire.update(allocations=str(report[key]["count"]), allocated_bytes=str(report[key]["bytes"]))
        report[key]["invocation"] = {
            "command": metrics.verify_command(Path(report["artifacts"][artifact_key]["path"]), report["operation"], Path(report["artifacts"]["dataset"]["path"]), report["source"]),
            "stdout": " ".join(f"{key}={value}" for key, value in wire.items()), "stderr": "",
        }
    for key in ("timing", "pmu"):
        if key not in report:
            continue
        timing = report[key]
        name = f"csv2/{report["operation"]}/{report["source"]}/{result["dataset"]}/real_time"
        timing["benchmark"] = name
        for sample in timing["samples"]:
            sample["name"] = name
        report[key + "_invocation"] = {
            "command": metrics.timing_command(Path(report["artifacts"]["executable"]["path"]), report["operation"], Path(report["artifacts"]["dataset"]["path"]), report["source"], Path("/benchmark.json"), report["runs"], "0.01s", 0.01, key == "pmu"),
            "stdout": "", "stderr": "",
        }
    if report.get("peak_rss") is not None:
        rss = report["peak_rss"]
        rss["command"] = ["/usr/bin/time", "-f", "%M", "-o", "/time.txt",
            *metrics.timing_command(Path(report["artifacts"]["executable"]["path"]),
             report["operation"], Path(report["artifacts"]["dataset"]["path"]),
             report["source"], Path("/rss.json"), 1, "0.01s", 0.0)]
        rss["time_output"] = str(rss["kib"]) + "\n"
    if report.get("code_size") is not None and "text_bytes" in report["code_size"]:
        size = report["code_size"]
        executable = report["artifacts"]["executable"]["path"]
        size["command"] = ["size", "--format=berkeley", "--radix=10", executable]
        size["stdout"] = ("text data bss dec hex filename\n"
            + " ".join(str(size[field]) for field in ("text_bytes", "data_bytes", "bss_bytes", "total_bytes"))
            + f" {size['total_bytes']:x} {executable}\n")



def controlled_comparison_report() -> dict[str, object]:
    report = comparison_report()
    revision = "d" * 40
    adapter_commit = "e" * 40
    adapter_sha256 = "f" * 64
    for side_name in ("baseline", "candidate"):
        side = report[side_name]
        side["artifact"]["revision"] = revision
        side["description"]["revision"] = revision
        side["description_invocation"]["stdout"] = " ".join(
            f"{key}={value}" for key, value in side["description"].items()
        )
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
    report["machine_profile"] = machine_profile()
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
            "schema": "csv2-benchmark-build-v2",
            "kind": "common-driver",
            "generated_at_utc": "now",
            "revision": revision,
            "instrumentation": "none",
            "capabilities": ["legacy-reader", "legacy-writer"],
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
                "/artifact", "-std=c++11", "-O3", "-DNDEBUG",
                "-ffile-prefix-map=/adapter=/_csv2/adapter",
                f"-ffile-prefix-map=/{side_name}-headers=/_csv2/source",
                "-MD", "-MF", f"/.{side_name}.run.d",
                f'-DCSV2_BENCHMARK_REVISION="{revision}"',
                "-DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=0",
                "-DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=0",
                f"-I/{side_name}-headers/include", "/adapter/benchmark/compare/common_driver.cpp", "-o", f"/.{side_name}.run.build",
            ],
            "normalized_argv": [
                "/artifact", "-std=c++11", "-O3", "-DNDEBUG",
                "-ffile-prefix-map={adapter_root}=/_csv2/adapter",
                "-ffile-prefix-map={header_root}=/_csv2/source",
                "-MD", "-MF", "{dependencies}",
                '-DCSV2_BENCHMARK_REVISION="{revision}"',
                "-DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=0",
                "-DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=0",
                "-I{include_root}", "{adapter_source}", "-o", "{output}",
            ],
            "build_log": {"returncode": 0, "stdout": "", "stderr": ""},
            "output": output,
        }
        build["input_policy"] = builds.owned_inputs.environment()[1]
        build["dependencies"] = {"schema": "csv2-compile-dependencies-v2", "files": [{"export": "headers", "path": "include/csv2/reader.hpp", "sha256": "c" * 64}, {"export": "adapter", "path": "benchmark/compare/common_driver.cpp", "sha256": adapter_sha256}], "trusted_system_inputs": [], "trusted_system_roots": []}
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
    report["machine"]["system"] = "Linux"
    report["machine_profile"] = machine_profile()
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
        "stdout": "",
        "stderr": "",
    }
    report["code_size"] = {
        "text_bytes": 1,
        "data_bytes": 1,
        "bss_bytes": 1,
        "total_bytes": 3,
        "stderr": "",
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
    for path in sorted({path for paths in builds.current_dependency_owners().values() for path in paths} | {"include/csv2/reader.hpp"}):
        source["files"].append({**source["files"][0], "path": path})
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
            "sources": [
                "benchmark/current/benchmark.cpp",
                "benchmark/current/support.cpp",
            ],
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
        "schema": "csv2-benchmark-build-v2",
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
    current_build["input_policy"] = builds.owned_inputs.environment()[1]
    current_build["dependencies"] = {"schema": "csv2-compile-dependencies-v2", "files": [{"export": "source", "path": entry["path"], "sha256": entry["sha256"]} for entry in source["files"]], "trusted_system_inputs": [], "trusted_system_roots": [], "units": [{"owner": owner, "source": relative, "inputs": [str(Path(source["root"]) / entry["path"]) for entry in source["files"]]} for owner, sources in builds.current_dependency_owners().items() for relative in sources]}
    current_build["configure_argv"] = [
        current_build["cmake"]["artifact"]["path"], "-S", current_build["source_root"],
        "-B", current_build["build_root"], "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DCMAKE_CXX_COMPILER=" + current_build["compiler"]["artifact"]["path"],
        "-DCMAKE_CXX_FLAGS=", "-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG",
        "-DCSV2_BUILD_BENCHMARKS=ON", "-DCSV2_BUILD_BENCHMARK_CHECKS=ON",
        "-DCSV2_VERIFICATION_PROFILE=perf", "-DCSV2_BENCHMARK_CORPUS_SCALE=1",
        "-DCSV2_BENCHMARK_REVISION=" + current_build["revision"], "-DCSV2_REQUIRE_PYTHON_AUDITS=ON",
    ]
    current_build["normalized_configure_argv"] = builds.normalize_build_argv(
        current_build["configure_argv"], (
            (current_build["source_root"], "{source_root}"), (current_build["build_root"], "{build_root}"),
            (current_build["compiler"]["artifact"]["path"], "{compiler}"), (current_build["revision"], "{revision}"),
        ),
    )
    current_build["build_argv"] = [
        current_build["cmake"]["artifact"]["path"], "--build", current_build["build_root"], "--target",
        "csv2_benchmark", "csv2_benchmark_allocations", "--parallel",
    ]
    current_build["corpus_argv"] = [
        current_build["cmake"]["artifact"]["path"], "--build", current_build["build_root"],
        "--target", "csv2_benchmark_corpus",
    ]
    current_build["corpus_log"] = {"returncode": 0, "stdout": "generated", "stderr": ""}
    current_build["identity_digest"] = builds.current_build_identity_digest(current_build)
    current_build["digest"] = builds.document_digest(current_build)
    report["build"] = current_build
    report["clean_build"] = {
        "command": list(current_build["build_argv"]),
        **{field: current_build["build_log"][field] for field in ("seconds", "stdout", "stderr")},
    }
    bind_metrics_invocations(report)
    return report


class ProtocolTests(unittest.TestCase):
    def test_resource_metrics_bind_context_and_primary_observations(self) -> None:
        report = controlled_metrics_report()
        protocol.validate_fixed_metrics_report(report)
        mutations = {
            "rss scope": lambda r: r["peak_rss"].update(scope="operation"),
            "rss value": lambda r: r["peak_rss"].update(kib=999),
            "rss command": lambda r: r["peak_rss"].update(command=["other"]),
            "size command": lambda r: r["code_size"].update(command=["other"]),
            "size values": lambda r: r["code_size"].update(text_bytes=8, total_bytes=10),
            "rss raw": lambda r: r["peak_rss"].update(time_output="999\n"),
            "rss input": lambda r: r["peak_rss"]["command"].__setitem__(7, "/other.csv"),
            "rss repetitions": lambda r: r["peak_rss"]["command"].__setitem__(13, "--benchmark_repetitions=20"),
            "rss warmup": lambda r: r["peak_rss"]["command"].__setitem__(15, "--benchmark_min_warmup_time=0.1"),
            "size hex": lambda r: r["code_size"].update(stdout=r["code_size"]["stdout"].replace("3 3 ", "3 4 ")),
            "size raw": lambda r: r["code_size"].update(stdout=r["code_size"]["stdout"].replace("1 1 1 3 3", "8 1 1 10 a")),
            "size input": lambda r: r["code_size"]["command"].__setitem__(-1, "/other"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                changed = copy.deepcopy(report)
                mutate(changed)
                with self.assertRaises(RuntimeError):
                    protocol.validate_fixed_metrics_report(changed)

        report = fixed_metrics_report()
        report["code_size"] = {"file_bytes": report["artifacts"]["executable"]["size"], "method": "filesystem"}
        protocol.validate_fixed_metrics_report(report)
        for field, value in (("file_bytes", report["artifacts"]["executable"]["size"] + 1),
                             ("method", "other")):
            changed = copy.deepcopy(report)
            changed["code_size"][field] = value
            with self.subTest(filesystem=field), self.assertRaises(RuntimeError):
                protocol.validate_fixed_metrics_report(changed)

        schema = json.loads((Path(__file__).resolve().parents[2]
            / "protocol/schemas/fixed-machine-v8.schema.json").read_text(encoding="utf-8"))
        for candidate, field, value in ((report, "stdout", ""),
                (controlled_metrics_report(), "method", "filesystem")):
            validate_schema(candidate, schema)
            changed = copy.deepcopy(candidate)
            changed["code_size"][field] = value
            with self.subTest(mixed_branch=field):
                with self.assertRaises(RuntimeError):
                    protocol.validate_fixed_metrics_report(changed)
                with self.assertRaises(SchemaValidationError):
                    validate_schema(changed, schema)

    def test_owned_metrics_bind_build_cost_and_preparation(self) -> None:
        report = controlled_metrics_report()
        protocol.validate_fixed_metrics_report(report)
        self.assertIsNone(report["post_build"])
        for field, value in (("command", ["other-build"]), ("seconds", 2.0),
                             ("stdout", "other output"), ("stderr", "other errors")):
            with self.subTest(field=field):
                changed = copy.deepcopy(report)
                changed["clean_build"][field] = value
                with self.assertRaisesRegex(RuntimeError, "clean_build differs"):
                    protocol.validate_fixed_metrics_report(changed)
        for field, value in (("returncode", 1), ("stdout", None), ("stderr", 1)):
            with self.subTest(corpus_field=field):
                changed = copy.deepcopy(report)
                changed["build"]["corpus_log"][field] = value
                changed["build"]["digest"] = builds.document_digest(
                    {k: v for k, v in changed["build"].items() if k != "digest"}
                )
                with self.assertRaisesRegex(RuntimeError, "corpus_log"):
                    protocol.validate_fixed_metrics_report(changed)
        report["post_build"] = invocation()
        with self.assertRaisesRegex(RuntimeError, "post_build must be null"):
            protocol.validate_fixed_metrics_report(report)
        external = fixed_metrics_report()
        external["post_build"] = invocation()
        protocol.validate_fixed_metrics_report(external)

    def test_fixed_metrics_rejects_inconsistent_primary_observations(self) -> None:
        def scale_rate(report):
            for sample in report["timing"]["samples"]:
                sample["bytes_per_second"] *= 2
            report["timing"]["bytes_per_second"]["median"] *= 2
        mutations = {
            "checksum": lambda r: r["verification"]["result"].update(checksum="2"),
            "allocation count": lambda r: r["allocations"].update(count=2),
            "allocation bytes": lambda r: r["allocations"].update(bytes=2),
            "scaled rate": scale_rate,
            "verification operation": lambda r: r["verification"]["invocation"]["command"].__setitem__(6, "traversal/rows"),
            "allocation source": lambda r: r["allocations"]["invocation"].update(stdout=r["allocations"]["invocation"]["stdout"].replace("source=buffer", "source=mmap")),
            "allocation checksum": lambda r: r["allocations"]["invocation"].update(stdout=r["allocations"]["invocation"]["stdout"].replace("checksum=1", "checksum=2")),
            "dataset label": lambda r: r["verification"]["result"].update(dataset="other.csv"),
            "benchmark name": lambda r: (r["timing"].update(benchmark="unrelated"), r["timing"]["samples"][0].update(name="unrelated")),
            "timing executable": lambda r: r["timing_invocation"]["command"].__setitem__(0, "/other"),
            "timing input": lambda r: r["timing_invocation"]["command"].__setitem__(2, "/other.csv"),
            "timing duplicate option": lambda r: r["timing_invocation"]["command"].append("--benchmark_repetitions=1"),
        }
        protocol.validate_fixed_metrics_report(fixed_metrics_report())
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                report = fixed_metrics_report()
                mutate(report)
                with self.assertRaises(RuntimeError):
                    protocol.validate_fixed_metrics_report(report)

    def test_fixed_metrics_pmu_and_commands_bind_the_recorded_case(self) -> None:
        for option, replacement in (
            ("--benchmark_repetitions=", "1"),
            ("--benchmark_filter=", "^other"),
            ("--benchmark_out_format=", "csv"),
            ("--benchmark_report_aggregates_only=", "true"),
            ("--benchmark_perf_counters=", "cycles"),
        ):
            with self.subTest(option=option):
                report = controlled_metrics_report()
                command = report["pmu_invocation"]["command"]
                index = next(i for i, value in enumerate(command) if value.startswith(option))
                command[index] = option + replacement
                with self.assertRaisesRegex(RuntimeError, "collection contract"):
                    protocol.validate_fixed_metrics_report(report)
        report = controlled_metrics_report()
        for sample in report["pmu"]["samples"]:
            sample["bytes_per_second"] = 2.0
        report["pmu"]["bytes_per_second"]["median"] = 2.0
        with self.assertRaisesRegex(RuntimeError, "input corpus bytes"):
            protocol.validate_fixed_metrics_report(report)

    def test_fixed_metrics_uses_input_bytes_and_portable_dataset_names(self) -> None:
        for path, dataset in (
            ("/corpus/a b.csv", "a_b.csv"),
            (r"/corpus/a\b.csv", "b.csv"),
            (r"C:\corpus\a b.csv", "a_b.csv"),
            ("/corpus/中文.csv", "______.csv"),
        ):
            with self.subTest(path=path):
                report = fixed_metrics_report()
                report["artifacts"]["dataset"]["path"] = path
                report["comparison_binding"]["dataset"] = dataset
                report["verification"]["result"].update(dataset=dataset, bytes="7")
                report["allocations"].update(count=3, bytes=17)
                bind_metrics_invocations(report)
                protocol.validate_fixed_metrics_report(report)
        report = fixed_metrics_report()
        report["timing"]["samples"][0]["bytes_per_second"] += 1e-10
        report["timing"]["bytes_per_second"]["median"] += 1e-10
        protocol.validate_fixed_metrics_report(report)

    def test_raw_writer_semantics_are_canonical_in_both_directions(self) -> None:
        schema_root = Path(__file__).resolve().parents[2] / "protocol"
        fixed_schema = json.loads((schema_root / "schemas" / "fixed-machine-v8.schema.json").read_text())
        for suffix in ("direct", "streamable"):
            operation = "writer/raw-" + suffix
            common_operation = "writer_raw_" + suffix
            prefix = "csv2.writer.raw-" + suffix
            raw_fields = prefix + ".raw-fields.v1"
            decoded = prefix + ".decoded-content.v1"
            report = fixed_metrics_report()
            report["operation"] = operation
            report["verification"]["result"].update(operation=operation, semantic_case_id=decoded, scope="writer_only")
            report["comparison_binding"].update(semantic_case_id=decoded, scope="writer_only")
            bind_metrics_invocations(report)
            protocol.validate_fixed_metrics_report(report)
            validate_schema(report, fixed_schema)
            protocol.parse_common(f"protocol=csv2-common-v5 operation={common_operation} semantic_case_id={raw_fields}", {"operation", "semantic_case_id"})
            for invalid in (prefix + ".v1", raw_fields, prefix + ".other.v1"):
                with self.subTest(operation=operation, invalid=invalid):
                    changed = json.loads(json.dumps(report))
                    changed["verification"]["result"]["semantic_case_id"] = invalid
                    changed["comparison_binding"]["semantic_case_id"] = invalid
                    bind_metrics_invocations(changed)
                    with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                        protocol.validate_fixed_metrics_report(changed)
                    with self.assertRaises(SchemaValidationError):
                        validate_schema(changed, fixed_schema)
            common = json.loads(
                json.dumps(comparison_report())
                .replace("rows_cells", common_operation)
                .replace("traversal_only", "writer_only")
                .replace("csv2.traversal.rows-cells.v1", raw_fields)
                .replace("legacy-reader,legacy-writer", "legacy-reader,legacy-writer,modern-writer")
            )
            common_schema = json.loads((schema_root / "schemas" / "comparison-v7.schema.json").read_text())
            protocol.validate_comparison_report(common)
            validate_schema(common, common_schema)
            for invalid in (prefix + ".v1", decoded):
                changed = json.loads(json.dumps(common).replace(raw_fields, invalid))
                with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                    protocol.validate_comparison_report(changed)
                with self.assertRaises(SchemaValidationError):
                    validate_schema(changed, common_schema)
            changed = json.loads(json.dumps(common).replace(common_operation, "rows_cells"))
            with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                protocol.validate_comparison_report(changed)
            with self.assertRaises(SchemaValidationError):
                validate_schema(changed, common_schema)
            evidence_schema = json.loads((schema_root / "schemas" / "evidence-bundle-v4.schema.json").read_text())
            for invalid in (prefix + ".v1", prefix + ".other.v1"):
                changed = evidence_bundle()
                changed["comparison_binding"]["semantic_case_id"] = invalid
                with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                    protocol.validate_evidence_bundle(changed)
                with self.assertRaises(SchemaValidationError):
                    validate_schema(changed, evidence_schema)
            for invalid in (prefix + ".v1", decoded):
                with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                    protocol.parse_common(f"protocol=csv2-common-v5 operation={common_operation} semantic_case_id={invalid}", {"operation"})
                with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                    protocol.parse_operation_contracts(f"{common_operation}:writer_only:buffer:{invalid}:input_corpus")
            for other_operation in ("traversal/rows-cells", operation + ".decoded-content"):
                changed = json.loads(json.dumps(report))
                changed["operation"] = other_operation
                changed["verification"]["result"]["operation"] = other_operation
                bind_metrics_invocations(changed)
                with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                    protocol.validate_fixed_metrics_report(changed)
                with self.assertRaises(SchemaValidationError):
                    validate_schema(changed, fixed_schema)
            with self.assertRaisesRegex(RuntimeError, "semantic case ID"):
                protocol.parse_common(f"protocol=csv2-common-v5 operation=rows_cells semantic_case_id={raw_fields}", {"operation"})

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

    def test_comparison_invocations_bind_their_execution_context(self) -> None:
        for factory in (comparison_report, controlled_comparison_report):
            original = factory()
            protocol.validate_comparison_report(original)
            for side in ("baseline", "candidate"):
                for index, value in ((0, "/other-driver"), (2, "legacy_writer_raw"),
                                     (4, "/other.csv"), (6, "mmap"), (8, "2")):
                    with self.subTest(mode=original["artifact_mode"], side=side, argument=index):
                        report = copy.deepcopy(original)
                        launch = next(item for item in report["cases"][0]["launches"]
                                      if item["side"] == side)
                        launch["command"][index] = value
                        with self.assertRaisesRegex(RuntimeError, "command.*bound execution context"):
                            protocol.validate_comparison_report(report)
                for field, value in (("command", ["/other-driver", "--describe"]),
                                     ("command", ["/artifact", "--describe", "extra"]),
                                     ("stdout", "not a description"),
                                     ("stdout", original[side]["description_invocation"]["stdout"].replace(
                                         "instrumentation=none", "instrumentation=timer-audit"))):
                    with self.subTest(mode=original["artifact_mode"], side=side, field=field, value=value):
                        report = copy.deepcopy(original)
                        report[side]["description_invocation"][field] = value
                        with self.assertRaises(RuntimeError):
                            protocol.validate_comparison_report(report)

    def test_hook_records_accept_empty_arguments_without_weakening_executable(self) -> None:
        schema = json.loads((Path(__file__).resolve().parents[2] /
                             "protocol/schemas/fixed-machine-v8.schema.json").read_text())
        for field in ("clean_build", "post_build"):
            for command in (["tool", "", "argument"], [], [""], ["tool", None],
                            ["tool\0"], ["tool", "argument\0"]):
                with self.subTest(field=field, command=command):
                    report = fixed_metrics_report()
                    record = {"command": command, "stdout": "", "stderr": ""}
                    if field == "clean_build":
                        record["seconds"] = 1.0
                    report[field] = record
                    if command == ["tool", "", "argument"]:
                        protocol.validate_fixed_metrics_report(report)
                        validate_schema(report, schema)
                    else:
                        with self.assertRaises(RuntimeError):
                            protocol.validate_fixed_metrics_report(report)
                        with self.assertRaises(SchemaValidationError):
                            validate_schema(report, schema)

    def test_schema_prefix_items_and_remaining_items_are_distinct(self) -> None:
        schema = {"type": "array", "prefixItems": [{"type": "string"}],
                  "items": {"type": "integer"}}
        for valid in ([], ["tool"], ["tool", 1, 2]):
            validate_schema(valid, schema)
        for invalid in ([1], ["tool", "bad"], ["tool", 1, "bad"]):
            with self.assertRaises(SchemaValidationError):
                validate_schema(invalid, schema)

    def test_completed_reports_pass_semantic_validation(self) -> None:
        protocol.validate_comparison_report(comparison_report())
        protocol.validate_fixed_metrics_report(fixed_metrics_report())

    def test_comparison_noise_uses_the_noisier_side(self) -> None:
        report = comparison_report()
        case = report["cases"][0]
        baseline = case["launches"][0]
        candidate = case["launches"][1]
        launches = []
        for round_index, entries in enumerate(
            ((baseline, candidate), (candidate, baseline))
        ):
            for order, template in enumerate(entries):
                launch = json.loads(json.dumps(template))
                launch["round"] = round_index
                launch["order"] = order
                if launch["side"] == "candidate" and round_index == 1:
                    launch["result"]["elapsed_ns"] = "2"
                    launch["stdout"] = " ".join(
                        f"{key}={value}" for key, value in launch["result"].items()
                    )
                    launch["throughput_gib_per_second"] /= 2.0
                launches.append(launch)
        case["launches"] = launches
        derived = derivation.derive_comparison_case(
            case,
            runs=2,
            warmups=0,
            iterations=1,
            common_protocol="csv2-common-v5",
        )
        self.assertGreater(derived["measured_noise"], 0.6)
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

    def test_fixed_metrics_completion_requirements_preserve_lifecycle(self) -> None:
        optional = ("pmu", "pmu_invocation", "peak_rss", "code_size")
        for field in optional:
            for missing in (False, True):
                report = controlled_metrics_report()
                if missing:
                    del report[field]
                else:
                    report[field] = None
                with self.subTest(field=field, missing=missing):
                    with self.assertRaises(RuntimeError):
                        protocol.validate_fixed_metrics_report(report)
        for status in ("running", "failed"):
            report = controlled_metrics_report()
            report.update(status=status, controlled_complete=False)
            if status == "failed":
                report["error"] = "collection interrupted"
            for field in (*optional, "verification", "allocations", "timing",
                          "timing_invocation", "comparison_binding", "completed_at_utc"):
                report.pop(field, None)
            protocol.validate_fixed_metrics_report(report)
        report = fixed_metrics_report()
        for field in optional:
            report[field] = None
        report["code_size"] = {"file_bytes": report["artifacts"]["executable"]["size"], "method": "filesystem"}
        protocol.validate_fixed_metrics_report(report)
        report = controlled_metrics_report()
        report["code_size"] = {"file_bytes": report["artifacts"]["executable"]["size"], "method": "filesystem"}
        with self.assertRaises(RuntimeError):
            protocol.validate_fixed_metrics_report(report)
        for field, value in (("bytes_per_second", 2.0), ("name", "wrong/real_time")):
            report = controlled_metrics_report()
            report["pmu"]["samples"][0][field] = value
            with self.subTest(pmu_field=field):
                with self.assertRaises(RuntimeError):
                    protocol.validate_fixed_metrics_report(report)

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

    def test_common_build_rejects_capability_and_instrumentation_command_drift(self) -> None:
        for definitions, message in (
            (("-DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1",), "reserved"),
            (("/DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1",), "reserved"),
            (("-D", "CSV2_BENCHMARK_TIMER_SCOPE_AUDIT=1"), "reserved"),
            (("/D", "CSV2_BENCHMARK_TIMER_SCOPE_AUDIT=1"), "reserved"),
            (("-Wp,-DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=1",), "reserved"),
            (("@flags.rsp",), "response files"),
            (("-Wp,-include,defines.hpp",), "pass-through"),
            (("-include", "defines.hpp"), "preprocessor input"),
        ):
            with self.subTest(definitions=definitions):
                report = controlled_comparison_report()
                for side in ("baseline", "candidate"):
                    build = report[side]["build"]
                    build["compiler_flags"].extend(definitions)
                    build["argv"][1:1] = definitions
                    build["normalized_argv"][1:1] = definitions
                    build["identity_digest"] = builds.common_build_identity_digest(build)
                    unsigned = dict(build)
                    unsigned.pop("digest")
                    build["digest"] = builds.document_digest(unsigned)
                with self.assertRaisesRegex(RuntimeError, message):
                    protocol.validate_comparison_report(report)

    def test_common_build_rejects_resigned_actual_input_redirection(self) -> None:
        for original, replacement in (("-I/baseline-headers/include", "-I/tmp/shadow"),
                                      ("/adapter/benchmark/compare/common_driver.cpp", "/tmp/shadow.cpp"),
                                      ("-MD", "-MMD")):
            build = controlled_comparison_report()["baseline"]["build"]
            build["argv"][build["argv"].index(original)] = replacement
            build["identity_digest"] = builds.common_build_identity_digest(build)
            build.pop("digest")
            build["digest"] = builds.document_digest(build)
            with self.assertRaisesRegex(RuntimeError, "immutable input contract"):
                protocol._common_build(build, "redirected build")

    def test_common_command_contract_reads_windows_msvc_on_any_host(self) -> None:
        build = controlled_comparison_report()["baseline"]["build"]
        compiler = r"C:\tools\cl.exe"
        build["compiler"]["artifact"]["path"] = compiler
        build["header_export"]["root"] = r"C:\headers"
        build["adapter_export"]["root"] = r"C:\adapter"
        build["output"]["path"] = r"C:\out\driver.exe"
        build["compiler_flags"] = ["/O2", "/DNDEBUG", "/EHsc"]
        revision = build["revision"]
        build["normalized_argv"] = [
            compiler, "/O2", "/DNDEBUG", "/EHsc", "/experimental:deterministic",
            "/pathmap:{adapter_root}=/_csv2/adapter", "/pathmap:{header_root}=/_csv2/source",
            "/Brepro", "/sourceDependencies", "{dependencies}",
            '/DCSV2_BENCHMARK_REVISION="{revision}"',
            "/DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=0",
            "/DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=0",
            "/I{include_root}", "{adapter_source}", "/Fe:{output}", "/Fo:{object}",
        ]
        build["argv"] = [
            compiler, "/O2", "/DNDEBUG", "/EHsc", "/experimental:deterministic",
            r"/pathmap:C:\adapter=/_csv2/adapter", r"/pathmap:C:\headers=/_csv2/source",
            "/Brepro", "/sourceDependencies", r"C:\out\temp.deps.json",
            f'/DCSV2_BENCHMARK_REVISION="{revision}"',
            "/DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=0",
            "/DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=0",
            r"/IC:\headers\include", r"C:\adapter\benchmark\compare\common_driver.cpp",
            r"/Fe:C:\out\temp.build", r"/Fo:C:\out\temp.build.obj",
        ]
        builds.validate_common_build_command_contract(build)

    def test_current_build_rejects_resigned_flag_and_config_redirection(self) -> None:
        for flag in ("-I/tmp/shadow", "-Xclang=-include", "--config=/tmp/config", "-O0"):
            build = controlled_metrics_report()["build"]
            build["compiler_flags"].append(flag)
            for field in ("configure_argv", "normalized_configure_argv"):
                index = next(i for i, value in enumerate(build[field])
                             if value.startswith("-DCMAKE_CXX_FLAGS_RELEASE="))
                build[field][index] += " " + flag
            build["identity_digest"] = builds.current_build_identity_digest(build)
            build.pop("digest")
            build["digest"] = builds.document_digest(build)
            with self.assertRaises(RuntimeError):
                protocol._current_build(build, "redirected current build")
        build = controlled_metrics_report()["build"]
        build["input_policy"]["bound"]["CPATH"] = "/tmp/shadow"
        with self.assertRaisesRegex(RuntimeError, "input policy"):
            builds._verify_input_policy(build)
        build = controlled_metrics_report()["build"]
        build["configure_argv"].append("-DCMAKE_TOOLCHAIN_FILE=/tmp/toolchain")
        build["normalized_configure_argv"].append("-DCMAKE_TOOLCHAIN_FILE=/tmp/toolchain")
        with self.assertRaisesRegex(RuntimeError, "controlled contract"):
            builds.validate_current_build_command_contract(build)

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
            "schema": "csv2-artifact-manifest-v4",
            "kind": "comparison",
            "report": artifact(),
            "inputs": {
                "baseline": artifact("base"),
                "candidate": artifact("candidate"),
                "datasets": [artifact()],
                "builds": {"baseline": "a" * 64, "candidate": "b" * 64},
                "machine_profile": None,
            },
        }
        protocol.validate_artifact_manifest(manifest)
        schema_root = Path(__file__).resolve().parents[2] / "protocol" / "schemas"
        schema = json.loads(
            (schema_root / "artifact-manifest-v4.schema.json").read_text(
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
            (schema_root / "artifact-manifest-v4.schema.json").read_text(
                encoding="utf-8"
            )
        )
        for owned in (False, True):
            with self.subTest(owned=owned):
                manifest = fixed_metrics_manifest(owned=owned)
                protocol.validate_artifact_manifest(manifest)
                validate_schema(manifest, schema)

        manifest = fixed_metrics_manifest()
        manifest["inputs"]["artifacts"]["compiler_executable"] = artifact()
        protocol.validate_artifact_manifest(manifest)
        validate_schema(manifest, schema)
        manifest["inputs"]["build"] = "c" * 64
        with self.assertRaisesRegex(RuntimeError, "requires compiler artifacts"):
            protocol.validate_artifact_manifest(manifest)
        with self.assertRaises(SchemaValidationError):
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
            "commands without compiler": lambda value: value["inputs"][
                "artifacts"
            ].__setitem__("compile_commands", artifact()),
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
        report["candidate"]["description_invocation"]["stdout"] = " ".join(
            f"{key}={value}" for key, value in report["candidate"]["description"].items()
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

    def test_controlled_machine_profile_binding_is_strict(self) -> None:
        report = controlled_comparison_report()
        report["machine_profile"]["observation"]["governor"] = "powersave"
        with self.assertRaisesRegex(RuntimeError, "governor"):
            protocol.validate_comparison_report(report)

        metrics = controlled_metrics_report()
        metrics["machine_profile"]["digest"] = "b" * 64
        with self.assertRaisesRegex(RuntimeError, "digest differs"):
            protocol.validate_fixed_metrics_report(metrics)

    def test_controlled_compiler_version_accepts_either_output_stream(self) -> None:
        report = controlled_metrics_report()
        identity = report["compiler_identity"]
        identity.update(version_stdout="", version_stderr="compiler version")
        protocol.validate_fixed_metrics_report(report)
        identity.update(version_stdout=" ", version_stderr="\n")
        with self.assertRaisesRegex(RuntimeError, "version output is empty"):
            protocol.validate_fixed_metrics_report(report)

    def test_controlled_identity_matches_profile_observation(self) -> None:
        for factory, validator, identity_key in (
            (controlled_comparison_report, protocol.validate_comparison_report, "host"),
            (controlled_metrics_report, protocol.validate_fixed_metrics_report, "machine"),
            (evidence_bundle, protocol.validate_evidence_bundle, "machine"),
        ):
            report = factory()
            if factory is evidence_bundle:
                report.update(evidence_level="controlled", decision_eligible=True,
                              machine_profile=machine_profile())
                for component in report["components"].values():
                    component["controlled_complete"] = True
            validator(report)
            mutations = {
                "machine": "other-architecture", "cpu_model": "other-cpu",
                "logical_cpus": 2, "process_affinity": [1],
            }
            if factory is controlled_metrics_report:
                mutations.update(system="other-system", release="other-release")
            for field, value in mutations.items():
                with self.subTest(factory=factory.__name__, field=field):
                    changed = copy.deepcopy(report)
                    changed[identity_key][field] = value
                    with self.assertRaises(RuntimeError):
                        validator(changed)
            for affinity in ([False], [0, 0], [1, 0]):
                for change_observation in (False, True):
                    with self.subTest(factory=factory.__name__, affinity=affinity,
                                      change_observation=change_observation):
                        changed = copy.deepcopy(report)
                        changed[identity_key]["process_affinity"] = affinity
                        if change_observation:
                            changed["machine_profile"]["observation"]["process_affinity"] = affinity
                            changed["machine_profile"]["profile"]["allowed_affinity"] = [0, 1]
                        with self.assertRaises(RuntimeError):
                            validator(changed)

    def test_evidence_schema_rejects_ineligible_documents(self) -> None:
        schema_root = Path(__file__).resolve().parents[2] / "protocol" / "schemas"
        evidence = json.loads(
            (schema_root / "evidence-bundle-v4.schema.json").read_text(encoding="utf-8")
        )
        validate_schema(evidence_bundle(), evidence)
        controlled_bundle = evidence_bundle()
        controlled_bundle["evidence_level"] = "controlled"
        controlled_bundle["decision_eligible"] = True
        controlled_bundle["machine_profile"] = machine_profile()
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

    def test_offline_schema_validator_enforces_collection_and_numeric_bounds(self) -> None:
        validate_schema([1, 2], {"type": "array", "maxItems": 2, "uniqueItems": True})
        with self.assertRaises(SchemaValidationError):
            validate_schema([1, 2, 3], {"type": "array", "maxItems": 2})
        with self.assertRaises(SchemaValidationError):
            validate_schema([1, 1], {"type": "array", "uniqueItems": True})
        validate_schema([True, 1], {"type": "array", "uniqueItems": True})
        with self.assertRaises(SchemaValidationError):
            validate_schema([1, 1.0], {"type": "array", "uniqueItems": True})
        validate_schema(1, {"type": "number", "exclusiveMinimum": 0})
        with self.assertRaises(SchemaValidationError):
            validate_schema(0, {"type": "number", "exclusiveMinimum": 0})

    def test_schema_const_and_enum_use_json_equality(self) -> None:
        for keyword in ("const", "enum"):
            for value, changed in ((False, 0), (True, 1), ([False], [0]), ({"value": True}, {"value": 1})):
                schema = {keyword: [value] if keyword == "enum" else value}
                validate_schema(value, schema)
                with self.subTest(keyword=keyword, value=value):
                    with self.assertRaises(SchemaValidationError):
                        validate_schema(changed, schema)
            validate_schema(1.0, {keyword: [1] if keyword == "enum" else 1})
        schema_path = Path(__file__).resolve().parents[2] / "protocol/schemas/fixed-machine-v8.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        report = fixed_metrics_report()
        validate_schema(report, schema)
        report["decision_eligible"] = 0
        with self.assertRaises(SchemaValidationError):
            validate_schema(report, schema)

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

    def test_common_v5_is_accepted_and_v4_is_rejected(self) -> None:
        result = protocol.parse_common(
            "protocol=csv2-common-v5 revision=x", {"revision"}
        )
        self.assertEqual(result["revision"], "x")
        with self.assertRaisesRegex(RuntimeError, "expected csv2-common-v5"):
            protocol.parse_common(
                "protocol=csv2-common-v4 revision=x", {"revision"}
            )

    def test_operation_contracts_are_strict_and_self_describing(self) -> None:
        contracts = protocol.parse_operation_contracts(
            "rows_cells:traversal_only:buffer+mmap:"
            "csv2.traversal.rows-cells.v1:input_corpus;"
            "writer_raw_direct:writer_only:buffer:"
            "csv2.writer.raw-direct.raw-fields.v1:input_corpus"
        )
        self.assertEqual(contracts["rows_cells"][0], "traversal_only")
        self.assertEqual(contracts["rows_cells"][1], frozenset({"buffer", "mmap"}))
        with self.assertRaisesRegex(RuntimeError, "duplicate operation contract"):
            protocol.parse_operation_contracts(
                "rows_cells:traversal_only:buffer:csv2.traversal.rows-cells.v1:input_corpus;"
                "rows_cells:traversal_only:mmap:csv2.traversal.rows-cells.v1:input_corpus"
            )
        with self.assertRaisesRegex(RuntimeError, "unsupported operation scope"):
            protocol.parse_operation_contracts(
                "rows_cells:guessed:buffer:csv2.rows.v1:input_corpus"
            )

    def test_current_v4_parses_exact_uint64_fields_and_rejects_v3(self) -> None:
        output = (
            "protocol=csv2-current-v4 revision=r operation=traversal/rows "
            "source=buffer dataset=x.csv semantic_case_id=csv2.traversal.rows.v1 "
            "scope=traversal_only byte_basis=input_corpus "
            "checksum=18446744073709551615 "
            "bytes=4 rows=1 cells=0 allocations=0 allocated_bytes=0"
        )
        result = protocol.parse_current(output)
        self.assertEqual(result["checksum"], "18446744073709551615")
        with self.assertRaisesRegex(RuntimeError, "expected csv2-current-v4"):
            protocol.parse_current(output.replace("csv2-current-v4", "csv2-current-v3"))

    def test_current_rejects_overflow_duplicate_and_missing_fields(self) -> None:
        valid = (
            "protocol=csv2-current-v4 revision=r operation=o source=buffer dataset=x "
            "semantic_case_id=csv2.o.v1 scope=source_only byte_basis=input_corpus "
            "checksum=1 bytes=1 rows=1 cells=1 allocations=0 allocated_bytes=0"
        )
        with self.assertRaisesRegex(RuntimeError, "outside uint64"):
            protocol.parse_current(valid.replace("checksum=1", f"checksum={1 << 64}"))
        with self.assertRaisesRegex(RuntimeError, "duplicate key"):
            protocol.parse_current(valid + " checksum=2")
        with self.assertRaisesRegex(RuntimeError, "missing required fields: cells"):
            protocol.parse_current(valid.replace(" cells=1", ""))
        with self.assertRaisesRegex(RuntimeError, "unknown fields"):
            protocol.parse_current(valid + " extra=1")
        for value in ("01", "+1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "canonical"):
                    protocol.parse_current(valid.replace("checksum=1", f"checksum={value}"))

    def test_non_finite_timing_values_are_rejected(self) -> None:
        for value in ("nan", "inf", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "finite and non-negative"):
                    protocol.finite_nonnegative(value, "sample")


if __name__ == "__main__":
    unittest.main()
