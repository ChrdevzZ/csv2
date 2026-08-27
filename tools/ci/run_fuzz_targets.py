#!/usr/bin/env python3
"""Run both CSV2 libFuzzer targets and preserve isolated reproducers."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path


Run = Callable[..., subprocess.CompletedProcess[str]]


def run_target(
    *,
    name: str,
    executable: Path,
    corpus: Path,
    runs: int,
    artifact_root: Path,
    run_fn: Run,
) -> int:
    artifact_directory = artifact_root / name
    artifact_directory.mkdir(parents=True, exist_ok=True)
    command = [
        str(executable),
        f"-artifact_prefix={artifact_directory.as_posix()}/",
        f"-runs={runs}",
        str(corpus),
    ]
    print(f"running {name}: {shlex.join(command)}", flush=True)
    try:
        completed = run_fn(command, check=False)
    except OSError as error:
        print(f"{name} could not be launched: {error}", file=sys.stderr, flush=True)
        (artifact_directory / "status.txt").write_text(
            f"launch_error={error}\n", encoding="utf-8"
        )
        return 127
    (artifact_directory / "status.txt").write_text(
        f"exit_code={completed.returncode}\n", encoding="utf-8"
    )
    if completed.returncode:
        print(
            f"{name} failed with exit code {completed.returncode}",
            file=sys.stderr,
            flush=True,
        )
    return completed.returncode


def run_pair(
    *,
    reader: Path,
    writer: Path,
    reader_corpus: Path,
    writer_corpus: Path,
    runs: int,
    artifact_root: Path,
    run_fn: Run = subprocess.run,
) -> int:
    if runs < 1:
        raise ValueError("runs must be positive")
    statuses = (
        run_target(
            name="reader",
            executable=reader,
            corpus=reader_corpus,
            runs=runs,
            artifact_root=artifact_root,
            run_fn=run_fn,
        ),
        run_target(
            name="writer",
            executable=writer,
            corpus=writer_corpus,
            runs=runs,
            artifact_root=artifact_root,
            run_fn=run_fn,
        ),
    )
    return 1 if any(status != 0 for status in statuses) else 0


def existing_path(value: str) -> Path:
    try:
        return Path(value).resolve(strict=True)
    except OSError as error:
        raise argparse.ArgumentTypeError(f"path does not exist: {value}") from error


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reader", type=existing_path, required=True)
    parser.add_argument("--writer", type=existing_path, required=True)
    parser.add_argument("--reader-corpus", type=existing_path, required=True)
    parser.add_argument("--writer-corpus", type=existing_path, required=True)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args(arguments)
    if args.runs < 1:
        parser.error("--runs must be positive")
    for name in ("reader_corpus", "writer_corpus"):
        if not getattr(args, name).is_dir():
            parser.error(f"--{name.replace('_', '-')} must be a directory")
    return args


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    return run_pair(
        reader=args.reader,
        writer=args.writer,
        reader_corpus=args.reader_corpus,
        writer_corpus=args.writer_corpus,
        runs=args.runs,
        artifact_root=args.artifact_root.resolve(),
    )


if __name__ == "__main__":
    sys.exit(main())
