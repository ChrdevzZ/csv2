from __future__ import annotations

import sys
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = BENCHMARK_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
