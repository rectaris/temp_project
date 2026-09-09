#!/usr/bin/env python3
"""Behavior tests for the referent-first contract lifecycle."""

from __future__ import annotations

import json
import os
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

    def registered_draft(self, cwd: Path, mode: str = "advisory", source: str = "source.md") -> Path:
        contract = self.init_contract(cwd, mode=mode)
        value = json.loads(contract.read_text())
        value["source"]["path"] = source
        contract.write_text(json.dumps(value))
        self.run_cli(cwd, "review-unknowns", str(contract), "--none")
        self.add_referent(cwd, contract, "R1", "the configured history amount", "value")
        self.run_cli(cwd, "seal-referents", str(contract))
        self.run_cli(cwd, "use-concrete-text", str(contract), "--id", "R1", "--reason", "Use the concrete description")
        self.run_cli(cwd, "finalize-labels", str(contract))
        (cwd / "draft.md").write_text("the configured history amount\n")
        self.run_cli(cwd, "record-draft", str(contract))
        destination = cwd / ".agent-artifacts/referent-contracts/sample/contract.json"
        destination.parent.mkdir(parents=True)
        contract.rename(destination)
        return destination

    def end_evidence(self, cwd: Path) -> str:
        path = cwd / ".agent-artifacts/end-evidence.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "target_history": "The old draft disappeared after its implementation plan was archived.",
            "applicability_ended_reason": "This evaluation concerned the superseded draft, not the checked plan.",
            "unresolved_facts": "The original uncommitted draft cannot be recovered; its acceptance is unknown.",
            "owner_instruction": "Resolve the obsolete evaluation records with preserved evidence.",
        }))
        return str(path.relative_to(cwd))

    def test_reopen_retains_relocated_draft_history_and_current_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd)
            (cwd / "draft.md").rename(cwd / "archive.md")
            self.run_cli(cwd, "relocate-target", str(contract), "--target", "archive.md", "--reason", "Moved unchanged")
            before = json.loads(contract.read_text())
            (cwd / "archive.md").write_text("the configured history amount, with revised context\n")
            self.run_cli(cwd, "reopen", str(contract), "--reason", "Review the revised context")
            self.assertIn("Definition work pending", self.run_cli(cwd, "pending", "--target", "archive.md").stdout)
            self.run_cli(cwd, "seal-referents", str(contract))
            self.run_cli(cwd, "use-concrete-text", str(contract), "--id", "R1", "--reason", "Keep the concrete description")
            self.run_cli(cwd, "finalize-labels", str(contract))
            self.run_cli(cwd, "record-draft", str(contract))
            self.run_cli(cwd, "check", str(contract))
            value = json.loads(contract.read_text())
            self.assertEqual(value["draft_history"], [{
                "target_sha256": before["target_sha256"], "target_relocations": before["target_relocations"],
            }])
            self.assertNotEqual(value["target_sha256"], before["target_sha256"])
            self.assertEqual(value["target"], before["target"])
            self.assertFalse((cwd / "draft.md").exists())
            self.assertIn("Closure pending", self.run_cli(cwd, "pending", "--target", "archive.md").stdout)

    def test_ended_evidence_requires_all_fields_and_local_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd)
            report = self.end_evidence(cwd)
            evidence = json.loads((cwd / report).read_text())
            before = contract.read_bytes()
            for field in evidence:
                for missing in (True, False):
                    invalid = dict(evidence)
                    if missing:
                        del invalid[field]
                    else:
                        invalid[field] = " "
                    (cwd / report).write_text(json.dumps(invalid))
                    self.run_cli(cwd, "end-applicability", str(contract), "--reason", "Obsolete", "--report", report, expected=1)
                    self.assertEqual(contract.read_bytes(), before)
            (cwd / report).write_text(json.dumps(evidence))
            (cwd / "outside.json").write_text(json.dumps(evidence))
            (cwd / ".agent-artifacts/linked.json").symlink_to(cwd / "outside.json")
            for invalid in ("outside.json", str(cwd / report), ".agent-artifacts/../outside.json", ".agent-artifacts/linked.json"):
                self.run_cli(cwd, "end-applicability", str(contract), "--reason", "Obsolete", "--report", invalid, expected=1)
                self.assertEqual(contract.read_bytes(), before)

    def test_relocation_preserves_seal_and_requires_identical_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd)
            original = json.loads(contract.read_text())
            (cwd / "draft.md").rename(cwd / "archive.md")
            before = contract.read_bytes()
            (cwd / "wrong.md").write_text("changed target")
            self.run_cli(cwd, "relocate-target", str(contract), "--target", "wrong.md", "--reason", "Moved", expected=1)
            self.assertEqual(before, contract.read_bytes())
            self.run_cli(cwd, "relocate-target", str(contract), "--target", "archive.md", "--reason", "Draft archived unchanged")
            self.run_cli(cwd, "check", str(contract))
            value = json.loads(contract.read_text())
            for field in ("referent_snapshot_sha256", "target", "target_sha256", "transitions"):
                self.assertEqual(original[field], value[field])
            self.run_cli(cwd, "close-advisory", str(contract), "--reason", "Evaluation completed")
            self.run_cli(cwd, "check", str(contract))
            self.assertEqual(self.run_cli(cwd, "pending").stdout, "")

    def test_snapshot_before_lifecycle_edit_and_relocation_history_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd)
            (cwd / "snapshot.md").write_bytes((cwd / "draft.md").read_bytes())
            self.run_cli(cwd, "relocate-target", str(contract), "--target", "snapshot.md", "--reason", "Preserve evaluation before plan status changes")
            (cwd / "draft.md").write_text("later lifecycle content")
            self.run_cli(cwd, "check", str(contract))
            value = json.loads(contract.read_text())
            value["target_relocations"][0]["from"] = "unrelated.md"
            contract.write_text(json.dumps(value))
            self.assertIn("location history", self.run_cli(cwd, "check", str(contract), expected=1).stderr)

    def test_relocation_cannot_hide_existing_drift_or_satisfy_required_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd, "required")
            (cwd / "snapshot.md").write_bytes((cwd / "draft.md").read_bytes())
            (cwd / "draft.md").write_text("changed")
            before = contract.read_bytes()
            self.run_cli(cwd, "relocate-target", str(contract), "--target", "snapshot.md", "--reason", "Hide change", expected=1)
            self.assertEqual(contract.read_bytes(), before)
            (cwd / "draft.md").unlink()
            self.run_cli(cwd, "relocate-target", str(contract), "--target", "snapshot.md", "--reason", "Recover exact original draft")
            self.assertIn("required contract", self.run_cli(cwd, "check", str(contract), expected=1).stderr)

    def test_relocation_rejects_nonregular_previous_targets_without_writes(self) -> None:
        for replacement in ("directory", "broken_symlink", "file_symlink", "fifo"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                contract = self.registered_draft(cwd)
                old = cwd / "draft.md"
                snapshot = cwd / "snapshot.md"
                old.rename(snapshot)
                if replacement == "directory":
                    old.mkdir()
                elif replacement == "broken_symlink":
                    old.symlink_to(cwd / "missing.md")
                elif replacement == "file_symlink":
                    old.symlink_to(snapshot)
                else:
                    os.mkfifo(old)
                before_contract, before_snapshot = contract.read_bytes(), snapshot.read_bytes()
                self.assertIn("Target is not a regular file", self.run_cli(cwd, "pending", "--target", "draft.md").stdout)
                result = subprocess.run([
                    "python3", str(CLI), "relocate-target", str(contract),
                    "--target", "snapshot.md", "--reason", "Preserve the original draft",
                ], cwd=cwd, text=True, capture_output=True, timeout=5, check=False)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("not a regular file", result.stderr)
                self.assertEqual(contract.read_bytes(), before_contract)
                self.assertEqual(snapshot.read_bytes(), before_snapshot)
                self.assertTrue(old.exists() or old.is_symlink())

    def test_ended_applicability_preserves_prior_evidence_without_acceptance(self) -> None:
        for mode in ("advisory", "required"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                contract = self.registered_draft(cwd, mode)
                before = json.loads(contract.read_text())
                (cwd / "draft.md").unlink()
                report = self.end_evidence(cwd)
                self.run_cli(cwd, "end-applicability", str(contract), "--reason", "Obsolete evaluation", "--report", report)
                value = json.loads(contract.read_text())
                self.assertEqual(value["end_record"]["prior_contract"], before)
                self.assertFalse(value["active"])
                self.assertEqual(value["reviews"], [])
                for args in ((), ("--require-review",)):
                    result = self.run_cli(cwd, "check", str(contract), *args, expected=1)
                    self.assertIn("without semantic acceptance", result.stderr)
                self.assertEqual(self.run_cli(cwd, "pending").stdout, "")
                self.run_cli(cwd, "reopen", str(contract), "--reason", "Try acceptance", expected=1)
                self.run_cli(cwd, "close-advisory", str(contract), "--reason", "Try acceptance", expected=1)
                evidence = json.loads((cwd / report).read_text())
                evidence["unresolved_facts"] = "Changed evidence"
                (cwd / report).write_text(json.dumps(evidence))
                self.assertIn("evidence is missing or changed", self.run_cli(cwd, "check", str(contract), expected=1).stderr)
                self.assertIn("invalid", self.run_cli(cwd, "pending").stdout)

    def test_end_applicability_rejects_missing_reason_report_and_prior_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd)
            report = self.end_evidence(cwd)
            before = contract.read_bytes()
            for reason, invalid_report in ((" ", report), ("Obsolete", "missing.md"), ("Obsolete", str(contract))):
                self.run_cli(cwd, "end-applicability", str(contract), "--reason", reason, "--report", invalid_report, expected=1)
                self.assertEqual(contract.read_bytes(), before)
            self.run_cli(cwd, "end-applicability", str(contract), "--reason", "Obsolete", "--report", report)
            value = json.loads(contract.read_text())
            value["target_sha256"] = "0" * 64
            contract.write_text(json.dumps(value))
            self.assertIn("preserve the complete prior", self.run_cli(cwd, "check", str(contract), expected=1).stderr)

    def test_pending_is_read_only_filters_exact_references_and_reports_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            contract = self.registered_draft(cwd)
            original = contract.read_bytes()
            self.assertIn("Closure pending", self.run_cli(cwd, "pending", "--target", "source.md").stdout)
            self.assertEqual(self.run_cli(cwd, "pending", "--target", "unrelated.md").stdout, "")
            (cwd / "draft.md").write_text("changed")
            self.assertIn("Draft changed", self.run_cli(cwd, "pending").stdout)
            (cwd / "draft.md").unlink()
            self.assertIn("Target missing", self.run_cli(cwd, "pending").stdout)
            self.assertEqual(contract.read_bytes(), original)
            value = json.loads(original)
            value["active"] = False
            contract.write_text(json.dumps(value))
            self.assertIn("invalid", self.run_cli(cwd, "pending").stdout)

    def test_plan_completion_and_archival_report_related_records_without_closing_them(self) -> None:
        from validation_tools import plan as fixtures
        helper = fixtures.PlanValidationCommandsTest()
        for variant in helper.COMPLETION_GATE_VARIANTS:
            with self.subTest(variant=variant["install"]), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                helper.build_completion_repo(cwd, variant)
                install = cwd / str(variant["install"])
                for name in ("referent-contract.py", "finalize-active-plan.sh"):
                    (install / name).write_bytes((ROOT / str(variant["source"]) / name).read_bytes())
                (cwd / "docs/plan/checked.md").write_text("# Checked Plan\n\nid\tpath\n")
                contract = self.registered_draft(cwd, source=helper.COMPLETION_PLAN)
                before = contract.read_bytes()
                hook = ROOT / ".project-agent-workflow/hooks/semantic_guard_advisory.py"
                output = subprocess.run(["python3", str(hook)], input="{}", cwd=cwd,
                                        text=True, capture_output=True, check=True)
                message = json.loads(output.stdout)
                self.assertTrue(message["continue"])
                self.assertIn("Closure pending", message["systemMessage"])
                self.assertEqual(contract.read_bytes(), before)
                for name in ("complete-plan.sh", "finalize-active-plan.sh"):
                    result = helper.run_in_repo(cwd, str(install / name), helper.COMPLETION_PLAN)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Closure pending", result.stderr)
                    self.assertEqual(contract.read_bytes(), before)
                self.assertFalse((cwd / helper.COMPLETION_PLAN).exists())
                self.assertEqual(len(list((cwd / "docs/plan/checked").glob("**/900-*.md"))), 1)

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
