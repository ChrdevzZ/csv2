#!/usr/bin/env python3
"""Verify that every retired doctest case maps to one stable runtime case."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPING = Path(__file__).with_name("legacy_case_map.tsv")
CASE_PATTERN = re.compile(
    r'CSV2_TEST_CASE\(\s*"([a-z0-9_.-]+)"\s*,\s*"([a-z0-9_.]+)"\s*\)'
)
EXPECTED_DOMAINS = {
    "reader.scan",
    "reader.iterate",
    "reader.extract",
    "reader.source",
    "reader.validate",
    "reader.convert",
    "reader.ranges",
    "reader.index",
    "writer.raw",
    "writer.escape",
    "writer.stream",
    "mio.mapping",
    "property.roundtrip",
}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    with MAPPING.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if len(rows) != 71:
        fail(f"expected 71 retired cases, found {len(rows)}")

    titles = [row["legacy_title"] for row in rows]
    mapped_ids = [row["stable_case_id"] for row in rows]
    for label, values in (("legacy title", titles), ("mapped stable ID", mapped_ids)):
        duplicates = sorted(value for value, count in Counter(values).items() if count != 1)
        if duplicates:
            fail(f"duplicate {label}: {', '.join(duplicates)}")

    discovered: dict[str, str] = {}
    for source in sorted((ROOT / "runtime").rglob("*.cpp")):
        for case_id, domain in CASE_PATTERN.findall(source.read_text(encoding="utf-8")):
            if case_id in discovered:
                fail(f"duplicate stable case ID: {case_id}")
            if not case_id.startswith(domain + "."):
                fail(f"case ID {case_id} is outside declared domain {domain}")
            discovered[case_id] = domain

    for row in rows:
        case_id = row["stable_case_id"]
        domain = row["domain"]
        if case_id not in discovered:
            fail(f"mapped stable case does not exist: {case_id}")
        if discovered[case_id] != domain:
            fail(f"domain mismatch for {case_id}: {domain} != {discovered[case_id]}")

    discovered_domains = set(discovered.values())
    missing_domains = sorted(EXPECTED_DOMAINS - discovered_domains)
    unexpected_domains = sorted(discovered_domains - EXPECTED_DOMAINS)
    if missing_domains or unexpected_domains:
        fail(
            "runtime domain mismatch: missing="
            + ",".join(missing_domains)
            + " unexpected="
            + ",".join(unexpected_domains)
        )
    print(f"verified {len(rows)} legacy mappings and {len(discovered)} stable cases")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"legacy parity check failed: {error}", file=sys.stderr)
        sys.exit(1)
