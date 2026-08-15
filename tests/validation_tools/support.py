"""Shared imports, paths, and loader for validation-tool tests."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMAND_MODULES = (
    ROOT / "scripts/plan_validation_commands.py",
    ROOT / "template/.project-agent-workflow/scripts/plan_validation_commands.py",
)
VALIDATE_CHANGE_MODULES = (
    ROOT / "scripts/validate-changes.py",
    ROOT / "template/.project-agent-workflow/scripts/validate-changes.py",
)
SECURITY_RULE_MODULE = ROOT / "template/.project-agent-workflow/scripts/security_rules.py"
SECURITY_CHECK_MODULE = ROOT / "template/.project-agent-workflow/scripts/security-static-check.py"
LEGACY_MIGRATOR = ROOT / "template/.project-agent-workflow/scripts/migrate-legacy-template-files.py"
ROOT_EXTERNAL_SERVICE_CHECK = ROOT / "scripts/check-external-service-policy.py"
PLANLIB = ROOT / "template/.project-agent-workflow/scripts/planlib.py"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
