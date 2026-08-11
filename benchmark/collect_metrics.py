#!/usr/bin/env python3
"""Collect fixed-machine CSV2 benchmark counters into a JSON report."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


PERF_EVENTS = ("cycles", "instructions", "branch-misses")


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
    return command


def run_benchmark(
    args: argparse.Namespace,
    track_allocations: bool = False,
    executable: Path | None = None,
) -> dict[str, str]:
    completed = subprocess.run(
        benchmark_command(args, track_allocations, executable),
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_benchmark_output(completed.stdout)


def collect_perf(args: argparse.Namespace, processed_bytes: int) -> dict[str, float]:
    perf = require_tool("perf")
    environment = dict(os.environ)
    environment["LC_ALL"] = "C"
    completed = subprocess.run(
        [
            perf,
            "stat",
            "--no-big-num",
            "-x",
            ";",
            "-r",
            str(args.runs),
            "-e",
            ",".join(PERF_EVENTS),
            "--",
            *benchmark_command(args),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    counters: dict[str, float] = {}
    for line in completed.stderr.splitlines():
        fields = line.split(";")
        if len(fields) < 3:
            continue
        event = fields[2].strip()
        if event not in PERF_EVENTS:
            continue
        value = fields[0].strip()
        if value.startswith("<"):
            raise RuntimeError(f"perf could not count {event}: {value}")
        counters[event] = float(value)
    missing = sorted(set(PERF_EVENTS) - set(counters))
    if missing:
        raise RuntimeError(f"perf did not report: {', '.join(missing)}")

    counters["cycles_per_byte"] = counters["cycles"] / processed_bytes
    counters["instructions_per_byte"] = counters["instructions"] / processed_bytes
    return counters


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
    integer_fields = {"bytes", "iterations", "rows", "cells", "allocations", "allocated_bytes", "checksum"}
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
    parser.add_argument("--skip-perf", action="store_true")
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--skip-size", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if args.runs < 20 and not args.skip_perf:
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
    if not args.skip_perf:
        report["perf"] = collect_perf(args, processed_bytes)
    if not args.skip_rss:
        report["peak_rss_kib"] = collect_peak_rss(args)
    if not args.skip_size:
        report["code_size"] = collect_code_size(args.executable)
    if args.build_command:
        report["clean_build_seconds"] = time_build(args.build_command)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
