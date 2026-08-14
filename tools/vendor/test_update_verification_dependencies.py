import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

import update_verification_dependencies as vendor


class VendorIntegrityTests(unittest.TestCase):
    def make_repository(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        snapshot = root / "third_party" / "verification" / "sample"
        snapshot.mkdir(parents=True)
        (snapshot / "LICENSE").write_bytes(b"license\n")
        (snapshot / "source.cpp").write_bytes(b"int value;\n")
        files = ["LICENSE", "source.cpp"]
        list_path = root / "third_party" / "verification" / "sample.files"
        list_path.write_text("\n".join(files) + "\n", encoding="utf-8")
        snapshot_digest = vendor.snapshot_hash(snapshot, files)
        hash_path = root / "third_party" / "verification" / "sample.sha256"
        hash_path.write_text(
            "\n".join(vendor.hash_lines(snapshot, files)) + "\n", encoding="utf-8"
        )
        manifest = {
            "schema": vendor.SCHEMA,
            "dependencies": {
                "sample": {
                    "root": "third_party/verification/sample",
                    "file_list": "third_party/verification/sample.files",
                    "hash_list": "third_party/verification/sample.sha256",
                    "license_file": "LICENSE",
                    "snapshot_sha256": snapshot_digest,
                    "archive_sha256": hashlib.sha256(b"archive").hexdigest(),
                    "archive_url": "https://invalid.example/archive.tar.gz",
                }
            },
        }
        (root / "third_party" / "verification" / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return temporary, root, manifest["dependencies"]["sample"]

    def test_accepts_exact_snapshot(self):
        temporary, root, entry = self.make_repository()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(
            vendor.check_dependency(root, "sample", entry), entry["snapshot_sha256"]
        )

    def test_rejects_extra_file(self):
        temporary, root, entry = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / entry["root"] / "extra").write_bytes(b"unexpected")
        with self.assertRaisesRegex(vendor.VendorError, "file-list mismatch"):
            vendor.check_dependency(root, "sample", entry)

    def test_rejects_modified_file(self):
        temporary, root, entry = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / entry["root"] / "source.cpp").write_bytes(b"changed")
        with self.assertRaisesRegex(vendor.VendorError, "SHA-256 mismatch"):
            vendor.check_dependency(root, "sample", entry)

    def test_rejects_stale_per_file_hash_allowlist(self):
        temporary, root, entry = self.make_repository()
        self.addCleanup(temporary.cleanup)
        hash_path = root / entry["hash_list"]
        hash_path.write_text("0" * 64 + "  LICENSE\n", encoding="utf-8")
        with self.assertRaisesRegex(vendor.VendorError, "allowlist is stale"):
            vendor.check_dependency(root, "sample", entry)

    def test_rejects_unsafe_whitelist_path(self):
        for value in ("../outside", r"..\..\outside", r"C:\outside", r"\\server\share\outside"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(vendor.VendorError, "unsafe path"):
                    vendor.safe_relative_path(value)

    def test_archive_extraction_rejects_windows_escape_paths(self):
        for value in (r"..\..\outside", r"C:\outside", r"\\server\share\outside"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                archive_path = Path(directory) / "unsafe.tar"
                payload = b"outside"
                with tarfile.open(archive_path, "w") as archive:
                    member = tarfile.TarInfo(value)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                with tarfile.open(archive_path) as archive:
                    with self.assertRaisesRegex(vendor.VendorError, "unsafe path"):
                        vendor.extract_regular_files(archive, Path(directory) / "stage")
                self.assertFalse((Path(directory) / "outside").exists())

    def test_archive_extraction_rejects_mixed_separator_escape(self):
        value = "root/../..\\outside"
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "unsafe.tar"
            payload = b"outside"
            with tarfile.open(archive_path, "w") as archive:
                member = tarfile.TarInfo(value)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            with tarfile.open(archive_path) as archive:
                with self.assertRaisesRegex(vendor.VendorError, "unsafe path"):
                    vendor.extract_regular_files(archive, Path(directory) / "stage")


if __name__ == "__main__":
    unittest.main()
