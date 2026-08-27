#!/usr/bin/env python3
"""Validate CPack source archives without extracting untrusted paths."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath


REQUIRED_METADATA = (
    "CMakeLists.txt",
    "LICENSE",
    "LICENSE.mio",
    "README.md",
    "csv2.pc.in",
    "csv2Config.cmake.in",
)

LOCAL_WORK_DIRECTORIES = {
    ".codex_tmp",
    ".idea",
    ".temp",
    ".tmp",
    ".vs",
    ".vscode",
    "analysis-cppcheck-build-dir",
    "artifacts",
    "build",
    "coverage",
    "Debug",
    "out",
    "Release",
    "test-output",
    "test-results",
    "x64",
    "x86",
}
LOCAL_WORK_PREFIXES = ("build-", "cmake-build-", "coverage-")
LOCAL_WORK_FILES = {".DS_Store", "desktop.ini"}
LOCAL_WORK_SUFFIXES = {
    ".a",
    ".dll",
    ".docstates",
    ".dylib",
    ".exe",
    ".gcda",
    ".gcno",
    ".iml",
    ".lib",
    ".log",
    ".nupkg",
    ".o",
    ".obj",
    ".pdb",
    ".profraw",
    ".pyc",
    ".pyd",
    ".pyo",
    ".so",
    ".suo",
    ".tmp",
    ".user",
    ".userosscache",
}
GENERATED_BUILD_NAMES = {
    ".ninja_deps",
    ".ninja_log",
    "CMakeCache.txt",
    "CMakeFiles",
    "CTestTestfile.cmake",
    "Testing",
    "_deps",
    "build.ninja",
    "cmake_install.cmake",
    "install_manifest.txt",
    "rules.ninja",
}


def safe_parts(member_name: str, archive: Path) -> tuple[str, ...]:
    if not member_name or "\\" in member_name or "\0" in member_name:
        raise RuntimeError(f"unsafe member path in {archive}: {member_name!r}")
    path = PurePosixPath(member_name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RuntimeError(f"unsafe member path in {archive}: {member_name!r}")
    return path.parts


def forbidden_source_member(relative: str, *, directory: bool = False) -> bool:
    path = PurePosixPath(relative)
    directory_parts = path.parts if directory else path.parts[:-1]
    return (
        any(part.startswith(".git") for part in path.parts)
        or any(
            part in LOCAL_WORK_DIRECTORIES
            or part.startswith(LOCAL_WORK_PREFIXES)
            for part in directory_parts
        )
        or any(part in GENERATED_BUILD_NAMES for part in path.parts)
        or (
            not directory
            and (
                path.name in LOCAL_WORK_FILES
                or path.name.endswith("-writer-output.csv")
                or path.name.endswith("~")
                or path.suffix in LOCAL_WORK_SUFFIXES
            )
        )
    )


def source_contract(source_root: Path) -> dict[str, bytes]:
    try:
        root = source_root.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"source root does not exist: {source_root}") from error
    required: list[Path] = [root / name for name in REQUIRED_METADATA]
    for relative_root in (Path("include/csv2"), Path("single_include/csv2")):
        header_root = root / relative_root
        headers = sorted(header_root.rglob("*.hpp")) if header_root.is_dir() else []
        if not headers:
            raise RuntimeError(f"source header tree is empty: {header_root}")
        required.extend(headers)

    contract: dict[str, bytes] = {}
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"required source contract file does not exist: {path}")
        relative = path.relative_to(root).as_posix()
        if relative in contract:
            raise RuntimeError(f"duplicate source contract path: {relative}")
        contract[relative] = path.read_bytes()
    return contract


def archive_inventory(path: Path) -> tuple[str, dict[str, tuple[int, str]]]:
    if not path.is_file():
        raise RuntimeError(f"source archive does not exist: {path}")
    inventory: dict[str, tuple[int, str]] = {}
    member_paths: set[str] = set()
    package_root: str | None = None
    try:
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                parts = safe_parts(member.name, path)
                if package_root is None:
                    package_root = parts[0]
                    if not package_root.startswith("csv2-"):
                        raise RuntimeError(
                            f"unexpected package root in {path}: {package_root}"
                        )
                elif parts[0] != package_root:
                    raise RuntimeError(f"multiple package roots in {path}")

                normalized = PurePosixPath(*parts).as_posix()
                if normalized in member_paths:
                    raise RuntimeError(
                        f"duplicate normalized member in {path}: {member.name}"
                    )
                member_paths.add(normalized)
                if len(parts) == 1:
                    if not member.isdir():
                        raise RuntimeError(
                            f"top-level package member is not a directory in {path}: "
                            f"{member.name}"
                        )
                    continue

                relative = PurePosixPath(*parts[1:]).as_posix()
                if forbidden_source_member(relative, directory=member.isdir()):
                    raise RuntimeError(
                        f"forbidden source package member in {path}: {relative}"
                    )
                if member.isdir():
                    continue
                if not member.isfile():
                    raise RuntimeError(
                        f"unsupported non-regular member in {path}: {member.name}"
                    )
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"could not read archive member: {member.name}")
                digest = hashlib.sha256(extracted.read()).hexdigest()
                inventory[relative] = (member.size, digest)
    except (tarfile.TarError, OSError) as error:
        raise RuntimeError(f"could not read source archive {path}: {error}") from error

    if package_root is None or not inventory:
        raise RuntimeError(f"source archive is empty: {path}")
    return package_root, inventory


def archive_kind(path: Path) -> str:
    if path.name.endswith(".tar.gz"):
        return "tgz"
    if path.name.endswith(".tar.xz"):
        return "txz"
    raise RuntimeError(f"unsupported source archive format: {path}")


def extract_archive(path: Path, extract_root: Path, package_root: str) -> Path:
    destination = extract_root / archive_kind(path)
    if destination.exists():
        raise RuntimeError(
            f"source archive extraction destination exists: {destination}"
        )
    destination.mkdir(parents=True)
    try:
        with tarfile.open(path, "r:*") as archive:
            normalized_paths: set[str] = set()
            for member in archive.getmembers():
                parts = safe_parts(member.name, path)
                normalized = PurePosixPath(*parts).as_posix()
                if normalized in normalized_paths:
                    raise RuntimeError(
                        f"duplicate normalized member in {path}: {member.name}"
                    )
                normalized_paths.add(normalized)
                if parts[0] != package_root:
                    raise RuntimeError(f"multiple package roots in {path}")
                output = destination.joinpath(*parts)
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise RuntimeError(
                        f"unsupported non-regular member in {path}: {member.name}"
                    )
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"could not read archive member: {member.name}")
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as stream:
                    shutil.copyfileobj(extracted, stream)
                output.chmod(member.mode & 0o777)
    except (tarfile.TarError, OSError) as error:
        raise RuntimeError(f"could not extract source archive {path}: {error}") from error
    return destination / package_root


def verify_archives(
    paths: Iterable[Path],
    *,
    source_root: Path,
    extract_root: Path | None = None,
) -> list[Path]:
    archives = tuple(paths)
    if not archives:
        raise RuntimeError("no source archives were provided")
    contract = source_contract(source_root)
    expected_contract = {
        name: (len(content), hashlib.sha256(content).hexdigest())
        for name, content in contract.items()
    }
    reference_root: str | None = None
    reference_inventory: dict[str, tuple[int, str]] | None = None
    reference_path: Path | None = None
    verified: list[tuple[Path, str]] = []
    for path in archives:
        archive_kind(path)
        package_root, inventory = archive_inventory(path)
        missing = sorted(expected_contract.keys() - inventory.keys())
        if missing:
            raise RuntimeError(
                f"source archive {path} is missing required files: "
                f"{', '.join(missing)}"
            )
        mismatched = sorted(
            name
            for name, expected in expected_contract.items()
            if inventory[name] != expected
        )
        if mismatched:
            raise RuntimeError(
                f"source archive {path} does not match source contract: "
                f"{', '.join(mismatched)}"
            )
        if reference_inventory is None:
            reference_root = package_root
            reference_inventory = inventory
            reference_path = path
        elif package_root != reference_root or inventory != reference_inventory:
            raise RuntimeError(f"source archive {path} does not match {reference_path}")
        verified.append((path, package_root))

    extracted: list[Path] = []
    if extract_root is not None:
        for path, package_root in verified:
            extracted.append(extract_archive(path, extract_root, package_root))
    return extracted


def parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--extract-root", type=Path)
    parser.add_argument("archives", type=Path, nargs="+")
    return parser.parse_args(arguments)


def main(arguments: Iterable[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        extracted = verify_archives(
            args.archives,
            source_root=args.source_root,
            extract_root=args.extract_root,
        )
    except RuntimeError as error:
        print(f"source archive verification failed: {error}", file=sys.stderr)
        return 1
    print(f"verified {len(args.archives)} equivalent CPack source archives")
    for path in extracted:
        print(f"extracted verified source tree: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
