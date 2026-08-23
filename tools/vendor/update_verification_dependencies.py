#!/usr/bin/env python3
"""Audit, fetch, and stage CSV2 verification dependency snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Mapping, Sequence


SCHEMA = "csv2-verification-vendor-v1"


class VendorError(RuntimeError):
    pass


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_manifest(root: Path) -> Mapping[str, object]:
    path = root / "third_party" / "verification" / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise VendorError(f"cannot read {path}: {error}") from error
    if manifest.get("schema") != SCHEMA:
        raise VendorError(f"unsupported vendor manifest schema in {path}")
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict) or not dependencies:
        raise VendorError("vendor manifest has no dependencies")
    return manifest


def dependency(manifest: Mapping[str, object], name: str) -> Mapping[str, object]:
    dependencies = manifest["dependencies"]
    assert isinstance(dependencies, dict)
    value = dependencies.get(name)
    if not isinstance(value, dict):
        raise VendorError(f"unknown dependency: {name}")
    return value


def safe_relative_path(value: str) -> PurePosixPath:
    if "\\" in value or ":" in value or re.match(r"^[A-Za-z]:", value):
        raise VendorError(f"unsafe path in vendor whitelist: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
        raise VendorError(f"unsafe path in vendor whitelist: {value!r}")
    return path


def contained_target(root: Path, value: str) -> Path:
    relative = safe_relative_path(value)
    root = root.resolve()
    target = root.joinpath(*relative.parts).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise VendorError(f"unsafe path outside vendor staging root: {value!r}") from error
    return target


def read_file_list(root: Path, entry: Mapping[str, object]) -> List[str]:
    list_path = root / str(entry["file_list"])
    try:
        values = [line.strip() for line in list_path.read_text(encoding="utf-8").splitlines()]
    except OSError as error:
        raise VendorError(f"cannot read {list_path}: {error}") from error
    values = [value for value in values if value and not value.startswith("#")]
    for value in values:
        safe_relative_path(value)
    if values != sorted(set(values)):
        raise VendorError(f"{list_path} must be sorted and contain no duplicates")
    return values


def files_under(root: Path) -> List[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def snapshot_hash(root: Path, files: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in files:
        path = root.joinpath(*safe_relative_path(value).parts)
        data = path.read_bytes()
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
    return digest.hexdigest()


def hash_lines(snapshot: Path, files: Iterable[str]) -> List[str]:
    return [
        f"{sha256_file(snapshot.joinpath(*safe_relative_path(value).parts))}  {value}"
        for value in files
    ]


def write_hash_list(root: Path, name: str) -> None:
    entry = dependency(load_manifest(root), name)
    files = read_file_list(root, entry)
    snapshot = root / str(entry["root"])
    if files != files_under(snapshot):
        raise VendorError(f"{name} file-list does not match the snapshot")
    hash_path = root / str(entry["hash_list"])
    contents = "\n".join(hash_lines(snapshot, files)) + "\n"
    hash_path.write_text(contents, encoding="utf-8", newline="\n")
    print(f"{hash_path}: {len(files)} files")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_dependency(root: Path, name: str, entry: Mapping[str, object]) -> str:
    snapshot = root / str(entry["root"])
    expected_files = read_file_list(root, entry)
    actual_files = files_under(snapshot)
    if expected_files != actual_files:
        missing = sorted(set(expected_files) - set(actual_files))
        extra = sorted(set(actual_files) - set(expected_files))
        raise VendorError(f"{name} file-list mismatch; missing={missing}, extra={extra}")
    license_path = snapshot / str(entry["license_file"])
    if not license_path.is_file():
        raise VendorError(f"{name} license is missing: {license_path}")
    actual_hash = snapshot_hash(snapshot, expected_files)
    expected_hash = str(entry["snapshot_sha256"]).lower()
    if actual_hash != expected_hash:
        raise VendorError(
            f"{name} snapshot SHA-256 mismatch: expected {expected_hash}, got {actual_hash}"
        )
    hash_path = root / str(entry["hash_list"])
    try:
        expected_hash_lines = hash_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise VendorError(f"{name} hash allowlist is missing: {hash_path}") from error
    actual_hash_lines = hash_lines(snapshot, expected_files)
    if expected_hash_lines != actual_hash_lines:
        raise VendorError(f"{name} per-file SHA-256 allowlist is stale")
    return actual_hash


def check_all(root: Path) -> None:
    manifest = load_manifest(root)
    dependencies = manifest["dependencies"]
    assert isinstance(dependencies, dict)
    for name in sorted(dependencies):
        entry = dependency(manifest, name)
        value = check_dependency(root, name, entry)
        print(f"{name}: {value}")


def print_snapshot_hash(root: Path, name: str) -> None:
    entry = dependency(load_manifest(root), name)
    files = read_file_list(root, entry)
    snapshot = root / str(entry["root"])
    if files != files_under(snapshot):
        raise VendorError(f"{name} file-list does not match the snapshot")
    print(snapshot_hash(snapshot, files))


def download(root: Path, name: str, output: Path, allow_network: bool) -> None:
    if not allow_network:
        raise VendorError("fetch requires the explicit --allow-network flag")
    entry = dependency(load_manifest(root), name)
    if output.exists() or output.is_symlink():
        raise VendorError(f"refusing to overwrite existing archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            with urllib.request.urlopen(str(entry["archive_url"]), timeout=60) as response:
                shutil.copyfileobj(response, stream)
            stream.flush()
            os.fsync(stream.fileno())
        actual_hash = sha256_file(temporary)
        expected_hash = str(entry["archive_sha256"]).lower()
        if actual_hash != expected_hash:
            raise VendorError(
                f"downloaded {name} archive SHA-256 mismatch: {actual_hash}"
            )
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"{output}: {actual_hash}")


def safe_members(archive: tarfile.TarFile) -> Sequence[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = safe_relative_path(member.name)
        if (path.is_absolute() or ".." in path.parts or member.issym() or
                member.islnk() or not (member.isdir() or member.isfile())):
            raise VendorError(f"unsafe archive member: {member.name}")
    return members


def extract_regular_files(archive: tarfile.TarFile, destination: Path) -> None:
    for member in safe_members(archive):
        target = contained_target(destination, member.name)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise VendorError(f"cannot read archive member: {member.name}")
        with source, target.open("xb") as stream:
            shutil.copyfileobj(source, stream)


def stage(root: Path, name: str, archive_path: Path, output: Path) -> None:
    entry = dependency(load_manifest(root), name)
    actual_archive_hash = sha256_file(archive_path)
    expected_archive_hash = str(entry["archive_sha256"]).lower()
    if actual_archive_hash != expected_archive_hash:
        raise VendorError(
            f"{name} archive SHA-256 mismatch: expected {expected_archive_hash}, "
            f"got {actual_archive_hash}"
        )
    if output.exists() or output.is_symlink():
        raise VendorError(f"refusing to overwrite staging path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent)
    )
    whitelist = read_file_list(root, entry)
    try:
        with tempfile.TemporaryDirectory(prefix="csv2-vendor-") as temporary:
            extracted = Path(temporary)
            with tarfile.open(archive_path, "r:*") as archive:
                extract_regular_files(archive, extracted)
            roots = [path for path in extracted.iterdir() if path.is_dir()]
            if len(roots) != 1:
                raise VendorError("vendor archive must contain exactly one root directory")
            archive_root = roots[0]
            for value in whitelist:
                source = contained_target(archive_root, value)
                if not source.is_file() or source.is_symlink():
                    raise VendorError(f"whitelisted archive file is missing: {value}")
                destination = contained_target(staging, value)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        actual_snapshot_hash = snapshot_hash(staging, whitelist)
        expected_snapshot_hash = str(entry["snapshot_sha256"]).lower()
        if actual_snapshot_hash != expected_snapshot_hash:
            raise VendorError(
                f"staged {name} snapshot SHA-256 mismatch: {actual_snapshot_hash}"
            )
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f"{output}: {actual_snapshot_hash}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    hashing = commands.add_parser("hash")
    hashing.add_argument("dependency")
    fetch = commands.add_parser("fetch")
    fetch.add_argument("dependency")
    fetch.add_argument("output", type=Path)
    fetch.add_argument("--allow-network", action="store_true")
    staging = commands.add_parser("stage")
    staging.add_argument("dependency")
    staging.add_argument("archive", type=Path)
    staging.add_argument("output", type=Path)
    hashes = commands.add_parser("write-hashes")
    hashes.add_argument("dependency")
    return parser.parse_args(argv)


def main(argv: Sequence[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "check":
            check_all(root)
        elif args.command == "hash":
            print_snapshot_hash(root, args.dependency)
        elif args.command == "fetch":
            download(root, args.dependency, args.output.resolve(), args.allow_network)
        elif args.command == "stage":
            stage(root, args.dependency, args.archive.resolve(), args.output.resolve())
        elif args.command == "write-hashes":
            write_hash_list(root, args.dependency)
        else:  # pragma: no cover - argparse enforces the command set
            raise VendorError(f"unsupported command: {args.command}")
    except (OSError, KeyError, TypeError, VendorError, tarfile.TarError) as error:
        print(f"vendor error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
