#!/usr/bin/env python3
"""Compatibility bridge to the Copier-managed hook implementation."""

from pathlib import Path
import runpy


TARGET = Path(__file__).resolve().parents[2] / ".project-agent-workflow/hooks/semantic_guard_advisory.py"
runpy.run_path(str(TARGET), run_name="__main__")
