"""Semantic-guard advisory Hook tests."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from .support import SEMANTIC_GUARD, run_hook


class SemanticGuardAdvisoryTest(unittest.TestCase):
    def test_allows_repository_without_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "Stop"}, cwd=repo)
        self.assertEqual(output, {})

    def test_reports_active_contract_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            contract = repo / ".agent-artifacts/referent-contracts/sample/contract.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps({"active": True, "state": "referents_sealed", "mode": "advisory"}) + "\n",
                encoding="utf-8",
            )
            output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "PostCompact"}, cwd=repo)
        self.assertTrue(output["continue"])
        self.assertIn("referents_sealed", output["systemMessage"])
        self.assertIn("scripts/referent-contract.py check", output["systemMessage"])

    def test_ignores_closed_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            contract = repo / ".agent-artifacts/referent-contracts/sample/contract.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps({"active": False, "state": "closed_advisory", "mode": "advisory"}) + "\n",
                encoding="utf-8",
            )
            output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "Stop"}, cwd=repo)
        self.assertEqual(output, {})

    def test_installed_checker_reports_actionable_diagnostics_without_writing(self) -> None:
        from .support import ROOT
        for install in ("scripts", ".project-agent-workflow/scripts"):
            with self.subTest(install=install), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                checker = repo / install / "referent-contract.py"
                checker.parent.mkdir(parents=True)
                checker.write_bytes((ROOT / "scripts/referent-contract.py").read_bytes())
                contract = repo / ".agent-artifacts/referent-contracts/sample/contract.json"
                subprocess.run([
                    "python3", str(checker), "init", str(contract), "--slug", "sample",
                    "--source", "source.md", "--target", "missing.md",
                    "--task-kind", "naming", "--mode", "required",
                ], cwd=repo, check=True, stdout=subprocess.DEVNULL)
                before = contract.read_bytes()
                output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "Stop"}, cwd=repo)
                self.assertTrue(output["continue"])
                self.assertIn("Target missing", output["systemMessage"])
                self.assertIn("relocate-target", output["systemMessage"])
                self.assertIn(str(checker), output["systemMessage"])
                self.assertEqual(contract.read_bytes(), before)

    def test_allows_when_stop_hook_already_active(self) -> None:
        output = run_hook(SEMANTIC_GUARD, {"stop_hook_active": True})
        self.assertEqual(output, {})



if __name__ == "__main__":
    unittest.main()
