#!/usr/bin/env python3
"""Tests for plan-level execution budgets and runner stop admission."""

from __future__ import annotations

import hashlib
import fcntl
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_SCRIPT = ROOT / "scripts/plan-execution-state.py"
RUNNER = ROOT / "scripts/run-sandboxed-plan-worker.py"
SCENARIOS = ROOT / "tests/fixtures/orchestration/plan-restructuring-scenarios.json"
HOLDOUT = ROOT / "tests/fixtures/orchestration/plan-restructuring-holdout.json"


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


class PlanExecutionStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True)
        self.plan = self.repo / "docs/plan/active/001-test.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("status: in_progress\nprimary_invariant: one invariant\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "plan"], cwd=self.repo, check=True)
        self.head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()
        self.state = self.base / "execution.json"
        self.lifecycle = self.base / "candidate-lifecycle.json"
        self.run_cli("init", str(self.state), "--run-id", "run-1", "--plan", "docs/plan/active/001-test.md",
                 "--plan-digest", digest(self.plan.read_text()), "--source-head", self.head,
                 "--primary-invariant-digest", digest("one invariant"), "--lifecycle-state", str(self.lifecycle),
                 "--implementation-mode", "candidate", check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(STATE_SCRIPT), *arguments], cwd=self.repo, check=check,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def record(self, event_id: str, event_type: str, *extra: str, mode: str = "candidate") -> subprocess.CompletedProcess[str]:
        self.lifecycle.write_text(event_id + "\n", encoding="utf-8")
        return self.run_cli(
            "record", str(self.state), "--run-id", "run-1", "--event-id", event_id,
            "--event-type", event_type, "--implementation-mode", mode,
            "--candidate-lifecycle-digest", digest(event_id + "\n"),
            "--lifecycle-state", str(self.lifecycle), *extra,
        )

    def payload(self) -> dict[str, object]:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def write_repair_evidence(
        self,
        event_id: str,
        receipt: str,
        invariant: str,
        **overrides: object,
    ) -> Path:
        state = self.payload()
        value: dict[str, object] = {
            "schema_version": 1,
            "plan_path": state["plan_path"],
            "plan_digest": state["plan_digest"],
            "source_head": state["source_head"],
            "primary_invariant_digest": state["primary_invariant_digest"],
            "affected_invariant_digests": [invariant],
            "candidate_lifecycle_identity_digest": state["candidate_lifecycle_identity_digest"],
            "candidate_lifecycle_digest": digest(event_id + "\n"),
            "independent_review_receipt_digest": receipt,
            "bounded_write_scope": True,
            "bounded_validation_scope": True,
            "source_scope_unchanged": True,
            "validation_authority_unchanged": True,
            "invariant_boundaries_unchanged": True,
            "source_acceptance_unchanged": True,
            "safety_conditions_unchanged": True,
            "external_effect_authority_unchanged": True,
            "independent_invariant_count": 1,
        }
        value.update(overrides)
        evidence = self.base / f"{event_id}-repair-evidence.json"
        evidence.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return evidence

    def test_two_rejected_corrections_stop_and_replay_is_rejected(self) -> None:
        self.assertEqual(self.record("generation-1", "candidate_generation").returncode, 0)
        self.assertEqual(self.record("correction-1", "correction_rejected").returncode, 0)
        replay = self.record("correction-1", "correction_rejected")
        self.assertNotEqual(replay.returncode, 0)
        self.assertEqual(self.record("correction-2", "correction_rejected").returncode, 0)
        state = self.payload()
        self.assertEqual(state["state"], "replan_required")
        self.assertEqual(state["candidate_generations"], 3)
        self.assertNotEqual(self.record("generation-4", "candidate_generation").returncode, 0)
        value = self.payload()
        value["state"] = "active"
        value["replan_reason_codes"] = []
        value["correction_rounds"] = 0
        self.state.write_text(json.dumps(value), encoding="utf-8")
        self.assertNotEqual(
            self.run_cli(
                "check", str(self.state), "--run-id", "run-1",
                "--lifecycle-state", str(self.lifecycle),
            ).returncode,
            0,
        )

    def test_parent_direct_budget_requires_independent_receipt(self) -> None:
        invariant = digest("one")
        missing = self.record(
            "parent-1", "parent_review", "--invariant-digest", invariant,
            "--finding-severity", "Medium", mode="parent_direct",
        )
        self.assertNotEqual(missing.returncode, 0)
        for index in (1, 2):
            result = self.record(
                f"parent-{index}", "parent_review", "--invariant-digest", invariant,
                "--finding-severity", "Medium", "--independent-review-receipt-digest",
                digest(f"receipt-{index}"), mode="parent_direct",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.payload()["state"], "replan_required")

    def test_multi_invariant_and_boundary_drift_trigger_immediately(self) -> None:
        result = self.record(
            "review-1", "parent_review", "--invariant-digest", digest("one"),
            "--invariant-digest", digest("two"), "--finding-severity", "Low",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("multiple_independent_invariants", self.payload()["replan_reason_codes"])

    def test_each_boundary_drift_stops_a_fresh_execution_run(self) -> None:
        for index, event_type in enumerate(("scope_drift", "spec_drift", "security_boundary_drift"), start=1):
            with self.subTest(event_type=event_type):
                run_id = f"boundary-{index}"
                state = self.base / f"{run_id}.json"
                lifecycle = self.base / f"{run_id}-lifecycle.json"
                initialized = self.run_cli(
                    "init", str(state), "--run-id", run_id,
                    "--plan", "docs/plan/active/001-test.md",
                    "--plan-digest", digest(self.plan.read_text()),
                    "--source-head", self.head,
                    "--primary-invariant-digest", digest("one invariant"),
                    "--lifecycle-state", str(lifecycle),
                    "--implementation-mode", "candidate",
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                lifecycle.write_text(event_type + "\n", encoding="utf-8")
                recorded = self.run_cli(
                    "record", str(state), "--run-id", run_id,
                    "--event-id", event_type, "--event-type", event_type,
                    "--implementation-mode", "candidate",
                    "--invariant-digest", digest("one invariant"),
                    "--candidate-lifecycle-digest", digest(event_type + "\n"),
                    "--lifecycle-state", str(lifecycle),
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                payload = json.loads(state.read_text(encoding="utf-8"))
                self.assertEqual(payload["state"], "replan_required")
                self.assertEqual(payload["replan_reason_codes"], [event_type])
                denied = self.run_cli(
                    "check", str(state), "--run-id", run_id,
                    "--lifecycle-state", str(lifecycle),
                )
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn("stopped for restructuring", denied.stderr)

    def test_post_authoritative_change_requires_authoritative_event(self) -> None:
        affected = ("--invariant-digest", digest("one invariant"))
        self.assertNotEqual(self.record("design-early", "post_authoritative_design_change", *affected).returncode, 0)
        self.assertEqual(self.record("authoritative-1", "authoritative_validation").returncode, 0)
        self.assertEqual(self.record("design-1", "post_authoritative_design_change", *affected).returncode, 0)
        self.assertEqual(self.payload()["state"], "replan_required")

    def test_independent_repair_requires_bounded_evidence_and_stops_only_current_run(self) -> None:
        invariant_digest = digest("one invariant")
        invariant = ("--invariant-digest", invariant_digest)
        receipt_digest = digest("repair-review")
        receipt = ("--independent-review-receipt-digest", receipt_digest)
        self.assertNotEqual(self.record("repair-missing", "repair_classification", *invariant).returncode, 0)
        coupled_evidence = self.write_repair_evidence(
            "repair-coupled", receipt_digest, invariant_digest,
        )
        self.assertNotEqual(
            self.record(
                "repair-coupled", "repair_classification", *invariant,
                "--invariant-digest", digest("second invariant"), *receipt,
                "--repair-evidence-file", str(coupled_evidence),
            ).returncode,
            0,
        )
        stale_lifecycle = self.write_repair_evidence(
            "repair-stale-lifecycle", receipt_digest, invariant_digest,
        )
        self.lifecycle.write_text("different lifecycle\n", encoding="utf-8")
        stale = self.run_cli(
            "record", str(self.state), "--run-id", "run-1",
            "--event-id", "repair-stale-lifecycle", "--event-type", "repair_classification",
            "--implementation-mode", "candidate", *invariant, *receipt,
            "--candidate-lifecycle-digest", digest("repair-stale-lifecycle\n"),
            "--repair-evidence-file", str(stale_lifecycle),
            "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(stale.returncode, 0)
        evidence = self.write_repair_evidence("repair-1", receipt_digest, invariant_digest)
        accepted = self.record(
            "repair-1", "repair_classification", *invariant, *receipt,
            "--repair-evidence-file", str(evidence),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], "repair_required")
        self.assertEqual(payload["repair_reason_codes"], ["independent_repair_required"])
        self.assertEqual(payload["replan_reason_codes"], [])
        denied = self.run_cli(
            "check", str(self.state), "--run-id", "run-1", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("stopped for an independent repair", denied.stderr)
        self.assertNotEqual(self.record("repair-continued", "elapsed_checkpoint").returncode, 0)

        fresh_state = self.base / "fresh-execution.json"
        fresh_lifecycle = self.base / "fresh-lifecycle.json"
        initialized = self.run_cli(
            "init", str(fresh_state), "--run-id", "run-2",
            "--plan", "docs/plan/active/001-test.md",
            "--plan-digest", digest(self.plan.read_text()), "--source-head", self.head,
            "--primary-invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(fresh_lifecycle), "--implementation-mode", "candidate",
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertEqual(json.loads(fresh_state.read_text(encoding="utf-8"))["state"], "active")

    def test_independent_repair_blocks_runner_before_prerequisites(self) -> None:
        invariant = digest("one invariant")
        receipt = digest("repair-review")
        evidence = self.write_repair_evidence("repair-runner", receipt, invariant)
        accepted = self.record(
            "repair-runner", "repair_classification",
            "--invariant-digest", invariant,
            "--independent-review-receipt-digest", receipt,
            "--repair-evidence-file", str(evidence),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        common = [
            "--orchestration-run-id", "run-1", "--lifecycle-state", str(self.lifecycle),
            "--plan-execution-state", str(self.state),
        ]
        commands = (
            ["run", self.source_path_for_runner(), *common, "--bwrap-bin", "definitely-missing-bwrap"],
            ["correct", self.source_path_for_runner(), "missing-manifest", "missing-brief", *common],
            ["validate", "missing-manifest", "--suite", "focused", "--output-dir", str(self.base / "validation"), *common],
            ["apply", "missing-manifest", *common],
            ["finalize-apply", "missing-manifest", *common],
        )
        for command in commands:
            denied = subprocess.run(
                [sys.executable, str(RUNNER), *command], cwd=self.repo,
                check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("stopped for an independent repair", denied.stderr)
            self.assertNotIn("missing-manifest", denied.stderr)
            self.assertNotIn("definitely-missing-bwrap", denied.stderr)

    def test_altered_authority_rejects_repair_classification_and_uses_hard_replan(self) -> None:
        scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
        scenario = next(
            item for item in scenarios
            if item["id"] == "negative-independent-repair-with-altered-authority"
        )
        invariant = digest("one invariant")
        receipt = digest("repair-review")
        evidence = self.write_repair_evidence(
            "repair-altered-authority", receipt, invariant,
            external_effect_authority_unchanged=False,
        )
        classified = self.record(
            "repair-altered-authority", "repair_classification",
            "--invariant-digest", invariant,
            "--independent-review-receipt-digest", receipt,
            "--repair-evidence-file", str(evidence),
        )
        self.assertEqual(classified.returncode, 0, classified.stderr)
        self.assertEqual(self.payload()["state"], scenario["expected"]["state"])
        self.assertIn(scenario["expected"]["reason_code"], self.payload()["replan_reason_codes"])

    def test_changed_plan_boundaries_atomically_select_hard_replan(self) -> None:
        cases = (
            ("source-scope", "source_scope_unchanged", "scope_drift"),
            ("validation-authority", "validation_authority_unchanged", "spec_drift"),
            ("invariant-boundaries", "invariant_boundaries_unchanged", "multiple_independent_invariants"),
        )
        for index, (label, predicate, reason) in enumerate(cases, start=1):
            with self.subTest(predicate=predicate):
                run_id = f"changed-boundary-{index}"
                state_path = self.base / f"{run_id}.json"
                lifecycle_path = self.base / f"{run_id}-lifecycle.json"
                initialized = self.run_cli(
                    "init", str(state_path), "--run-id", run_id,
                    "--plan", "docs/plan/active/001-test.md",
                    "--plan-digest", digest(self.plan.read_text()),
                    "--source-head", self.head,
                    "--primary-invariant-digest", digest("one invariant"),
                    "--lifecycle-state", str(lifecycle_path),
                    "--implementation-mode", "candidate",
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                event_id = f"repair-{label}"
                invariant = digest("one invariant")
                receipt = digest(f"review-{label}")
                lifecycle_path.write_text(event_id + "\n", encoding="utf-8")
                original_state = self.state
                self.state = state_path
                try:
                    evidence = self.write_repair_evidence(
                        event_id, receipt, invariant, **{predicate: False},
                    )
                finally:
                    self.state = original_state
                classified = self.run_cli(
                    "record", str(state_path), "--run-id", run_id,
                    "--event-id", event_id, "--event-type", "repair_classification",
                    "--implementation-mode", "candidate",
                    "--invariant-digest", invariant,
                    "--independent-review-receipt-digest", receipt,
                    "--candidate-lifecycle-digest", digest(event_id + "\n"),
                    "--repair-evidence-file", str(evidence),
                    "--lifecycle-state", str(lifecycle_path),
                )
                self.assertEqual(classified.returncode, 0, classified.stderr)
                payload = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["state"], "replan_required")
                self.assertEqual(payload["replan_reason_codes"], [reason])
                self.assertEqual(payload["repair_reason_codes"], [])

    def test_recomputed_history_after_terminal_repair_event_is_rejected(self) -> None:
        invariant = digest("one invariant")
        receipt = digest("repair-review")
        evidence = self.write_repair_evidence("repair-terminal", receipt, invariant)
        accepted = self.record(
            "repair-terminal", "repair_classification",
            "--invariant-digest", invariant,
            "--independent-review-receipt-digest", receipt,
            "--repair-evidence-file", str(evidence),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        value = self.payload()
        event: dict[str, object] = {
            "sequence": 2,
            "event_id": "forged-after-terminal",
            "event_type": "elapsed_checkpoint",
            "implementation_mode": "candidate",
            "invariant_digests": [],
            "finding_severities": [],
            "independent_review_receipt_digest": "",
            "repair_classification": {},
            "repair_evidence_digest": "",
            "candidate_lifecycle_digest": "",
            "elapsed_seconds": 1.0,
            "monotonic_ns": int(value["last_monotonic_ns"]) + 1,
            "previous_event_digest": value["event_chain_digest"],
        }
        event["event_digest"] = digest(json.dumps(event, sort_keys=True, separators=(",", ":")))
        value["events"].append(event)  # type: ignore[union-attr]
        value["last_monotonic_ns"] = event["monotonic_ns"]
        value["event_chain_digest"] = event["event_digest"]
        self.state.write_text(json.dumps(value), encoding="utf-8")
        denied = self.run_cli("check", str(self.state), "--run-id", "run-1")
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("continues after a terminal execution state", denied.stderr)

    def test_recomputed_repair_evidence_digest_tamper_is_rejected(self) -> None:
        invariant = digest("one invariant")
        receipt = digest("repair-review")
        evidence = self.write_repair_evidence("repair-digest", receipt, invariant)
        accepted = self.record(
            "repair-digest", "repair_classification",
            "--invariant-digest", invariant,
            "--independent-review-receipt-digest", receipt,
            "--repair-evidence-file", str(evidence),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        value = self.payload()
        event = value["events"][0]  # type: ignore[index]
        event["repair_evidence_digest"] = digest("different evidence")
        unsigned = {key: event[key] for key in event if key != "event_digest"}
        event["event_digest"] = digest(json.dumps(unsigned, sort_keys=True, separators=(",", ":")))
        value["event_chain_digest"] = event["event_digest"]
        self.state.write_text(json.dumps(value), encoding="utf-8")
        denied = self.run_cli("check", str(self.state), "--run-id", "run-1")
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("does not match embedded classification", denied.stderr)

    def test_plan119_scenario_and_fresh_run_holdout_keep_distinct_outcomes(self) -> None:
        scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
        plan119 = next(
            scenario for scenario in scenarios
            if scenario["id"] == "median-plan119-independent-validation-authorization-repair"
        )
        self.assertEqual(plan119["input"]["affected_invariant_count"], 1)
        self.assertIs(plan119["input"]["bounded_write_and_validation_scope"], True)
        self.assertIs(plan119["input"]["source_acceptance_changed"], False)
        self.assertIs(plan119["input"]["safety_boundary_changed"], False)
        self.assertIs(plan119["input"]["external_authority_changed"], False)
        self.assertEqual(plan119["expected"]["state"], "repair_required")
        self.assertEqual(plan119["expected"]["next_action"], "defer_source_and_create_bounded_repair_plan")

        holdouts = json.loads(HOLDOUT.read_text(encoding="utf-8"))["scenarios"]
        fresh_run = next(
            scenario for scenario in holdouts
            if scenario["id"] == "holdout-independent-repair-rejects-stopped-run-reuse"
        )
        self.assertIs(fresh_run["used_for_tuning"], False)
        self.assertEqual(fresh_run["input"]["execution_run"], "stopped_repair_required_run")
        self.assertEqual(fresh_run["expected"]["state"], "repair_required")
        self.assertEqual(
            fresh_run["expected"]["next_action"],
            "reject_transition_and_initialize_fresh_run",
        )

    def test_elapsed_checkpoint_is_telemetry_only_and_tampering_fails(self) -> None:
        self.assertEqual(self.record("elapsed-1", "elapsed_checkpoint", "--elapsed-seconds", "999999").returncode, 0)
        self.assertEqual(self.payload()["state"], "active")
        value = self.payload()
        value["candidate_generations"] = -1
        self.state.write_text(json.dumps(value), encoding="utf-8")
        self.assertNotEqual(self.run_cli("check", str(self.state), "--run-id", "run-1").returncode, 0)

    def test_hash_chain_and_lifecycle_content_detect_valid_shape_rewrites(self) -> None:
        self.assertEqual(self.record("generation-1", "candidate_generation").returncode, 0)
        self.lifecycle.write_text("different lifecycle\n", encoding="utf-8")
        self.assertNotEqual(
            self.run_cli(
                "check", str(self.state), "--run-id", "run-1",
                "--lifecycle-state", str(self.lifecycle),
            ).returncode,
            0,
        )
        value = self.payload()
        value["events"][0]["elapsed_seconds"] = 1.0  # type: ignore[index]
        self.state.write_text(json.dumps(value), encoding="utf-8")
        self.assertNotEqual(self.run_cli("check", str(self.state), "--run-id", "run-1").returncode, 0)

    def test_hard_trigger_waits_for_an_active_shared_lease(self) -> None:
        lock_path = self.state.with_name(self.state.name + ".lock")
        with lock_path.open("rb") as lease:
            fcntl.flock(lease.fileno(), fcntl.LOCK_SH)
            self.lifecycle.write_text("scope-lease\n", encoding="utf-8")
            process = subprocess.Popen(
                [
                    sys.executable, str(STATE_SCRIPT), "record", str(self.state),
                    "--run-id", "run-1", "--event-id", "scope-lease",
                    "--event-type", "scope_drift", "--implementation-mode", "candidate",
                    "--invariant-digest", digest("one invariant"),
                    "--candidate-lifecycle-digest", digest("scope-lease\n"),
                    "--lifecycle-state", str(self.lifecycle),
                ], cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            time.sleep(0.1)
            self.assertIsNone(process.poll())
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, (stdout, stderr))
        self.assertEqual(self.payload()["state"], "replan_required")

    def test_runner_gate_rejects_before_worker_prerequisites(self) -> None:
        self.assertEqual(
            self.record("scope-1", "scope_drift", "--invariant-digest", digest("one invariant")).returncode,
            0,
        )
        result = subprocess.run(
            [
                sys.executable, str(RUNNER), "run", "docs/plan/active/001-test.md",
                "--orchestration-run-id", "run-1", "--lifecycle-state", str(self.lifecycle),
                "--plan-execution-state", str(self.state), "--bwrap-bin", "definitely-missing-bwrap",
            ],
            cwd=self.repo, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stopped for restructuring", result.stderr)
        self.assertNotIn("definitely-missing-bwrap", result.stderr)

    def test_runner_rejects_omitted_execution_state(self) -> None:
        result = subprocess.run(
            [
                sys.executable, str(RUNNER), "run", "docs/plan/active/001-test.md",
                "--orchestration-run-id", "run-1", "--lifecycle-state", str(self.lifecycle),
            ], cwd=self.repo, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--plan-execution-state", result.stderr)

    def test_fixed_hard_trigger_scenarios_block_every_runner_operation(self) -> None:
        fixture = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        hard_scenarios = [
            scenario for scenario in fixture["scenarios"]
            if scenario["expected"]["next_action"] == "atomic_restructure"
        ]
        self.assertEqual(len(hard_scenarios), 7)
        for index, scenario in enumerate(hard_scenarios, start=1):
            with self.subTest(scenario=scenario["id"]):
                run_id = f"scenario-{index}"
                state = self.base / f"{run_id}.json"
                lifecycle = self.base / f"{run_id}-lifecycle.json"
                initialized = self.run_cli(
                    "init", str(state), "--run-id", run_id,
                    "--plan", "docs/plan/active/001-test.md",
                    "--plan-digest", digest(self.plan.read_text()),
                    "--source-head", self.head,
                    "--primary-invariant-digest", digest("one invariant"),
                    "--lifecycle-state", str(lifecycle),
                    "--implementation-mode", "candidate",
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)

                event_number = 0

                def record_event(event_type: str, *extra: str, mode: str = "candidate") -> None:
                    nonlocal event_number
                    event_number += 1
                    event_id = f"{scenario['id']}-{event_number}"
                    lifecycle.write_text(event_id + "\n", encoding="utf-8")
                    result = self.run_cli(
                        "record", str(state), "--run-id", run_id,
                        "--event-id", event_id, "--event-type", event_type,
                        "--implementation-mode", mode,
                        "--candidate-lifecycle-digest", digest(event_id + "\n"),
                        "--lifecycle-state", str(lifecycle), *extra,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

                reason = scenario["expected"]["reason_code"]
                invariant = ("--invariant-digest", digest("one invariant"))
                if reason == "multiple_independent_invariants":
                    record_event(
                        "parent_review", *invariant,
                        "--invariant-digest", digest("second invariant"),
                        "--finding-severity", "Low",
                    )
                elif reason == "candidate_correction_budget_exhausted":
                    record_event("candidate_generation")
                    record_event("correction_rejected")
                    record_event("correction_rejected")
                elif reason == "parent_remediation_budget_exhausted":
                    for round_number in (1, 2):
                        record_event(
                            "parent_review", *invariant,
                            "--finding-severity", "Medium",
                            "--independent-review-receipt-digest", digest(f"receipt-{round_number}"),
                            mode="parent_direct",
                        )
                elif reason == "post_authoritative_design_change":
                    record_event("authoritative_validation")
                    record_event("post_authoritative_design_change", *invariant)
                else:
                    record_event(reason, *invariant)

                payload = json.loads(state.read_text(encoding="utf-8"))
                self.assertEqual(payload["state"], "replan_required")
                self.assertIn(reason, payload["replan_reason_codes"])
                common = [
                    "--orchestration-run-id", run_id,
                    "--lifecycle-state", str(lifecycle),
                    "--plan-execution-state", str(state),
                ]
                commands = (
                    ["run", self.source_path_for_runner(), *common],
                    ["correct", self.source_path_for_runner(), "missing-manifest", "missing-brief", *common],
                    ["validate", "missing-manifest", "--suite", "focused", "--output-dir", str(self.base / "validation"), *common],
                    ["apply", "missing-manifest", *common],
                    ["finalize-apply", "missing-manifest", *common],
                )
                for command in commands:
                    denied = subprocess.run(
                        [sys.executable, str(RUNNER), *command], cwd=self.repo,
                        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    self.assertNotEqual(denied.returncode, 0)
                    self.assertIn("stopped for restructuring", denied.stderr)
                    self.assertNotIn("missing-manifest", denied.stderr)

    def test_untuned_holdout_security_drift_stops_the_runner(self) -> None:
        scenario = json.loads(HOLDOUT.read_text(encoding="utf-8"))["scenarios"][0]
        self.assertIs(scenario["used_for_tuning"], False)
        self.assertEqual(scenario["input"]["event"], "security_boundary_drift")
        event_id = scenario["id"]
        self.lifecycle.write_text(event_id + "\n", encoding="utf-8")
        recorded = self.run_cli(
            "record", str(self.state), "--run-id", "run-1",
            "--event-id", event_id, "--event-type", scenario["input"]["event"],
            "--implementation-mode", "candidate",
            "--invariant-digest", digest("one invariant"),
            "--candidate-lifecycle-digest", digest(event_id + "\n"),
            "--lifecycle-state", str(self.lifecycle),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], scenario["expected"]["state"])
        self.assertIn(scenario["expected"]["reason_code"], payload["replan_reason_codes"])
        denied = subprocess.run(
            [
                sys.executable, str(RUNNER), "run", self.source_path_for_runner(),
                "--orchestration-run-id", "run-1", "--lifecycle-state", str(self.lifecycle),
                "--plan-execution-state", str(self.state),
            ],
            cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("stopped for restructuring", denied.stderr)

    def source_path_for_runner(self) -> str:
        return self.plan.relative_to(self.repo).as_posix()


if __name__ == "__main__":
    unittest.main()
