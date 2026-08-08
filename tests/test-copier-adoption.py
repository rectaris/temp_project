#!/usr/bin/env python3
"""Focused tests for non-destructive namespaced-layout adoption."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/adopt-to-namespaced-layout.py"
SPEC = importlib.util.spec_from_file_location("copier_adoption", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CopierAdoptionTest(unittest.TestCase):
    def test_adoption_backs_up_and_preserves_legacy_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            self.write(repo / ".copier-answers.yml", "_commit: v0.4.5\n_src_path: local-template\n")
            self.write(repo / "AGENTS.md", "# Project Rules\n\nPreserve local routing.\n")
            self.write(repo / "docs/agent/SPEC_ENVIRONMENT.md", "project environment\n")
            self.write(repo / "scripts/create-plan.sh", "project plan helper\n")
            self.write(repo / ".codex/skills/decision-audit/SKILL.md", "project skill changes\n")
            self.write(repo / ".codex/agents/docs_researcher.toml", "project agent changes\n")
            self.write(repo / ".codex/hooks/stop_review_gate.py", "legacy stop hook\n")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)

            def fake_recopy(
                destination: Path,
                copier_executable: str | None,
                target_ref: str,
                data: tuple[str, ...],
            ) -> None:
                self.assertIsNone(copier_executable)
                self.assertEqual(target_ref, "v1.1.0")
                self.assertEqual(data, ())
                self.write(destination / ".copier-answers.yml", "_commit: v1.1.0\n_src_path: local-template\n")
                self.write(destination / ".project-agent-workflow/AGENTS.md", "managed policy\n")
                self.write(destination / ".project-agent-workflow/ownership.yaml", "version: 1\n")
                self.write(destination / ".codex/hooks/stop_review_gate.py", "stable bridge\n")

            with patch.object(MODULE, "run_recopy", side_effect=fake_recopy):
                MODULE.adopt(repo, "v1.1.0", None, ())

            self.assertEqual(
                (repo / "docs/agent/SPEC_ENVIRONMENT.md").read_text(encoding="utf-8"),
                "project environment\n",
            )
            self.assertEqual((repo / "scripts/create-plan.sh").read_text(encoding="utf-8"), "project plan helper\n")
            self.assertEqual(
                (repo / ".codex/skills/decision-audit/SKILL.md").read_text(encoding="utf-8"),
                "project skill changes\n",
            )
            self.assertEqual(
                (repo / ".codex/agents/docs_researcher.toml").read_text(encoding="utf-8"),
                "project agent changes\n",
            )
            self.assertIn("project-agent-workflow:managed-core:start", (repo / "AGENTS.md").read_text(encoding="utf-8"))
            backup = repo / ".project-agent-workflow-migration/v1-pre-namespace"
            self.assertEqual((backup / ".codex/hooks/stop_review_gate.py").read_text(encoding="utf-8"), "legacy stop hook\n")
            manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["operation"], "recopy_adoption")
            self.assertEqual(manifest["previous_ref"], "v0.4.5")
            self.assertEqual(manifest["target_ref"], "v1.1.0")

    def test_adoption_rejects_the_published_unsafe_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self.write(repo / ".copier-answers.yml", "_commit: v0.4.5\n_src_path: local-template\n")
            with self.assertRaisesRegex(SystemExit, "v1.0.0 contains the unsafe"):
                MODULE.adopt(repo, "v1.0.0", None, ())

    def test_adoption_rejects_an_unversioned_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            with self.assertRaisesRegex(SystemExit, "stable release tag"):
                MODULE.adopt(repo, "main", None, ())

    def test_unchanged_enabled_legacy_skillspector_becomes_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            content = b"legacy generated helper\n"
            self.write(
                repo / ".copier-answers.yml",
                "skillspector_mode: document_optional\n",
            )
            helper = repo / "scripts/skillspector-scan.sh"
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_bytes(content)
            manifest: dict[str, object] = {}
            digests = {"scripts/skillspector-scan.sh": hashlib.sha256(content).hexdigest()}

            with patch.object(MODULE, "LEGACY_OPTIONAL_DIGESTS", digests):
                retired, review = MODULE.reconcile_unchanged_optional_paths(repo, manifest)

            self.assertEqual(retired, [])
            self.assertEqual(review, [])
            self.assertEqual(helper.read_text(encoding="utf-8"), MODULE.SKILLSPECTOR_BRIDGE)
            self.assertEqual(
                manifest["bridged_legacy_optional_paths"],
                ["scripts/skillspector-scan.sh"],
            )

    @staticmethod
    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
