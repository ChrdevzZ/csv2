#!/usr/bin/env python3
"""Verify every committed current-tree checksum against the exact wire fields."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


UINT64_MAX = (1 << 64) - 1


def parse_wire(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("benchmark must print exactly one non-empty result line")
    fields: dict[str, str] = {}
    for token in lines[0].split():
        if token.count("=") != 1:
            raise RuntimeError(f"malformed benchmark field: {token!r}")
        key, value = token.split("=", 1)
        if not key or not value or key in fields:
            raise RuntimeError(f"malformed or duplicate benchmark field: {token!r}")
        fields[key] = value
    return fields


def load_manifest(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("checksum manifest is malformed") from error
    if not isinstance(document, dict) or document.get("protocol") != "csv2-current-v3":
        raise RuntimeError("checksum manifest has an unsupported protocol")
    checks = document.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError("checksum manifest has no checks")
    return document


def validate_checksum(value: object) -> str:
    if not isinstance(value, str) or not value or not value.isascii() or not value.isdecimal():
        raise RuntimeError("manifest checksum must be canonical unsigned decimal")
    parsed = int(value)
    if parsed > UINT64_MAX or str(parsed) != value:
        raise RuntimeError("manifest checksum is outside uint64 or is not canonical")
    return value


def resolve_dataset(source_root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeError("manifest dataset path is invalid")
    root = source_root.resolve(strict=True)
    dataset = (root / value).resolve(strict=True)
    try:
        dataset.relative_to(root)
    except ValueError as error:
        raise RuntimeError("manifest dataset escapes the source tree") from error
    if not dataset.is_file():
        raise RuntimeError("manifest dataset is not a regular file")
    return dataset


def verify(executable: Path, source_root: Path, manifest: Path) -> None:
    executable = executable.resolve(strict=True)
    document = load_manifest(manifest.resolve(strict=True))
    protocol = str(document["protocol"])
    seen: set[tuple[str, str, str]] = set()
    for raw_check in document["checks"]:
        if not isinstance(raw_check, dict):
            raise RuntimeError("checksum manifest contains a non-object check")
        operation = raw_check.get("operation")
        source = raw_check.get("source")
        if not isinstance(operation, str) or not operation:
            raise RuntimeError("checksum check has no operation")
        if source not in {"buffer", "mmap", "file"}:
            raise RuntimeError("checksum check has an invalid source")
        dataset = resolve_dataset(source_root, raw_check.get("dataset"))
        checksum = validate_checksum(raw_check.get("checksum"))
        key = (operation, str(source), str(dataset))
        if key in seen:
            raise RuntimeError("checksum manifest contains a duplicate check")
        seen.add(key)

        command = [
            str(executable),
            "--csv2-input",
            str(dataset),
            "--csv2-source",
            str(source),
            "--csv2-operation",
            operation,
            "--csv2-verify",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if completed.returncode != 0:
            raise RuntimeError(
                f"benchmark check failed for {operation}: {completed.stderr.strip()}"
            )
        fields = parse_wire(completed.stdout)
        expected = {
            "protocol": protocol,
            "operation": operation,
            "source": str(source),
            "dataset": dataset.name,
            "checksum": checksum,
        }
        for field, value in expected.items():
            if fields.get(field) != value:
                raise RuntimeError(
                    f"benchmark {field} mismatch for {operation}: "
                    f"expected {value}, got {fields.get(field)}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        verify(arguments.executable, arguments.source_root, arguments.manifest)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
