from __future__ import annotations

import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).with_name("verify_source_archives.py")
SOURCE_ROOT = MODULE.parents[2]
SPEC = importlib.util.spec_from_file_location("verify_source_archives", MODULE)
assert SPEC and SPEC.loader
verify_source_archives = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_source_archives)


def write_archive(
    path: Path, files: dict[str, bytes], *, include_root_directory: bool = False
) -> None:
    mode = "w:gz" if path.name.endswith(".tar.gz") else "w:xz"
    with tarfile.open(path, mode) as archive:
        if include_root_directory:
            root = tarfile.TarInfo("csv2-1.8.0/")
            root.type = tarfile.DIRTYPE
            root.mode = 0o755
            archive.addfile(root)
        for name, content in files.items():
            info = tarfile.TarInfo(f"csv2-1.8.0/{name}")
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))


def required_files() -> dict[str, bytes]:
    return verify_source_archives.source_contract(SOURCE_ROOT)


class VerifySourceArchivesTests(unittest.TestCase):
    def test_accepts_equivalent_complete_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archives = [root / "csv2-1.8.0.tar.gz", root / "csv2-1.8.0.tar.xz"]
            for archive in archives:
                write_archive(archive, required_files())
            verify_source_archives.verify_archives(
                archives, source_root=SOURCE_ROOT
            )

    def test_accepts_legal_top_level_directory_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "csv2-1.8.0.tar.gz"
            write_archive(
                archive, required_files(), include_root_directory=True
            )
            verify_source_archives.verify_archives(
                [archive], source_root=SOURCE_ROOT
            )

    def test_accepts_file_name_that_only_resembles_a_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "csv2-1.8.0.tar.gz"
            files = required_files()
            files["benchmark/protocol/schemas/build-v1.schema.json"] = b"{}\n"
            write_archive(archive, files)
            verify_source_archives.verify_archives(
                [archive], source_root=SOURCE_ROOT
            )

    def test_rejects_missing_required_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "csv2-1.8.0.tar.gz"
            files = required_files()
            del files["LICENSE.mio"]
            write_archive(archive, files)
            with self.assertRaisesRegex(
                RuntimeError, "missing required files.*LICENSE.mio"
            ):
                verify_source_archives.verify_archives(
                    [archive], source_root=SOURCE_ROOT
                )

    def test_rejects_each_missing_public_header(self) -> None:
        complete = required_files()
        public_headers = [
            name
            for name in complete
            if name.startswith("include/csv2/")
            or name.startswith("single_include/csv2/")
        ]
        self.assertGreater(len(public_headers), 3)
        for missing in public_headers:
            with (
                self.subTest(missing=missing),
                tempfile.TemporaryDirectory() as directory,
            ):
                archive = Path(directory) / "csv2-1.8.0.tar.gz"
                incomplete = dict(complete)
                del incomplete[missing]
                write_archive(archive, incomplete)
                with self.assertRaisesRegex(
                    RuntimeError, f"missing required files.*{missing}"
                ):
                    verify_source_archives.verify_archives(
                        [archive], source_root=SOURCE_ROOT
                    )

    def test_rejects_unsafe_member_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "csv2-1.8.0.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                for name, content in required_files().items():
                    info = tarfile.TarInfo(f"csv2-1.8.0/{name}")
                    info.size = len(content)
                    stream.addfile(info, io.BytesIO(content))
                unsafe = tarfile.TarInfo("csv2-1.8.0/../escape")
                unsafe.size = 1
                stream.addfile(unsafe, io.BytesIO(b"x"))
            with self.assertRaisesRegex(RuntimeError, "unsafe member path"):
                verify_source_archives.verify_archives(
                    [archive], source_root=SOURCE_ROOT
                )

    def test_rejects_duplicate_normalized_member_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "csv2-1.8.0.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                for name, content in required_files().items():
                    info = tarfile.TarInfo(f"csv2-1.8.0/{name}")
                    info.size = len(content)
                    stream.addfile(info, io.BytesIO(content))
                duplicate = tarfile.TarInfo("csv2-1.8.0/./README.md")
                duplicate.size = 1
                stream.addfile(duplicate, io.BytesIO(b"x"))
            with self.assertRaisesRegex(
                RuntimeError, "duplicate normalized member"
            ):
                verify_source_archives.verify_archives(
                    [archive], source_root=SOURCE_ROOT
                )

    def test_rejects_local_work_products_and_repository_control_files(self) -> None:
        forbidden = (
            ".gitattributes",
            ".github/workflows/ci.yml",
            "build/CMakeCache.txt",
            "benchmark/artifacts/report.json",
            "benchmark/build-local/results.txt",
            "benchmark/object.o",
            "benchmark/profile.log",
            "notes~",
            "test/.idea/workspace.xml",
            "tools/cache.pyd",
            "tools/local.user",
            "tools/report-writer-output.csv",
            "tools/ci/__pycache__/policy.pyc",
            "utils/.DS_Store",
        )
        for relative in forbidden:
            with (
                self.subTest(relative=relative),
                tempfile.TemporaryDirectory() as directory,
            ):
                archive = Path(directory) / "csv2-1.8.0.tar.gz"
                files = required_files()
                files[relative] = b"must not ship\n"
                write_archive(archive, files)
                with self.assertRaisesRegex(
                    RuntimeError, "forbidden source package member"
                ):
                    verify_source_archives.verify_archives(
                        [archive], source_root=SOURCE_ROOT
                    )

    def test_rejects_inventory_or_content_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "csv2-1.8.0.tar.gz"
            second = root / "csv2-1.8.0.tar.xz"
            write_archive(first, required_files())
            changed = required_files()
            changed["README.md"] = b"different"
            write_archive(second, changed)
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                verify_source_archives.verify_archives(
                    [first, second], source_root=SOURCE_ROOT
                )

    def test_safely_extracts_each_verified_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archives = [root / "csv2-1.8.0.tar.gz", root / "csv2-1.8.0.tar.xz"]
            for archive in archives:
                write_archive(archive, required_files())
            extraction = root / "extracted"
            verify_source_archives.verify_archives(
                archives,
                source_root=SOURCE_ROOT,
                extract_root=extraction,
            )
            for archive_kind in ("tgz", "txz"):
                self.assertEqual(
                    (
                        extraction
                        / archive_kind
                        / "csv2-1.8.0"
                        / "include/csv2/reader.hpp"
                    ).read_bytes(),
                    (SOURCE_ROOT / "include/csv2/reader.hpp").read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
