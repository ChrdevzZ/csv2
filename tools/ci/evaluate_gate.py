#!/usr/bin/env python3
"""Fail closed when a planned CI owner did not complete successfully."""

from __future__ import annotations

import argparse
import sys


VALID_RESULTS = {"success", "failure", "cancelled", "skipped"}


def parse_job(parser: argparse.ArgumentParser, value: str) -> tuple[str, bool, str]:
    fields = value.split(":")
    if len(fields) != 3 or not fields[0]:
        parser.error(f"invalid job specification: {value!r}")
    name, required_value, result = fields
    if required_value not in {"true", "false"}:
        parser.error(f"invalid required flag for {name}: {required_value!r}")
    if result not in VALID_RESULTS:
        parser.error(f"invalid result for {name}: {result!r}")
    return name, required_value == "true", result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", action="append", required=True)
    args = parser.parse_args()

    failed = False
    names: set[str] = set()
    for value in args.job:
        name, required, result = parse_job(parser, value)
        if name in names:
            parser.error(f"duplicate job: {name}")
        names.add(name)
        if required and result != "success":
            print(f"required job {name} ended as {result}", file=sys.stderr)
            failed = True
        elif not required and result not in {"success", "skipped"}:
            print(
                f"optional job {name} unexpectedly ended as {result}",
                file=sys.stderr,
            )
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
