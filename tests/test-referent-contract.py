#!/usr/bin/env python3
"""Behavior tests for the referent-first contract lifecycle."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/referent-contract.py"
TEMPLATE_CLI = ROOT / "template/.project-agent-workflow/scripts/referent-contract.py"
SCENARIOS = ROOT / "tests/fixtures/referent-contract/scenarios.json"


class ReferentContractTest(unittest.TestCase):
    def run_cli(self, cwd: Path, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["python3", str(CLI), *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        return result

    def init_contract(self, cwd: Path, *, mode: str = "advisory") -> Path:
        contract = cwd / "contract.json"
        self.run_cli(
            cwd,
            "init",
            str(contract),
            "--slug",
            "compaction-semantics",
            "--task-kind",
            "state-design",
            "--source",
            "source.md",
            "--target",
            "draft.md",
            "--mode",
            mode,
        )
        return contract

    def add_referent(
        self,
        cwd: Path,
        contract: Path,
        referent_id: str,
        concrete_target: str,
        kind: str,
        certainty: str = "confirmed",
    ) -> None:
        self.run_cli(
            cwd,
            "add-referent",
            str(contract),
            "--id",
            referent_id,
            "--purpose",
            "Keep semantic roles distinct",
            "--concrete-target",
            concrete_target,
            "--kind",
            kind,
            "--reasoning-role",
            "evidence",
            "--relation",
            "threshold comparison precedes start event",
            "--evidence",
            "source paragraph 1",
            "--certainty",
            certainty,
        )

    def test_required_contract_completes_full_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.init_contract(cwd, mode="required")
            self.run_cli(cwd, "review-unknowns", str(contract), "--none")
            self.add_referent(cwd, contract, "R1", "the configured history amount", "value")
            self.add_referent(cwd, contract, "R2", "automatic summarization begins", "event")
            self.run_cli(cwd, "seal-referents", str(contract))
            self.run_cli(
                cwd,
                "assign-label",
                str(contract),
                "--id",
                "R1",
                "--label",
                "Compaction threshold",
                "--definition",
                "Compaction threshold means the configured history amount.",
            )
            self.run_cli(
                cwd,
                "assign-label",
                str(contract),
                "--id",
                "R2",
                "--label",
                "Compaction start event",
                "--definition",
                "Compaction start event means automatic summarization begins.",
            )
            self.run_cli(cwd, "finalize-labels", str(contract))
            (cwd / "draft.md").write_text(
                "Compaction threshold means the configured history amount.\n\n"
                "Compaction start event means automatic summarization begins.\n",
                encoding="utf-8",
            )
            self.run_cli(cwd, "record-draft", str(contract))
            self.run_cli(cwd, "check", str(contract), expected=1)
            diff = self.run_cli(cwd, "semantic-diff", str(contract)).stdout
            self.assertIn("| current | R1 | the configured history amount | value |", diff)
            (cwd / "review.md").write_text("Independent comparison passed.\n", encoding="utf-8")
            self.run_cli(
                cwd,
                "record-review",
                str(contract),
                "--report",
                "review.md",
                "--status",
                "passed",
                "--reviewer",
                "independent-agent",
            )
            self.run_cli(cwd, "check", str(contract), "--require-review")
            value = json.loads(contract.read_text(encoding="utf-8"))
            self.assertEqual(value["state"], "semantic_review_passed")
            self.assertFalse(value["active"])

    def test_rejects_label_before_referents_are_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.init_contract(cwd)
            self.run_cli(cwd, "review-unknowns", str(contract), "--none")
            self.add_referent(cwd, contract, "R1", "the configured history amount", "value")
            result = self.run_cli(
                cwd,
                "assign-label",
                str(contract),
                "--id",
                "R1",
                "--label",
                "Compaction threshold",
                "--definition",
                "Compaction threshold means the configured history amount.",
                expected=1,
            )
            self.assertIn("referents_sealed", result.stderr)

    def test_preserves_unknown_and_blocks_its_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.init_contract(cwd)
            self.run_cli(
                cwd,
                "add-unknown",
                str(contract),
                "--id",
                "U1",
                "--description",
                "The failing component is not known",
                "--evidence-needed",
                "Run the isolation test",
            )
            self.run_cli(cwd, "review-unknowns", str(contract))
            self.add_referent(cwd, contract, "R1", "the failing component", "entity", certainty="unknown")
            self.run_cli(cwd, "seal-referents", str(contract))
            result = self.run_cli(
                cwd,
                "assign-label",
                str(contract),
                "--id",
                "R1",
                "--label",
                "Root component",
                "--definition",
                "Root component means the failing component.",
                expected=1,
            )
            self.assertIn("cannot be named", result.stderr)
            self.run_cli(cwd, "finalize-labels", str(contract))
            (cwd / "draft.md").write_text("The failing component is not known.\n", encoding="utf-8")
            self.run_cli(cwd, "record-draft", str(contract))
            self.run_cli(cwd, "close-advisory", str(contract), "--reason", "Independent review deferred")
            self.run_cli(cwd, "check", str(contract))

    def test_rejects_one_label_for_two_referents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.init_contract(cwd)
            self.run_cli(cwd, "review-unknowns", str(contract), "--none")
            self.add_referent(cwd, contract, "R1", "the configured history amount", "value")
            self.add_referent(cwd, contract, "R2", "automatic summarization begins", "event")
            self.run_cli(cwd, "seal-referents", str(contract))
            for referent_id, definition, expected in (
                ("R1", "Compression point means the configured history amount.", 0),
                ("R2", "Compression point means automatic summarization begins.", 1),
            ):
                result = self.run_cli(
                    cwd,
                    "assign-label",
                    str(contract),
                    "--id",
                    referent_id,
                    "--label",
                    "Compression point",
                    "--definition",
                    definition,
                    expected=expected,
                )
            self.assertIn("maps to both R1 and R2", result.stderr)

    def test_detects_changes_to_sealed_referents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.init_contract(cwd)
            self.run_cli(cwd, "review-unknowns", str(contract), "--none")
            self.add_referent(cwd, contract, "R1", "the configured history amount", "value")
            self.run_cli(cwd, "seal-referents", str(contract))
            value = json.loads(contract.read_text(encoding="utf-8"))
            value["referents"][0]["concrete_target"] = "a different target"
            contract.write_text(json.dumps(value), encoding="utf-8")
            result = self.run_cli(cwd, "semantic-diff", str(contract), expected=1)
            self.assertIn("projection hash", result.stderr)

    def test_detects_tampered_transition_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.init_contract(cwd)
            value = json.loads(contract.read_text(encoding="utf-8"))
            value["state"] = "labels_assigned"
            contract.write_text(json.dumps(value), encoding="utf-8")
            result = self.run_cli(cwd, "semantic-diff", str(contract), expected=1)
            self.assertIn("final transition", result.stderr)

    def test_root_and_template_cli_remain_identical(self) -> None:
        template_text = TEMPLATE_CLI.read_text(encoding="utf-8").replace(".project-agent-workflow/", "")
        self.assertEqual(CLI.read_text(encoding="utf-8"), template_text)

    def test_evaluation_matrix_has_fixed_scenario_classes_and_critical_requirements(self) -> None:
        value = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        scenarios = value["scenarios"]
        self.assertEqual({scenario["class"] for scenario in scenarios}, {"median", "edge", "negative", "holdout"})
        self.assertEqual(len({scenario["id"] for scenario in scenarios}), len(scenarios))
        for scenario in scenarios:
            self.assertTrue(any(requirement["critical"] for requirement in scenario["requirements"]))
        skill_text = (ROOT / ".codex/skills/define-referents-first/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("holdout-retry-point", skill_text)
        self.assertIn("without candidate labels or controlled terms", skill_text)
        self.assertIn("keep the settled referent separate", skill_text)
        self.assertIn("Classify a referent by its role in the source", skill_text)
        self.assertIn("For a threshold", skill_text)
        self.assertIn("Preserve source specificity", skill_text)
        self.assertIn("Run a source-fidelity pass", skill_text)
        self.assertIn("For a sequence summary", skill_text)
        self.assertIn("changes the sealed semantic kind", skill_text)
        self.assertIn("Do not add an artifact-order disclaimer", skill_text)
        self.assertNotIn("state that artifact-order validation is unavailable", skill_text)


if __name__ == "__main__":
    unittest.main()
