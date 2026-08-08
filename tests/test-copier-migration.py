#!/usr/bin/env python3
"""Behavior tests for the pre-v1 namespaced-layout migration."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATOR = ROOT / "scripts/migrate-to-namespaced-layout.py"


class NamespacedLayoutMigrationTest(unittest.TestCase):
    def run_migration(self, repo: Path, stage: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(MIGRATOR), "--stage", stage],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_preserves_generated_legacy_paths_and_leaves_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self.write(repo / "AGENTS.md", "legacy agent policy\n")
            self.write(repo / "scripts/create-plan.sh", "legacy generated helper\n")
            self.write(repo / "scripts/product-build.sh", "project helper\n")
            self.write(repo / ".codex/skills/decision-audit/SKILL.md", "modified generic skill\n")
            self.write(repo / ".codex/skills/product-rules/SKILL.md", "project skill\n")
            self.write(repo / ".github/workflows/ci.yml", "name: Project CI\n")
            self.write(
                repo / "docs/agent/external-services.yaml",
                "external_services:\n  mcp:\n    credential_env: \"MCP_TOKEN\"\n",
            )

            self.run_migration(repo, "before")

            backup = repo / ".project-agent-workflow-migration/v1-pre-namespace"
            self.assertFalse((repo / "AGENTS.md").exists())
            self.assertEqual((backup / "AGENTS.md").read_text(encoding="utf-8"), "legacy agent policy\n")
            self.assertTrue((backup / "scripts/create-plan.sh").is_file())
            self.assertTrue((backup / ".codex/skills/decision-audit/SKILL.md").is_file())
            self.assertTrue((repo / "scripts/product-build.sh").is_file())
            self.assertTrue((repo / ".codex/skills/product-rules/SKILL.md").is_file())
            self.assertTrue((repo / ".github/workflows/ci.yml").is_file())

            (repo / ".github/workflows/ci.yml").unlink()
            self.write(repo / "AGENTS.md", "new bridge\n")
            self.run_migration(repo, "after")

            self.assertEqual((repo / "AGENTS.md").read_text(encoding="utf-8"), "new bridge\n")
            self.assertEqual(
                (repo / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
                "name: Project CI\n",
            )
            external = (repo / "docs/agent/external-services.yaml").read_text(encoding="utf-8")
            self.assertIn("authentication: environment", external)
            self.assertIn('credential_reference: "MCP_TOKEN"', external)
            self.assertNotIn("credential_env:", external)
            manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("AGENTS.md", manifest["moved"])
            self.assertIn(".github/workflows/ci.yml", manifest["copied"])
            self.assertIn(".github/workflows/ci.yml", manifest["restored"])

    @staticmethod
    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
