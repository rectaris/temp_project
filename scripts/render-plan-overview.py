#!/usr/bin/env python3
"""Entry point for rendering plan overview rows from lifecycle files."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


if __name__ == "__main__":
    module_path = Path(__file__).resolve().parents[1] / "template" / ".project-agent-workflow" / "scripts" / "plan_overview.py"
    spec = importlib.util.spec_from_file_location("plan_overview_shared", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("plan overview implementation is missing: %s" % module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    raise SystemExit(module.main())
