#!/usr/bin/env python3
"""Compatibility entry point for the CSV2 performance evidence finalizer."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "tools"
sys.path.insert(0, str(TOOLS))

from csv2bench.evidence import main  # noqa: E402


if __name__ == "__main__":
    main()
