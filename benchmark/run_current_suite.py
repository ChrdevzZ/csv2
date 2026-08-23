#!/usr/bin/env python3
"""Compatibility entry point for isolated current-tree benchmark cases."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "tools"
sys.path.insert(0, str(TOOLS))

from csv2bench.current import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
