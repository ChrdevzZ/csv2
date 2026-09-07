from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
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
            files["benchmark/protocol/schemas/build-v2.schema.json"] = b"{}\n"
            write_archive(archive, files)
            verify_source_archives.verify_archives(
                [archive], source_root=SOURCE_ROOT
            )

    def test_rejects_missing_required_file(self) -> None:
        for missing in (
            "LICENSE.mio", "cmake/Csv2SourcePackaging.cmake",
            "cmake/csv2-package-source.cmake.in",
            "cmake/verification/Csv2VerificationOptions.cmake",
        ):
            with (
                self.subTest(missing=missing),
                tempfile.TemporaryDirectory() as directory,
            ):
                archive = Path(directory) / "csv2-1.8.0.tar.gz"
                files = required_files()
                del files[missing]
                write_archive(archive, files)
                with self.assertRaisesRegex(RuntimeError, "missing required files"):
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

    def test_rejects_nonportable_paths_before_extracting(self) -> None:
        for unsafe in (
            "C:/outside.txt", "folder/C:outside.txt", "bad\x01.txt",
            "bad\x7f.txt", "bad\x85.txt",
        ):
            with (
                self.subTest(unsafe=unsafe),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                archive = root / "csv2-1.8.0.tar.gz"
                write_archive(archive, {"safe.txt": b"safe", unsafe: b"unsafe"})
                with self.assertRaisesRegex(RuntimeError, "unsafe member path"):
                    verify_source_archives.extract_archive(
                        archive, root / "extracted", "csv2-1.8.0"
                    )
                self.assertFalse((root / "extracted/tgz/csv2-1.8.0/safe.txt").exists())

    def test_rejects_links_before_extracting_regular_members(self) -> None:
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "csv2-1.8.0.tar.gz"
                with tarfile.open(path, "w:gz") as archive:
                    regular = tarfile.TarInfo("csv2-1.8.0/safe.txt")
                    regular.size = 1
                    archive.addfile(regular, io.BytesIO(b"x"))
                    link = tarfile.TarInfo("csv2-1.8.0/link")
                    link.type = kind
                    link.linkname = "../outside"
                    archive.addfile(link)
                with self.assertRaisesRegex(RuntimeError, "non-regular member"):
                    verify_source_archives.extract_archive(
                        path, root / "extracted", "csv2-1.8.0"
                    )
                self.assertFalse((root / "extracted").exists())

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
            ".ccache/a/cache-entry",
            "test/.ccache/CACHEDIR.TAG",
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


@unittest.skipUnless(shutil.which("cmake"), "CMake is needed for source packaging")
class SourcePackagingTests(unittest.TestCase):
    def run_cmake(self, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["cmake", *arguments], cwd=cwd, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def make_source(self, source: Path) -> None:
        source.mkdir(parents=True)
        for relative, content in required_files().items():
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (source / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.10)\n"
            "project(csv2 VERSION 1.8.0 LANGUAGES NONE)\n"
            "include(cmake/Csv2SourcePackaging.cmake)\n",
            encoding="utf-8",
        )
        (source / "cmake").mkdir(exist_ok=True)
        for name in ("Csv2SourcePackaging.cmake", "csv2-package-source.cmake.in"):
            shutil.copy2(SOURCE_ROOT / "cmake" / name, source / "cmake" / name)
        for relative in (
            "nested/[quoted].csv", "nested/数据 (a)+.txt",
            "nested/" + "long-" * 22 + "[数据].txt",
        ):
            target = source / relative
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(b"source content\n")
            target.chmod(0o755)
        for relative in (
            ".ccache/cache-entry", "nested/.ccache/cache-entry",
            "build-local/generated",
        ):
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"must not ship")

    def test_literal_source_build_output_and_working_paths(self) -> None:
        for source_parent in ("ordinary", "build-review", "out", "parent [x]+(y) 空格", "parent ]==]"):
            with (
                self.subTest(source_parent=source_parent),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                source = root / source_parent / "source"
                build = source / "generated [b] ]=]"
                output = source / "archives [a] ]===]"
                cwd = root / "working [w]"
                cwd.mkdir()
                self.make_source(source)
                self.run_cmake(
                    "-H" + str(source), "-B" + str(build),
                    "-DCSV2_SOURCE_PACKAGE_OUTPUT_DIRECTORY=" + str(output),
                    cwd=cwd,
                )
                self.run_cmake(
                    "--build", str(build), "--target", "package_source", cwd=cwd
                )
                archives = [
                    output / ("csv2-1.8.0.tar." + extension)
                    for extension in ("gz", "xz")
                ]
                verify_source_archives.verify_archives(archives, source_root=source)
                first = verify_source_archives.archive_inventory(archives[0])
                self.assertIn("nested/[quoted].csv", first[1])
                self.assertIn("nested/数据 (a)+.txt", first[1])
                self.assertFalse(any(
                    name.startswith(("generated [b] ]=]/", "archives [a] ]===]/"))
                    for name in first[1]
                ))
                self.assertIn("nested/" + "long-" * 22 + "[数据].txt", first[1])
                if os.name != "nt":
                    with tarfile.open(archives[0]) as archive:
                        member = archive.getmember("csv2-1.8.0/nested/[quoted].csv")
                        self.assertEqual(member.mode & 0o777, 0o755)
                self.run_cmake("-P", str(build / "csv2-package-source.cmake"), cwd=cwd)
                self.assertEqual(
                    first, verify_source_archives.archive_inventory(archives[0])
                )
                self.assertFalse((build / "CPackSourceConfig.cmake").exists())

    def test_in_source_build_migration_concurrency_and_failure_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source [in]"
            self.make_source(source)
            (source / "CPackSourceConfig.cmake").write_text(
                "obsolete", encoding="utf-8"
            )
            self.run_cmake("-H" + str(source), "-B" + str(source), cwd=source)
            self.assertFalse((source / "CPackSourceConfig.cmake").exists())
            self.run_cmake(
                "--build", str(source), "--target", "package_source", cwd=source
            )
            archives = [
                source / ("csv2-1.8.0.tar." + extension)
                for extension in ("gz", "xz")
            ]
            verify_source_archives.verify_archives(archives, source_root=source)
            initial = verify_source_archives.archive_inventory(archives[0])
            for name in ("Makefile", "CPackConfig.cmake", "csv2-package-source.cmake"):
                self.assertNotIn(name, initial[1])
            command = ["cmake", "-P", str(source / "csv2-package-source.cmake")]
            processes = [
                subprocess.Popen(
                    command, cwd=source, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True,
                )
                for _ in range(2)
            ]
            for process in processes:
                output, _ = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 0, output)
            self.assertEqual(
                initial, verify_source_archives.archive_inventory(archives[0])
            )
            self.assertFalse(list(source.glob(".csv2-source-package-*/")))
            archives[0].unlink()
            archives[0].mkdir()
            sentinel = archives[0] / "sentinel"
            sentinel.write_bytes(b"preserve")
            failed = subprocess.run(command, cwd=source, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            self.assertFalse(list(source.glob(".csv2-source-package-*/")))


if __name__ == "__main__":
    unittest.main()
