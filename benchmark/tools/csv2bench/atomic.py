"""Crash-safe, same-directory JSON report replacement."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


def replace(temporary: Path, output: Path) -> None:
    for attempt in range(100):
        try:
            os.replace(temporary, output)
            return
        except PermissionError as error:
            if os.name != "nt" or getattr(error, "winerror", None) not in (5, 32) or attempt == 99:
                raise
            time.sleep(0.01)


def stage_json(path: Path, report: dict[str, object]) -> Path:
    """Durably stage JSON beside its destination without publishing it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
            descriptor = -1
            json.dump(report, destination, indent=2, sort_keys=True)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        return temporary
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def publish_staged(temporary: Path, path: Path) -> None:
    """Atomically publish a same-directory staged file and sync its directory."""
    try:
        if temporary.parent.resolve(strict=True) != path.parent.resolve(strict=True):
            raise RuntimeError("staged JSON must share its destination directory")
        replace(temporary, path)
        if os.name == "posix":
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_descriptor = os.open(path.parent, flags)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def discard_staged(temporary: Path) -> None:
    try:
        temporary.unlink()
    except FileNotFoundError:
        pass


def write_json(path: Path, report: dict[str, object]) -> None:
    temporary = stage_json(path, report)
    publish_staged(temporary, path)
