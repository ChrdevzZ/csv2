#!/usr/bin/env python3
"""Require verify and dry-run coverage for every registered current operation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


CONDITIONAL_OPERATIONS = {
    "source/mmap-open",
    "source/mmap-touch-resident",
    "source/parse-span",
    "conversion/integer-expected",
    "ranges/to-container",
}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {json.dumps(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def load_manifest(path: Path, source_root: Path) -> dict[str, tuple[str, Path]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "cases"}
        or document["schema"] != "csv2-benchmark-case-manifest-v1"
        or not isinstance(document["cases"], list)
        or not document["cases"]
    ):
        raise RuntimeError("benchmark case manifest is malformed")
    result: dict[str, tuple[str, Path]] = {}
    for index, value in enumerate(document["cases"]):
        if not isinstance(value, dict) or set(value) != {
            "operation",
            "source",
            "dataset",
        }:
            raise RuntimeError(f"benchmark case {index} is malformed")
        operation = value["operation"]
        source = value["source"]
        dataset = value["dataset"]
        if (
            not isinstance(operation, str)
            or not operation
            or operation in result
            or source not in {"file", "buffer", "mmap"}
            or not isinstance(dataset, str)
            or not dataset
            or "\\" in dataset
        ):
            raise RuntimeError(f"benchmark case {index} has invalid metadata")
        root = source_root.resolve(strict=True)
        target = (root / dataset).resolve(strict=True)
        try:
            target.relative_to(root)
        except ValueError as error:
            raise RuntimeError(f"benchmark case {index} escapes the source root") from error
        if not target.is_file():
            raise RuntimeError(f"benchmark case {index} dataset is not a file")
        result[operation] = (source, target)
    return result


def registered_operations(executable: Path) -> dict[str, set[str]]:
    completed = run([str(executable), "--csv2-list"])
    result: dict[str, set[str]] = {}
    for line in completed.stdout.splitlines():
        fields = line.split()
        if not fields or not fields[0] or len(fields) < 2 or not fields[1].startswith("source="):
            raise RuntimeError(f"malformed registry line: {line!r}")
        result.setdefault(fields[0], set()).add(fields[1].split("=", 1)[1])
    if not result:
        raise RuntimeError("current benchmark registry is empty")
    return result


def verify_wire(stdout: str, operation: str, source: str) -> None:
    fields: dict[str, str] = {}
    for field in stdout.split():
        if "=" not in field:
            raise RuntimeError(f"malformed verification field: {field!r}")
        key, value = field.split("=", 1)
        if not key or key in fields:
            raise RuntimeError(f"duplicate or empty verification field: {field!r}")
        fields[key] = value
    expected = {
        "protocol": "csv2-current-v3",
        "operation": operation,
        "source": source,
        "byte_basis": "input_corpus",
    }
    if any(fields.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"verification wire metadata mismatch for {operation}/{source}")
    if not fields.get("semantic_case_id", "").startswith("csv2."):
        raise RuntimeError(f"verification wire lacks semantic metadata for {operation}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    executable = args.executable.resolve(strict=True)
    cases = load_manifest(args.manifest.resolve(strict=True), args.source_root)
    operations = registered_operations(executable)
    missing = sorted(set(operations) - set(cases))
    if missing:
        raise RuntimeError(
            "registered operations lack stable cases: " + ", ".join(missing)
        )
    stale = sorted(set(cases) - set(operations) - CONDITIONAL_OPERATIONS)
    if stale:
        raise RuntimeError(
            "case manifest contains unknown operations: " + ", ".join(stale)
        )
    for operation in sorted(operations):
        source, dataset = cases[operation]
        if source not in operations[operation]:
            raise RuntimeError(
                f"stable case source is unsupported for {operation}: {source}"
            )
        common = [
            str(executable),
            "--csv2-input",
            str(dataset),
            "--csv2-source",
            source,
            "--csv2-operation",
            operation,
        ]
        verification = run([*common, "--csv2-verify"])
        verify_wire(verification.stdout, operation, source)
        run(
            [
                *common,
                "--benchmark_min_time=0.001s",
                "--benchmark_repetitions=1",
            ]
        )


if __name__ == "__main__":
    main()
