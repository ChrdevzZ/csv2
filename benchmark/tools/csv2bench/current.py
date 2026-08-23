"""Launch each current-tree benchmark case in a separate process."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Callable, Sequence


Run = Callable[..., subprocess.CompletedProcess[str]]


def parse_case(value: str) -> tuple[str, str, str]:
    parts = value.split("|")
    if len(parts) != 3 or not all(parts):
        raise argparse.ArgumentTypeError(
            "case must be OPERATION|SOURCE|DATASET"
        )
    operation, source, dataset = parts
    if source == "all":
        raise argparse.ArgumentTypeError("case source must be concrete")
    return operation, source, dataset


def run_cases(
    executable: Path,
    dataset_root: Path,
    cases: Sequence[tuple[str, str, str]],
    benchmark_arguments: Sequence[str],
    *,
    verify: bool,
    run_fn: Run = subprocess.run,
) -> list[subprocess.CompletedProcess[str]]:
    if not cases:
        raise ValueError("at least one current benchmark case is required")
    completed: list[subprocess.CompletedProcess[str]] = []
    for operation, source, dataset in cases:
        command = [
            str(executable),
            "--csv2-input",
            str(dataset_root / dataset),
            "--csv2-operation",
            operation,
            "--csv2-source",
            source,
        ]
        if verify:
            command.append("--csv2-verify")
        else:
            command.extend(benchmark_arguments)
        result = run_fn(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"current benchmark case failed: {operation}/{source}/{dataset}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        completed.append(result)
    return completed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--case", action="append", type=parse_case, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("benchmark_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    benchmark_arguments = args.benchmark_arguments
    if benchmark_arguments[:1] == ["--"]:
        benchmark_arguments = benchmark_arguments[1:]
    results = run_cases(
        args.executable,
        args.datasets,
        args.case,
        benchmark_arguments,
        verify=args.verify,
    )
    for result in results:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    return 0
