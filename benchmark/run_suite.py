#!/usr/bin/env python3
"""Auditable paired benchmark runner for the version-neutral CSV2 driver."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence


PROTOCOL = "csv2-common-v1"
SCHEMA = "csv2-benchmark-report-v2"
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
}

Executable = Path | Sequence[Path | str]
Invoke = Callable[[Executable, str, Path, str, int], dict[str, str]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_existing(path: Path, label: str) -> Path:
    try:
        return path.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(f"{label} does not exist or cannot be resolved: {path}") from error


def canonical_output(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(f"output path cannot be resolved: {path}") from error


def paths_alias(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return left.resolve(strict=False) == right.resolve(strict=False)


def reject_output_alias(
    output: Path, protected_paths: Iterable[tuple[str, Path]]
) -> None:
    for label, protected in protected_paths:
        if paths_alias(output, protected):
            raise RuntimeError(f"output path aliases {label}: {protected}")


def replace_report(temporary: Path, output: Path) -> None:
    for attempt in range(100):
        try:
            os.replace(temporary, output)
            return
        except PermissionError as error:
            if os.name != "nt" or error.winerror not in (5, 32) or attempt == 99:
                raise
            time.sleep(0.01)


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
    return {
        "platform": platform.platform(),
        "node": platform.node(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_model": model,
        "cpu_model_source": model_source,
        "logical_cpus": os.cpu_count(),
        "python": platform.python_version(),
    }


def command_prefix(executable: Executable) -> list[str]:
    if isinstance(executable, Path):
        return [str(executable)]
    return [str(part) for part in executable]


def parse_key_value_line(output: str, required: set[str]) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("benchmark must print exactly one result line")
    result: dict[str, str] = {}
    for part in lines[0].split():
        if part.count("=") != 1:
            raise RuntimeError(f"malformed benchmark field: {part!r}")
        key, value = part.split("=", 1)
        if not key or not value:
            raise RuntimeError(f"malformed benchmark field: {part!r}")
        if key in result:
            raise RuntimeError(f"duplicate key in benchmark output: {key}")
        result[key] = value
    missing = sorted(required - result.keys())
    if missing:
        raise RuntimeError(f"benchmark output is missing required fields: {', '.join(missing)}")
    return result


def parse_output(output: str) -> dict[str, str]:
    result = parse_key_value_line(output, RESULT_FIELDS)
    if result["protocol"] != PROTOCOL:
        raise RuntimeError(f"unsupported benchmark protocol: {result['protocol']}")
    return result


def validate_case_matrix(operations: Sequence[str], sources: Sequence[str]) -> None:
    if "legacy_mmap_rows_cells" in operations and "mmap" not in sources:
        raise ValueError("legacy_mmap_rows_cells requires source mmap")


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
            "prepared_scope",
            "legacy_scope",
        },
    )
    if result["protocol"] != PROTOCOL:
        raise RuntimeError(f"unsupported benchmark protocol: {result['protocol']}")
    result["_command"] = json.dumps(command)
    result["_stdout"] = completed.stdout.rstrip("\n")
    result["_stderr"] = completed.stderr.rstrip("\n")
    return result


def artifact_metadata(path: Path, revision: str) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "path": str(resolved),
        "revision": revision,
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def verify_artifact_unchanged(metadata: dict[str, object], label: str) -> None:
    try:
        path = Path(str(metadata["path"]))
        expected_size = int(metadata["size"])
        expected_hash = str(metadata["sha256"])
        current_size = path.stat().st_size
        current_hash = sha256_file(path)
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise RuntimeError(f"cannot revalidate {label} provenance") from error
    if current_size != expected_size or current_hash != expected_hash:
        raise RuntimeError(f"{label} changed during benchmark execution")


def dataset_metadata(path: Path, logical_name: str | None = None) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "name": logical_name if logical_name is not None else path.name,
        "path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def median_mad(values: list[float]) -> tuple[float, float]:
    median = statistics.median(values)
    mad = statistics.median(abs(value - median) for value in values)
    return median, mad


def bootstrap_ratio(
    baseline: list[float], candidate: list[float], samples: int = 5000
) -> tuple[float, float]:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired bootstrap requires equally sized non-empty samples")
    generator = random.Random(0x43535632)
    ratios = []
    for _ in range(samples):
        indices = [generator.randrange(len(baseline)) for _ in baseline]
        base_sample = [baseline[index] for index in indices]
        candidate_sample = [candidate[index] for index in indices]
        ratios.append(statistics.median(candidate_sample) / statistics.median(base_sample))
    ratios.sort()
    return ratios[int(samples * 0.025)], ratios[min(int(samples * 0.975), samples - 1)]


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
    expected_bytes: int,
    expected_revision: str | None = None,
) -> float:
    if operation == "rows_cells":
        expected_scope = "traversal_only"
    elif operation == "legacy_mmap_rows_cells":
        expected_scope = "mmap_and_traversal"
    else:
        expected_scope = "writer_only"
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
        or any(
            value > UINT64_MAX
            for value in (byte_count, rows, cells, row_bytes, checksum)
        )
    ):
        raise RuntimeError("benchmark numeric fields are outside their valid range")
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
    invoke_fn: Invoke = invoke,
    calibration_noise: float = 0.0,
    baseline_revision: str | None = None,
    candidate_revision: str | None = None,
    expected_bytes: int | None = None,
) -> dict[str, object]:
    if not math.isfinite(calibration_noise) or calibration_noise < 0:
        raise ValueError("calibration noise must be finite and non-negative")
    baseline_values: list[float] = []
    candidate_values: list[float] = []
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
        if phase == "sample":
            (baseline_values if side == "baseline" else candidate_values).append(throughput)

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

    base_median, base_mad = median_mad(baseline_values)
    candidate_median, candidate_mad = median_mad(candidate_values)
    low, high = bootstrap_ratio(baseline_values, candidate_values)
    measured_noise = 2.0 * base_mad / base_median if base_median else float("inf")
    threshold = max(0.05, measured_noise, calibration_noise)
    regression = candidate_median < base_median * (1.0 - threshold) and high < 1.0
    improvement = candidate_median > base_median * (1.0 + threshold) and low > 1.0
    observed_noise = max(
        abs(candidate_median / base_median - 1.0), abs(low - 1.0), abs(high - 1.0)
    )
    return {
        "dataset": dataset.name,
        "operation": operation,
        "source": source,
        "semantic_signature": list(signature or ()),
        "baseline": {"median": base_median, "mad": base_mad, "samples": baseline_values},
        "candidate": {
            "median": candidate_median,
            "mad": candidate_mad,
            "samples": candidate_values,
        },
        "candidate_over_baseline_95pct": [low, high],
        "measured_noise": measured_noise,
        "calibration_noise": calibration_noise,
        "observed_noise": observed_noise,
        "regression_threshold": threshold,
        "regression": regression,
        "improvement": improvement,
        "launches": launches,
    }


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
    for key in ("compiler", "compiler_flags", "runs", "iterations_per_run", "warmups"):
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
        calibrated_artifact = calibration["candidate"]["artifact"]
        current_artifact = current["candidate"]["artifact"]
        calibrated_hash = calibrated_artifact["sha256"]
        current_hash = current_artifact["sha256"]
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
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
            descriptor = -1
            json.dump(report, destination, indent=2, sort_keys=True)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        replace_report(temporary, path)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--candidate-revision", required=True)
    parser.add_argument(
        "--adapter-source", type=Path, default=Path(__file__).with_name("common_driver.cpp")
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
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--compiler-flags", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 20:
        parser.error("--runs must be at least 20 for regression decisions")
    if args.warmups < 0:
        parser.error("--warmups must not be negative")
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    if args.mode == "compare" and not args.calibration and not args.allow_uncalibrated:
        parser.error("comparison runs require --calibration or --allow-uncalibrated")

    try:
        runner_path = canonical_existing(Path(__file__), "runner")
        args.baseline = canonical_existing(args.baseline, "baseline executable")
        args.candidate = canonical_existing(args.candidate, "candidate executable")
        args.adapter_source = canonical_existing(args.adapter_source, "adapter source")
        args.datasets = canonical_existing(args.datasets, "dataset directory")
        for label, path in (
            ("runner", runner_path),
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

        discovered_datasets = sorted(args.datasets.glob("*.csv"))
        dataset_paths = []
        for path in discovered_datasets:
            resolved = canonical_existing(path, f"dataset {path.name}")
            if not resolved.is_file():
                raise RuntimeError(f"dataset is not a file: {path.name}")
            dataset_paths.append((path.name, resolved))
        protected_paths = [
            ("runner", runner_path),
            ("adapter source", args.adapter_source),
            ("baseline executable", args.baseline),
            ("candidate executable", args.candidate),
        ]
        protected_paths.extend(
            (f"dataset {name}", path) for name, path in dataset_paths
        )
        if args.calibration is not None:
            protected_paths.append(("calibration", args.calibration))
        reject_output_alias(args.output, protected_paths)
    except RuntimeError as error:
        parser.error(str(error))

    baseline_description = describe(args.baseline)
    candidate_description = describe(args.candidate)
    if baseline_description["revision"] != args.baseline_revision:
        parser.error("baseline executable revision does not match --baseline-revision")
    if candidate_description["revision"] != args.candidate_revision:
        parser.error("candidate executable revision does not match --candidate-revision")

    baseline_artifact = artifact_metadata(args.baseline, args.baseline_revision)
    candidate_artifact = artifact_metadata(args.candidate, args.candidate_revision)
    if args.mode == "aa" and baseline_artifact["sha256"] != candidate_artifact["sha256"]:
        parser.error("A/A calibration requires byte-identical executables")

    if not dataset_paths:
        parser.error(f"no CSV datasets found in {args.datasets}")
    by_name = dict(dataset_paths)
    try:
        datasets = selected(args.files, (name for name, _ in dataset_paths))
        operations = selected(args.operations, OPERATIONS)
        sources = selected(args.sources, SOURCES)
        validate_case_matrix(operations, sources)
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

    calibration_noise: dict[str, float] = {}
    calibration_metadata: dict[str, object] | None = None
    calibration_report: dict[str, object] | None = None
    if args.calibration:
        calibration_noise, calibration_metadata, calibration_report = load_calibration(
            args.calibration
        )

    report: dict[str, object] = {
        "schema": SCHEMA,
        "mode": args.mode,
        "status": "running",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs": args.runs,
        "warmups": args.warmups,
        "iterations_per_run": args.iterations,
        "compiler": args.compiler,
        "compiler_flags": args.compiler_flags,
        "host": host_metadata(),
        "runner": artifact_metadata(runner_path, "runner-source"),
        "adapter_source": artifact_metadata(args.adapter_source, "shared-source"),
        "baseline": {
            "artifact": baseline_artifact,
            "description": public_result(baseline_description),
            "description_invocation": invocation_record(baseline_description),
        },
        "candidate": {
            "artifact": candidate_artifact,
            "description": public_result(candidate_description),
            "description_invocation": invocation_record(candidate_description),
        },
        "datasets": [dataset_metadata(by_name[name], name) for name in datasets],
        "calibration": calibration_metadata,
        "cases": [],
    }
    write_report(args.output, report)

    try:
        if calibration_report is not None:
            validate_calibration_context(calibration_report, report)
        for dataset_name in datasets:
            for operation in operations:
                case_sources = ["mmap"] if operation == "legacy_mmap_rows_cells" else sources
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
        for dataset in report["datasets"]:
            verify_artifact_unchanged(dataset, f"dataset {dataset['name']}")
        if calibration_metadata is not None:
            verify_artifact_unchanged(calibration_metadata, "calibration")
        report["status"] = "completed"
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_report(args.output, report)
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = str(error)
        write_report(args.output, report)
        raise


if __name__ == "__main__":
    main()
