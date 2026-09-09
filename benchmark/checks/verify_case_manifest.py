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
) -> tuple[dict[str, tuple[str, Path, dict[str, str]]], set[str]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "cases"}
        or document["schema"] != "csv2-benchmark-case-manifest-v3"
        or not isinstance(document["cases"], list)
        or not document["cases"]
    ):
        raise RuntimeError("benchmark case manifest is malformed")
    result: dict[str, tuple[str, Path, dict[str, str]]] = {}
    conditional: set[str] = set()
    for index, value in enumerate(document["cases"]):
        required_fields = {
            "operation", "source", "dataset", "semantic_case_id", "scope", "byte_basis"
        }
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
        contract = {key: value[key] for key in ("semantic_case_id", "scope", "byte_basis")}
        if (
            not isinstance(operation, str)
            or not operation
            or operation in result
            or source not in {"file", "buffer", "mmap"}
            or not isinstance(dataset, str)
            or not dataset
            or "\\" in dataset
            or not isinstance(is_conditional, bool)
            or any(not isinstance(item, str) or not item for item in contract.values())
            or not contract["semantic_case_id"].startswith("csv2.")
            or contract["byte_basis"] != "input_corpus"
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
        result[operation] = (source, target, contract)
        if is_conditional:
            conditional.add(operation)
    return result, conditional


def wire_fields(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field in stdout.split():
        if "=" not in field:
            raise RuntimeError(f"malformed wire field: {field!r}")
        key, value = field.split("=", 1)
        if not key or not value or key in fields:
            raise RuntimeError(f"duplicate or empty wire field: {field!r}")
        fields[key] = value
    return fields


def registered_operations(executable: Path) -> dict[str, dict[str, dict[str, str]]]:
    completed = run([str(executable), "--csv2-list"])
    result: dict[str, dict[str, dict[str, str]]] = {}
    for line in completed.stdout.splitlines():
        operation, separator, metadata = line.partition(" ")
        if not operation or not separator:
            raise RuntimeError(f"malformed registry line: {line!r}")
        fields = wire_fields(metadata)
        if set(fields) != {
            "source", "scope", "semantic_case_id", "byte_basis", "zero_allocations"
        }:
            raise RuntimeError(f"malformed registry metadata: {line!r}")
        source = fields.pop("source")
        if source not in {"file", "buffer", "mmap"} or fields.pop(
            "zero_allocations"
        ) not in {"true", "false"}:
            raise RuntimeError(f"invalid registry metadata: {line!r}")
        sources = result.setdefault(operation, {})
        if source in sources:
            raise RuntimeError(f"duplicate registry operation/source: {operation}/{source}")
        sources[source] = fields
    if not result:
        raise RuntimeError("current benchmark registry is empty")
    return result


def verify_wire(stdout: str, operation: str, source: str, contract: dict[str, str]) -> None:
    fields = wire_fields(stdout)
    expected = {
        "protocol": "csv2-current-v4",
        "operation": operation,
        "source": source,
        **contract,
    }
    if any(fields.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"verification wire metadata mismatch for {operation}/{source}")


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
        source, _, contract = cases[operation]
        if source not in operations[operation]:
            raise RuntimeError(
                f"stable case source is unsupported for {operation}: {source}"
            )
        if any(metadata != contract for metadata in operations[operation].values()):
            raise RuntimeError(f"registry contract differs from stable case for {operation}")
    if args.registry_only:
        return
    for operation in sorted(operations):
        source, dataset, contract = cases[operation]
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
        verify_wire(verification.stdout, operation, source, contract)
        run([*common, "--benchmark_dry_run"])


if __name__ == "__main__":
    main()
