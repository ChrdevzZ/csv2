from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import update_verification_dependencies as vendor


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.close()
        return False


class FailingResponse(Response):
    def read(self, size=-1):
        if self.tell() != 0:
            raise OSError("simulated interrupted response")
        return super().read(4 if size < 0 else min(size, 4))


class VendorToolSafetyTests(unittest.TestCase):
    def write_repository(
        self, root: Path, archive_hash: str, snapshot_hash: str
    ) -> None:
        metadata_root = root / "third_party" / "verification"
        metadata_root.mkdir(parents=True)
        (metadata_root / "sample.files").write_text(
            "LICENSE\nsource.cpp\n", encoding="utf-8"
        )
        manifest = {
            "schema": vendor.SCHEMA,
            "dependencies": {
                "sample": {
                    "root": "third_party/verification/sample",
                    "file_list": "third_party/verification/sample.files",
                    "hash_list": "third_party/verification/sample.sha256",
                    "license_file": "LICENSE",
                    "snapshot_sha256": snapshot_hash,
                    "archive_sha256": archive_hash,
                    "archive_url": "https://invalid.example/archive.tar.gz",
                }
            },
        }
        (metadata_root / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def make_archive(self, root: Path) -> tuple[Path, dict[str, bytes]]:
        payloads = {"LICENSE": b"license\n", "source.cpp": b"int value;\n"}
        archive_path = root / "sample.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            directory = tarfile.TarInfo("sample-root")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            for relative, payload in payloads.items():
                member = tarfile.TarInfo(f"sample-root/{relative}")
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        return archive_path, payloads

    def expected_snapshot_hash(self, root: Path, payloads: dict[str, bytes]) -> str:
        snapshot = root / "expected"
        snapshot.mkdir()
        for relative, payload in payloads.items():
            (snapshot / relative).write_bytes(payload)
        return vendor.snapshot_hash(snapshot, sorted(payloads))

    def test_rejects_unsafe_whitelist_paths(self) -> None:
        for value in (
            "../outside",
            r"..\..\outside",
            r"C:\outside",
            r"\\server\share\outside",
        ):
            with self.subTest(value=value):
                with self.assertRaises(vendor.VendorError):
                    vendor.safe_relative_path(value)

    def test_archive_extraction_cannot_escape_staging_root(self) -> None:
        for value in (
            "root/../..\\outside",
            r"..\..\outside",
            r"C:\outside",
            r"\\server\share\outside",
        ):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive_path = root / "unsafe.tar"
                payload = b"outside"
                with tarfile.open(archive_path, "w") as archive:
                    member = tarfile.TarInfo(value)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                with tarfile.open(archive_path) as archive:
                    with self.assertRaises(vendor.VendorError):
                        vendor.extract_regular_files(archive, root / "stage")
                self.assertFalse((root / "outside").exists())

    def test_failed_download_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"downloaded archive"
            self.write_repository(root, hashlib.sha256(b"other").hexdigest(), "0" * 64)
            output = root / "downloads" / "sample.tar.gz"
            with mock.patch.object(
                vendor.urllib.request, "urlopen", return_value=Response(payload)
            ):
                with self.assertRaises(vendor.VendorError):
                    vendor.download(root, "sample", output, allow_network=True)
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob(f".{output.name}.*")), [])

    def test_interrupted_download_is_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"downloaded archive"
            self.write_repository(root, hashlib.sha256(payload).hexdigest(), "0" * 64)
            output = root / "downloads" / "sample.tar.gz"
            with mock.patch.object(
                vendor.urllib.request,
                "urlopen",
                return_value=FailingResponse(payload),
            ):
                with self.assertRaises(OSError):
                    vendor.download(root, "sample", output, allow_network=True)
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob(f".{output.name}.*")), [])

    def test_verified_download_is_published_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"downloaded archive"
            self.write_repository(root, hashlib.sha256(payload).hexdigest(), "0" * 64)
            output = root / "downloads" / "sample.tar.gz"
            with mock.patch.object(
                vendor.urllib.request, "urlopen", return_value=Response(payload)
            ), mock.patch("builtins.print"):
                vendor.download(root, "sample", output, allow_network=True)
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(list(output.parent.glob(f".{output.name}.*")), [])

    def test_failed_stage_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path, _ = self.make_archive(root)
            self.write_repository(root, vendor.sha256_file(archive_path), "0" * 64)
            output = root / "stage" / "sample"
            with self.assertRaises(vendor.VendorError):
                vendor.stage(root, "sample", archive_path, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob(f".{output.name}.*")), [])

    def test_verified_stage_is_published_as_a_complete_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path, payloads = self.make_archive(root)
            self.write_repository(
                root,
                vendor.sha256_file(archive_path),
                self.expected_snapshot_hash(root, payloads),
            )
            output = root / "stage" / "sample"
            with mock.patch("builtins.print"):
                vendor.stage(root, "sample", archive_path, output)
            self.assertEqual(
                {path.name: path.read_bytes() for path in output.iterdir()}, payloads
            )
            self.assertEqual(list(output.parent.glob(f".{output.name}.*")), [])


if __name__ == "__main__":
    unittest.main()
