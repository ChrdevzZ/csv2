#!/usr/bin/env python3
"""Collect fixed-machine CSV2 benchmark counters into a JSON report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shlex
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


COUNTER_FIELDS = ("cycles", "instructions", "branch_misses")
UINT64_MAX = (1 << 64) - 1
SEMANTIC_FIELDS = (
    "revision",
    "operation",
    "source",
    "bytes",
    "iterations",
    "rows",
    "cells",
    "checksum",
)
INTEGER_FIELDS = {
    "bytes",
    "iterations",
    "rows",
    "cells",
    "allocations",
    "allocated_bytes",
    "hardware_counter_time_enabled",
    "hardware_counter_time_running",
    "cycles",
    "instructions",
    "branch_misses",
    "checksum",
}
FLOAT_FIELDS = {"seconds", "gib_per_second", "rows_per_second", "cells_per_second"}
REQUIRED_BENCHMARK_FIELDS = {
    "revision",
    "operation",
    "source",
    "allocation_tracking",
    "hardware_counter_scope",
    *INTEGER_FIELDS,
    *FLOAT_FIELDS,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_metadata(path: Path, revision: str | None = None) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    result: dict[str, object] = {
        "path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }
    if revision is not None:
        result["revision"] = revision
    return result


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
        raise RuntimeError(f"{label} changed during metrics collection")


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


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(f"required tool was not found: {name}")
    return executable


def parse_benchmark_output(output: str) -> dict[str, str]:
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
    missing = sorted(REQUIRED_BENCHMARK_FIELDS - result.keys())
    if missing:
        raise RuntimeError(
            f"benchmark output is missing required fields: {', '.join(missing)}"
        )
    return result


def public_result(values: dict[str, str]) -> dict[str, str]:
    return {name: value for name, value in values.items() if not name.startswith("_")}


def invocation_record(values: dict[str, str]) -> dict[str, object]:
    command = values.get("_command")
    return {
        "command": json.loads(command) if command else None,
        "stdout": values.get("_stdout"),
        "stderr": values.get("_stderr"),
        "result": numeric_result(values),
    }


def semantic_signature(values: dict[str, str]) -> tuple[str, ...]:
    return tuple(values[name] for name in SEMANTIC_FIELDS)


def require_matching_semantics(
    reference: dict[str, str], current: dict[str, str], label: str
) -> None:
    if semantic_signature(current) != semantic_signature(reference):
        raise RuntimeError(f"{label} changed benchmark semantics")


def validate_benchmark_result(
    args: argparse.Namespace,
    values: dict[str, str],
    expected_bytes: int,
    *,
    track_allocations: bool = False,
    track_hardware_counters: bool = False,
) -> dict[str, object]:
    numeric = numeric_result(values)
    expected = {
        "revision": args.revision,
        "operation": args.operation,
        "source": args.source,
        "iterations": str(args.iterations),
        "bytes": str(expected_bytes),
    }
    for name, value in expected.items():
        if values.get(name) != value:
            raise RuntimeError(
                f"benchmark metadata mismatch for {name}: expected {value}, "
                f"got {values.get(name)}"
            )

    expected_allocation_tracking = "available" if track_allocations else "unavailable"
    if values.get("allocation_tracking") != expected_allocation_tracking:
        raise RuntimeError(
            "benchmark allocation tracking mismatch: "
            f"expected {expected_allocation_tracking}, "
            f"got {values.get('allocation_tracking')}"
        )
    if not track_allocations and (
        numeric["allocations"] != 0 or numeric["allocated_bytes"] != 0
    ):
        raise RuntimeError(
            "unavailable allocation tracking must report zero allocations and bytes"
        )
    expected_counter_scope = "timed_operation" if track_hardware_counters else "disabled"
    if values.get("hardware_counter_scope") != expected_counter_scope:
        raise RuntimeError(
            "benchmark hardware counter scope mismatch: "
            f"expected {expected_counter_scope}, got {values.get('hardware_counter_scope')}"
        )
    if track_hardware_counters:
        if (
            numeric["hardware_counter_time_enabled"] <= 0
            or numeric["hardware_counter_time_running"] <= 0
        ):
            raise RuntimeError("hardware counter timing values must be positive")
    elif (
        numeric["hardware_counter_time_enabled"] != 0
        or numeric["hardware_counter_time_running"] != 0
        or any(numeric[name] != 0 for name in COUNTER_FIELDS)
    ):
        raise RuntimeError("disabled hardware counters must report zero values")
    return numeric


def benchmark_command(
    args: argparse.Namespace,
    track_allocations: bool = False,
    track_hardware_counters: bool = False,
    executable: Path | None = None,
) -> list[str]:
    command = [
        str(executable or args.executable),
        "--operation",
        args.operation,
        "--input",
        str(args.input),
        "--source",
        args.source,
        "--iterations",
        str(args.iterations),
    ]
    if track_allocations:
        command.append("--track-allocations")
    if track_hardware_counters:
        command.append("--track-counters")
    return command


def run_benchmark(
    args: argparse.Namespace,
    track_allocations: bool = False,
    track_hardware_counters: bool = False,
    executable: Path | None = None,
) -> dict[str, str]:
    command = benchmark_command(
        args, track_allocations, track_hardware_counters, executable
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "benchmark command failed\n"
            f"command: {json.dumps(command)}\n"
            f"exit: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    result = parse_benchmark_output(completed.stdout)
    result["_command"] = json.dumps(command)
    result["_stdout"] = completed.stdout.rstrip("\n")
    result["_stderr"] = completed.stderr.rstrip("\n")
    return result


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def summarize_counter_samples(
    samples: list[dict[str, str]], processed_bytes: int, reference: dict[str, str]
) -> dict[str, object]:
    if not samples or processed_bytes <= 0:
        raise RuntimeError("hardware counter samples and processed bytes must be positive")

    normalized: list[dict[str, object]] = []
    values: dict[str, list[float]] = {
        "cycles": [],
        "instructions": [],
        "branch_misses": [],
        "cycles_per_byte": [],
        "instructions_per_byte": [],
    }
    for sample in samples:
        require_matching_semantics(reference, sample, "hardware counter tracking")
        if sample.get("hardware_counter_scope") != "timed_operation":
            raise RuntimeError("hardware counters must cover timed_operation")
        time_enabled = int(sample["hardware_counter_time_enabled"])
        time_running = int(sample["hardware_counter_time_running"])
        if time_enabled <= 0 or time_running <= 0:
            raise RuntimeError("hardware counter timing values must be positive")
        scale = time_enabled / time_running
        scaled = {name: int(sample[name]) * scale for name in COUNTER_FIELDS}
        scaled["cycles_per_byte"] = scaled["cycles"] / processed_bytes
        scaled["instructions_per_byte"] = scaled["instructions"] / processed_bytes
        normalized.append(
            {
                "time_enabled": time_enabled,
                "time_running": time_running,
                "scale": scale,
                "raw": {name: int(sample[name]) for name in COUNTER_FIELDS},
                "scaled": scaled,
                "benchmark": numeric_result(sample),
                "invocation": invocation_record(sample),
            }
        )
        for name in values:
            values[name].append(float(scaled[name]))

    return {
        "scope": "timed_operation",
        "runs": len(normalized),
        "samples": normalized,
        "median": {name: statistics.median(data) for name, data in values.items()},
        "mad": {name: median_absolute_deviation(data) for name, data in values.items()},
    }


def collect_hardware_counters(
    args: argparse.Namespace,
    processed_bytes: int,
    expected_bytes: int,
    reference: dict[str, str],
) -> dict[str, object]:
    samples = []
    for _ in range(args.runs):
        sample = run_benchmark(args, track_hardware_counters=True)
        validate_benchmark_result(
            args, sample, expected_bytes, track_hardware_counters=True
        )
        samples.append(sample)
    return summarize_counter_samples(samples, processed_bytes, reference)


def collect_peak_rss(
    args: argparse.Namespace, expected_bytes: int, reference: dict[str, str]
) -> dict[str, object]:
    time_tool = "/usr/bin/time"
    if not Path(time_tool).is_file():
        raise RuntimeError("required tool was not found: /usr/bin/time")
    with tempfile.TemporaryDirectory(prefix="csv2-metrics-") as directory:
        report_path = Path(directory) / "time.txt"
        command = [time_tool, "-v", "-o", str(report_path), *benchmark_command(args)]
        environment = {**os.environ, "LC_ALL": "C"}
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "peak RSS command failed\n"
                f"command: {json.dumps(command)}\n"
                f"exit: {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        benchmark = parse_benchmark_output(completed.stdout)
        validate_benchmark_result(args, benchmark, expected_bytes)
        require_matching_semantics(reference, benchmark, "peak RSS measurement")
        time_report = report_path.read_text(encoding="utf-8")
        for line in time_report.splitlines():
            if "Maximum resident set size (kbytes):" in line:
                kib = int(line.rsplit(":", 1)[1].strip())
                if kib < 0:
                    raise RuntimeError("peak RSS must be non-negative")
                return {
                    "scope": "whole_process",
                    "kib": kib,
                    "command": command,
                    "environment": {"LC_ALL": "C"},
                    "stdout": completed.stdout.rstrip("\n"),
                    "stderr": completed.stderr.rstrip("\n"),
                    "time_report": time_report.rstrip("\n"),
                    "benchmark": numeric_result(benchmark),
                }
    raise RuntimeError("/usr/bin/time did not report peak RSS")


def collect_code_size(executable: Path) -> dict[str, object]:
    size_tool = require_tool("size")
    command = [size_tool, "--format=berkeley", str(executable)]
    environment = {**os.environ, "LC_ALL": "C"}
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    lines = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0][:4] != ["text", "data", "bss", "dec"]:
        raise RuntimeError("unexpected size output")
    values = lines[1]
    sizes = {
        "text_bytes": int(values[0]),
        "data_bytes": int(values[1]),
        "bss_bytes": int(values[2]),
        "total_bytes": int(values[3]),
    }
    if any(value < 0 for value in sizes.values()):
        raise RuntimeError("executable sizes must be non-negative")
    return {
        **sizes,
        "command": command,
        "environment": {"LC_ALL": "C"},
        "stdout": completed.stdout.rstrip("\n"),
        "stderr": completed.stderr.rstrip("\n"),
    }


def time_build(command: str) -> dict[str, object]:
    arguments = shlex.split(command)
    if not arguments:
        raise RuntimeError("--build-command must not be empty")
    started = time.perf_counter()
    completed = subprocess.run(arguments, capture_output=True, text=True)
    seconds = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            "clean build command failed\n"
            f"command: {json.dumps(arguments)}\n"
            f"exit: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return {
        "command": arguments,
        "cwd": str(Path.cwd().resolve()),
        "seconds": seconds,
        "stdout": completed.stdout.rstrip("\n"),
        "stderr": completed.stderr.rstrip("\n"),
    }


def numeric_result(values: dict[str, str]) -> dict[str, object]:
    result: dict[str, object] = public_result(values)
    for name in INTEGER_FIELDS & values.keys():
        try:
            parsed = int(values[name])
        except ValueError as error:
            raise RuntimeError(f"benchmark field must be an integer: {name}") from error
        if parsed < 0:
            raise RuntimeError(f"benchmark field must be non-negative: {name}")
        if parsed > UINT64_MAX:
            raise RuntimeError(f"benchmark field is outside uint64 range: {name}")
        result[name] = parsed
    for name in FLOAT_FIELDS & values.keys():
        try:
            parsed = float(values[name])
        except ValueError as error:
            raise RuntimeError(f"benchmark field must be numeric: {name}") from error
        if not math.isfinite(parsed):
            raise RuntimeError(f"benchmark field must be finite: {name}")
        if parsed < 0:
            raise RuntimeError(f"benchmark field must be non-negative: {name}")
        result[name] = parsed
    if result.get("bytes", 0) <= 0 or result.get("iterations", 0) <= 0:
        raise RuntimeError("benchmark bytes and iterations must be positive")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--allocation-executable", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--compiler-flags", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", choices=("buffer", "mmap"), default="buffer")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--build-command")
    parser.add_argument(
        "--skip-counters", "--skip-perf", dest="skip_counters", action="store_true"
    )
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--skip-size", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if args.runs < 20 and not args.skip_counters:
        parser.error("--runs must be at least 20 for fixed-machine counter collection")
    args.executable = args.executable.resolve()
    if args.allocation_executable is None:
        args.allocation_executable = args.executable.with_name(
            f"{args.executable.stem}_allocations{args.executable.suffix}"
        )
    args.allocation_executable = args.allocation_executable.resolve()
    args.input = args.input.resolve()
    clean_build = time_build(args.build_command) if args.build_command else None
    if not args.executable.is_file():
        parser.error(f"benchmark executable does not exist: {args.executable}")
    if not args.allocation_executable.is_file():
        parser.error(
            "allocation benchmark executable does not exist: "
            f"{args.allocation_executable}"
        )
    if not args.input.is_file():
        parser.error(f"input does not exist: {args.input}")

    expected_bytes = args.input.stat().st_size
    if expected_bytes <= 0:
        parser.error("benchmark input must not be empty")

    collector_metadata = artifact_metadata(Path(__file__))
    executable_metadata = artifact_metadata(args.executable, args.revision)
    allocation_executable_metadata = artifact_metadata(
        args.allocation_executable, args.revision
    )
    dataset_metadata = artifact_metadata(args.input)

    benchmark = run_benchmark(args)
    validate_benchmark_result(args, benchmark, expected_bytes)
    allocations = run_benchmark(
        args,
        track_allocations=True,
        executable=args.allocation_executable,
    )
    validate_benchmark_result(
        args, allocations, expected_bytes, track_allocations=True
    )
    require_matching_semantics(benchmark, allocations, "allocation tracking")
    processed_bytes = expected_bytes * args.iterations
    model, model_source = cpu_identity()

    report: dict[str, object] = {
        "schema": "csv2-fixed-machine-metrics-v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
            "cpu_model": model,
            "cpu_model_source": model_source,
            "logical_cpus": os.cpu_count(),
        },
        "compiler": args.compiler,
        "compiler_flags": args.compiler_flags,
        "collector": collector_metadata,
        "executable": executable_metadata,
        "allocation_executable": allocation_executable_metadata,
        "dataset": dataset_metadata,
        "command": benchmark_command(args),
        "benchmark": numeric_result(benchmark),
        "benchmark_invocation": invocation_record(benchmark),
        "allocation_tracking": {
            "allocations": int(allocations["allocations"]),
            "allocated_bytes": int(allocations["allocated_bytes"]),
            "benchmark": numeric_result(allocations),
            "invocation": invocation_record(allocations),
        },
    }
    if not args.skip_counters:
        report["hardware_counters"] = collect_hardware_counters(
            args, processed_bytes, expected_bytes, benchmark
        )
    if not args.skip_rss:
        report["peak_rss"] = collect_peak_rss(args, expected_bytes, benchmark)
    if not args.skip_size:
        report["code_size"] = collect_code_size(args.executable)
    if clean_build is not None:
        report["clean_build"] = clean_build

    verify_artifact_unchanged(collector_metadata, "collector")
    verify_artifact_unchanged(executable_metadata, "benchmark executable")
    verify_artifact_unchanged(
        allocation_executable_metadata, "allocation benchmark executable"
    )
    verify_artifact_unchanged(dataset_metadata, "dataset")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, args.output)


if __name__ == "__main__":
    main()
