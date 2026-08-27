#!/usr/bin/env python3
"""Require verify and dry-run coverage for every registered current operation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {json.dumps(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def load_manifest(
    path: Path, source_root: Path
) -> tuple[dict[str, tuple[str, Path]], set[str]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "cases"}
        or document["schema"] != "csv2-benchmark-case-manifest-v2"
        or not isinstance(document["cases"], list)
        or not document["cases"]
    ):
        raise RuntimeError("benchmark case manifest is malformed")
    result: dict[str, tuple[str, Path]] = {}
    conditional: set[str] = set()
    for index, value in enumerate(document["cases"]):
        required_fields = {"operation", "source", "dataset"}
        allowed_fields = required_fields | {"conditional"}
        if (
            not isinstance(value, dict)
            or not required_fields.issubset(value)
            or set(value) - allowed_fields
        ):
            raise RuntimeError(f"benchmark case {index} is malformed")
        operation = value["operation"]
        source = value["source"]
        dataset = value["dataset"]
        is_conditional = value.get("conditional", False)
        if (
            not isinstance(operation, str)
            or not operation
            or operation in result
            or source not in {"file", "buffer", "mmap"}
            or not isinstance(dataset, str)
            or not dataset
            or "\\" in dataset
            or not isinstance(is_conditional, bool)
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
        if is_conditional:
            conditional.add(operation)
    return result, conditional


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
        "protocol": "csv2-current-v4",
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
    parser.add_argument(
        "--registry-only",
        action="store_true",
        help="Validate registry and manifest coverage without executing cases",
    )
    args = parser.parse_args()

    executable = args.executable.resolve(strict=True)
    cases, conditional = load_manifest(
        args.manifest.resolve(strict=True), args.source_root
    )
    operations = registered_operations(executable)
    missing = sorted(set(operations) - set(cases))
    if missing:
        raise RuntimeError(
            "registered operations lack stable cases: " + ", ".join(missing)
        )
    stale = sorted(set(cases) - set(operations) - conditional)
    if stale:
        raise RuntimeError(
            "case manifest contains unknown operations: " + ", ".join(stale)
        )
    for operation in sorted(operations):
        source, _ = cases[operation]
        if source not in operations[operation]:
            raise RuntimeError(
                f"stable case source is unsupported for {operation}: {source}"
            )
    if args.registry_only:
        return
    for operation in sorted(operations):
        source, dataset = cases[operation]
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
        run([*common, "--benchmark_dry_run"])


if __name__ == "__main__":
    main()
