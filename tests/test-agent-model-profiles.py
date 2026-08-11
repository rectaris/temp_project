#!/usr/bin/env python3
"""Tests for fixed generated-agent model profile normalization."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "update_agent_model_profiles",
    ROOT / "scripts/update_agent_model_profiles.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AgentModelProfileTests(unittest.TestCase):
    def test_adds_missing_fields_without_changing_instructions(self) -> None:
        original = '''name = "worker"
description = "Customized worker."
sandbox_mode = "read-only"

developer_instructions = """
Preserve this project instruction.
"""
'''
        rendered = MODULE.render_profile(original, "gpt-5.6-luna", "low")
        self.assertIn('model = "gpt-5.6-luna"', rendered)
        self.assertIn('model_reasoning_effort = "low"', rendered)
        self.assertIn("Preserve this project instruction.", rendered)

    def test_replaces_existing_fields_idempotently(self) -> None:
        original = '''name = "worker"
description = "Customized worker."
model = "old-model"
model_reasoning_effort = "max"
sandbox_mode = "workspace-write"
'''
        rendered = MODULE.render_profile(original, "gpt-5.6-terra", "medium")
        self.assertEqual(rendered, MODULE.render_profile(rendered, "gpt-5.6-terra", "medium"))
        self.assertIn('description = "Customized worker."', rendered)
        self.assertIn('sandbox_mode = "workspace-write"', rendered)

    def test_replaces_existing_indented_fields_without_changing_indent(self) -> None:
        original = '''  name = "worker"
  description = "Customized worker."
  model = "old-model"
  model_reasoning_effort = "max"
  sandbox_mode = "workspace-write"
'''
        rendered = MODULE.render_profile(original, "gpt-5.6-luna", "low")
        self.assertIn('  model = "gpt-5.6-luna"', rendered)
        self.assertIn('  model_reasoning_effort = "low"', rendered)
        self.assertIn('  description = "Customized worker."', rendered)

    def test_inserts_missing_fields_after_indented_anchors(self) -> None:
        original = '''  name = "worker"
  description = "Indent-preserving worker."
sandbox_mode = "read-only"
'''
        rendered = MODULE.render_profile(original, "gpt-5.6-luna", "low")
        self.assertIn('  model = "gpt-5.6-luna"', rendered)
        self.assertIn('  model_reasoning_effort = "low"', rendered)

    def test_refuses_duplicated_indented_model_fields(self) -> None:
        original = '''name = "worker"
description = "Customized worker."
model = "duplicate"
  model = "duplicate-two"
'''
        with self.assertRaises(MODULE.ProfileError):
            MODULE.render_profile(original, "gpt-5.6-luna", "low")

    def test_refuses_invalid_toml(self) -> None:
        original = '''name = "worker"
sandbox_mode = "read-only"
[invalid [section
'''
        with self.assertRaises(MODULE.ProfileError):
            MODULE.render_profile(original, "gpt-5.6-luna", "low")

    def test_check_reports_profiles_that_need_changes_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            agents = destination / ".codex/agents"
            agents.mkdir(parents=True)
            original = 'name = "worker"\ndescription = "Keep me."\nsandbox_mode = "read-only"\n'
            for name in MODULE.PROFILES:
                (agents / f"{name}.toml").write_text(original, encoding="utf-8")
            changed = MODULE.normalize_destination(destination, check=True)
            self.assertEqual(len(changed), len(MODULE.PROFILES))
            self.assertNotIn("model =", (agents / "repo_explorer.toml").read_text(encoding="utf-8"))

    def test_refuses_missing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            agents = destination / ".codex/agents"
            agents.mkdir(parents=True)
            (agents / "change_reviewer.toml").write_text('name = "worker"\n', encoding="utf-8")
            with self.assertRaises(MODULE.ProfileError):
                MODULE.normalize_destination(destination)

    def test_refuses_symlinked_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            agents = destination / ".codex/agents"
            agents.mkdir(parents=True)
            target = destination / "target.toml"
            target.write_text('name = "worker"\n', encoding="utf-8")
            for name in MODULE.PROFILES:
                path = agents / f"{name}.toml"
                if name == "repo_explorer":
                    path.symlink_to(target)
                else:
                    path.write_text('name = "worker"\n', encoding="utf-8")
            with self.assertRaises(MODULE.ProfileError):
                MODULE.normalize_destination(destination)


if __name__ == "__main__":
    unittest.main()
