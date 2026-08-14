#!/usr/bin/env python3
"""Generate the committed, deterministic CSV2 benchmark smoke corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

SCHEMA = "csv2-benchmark-corpus-v2"
GENERATOR_VERSION = 2
SEED = 0x43535632


class Lcg32:
    """Small, specified PRNG whose output is stable across Python versions."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFF

    def next(self) -> int:
        self._state = (1664525 * self._state + 1013904223) & 0xFFFFFFFF
        return self._state


def fnv1a(chunks: Iterable[bytes]) -> int:
    value = 1469598103934665603
    for chunk in chunks:
        for byte in chunk:
            value ^= byte
            value = (value * 1099511628211) & ((1 << 64) - 1)
    return value


def encode_rows(rows: Sequence[Sequence[str]], line_ending: str = "\n") -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator=line_ending, quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def content_checksum(rows: Sequence[Sequence[str]]) -> int:
    chunks: list[bytes] = []
    for row in rows:
        chunks.append(len(row).to_bytes(8, "little"))
        for field in row:
            data = field.encode("utf-8")
            chunks.append(len(data).to_bytes(8, "little"))
            chunks.append(data)
    return fnv1a(chunks)


def parse_rows(data: bytes) -> list[list[str]]:
    text = data.decode("utf-8")
    return [list(row) for row in csv.reader(io.StringIO(text, newline=""))]


def generated_datasets(scale: int = 1) -> dict[str, tuple[bytes, dict[str, object]]]:
    if scale < 1:
        raise ValueError("scale must be at least one")

    random = Lcg32(SEED)
    boundary_lengths = [15, 16, 31, 32, 63, 64, 255, 256, 4095, 4096]
    short_rows = 128 * scale
    tall_rows = 256 * scale
    wide_rows = 4 * scale
    numeric_rows = 256 * scale
    rows: dict[str, tuple[Sequence[Sequence[str]], str, dict[str, object]]] = {
        "small_startup.csv": ([['a', 'b', 'c']], "\n", {"kind": "small-startup"}),
        "tall_narrow.csv": (
            [[str(index), "x", "y"] for index in range(tall_rows)],
            "\n",
            {"kind": "tall-narrow", "row_count": tall_rows},
        ),
        "short_unquoted.csv": (
            [
                [f"r{row}c{column}_{random.next():08x}" for column in range(8)]
                for row in range(short_rows)
            ],
            "\n",
            {"kind": "short-unquoted", "row_count": short_rows, "column_count": 8},
        ),
        "wide_rows.csv": (
            [[f"r{row}-{column:04d}" for column in range(512)] for row in range(wide_rows)],
            "\n",
            {"kind": "wide-rows", "row_count": wide_rows, "column_count": 512},
        ),
        "numeric.csv": (
            [[str(index), str(-index), str(index * 17)] for index in range(numeric_rows)],
            "\n",
            {"kind": "numeric", "row_count": numeric_rows},
        ),
        "header_empty_lines.csv": (
            [["name", "value"]]
            + [row for _ in range(scale) for row in ([], ["alpha", "1"], [], ["beta", "2"])],
            "\n",
            {"kind": "header-ignored-empty-lines"},
        ),
        "utf8.csv": (
            [["café", "你好", "Καλημέρα"], ["🙂", "naïve", "résumé"]] * scale,
            "\n",
            {"kind": "utf8-byte-payload"},
        ),
        "boundary_fields.csv": (
            [["x" * length, str(length)] for _ in range(scale) for length in boundary_lengths],
            "\n",
            {"kind": "field-boundaries", "lengths": boundary_lengths},
        ),
        "empty_fields.csv": (
            [["", "", ""], ["a", "", ""], ["", "b", ""]] * scale,
            "\n",
            {"kind": "empty-and-trailing-fields"},
        ),
        "crlf.csv": (
            [["12", "345", "6789", "word"]] * scale,
            "\r\n",
            {"kind": "crlf"},
        ),
        "doubled_quotes.csv": (
            [['a"b', 'c""d', "tail"]] * scale,
            "\n",
            {"kind": "doubled-quotes"},
        ),
        "long_field.csv": (
            [["x" * 512, "tail"]] * scale,
            "\n",
            {"kind": "single-long-field", "field_size": 512},
        ),
        "multiline.csv": (
            [["left", "line one\nline two", "right"]] * scale,
            "\n",
            {"kind": "quoted-lf"},
        ),
        "quote_heavy.csv": (
            [["a,b", "c\nd", "e\r\nf"]] * scale,
            "\n",
            {"kind": "quote-heavy"},
        ),
        "trailing_empty.csv": (
            [["a", "b", ""], ["", "", ""]] * scale,
            "\n",
            {"kind": "trailing-empty"},
        ),
    }
    result: dict[str, tuple[bytes, dict[str, object]]] = {}
    for name, (dataset_rows, line_ending, parameters) in rows.items():
        result[name] = (encode_rows(dataset_rows, line_ending), parameters)
    result["invalid_early.csv"] = (b'a"b,c\n', {"kind": "strict-invalid-early"})
    result["invalid_middle.csv"] = (
        b"a,b\n" + b"1,2\n" * scale + b"\"unclosed,field\n3,4\n",
        {"kind": "strict-invalid-middle"},
    )
    result["invalid_late.csv"] = (
        b"a,b\n" + b"1,2\n3,4\n" * scale + b"\"closed\"x,last\n",
        {"kind": "strict-invalid-late"},
    )
    return result


def build_manifest(fixtures: Path, scale: int) -> dict[str, object]:
    invalid = {"invalid_early.csv", "invalid_middle.csv", "invalid_late.csv"}
    generated = generated_datasets(scale)
    records: list[dict[str, object]] = []
    for path in sorted(fixtures.glob("*.csv")):
        data = path.read_bytes()
        valid = path.name not in invalid
        rows = parse_rows(data) if valid else []
        parameters = generated.get(path.name, (b"", {"kind": "legacy-smoke"}))[1]
        records.append(
            {
                "name": path.name,
                "path": f"fixtures/{path.name}",
                "parameters": parameters,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "rows": len(rows) if valid else None,
                "cells": sum(len(row) for row in rows) if valid else None,
                "raw_checksum": str(fnv1a([data])),
                "content_checksum": str(content_checksum(rows)) if valid else None,
                "strict_valid": valid,
            }
        )
    return {
        "schema": SCHEMA,
        "generator_version": GENERATOR_VERSION,
        "prng": {"algorithm": "lcg32", "seed": SEED},
        "scale": scale,
        "datasets": records,
    }


def atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "fixtures")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    if arguments.scale < 1:
        parser.error("--scale must be at least one")
    if arguments.manifest is None:
        arguments.manifest = arguments.output.parent / "manifest.json"

    if arguments.check:
        if not arguments.output.is_dir():
            raise SystemExit("benchmark corpus directory does not exist")
    else:
        arguments.output.mkdir(parents=True, exist_ok=True)

    generated = generated_datasets(arguments.scale)
    expected_names = sorted(generated)
    discovered_names = sorted(path.name for path in arguments.output.glob("*.csv"))
    extras = sorted(set(discovered_names) - set(expected_names))
    if extras:
        raise SystemExit(
            "benchmark corpus contains unexpected CSV fixtures: " + ", ".join(extras)
        )
    if arguments.check:
        missing = sorted(set(expected_names) - set(discovered_names))
        if missing:
            raise SystemExit(
                "benchmark corpus is missing CSV fixtures: " + ", ".join(missing)
            )
    if not arguments.check:
        for name, (data, _) in generated.items():
            atomic_write(arguments.output / name, data)
    else:
        for name, (data, _) in generated.items():
            path = arguments.output / name
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit(f"benchmark corpus fixture is not reproducible: {name}")

    manifest = build_manifest(arguments.output, arguments.scale)
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if arguments.check:
        if not arguments.manifest.exists() or arguments.manifest.read_bytes() != encoded:
            raise SystemExit("benchmark corpus or manifest is not reproducible")
    else:
        atomic_write(arguments.manifest, encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
