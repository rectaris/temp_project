#!/usr/bin/env python3
"""Tests for plan-level execution budgets and runner stop admission."""

from __future__ import annotations

import hashlib
import fcntl
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_SCRIPT = ROOT / "scripts/plan-execution-state.py"
RUNNER = ROOT / "scripts/run-sandboxed-plan-worker.py"
SCENARIOS = ROOT / "tests/fixtures/orchestration/plan-restructuring-scenarios.json"
HOLDOUT = ROOT / "tests/fixtures/orchestration/plan-restructuring-holdout.json"
SEQUENCING_SCENARIOS = ROOT / "tests/fixtures/orchestration/review-sequencing-scenarios.json"
SEQUENCING_HOLDOUT = ROOT / "tests/fixtures/orchestration/review-sequencing-holdout.json"
DIAGNOSIS_SCENARIOS = ROOT / "tests/fixtures/orchestration/failure-diagnosis-scenarios.json"


def load_state_module():
    spec = importlib.util.spec_from_file_location("plan_execution_state", STATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load plan execution state module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STATE_MODULE = load_state_module()


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
        self.plan.write_text(
            "status: in_progress\n"
            "task_types:\n  - template_workflow\n"
            "review_class: B\n"
            "human_design_required: no\n"
            "human_approval_status: not_required\n"
            "primary_invariant: one invariant\n"
            "write_scope:\n  - allowed.txt\n"
            "context_files:\n  - AGENTS.md\n"
            "required_specs:\n  - AGENTS.md\n"
            "validation:\n  - true\n  - git diff --check\n"
            "acceptance:\n  - Test acceptance.\n"
            "checked_summary_ja: fixture\n",
            encoding="utf-8",
        )
        self.child_plan = self.repo / "docs/plan/active/002-child.md"
        self.child_plan.write_text(
            "status: in_progress\n"
            "task_types:\n  - template_workflow\n"
            "review_class: B\n"
            "human_design_required: no\n"
            "human_approval_status: not_required\n"
            "implementation_risk: low\n"
            "implementation_ambiguity: low\n"
            "primary_invariant: child invariant\n"
            "write_scope:\n  - allowed.txt\n"
            "context_files:\n  - AGENTS.md\n"
            "required_specs:\n  - AGENTS.md\n"
            "validation:\n  - true\n"
            "acceptance:\n  - Test child acceptance.\n"
            "checked_summary_ja: child fixture\n",
            encoding="utf-8",
        )
        (self.repo / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nid\tpath\tstatus\n"
            "001\tdocs/plan/active/001-test.md\tin_progress\n"
            "002\tdocs/plan/active/002-child.md\tin_progress\n",
            encoding="utf-8",
        )
        (self.repo / "AGENTS.md").write_text("test policy\n", encoding="utf-8")
        (self.repo / "allowed.txt").write_text("original\n", encoding="utf-8")
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
        if event_type != "repair_classification" or not self.lifecycle.exists():
            self.lifecycle.write_text(event_id + "\n", encoding="utf-8")
        lifecycle_content = self.lifecycle.read_text(encoding="utf-8")
        return self.run_cli(
            "record", str(self.state), "--run-id", "run-1", "--event-id", event_id,
            "--event-type", event_type, "--implementation-mode", mode,
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--lifecycle-state", str(self.lifecycle), *extra,
        )

    def payload(self) -> dict[str, object]:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def test_event_implementation_mode_must_match_ledger_mode(self) -> None:
        mismatched = self.record("wrong-mode", "elapsed_checkpoint", mode="parent_direct")
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("implementation mode differs", mismatched.stderr)
        self.assertEqual(self.payload()["events"], [])

    def test_legacy_v4_event_without_successor_genesis_remains_appendable(self) -> None:
        recorded = self.record(
            "legacy-review", "parent_review", "--invariant-digest", digest("one invariant")
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        value = self.payload()
        event = value["events"][0]  # type: ignore[index]
        del event["successor_genesis_digest"]
        unsigned = {key: item for key, item in event.items() if key != "event_digest"}
        event["event_digest"] = digest(json.dumps(unsigned, sort_keys=True, separators=(",", ":")))
        value["event_chain_digest"] = event["event_digest"]
        self.state.write_text(json.dumps(value), encoding="utf-8")

        appended = self.record("after-legacy", "elapsed_checkpoint")
        self.assertEqual(appended.returncode, 0, appended.stderr)
        self.assertEqual(len(self.payload()["events"]), 2)  # type: ignore[arg-type]

    def test_failure_diagnosis_fixture_freezes_confirmation_and_fail_closed_cases(self) -> None:
        fixture = json.loads(DIAGNOSIS_SCENARIOS.read_text(encoding="utf-8"))
        self.assertEqual(fixture["schema_version"], 1)
        scenarios = {item["id"]: item for item in fixture["scenarios"]}
        self.assertEqual(
            set(scenarios),
            {
                "confirmed-single-invariant",
                "inconclusive-read-only-stop",
                "disputed-read-only-stop",
                "receipt-replay-rejected",
                "failure-identity-mutation-rejected",
                "validation-authority-drift-rejected",
            },
        )
        self.assertEqual(
            scenarios["confirmed-single-invariant"]["expected"]["next_action"],
            "classify_repair_or_replan",
        )
        for scenario in scenarios.values():
            self.assertEqual(scenario["expected"]["state"], "diagnosis_required")

    def initialize_execution(
        self,
        label: str,
        *,
        plan: Path | None = None,
        predecessor: Path | None = None,
        mode: str = "candidate",
    ) -> tuple[Path, Path, str]:
        selected_plan = plan or self.plan
        run_id = f"run-{label}"
        state = self.base / f"{label}-execution.json"
        lifecycle = self.base / f"{label}-lifecycle.json"
        invariant = next(
            line.split(": ", 1)[1]
            for line in selected_plan.read_text(encoding="utf-8").splitlines()
            if line.startswith("primary_invariant: ")
        )
        arguments = [
            "init", str(state), "--run-id", run_id,
            "--plan", selected_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(selected_plan.read_text(encoding="utf-8")),
            "--source-head", subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
            ).strip(),
            "--primary-invariant-digest", digest(invariant),
            "--lifecycle-state", str(lifecycle),
            "--implementation-mode", mode,
        ]
        if predecessor is not None:
            arguments.extend(("--predecessor-state", str(predecessor)))
        initialized = self.run_cli(*arguments)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        return state, lifecycle, run_id

    def start_writable_attempt(
        self,
        state: Path,
        lifecycle: Path,
        run_id: str,
        attempt_id: str,
        *,
        plan: Path | None = None,
        kind: str = "initial",
        predecessor: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        selected_plan = plan or self.plan
        arguments = [
            "start", str(state), "--run-id", run_id,
            "--plan", selected_plan.relative_to(self.repo).as_posix(),
            "--attempt-id", attempt_id, "--attempt-kind", kind,
            "--lifecycle-state", str(lifecycle),
        ]
        if predecessor is not None:
            arguments.extend(("--predecessor-state", str(predecessor)))
        if kind == "correction":
            payload = json.loads(state.read_text(encoding="utf-8"))
            closures = [
                event for event in payload["events"]
                if event["event_type"] == "attempt_closed"
            ]
            if closures and closures[-1]["candidate_digest"]:
                arguments.extend(("--prior-candidate-digest", closures[-1]["candidate_digest"]))
        return self.run_cli(*arguments)

    def write_applied_lifecycle(
        self,
        lifecycle: Path,
        run_id: str,
        attempt_id: str,
        candidate_digest: str,
        patch_digest: str,
    ) -> str:
        payload = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt_id,
            "current_manifest_digest": candidate_digest.removeprefix("sha256:"),
            "current_patch_digest": patch_digest,
            "correction_round": 0,
            "candidate_generations": 1,
            "phase": "applied",
            "focused_required": False,
            "focused_validation_count": 0,
            "authoritative_validation_count": 1,
            "parent_review_rejections": 0,
        }
        content = json.dumps(payload, sort_keys=True, indent=2) + "\n"
        lifecycle.write_text(content, encoding="utf-8")
        return digest(content)

    def close_writable_attempt(
        self,
        state: Path,
        lifecycle: Path,
        run_id: str,
        attempt_id: str,
        *,
        invariant: str,
        outcome: str,
        reason: str | None = None,
        evidence: str = "review-evidence",
        author: str = "parent",
        candidate: str | None = None,
        lifecycle_digest: str | None = None,
        extra_invariants: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        candidate_manifest: Path | None = None
        accepted_source_head: str | None = None
        if outcome in {"accepted", "correction_requested"} and candidate is None:
            state_payload = json.loads(state.read_text(encoding="utf-8"))
            if outcome == "accepted":
                target = self.repo / "allowed.txt"
                target.write_text(
                    target.read_text(encoding="utf-8") + f"accepted {attempt_id}\n",
                    encoding="utf-8",
                )
                subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
                subprocess.run(
                    ["git", "commit", "-qm", f"accept {attempt_id}"], cwd=self.repo, check=True
                )
                accepted_source_head = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
                ).strip()
                patch = subprocess.check_output(
                    [
                        "git", "diff", "--binary", "--full-index",
                        state_payload["source_head"], accepted_source_head, "--",
                    ],
                    cwd=self.repo,
                )
                patch_digest = hashlib.sha256(patch).hexdigest()
            else:
                patch_digest = hashlib.sha256(f"patch:{attempt_id}".encode()).hexdigest()
            manifest = {
                "schema_version": 2,
                "orchestration_run_id": run_id,
                "plan_execution_attempt_id": attempt_id,
                "plan_path": state_payload["plan_path"],
                "plan_digest": state_payload["plan_digest"].removeprefix("sha256:"),
                "source_head": state_payload["source_head"],
                "patch_digest": patch_digest,
            }
            manifest_content = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
            candidate_manifest = self.base / f"{attempt_id}-manifest.json"
            candidate_manifest.write_text(manifest_content, encoding="utf-8")
            candidate = digest(manifest_content)
            lifecycle_digest = self.write_applied_lifecycle(
                lifecycle, run_id, attempt_id, candidate, patch_digest
            )
        arguments = [
            "close", str(state), "--run-id", run_id,
            "--attempt-id", attempt_id, "--outcome", outcome,
            "--review-author", author,
            "--review-evidence-digest", digest(evidence),
            "--invariant-digest", invariant,
            "--lifecycle-state", str(lifecycle),
        ]
        for item in extra_invariants:
            arguments.extend(("--invariant-digest", item))
        if reason is not None:
            arguments.extend(("--review-reason-code", reason))
        if candidate is not None:
            arguments.extend(("--candidate-digest", candidate))
        if candidate_manifest is not None:
            arguments.extend(("--candidate-manifest", str(candidate_manifest)))
        if lifecycle_digest is not None:
            arguments.extend(("--candidate-lifecycle-digest", lifecycle_digest))
        if accepted_source_head is not None:
            arguments.extend(("--accepted-source-head", accepted_source_head))
        return self.run_cli(*arguments)

    def accepted_execution(self, label: str) -> tuple[Path, Path, str]:
        state, lifecycle, run_id = self.initialize_execution(label)
        started = self.start_writable_attempt(
            state, lifecycle, run_id, f"{label}-attempt"
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        closed = self.close_writable_attempt(
            state, lifecycle, run_id, f"{label}-attempt",
            invariant=digest("one invariant"), outcome="accepted",
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        return state, lifecycle, run_id

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
            "candidate_lifecycle_digest": digest(
                self.lifecycle.read_text(encoding="utf-8")
                if self.lifecycle.exists() else event_id + "\n"
            ),
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

    def enter_confirmed_diagnosis(
        self,
        *,
        state: Path | None = None,
        lifecycle: Path | None = None,
        run_id: str = "run-1",
        invariant: str | None = None,
        label: str = "confirmed",
        results: tuple[str, ...] = ("confirmed",),
        failure_kind: str = "command",
        command_status: int = 7,
        observed_exit_status: int = 7,
        lifecycle_overrides: dict[str, object] | None = None,
        report_overrides: dict[str, object] | None = None,
        expected_rejection: str | None = None,
    ) -> None:
        selected_state = state or self.state
        selected_lifecycle = lifecycle or self.lifecycle
        affected = invariant or digest("one invariant")
        attempt_id = f"{label}-attempt"
        started = self.start_writable_attempt(
            selected_state, selected_lifecycle, run_id, attempt_id
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        manifest_digest = hashlib.sha256(f"{label}-manifest".encode()).hexdigest()
        patch_digest = hashlib.sha256(f"{label}-patch".encode()).hexdigest()
        lifecycle_value = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt_id,
            "current_manifest_digest": manifest_digest,
            "current_patch_digest": patch_digest,
            "correction_round": 0,
            "candidate_generations": 1,
            "phase": "authoritative_failed",
            "focused_required": False,
            "focused_validation_count": 0,
            "authoritative_validation_count": 1,
            "parent_review_rejections": 0,
        }
        lifecycle_value.update(lifecycle_overrides or {})
        lifecycle_content = json.dumps(lifecycle_value, sort_keys=True, indent=2) + "\n"
        selected_lifecycle.write_text(lifecycle_content, encoding="utf-8")
        authoritative = self.run_cli(
            "record", str(selected_state), "--run-id", run_id,
            "--event-id", f"{label}-authoritative",
            "--event-type", "authoritative_validation",
            "--implementation-mode", "candidate",
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--lifecycle-state", str(selected_lifecycle),
        )
        self.assertEqual(authoritative.returncode, 0, authoritative.stderr)
        argv = ["true"]
        identity = {
            "suite": "authoritative",
            "kind": failure_kind,
            "command_index": 0,
            "argv": argv,
        }
        operation_digest = digest(json.dumps(identity, sort_keys=True, separators=(",", ":")))
        report = {
            "candidate_manifest_digest": manifest_digest,
            "candidate_patch_digest": patch_digest,
            "plan_execution_attempt_id": attempt_id,
            "plan_path": "docs/plan/active/001-test.md",
            "plan_digest": json.loads(selected_state.read_text(encoding="utf-8"))["plan_digest"],
            "source_head": json.loads(selected_state.read_text(encoding="utf-8"))["source_head"],
            "implementation_mode": "candidate",
            "suite": "authoritative",
            "passed": False,
            "commands": [{"index": 0, "argv": argv, "returncode": command_status}],
            "failure": {
                "kind": failure_kind,
                "command_index": 0,
                "operation_digest": operation_digest,
                "observed_exit_status": observed_exit_status,
            },
        }
        report.update(report_overrides or {})
        report_path = self.base / f"{label}-validation.json"
        report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        failure = self.run_cli(
            "record", str(selected_state), "--run-id", run_id,
            "--event-id", f"{label}-failure",
            "--event-type", "authoritative_failure",
            "--implementation-mode", "candidate",
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--validation-report", str(report_path),
            "--lifecycle-state", str(selected_lifecycle),
        )
        if expected_rejection is not None:
            self.assertNotEqual(failure.returncode, 0)
            self.assertIn(expected_rejection, failure.stderr)
            return
        self.assertEqual(failure.returncode, 0, failure.stderr)
        for index, result in enumerate(results, start=1):
            payload = json.loads(selected_state.read_text(encoding="utf-8"))
            failure_event = next(
                event for event in payload["events"]
                if event["event_type"] == "authoritative_failure"
            )
            receipt = digest(f"{label}-diagnosis-review-{index}")
            diagnosis = {
                "schema_version": 1,
                "plan_path": payload["plan_path"],
                "plan_digest": payload["plan_digest"],
                "source_head": payload["source_head"],
                "candidate_lifecycle_identity_digest": payload["candidate_lifecycle_identity_digest"],
                "candidate_lifecycle_digest": digest(lifecycle_content),
                "authoritative_failure_event_digest": failure_event["event_digest"],
                "failure_evidence_digest": failure_event["failure_evidence_digest"],
                "failed_operation_digest": failure_event["failure_evidence"]["failed_operation_digest"],
                "observed_exit_status": observed_exit_status,
                "affected_invariant_digest": affected if result == "confirmed" else "",
                "independent_review_receipt_digest": receipt,
                "reproduction_evidence_digest": digest(f"{label}-bounded-reproduction-{index}"),
                "diagnosis_result": result,
            }
            diagnosis_path = self.base / f"{label}-diagnosis-{index}.json"
            diagnosis_path.write_text(
                json.dumps(diagnosis, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            arguments = [
                "record", str(selected_state), "--run-id", run_id,
                "--event-id", f"{label}-diagnosis-{index}",
                "--event-type", "failure_diagnosis",
                "--implementation-mode", "candidate",
                "--independent-review-receipt-digest", receipt,
                "--candidate-lifecycle-digest", digest(lifecycle_content),
                "--diagnosis-evidence-file", str(diagnosis_path),
                "--lifecycle-state", str(selected_lifecycle),
            ]
            if result == "confirmed":
                arguments.extend(("--invariant-digest", affected))
            recorded = self.run_cli(*arguments)
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(
            json.loads(selected_state.read_text(encoding="utf-8"))["state"],
            "diagnosis_required",
        )

    def test_authoritative_failure_binds_exact_candidate_leaf_and_status_shape(self) -> None:
        cases = (
            (
                "lifecycle-schema",
                {"unexpected": "field"},
                None,
                "invalid exact schema",
                "command",
                7,
                7,
            ),
            (
                "lifecycle-attempt",
                {"plan_execution_attempt_id": "different-attempt"},
                None,
                "attempt identity mismatch",
                "command",
                7,
                7,
            ),
            (
                "lifecycle-counters",
                {
                    "correction_round": 1,
                    "candidate_generations": 2,
                    "parent_review_rejections": 1,
                },
                None,
                "lineage differs from the execution ledger",
                "command",
                7,
                7,
            ),
            (
                "report-patch",
                None,
                {"candidate_patch_digest": "0" * 64},
                "patch does not match",
                "command",
                7,
                7,
            ),
            (
                "report-attempt",
                None,
                {"plan_execution_attempt_id": "different-attempt"},
                "report attempt does not match",
                "command",
                7,
                7,
            ),
            (
                "integrity-status",
                None,
                None,
                "safety-check failure",
                "dependency_integrity",
                7,
                1,
            ),
        )
        for label, lifecycle_overrides, report_overrides, message, kind, status, observed in cases:
            with self.subTest(label=label):
                state, lifecycle, run_id = self.initialize_execution(label)
                self.enter_confirmed_diagnosis(
                    state=state,
                    lifecycle=lifecycle,
                    run_id=run_id,
                    label=label,
                    lifecycle_overrides=lifecycle_overrides,
                    report_overrides=report_overrides,
                    failure_kind=kind,
                    command_status=status,
                    observed_exit_status=observed,
                    expected_rejection=message,
                )

        signal_state, signal_lifecycle, signal_run = self.initialize_execution("signal-status")
        self.enter_confirmed_diagnosis(
            state=signal_state,
            lifecycle=signal_lifecycle,
            run_id=signal_run,
            label="signal-status",
            command_status=-15,
            observed_exit_status=-15,
        )

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
        state, lifecycle, run_id = self.initialize_execution(
            "parent-budget", mode="parent_direct"
        )

        def parent_record(event_id: str, *extra: str) -> subprocess.CompletedProcess[str]:
            lifecycle.write_text(event_id + "\n", encoding="utf-8")
            return self.run_cli(
                "record", str(state), "--run-id", run_id, "--event-id", event_id,
                "--event-type", "parent_review", "--implementation-mode", "parent_direct",
                "--candidate-lifecycle-digest", digest(event_id + "\n"),
                "--lifecycle-state", str(lifecycle), *extra,
            )

        missing = parent_record(
            "parent-1", "--invariant-digest", invariant, "--finding-severity", "Medium"
        )
        self.assertNotEqual(missing.returncode, 0)
        for index in (1, 2):
            result = parent_record(
                f"parent-{index}", "--invariant-digest", invariant,
                "--finding-severity", "Medium", "--independent-review-receipt-digest",
                digest(f"receipt-{index}"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(state.read_text(encoding="utf-8"))["state"], "replan_required"
        )

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

    def test_parent_direct_authoritative_failure_enters_diagnosis_without_candidate_artifacts(self) -> None:
        state = self.base / "parent-direct-execution.json"
        lifecycle = self.base / "parent-direct-lifecycle.json"
        run_id = "parent-direct-failure"
        initialized = self.run_cli(
            "init", str(state), "--run-id", run_id,
            "--plan", "docs/plan/active/001-test.md",
            "--plan-digest", digest(self.plan.read_text()),
            "--source-head", self.head,
            "--primary-invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        lifecycle_content = "parent-direct-authoritative-failed\n"
        lifecycle.write_text(lifecycle_content, encoding="utf-8")
        authoritative = self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "parent-direct-authoritative",
            "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(authoritative.returncode, 0, authoritative.stderr)
        identity = {
            "suite": "authoritative",
            "kind": "command",
            "command_index": 0,
            "argv": ["true"],
        }
        report = {
            "plan_path": "docs/plan/active/001-test.md",
            "plan_digest": digest(self.plan.read_text()),
            "source_head": self.head,
            "implementation_mode": "parent_direct",
            "suite": "authoritative",
            "passed": False,
            "commands": [{"index": 0, "argv": ["true"], "returncode": 9}],
            "failure": {
                "kind": "command",
                "command_index": 0,
                "operation_digest": digest(
                    json.dumps(identity, sort_keys=True, separators=(",", ":"))
                ),
                "observed_exit_status": 9,
            },
        }
        report_path = self.base / "parent-direct-validation.json"
        report_path.write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        failed = self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "parent-direct-failure",
            "--event-type", "authoritative_failure",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--validation-report", str(report_path),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)
        payload = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "diagnosis_required")
        failure_event = payload["events"][-1]
        self.assertEqual(failure_event["failure_evidence"]["implementation_mode"], "parent_direct")
        self.assertEqual(failure_event["failure_evidence"]["candidate_manifest_digest"], "")

    def test_unconfirmed_failure_diagnosis_blocks_write_lifecycle_operations(self) -> None:
        invariant = digest("one invariant")
        active_repair_plan = self.run_cli(
            "check", str(self.state), "--run-id", "run-1",
            "--operation", "repair_plan", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(active_repair_plan.returncode, 0)
        self.assertIn("confirmed independent repair classification", active_repair_plan.stderr)
        self.enter_confirmed_diagnosis(
            invariant=invariant,
            label="unconfirmed",
            results=("inconclusive", "disputed"),
        )
        self.assertEqual(self.payload()["state"], "diagnosis_required")
        readable = self.run_cli(
            "check", str(self.state), "--run-id", "run-1",
            "--operation", "diagnosis_read", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertEqual(readable.returncode, 0, readable.stderr)
        for operation in ("execution", "completion", "archive", "repair_plan"):
            with self.subTest(operation=operation):
                denied = self.run_cli(
                    "check", str(self.state), "--run-id", "run-1",
                    "--operation", operation, "--lifecycle-state", str(self.lifecycle),
                )
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn("pending confirmed failure diagnosis", denied.stderr)
        repair_receipt = digest("premature-repair-review")
        repair_evidence = self.write_repair_evidence(
            "premature-repair", repair_receipt, invariant
        )
        premature = self.record(
            "premature-repair", "repair_classification",
            "--invariant-digest", invariant,
            "--independent-review-receipt-digest", repair_receipt,
            "--repair-evidence-file", str(repair_evidence),
        )
        self.assertNotEqual(premature.returncode, 0)
        self.assertIn("confirmed failure diagnosis", premature.stderr)
        common = [
            "--orchestration-run-id", "run-1", "--lifecycle-state", str(self.lifecycle),
            "--plan-execution-state", str(self.state),
        ]
        for command in (
            ["run", self.source_path_for_runner(), *common, "--bwrap-bin", "missing-bwrap"],
            ["correct", self.source_path_for_runner(), "missing-manifest", "missing-brief", *common],
            ["validate", "missing-manifest", "--suite", "focused", "--output-dir", str(self.base / "validation"), *common],
            ["apply", "missing-manifest", *common],
            ["finalize-apply", "missing-manifest", *common],
        ):
            denied = subprocess.run(
                [sys.executable, str(RUNNER), *command], cwd=self.repo,
                check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("pending confirmed failure diagnosis", denied.stderr)
            self.assertNotIn("missing-manifest", denied.stderr)

    def test_diagnosis_replay_mutation_authority_drift_and_budget_fail_closed(self) -> None:
        self.enter_confirmed_diagnosis(
            label="bounded-diagnosis", results=("inconclusive",)
        )
        payload = self.payload()
        failure = next(
            event for event in payload["events"]
            if event["event_type"] == "authoritative_failure"
        )
        first = next(
            event for event in payload["events"]
            if event["event_type"] == "failure_diagnosis"
        )

        def write_evidence(label: str, receipt: str, **overrides: object) -> Path:
            value: dict[str, object] = {
                **first["diagnosis_evidence"],
                "independent_review_receipt_digest": receipt,
                "reproduction_evidence_digest": digest(label),
                "diagnosis_result": "disputed",
            }
            value.update(overrides)
            path = self.base / f"{label}.json"
            path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            return path

        replay_receipt = first["independent_review_receipt_digest"]
        replay_path = write_evidence("diagnosis-replay", replay_receipt)
        replay = self.run_cli(
            "record", str(self.state), "--run-id", "run-1",
            "--event-id", "diagnosis-replay", "--event-type", "failure_diagnosis",
            "--implementation-mode", "candidate",
            "--independent-review-receipt-digest", replay_receipt,
            "--candidate-lifecycle-digest", first["candidate_lifecycle_digest"],
            "--diagnosis-evidence-file", str(replay_path),
            "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(replay.returncode, 0)
        self.assertIn("receipt replay", replay.stderr)

        mutation_receipt = digest("diagnosis-mutation-review")
        mutation_path = write_evidence(
            "diagnosis-mutation", mutation_receipt,
            failed_operation_digest=digest("substituted operation"),
        )
        mutation = self.run_cli(
            "record", str(self.state), "--run-id", "run-1",
            "--event-id", "diagnosis-mutation", "--event-type", "failure_diagnosis",
            "--implementation-mode", "candidate",
            "--independent-review-receipt-digest", mutation_receipt,
            "--candidate-lifecycle-digest", first["candidate_lifecycle_digest"],
            "--diagnosis-evidence-file", str(mutation_path),
            "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(mutation.returncode, 0)
        self.assertIn("does not match the authoritative failure", mutation.stderr)

        original_plan = self.plan.read_text(encoding="utf-8")
        self.plan.write_text(original_plan.replace("  - true\n", "  - false\n"), encoding="utf-8")
        drift_receipt = digest("diagnosis-authority-drift-review")
        drift_path = write_evidence("diagnosis-authority-drift", drift_receipt)
        drift = self.run_cli(
            "record", str(self.state), "--run-id", "run-1",
            "--event-id", "diagnosis-authority-drift", "--event-type", "failure_diagnosis",
            "--implementation-mode", "candidate",
            "--independent-review-receipt-digest", drift_receipt,
            "--candidate-lifecycle-digest", first["candidate_lifecycle_digest"],
            "--diagnosis-evidence-file", str(drift_path),
            "--lifecycle-state", str(self.lifecycle),
        )
        self.plan.write_text(original_plan, encoding="utf-8")
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("plan digest differs", drift.stderr)

        for index in (2, 3):
            receipt = digest(f"bounded-diagnosis-review-{index}")
            evidence = write_evidence(f"bounded-diagnosis-{index}", receipt)
            recorded = self.run_cli(
                "record", str(self.state), "--run-id", "run-1",
                "--event-id", f"bounded-diagnosis-{index}",
                "--event-type", "failure_diagnosis", "--implementation-mode", "candidate",
                "--independent-review-receipt-digest", receipt,
                "--candidate-lifecycle-digest", first["candidate_lifecycle_digest"],
                "--diagnosis-evidence-file", str(evidence),
                "--lifecycle-state", str(self.lifecycle),
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
        exhausted_receipt = digest("bounded-diagnosis-review-4")
        exhausted_path = write_evidence("bounded-diagnosis-4", exhausted_receipt)
        exhausted = self.run_cli(
            "record", str(self.state), "--run-id", "run-1",
            "--event-id", "bounded-diagnosis-4", "--event-type", "failure_diagnosis",
            "--implementation-mode", "candidate",
            "--independent-review-receipt-digest", exhausted_receipt,
            "--candidate-lifecycle-digest", first["candidate_lifecycle_digest"],
            "--diagnosis-evidence-file", str(exhausted_path),
            "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(exhausted.returncode, 0)
        self.assertIn("attempt budget is exhausted", exhausted.stderr)
        self.assertEqual(self.payload()["state"], "diagnosis_required")

    def test_independent_repair_requires_bounded_evidence_and_stops_only_current_run(self) -> None:
        invariant_digest = digest("one invariant")
        invariant = ("--invariant-digest", invariant_digest)
        receipt_digest = digest("repair-review")
        receipt = ("--independent-review-receipt-digest", receipt_digest)
        self.assertNotEqual(self.record("repair-missing", "repair_classification", *invariant).returncode, 0)
        self.enter_confirmed_diagnosis(invariant=invariant_digest)
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
        confirmed_lifecycle = self.lifecycle.read_text(encoding="utf-8")
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
        self.lifecycle.write_text(confirmed_lifecycle, encoding="utf-8")
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
        repair_plan_gate = self.run_cli(
            "check", str(self.state), "--run-id", "run-1",
            "--operation", "repair_plan", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertEqual(repair_plan_gate.returncode, 0, repair_plan_gate.stderr)
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
        self.enter_confirmed_diagnosis(invariant=invariant)
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
        self.enter_confirmed_diagnosis(invariant=invariant)
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
                self.enter_confirmed_diagnosis(
                    state=state_path, lifecycle=lifecycle_path, run_id=run_id,
                    invariant=invariant, label=f"diagnosis-{label}",
                )
                original_state = self.state
                original_lifecycle = self.lifecycle
                self.state = state_path
                self.lifecycle = lifecycle_path
                try:
                    evidence = self.write_repair_evidence(
                        event_id, receipt, invariant, **{predicate: False},
                    )
                finally:
                    self.state = original_state
                    self.lifecycle = original_lifecycle
                classified = self.run_cli(
                    "record", str(state_path), "--run-id", run_id,
                    "--event-id", event_id, "--event-type", "repair_classification",
                    "--implementation-mode", "candidate",
                    "--invariant-digest", invariant,
                    "--independent-review-receipt-digest", receipt,
                    "--candidate-lifecycle-digest", digest(
                        lifecycle_path.read_text(encoding="utf-8")
                    ),
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
        self.enter_confirmed_diagnosis(invariant=invariant)
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
            "sequence": len(value["events"]) + 1,  # type: ignore[arg-type]
            "event_id": "forged-after-terminal",
            "event_type": "elapsed_checkpoint",
            "implementation_mode": "candidate",
            "invariant_digests": [],
            "finding_severities": [],
            "independent_review_receipt_digest": "",
            "repair_classification": {},
            "repair_evidence_digest": "",
            "candidate_lifecycle_digest": "",
            "attempt_id": "",
            "attempt_kind": "",
            "candidate_digest": "",
            "review_outcome": "",
            "review_reason_code": "",
            "review_author": "",
            "review_evidence_digest": "",
            "predecessor_plan_digest": "",
            "predecessor_accepted_candidate_digest": "",
            "predecessor_closing_event_digest": "",
            "predecessor_accepted_source_head": "",
            "accepted_source_head": "",
            "successor_run_id": "",
            "successor_plan_digest": "",
            "successor_source_head": "",
            "successor_primary_invariant_digest": "",
            "successor_genesis_digest": "",
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
        self.enter_confirmed_diagnosis(invariant=invariant)
        evidence = self.write_repair_evidence("repair-digest", receipt, invariant)
        accepted = self.record(
            "repair-digest", "repair_classification",
            "--invariant-digest", invariant,
            "--independent-review-receipt-digest", receipt,
            "--repair-evidence-file", str(evidence),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        value = self.payload()
        event = value["events"][-1]  # type: ignore[index]
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
        self.assertIs(plan119["input"]["source_scope_changed"], False)
        self.assertIs(plan119["input"]["validation_authority_changed"], False)
        self.assertIs(plan119["input"]["invariant_boundaries_changed"], False)
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
                reason = scenario["expected"]["reason_code"]
                scenario_mode = (
                    "parent_direct" if reason == "parent_remediation_budget_exhausted"
                    else "candidate"
                )
                state = self.base / f"{run_id}.json"
                lifecycle = self.base / f"{run_id}-lifecycle.json"
                initialized = self.run_cli(
                    "init", str(state), "--run-id", run_id,
                    "--plan", "docs/plan/active/001-test.md",
                    "--plan-digest", digest(self.plan.read_text()),
                    "--source-head", self.head,
                    "--primary-invariant-digest", digest("one invariant"),
                    "--lifecycle-state", str(lifecycle),
                    "--implementation-mode", scenario_mode,
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)

                event_number = 0

                def record_event(
                    event_type: str, *extra: str, mode: str = scenario_mode
                ) -> None:
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

    def test_accepted_two_plan_chain_is_exact_sequential_and_helper_reads_do_not_lock_it(self) -> None:
        predecessor, _, _ = self.accepted_execution("predecessor")
        child_state, child_lifecycle, child_run = self.initialize_execution(
            "child", plan=self.child_plan, predecessor=predecessor
        )
        started = self.start_writable_attempt(
            child_state, child_lifecycle, child_run, "child-attempt",
            plan=self.child_plan, predecessor=predecessor,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        before_helper = child_state.read_bytes()
        helper_check = self.run_cli(
            "check", str(child_state), "--run-id", child_run,
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertEqual(helper_check.returncode, 0, helper_check.stderr)
        self.assertEqual(child_state.read_bytes(), before_helper)
        overlapping = self.start_writable_attempt(
            child_state, child_lifecycle, child_run, "overlap",
            plan=self.child_plan, predecessor=predecessor,
        )
        self.assertNotEqual(overlapping.returncode, 0)
        self.assertIn("already open", overlapping.stderr)

        payload = json.loads(child_state.read_text(encoding="utf-8"))
        predecessor_payload = json.loads(predecessor.read_text(encoding="utf-8"))
        self.assertEqual(payload["writable_attempt_starts"], 1)
        self.assertEqual(payload["open_attempt_id"], "child-attempt")
        self.assertEqual(
            payload["predecessor_closing_event_digest"],
            predecessor_payload["accepted_closing_event_digest"],
        )

    def test_rejected_or_substituted_predecessor_cannot_admit_a_dependent_start(self) -> None:
        rejected_state, rejected_lifecycle, rejected_run = self.initialize_execution("rejected")
        self.assertEqual(
            self.start_writable_attempt(
                rejected_state, rejected_lifecycle, rejected_run, "rejected-attempt"
            ).returncode,
            0,
        )
        rejected = self.close_writable_attempt(
            rejected_state, rejected_lifecycle, rejected_run, "rejected-attempt",
            invariant=digest("one invariant"), outcome="rejected",
            reason="acceptance_unmet",
        )
        self.assertEqual(rejected.returncode, 0, rejected.stderr)
        child_state = self.base / "rejected-child.json"
        denied_init = self.run_cli(
            "init", str(child_state), "--run-id", "rejected-child",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text(encoding="utf-8")),
            "--source-head", self.head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "rejected-child-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(rejected_state),
        )
        self.assertNotEqual(denied_init.returncode, 0)
        self.assertIn("lacks an accepted closing transition", denied_init.stderr)

        first, _, _ = self.accepted_execution("accepted-first")
        second, _, _ = self.accepted_execution("accepted-second")
        bound_state, bound_lifecycle, bound_run = self.initialize_execution(
            "bound-child", plan=self.child_plan, predecessor=first
        )
        substituted = self.start_writable_attempt(
            bound_state, bound_lifecycle, bound_run, "substituted",
            plan=self.child_plan, predecessor=second,
        )
        self.assertNotEqual(substituted.returncode, 0)
        self.assertIn("stale or mismatched", substituted.stderr)

    def test_parent_review_reason_authority_replay_and_crash_recovery_fail_closed(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("classification")
        invariant = digest("one invariant")
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, "classification-1").returncode,
            0,
        )
        unknown = self.close_writable_attempt(
            state, lifecycle, run_id, "classification-1", invariant=invariant,
            outcome="correction_requested", reason="unknown_reason",
        )
        self.assertNotEqual(unknown.returncode, 0)
        worker_authored = self.close_writable_attempt(
            state, lifecycle, run_id, "classification-1", invariant=invariant,
            outcome="correction_requested", reason="acceptance_unmet", author="worker",
        )
        self.assertNotEqual(worker_authored.returncode, 0)
        missing_evidence = self.run_cli(
            "close", str(state), "--run-id", run_id,
            "--attempt-id", "classification-1", "--outcome", "correction_requested",
            "--review-author", "parent", "--review-reason-code", "acceptance_unmet",
            "--invariant-digest", invariant, "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(missing_evidence.returncode, 0)

        closed = self.close_writable_attempt(
            state, lifecycle, run_id, "classification-1", invariant=invariant,
            outcome="correction_requested", reason="acceptance_unmet",
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        replay = self.close_writable_attempt(
            state, lifecycle, run_id, "classification-1", invariant=invariant,
            outcome="correction_requested", reason="acceptance_unmet",
        )
        self.assertNotEqual(replay.returncode, 0)
        self.assertEqual(
            self.start_writable_attempt(
                state, lifecycle, run_id, "classification-2", kind="correction"
            ).returncode,
            0,
        )
        repeated = self.close_writable_attempt(
            state, lifecycle, run_id, "classification-2", invariant=invariant,
            outcome="correction_requested", reason="acceptance_unmet",
        )
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        payload = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "replan_required")
        self.assertIn("acceptance_unmet", payload["replan_reason_codes"])

        crashed_state, crashed_lifecycle, crashed_run = self.initialize_execution("crashed")
        self.assertEqual(
            self.start_writable_attempt(
                crashed_state, crashed_lifecycle, crashed_run, "crashed-attempt"
            ).returncode,
            0,
        )
        recovered = self.close_writable_attempt(
            crashed_state, crashed_lifecycle, crashed_run, "crashed-attempt",
            invariant=invariant, outcome="rejected", reason="evidence_incomplete",
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(
            json.loads(crashed_state.read_text(encoding="utf-8"))["state"], "rejected"
        )

    def test_changed_reasons_use_two_corrections_then_budget_and_coupling_stop(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("changed-reasons")
        invariant = digest("one invariant")
        reasons = ("acceptance_unmet", "required_spec_missed", "focused_validation_failed")
        kinds = ("initial", "correction", "correction")
        for index, (reason, kind) in enumerate(zip(reasons, kinds), start=1):
            attempt = f"changed-{index}"
            started = self.start_writable_attempt(
                state, lifecycle, run_id, attempt, kind=kind
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            closed = self.close_writable_attempt(
                state, lifecycle, run_id, attempt, invariant=invariant,
                outcome="correction_requested", reason=reason,
            )
            self.assertEqual(closed.returncode, 0, closed.stderr)
        payload = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "replan_required")
        self.assertIn("candidate_correction_budget_exhausted", payload["replan_reason_codes"])
        self.assertEqual(payload["correction_rounds"], 2)

        coupled_state, coupled_lifecycle, coupled_run = self.initialize_execution("coupled")
        self.assertEqual(
            self.start_writable_attempt(
                coupled_state, coupled_lifecycle, coupled_run, "coupled-attempt"
            ).returncode,
            0,
        )
        coupled = self.close_writable_attempt(
            coupled_state, coupled_lifecycle, coupled_run, "coupled-attempt",
            invariant=invariant, extra_invariants=(digest("second invariant"),),
            outcome="correction_requested", reason="multiple_invariants_coupled",
        )
        self.assertEqual(coupled.returncode, 0, coupled.stderr)
        self.assertEqual(
            json.loads(coupled_state.read_text(encoding="utf-8"))["state"],
            "replan_required",
        )

        rejected_state, rejected_lifecycle, rejected_run = self.initialize_execution(
            "final-correction-rejected"
        )
        for index, outcome in enumerate(
            ("correction_requested", "correction_requested", "rejected"), start=1
        ):
            kind = "initial" if index == 1 else "correction"
            attempt = f"final-rejected-{index}"
            started = self.start_writable_attempt(
                rejected_state, rejected_lifecycle, rejected_run, attempt, kind=kind
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            closed = self.close_writable_attempt(
                rejected_state, rejected_lifecycle, rejected_run, attempt,
                invariant=invariant, outcome=outcome,
                reason=("acceptance_unmet", "required_spec_missed", "evidence_incomplete")[index - 1],
            )
            self.assertEqual(closed.returncode, 0, closed.stderr)
        final_payload = json.loads(rejected_state.read_text(encoding="utf-8"))
        self.assertEqual(final_payload["state"], "replan_required")
        self.assertIn("candidate_correction_budget_exhausted", final_payload["replan_reason_codes"])

    def test_runner_records_open_attempt_before_prerequisite_failure(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("runner-start")
        command = [
            sys.executable, str(RUNNER), "run", self.source_path_for_runner(),
            "--orchestration-run-id", run_id,
            "--lifecycle-state", str(lifecycle),
            "--plan-execution-state", str(state),
            "--bwrap-bin", "definitely-missing-bwrap",
        ]
        failed = subprocess.run(
            command, cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("definitely-missing-bwrap", failed.stderr)
        payload = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(payload["writable_attempt_starts"], 1)
        self.assertTrue(payload["open_attempt_id"])
        overlapping = subprocess.run(
            command, cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(overlapping.returncode, 0)
        self.assertIn("already open", overlapping.stderr)
        self.assertNotIn("definitely-missing-bwrap", overlapping.stderr)

    def test_plan_head_and_genesis_drift_fail_before_writable_start(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("baseline-drift")
        self.plan.write_text(self.plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        plan_drift = self.start_writable_attempt(
            state, lifecycle, run_id, "plan-drift"
        )
        self.assertNotEqual(plan_drift.returncode, 0)
        self.assertIn("plan digest differs", plan_drift.stderr)
        subprocess.run(["git", "restore", self.plan.relative_to(self.repo)], cwd=self.repo, check=True)
        (self.repo / "later.txt").write_text("later\n", encoding="utf-8")
        subprocess.run(["git", "add", "later.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "advance"], cwd=self.repo, check=True)
        head_drift = self.start_writable_attempt(
            state, lifecycle, run_id, "head-drift"
        )
        self.assertNotEqual(head_drift.returncode, 0)
        self.assertIn("source HEAD differs", head_drift.stderr)

        value = json.loads(state.read_text(encoding="utf-8"))
        value["source_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        state.write_text(json.dumps(value), encoding="utf-8")
        tampered = self.run_cli("check", str(state), "--run-id", run_id)
        self.assertNotEqual(tampered.returncode, 0)
        self.assertIn("genesis identity digest mismatch", tampered.stderr)

    def test_predecessor_source_ancestry_and_single_successor_claim_fail_closed(self) -> None:
        predecessor, _, _ = self.accepted_execution("chain-root")
        first_state, first_lifecycle, first_run = self.initialize_execution(
            "chain-first", plan=self.child_plan, predecessor=predecessor
        )
        second_state, second_lifecycle, second_run = self.initialize_execution(
            "chain-second", plan=self.child_plan, predecessor=predecessor
        )

        commands = []
        for state, lifecycle, run_id, attempt in (
            (first_state, first_lifecycle, first_run, "first-attempt"),
            (second_state, second_lifecycle, second_run, "second-attempt"),
        ):
            commands.append([
                sys.executable, str(STATE_SCRIPT), "start", str(state),
                "--run-id", run_id,
                "--plan", self.child_plan.relative_to(self.repo).as_posix(),
                "--attempt-id", attempt, "--attempt-kind", "initial",
                "--predecessor-state", str(predecessor),
                "--lifecycle-state", str(lifecycle),
            ])
        processes = [
            subprocess.Popen(
                command, cwd=self.repo, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            for command in commands
        ]
        results = [(*process.communicate(timeout=10), process.returncode) for process in processes]
        self.assertEqual(sorted(result[2] for result in results), [0, 1])
        self.assertTrue(any("already claimed" in result[1] for result in results if result[2]))
        predecessor_payload = json.loads(predecessor.read_text(encoding="utf-8"))
        self.assertTrue(predecessor_payload["successor_claim_digest"])
        self.assertEqual(
            sum(
                1 for event in predecessor_payload["events"]
                if event["event_type"] == "successor_claimed"
            ),
            1,
        )

        duplicate_predecessor, _, _ = self.accepted_execution("duplicate-root")
        duplicate_run = "same-successor-run"
        duplicate_states = (
            (self.base / "duplicate-a.json", self.base / "duplicate-a-lifecycle.json"),
            (self.base / "duplicate-b.json", self.base / "duplicate-b-lifecycle.json"),
        )
        duplicate_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        for state_path, lifecycle_path in duplicate_states:
            initialized = self.run_cli(
                "init", str(state_path), "--run-id", duplicate_run,
                "--plan", self.child_plan.relative_to(self.repo).as_posix(),
                "--plan-digest", digest(self.child_plan.read_text(encoding="utf-8")),
                "--source-head", duplicate_head,
                "--primary-invariant-digest", digest("child invariant"),
                "--lifecycle-state", str(lifecycle_path),
                "--implementation-mode", "candidate",
                "--predecessor-state", str(duplicate_predecessor),
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
        first_duplicate = self.start_writable_attempt(
            duplicate_states[0][0], duplicate_states[0][1], duplicate_run,
            "duplicate-attempt-a", plan=self.child_plan, predecessor=duplicate_predecessor,
        )
        self.assertEqual(first_duplicate.returncode, 0, first_duplicate.stderr)
        second_duplicate = self.start_writable_attempt(
            duplicate_states[1][0], duplicate_states[1][1], duplicate_run,
            "duplicate-attempt-b", plan=self.child_plan, predecessor=duplicate_predecessor,
        )
        self.assertNotEqual(second_duplicate.returncode, 0)
        self.assertIn("already claimed", second_duplicate.stderr)

        tree = subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=self.repo, text=True
        ).strip()
        unrelated = subprocess.run(
            ["git", "commit-tree", tree, "-m", "unrelated root"],
            cwd=self.repo, check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        subprocess.run(["git", "switch", "-q", "--detach", unrelated], cwd=self.repo, check=True)
        denied_state = self.base / "unrelated-child.json"
        denied = self.run_cli(
            "init", str(denied_state), "--run-id", "unrelated-child",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text(encoding="utf-8")),
            "--source-head", unrelated,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "unrelated-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(predecessor),
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("not based on the accepted predecessor source", denied.stderr)

    def test_attempt_binding_and_post_start_recheck_reject_closed_attempt(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("attempt-binding")
        attempt = "bound-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt).returncode,
            0,
        )
        mismatched_lifecycle = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": "different-attempt",
            "current_manifest_digest": "1" * 64,
            "current_patch_digest": "2" * 64,
            "correction_round": 0,
            "candidate_generations": 1,
            "phase": "applied",
            "focused_required": False,
            "focused_validation_count": 0,
            "authoritative_validation_count": 1,
            "parent_review_rejections": 0,
        }
        lifecycle_content = json.dumps(mismatched_lifecycle, sort_keys=True, indent=2) + "\n"
        lifecycle.write_text(lifecycle_content, encoding="utf-8")
        mismatch = self.close_writable_attempt(
            state, lifecycle, run_id, attempt,
            invariant=digest("one invariant"), outcome="rejected",
            reason="integration_contract_mismatch", candidate="sha256:" + "1" * 64,
            lifecycle_digest=digest(lifecycle_content),
        )
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("attempt identity mismatch", mismatch.stderr)

        lifecycle.unlink()
        closed = self.close_writable_attempt(
            state, lifecycle, run_id, attempt,
            invariant=digest("one invariant"), outcome="correction_requested",
            reason="evidence_incomplete",
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        post_close = self.run_cli(
            "check", str(state), "--run-id", run_id,
            "--plan", self.plan.relative_to(self.repo).as_posix(),
            "--lifecycle-state", str(lifecycle),
            "--open-attempt-id", attempt,
        )
        self.assertNotEqual(post_close.returncode, 0)
        self.assertIn("no longer the exact open writable attempt", post_close.stderr)

    def test_accepted_close_rejects_a_multi_commit_cumulative_patch(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("multi-commit")
        attempt = "multi-commit-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt).returncode,
            0,
        )
        baseline = json.loads(state.read_text(encoding="utf-8"))["source_head"]
        (self.repo / "temporary-extra.txt").write_text("temporary\n", encoding="utf-8")
        subprocess.run(["git", "add", "temporary-extra.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "temporary intermediate"], cwd=self.repo, check=True)
        (self.repo / "temporary-extra.txt").unlink()
        (self.repo / "allowed.txt").write_text("accepted candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate after revert"], cwd=self.repo, check=True)
        accepted_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        patch = subprocess.check_output(
            ["git", "diff", "--binary", "--full-index", baseline, accepted_head, "--"],
            cwd=self.repo,
        )
        patch_digest = hashlib.sha256(patch).hexdigest()
        state_payload = json.loads(state.read_text(encoding="utf-8"))
        manifest = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt,
            "plan_path": state_payload["plan_path"],
            "plan_digest": state_payload["plan_digest"].removeprefix("sha256:"),
            "source_head": baseline,
            "patch_digest": patch_digest,
        }
        manifest_content = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        manifest_path = self.base / "multi-commit-manifest.json"
        manifest_path.write_text(manifest_content, encoding="utf-8")
        candidate = digest(manifest_content)
        lifecycle_digest = self.write_applied_lifecycle(
            lifecycle, run_id, attempt, candidate, patch_digest
        )
        denied = self.run_cli(
            "close", str(state), "--run-id", run_id,
            "--attempt-id", attempt, "--outcome", "accepted",
            "--review-author", "parent",
            "--review-evidence-digest", digest("multi-commit-review"),
            "--invariant-digest", digest("one invariant"),
            "--candidate-digest", candidate,
            "--candidate-manifest", str(manifest_path),
            "--candidate-lifecycle-digest", lifecycle_digest,
            "--accepted-source-head", accepted_head,
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("exactly one non-merge commit", denied.stderr)

    def test_runner_consumes_exact_predecessor_proof_before_prerequisites(self) -> None:
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.invalid/test/repo.git"],
            cwd=self.repo, check=True,
        )
        predecessor, _, _ = self.accepted_execution("runner-predecessor")
        child_state, child_lifecycle, child_run = self.initialize_execution(
            "runner-child", plan=self.child_plan, predecessor=predecessor
        )
        result = subprocess.run(
            [
                sys.executable, str(RUNNER), "run",
                self.child_plan.relative_to(self.repo).as_posix(),
                "--orchestration-run-id", child_run,
                "--lifecycle-state", str(child_lifecycle),
                "--plan-execution-state", str(child_state),
                "--predecessor-plan-execution-state", str(predecessor),
                "--bwrap-bin", "definitely-missing-bwrap",
            ],
            cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("definitely-missing-bwrap", result.stderr)
        child_payload = json.loads(child_state.read_text(encoding="utf-8"))
        self.assertTrue(child_payload["open_attempt_id"])
        predecessor_payload = json.loads(predecessor.read_text(encoding="utf-8"))
        self.assertTrue(predecessor_payload["successor_claim_digest"])

    def test_atomic_ledger_replace_fsyncs_file_and_parent_directory(self) -> None:
        target = self.base / "durable-state.json"
        observed_modes: list[int] = []
        original_fsync = STATE_MODULE.os.fsync

        def tracked_fsync(descriptor: int) -> None:
            observed_modes.append(os.fstat(descriptor).st_mode)
            original_fsync(descriptor)

        with mock.patch.object(STATE_MODULE.os, "fsync", side_effect=tracked_fsync):
            STATE_MODULE.atomic_write(target, {"durable": True})
        self.assertTrue(any(stat.S_ISREG(mode) for mode in observed_modes))
        self.assertTrue(any(stat.S_ISDIR(mode) for mode in observed_modes))

    def test_review_sequencing_fixtures_keep_tuned_and_holdout_boundaries(self) -> None:
        fixture = json.loads(SEQUENCING_SCENARIOS.read_text(encoding="utf-8"))
        holdout = json.loads(SEQUENCING_HOLDOUT.read_text(encoding="utf-8"))
        self.assertIs(fixture["used_for_tuning"], True)
        self.assertEqual(len(fixture["requirements"]), 4)
        scenario_ids = {scenario["id"] for scenario in fixture["scenarios"]}
        self.assertEqual(len(scenario_ids), 15)
        self.assertIn("negative-global-lock-or-shared-write", scenario_ids)
        self.assertIs(holdout["used_for_tuning"], False)
        self.assertEqual(
            holdout["scenarios"][0]["expected"], "dependent_start_rejected"
        )

    def source_path_for_runner(self) -> str:
        return self.plan.relative_to(self.repo).as_posix()


if __name__ == "__main__":
    unittest.main()
