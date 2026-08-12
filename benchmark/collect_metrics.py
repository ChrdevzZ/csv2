#!/usr/bin/env python3
"""Collect fixed-machine CSV2 benchmark counters into a JSON report."""

from __future__ import annotations

import argparse
import json
import platform
import shlex
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path


COUNTER_FIELDS = ("cycles", "instructions", "branch_misses")


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(f"required tool was not found: {name}")
    return executable


def parse_benchmark_output(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("benchmark must print exactly one result line")
    return dict(part.split("=", 1) for part in lines[0].split())


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
    completed = subprocess.run(
        benchmark_command(args, track_allocations, track_hardware_counters, executable),
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_benchmark_output(completed.stdout)


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def summarize_counter_samples(
    samples: list[dict[str, str]], processed_bytes: int, expected_checksum: str
) -> dict[str, object]:
    if not samples or processed_bytes <= 0:
        raise RuntimeError("hardware counter samples and processed bytes must be positive")
    checksums = {sample.get("checksum") for sample in samples}
    if len(checksums) != 1:
        raise RuntimeError("hardware counter samples produced different checksums")
    if checksums != {expected_checksum}:
        raise RuntimeError("hardware counter tracking changed the benchmark checksum")

    normalized: list[dict[str, object]] = []
    values: dict[str, list[float]] = {
        "cycles": [],
        "instructions": [],
        "branch_misses": [],
        "cycles_per_byte": [],
        "instructions_per_byte": [],
    }
    for sample in samples:
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
    args: argparse.Namespace, processed_bytes: int, expected_checksum: str
) -> dict[str, object]:
    samples = [run_benchmark(args, track_hardware_counters=True) for _ in range(args.runs)]
    return summarize_counter_samples(samples, processed_bytes, expected_checksum)


def collect_peak_rss(args: argparse.Namespace) -> int:
    time_tool = "/usr/bin/time"
    if not Path(time_tool).is_file():
        raise RuntimeError("required tool was not found: /usr/bin/time")
    with tempfile.TemporaryDirectory(prefix="csv2-metrics-") as directory:
        report_path = Path(directory) / "time.txt"
        subprocess.run(
            [time_tool, "-v", "-o", str(report_path), *benchmark_command(args)],
            check=True,
            capture_output=True,
            text=True,
        )
        for line in report_path.read_text(encoding="utf-8").splitlines():
            if "Maximum resident set size (kbytes):" in line:
                return int(line.rsplit(":", 1)[1].strip())
    raise RuntimeError("/usr/bin/time did not report peak RSS")


def collect_code_size(executable: Path) -> dict[str, int]:
    size_tool = require_tool("size")
    completed = subprocess.run(
        [size_tool, "--format=berkeley", str(executable)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0][:4] != ["text", "data", "bss", "dec"]:
        raise RuntimeError("unexpected size output")
    values = lines[1]
    return {
        "text_bytes": int(values[0]),
        "data_bytes": int(values[1]),
        "bss_bytes": int(values[2]),
        "total_bytes": int(values[3]),
    }


def time_build(command: str) -> float:
    arguments = shlex.split(command)
    if not arguments:
        raise RuntimeError("--build-command must not be empty")
    started = time.perf_counter()
    subprocess.run(arguments, check=True)
    return time.perf_counter() - started


def numeric_result(values: dict[str, str]) -> dict[str, object]:
    integer_fields = {
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
    float_fields = {"seconds", "gib_per_second", "rows_per_second", "cells_per_second"}
    result: dict[str, object] = dict(values)
    for name in integer_fields & values.keys():
        result[name] = int(values[name])
    for name in float_fields & values.keys():
        result[name] = float(values[name])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--allocation-executable", type=Path)
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
    if not args.executable.is_file():
        parser.error(f"benchmark executable does not exist: {args.executable}")
    if not args.allocation_executable.is_file():
        parser.error(
            "allocation benchmark executable does not exist: "
            f"{args.allocation_executable}"
        )
    if not args.input.is_file():
        parser.error(f"input does not exist: {args.input}")

    benchmark = run_benchmark(args)
    allocations = run_benchmark(
        args,
        track_allocations=True,
        executable=args.allocation_executable,
    )
    if allocations["checksum"] != benchmark["checksum"]:
        raise RuntimeError("allocation tracking changed the benchmark checksum")
    processed_bytes = int(benchmark["bytes"]) * int(benchmark["iterations"])

    report: dict[str, object] = {
        "machine": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "command": benchmark_command(args),
        "benchmark": numeric_result(benchmark),
        "allocation_tracking": {
            "allocations": int(allocations["allocations"]),
            "allocated_bytes": int(allocations["allocated_bytes"]),
        },
    }
    if not args.skip_counters:
        report["hardware_counters"] = collect_hardware_counters(
            args, processed_bytes, benchmark["checksum"]
        )
    if not args.skip_rss:
        report["peak_rss"] = {"scope": "whole_process", "kib": collect_peak_rss(args)}
    if not args.skip_size:
        report["code_size"] = collect_code_size(args.executable)
    if args.build_command:
        report["clean_build_seconds"] = time_build(args.build_command)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
