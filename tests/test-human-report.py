#!/usr/bin/env python3
"""Focused tests for local human report assessment and rendering."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "template/.project-agent-workflow/scripts/human-report.py"


def base_report() -> dict[str, object]:
    return {
        "version": 1,
        "title": "Delivery decision",
        "language": "en",
        "audience": "developer",
        "purpose": "decision",
        "summary": "Choose a delivery approach from repository evidence.",
        "facts": [
            {
                "label": "Current state",
                "value": "The source is available.",
                "certainty": "confirmed",
                "source": "docs/source.md",
            }
        ],
        "decisions": [],
        "relations": [],
        "risks": [],
        "next_actions": [],
        "presentation": {
            "explicit_html": False,
            "needs_cross_comparison": False,
            "needs_filtering": False,
        },
        "content_safety": {
            "reviewed": True,
            "contains_raw_logs": False,
            "contains_unredacted_sensitive_data": False,
        },
        "sources": ["docs/source.md"],
    }


class HumanReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        managed = self.root / ".project-agent-workflow"
        (managed / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, managed / "scripts/human-report.py")
        shutil.copy2(
            ROOT / "template/.project-agent-workflow/scripts/security_rules.py",
            managed / "scripts/security_rules.py",
        )
        (self.root / "docs").mkdir()
        (self.root / "docs/source.md").write_text("# Source\n\nConfirmed evidence.\n", encoding="utf-8")
        self.set_mode("agent_select_local")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def set_mode(self, mode: str) -> None:
        (self.root / ".project-agent-workflow/human-report.json").write_text(
            json.dumps({"version": 1, "mode": mode}), encoding="utf-8"
        )

    def write_report(self, report: dict[str, object]) -> Path:
        path = self.root / "report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, ".project-agent-workflow/scripts/human-report.py", *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def complex_report(self) -> dict[str, object]:
        report = base_report()
        report["title"] = "<script>alert(1)</script> decision"
        facts = report["facts"]
        assert isinstance(facts, list) and isinstance(facts[0], dict)
        facts[0]["label"] = "<script>alert(2)</script>"
        presentation = report["presentation"]
        assert isinstance(presentation, dict)
        presentation["needs_cross_comparison"] = True
        report["decisions"] = [
            {
                "question": "Which option should be used?",
                "options": [
                    {
                        "label": label,
                        "summary": f"Summary for {label}.",
                        "advantages": ["Advantage"],
                        "disadvantages": ["Disadvantage"],
                    }
                    for label in ("A", "B", "C")
                ],
                "recommendation": "A",
                "reason": "It preserves the local boundary.",
            }
        ]
        return report

    def test_complex_report_is_assessed_and_rendered_safely(self) -> None:
        example = self.run_cli("example")
        self.assertEqual(example.returncode, 0, example.stderr)
        self.assertEqual(json.loads(example.stdout)["content_safety"]["reviewed"], False)

        report_path = self.write_report(self.complex_report())
        assessed = self.run_cli("assess", report_path.name)
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        assessment = json.loads(assessed.stdout)
        self.assertEqual(assessment["decision"], "generate")
        self.assertEqual(assessment["score"], 4)

        rendered = self.run_cli("render", report_path.name, "--report-id", "delivery-decision")
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertEqual(
            rendered.stdout.strip(), ".agent-artifacts/human-reports/delivery-decision/index.html"
        )
        output = self.root / rendered.stdout.strip()
        text = output.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text)
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("Content-Security-Policy", text)
        self.assertNotIn("https://", text)
        expected_hash = hashlib.sha256((self.root / "docs/source.md").read_bytes()).hexdigest()
        self.assertIn(expected_hash, text)
        self.assertTrue(output.with_name("assessment.json").is_file())

        first = text
        rerendered = self.run_cli("render", report_path.name, "--report-id", "delivery-decision")
        self.assertEqual(rerendered.returncode, 0, rerendered.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), first)

    def test_simple_report_is_skipped_without_output(self) -> None:
        report_path = self.write_report(base_report())
        assessed = self.run_cli("assess", report_path.name)
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        self.assertEqual(json.loads(assessed.stdout)["decision"], "skip")
        rendered = self.run_cli("render", report_path.name, "--report-id", "simple")
        self.assertEqual(rendered.returncode, 3)
        self.assertFalse((self.root / ".agent-artifacts").exists())

    def test_unreviewed_or_sensitive_content_is_blocked(self) -> None:
        report = base_report()
        safety = report["content_safety"]
        assert isinstance(safety, dict)
        safety["reviewed"] = False
        safety["contains_unredacted_sensitive_data"] = True
        assessed = self.run_cli("assess", self.write_report(report).name)
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        result = json.loads(assessed.stdout)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(len(result["blocking_reasons"]), 2)

        report = base_report()
        report["summary"] = "Token " + "ghp_" + "a" * 30
        detected = self.run_cli("assess", self.write_report(report).name)
        self.assertEqual(detected.returncode, 0, detected.stderr)
        result = json.loads(detected.stdout)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("GitHub token-like material was detected", result["blocking_reasons"])

    def test_disabled_mode_skips_an_explicit_report(self) -> None:
        report = base_report()
        presentation = report["presentation"]
        assert isinstance(presentation, dict)
        presentation["explicit_html"] = True
        self.set_mode("disabled")
        assessed = self.run_cli("assess", self.write_report(report).name)
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        self.assertEqual(json.loads(assessed.stdout)["decision"], "skip")

    def test_unknown_fields_and_unsafe_sources_are_rejected(self) -> None:
        report = base_report()
        report["unexpected"] = "not allowed"
        invalid = self.run_cli("assess", self.write_report(report).name)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("unknown=['unexpected']", invalid.stderr)

        report = base_report()
        (self.root / ".agent-artifacts").mkdir()
        (self.root / ".agent-artifacts/source.md").write_text("unsafe", encoding="utf-8")
        report["sources"] = [".agent-artifacts/source.md"]
        facts = report["facts"]
        assert isinstance(facts, list) and isinstance(facts[0], dict)
        facts[0]["source"] = ".agent-artifacts/source.md"
        unsafe = self.run_cli("assess", self.write_report(report).name)
        self.assertEqual(unsafe.returncode, 2)
        self.assertIn("outside the allowed evidence boundary", unsafe.stderr)

    def test_output_id_and_symlink_boundaries_are_enforced(self) -> None:
        report_path = self.write_report(self.complex_report())
        invalid_id = self.run_cli("render", report_path.name, "--report-id", "../escape")
        self.assertEqual(invalid_id.returncode, 2)
        self.assertFalse((self.root.parent / "escape").exists())

        outside = self.root / "outside"
        outside.mkdir()
        artifacts = self.root / ".agent-artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "human-reports").symlink_to(outside, target_is_directory=True)
        symlinked = self.run_cli("render", report_path.name, "--report-id", "safe-id")
        self.assertEqual(symlinked.returncode, 2)
        self.assertIn("symlink output root", symlinked.stderr)


if __name__ == "__main__":
    unittest.main()
