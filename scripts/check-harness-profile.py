#!/usr/bin/env python3
"""Root entry point for the template-owned harness profile checker."""

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
        / "check-harness-profile.py"
    )
    spec = importlib.util.spec_from_file_location("check_harness_profile_shared", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"harness profile implementation is missing: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    raise SystemExit(module.main())
