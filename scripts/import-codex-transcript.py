#!/usr/bin/env python3
"""Delegate root Codex transcript import to the generated template importer."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


TEMPLATE_IMPORTER = Path(__file__).resolve().parents[1] / "template/.project-agent-workflow/scripts/import-codex-transcript.py"

sys.path.insert(0, str(TEMPLATE_IMPORTER.parent))
runpy.run_path(str(TEMPLATE_IMPORTER), run_name="__main__")
