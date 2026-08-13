from __future__ import annotations

import concurrent.futures
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
from csv2bench import artifacts, atomic


class ArtifactTests(unittest.TestCase):
    def test_metadata_is_canonical_and_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_bytes(b"a,b\n")
            identity = artifacts.metadata(path, "revision")
            self.assertEqual(Path(str(identity["path"])), path.resolve())
            artifacts.verify_unchanged(identity, "input")
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "changed during collection"):
                artifacts.verify_unchanged(identity, "input")

    def test_output_alias_rejects_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            alias = Path(directory) / "alias"
            source.write_bytes(b"protected")
            os.link(source, alias)
            with self.assertRaisesRegex(RuntimeError, "aliases dataset"):
                artifacts.reject_output_alias(alias, (("dataset", source),))

    def test_source_bundle_is_order_independent_and_detects_helper_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "entry.py"
            helper = root / "helper.py"
            entry.write_text("import helper\n", encoding="utf-8")
            helper.write_text("VALUE = 1\n", encoding="utf-8")
            first = artifacts.bundle_metadata(
                root, [entry, helper], "tool-bundle"
            )
            reordered = artifacts.bundle_metadata(
                root, [helper, entry], "tool-bundle"
            )
            self.assertEqual(first, reordered)
            artifacts.verify_unchanged(first, "tool bundle")
            helper.write_text("VALUE = 2\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "source bundle"):
                artifacts.verify_unchanged(first, "tool bundle")

    def test_atomic_write_has_no_shared_temporary_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"

            def write(value: int) -> None:
                atomic.write_json(output, {"value": value, "payload": "x" * 4096})

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(write, range(32)))
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn(document["value"], range(32))
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_atomic_write_cleans_failed_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with mock.patch("csv2bench.atomic.replace", side_effect=OSError("blocked")):
                with self.assertRaisesRegex(OSError, "blocked"):
                    atomic.write_json(output, {"value": 1})
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    @unittest.skipUnless(os.name == "posix", "directory fsync is POSIX-only")
    def test_atomic_write_fsyncs_the_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            real_fsync = os.fsync
            descriptors: list[int] = []

            def capture(descriptor: int) -> None:
                descriptors.append(descriptor)
                real_fsync(descriptor)

            with mock.patch("csv2bench.atomic.os.fsync", side_effect=capture):
                atomic.write_json(output, {"value": 1})
            self.assertGreaterEqual(len(descriptors), 2)


if __name__ == "__main__":
    unittest.main()
