"""Collect provenance-bound current-tree timing and machine metrics."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from . import METRICS_SCHEMA
from . import artifacts, atomic, protocol, statistics


TIME_SCALE = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}
PMU_COUNTERS = ("cycles", "instructions", "branch-misses")


def collector_source_paths() -> list[Path]:
    benchmark_root = Path(__file__).resolve().parents[2]
    package_root = Path(__file__).resolve().parent
    return [
        benchmark_root / "collect_metrics.py",
        package_root / "__init__.py",
        package_root / "artifacts.py",
        package_root / "atomic.py",
        package_root / "metrics.py",
        package_root / "protocol.py",
        package_root / "statistics.py",
    ]


def cpu_identity() -> tuple[str, str]:
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                name, separator, value = line.partition(":")
                if separator and name.strip() in {"model name", "Hardware", "Processor"}:
                    if value.strip():
                        return value.strip(), f"/proc/cpuinfo:{name.strip()}"
        except OSError:
            pass
    value = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
    if value:
        return value, "environment:PROCESSOR_IDENTIFIER"
    value = platform.processor().strip()
    return (value, "platform.processor") if value else ("unknown", "unavailable")


def machine_metadata() -> dict[str, object]:
    model, source = cpu_identity()
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        affinity = sorted(os.sched_getaffinity(0))
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "node": platform.node(),
        "cpu_model": model,
        "cpu_model_source": source,
        "logical_cpus": os.cpu_count() or 1,
        "process_affinity": affinity,
        "python": platform.python_version(),
    }


def run(
    command: Sequence[str], *, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command), capture_output=True, text=True, env=environment
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "benchmark command failed\n"
            f"command: {json.dumps(list(command))}\n"
            f"exit: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def verify_command(executable: Path, operation: str, input_path: Path, source: str) -> list[str]:
    return [
        str(executable),
        "--csv2-input",
        str(input_path),
        "--csv2-source",
        source,
        "--csv2-operation",
        operation,
        "--csv2-verify",
    ]


def verify(
    executable: Path, operation: str, input_path: Path, source: str, revision: str
) -> tuple[dict[str, str], dict[str, object]]:
    command = verify_command(executable, operation, input_path, source)
    completed = run(command)
    values = protocol.parse_current(completed.stdout)
    expected = {"operation": operation, "source": source, "revision": revision}
    for field, value in expected.items():
        if values[field] != value:
            raise RuntimeError(
                f"verification metadata mismatch for {field}: expected {value}, got {values[field]}"
            )
    return values, {
        "command": command,
        "stdout": completed.stdout.rstrip("\n"),
        "stderr": completed.stderr.rstrip("\n"),
    }


def timing_command(
    executable: Path,
    operation: str,
    input_path: Path,
    source: str,
    output: Path,
    runs: int,
    minimum_time: str,
    warmup_seconds: float,
    pmu: bool = False,
) -> list[str]:
    # Google Benchmark uses std::regex. Python's re.escape emits ``\-``, which
    # is rejected by some standard-library regex implementations outside a
    # character class even though '-' is literal there.
    prefix = re.escape(f"csv2/{operation}/{source}/").replace(r"\-", "-")
    command = [
        str(executable),
        "--csv2-input",
        str(input_path),
        "--csv2-source",
        source,
        "--csv2-operation",
        operation,
        f"--benchmark_filter=^{prefix}",
        f"--benchmark_repetitions={runs}",
        f"--benchmark_min_time={minimum_time}",
        f"--benchmark_min_warmup_time={warmup_seconds}",
        "--benchmark_enable_random_interleaving=true",
        "--benchmark_report_aggregates_only=false",
        "--benchmark_display_aggregates_only=false",
        "--benchmark_out_format=json",
        f"--benchmark_out={output}",
    ]
    if pmu:
        command.append(f"--benchmark_perf_counters={','.join(PMU_COUNTERS)}")
    return command


def parse_timing_report(
    path: Path, expected_runs: int, *, require_pmu: bool = False
) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        records = document["benchmarks"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("Google Benchmark JSON is malformed") from error
    samples: list[dict[str, object]] = []
    names: set[str] = set()
    for record in records:
        if record.get("run_type", "iteration") != "iteration":
            continue
        unit = str(record.get("time_unit", ""))
        if unit not in TIME_SCALE:
            raise RuntimeError(f"unsupported Google Benchmark time unit: {unit}")
        seconds = (
            protocol.finite_nonnegative(record.get("real_time"), "real_time")
            * TIME_SCALE[unit]
        )
        if seconds <= 0:
            raise RuntimeError("benchmark sample duration must be positive")
        name = str(record.get("name", ""))
        if not name:
            raise RuntimeError("benchmark sample has no name")
        names.add(name)
        sample: dict[str, object] = {
            "name": name,
            "seconds": seconds,
            "bytes_per_second": protocol.finite_nonnegative(
                record.get("bytes_per_second", 0), "bytes_per_second"
            ),
            "items_per_second": protocol.finite_nonnegative(
                record.get("items_per_second", 0), "items_per_second"
            ),
        }
        counters = {}
        for counter in PMU_COUNTERS:
            if counter in record:
                counters[counter] = protocol.finite_nonnegative(record[counter], counter)
        if counters:
            sample["pmu"] = counters
        if require_pmu and set(counters) != set(PMU_COUNTERS):
            missing = sorted(set(PMU_COUNTERS) - set(counters))
            raise RuntimeError(
                "timing report is missing required PMU counters: " + ", ".join(missing)
            )
        samples.append(sample)
    if len(names) != 1:
        raise RuntimeError("timing report must contain exactly one benchmark name")
    if len(samples) != expected_runs:
        raise RuntimeError(
            f"timing report contains {len(samples)} samples; expected {expected_runs}"
        )
    throughput = [float(sample["bytes_per_second"]) for sample in samples]
    duration = [float(sample["seconds"]) for sample in samples]
    throughput_median, throughput_mad = statistics.median_mad(throughput)
    duration_median, duration_mad = statistics.median_mad(duration)
    return {
        "benchmark": next(iter(names)),
        "runs": len(samples),
        "samples": samples,
        "bytes_per_second": {"median": throughput_median, "mad": throughput_mad},
        "seconds": {"median": duration_median, "mad": duration_mad},
    }


def collect_timing(
    args: argparse.Namespace, *, pmu: bool = False
) -> tuple[dict[str, object], dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="csv2-current-") as directory:
        output = Path(directory) / "benchmark.json"
        command = timing_command(
            args.executable,
            args.operation,
            args.input,
            args.source,
            output,
            args.runs,
            args.minimum_time,
            args.warmup_seconds,
            pmu,
        )
        completed = run(command)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(
                "Google Benchmark produced no JSON report\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        result = parse_timing_report(output, args.runs, require_pmu=pmu)
        invocation = {
            "command": command,
            "stdout": completed.stdout.rstrip("\n"),
            "stderr": completed.stderr.rstrip("\n"),
        }
        return result, invocation


def collect_peak_rss(args: argparse.Namespace) -> dict[str, object] | None:
    time_tool = Path("/usr/bin/time")
    if not time_tool.is_file():
        return None
    with tempfile.TemporaryDirectory(prefix="csv2-rss-") as directory:
        report = Path(directory) / "time.txt"
        timing = Path(directory) / "benchmark.json"
        benchmark = timing_command(
            args.executable,
            args.operation,
            args.input,
            args.source,
            timing,
            1,
            args.minimum_time,
            0.0,
        )
        command = [str(time_tool), "-v", "-o", str(report), *benchmark]
        completed = run(command, environment={**os.environ, "LC_ALL": "C"})
        for line in report.read_text(encoding="utf-8").splitlines():
            if "Maximum resident set size (kbytes):" in line:
                return {
                    "scope": "whole_process",
                    "kib": int(line.rsplit(":", 1)[1].strip()),
                    "command": command,
                    "stdout": completed.stdout.rstrip("\n"),
                    "stderr": completed.stderr.rstrip("\n"),
                }
    raise RuntimeError("/usr/bin/time did not report peak RSS")


def collect_code_size(executable: Path) -> dict[str, object]:
    size_tool = shutil.which("size")
    if not size_tool:
        return {"file_bytes": executable.stat().st_size, "method": "filesystem"}
    command = [size_tool, "--format=berkeley", str(executable)]
    completed = run(command, environment={**os.environ, "LC_ALL": "C"})
    lines = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0][:4] != ["text", "data", "bss", "dec"]:
        raise RuntimeError("unexpected size tool output")
    return {
        "text_bytes": int(lines[1][0]),
        "data_bytes": int(lines[1][1]),
        "bss_bytes": int(lines[1][2]),
        "total_bytes": int(lines[1][3]),
        "command": command,
    }


def time_build(command_text: str) -> dict[str, object]:
    command = shlex.split(command_text)
    if not command:
        raise RuntimeError("--build-command must not be empty")
    started = time.perf_counter()
    completed = run(command)
    return {
        "command": command,
        "seconds": time.perf_counter() - started,
        "stdout": completed.stdout.rstrip("\n"),
        "stderr": completed.stderr.rstrip("\n"),
    }


def run_post_build(command_text: str) -> dict[str, object]:
    command = shlex.split(command_text)
    if not command:
        raise RuntimeError("--post-build-command must not be empty")
    completed = run(command)
    return {
        "command": command,
        "stdout": completed.stdout.rstrip("\n"),
        "stderr": completed.stderr.rstrip("\n"),
    }


def parse_affinity(value: str) -> list[int]:
    try:
        cpus = sorted({int(entry) for entry in value.split(",") if entry != ""})
    except ValueError as error:
        raise RuntimeError("CPU affinity must be a comma-separated integer list") from error
    if not cpus or cpus[0] < 0:
        raise RuntimeError("CPU affinity must contain non-negative CPU indices")
    return cpus


def validate_compile_commands(path: Path, compiler: Path) -> int:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("compile_commands.json is malformed") from error
    if not isinstance(document, list) or not document:
        raise RuntimeError("compile_commands.json must contain at least one command")

    compiler = compiler.resolve(strict=True)
    matches = 0
    for entry in document:
        if not isinstance(entry, dict):
            raise RuntimeError("compile_commands.json contains a non-object entry")
        arguments = entry.get("arguments")
        command = entry.get("command")
        if isinstance(arguments, list) and arguments and all(
            isinstance(value, str) for value in arguments
        ):
            executable = arguments[0]
        elif isinstance(command, str):
            parts = shlex.split(command)
            if not parts:
                raise RuntimeError("compile_commands.json contains an empty command")
            executable = parts[0]
        else:
            raise RuntimeError(
                "compile_commands.json entry has neither command nor arguments"
            )
        resolved = shutil.which(executable)
        if resolved is None and Path(executable).is_absolute():
            resolved = executable
        if resolved is not None:
            try:
                resolved_compiler = Path(resolved).resolve(strict=True)
            except OSError:
                continue
            if resolved_compiler == compiler:
                matches += 1
    if matches == 0:
        raise RuntimeError(
            "compile_commands.json does not reference the declared compiler executable"
        )
    return matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--allocation-executable", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--compiler-flags", required=True)
    parser.add_argument("--compiler-executable", type=Path)
    parser.add_argument("--compile-commands", type=Path)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", choices=("buffer", "mmap", "file"), default="buffer")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--minimum-time", default="0.5s")
    parser.add_argument("--warmup-seconds", type=float, default=0.1)
    parser.add_argument(
        "--evidence-level",
        choices=("exploratory", "controlled"),
        default="exploratory",
    )
    parser.add_argument("--cpu-affinity")
    parser.add_argument("--build-command")
    parser.add_argument("--post-build-command")
    parser.add_argument("--skip-pmu", action="store_true")
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--skip-size", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be positive")
    if args.warmup_seconds < 0 or not math.isfinite(args.warmup_seconds):
        parser.error("--warmup-seconds must be finite and non-negative")
    if args.evidence_level == "controlled" and args.runs < 20:
        parser.error("controlled evidence requires at least 20 repetitions")
    if args.evidence_level == "controlled" and args.warmup_seconds <= 0:
        parser.error("controlled evidence requires a positive warmup duration")
    if args.evidence_level == "controlled" and not args.cpu_affinity:
        parser.error("controlled evidence requires --cpu-affinity")
    if args.evidence_level == "controlled" and platform.system() != "Linux":
        parser.error("controlled fixed-machine metrics currently require Linux")
    if args.evidence_level == "controlled" and (
        args.skip_pmu or args.skip_rss or args.skip_size
    ):
        parser.error("controlled evidence requires PMU, RSS, and code-size collection")
    if args.evidence_level == "controlled" and (
        args.compiler_executable is None or args.compile_commands is None
    ):
        parser.error(
            "controlled evidence requires --compiler-executable and --compile-commands"
        )
    if args.evidence_level == "controlled" and not args.build_command:
        parser.error("controlled evidence requires --build-command for clean-build timing")
    if args.evidence_level == "controlled" and not args.post_build_command:
        parser.error(
            "controlled evidence requires --post-build-command to restore generated inputs"
        )
    if args.post_build_command and not args.build_command:
        parser.error("--post-build-command requires --build-command")

    if args.allocation_executable is None:
        args.allocation_executable = args.executable.with_name(
            f"{args.executable.stem}_allocations{args.executable.suffix}"
        )
    try:
        collector_paths = [
            artifacts.canonical_existing(path, "collector source")
            for path in collector_source_paths()
        ]
        collector_root = artifacts.canonical_existing(
            Path(__file__).resolve().parents[2], "collector source root"
        )
        collector_bundle = artifacts.bundle_metadata(
            collector_root, collector_paths, "collector-tool-bundle"
        )
        args.executable = artifacts.canonical_existing(args.executable, "benchmark executable")
        args.allocation_executable = artifacts.canonical_existing(
            args.allocation_executable, "allocation benchmark executable"
        )
        args.input = artifacts.canonical_existing(args.input, "input")
        if args.compiler_executable is not None:
            args.compiler_executable = artifacts.canonical_existing(
                args.compiler_executable, "compiler executable"
            )
        if args.compile_commands is not None:
            args.compile_commands = artifacts.canonical_existing(
                args.compile_commands, "compile commands"
            )
        args.output = artifacts.canonical_output(args.output)
        args.manifest = artifacts.canonical_output(
            args.manifest or args.output.with_suffix(args.output.suffix + ".sha256.json")
        )
        protected = [
            ("benchmark executable", args.executable),
            ("allocation benchmark executable", args.allocation_executable),
            ("input", args.input),
        ]
        protected.extend(
            (f"collector source {path.name}", path) for path in collector_paths
        )
        if args.compiler_executable is not None:
            protected.append(("compiler executable", args.compiler_executable))
        if args.compile_commands is not None:
            protected.append(("compile commands", args.compile_commands))
        artifacts.reject_output_alias(args.output, protected)
        artifacts.reject_output_alias(args.manifest, protected)
        if artifacts.paths_alias(args.output, args.manifest):
            raise RuntimeError("report and manifest paths must be distinct")
    except RuntimeError as error:
        parser.error(str(error))

    if args.evidence_level == "controlled":
        requested = parse_affinity(args.cpu_affinity)
        actual = sorted(os.sched_getaffinity(0))
        if requested != actual:
            parser.error(f"process affinity {actual} does not match requested affinity {requested}")

    identities = {
        "collector": collector_bundle,
        "executable": artifacts.metadata(args.executable, args.revision),
        "allocation_executable": artifacts.metadata(args.allocation_executable, args.revision),
        "dataset": artifacts.metadata(args.input),
    }
    compiler_identity = None
    if args.compiler_executable is not None:
        compiler_matches = validate_compile_commands(
            args.compile_commands, args.compiler_executable
        ) if args.compile_commands is not None else None
        version = run([str(args.compiler_executable), "--version"])
        identities["compiler_executable"] = artifacts.metadata(
            args.compiler_executable
        )
        compiler_identity = {
            "artifact": identities["compiler_executable"],
            "compile_command_matches": compiler_matches,
            "version_command": [str(args.compiler_executable), "--version"],
            "version_stdout": version.stdout.rstrip("\n"),
            "version_stderr": version.stderr.rstrip("\n"),
        }
    if args.compile_commands is not None:
        identities["compile_commands"] = artifacts.metadata(args.compile_commands)
    report: dict[str, object] = {
        "schema": METRICS_SCHEMA,
        "status": "running",
        "evidence_level": args.evidence_level,
        "decision_eligible": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": machine_metadata(),
        "compiler": args.compiler,
        "compiler_identity": compiler_identity,
        "compiler_flags": args.compiler_flags,
        "operation": args.operation,
        "source": args.source,
        "runs": args.runs,
        "artifacts": identities,
        "clean_build": None,
        "post_build": None,
    }
    protocol.validate_fixed_metrics_report(report)
    atomic.write_json(args.output, report)

    try:
        if args.build_command:
            report["clean_build"] = time_build(args.build_command)
            if args.post_build_command:
                report["post_build"] = run_post_build(args.post_build_command)
            # A clean build may legitimately replace the executables and a
            # generated corpus. Bind the report to the artifacts that are
            # actually measured and repeat alias checks after replacement.
            args.executable = artifacts.canonical_existing(
                args.executable, "benchmark executable after build"
            )
            args.allocation_executable = artifacts.canonical_existing(
                args.allocation_executable, "allocation benchmark executable after build"
            )
            args.input = artifacts.canonical_existing(
                args.input, "input after build"
            )
            rebuilt_protected = [
                (f"collector source {path.name}", path) for path in collector_paths
            ]
            rebuilt_protected.extend(
                [
                    ("benchmark executable", args.executable),
                    ("allocation benchmark executable", args.allocation_executable),
                    ("input", args.input),
                ]
            )
            if args.compiler_executable is not None:
                rebuilt_protected.append(
                    ("compiler executable", args.compiler_executable)
                )
            if args.compile_commands is not None:
                rebuilt_protected.append(("compile commands", args.compile_commands))
            artifacts.reject_output_alias(args.output, rebuilt_protected)
            artifacts.reject_output_alias(args.manifest, rebuilt_protected)
            identities["executable"] = artifacts.metadata(args.executable, args.revision)
            identities["allocation_executable"] = artifacts.metadata(
                args.allocation_executable, args.revision
            )
            identities["dataset"] = artifacts.metadata(args.input)
            report["artifacts"] = identities
        verification, verification_invocation = verify(
            args.executable, args.operation, args.input, args.source, args.revision
        )
        allocation, allocation_invocation = verify(
            args.allocation_executable, args.operation, args.input, args.source, args.revision
        )
        semantic_fields = ("operation", "source", "dataset", "checksum", "bytes", "rows", "cells")
        if any(verification[field] != allocation[field] for field in semantic_fields):
            raise RuntimeError("allocation executable changed benchmark semantics")
        report["verification"] = {
            "result": verification,
            "invocation": verification_invocation,
        }
        report["allocations"] = {
            "count": int(allocation["allocations"]),
            "bytes": int(allocation["allocated_bytes"]),
            "invocation": allocation_invocation,
        }
        report["timing"], report["timing_invocation"] = collect_timing(args)
        if not args.skip_pmu:
            if platform.system() == "Linux":
                report["pmu"], report["pmu_invocation"] = collect_timing(args, pmu=True)
            elif args.evidence_level == "controlled":
                raise RuntimeError("controlled evidence requires Linux PMU counters")
            else:
                report["pmu"] = None
        if not args.skip_rss:
            report["peak_rss"] = collect_peak_rss(args)
            if args.evidence_level == "controlled" and report["peak_rss"] is None:
                raise RuntimeError("controlled evidence requires peak RSS collection")
        if not args.skip_size:
            report["code_size"] = collect_code_size(args.executable)

        for label, identity in identities.items():
            artifacts.verify_unchanged(identity, label)
        report["status"] = "completed"
        report["decision_eligible"] = protocol.decision_eligible(
            args.evidence_level, report["status"]
        )
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        protocol.validate_fixed_metrics_report(report)
        atomic.write_json(args.output, report)
        manifest = {
            "schema": "csv2-artifact-manifest-v1",
            "report": artifacts.metadata(args.output),
            "inputs": identities,
        }
        atomic.write_json(args.manifest, manifest)
    except BaseException as error:
        report["status"] = "failed"
        report["decision_eligible"] = False
        report["error"] = str(error)
        atomic.write_json(args.output, report)
        raise


if __name__ == "__main__":
    main()
