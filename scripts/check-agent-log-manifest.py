#!/usr/bin/env python3
"""Delegate root manifest validation to the generated template checker."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


TEMPLATE_CHECKER = Path(__file__).resolve().parents[1] / "template/.project-agent-workflow/scripts/check-agent-log-manifest.py"

sys.path.insert(0, str(TEMPLATE_CHECKER.parent))
runpy.run_path(str(TEMPLATE_CHECKER), run_name="__main__")
