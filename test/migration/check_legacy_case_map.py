#!/usr/bin/env python3
"""Verify the retired doctest inventory and its stable runtime mappings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
MAPPING = Path(__file__).with_name("legacy_case_map.tsv")
INVENTORY = Path(__file__).with_name("legacy_doctest_inventory.json")

INVENTORY_SCHEMA = "csv2-legacy-doctest-inventory-v1"
EXPECTED_BASE = {
    "commit": "635e59a341bba40689d2b3e74ef7508b921f1133",
    "tree": "dc3a174e99ee63190bb41e17836aa816a1325175",
    "path": "test/main.cpp",
    "blob": "9ec2485d8f5c8ed600f86e8027ca872953e61967",
}
EXPECTED_TITLE_COUNT = 71
EXPECTED_TITLE_SET_SHA256 = (
    "80f84f3b0a236b22d6491ee9383605a9f757bdc8c0f1ccef54bb0241ea188071"
)
EXPECTED_INVENTORY_SHA256 = (
    "a0b2712b084b362db730b5833c194b1685e3dceeef671a8ead58448964238195"
)
MAPPING_COLUMNS = ["legacy_title", "stable_case_id", "domain"]

CASE_PATTERN = re.compile(
    r'CSV2_TEST_CASE\(\s*"([a-z0-9_.-]+)"\s*,\s*"([a-z0-9_.]+)"\s*\)'
)
LEGACY_CASE_PATTERN = re.compile(r'TEST_CASE\(\s*"([^"\r\n]+)"')
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


def canonical_document_digest(document: object) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_title_digest(titles: Iterable[str]) -> str:
    encoded = ("\n".join(sorted(titles)) + "\n").encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"legacy inventory contains duplicate JSON key: {key}")
        result[key] = value
    return result


def require_fields(document: dict[str, object], expected: set[str], label: str) -> None:
    missing = sorted(expected - document.keys())
    unexpected = sorted(document.keys() - expected)
    if missing or unexpected:
        fail(
            f"{label} fields mismatch: missing={','.join(missing)} "
            f"unexpected={','.join(unexpected)}"
        )


def load_inventory(path: Path = INVENTORY) -> frozenset[str]:
    document = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )
    if not isinstance(document, dict):
        fail("legacy inventory must be a JSON object")
    require_fields(
        document,
        {"schema", "base", "title_count", "title_set_sha256", "titles"},
        "legacy inventory",
    )
    if document["schema"] != INVENTORY_SCHEMA:
        fail("legacy inventory schema is unsupported")

    base = document["base"]
    if not isinstance(base, dict):
        fail("legacy inventory base metadata must be an object")
    require_fields(base, set(EXPECTED_BASE), "legacy inventory base metadata")
    if base != EXPECTED_BASE:
        fail("legacy inventory base metadata differs from the pinned Git objects")

    count = document["title_count"]
    if isinstance(count, bool) or count != EXPECTED_TITLE_COUNT:
        fail(f"legacy inventory title_count must be {EXPECTED_TITLE_COUNT}")
    if document["title_set_sha256"] != EXPECTED_TITLE_SET_SHA256:
        fail("legacy inventory title-set digest differs from the pinned digest")

    titles = document["titles"]
    if not isinstance(titles, list) or not all(
        isinstance(title, str) and title for title in titles
    ):
        fail("legacy inventory titles must be non-empty strings")
    duplicates = sorted(
        title for title, occurrences in Counter(titles).items() if occurrences != 1
    )
    if duplicates:
        fail("duplicate legacy inventory title: " + ", ".join(duplicates))
    if len(titles) != EXPECTED_TITLE_COUNT:
        fail(
            f"expected {EXPECTED_TITLE_COUNT} inventory titles, found {len(titles)}"
        )
    if canonical_title_digest(titles) != EXPECTED_TITLE_SET_SHA256:
        fail("legacy inventory titles differ from the pinned title-set digest")
    if canonical_document_digest(document) != EXPECTED_INVENTORY_SHA256:
        fail("legacy inventory manifest differs from the pinned manifest digest")
    return frozenset(titles)


def git_object_type(repository: Path, object_id: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "cat-file", "-t", object_id],
            cwd=repository,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def run_git(repository: Path, arguments: list[str], label: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        fail(f"cannot execute git while verifying {label}: {error}")
    if completed.returncode != 0:
        fail(f"git failed while verifying {label}: {completed.stderr.strip()}")
    return completed.stdout


def verify_git_provenance(
    inventory_titles: frozenset[str], repository: Path = REPOSITORY
) -> bool:
    blob_type = git_object_type(repository, EXPECTED_BASE["blob"])
    if blob_type is None:
        return False
    if blob_type != "blob":
        fail("pinned legacy source object is not a Git blob")

    source = run_git(
        repository,
        ["cat-file", "blob", EXPECTED_BASE["blob"]],
        "legacy source blob",
    )
    blob_titles = LEGACY_CASE_PATTERN.findall(source)
    if len(blob_titles) != EXPECTED_TITLE_COUNT:
        fail(
            "pinned legacy source blob contains "
            f"{len(blob_titles)} TEST_CASE titles instead of {EXPECTED_TITLE_COUNT}"
        )
    if len(set(blob_titles)) != EXPECTED_TITLE_COUNT:
        fail("pinned legacy source blob contains duplicate TEST_CASE titles")
    if frozenset(blob_titles) != inventory_titles:
        fail("legacy inventory titles differ from the pinned Git blob")

    commit_type = git_object_type(repository, EXPECTED_BASE["commit"])
    if commit_type is None:
        return True
    if commit_type != "commit":
        fail("pinned legacy base object is not a Git commit")
    commit = run_git(
        repository,
        ["cat-file", "commit", EXPECTED_BASE["commit"]],
        "legacy base commit",
    )
    tree_lines = [line for line in commit.splitlines() if line.startswith("tree ")]
    if tree_lines != [f"tree {EXPECTED_BASE['tree']}"]:
        fail("pinned legacy base commit does not reference the expected tree")

    tree_type = git_object_type(repository, EXPECTED_BASE["tree"])
    if tree_type is None:
        return True
    if tree_type != "tree":
        fail("pinned legacy base tree object is not a Git tree")
    resolved_blob = run_git(
        repository,
        ["rev-parse", f"{EXPECTED_BASE['commit']}:{EXPECTED_BASE['path']}"],
        "legacy source path",
    ).strip()
    if resolved_blob != EXPECTED_BASE["blob"]:
        fail("pinned legacy source path does not reference the expected blob")
    return True


def load_mapping(path: Path = MAPPING) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != MAPPING_COLUMNS:
            fail("legacy mapping columns are invalid")
        rows = list(reader)
    for index, row in enumerate(rows, start=2):
        valid_columns = set(row) == set(MAPPING_COLUMNS)
        populated_columns = all(row.get(column) for column in MAPPING_COLUMNS)
        if not valid_columns or not populated_columns:
            fail(f"legacy mapping row {index} is malformed")
    return rows


def verify(
    *,
    mapping: Path = MAPPING,
    inventory: Path = INVENTORY,
    runtime_root: Path = ROOT / "runtime",
    repository: Path = REPOSITORY,
    check_git: bool = True,
) -> tuple[int, int, bool]:
    inventory_titles = load_inventory(inventory)
    rows = load_mapping(mapping)
    if len(rows) != EXPECTED_TITLE_COUNT:
        fail(f"expected {EXPECTED_TITLE_COUNT} retired cases, found {len(rows)}")

    titles = [row["legacy_title"] for row in rows]
    mapped_ids = [row["stable_case_id"] for row in rows]
    for label, values in (("legacy title", titles), ("mapped stable ID", mapped_ids)):
        duplicates = sorted(
            value for value, occurrences in Counter(values).items() if occurrences != 1
        )
        if duplicates:
            fail(f"duplicate {label}: {', '.join(duplicates)}")

    mapped_titles = frozenset(titles)
    if mapped_titles != inventory_titles:
        missing = sorted(inventory_titles - mapped_titles)
        unexpected = sorted(mapped_titles - inventory_titles)
        fail(
            "legacy title inventory mismatch: missing="
            + " | ".join(missing)
            + " unexpected="
            + " | ".join(unexpected)
        )

    discovered: dict[str, str] = {}
    for source in sorted(runtime_root.rglob("*.cpp")):
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

    git_verified = (
        verify_git_provenance(inventory_titles, repository) if check_git else False
    )
    return len(rows), len(discovered), git_verified


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "runtime")
    parser.add_argument("--repository", type=Path, default=REPOSITORY)
    parser.add_argument("--no-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    mappings, stable_cases, git_verified = verify(
        mapping=args.mapping,
        inventory=args.inventory,
        runtime_root=args.runtime_root,
        repository=args.repository,
        check_git=not args.no_git,
    )
    provenance = "Git blob verified" if git_verified else "pinned inventory verified"
    print(
        f"verified {mappings} legacy mappings and {stable_cases} stable cases; "
        + provenance
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"legacy parity check failed: {error}", file=sys.stderr)
        sys.exit(1)
