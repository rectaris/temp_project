#!/usr/bin/env python3
"""Root entry point for the template-owned development direction command."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


if __name__ == "__main__":
    module_path = (
        Path(__file__).resolve().parents[1]
        / "template"
        / ".project-agent-workflow"
        / "scripts"
        / "development-direction.py"
    )
    spec = importlib.util.spec_from_file_location("development_direction_shared", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"development direction implementation is missing: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    raise SystemExit(module.main())
