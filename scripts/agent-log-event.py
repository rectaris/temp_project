#!/usr/bin/env python3
"""Best-effort Codex lifecycle event logger for this repository root."""

from __future__ import annotations

import runpy
from pathlib import Path


TEMPLATE_HOOK = Path(__file__).resolve().parents[1] / "template/.codex/hooks/agent_log_event.py"

runpy.run_path(str(TEMPLATE_HOOK), run_name="__main__")
