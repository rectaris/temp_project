#!/usr/bin/env python3
"""Entry point for comparing paired local harness runs from explicit records."""

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
        / "compare-harness-runs.py"
    )
    spec = importlib.util.spec_from_file_location("compare_harness_runs_shared", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("harness comparison implementation is missing: %s" % module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    raise SystemExit(module.main())
