#!/usr/bin/env python3
"""Focused tests for local human report assessment and rendering."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


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

    def set_shared_mode(self, shared_mode: str) -> None:
        (self.root / ".project-agent-workflow/human-report.json").write_text(
            json.dumps({"version": 1, "mode": "agent_select_local", "shared_mode": shared_mode}),
            encoding="utf-8",
        )

    def published(self, report_id: str = "team-decision") -> tuple[Path, Path]:
        directory = self.root / "docs/human-report" / report_id
        return directory / "report.json", directory / "index.html"

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

    def test_shared_publication_needs_explicit_configuration(self) -> None:
        report_path = self.write_report(self.complex_report())
        refused = self.run_cli("publish", report_path.name, "--report-id", "team-decision")
        self.assertEqual(refused.returncode, 4)
        self.assertIn("disabled by project configuration", refused.stderr)
        self.assertFalse((self.root / "docs/human-report").exists())

        self.set_shared_mode("explicit_publish")
        allowed = self.run_cli("publish", report_path.name, "--report-id", "team-decision")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(
            allowed.stdout.split(),
            ["docs/human-report/team-decision/report.json", "docs/human-report/team-decision/index.html"],
        )
        self.assertIn("never stages or commits", allowed.stderr)

    def test_shared_publication_records_provenance_and_detects_stale_sources(self) -> None:
        self.set_shared_mode("explicit_publish")
        report_path = self.write_report(self.complex_report())
        self.assertEqual(self.run_cli("publish", report_path.name, "--report-id", "team-decision").returncode, 0)
        source, html = self.published()

        document = json.loads(source.read_text(encoding="utf-8"))
        expected_hash = hashlib.sha256((self.root / "docs/source.md").read_bytes()).hexdigest()
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["generator_version"], 1)
        self.assertEqual(document["report_id"], "team-decision")
        self.assertEqual(document["sources"], [{"path": "docs/source.md", "sha256": expected_hash}])
        self.assertTrue(document["source_commit"])
        self.assertRegex(document["generated_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        original_generated_at = document["generated_at"]

        rendered = html.read_text(encoding="utf-8")
        for marker in ("team-decision", expected_hash, document["generated_at"], "&lt;script&gt;alert(1)&lt;/script&gt;"):
            self.assertIn(marker, rendered)
        self.assertNotIn("<script", rendered)

        fresh = self.run_cli("verify-shared")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertIn("fresh shared human report: docs/human-report/team-decision", fresh.stdout)

        (self.root / "docs/source.md").write_text("# Source\n\nChanged evidence.\n", encoding="utf-8")
        stale = self.run_cli("verify-shared")
        self.assertEqual(stale.returncode, 4)
        self.assertIn("recorded source docs/source.md changed", stale.stderr)

        time.sleep(1.05)
        superseded = self.run_cli(
            "publish", report_path.name, "--report-id", "team-decision", "--supersede"
        )
        self.assertEqual(superseded.returncode, 0, superseded.stderr)
        current_hash = hashlib.sha256((self.root / "docs/source.md").read_bytes()).hexdigest()
        refreshed_document = json.loads(source.read_text(encoding="utf-8"))
        self.assertNotEqual(refreshed_document["generated_at"], original_generated_at)
        self.assertEqual(
            refreshed_document["sources"],
            [{"path": "docs/source.md", "sha256": current_hash}],
        )
        refreshed = self.run_cli("verify-shared")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)

    def test_shared_publication_requires_explicit_supersede_and_stops_at_conflicts(self) -> None:
        self.set_shared_mode("explicit_publish")
        report_path = self.write_report(self.complex_report())
        self.assertEqual(self.run_cli("publish", report_path.name, "--report-id", "team-decision").returncode, 0)
        source, html = self.published()
        first_source = source.read_text(encoding="utf-8")
        first_html = html.read_text(encoding="utf-8")
        first_generated_at = json.loads(first_source)["generated_at"]

        blocked = self.run_cli("publish", report_path.name, "--report-id", "team-decision")
        self.assertEqual(blocked.returncode, 4)
        self.assertIn("pass --supersede", blocked.stderr)
        self.assertEqual(html.read_text(encoding="utf-8"), first_html)

        time.sleep(1.05)
        superseded = self.run_cli("publish", report_path.name, "--report-id", "team-decision", "--supersede")
        self.assertEqual(superseded.returncode, 0, superseded.stderr)
        self.assertEqual(source.read_text(encoding="utf-8"), first_source)
        self.assertEqual(html.read_text(encoding="utf-8"), first_html)

        changed_report = self.complex_report()
        changed_report["summary"] = "Changed reviewed summary."
        self.write_report(changed_report)
        changed = self.run_cli(
            "publish", report_path.name, "--report-id", "team-decision", "--supersede"
        )
        self.assertEqual(changed.returncode, 0, changed.stderr)
        changed_document = json.loads(source.read_text(encoding="utf-8"))
        self.assertNotEqual(changed_document["generated_at"], first_generated_at)
        self.assertEqual(changed_document["report"]["summary"], "Changed reviewed summary.")

        source.write_text(
            "<<<<<<< HEAD\n" + source.read_text(encoding="utf-8") + "=======\n>>>>>>> other\n", encoding="utf-8"
        )
        conflicted = self.run_cli("verify-shared")
        self.assertEqual(conflicted.returncode, 4)
        self.assertIn("merge conflict marker", conflicted.stderr)

    def test_supersede_rejects_stored_forbidden_sources_and_distinguishes_json_types(self) -> None:
        self.set_shared_mode("explicit_publish")
        report_path = self.write_report(self.complex_report())
        self.assertEqual(self.run_cli("publish", report_path.name, "--report-id", "team-decision").returncode, 0)
        source, html = self.published()
        spec = importlib.util.spec_from_file_location("human_report", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
            spec.loader.exec_module(module)
        original = json.loads(source.read_text())
        for forbidden in (".agent-logs/evidence.md", "../outside.md", ".env"):
            with self.subTest(forbidden=forbidden):
                document = json.loads(json.dumps(original))
                document["sources"][0]["path"] = forbidden
                document["report"]["sources"] = [forbidden]
                document["report"]["facts"][0]["source"] = forbidden
                source.write_text(module.json_text(document))
                html.write_text(module.render_shared_html(document))
                before = (source.read_bytes(), html.read_bytes())
                result = self.run_cli("publish", report_path.name, "--report-id", "team-decision", "--supersede")
                self.assertEqual(result.returncode, 4, result.stderr)
                self.assertIn("no longer publishable", result.stderr)
                self.assertEqual((source.read_bytes(), html.read_bytes()), before)
        for value in (True, 1.0):
            with self.subTest(version=value):
                document = json.loads(json.dumps(original))
                document["schema_version"] = value
                document["generated_at"] = "2000-01-01T00:00:00Z"
                source.write_text(module.json_text(document))
                html.write_text(module.render_shared_html(document))
                result = self.run_cli("publish", report_path.name, "--report-id", "team-decision", "--supersede")
                self.assertEqual(result.returncode, 0, result.stderr)
                current = json.loads(source.read_text())
                self.assertIs(type(current["schema_version"]), int)
                self.assertNotEqual(current["generated_at"], document["generated_at"])
                self.assertEqual(self.run_cli("verify-shared").returncode, 0)

    def test_supersede_rejects_directory_and_file_swaps_after_validation(self) -> None:
        self.set_shared_mode("explicit_publish")
        report = self.complex_report()
        report_path = self.write_report(report)
        spec = importlib.util.spec_from_file_location("human_report", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
            spec.loader.exec_module(module)
        for changed in (False, True):
            for swap in ("directory", "directory-symlink", "report.json", "index.html"):
                with self.subTest(changed=changed, swap=swap):
                    report_id = "race-" + str(changed).lower() + "-" + swap.replace(".", "-")
                    self.write_report(report)
                    self.assertEqual(self.run_cli("publish", report_path.name, "--report-id", report_id).returncode, 0)
                    directory = self.root / "docs/human-report" / report_id
                    original = {name: (directory / name).read_bytes() for name in ("report.json", "index.html")}
                    if changed:
                        self.write_report({**report, "summary": "Changed reviewed content."})
                    replacement = self.root / (report_id + "-replacement")
                    replacement.mkdir()
                    for name in original:
                        (replacement / name).write_text("replacement sentinel")
                    aside = self.root / (report_id + "-original")
                    real_integrity = module.stored_pair_integrity

                    def swap_after_validation(*args, **kwargs):
                        result = real_integrity(*args, **kwargs)
                        self.assertEqual(result[1], [])
                        if swap.startswith("directory"):
                            directory.rename(aside)
                            if swap == "directory-symlink":
                                directory.symlink_to(replacement, target_is_directory=True)
                            else:
                                replacement.rename(directory)
                        else:
                            (directory / swap).rename(aside)
                            (directory / swap).write_text("replacement sentinel")
                        return result

                    previous_cwd = Path.cwd()
                    try:
                        os.chdir(self.root)
                        with (
                            mock.patch.object(module, "stored_pair_integrity", side_effect=swap_after_validation),
                            mock.patch.object(sys, "argv", [str(SCRIPT), "publish", report_path.name, "--report-id", report_id, "--supersede"]),
                            mock.patch.object(sys, "stderr", io.StringIO()) as errors,
                        ):
                            result = module.main()
                            self.assertIn("changed during", errors.getvalue())
                    finally:
                        os.chdir(previous_cwd)
                    self.assertNotEqual(result, 0)
                    if swap.startswith("directory"):
                        for name, content in original.items():
                            self.assertEqual((directory / name).read_text(), "replacement sentinel")
                            self.assertEqual((aside / name).read_bytes(), content)
                    else:
                        self.assertEqual((directory / swap).read_text(), "replacement sentinel")
                        other = "index.html" if swap == "report.json" else "report.json"
                        self.assertEqual((directory / other).read_bytes(), original[other])
                        self.assertEqual(aside.read_bytes(), original[swap])

    def test_shared_writer_does_not_follow_directory_replacement(self) -> None:
        spec = importlib.util.spec_from_file_location("human_report", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
            spec.loader.exec_module(module)
        with self.assertRaises(module.ReportError):
            with module.shared_directory_access("writer-race", self.root, create=True) as (descriptor, _check, _created):
                directory = self.root / "docs/human-report/writer-race"
                aside = self.root / "original-output"
                directory.rename(aside)
                directory.mkdir()
                (directory / "report.json").write_text("replacement sentinel")
                module.atomic_write(directory / "report.json", "new content", directory_fd=descriptor)
                self.assertEqual((directory / "report.json").read_text(), "replacement sentinel")
                self.assertEqual((aside / "report.json").read_text(), "new content")

    def test_supersede_preflights_existing_pair_and_preserves_source_bytes(self) -> None:
        self.set_shared_mode("explicit_publish")
        report_path = self.write_report(self.complex_report())
        published = self.run_cli(
            "publish", report_path.name, "--report-id", "team-decision"
        )
        self.assertEqual(published.returncode, 0, published.stderr)
        source, html = self.published()
        original_html = html.read_text(encoding="utf-8")
        document = json.loads(source.read_text(encoding="utf-8"))
        compact_source = json.dumps(document, separators=(",", ":"))
        source.write_text(compact_source, encoding="utf-8")
        self.assertEqual(self.run_cli("verify-shared").returncode, 0)

        time.sleep(1.05)
        unchanged = self.run_cli(
            "publish",
            report_path.name,
            "--report-id",
            "team-decision",
            "--supersede",
        )
        self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
        self.assertEqual(source.read_text(encoding="utf-8"), compact_source)
        self.assertEqual(html.read_text(encoding="utf-8"), original_html)

        stale_document = dict(document)
        stale_document["generated_at"] = "2000-01-01T00:00:00Z"
        stale_source = json.dumps(stale_document, separators=(",", ":"))
        source.write_text(stale_source, encoding="utf-8")
        stale = self.run_cli(
            "publish",
            report_path.name,
            "--report-id",
            "team-decision",
            "--supersede",
        )
        self.assertEqual(stale.returncode, 4)
        self.assertIn("not the deterministic rendering", stale.stderr)
        self.assertEqual(source.read_text(encoding="utf-8"), stale_source)
        self.assertEqual(html.read_text(encoding="utf-8"), original_html)

        source.write_text(compact_source, encoding="utf-8")
        conflicted_html = original_html + "\n<<<<<<< HEAD\n=======\n>>>>>>> other\n"
        html.write_text(conflicted_html, encoding="utf-8")
        conflicted = self.run_cli(
            "publish",
            report_path.name,
            "--report-id",
            "team-decision",
            "--supersede",
        )
        self.assertEqual(conflicted.returncode, 4)
        self.assertIn("merge conflict marker", conflicted.stderr)
        self.assertEqual(source.read_text(encoding="utf-8"), compact_source)
        self.assertEqual(html.read_text(encoding="utf-8"), conflicted_html)

        html.unlink()
        outside = self.root / "outside-index.html"
        outside.write_text("outside\n", encoding="utf-8")
        html.symlink_to(outside)
        symlinked = self.run_cli(
            "publish",
            report_path.name,
            "--report-id",
            "team-decision",
            "--supersede",
        )
        self.assertEqual(symlinked.returncode, 4)
        self.assertIn("missing published rendered HTML", symlinked.stderr)
        self.assertEqual(source.read_text(encoding="utf-8"), compact_source)
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_shared_publication_gates_reject_unsafe_content_and_tampered_output(self) -> None:
        self.set_shared_mode("explicit_publish")
        report = self.complex_report()
        safety = report["content_safety"]
        assert isinstance(safety, dict)
        safety["contains_raw_logs"] = True
        raw_logs = self.run_cli("publish", self.write_report(report).name, "--report-id", "team-decision")
        self.assertEqual(raw_logs.returncode, 3)
        self.assertFalse((self.root / "docs/human-report").exists())

        report = self.complex_report()
        report["summary"] = "Token " + "ghp_" + "a" * 30
        secret = self.run_cli("publish", self.write_report(report).name, "--report-id", "team-decision")
        self.assertEqual(secret.returncode, 3)
        self.assertFalse((self.root / "docs/human-report").exists())

        report_path = self.write_report(self.complex_report())
        self.assertEqual(self.run_cli("publish", report_path.name, "--report-id", "team-decision").returncode, 0)
        _, html = self.published()
        html.write_text(
            html.read_text(encoding="utf-8")
            .replace("<h1>", '<script src="https://example.invalid/x.js"></script><h1>')
            .replace('<html lang="en">', "<html>"),
            encoding="utf-8",
        )
        tampered = self.run_cli("verify-shared")
        self.assertEqual(tampered.returncode, 4)
        for marker in (
            "not the deterministic rendering",
            "forbidden <script> element",
            "external reference attribute src",
            "must declare a document language",
        ):
            self.assertIn(marker, tampered.stderr)


if __name__ == "__main__":
    unittest.main()
