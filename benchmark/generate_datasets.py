#!/usr/bin/env python3
"""Compatibility entry point for the deterministic corpus generator."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "datasets" / "generate.py"),
        run_name="__main__",
    )
