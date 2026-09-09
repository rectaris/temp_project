#!/usr/bin/env python3
"""Regression tests for the project-controlled natural-japanese adaptation."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class NaturalJapaneseTest(unittest.TestCase):
    def test_root_and_template_skill_assets_align(self) -> None:
        root = ROOT / ".codex/skills/natural-japanese"
        generated = ROOT / "template/.project-agent-workflow/skills/natural-japanese"
        for relative in (
            "SKILL.md",
            "agents/openai.yaml",
            "references/workflow.md",
            "references/upstream-adaptation.md",
            "scripts/check-japanese-prose.py",
            "LICENSE",
        ):
            root_text = (root / relative).read_text(encoding="utf-8")
            generated_text = (generated / relative).read_text(encoding="utf-8")
            normalized = generated_text.replace(
                ".project-agent-workflow/skills/natural-japanese/",
                ".codex/skills/natural-japanese/",
            ).replace(".project-agent-workflow/", "").replace(
                ".agents/skills/", ".codex/skills/"
            )
            self.assertEqual(root_text, normalized, relative)

        for helper in (root / "scripts/check-japanese-prose.py", generated / "scripts/check-japanese-prose.py"):
            self.assertTrue(helper.stat().st_mode & 0o111, helper)

    def test_discovery_bridges_and_routing(self) -> None:
        self.assertIn(
            ".codex/skills/natural-japanese/SKILL.md",
            read(".agents/skills/natural-japanese/SKILL.md"),
        )
        self.assertIn(
            ".project-agent-workflow/skills/natural-japanese/SKILL.md",
            read("template/.agents/skills/natural-japanese/SKILL.md"),
        )
        for path in ("AGENTS.md", "template/AGENTS.md.jinja", "template/.project-agent-workflow/AGENTS.md.jinja"):
            text = read(path)
            self.assertIn("natural-japanese", text)
            for marker in ("facts", "quotations", "uncertainty", "project terms", "requested form", "document purpose"):
                self.assertIn(marker, text)

    def test_policy_priority_and_three_depths(self) -> None:
        for path in (
            "docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
            "template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
        ):
            text = read(path)
            lowered = text.lower()
            positions = [
                lowered.index("requested tone"),
                lowered.index("facts, quotations, uncertainty"),
                lowered.index("document's purpose"),
                lowered.index("project specification"),
                lowered.index("naturalness advice"),
                lowered.index("mechanical lint"),
            ]
            self.assertEqual(positions, sorted(positions))
            self.assertIn("short Japanese reply", text)
            self.assertIn("drafting or revising a Japanese file", text)
            self.assertIn("important long-form document", text)
            self.assertIn("Do not invent personal experience", text)
            self.assertIn("code-only edits", text)

    def test_upstream_provenance_and_license(self) -> None:
        provenance = read(".codex/skills/natural-japanese/references/upstream-adaptation.md")
        self.assertIn("v1.5.0", provenance)
        self.assertIn("21e632661a910bf97289c501089ad11eb8b4d85f", provenance)
        self.assertIn("runtime downloads", provenance)
        self.assertIn("future upstream update requires an explicit review", provenance)
        license_text = read(".codex/skills/natural-japanese/LICENSE")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 coji", license_text)

    def test_lint_is_advisory_dependency_free_and_skips_code(self) -> None:
        script = ROOT / ".codex/skills/natural-japanese/scripts/check-japanese-prose.py"
        before = """重要なのは事実です。\n\n```text\n重要なのはコード内の文字列です。\n```\n"""
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "sample.md"
            target.write_text(before, encoding="utf-8")
            result = subprocess.run(
                ["python3", str(script), "--json", str(target)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), before)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["advisory"])
            self.assertFalse(payload["modified"])
            self.assertEqual(payload["finding_count"], 1)
            self.assertEqual(payload["findings"][0]["line"], 1)

        script_text = script.read_text(encoding="utf-8")
        for forbidden in ("subprocess", "urllib", "requests", "http://", "https://", "sudachi"):
            self.assertNotIn(forbidden, script_text.lower())

    def test_lint_skips_tilde_and_longer_backtick_fences(self) -> None:
        script = ROOT / ".codex/skills/natural-japanese/scripts/check-japanese-prose.py"
        text = (
            "~~~~text\n"
            "重要なのはチルダ内です。\n"
            "~~~~\n"
            "````text\n"
            "```not-a-closer\n"
            "重要なのは長いフェンス内です。\n"
            "````\n"
            "```bad`info\n"
            "重要なのは無効な開始行の後の本文です。\n"
            "重要なのは本文です。\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "fences.md"
            target.write_text(text, encoding="utf-8")
            result = subprocess.run(
                ["python3", str(script), "--json", str(target)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["finding_count"], 2)
        self.assertEqual(
            [item["line"] for item in payload["findings"]],
            [9, 10],
        )

    def test_evaluation_record(self) -> None:
        result = subprocess.run(
            ["python3", "scripts/natural-japanese-evaluation.py"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_evaluation_module_rejects_drift(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "natural_japanese_evaluation",
            ROOT / "scripts/natural-japanese-evaluation.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(module.EvaluationError):
            module.require(False, "expected rejection")


if __name__ == "__main__":
    unittest.main()
