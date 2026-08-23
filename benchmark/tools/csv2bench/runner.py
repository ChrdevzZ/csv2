#!/usr/bin/env python3
"""Auditable paired benchmark runner for the version-neutral CSV2 driver."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence


from . import artifacts, atomic, builds, derivation, protocol as wire
from . import ARTIFACT_MANIFEST_SCHEMA
from . import COMMON_PROTOCOL as PROTOCOL
from . import COMPARISON_SCHEMA as SCHEMA
OPERATIONS = (
    "rows_cells",
    "legacy_mmap_rows_cells",
    "legacy_writer_raw",
    "writer_raw_direct",
    "writer_raw_streamable",
    "writer_escaped_direct",
    "writer_escaped_streamable",
)
SOURCES = ("buffer", "mmap")
UINT64_MAX = (1 << 64) - 1
INT64_MAX = (1 << 63) - 1
RESULT_FIELDS = {
    "protocol",
    "revision",
    "operation",
    "scope",
    "source",
    "bytes",
    "iterations",
    "elapsed_ns",
    "rows",
    "cells",
    "row_bytes",
    "checksum",
    "timed_reader_steps",
}

Executable = Path | Sequence[Path | str]
Invoke = Callable[[Executable, str, Path, str, int], dict[str, str]]


def sha256_file(path: Path) -> str:
    return artifacts.sha256_file(path)


def canonical_existing(path: Path, label: str) -> Path:
    return artifacts.canonical_existing(path, label)


def canonical_output(path: Path) -> Path:
    return artifacts.canonical_output(path)


def paths_alias(left: Path, right: Path) -> bool:
    return artifacts.paths_alias(left, right)


def reject_output_alias(
    output: Path, protected_paths: Iterable[tuple[str, Path]]
) -> None:
    artifacts.reject_output_alias(output, protected_paths)


def replace_report(temporary: Path, output: Path) -> None:
    atomic.replace(temporary, output)


def cpu_identity() -> tuple[str, str]:
    if platform.system() == "Linux":
        try:
            with Path("/proc/cpuinfo").open(
                "r", encoding="utf-8", errors="replace"
            ) as cpuinfo:
                for line in cpuinfo:
                    name, separator, value = line.partition(":")
                    if (
                        separator
                        and name.strip() in {"model name", "Hardware", "Processor"}
                        and value.strip()
                    ):
                        return value.strip(), f"/proc/cpuinfo:{name.strip()}"
        except OSError:
            pass
    elif platform.system() == "Darwin":
        sysctl = Path("/usr/sbin/sysctl")
        if sysctl.is_file():
            for name in ("machdep.cpu.brand_string", "hw.model"):
                try:
                    completed = subprocess.run(
                        [str(sysctl), "-n", name],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    continue
                value = completed.stdout.strip()
                if completed.returncode == 0 and value:
                    return value, f"sysctl:{name}"
    elif platform.system() == "Windows":
        value = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
        if value:
            return value, "environment:PROCESSOR_IDENTIFIER"

    for source, value in (
        ("platform.processor", platform.processor()),
        ("platform.uname.processor", platform.uname().processor),
    ):
        if value.strip():
            return value.strip(), source
    return "unknown", "unavailable"


def host_metadata() -> dict[str, object]:
    model, model_source = cpu_identity()
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        affinity = sorted(os.sched_getaffinity(0))
    return {
        "platform": platform.platform(),
        "node": platform.node(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_model": model,
        "cpu_model_source": model_source,
        "logical_cpus": os.cpu_count() or 1,
        "process_affinity": affinity,
        "python": platform.python_version(),
    }


def command_prefix(executable: Executable) -> list[str]:
    if isinstance(executable, Path):
        return [str(executable)]
    return [str(part) for part in executable]


def parse_key_value_line(output: str, required: set[str]) -> dict[str, str]:
    return wire.parse_key_value_line(output, required)


def parse_output(output: str) -> dict[str, str]:
    result = parse_key_value_line(output, RESULT_FIELDS)
    if result["protocol"] != PROTOCOL:
        raise RuntimeError(f"unsupported benchmark protocol: {result['protocol']}")
    return result


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "benchmark command failed\n"
            f"command: {json.dumps(command)}\n"
            f"exit: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def invoke(
    executable: Executable, operation: str, dataset: Path, source: str, iterations: int
) -> dict[str, str]:
    command = [
        *command_prefix(executable),
        "--operation",
        operation,
        "--input",
        str(dataset),
        "--source",
        source,
        "--iterations",
        str(iterations),
    ]
    completed = run_command(command)
    result = parse_output(completed.stdout)
    result["_command"] = json.dumps(command)
    result["_stdout"] = completed.stdout.rstrip("\n")
    result["_stderr"] = completed.stderr.rstrip("\n")
    return result


def describe(executable: Executable) -> dict[str, str]:
    command = [*command_prefix(executable), "--describe"]
    completed = run_command(command)
    result = parse_key_value_line(
        completed.stdout,
        {
            "protocol",
            "revision",
            "operations",
            "sources",
            "operation_contracts",
        },
    )
    if result["protocol"] != PROTOCOL:
        raise RuntimeError(f"unsupported benchmark protocol: {result['protocol']}")
    result["_command"] = json.dumps(command)
    result["_stdout"] = completed.stdout.rstrip("\n")
    result["_stderr"] = completed.stderr.rstrip("\n")
    return result


def artifact_metadata(
    path: Path, revision: str | None = None
) -> dict[str, object]:
    return artifacts.metadata(path, revision)


def verify_artifact_unchanged(metadata: dict[str, object], label: str) -> None:
    artifacts.verify_unchanged(metadata, label)


def runner_source_paths() -> list[Path]:
    benchmark_root = Path(__file__).resolve().parents[2]
    package_root = Path(__file__).resolve().parent
    return [
        benchmark_root / "run_suite.py",
        package_root / "__init__.py",
        package_root / "artifacts.py",
        package_root / "atomic.py",
        package_root / "builds.py",
        package_root / "derivation.py",
        package_root / "protocol.py",
        package_root / "runner.py",
        package_root / "statistics.py",
    ]


def dataset_metadata(path: Path, logical_name: str | None = None) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "name": logical_name if logical_name is not None else path.name,
        "path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def selected(requested: str, available: Iterable[str]) -> list[str]:
    choices = list(available)
    if requested == "all":
        return choices
    entries = requested.split(",")
    wanted = [item.strip() for item in entries]
    if len(entries) == 1 and not wanted[0]:
        raise ValueError("selection must not be empty")
    if any(not item for item in wanted):
        raise ValueError("selections must not contain empty entries")
    if len(wanted) != len(set(wanted)):
        raise ValueError("selections must not contain duplicates")
    unknown = sorted(set(wanted) - set(choices))
    if unknown:
        raise ValueError(f"unknown selections: {', '.join(unknown)}")
    return wanted


def validate_mode_invariants(
    mode: str,
    baseline_revision: str,
    candidate_revision: str,
    baseline_sha256: str,
    candidate_sha256: str,
    baseline_build_identity: str | None,
    candidate_build_identity: str | None,
) -> None:
    if mode == "aa":
        if baseline_revision != candidate_revision:
            raise ValueError("A/A calibration requires the same revision")
        if baseline_sha256 != candidate_sha256:
            raise ValueError("A/A calibration requires byte-identical executables")
        if baseline_build_identity != candidate_build_identity:
            raise ValueError("A/A calibration requires the same owned build identity")
    elif mode == "compare":
        if baseline_revision == candidate_revision:
            raise ValueError("A/B comparison requires different revisions")
    else:
        raise ValueError(f"unsupported comparison mode: {mode}")


def public_result(result: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def reported_command(result: dict[str, str]) -> list[str] | None:
    encoded = result.get("_command")
    if encoded is None:
        return None
    try:
        command = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise RuntimeError("benchmark invocation command is malformed") from error
    if not isinstance(command, list) or not all(
        isinstance(argument, str) for argument in command
    ):
        raise RuntimeError("benchmark invocation command must be an argv array")
    return command


def invocation_record(result: dict[str, str]) -> dict[str, object]:
    return {
        "command": reported_command(result),
        "stdout": result.get("_stdout"),
        "stderr": result.get("_stderr"),
    }


def validate_result(
    result: dict[str, str],
    operation: str,
    source: str,
    iterations: int,
    *,
    expected_scope: str,
    expected_bytes: int,
    expected_revision: str | None = None,
) -> float:
    expected = {
        "protocol": PROTOCOL,
        "operation": operation,
        "scope": expected_scope,
        "source": source,
        "iterations": str(iterations),
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(
                f"benchmark metadata mismatch for {key}: expected {value}, got {result.get(key)}"
            )
    if expected_revision is not None and result.get("revision") != expected_revision:
        raise RuntimeError(
            "benchmark revision changed between description and measurement: "
            f"expected {expected_revision}, got {result.get('revision')}"
        )
    try:
        byte_count = int(result["bytes"])
        elapsed_ns = int(result["elapsed_ns"])
        rows = int(result["rows"])
        cells = int(result["cells"])
        row_bytes = int(result["row_bytes"])
        checksum = int(result["checksum"])
        timed_reader_steps = int(result["timed_reader_steps"])
    except (KeyError, ValueError) as error:
        raise RuntimeError("benchmark numeric fields must be integers") from error
    if (
        byte_count <= 0
        or elapsed_ns <= 0
        or elapsed_ns > INT64_MAX
        or rows < 0
        or cells < 0
        or row_bytes < 0
        or checksum < 0
        or timed_reader_steps < 0
        or any(
            value > UINT64_MAX
            for value in (byte_count, rows, cells, row_bytes, checksum)
        )
    ):
        raise RuntimeError("benchmark numeric fields are outside their valid range")
    if expected_scope == "writer_only" and timed_reader_steps != 0:
        raise RuntimeError("writer-only benchmark traversed Reader state inside the timer")
    if expected_bytes <= 0:
        raise ValueError("expected dataset byte count must be positive")
    if byte_count != expected_bytes:
        raise RuntimeError(
            "benchmark byte count does not match the dataset: "
            f"expected {expected_bytes}, got {byte_count}"
        )
    throughput = byte_count * iterations * 1_000_000_000.0 / elapsed_ns / (1024.0**3)
    if not math.isfinite(throughput) or throughput <= 0:
        raise RuntimeError("computed throughput must be positive and finite")
    return throughput


def semantic_signature(result: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        result[key] for key in ("bytes", "iterations", "rows", "cells", "row_bytes", "checksum")
    )


def measure_case(
    baseline: Executable,
    candidate: Executable,
    operation: str,
    dataset: Path,
    source: str,
    runs: int,
    iterations: int,
    warmups: int,
    expected_scope: str,
    invoke_fn: Invoke = invoke,
    calibration_noise: float = 0.0,
    baseline_revision: str | None = None,
    candidate_revision: str | None = None,
    expected_bytes: int | None = None,
) -> dict[str, object]:
    if not math.isfinite(calibration_noise) or calibration_noise < 0:
        raise ValueError("calibration noise must be finite and non-negative")
    launches: list[dict[str, object]] = []
    signature: tuple[str, ...] | None = None
    if expected_bytes is None:
        expected_bytes = dataset.stat().st_size
    if expected_bytes <= 0:
        raise RuntimeError("benchmark dataset must not be empty")

    def launch(
        executable: Executable, side: str, phase: str, round_index: int, order: int
    ) -> None:
        nonlocal signature
        result = invoke_fn(executable, operation, dataset, source, iterations)
        expected_revision = (
            baseline_revision if side == "baseline" else candidate_revision
        )
        throughput = validate_result(
            result,
            operation,
            source,
            iterations,
            expected_scope=expected_scope,
            expected_bytes=expected_bytes,
            expected_revision=expected_revision,
        )
        current_signature = semantic_signature(result)
        if signature is None:
            signature = current_signature
        elif current_signature != signature:
            raise RuntimeError(
                f"semantic mismatch for {dataset.name}/{operation}/{source}"
            )
        launches.append(
            {
                "phase": phase,
                "round": round_index,
                "order": order,
                "side": side,
                "command": reported_command(result),
                "stdout": result.get("_stdout"),
                "stderr": result.get("_stderr"),
                "throughput_gib_per_second": throughput,
                "result": public_result(result),
            }
        )
    for round_index in range(warmups):
        order = ((baseline, "baseline"), (candidate, "candidate"))
        if round_index % 2:
            order = tuple(reversed(order))
        for position, (executable, side) in enumerate(order):
            launch(executable, side, "warmup", round_index, position)

    for round_index in range(runs):
        order = ((baseline, "baseline"), (candidate, "candidate"))
        if round_index % 2:
            order = tuple(reversed(order))
        for position, (executable, side) in enumerate(order):
            launch(executable, side, "sample", round_index, position)

    case: dict[str, object] = {
        "dataset": dataset.name,
        "operation": operation,
        "source": source,
        "calibration_noise": calibration_noise,
        "launches": launches,
    }
    case.update(
        derivation.derive_comparison_case(
            case,
            runs=runs,
            warmups=warmups,
            iterations=iterations,
            common_protocol=PROTOCOL,
        )
    )
    return case


def case_key(dataset: str, operation: str, source: str) -> str:
    return f"{dataset}\0{operation}\0{source}"


def load_calibration(
    path: Path,
) -> tuple[dict[str, float], dict[str, object], dict[str, object]]:
    contents = path.read_bytes()
    report = json.loads(contents.decode("utf-8"))
    if (
        report.get("schema") != SCHEMA
        or report.get("mode") != "aa"
        or report.get("status") != "completed"
    ):
        raise RuntimeError("calibration must be a completed A/A csv2 benchmark report")
    wire.validate_comparison_report(report)
    try:
        baseline_hash = report["baseline"]["artifact"]["sha256"]
        candidate_hash = report["candidate"]["artifact"]["sha256"]
    except (KeyError, TypeError) as error:
        raise RuntimeError("calibration is missing artifact provenance") from error
    if baseline_hash != candidate_hash:
        raise RuntimeError("calibration A/A artifacts are not byte-identical")
    noise: dict[str, float] = {}
    try:
        cases = report.get("cases", [])
        for case in cases:
            key = case_key(case["dataset"], case["operation"], case["source"])
            if key in noise:
                raise RuntimeError("calibration contains duplicate cases")
            value = float(case["observed_noise"])
            if not math.isfinite(value) or value < 0:
                raise RuntimeError("calibration noise must be finite and non-negative")
            noise[key] = value
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("calibration contains malformed cases") from error
    return (
        noise,
        {
            "path": str(path.resolve(strict=True)),
            "size": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
            "schema": report["schema"],
        },
        report,
    )


def validate_calibration_context(
    calibration: dict[str, object], current: dict[str, object]
) -> None:
    for key in (
        "artifact_mode",
        "compiler",
        "compiler_flags",
        "runs",
        "iterations_per_run",
        "warmups",
    ):
        if calibration.get(key) != current.get(key):
            raise RuntimeError(f"calibration {key} does not match this comparison")

    for section, fields in (
        (
            "host",
            (
                "platform",
                "node",
                "machine",
                "processor",
                "cpu_model",
                "cpu_model_source",
                "logical_cpus",
                "process_affinity",
                "python",
            ),
        ),
        ("runner", ("sha256",)),
        ("adapter_source", ("sha256",)),
    ):
        calibration_section = calibration.get(section)
        current_section = current.get(section)
        if not isinstance(calibration_section, dict) or not isinstance(current_section, dict):
            raise RuntimeError(f"calibration is missing {section} provenance")
        for field in fields:
            if calibration_section.get(field) != current_section.get(field):
                raise RuntimeError(
                    f"calibration {section}.{field} does not match this comparison"
                )

    try:
        if current["artifact_mode"] == "owned":
            calibrated_hash = calibration["candidate"]["build"]["identity_digest"]
            current_hash = current["candidate"]["build"]["identity_digest"]
        else:
            calibrated_hash = calibration["candidate"]["artifact"]["sha256"]
            current_hash = current["candidate"]["artifact"]["sha256"]
    except (KeyError, TypeError) as error:
        raise RuntimeError("calibration is missing candidate artifact provenance") from error
    if calibrated_hash != current_hash:
        raise RuntimeError("calibration was not measured with this candidate executable")

    try:
        calibrated_datasets = {
            dataset["name"]: (dataset["size"], dataset["sha256"])
            for dataset in calibration["datasets"]
        }
        current_datasets = {
            dataset["name"]: (dataset["size"], dataset["sha256"])
            for dataset in current["datasets"]
        }
    except (KeyError, TypeError) as error:
        raise RuntimeError("calibration is missing dataset provenance") from error
    for name, identity in current_datasets.items():
        if calibrated_datasets.get(name) != identity:
            raise RuntimeError(f"calibration dataset does not match: {name}")


def write_report(path: Path, report: dict[str, object]) -> None:
    atomic.write_json(path, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-artifacts", action="store_true")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--baseline-ref")
    parser.add_argument("--candidate-ref")
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--baseline-revision")
    parser.add_argument("--candidate-revision")
    parser.add_argument(
        "--adapter-source",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "compare" / "common_driver.cpp",
    )
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--operations", default="all")
    parser.add_argument("--sources", default="buffer,mmap")
    parser.add_argument("--files", default="all")
    parser.add_argument("--mode", choices=("aa", "compare"), default="compare")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--allow-uncalibrated", action="store_true")
    parser.add_argument(
        "--evidence-level",
        choices=("exploratory", "controlled"),
        default="exploratory",
    )
    parser.add_argument("--cpu-affinity")
    parser.add_argument("--compiler")
    parser.add_argument("--compiler-executable", type=Path)
    parser.add_argument("--compiler-flags", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.external_artifacts:
        if args.evidence_level != "exploratory":
            parser.error("--external-artifacts is restricted to exploratory evidence")
        if any(
            value is None
            for value in (
                args.baseline,
                args.candidate,
                args.baseline_revision,
                args.candidate_revision,
            )
        ):
            parser.error(
                "--external-artifacts requires --baseline, --candidate, "
                "--baseline-revision, and --candidate-revision"
            )
        if args.baseline_ref or args.candidate_ref or args.build_root:
            parser.error("external artifacts cannot use owned-build ref options")
    else:
        if args.baseline is not None or args.candidate is not None:
            parser.error("--baseline/--candidate require --external-artifacts")
        if args.baseline_revision is not None or args.candidate_revision is not None:
            parser.error("explicit revisions require --external-artifacts")
        if not args.baseline_ref or not args.candidate_ref:
            parser.error("owned builds require --baseline-ref and --candidate-ref")
        if args.compiler_executable is None:
            parser.error("owned builds require --compiler-executable")
        if args.build_root is None:
            args.build_root = args.output.with_suffix(args.output.suffix + ".build")
    if args.runs < 1:
        parser.error("--runs must be positive")
    if args.evidence_level == "controlled" and args.runs < 20:
        parser.error("controlled evidence requires at least 20 paired runs")
    if args.warmups < 0:
        parser.error("--warmups must not be negative")
    if args.evidence_level == "controlled" and args.warmups < 3:
        parser.error("controlled evidence requires at least three warmup rounds")
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    if args.mode == "compare" and not args.calibration and not args.allow_uncalibrated:
        parser.error("comparison runs require --calibration or --allow-uncalibrated")
    if args.evidence_level == "controlled" and args.allow_uncalibrated:
        parser.error("controlled comparisons cannot use --allow-uncalibrated")
    if args.evidence_level == "controlled":
        if platform.system() != "Linux" or not hasattr(os, "sched_getaffinity"):
            parser.error("controlled comparisons currently require Linux CPU affinity")
        if not args.cpu_affinity:
            parser.error("controlled comparisons require --cpu-affinity")
        try:
            requested_affinity = sorted(
                {int(value) for value in args.cpu_affinity.split(",") if value != ""}
            )
        except ValueError:
            parser.error("--cpu-affinity must be a comma-separated integer list")
        if not requested_affinity or requested_affinity[0] < 0:
            parser.error("--cpu-affinity must contain non-negative CPU indices")
        if requested_affinity != sorted(os.sched_getaffinity(0)):
            parser.error("current process affinity does not match --cpu-affinity")

    artifact_mode = "external" if args.external_artifacts else "owned"
    owned_builds: dict[str, object] | None = None
    if not args.external_artifacts:
        try:
            repository = canonical_existing(args.repository, "benchmark repository")
            compiler = canonical_existing(args.compiler_executable, "compiler executable")
            compiler_flags = shlex.split(args.compiler_flags, posix=os.name != "nt")
            if not compiler_flags:
                raise RuntimeError("--compiler-flags must contain at least one flag")
            owned_builds = builds.build_common_pair(
                repository=repository,
                baseline_reference=args.baseline_ref,
                candidate_reference=args.candidate_ref,
                compiler=compiler,
                compiler_flags=compiler_flags,
                workspace=canonical_output(args.build_root),
            )
            args.compiler_flags = " ".join(compiler_flags)
            args.baseline = Path(str(owned_builds["baseline"]["output"]["path"]))
            args.candidate = Path(str(owned_builds["candidate"]["output"]["path"]))
            args.baseline_revision = str(owned_builds["baseline"]["revision"])
            args.candidate_revision = str(owned_builds["candidate"]["revision"])
            adapter_export = owned_builds["adapter"]
            args.adapter_source = (
                Path(str(adapter_export["root"]))
                / "benchmark"
                / "compare"
                / "common_driver.cpp"
            )
            version = owned_builds["candidate"]["compiler"]["version"]
            identity = (str(version["stdout"]) + "\n" + str(version["stderr"])).strip()
            args.compiler = args.compiler or identity.splitlines()[0]
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(str(error))
    elif args.compiler is None:
        args.compiler = "external-artifact compiler (unverified)"

    try:
        runner_paths = [
            canonical_existing(path, "runner source") for path in runner_source_paths()
        ]
        runner_root = canonical_existing(
            Path(__file__).resolve().parents[2], "runner source root"
        )
        runner_bundle = artifacts.bundle_metadata(
            runner_root, runner_paths, "runner-tool-bundle"
        )
        args.baseline = canonical_existing(args.baseline, "baseline executable")
        args.candidate = canonical_existing(args.candidate, "candidate executable")
        args.adapter_source = canonical_existing(args.adapter_source, "adapter source")
        args.datasets = canonical_existing(args.datasets, "dataset directory")
        for label, path in (
            ("baseline executable", args.baseline),
            ("candidate executable", args.candidate),
            ("adapter source", args.adapter_source),
        ):
            if not path.is_file():
                raise RuntimeError(f"{label} is not a file: {path}")
        if not args.datasets.is_dir():
            raise RuntimeError(f"dataset path is not a directory: {args.datasets}")
        if args.calibration is not None:
            args.calibration = canonical_existing(args.calibration, "calibration")
            if not args.calibration.is_file():
                raise RuntimeError(f"calibration is not a file: {args.calibration}")
        args.output = canonical_output(args.output)
        args.manifest = canonical_output(
            args.manifest
            or args.output.with_suffix(args.output.suffix + ".sha256.json")
        )

        discovered_datasets = sorted(args.datasets.glob("*.csv"))
        dataset_paths = []
        for path in discovered_datasets:
            resolved = canonical_existing(path, f"dataset {path.name}")
            if not resolved.is_file():
                raise RuntimeError(f"dataset is not a file: {path.name}")
            dataset_paths.append((path.name, resolved))
        protected_paths = [
            ("adapter source", args.adapter_source),
            ("baseline executable", args.baseline),
            ("candidate executable", args.candidate),
        ]
        if owned_builds is not None:
            for side in ("baseline", "candidate"):
                export = owned_builds[side]["header_export"]
                export_root = Path(str(export["root"]))
                protected_paths.extend(
                    (
                        f"{side} exported source {entry['path']}",
                        export_root.joinpath(*entry["path"].split("/")),
                    )
                    for entry in export["files"]
                )
        protected_paths.extend(
            (f"runner source {path.name}", path) for path in runner_paths
        )
        protected_paths.extend(
            (f"dataset {name}", path) for name, path in dataset_paths
        )
        if args.calibration is not None:
            protected_paths.append(("calibration", args.calibration))
        reject_output_alias(args.output, protected_paths)
        reject_output_alias(args.manifest, protected_paths)
        if paths_alias(args.output, args.manifest):
            raise RuntimeError("report and manifest paths must be distinct")
    except RuntimeError as error:
        parser.error(str(error))

    baseline_description = describe(args.baseline)
    candidate_description = describe(args.candidate)
    if baseline_description["revision"] != args.baseline_revision:
        parser.error("baseline executable revision does not match --baseline-revision")
    if candidate_description["revision"] != args.candidate_revision:
        parser.error("candidate executable revision does not match --candidate-revision")
    try:
        baseline_contracts = wire.parse_operation_contracts(
            baseline_description["operation_contracts"]
        )
        candidate_contracts = wire.parse_operation_contracts(
            candidate_description["operation_contracts"]
        )
        if baseline_contracts != candidate_contracts:
            raise RuntimeError("baseline and candidate operation contracts differ")
        for description, contracts, side in (
            (baseline_description, baseline_contracts, "baseline"),
            (candidate_description, candidate_contracts, "candidate"),
        ):
            if set(description["operations"].split(",")) != set(contracts):
                raise RuntimeError(f"{side} operation list and contracts differ")
    except RuntimeError as error:
        parser.error(str(error))

    baseline_artifact = artifact_metadata(args.baseline, args.baseline_revision)
    candidate_artifact = artifact_metadata(args.candidate, args.candidate_revision)
    try:
        validate_mode_invariants(
            args.mode,
            str(args.baseline_revision),
            str(args.candidate_revision),
            str(baseline_artifact["sha256"]),
            str(candidate_artifact["sha256"]),
            str(owned_builds["baseline"]["identity_digest"])
            if owned_builds is not None
            else None,
            str(owned_builds["candidate"]["identity_digest"])
            if owned_builds is not None
            else None,
        )
    except ValueError as error:
        parser.error(str(error))

    if not dataset_paths:
        parser.error(f"no CSV datasets found in {args.datasets}")
    by_name = dict(dataset_paths)
    try:
        datasets = selected(args.files, (name for name, _ in dataset_paths))
        operations = selected(args.operations, OPERATIONS)
        sources = selected(args.sources, SOURCES)
    except ValueError as error:
        parser.error(str(error))

    for description, side in (
        (baseline_description, "baseline"),
        (candidate_description, "candidate"),
    ):
        supported_operations = set(description["operations"].split(","))
        supported_sources = set(description["sources"].split(","))
        if not set(operations) <= supported_operations:
            parser.error(f"{side} executable lacks a requested operation")
        if not set(sources) <= supported_sources:
            parser.error(f"{side} executable lacks a requested source")
        if not set(operations) <= set(baseline_contracts):
            parser.error(f"{side} executable lacks a requested operation contract")

    calibration_noise: dict[str, float] = {}
    calibration_metadata: dict[str, object] | None = None
    calibration_report: dict[str, object] | None = None
    if args.calibration:
        calibration_noise, calibration_metadata, calibration_report = load_calibration(
            args.calibration
        )
        if (
            args.evidence_level == "controlled"
            and calibration_report.get("evidence_level") != "controlled"
        ):
            parser.error("controlled comparisons require a controlled A/A calibration")

    report: dict[str, object] = {
        "schema": SCHEMA,
        "artifact_mode": artifact_mode,
        "mode": args.mode,
        "evidence_level": args.evidence_level,
        "controlled_complete": False,
        "decision_eligible": False,
        "status": "running",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs": args.runs,
        "warmups": args.warmups,
        "iterations_per_run": args.iterations,
        "compiler": args.compiler,
        "compiler_flags": args.compiler_flags,
        "host": host_metadata(),
        "runner": runner_bundle,
        "adapter_source": artifact_metadata(
            args.adapter_source,
            str(owned_builds["adapter"]["commit"])
            if owned_builds is not None
            else "shared-source",
        ),
        "baseline": {
            "artifact": baseline_artifact,
            "build": owned_builds["baseline"] if owned_builds is not None else None,
            "description": public_result(baseline_description),
            "description_invocation": invocation_record(baseline_description),
        },
        "candidate": {
            "artifact": candidate_artifact,
            "build": owned_builds["candidate"] if owned_builds is not None else None,
            "description": public_result(candidate_description),
            "description_invocation": invocation_record(candidate_description),
        },
        "datasets": [dataset_metadata(by_name[name], name) for name in datasets],
        "calibration": calibration_metadata,
        "cases": [],
    }
    wire.validate_comparison_report(report)
    write_report(args.output, report)

    try:
        if calibration_report is not None:
            validate_calibration_context(calibration_report, report)
        for dataset_name in datasets:
            for operation in operations:
                expected_scope, supported_sources = baseline_contracts[operation]
                case_sources = [source for source in sources if source in supported_sources]
                if not case_sources:
                    raise RuntimeError(
                        f"operation contract rejects every source for {operation}"
                    )
                for source in case_sources:
                    key = case_key(dataset_name, operation, source)
                    if args.calibration and key not in calibration_noise:
                        raise RuntimeError(
                            f"calibration lacks {dataset_name}/{operation}/{source}"
                        )
                    case = measure_case(
                        args.baseline,
                        args.candidate,
                        operation,
                        by_name[dataset_name],
                        source,
                        args.runs,
                        args.iterations,
                        args.warmups,
                        expected_scope,
                        calibration_noise=calibration_noise.get(key, 0.0),
                        baseline_revision=args.baseline_revision,
                        candidate_revision=args.candidate_revision,
                    )
                    report["cases"].append(case)
                    write_report(args.output, report)
        verify_artifact_unchanged(report["runner"], "runner")
        verify_artifact_unchanged(report["adapter_source"], "adapter source")
        verify_artifact_unchanged(baseline_artifact, "baseline executable")
        verify_artifact_unchanged(candidate_artifact, "candidate executable")
        if owned_builds is not None:
            builds.assert_compatible_builds(
                owned_builds["baseline"], owned_builds["candidate"]
            )
        for dataset in report["datasets"]:
            verify_artifact_unchanged(dataset, f"dataset {dataset['name']}")
        if calibration_metadata is not None:
            verify_artifact_unchanged(calibration_metadata, "calibration")
        report["status"] = "completed"
        report["controlled_complete"] = wire.controlled_complete(
            args.evidence_level,
            report["status"],
            owned_build=artifact_mode == "owned",
        )
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        wire.validate_comparison_report(report)
        write_report(args.output, report)
        artifact_manifest = {
            "schema": ARTIFACT_MANIFEST_SCHEMA,
            "kind": "comparison",
            "report": artifact_metadata(args.output),
            "inputs": {
                "baseline": baseline_artifact,
                "candidate": candidate_artifact,
                "builds": {
                    "baseline": owned_builds["baseline"]["digest"]
                    if owned_builds is not None
                    else None,
                    "candidate": owned_builds["candidate"]["digest"]
                    if owned_builds is not None
                    else None,
                },
                "datasets": [artifact_metadata(by_name[name]) for name in datasets],
            },
        }
        wire.validate_artifact_manifest(artifact_manifest)
        write_report(args.manifest, artifact_manifest)
    except BaseException as error:
        report["status"] = "failed"
        report["controlled_complete"] = False
        report["decision_eligible"] = False
        report["error"] = str(error)
        write_report(args.output, report)
        raise


if __name__ == "__main__":
    main()
