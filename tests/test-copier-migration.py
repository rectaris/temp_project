#!/usr/bin/env python3
"""Behavior tests for the pre-v1 direct-update guard."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATOR = ROOT / "scripts/migrate-to-namespaced-layout.py"


class NamespacedLayoutMigrationTest(unittest.TestCase):
    def test_before_stage_fails_without_changing_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            legacy = repo / "AGENTS.md"
            legacy.write_text("legacy project policy\n", encoding="utf-8")
            subprocess.run(["git", "add", "AGENTS.md"], cwd=repo, check=True)
            before = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout

            result = subprocess.run(
                ["python3", str(MIGRATOR), "--stage", "before"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("destination was not changed", result.stderr)
            self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy project policy\n")
            after = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout
            self.assertEqual(after, before)
            self.assertFalse((repo / ".project-agent-workflow-migration").exists())

    def test_after_stage_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            result = subprocess.run(
                ["python3", str(MIGRATOR), "--stage", "after"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertIn("update guard completed", result.stdout)
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain=v1"],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    check=True,
                ).stdout,
                "",
            )


if __name__ == "__main__":
    unittest.main()
