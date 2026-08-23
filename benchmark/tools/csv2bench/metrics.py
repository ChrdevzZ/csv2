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

from . import ARTIFACT_MANIFEST_SCHEMA, METRICS_SCHEMA
from . import artifacts, atomic, builds, machine, protocol, statistics


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
        package_root / "builds.py",
        package_root / "derivation.py",
        package_root / "metrics.py",
        package_root / "machine.py",
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
        if record.get("error_occurred") or record.get("skipped"):
            message = str(record.get("error_message", "")).strip()
            suffix = f": {message}" if message else ""
            raise RuntimeError(f"benchmark sample failed or skipped{suffix}")
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
            parts = shlex.split(command, posix=os.name != "nt")
            if not parts:
                raise RuntimeError("compile_commands.json contains an empty command")
            executable = parts[0].strip('"')
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
    parser.add_argument("--external-artifacts", action="store_true")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--candidate-ref")
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--corpus-scale", type=int, default=1)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--allocation-executable", type=Path)
    parser.add_argument("--revision")
    parser.add_argument("--compiler")
    parser.add_argument("--compiler-flags", default="")
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
    parser.add_argument("--machine-profile", type=Path)
    parser.add_argument("--build-command")
    parser.add_argument("--post-build-command")
    parser.add_argument("--skip-pmu", action="store_true")
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--skip-size", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    if args.external_artifacts:
        if args.evidence_level != "exploratory":
            parser.error("--external-artifacts is restricted to exploratory evidence")
        if args.executable is None or args.revision is None:
            parser.error("--external-artifacts requires --executable and --revision")
        if args.candidate_ref or args.build_root:
            parser.error("external artifacts cannot use owned-build ref options")
    else:
        if args.executable is not None or args.allocation_executable is not None:
            parser.error("explicit executable paths require --external-artifacts")
        if args.revision is not None:
            parser.error("explicit revision requires --external-artifacts")
        if not args.candidate_ref or args.compiler_executable is None:
            parser.error("owned metrics require --candidate-ref and --compiler-executable")
        if args.build_root is None:
            args.build_root = args.output.with_suffix(args.output.suffix + ".build")
        if args.corpus_scale < 1:
            parser.error("--corpus-scale must be positive")
        if args.build_command or args.post_build_command:
            parser.error("owned metrics build internally; external build commands are forbidden")

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
    if args.evidence_level == "controlled" and args.machine_profile is None:
        parser.error("controlled evidence requires --machine-profile")
    if args.evidence_level == "exploratory" and args.machine_profile is not None:
        parser.error("exploratory evidence does not accept --machine-profile")
    if args.evidence_level == "controlled" and platform.system() != "Linux":
        parser.error("controlled fixed-machine metrics currently require Linux")
    if args.evidence_level == "controlled" and (
        args.skip_pmu or args.skip_rss or args.skip_size
    ):
        parser.error("controlled evidence requires PMU, RSS, and code-size collection")
    if args.evidence_level == "controlled" and args.external_artifacts:
        parser.error("controlled evidence requires an owned current-tree build")
    if args.post_build_command and not args.build_command:
        parser.error("--post-build-command requires --build-command")

    owned_build: dict[str, object] | None = None
    artifact_mode = "external" if args.external_artifacts else "owned"
    if not args.external_artifacts:
        try:
            compiler_flags = shlex.split(args.compiler_flags, posix=os.name != "nt")
            if not compiler_flags:
                raise RuntimeError("owned metrics require non-empty --compiler-flags")
            owned_build = builds.build_current_tree(
                repository=args.repository,
                reference=args.candidate_ref,
                compiler=args.compiler_executable,
                compiler_flags=compiler_flags,
                workspace=artifacts.canonical_output(args.build_root),
                corpus_scale=args.corpus_scale,
            )
            args.compiler_flags = " ".join(compiler_flags)
            args.revision = str(owned_build["revision"])
            args.executable = Path(str(owned_build["targets"]["csv2_benchmark"]["path"]))
            args.allocation_executable = Path(
                str(owned_build["targets"]["csv2_benchmark_allocations"]["path"])
            )
            args.compile_commands = Path(str(owned_build["compile_commands"]["path"]))
            if not args.input.is_absolute():
                args.input = (
                    Path(str(owned_build["build_root"]))
                    / "benchmark-corpus"
                    / "fixtures"
                    / args.input
                )
            version = owned_build["compiler"]["version"]
            identity = (str(version["stdout"]) + "\n" + str(version["stderr"])).strip()
            args.compiler = args.compiler or identity.splitlines()[0]
        except (OSError, RuntimeError) as error:
            parser.error(str(error))
    elif args.compiler is None:
        args.compiler = "external-artifact compiler (unverified)"

    if args.allocation_executable is None:
        args.allocation_executable = args.executable.with_name(
            f"{args.executable.stem}_allocations{args.executable.suffix}"
        )
    machine_profile: dict[str, object] | None = None
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
        if args.machine_profile is not None:
            machine_profile = machine.load(args.machine_profile)
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
        if machine_profile is not None:
            protected.append(
                ("machine profile", Path(str(machine_profile["artifact"]["path"])))
            )
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
        if machine_profile["observation"]["process_affinity"] != requested:
            parser.error("machine-profile affinity differs from --cpu-affinity")

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
        if owned_build is not None:
            recorded_version = owned_build["compiler"]["version"]
            version_command = list(recorded_version["command"])
            version_stdout = str(recorded_version["stdout"])
            version_stderr = str(recorded_version["stderr"])
        else:
            version = run([str(args.compiler_executable), "--version"])
            version_command = [str(args.compiler_executable), "--version"]
            version_stdout = version.stdout.rstrip("\n")
            version_stderr = version.stderr.rstrip("\n")
        identities["compiler_executable"] = artifacts.metadata(
            args.compiler_executable
        )
        compiler_identity = {
            "artifact": identities["compiler_executable"],
            "compile_command_matches": compiler_matches,
            "version_command": version_command,
            "version_stdout": version_stdout,
            "version_stderr": version_stderr,
        }
    if args.compile_commands is not None:
        identities["compile_commands"] = artifacts.metadata(args.compile_commands)
    report: dict[str, object] = {
        "schema": METRICS_SCHEMA,
        "artifact_mode": artifact_mode,
        "build": owned_build,
        "status": "running",
        "evidence_level": args.evidence_level,
        "controlled_complete": False,
        "decision_eligible": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": machine_metadata(),
        "machine_profile": machine_profile,
        "compiler": args.compiler,
        "compiler_identity": compiler_identity,
        "compiler_flags": args.compiler_flags,
        "operation": args.operation,
        "source": args.source,
        "runs": args.runs,
        "artifacts": identities,
        "clean_build": (
            {
                "command": owned_build["build_argv"],
                "seconds": owned_build["build_log"]["seconds"],
                "stdout": owned_build["build_log"]["stdout"],
                "stderr": owned_build["build_log"]["stderr"],
            }
            if owned_build is not None
            else None
        ),
        "post_build": (
            {
                "command": owned_build["build_argv"],
                "stdout": owned_build["build_log"]["stdout"],
                "stderr": owned_build["build_log"]["stderr"],
            }
            if owned_build is not None
            else None
        ),
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
        semantic_fields = (
            "operation", "source", "dataset", "semantic_case_id", "scope",
            "byte_basis", "checksum", "bytes", "rows", "cells",
        )
        if any(verification[field] != allocation[field] for field in semantic_fields):
            raise RuntimeError("allocation executable changed benchmark semantics")
        report["verification"] = {
            "result": verification,
            "invocation": verification_invocation,
        }
        report["comparison_binding"] = {
            field: verification[field]
            for field in (
                "dataset", "semantic_case_id", "scope", "source", "byte_basis"
            )
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
        if machine_profile is not None:
            artifacts.verify_unchanged(machine_profile["artifact"], "machine profile")
        if owned_build is not None:
            builds.verify_current_build_manifest(owned_build)
        report["status"] = "completed"
        report["controlled_complete"] = protocol.controlled_complete(
            args.evidence_level,
            report["status"],
            owned_build=artifact_mode == "owned",
        )
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        protocol.validate_fixed_metrics_report(report)
        atomic.write_json(args.output, report)
        manifest = {
            "schema": ARTIFACT_MANIFEST_SCHEMA,
            "kind": "fixed-metrics",
            "report": artifacts.metadata(args.output),
            "inputs": {
                "artifacts": identities,
                "build": owned_build["identity_digest"] if owned_build is not None else None,
                "machine_profile": (
                    machine_profile["artifact"] if machine_profile is not None else None
                ),
            },
        }
        protocol.validate_artifact_manifest(manifest)
        atomic.write_json(args.manifest, manifest)
    except BaseException as error:
        report["status"] = "failed"
        report["controlled_complete"] = False
        report["decision_eligible"] = False
        report["error"] = str(error)
        atomic.write_json(args.output, report)
        raise


if __name__ == "__main__":
    main()
