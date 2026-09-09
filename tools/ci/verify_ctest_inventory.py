#!/usr/bin/env python3
"""Verify that a CTest label and its canonical target manifest agree."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any


def labels_for(test: dict[str, Any]) -> set[str]:
    properties = test.get("properties")
    if not isinstance(properties, list):
        raise RuntimeError(f"CTest entry has invalid properties: {test!r}")
    label_values = [
        property_value.get("value")
        for property_value in properties
        if isinstance(property_value, dict) and property_value.get("name") == "LABELS"
    ]
    if len(label_values) != 1:
        raise RuntimeError(f"CTest entry must have exactly one LABELS property: {test!r}")
    value = label_values[0]
    if isinstance(value, str):
        return {label for label in value.split(";") if label}
    if isinstance(value, list) and all(isinstance(label, str) for label in value):
        return set(value)
    raise RuntimeError(f"CTest entry has invalid LABELS value: {test!r}")


def command_target(test: dict[str, Any]) -> str:
    command = test.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not isinstance(command[0], str)
    ):
        raise RuntimeError(f"CTest entry has invalid command: {test!r}")
    name = PurePosixPath(command[0].replace("\\", "/")).name
    if name.lower().endswith(".exe"):
        name = name[:-4]
    if not name:
        raise RuntimeError(f"CTest entry has empty executable name: {test!r}")
    return name


def verify_inventory(
    payload: object,
    *,
    label: str,
    expected_targets: set[str],
    expected_tests: dict[str, str],
) -> list[str]:
    if not expected_targets:
        raise RuntimeError("expected target manifest is empty")
    if not expected_tests:
        raise RuntimeError("expected CTest manifest is empty")
    expected_test_targets = set(expected_tests.values())
    missing_manifest_targets = sorted(expected_targets - expected_test_targets)
    unexpected_manifest_targets = sorted(expected_test_targets - expected_targets)
    if missing_manifest_targets:
        raise RuntimeError(
            "expected CTest manifest has no test for target(s): "
            f"{', '.join(missing_manifest_targets)}"
        )
    if unexpected_manifest_targets:
        raise RuntimeError(
            "expected CTest manifest references unknown target(s): "
            f"{', '.join(unexpected_manifest_targets)}"
        )
    if not isinstance(payload, dict) or not isinstance(payload.get("tests"), list):
        raise RuntimeError("CTest JSON does not contain a tests list")

    names: list[str] = []
    actual_tests: dict[str, str] = {}
    for raw_test in payload["tests"]:
        if not isinstance(raw_test, dict):
            raise RuntimeError(f"CTest entry is not an object: {raw_test!r}")
        name = raw_test.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"CTest entry has invalid name: {raw_test!r}")
        if name in names:
            raise RuntimeError(f"duplicate CTest name in labeled inventory: {name}")
        if label not in labels_for(raw_test):
            raise RuntimeError(f"CTest {name} does not carry label {label}")
        names.append(name)
        actual_tests[name] = command_target(raw_test)

    mismatches = sorted(
        name
        for name in expected_tests.keys() & actual_tests.keys()
        if expected_tests[name] != actual_tests[name]
    )
    if mismatches:
        details = ", ".join(
            f"{name} (expected {expected_tests[name]}, found {actual_tests[name]})"
            for name in mismatches
        )
        raise RuntimeError(f"labeled CTest target mismatch: {details}")
    missing = sorted(expected_tests.keys() - actual_tests.keys())
    unexpected = sorted(actual_tests.keys() - expected_tests.keys())
    if missing:
        raise RuntimeError(f"missing labeled CTest names: {', '.join(missing)}")
    if unexpected:
        raise RuntimeError(f"unexpected labeled CTest names: {', '.join(unexpected)}")
    return names


def read_target_manifest(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    targets = [line.strip() for line in lines if line.strip()]
    if len(targets) != len(set(targets)):
        raise RuntimeError(f"duplicate target in manifest: {path}")
    if any("/" in target or "\\" in target for target in targets):
        raise RuntimeError(f"manifest contains a path instead of a target name: {path}")
    return set(targets)


def read_test_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2 or not all(fields):
            raise RuntimeError(
                f"invalid expected CTest manifest line {path}:{line_number}"
            )
        name, target = fields
        if name in result:
            raise RuntimeError(f"duplicate CTest name in manifest: {name}")
        if "/" in target or "\\" in target:
            raise RuntimeError(f"CTest manifest contains a target path: {target}")
        result[name] = target
    return result


def load_ctest_inventory(*, build_dir: Path, label: str, ctest: str) -> object:
    completed = subprocess.run(
        [
            ctest,
            "--test-dir",
            str(build_dir),
            "-L",
            label,
            "--show-only=json-v1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"CTest inventory failed ({completed.returncode}):\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("CTest inventory did not produce valid JSON") from error


def parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--expected-targets", type=Path, required=True)
    parser.add_argument("--expected-tests", type=Path, required=True)
    parser.add_argument("--ctest", default="ctest")
    return parser.parse_args(arguments)


def main(arguments: Iterable[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        expected_targets = read_target_manifest(args.expected_targets)
        expected_tests = read_test_manifest(args.expected_tests)
        payload = load_ctest_inventory(
            build_dir=args.build_dir,
            label=args.label,
            ctest=args.ctest,
        )
        tests = verify_inventory(
            payload,
            label=args.label,
            expected_targets=expected_targets,
            expected_tests=expected_tests,
        )
    except (OSError, RuntimeError) as error:
        print(f"CTest inventory verification failed: {error}", file=sys.stderr)
        return 1
    print(
        f"verified {len(tests)} {args.label} tests across "
        f"{len(expected_targets)} canonical targets"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
