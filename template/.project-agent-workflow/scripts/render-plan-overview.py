#!/usr/bin/env python3
"""Entry point for rendering plan overview rows from lifecycle files."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    module = Path(__file__).resolve().with_name("plan_overview.py")
    runpy.run_path(str(module), run_name="__main__")
