"""Canonical artifact identities and alias/drift protection."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Sequence


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_existing(path: Path, label: str) -> Path:
    try:
        return path.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(f"{label} does not exist or cannot be resolved: {path}") from error


def canonical_output(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(f"output path cannot be resolved: {path}") from error


def paths_alias(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return left.resolve(strict=False) == right.resolve(strict=False)


def reject_output_alias(
    output: Path, protected_paths: Iterable[tuple[str, Path]]
) -> None:
    for label, protected in protected_paths:
        if paths_alias(output, protected):
            raise RuntimeError(f"output path aliases {label}: {protected}")


def metadata(path: Path, revision: str | None = None) -> dict[str, object]:
    canonical = canonical_existing(path, "artifact")
    stat = canonical.stat()
    result: dict[str, object] = {
        "path": str(canonical),
        "size": stat.st_size,
        "sha256": sha256_file(canonical),
        "mtime_ns": stat.st_mtime_ns,
    }
    if revision is not None:
        result["revision"] = revision
    return result


def bundle_metadata(
    root: Path, paths: Sequence[Path], revision: str
) -> dict[str, object]:
    canonical_root = canonical_existing(root, "source bundle root")
    if not canonical_root.is_dir():
        raise RuntimeError(f"source bundle root is not a directory: {canonical_root}")

    members: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for path in paths:
        canonical = canonical_existing(path, "source bundle member")
        if not canonical.is_file():
            raise RuntimeError(f"source bundle member is not a file: {canonical}")
        try:
            relative = canonical.relative_to(canonical_root).as_posix()
        except ValueError as error:
            raise RuntimeError(
                f"source bundle member is outside its root: {canonical}"
            ) from error
        if relative in seen:
            raise RuntimeError(f"duplicate source bundle member: {relative}")
        seen.add(relative)
        members.append((relative, canonical))

    if not members:
        raise RuntimeError("source bundle must contain at least one file")

    digest = hashlib.sha256()
    files: list[dict[str, object]] = []
    for relative, path in sorted(members):
        contents = path.read_bytes()
        stat = path.stat()
        encoded_path = relative.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
        files.append(
            {
                "path": relative,
                "size": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
                "mtime_ns": stat.st_mtime_ns,
            }
        )

    return {
        "kind": "source-bundle",
        "root": str(canonical_root),
        "revision": revision,
        "sha256": digest.hexdigest(),
        "files": files,
    }


def verify_unchanged(identity: dict[str, object], label: str) -> None:
    if identity.get("kind") == "source-bundle":
        try:
            root = canonical_existing(Path(str(identity["root"])), label)
            members = identity["files"]
            if not isinstance(members, list):
                raise RuntimeError("source bundle files are malformed")
            paths = [root / str(member["path"]) for member in members]
            actual = bundle_metadata(root, paths, str(identity["revision"]))
        except (KeyError, OSError, RuntimeError, TypeError) as error:
            raise RuntimeError(f"{label} identity is invalid or unavailable") from error
        if actual != identity:
            raise RuntimeError(f"{label} changed during collection: source bundle")
        return

    try:
        path = canonical_existing(Path(str(identity["path"])), label)
        actual = metadata(path, identity.get("revision"))
    except (KeyError, OSError, RuntimeError) as error:
        raise RuntimeError(f"{label} identity is invalid or unavailable") from error
    keys = ["path", "size", "sha256"]
    if "mtime_ns" in identity:
        keys.append("mtime_ns")
    for key in keys:
        if actual[key] != identity.get(key):
            raise RuntimeError(f"{label} changed during collection: {key}")
