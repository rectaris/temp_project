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
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
STATE_SCRIPT = ROOT / "scripts/plan-execution-state.py"
GROUP_SCRIPT = ROOT / "scripts/parallel-plan-state.py"
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


def digest(value: str | bytes) -> str:
    data = value.encode() if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(data).hexdigest()


class PlanExecutionStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True)
        (self.repo / ".git/info/exclude").write_text(".agent-logs/\n", encoding="utf-8")
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
        self.registry = self.base / "reviewer-registry.jsonl"
        self.continuation_registry = self.base / "epoch-registry.jsonl"
        self.review_manifests: dict[Path, Path] = {}
        self.run_cli("registry-init", "--output", str(self.registry), check=True)
        self.run_cli(
            "continuation-registry-init",
            "--output",
            str(self.continuation_registry),
            check=True,
        )
        self.run_cli("init", str(self.state), "--run-id", "run-1", "--plan", "docs/plan/active/001-test.md",
                 "--plan-digest", digest(self.plan.read_text()), "--source-head", self.head,
                 "--primary-invariant-digest", digest("one invariant"), "--lifecycle-state", str(self.lifecycle),
                 "--implementation-mode", "candidate", check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        command = list(arguments)
        if (
            command
            and command[0] in {"review", "checkpoint"}
            and "--reviewer-registry" not in command
        ):
            command.extend(["--reviewer-registry", str(self.registry)])
        if (
            command
            and command[0] in {"init", "start"}
            and "--predecessor-checkpoint" in command
            and "--reviewer-registry" not in command
        ):
            command.extend(["--reviewer-registry", str(self.registry)])
        return subprocess.run(
            [sys.executable, str(STATE_SCRIPT), *command], cwd=self.repo, check=check,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def run_candidate_review(
        self,
        state: Path,
        lifecycle: Path,
        run_id: str,
        event_id: str,
        receipt: Path,
        manifest: Path,
        invariant: str,
        *,
        finding_severities: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        candidate_digest = digest(manifest.read_bytes())
        target = f"sha256:{payload['patch_digest']}"
        worker_receipt_digest = digest(f"worker receipt:{candidate_digest}")
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        receipt_payload["worker_receipt_digests"] = [worker_receipt_digest]
        packet = {
            key: receipt_payload[key]
            for key in (
                "plan_digest", "review_target_digest", "admitted_diff_digest",
                "worker_receipt_digests", "applicable_specification_digests",
            )
        }
        receipt_payload["packet_digest"] = STATE_MODULE.canonical_digest(packet)
        review_manifest = self.review_manifests[receipt]
        review_manifest_payload = json.loads(review_manifest.read_text(encoding="utf-8"))
        event_path = review_manifest.parent / review_manifest_payload["hook_event_log"]
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        events[-1]["payload"]["review_packet_digest"] = receipt_payload["packet_digest"]
        event_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in events),
            encoding="utf-8",
        )
        evidence_digest = digest(event_path.read_bytes())
        review_manifest_payload["resource_observations"]["evidence_digests"][
            "codex_hooks"
        ] = evidence_digest
        review_manifest.write_text(json.dumps(review_manifest_payload), encoding="utf-8")
        receipt_payload["inheritance_evidence_digest"] = evidence_digest
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        identity = STATE_MODULE.review_candidate_identity_digest(
            payload["plan_execution_attempt_id"], candidate_digest, target
        )
        args = SimpleNamespace(
            state=str(state),
            run_id=run_id,
            event_id=event_id,
            implementation_mode="candidate",
            review_receipt=str(receipt),
            candidate_manifest=str(manifest),
            predecessor_state=None,
            predecessor_checkpoint=None,
            reviewer_registry=str(self.registry),
            invariant_digest=[invariant],
            finding_severity=finding_severities,
            lifecycle_state=str(lifecycle),
            elapsed_seconds=0.0,
            review_resource_manifest=str(self.review_manifests[receipt]),
        )
        try:
            with (
                mock.patch.object(STATE_MODULE, "repository_root", return_value=self.repo),
                mock.patch.object(
                    STATE_MODULE,
                    "candidate_review_identity",
                    return_value=(
                        target,
                        identity,
                        payload["plan_execution_attempt_id"],
                        candidate_digest,
                        [worker_receipt_digest],
                    ),
                ),
            ):
                STATE_MODULE.record_bounded_review(args)
        except (OSError, UnicodeError, STATE_MODULE.StateError) as exc:
            return subprocess.CompletedProcess([], 1, "", f"{exc}\n")
        return subprocess.CompletedProcess([], 0, "", "")

    def append_candidate_review_fixture(
        self,
        state: Path,
        lifecycle: Path,
        run_id: str,
        attempt_id: str,
        candidate_digest: str,
        patch_digest: str,
        invariant: str,
        *,
        label: str | None = None,
        finding_severities: list[str] | None = None,
    ) -> None:
        target = f"sha256:{patch_digest}"
        event_label = label or attempt_id
        STATE_MODULE.record_event(SimpleNamespace(
            state=str(state),
            run_id=run_id,
            event_id=f"fixture-review:{event_label}",
            event_type="parent_review",
            implementation_mode="candidate",
            invariant_digest=[invariant],
            finding_severity=finding_severities,
            independent_review_receipt_digest=digest(f"fixture-receipt:{event_label}"),
            repair_evidence_file=None,
            validation_report=None,
            diagnosis_evidence_file=None,
            candidate_lifecycle_digest=STATE_MODULE.review_candidate_identity_digest(
                attempt_id, candidate_digest, target
            ),
            review_target_digest=target,
            review_attempt_id=attempt_id,
            review_candidate_digest=candidate_digest,
            lifecycle_state=str(lifecycle),
            elapsed_seconds=0.0,
        ))

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

    def resource_manifest(
        self,
        label: str,
        *,
        observed_session: bool = True,
        session: str = "source-session",
        review_packet_digest: str | None = None,
        inherited_turns: int = 0,
    ) -> Path:
        run_dir = self.repo / ".agent-logs" / label
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)
        event_path = raw_dir / "events.jsonl"
        event = {
            "schema_version": 1,
            "event": "SessionStart",
            "created_at": "2026-08-23T00:00:00Z",
            "cwd": str(self.repo),
            "payload": {"session_id": session} if observed_session else {},
        }
        events = [event]
        if review_packet_digest is not None:
            events.append({
                "schema_version": 1,
                "event": "ReviewPacketStart",
                "created_at": "2026-08-23T00:00:01Z",
                "cwd": str(self.repo),
                "payload": {
                    "session_id": session,
                    "hook_event_name": "ReviewPacketStart",
                    "review_packet_digest": review_packet_digest,
                    "inherited_turns": inherited_turns,
                },
            })
        event_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in events),
            encoding="utf-8",
        )
        evidence_digest = "sha256:" + hashlib.sha256(event_path.read_bytes()).hexdigest()
        (run_dir / "redaction-report.md").write_text(
            "# Redaction Report\n",
            encoding="utf-8",
        )
        metrics = {
            name: {
                "status": "not_observed",
                "value": None,
                "provenance": "not_observed",
            }
            for name in STATE_MODULE.RESOURCE_METRICS
        }
        metrics["tool_call_count"] = {
            "status": "observed",
            "value": 3,
            "provenance": "deterministic_proxy",
        }
        path = run_dir / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": label,
                    "created_at": "2026-08-23T00:00:00Z",
                    "task": "test resource evidence",
                    "plans": [],
                    "raw_logs": ["raw/events.jsonl"],
                    "artifacts": [],
                    "compressed_outputs": [],
                    "redaction_report": "redaction-report.md",
                    "pinned": False,
                    "transcript_log": None,
                    "hook_event_log": "raw/events.jsonl",
                    "coverage": {
                        "external_transcript": {
                            "present": False,
                            "path": None,
                            "status": "missing",
                            "redaction_status": "not_applicable",
                        },
                        "codex_hooks": {
                            "present": True,
                            "path": "raw/events.jsonl",
                            "status": "present",
                            "redaction_status": "automatic_redaction",
                        },
                    },
                    "missing_sources": ["external_transcript"],
                    "resource_observations": {
                        "schema_version": 1,
                        "root_session_identity": (
                            {"status": "observed", "digest": digest(session)}
                            if observed_session
                            else {"status": "not_observed", "digest": None}
                        ),
                        "evidence_digests": {
                            "external_transcript": None,
                            "codex_hooks": evidence_digest,
                        },
                        "metrics": metrics,
                    }
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_resource_identity_must_match_bound_runtime_evidence(self) -> None:
        path = self.resource_manifest("forged-identity", session="observed-session")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["resource_observations"]["root_session_identity"]["digest"] = digest(
            "fabricated-session"
        )
        path.write_text(json.dumps(manifest), encoding="utf-8")

        with (
            mock.patch.object(STATE_MODULE, "repository_root", return_value=self.repo),
            self.assertRaisesRegex(
                STATE_MODULE.StateError,
                "does not match bound runtime evidence",
            ),
        ):
            STATE_MODULE.resource_observations_from_manifest(path)

    def test_resource_evidence_change_after_manifest_check_is_rejected(self) -> None:
        path = self.resource_manifest("changed-evidence", session="observed-session")
        event_path = path.parent / "raw/events.jsonl"

        def mutate_evidence(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            event_path.write_text(
                event_path.read_text(encoding="utf-8")
                + json.dumps({"payload": {"session_id": "replacement-session"}})
                + "\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with (
            mock.patch.object(STATE_MODULE, "repository_root", return_value=self.repo),
            mock.patch.object(STATE_MODULE.subprocess, "run", side_effect=mutate_evidence),
            self.assertRaisesRegex(
                STATE_MODULE.StateError,
                "evidence digest changed after manifest validation",
            ),
        ):
            STATE_MODULE.resource_observations_from_manifest(path)

    def review_receipt(
        self,
        label: str,
        plan_digest: str,
        *,
        round_value: int,
        inherited_turns: int = 0,
        reviewer_session: str | None = None,
        review_target: str | None = None,
        source_head: str | None = None,
    ) -> Path:
        target_digest = review_target or digest(
            subprocess.check_output(
                [
                    "git", "diff", "--binary", "--full-index",
                    source_head or self.head, "--", "allowed.txt",
                ],
                cwd=self.repo,
            )
        )
        packet = {
            "plan_digest": plan_digest,
            "review_target_digest": target_digest,
            "admitted_diff_digest": target_digest,
            "worker_receipt_digests": [],
            "applicable_specification_digests": [
                digest((self.repo / "AGENTS.md").read_bytes())
            ],
        }
        receipt = {
            "schema_version": 1,
            **packet,
            "reviewer_session_digest": digest(reviewer_session or label),
            "inherited_turns": inherited_turns,
            "inheritance_evidence": "observed",
            "inheritance_evidence_digest": "",
            "review_round": round_value,
            "packet_digest": STATE_MODULE.canonical_digest(packet),
        }
        review_manifest = self.resource_manifest(
            f"{label}-review-runtime",
            session=reviewer_session or label,
            review_packet_digest=receipt["packet_digest"],
            inherited_turns=inherited_turns,
        )
        review_manifest_payload = json.loads(review_manifest.read_text(encoding="utf-8"))
        receipt["inheritance_evidence_digest"] = review_manifest_payload[
            "resource_observations"
        ]["evidence_digests"]["codex_hooks"]
        path = self.base / f"{label}-review.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.review_manifests[path] = review_manifest
        return path

    def rebind_review_runtime(self, receipt: Path) -> None:
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        review_manifest = self.review_manifests[receipt]
        manifest_payload = json.loads(review_manifest.read_text(encoding="utf-8"))
        event_path = review_manifest.parent / manifest_payload["hook_event_log"]
        events = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        events[-1]["payload"]["review_packet_digest"] = receipt_payload["packet_digest"]
        event_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in events),
            encoding="utf-8",
        )
        evidence_digest = digest(event_path.read_bytes())
        manifest_payload["resource_observations"]["evidence_digests"][
            "codex_hooks"
        ] = evidence_digest
        review_manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
        receipt_payload["inheritance_evidence_digest"] = evidence_digest
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")

    def test_event_implementation_mode_must_match_ledger_mode(self) -> None:
        mismatched = self.record("wrong-mode", "elapsed_checkpoint", mode="parent_direct")
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("implementation mode differs", mismatched.stderr)
        self.assertEqual(self.payload()["events"], [])

    def test_session_checkpoint_requires_a_different_observed_root_and_is_claimed_once(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("checkpoint", mode="parent_direct")
        (self.repo / "allowed.txt").write_text("checkpoint candidate\n", encoding="utf-8")
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        recorded = self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "authoritative", "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest("authoritative\n"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        review = self.review_receipt(
            "checkpoint-review", digest(self.plan.read_text()), round_value=1
        )
        reviewed = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "checkpoint-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(review),
            "--review-resource-manifest", str(self.review_manifests[review]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "checkpoint candidate"], cwd=self.repo, check=True)
        checked_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        checkpoint = self.base / "session-checkpoint.json"
        created = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(checkpoint), "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("checkpoint")),
            "--review-receipt", str(review),
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(
            self.run_cli(
                "verify-checkpoint", str(checkpoint), "--state", str(state)
            ).returncode,
            0,
        )
        duplicate = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(self.base / "duplicate-checkpoint.json"),
            "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("duplicate-checkpoint")),
            "--review-receipt", str(review),
        )
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("already emitted", duplicate.stderr)

        same_state = self.base / "same-session.json"
        same = self.run_cli(
            "init", str(same_state), "--run-id", "same-session",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text()),
            "--source-head", checked_head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "same-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(checkpoint),
            "--root-session-manifest", str(
                self.resource_manifest("same-session", session="source-session")
            ),
        )
        self.assertNotEqual(same.returncode, 0)
        self.assertIn("cannot start in the checkpointed root session", same.stderr)

        child_state = self.base / "fresh-session.json"
        child_lifecycle = self.base / "fresh-lifecycle.json"
        fresh = self.run_cli(
            "init", str(child_state), "--run-id", "fresh-session",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text()),
            "--source-head", checked_head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(checkpoint),
            "--root-session-manifest", str(
                self.resource_manifest("different-session", session="different-session")
            ),
        )
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        child_payload = json.loads(child_state.read_text(encoding="utf-8"))
        original_checkpoint = STATE_MODULE.read_session_checkpoint(checkpoint)
        STATE_MODULE.require_claimed_session_checkpoint(
            original_checkpoint,
            state,
            child_payload,
        )
        STATE_MODULE.append_checkpoint_event(
            child_payload,
            event_type="session_checkpoint_emitted",
            checkpoint=original_checkpoint,
        )
        STATE_MODULE.append_checkpoint_event(
            child_payload,
            event_type="session_checkpoint_claimed",
            checkpoint=original_checkpoint,
            successor={
                "run_id": "grandchild",
                "plan_digest": digest("grandchild plan"),
                "source_head": checked_head,
                "primary_invariant_digest": digest("grandchild invariant"),
                "genesis_digest": digest("grandchild genesis"),
            },
        )
        STATE_MODULE.validate_state(child_payload)
        alternate_registry = self.base / "alternate-registry.jsonl"
        self.run_cli("registry-init", "--output", str(alternate_registry), check=True)
        (self.repo / "allowed.txt").write_text("child review\n", encoding="utf-8")
        child_review = self.review_receipt(
            "child-without-checkpoint",
            digest(self.child_plan.read_text()),
            round_value=1,
            source_head=checked_head,
        )
        switched = self.run_cli(
            "review", str(child_state), "--run-id", "fresh-session",
            "--event-id", "child-without-checkpoint",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(child_review),
            "--review-resource-manifest", str(self.review_manifests[child_review]),
            "--reviewer-registry", str(alternate_registry),
            "--invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertNotEqual(switched.returncode, 0)
        self.assertIn("requires the predecessor state and session checkpoint", switched.stderr)
        (self.repo / "allowed.txt").write_text("checkpoint candidate\n", encoding="utf-8")
        forged_checkpoint = json.loads(checkpoint.read_text(encoding="utf-8"))
        forged_checkpoint["reviewer_registry"] = STATE_MODULE.reviewer_registry_reference(
            STATE_MODULE.read_reviewer_registry(alternate_registry)
        )
        forged_checkpoint["checkpoint_digest"] = STATE_MODULE.checkpoint_payload_digest(
            forged_checkpoint
        )
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "not claimed by this execution",
        ):
            STATE_MODULE.require_claimed_session_checkpoint(
                forged_checkpoint,
                state,
                child_payload,
            )

        replay = self.run_cli(
            "init", str(self.base / "replay.json"), "--run-id", "replay-session",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text()),
            "--source-head", checked_head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "replay-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(checkpoint),
            "--root-session-manifest", str(
                self.resource_manifest("third-session", session="third-session")
            ),
        )
        self.assertNotEqual(replay.returncode, 0)
        self.assertIn("already claimed", replay.stderr)

    def test_not_observed_checkpoint_and_proxy_token_claim_fail_closed(self) -> None:
        observations = json.loads(
            self.resource_manifest("invalid-proxy", observed_session=False).read_text()
        )["resource_observations"]
        observations["metrics"]["provider_input_tokens"] = {
            "status": "observed",
            "value": 10,
            "provenance": "deterministic_proxy",
        }
        with self.assertRaises(STATE_MODULE.StateError):
            STATE_MODULE.validate_resource_observations(observations)

        state, lifecycle, run_id = self.initialize_execution("unobserved", mode="parent_direct")
        (self.repo / "allowed.txt").write_text("unobserved candidate\n", encoding="utf-8")
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "authoritative", "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest("authoritative\n"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        review = self.review_receipt(
            "unobserved-review", digest(self.plan.read_text()), round_value=1
        )
        self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "unobserved-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(review),
            "--review-resource-manifest", str(self.review_manifests[review]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "unobserved candidate"], cwd=self.repo, check=True)
        checked_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        checkpoint = self.base / "unobserved-checkpoint.json"
        self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(checkpoint), "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("unobserved", observed_session=False)),
            "--review-receipt", str(review),
            check=True,
        )
        child = self.run_cli(
            "init", str(self.base / "blocked-child.json"), "--run-id", "blocked-child",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text()),
            "--source-head", checked_head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "blocked-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(checkpoint),
            "--root-session-manifest", str(
                self.resource_manifest("blocked-session", session="different-session")
            ),
        )
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("predecessor root-session identity is not observed", child.stderr)

    def test_bounded_review_requires_zero_inheritance_and_two_round_budget(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("bounded-review", mode="parent_direct")
        (self.repo / "allowed.txt").write_text("bounded candidate\n", encoding="utf-8")
        plan_digest = digest(self.plan.read_text())
        invariant = digest("one invariant")
        bad = self.review_receipt(
            "full-history", plan_digest, round_value=1, inherited_turns=4
        )
        rejected = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "bad-review", "--implementation-mode", "parent_direct",
            "--review-receipt", str(bad), "--invariant-digest", invariant,
            "--review-resource-manifest", str(self.review_manifests[bad]),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("zero inherited turns", rejected.stderr)

        for round_value in (1, 2):
            receipt = self.review_receipt(
                f"review-{round_value}", plan_digest, round_value=round_value
            )
            accepted = self.run_cli(
                "review", str(state), "--run-id", run_id,
                "--event-id", f"review-{round_value}",
                "--implementation-mode", "parent_direct",
                "--review-receipt", str(receipt), "--invariant-digest", invariant,
                "--review-resource-manifest", str(self.review_manifests[receipt]),
                "--lifecycle-state", str(lifecycle),
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
        third = self.review_receipt("review-3", plan_digest, round_value=2)
        exhausted = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "review-3", "--implementation-mode", "parent_direct",
            "--review-receipt", str(third), "--invariant-digest", invariant,
            "--review-resource-manifest", str(self.review_manifests[third]),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(exhausted.returncode, 0)
        self.assertIn("one initial review and one bounded rereview", exhausted.stderr)

        next_candidate = self.review_receipt(
            "next-candidate", plan_digest, round_value=1, review_target=digest("next-target")
        )
        restarted = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "next-candidate-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(next_candidate), "--invariant-digest", invariant,
            "--review-resource-manifest", str(self.review_manifests[next_candidate]),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(restarted.returncode, 0)
        self.assertIn("differs from the admitted candidate diff", restarted.stderr)

    def test_same_plan_continuation_requires_preflight_and_refuses_replay(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "continuation-source", mode="parent_direct", require_preflight=True
        )
        (self.repo / "allowed.txt").write_text("continued candidate\n", encoding="utf-8")
        plan_digest = digest(self.plan.read_text())
        invariant = digest("one invariant")
        source_target = digest(
            subprocess.check_output(
                [
                    "git", "diff", "--binary", "--full-index",
                    self.head, "--", "allowed.txt",
                ],
                cwd=self.repo,
            )
        )
        source_identity = STATE_MODULE.canonical_digest(
            {
                "implementation_mode": "parent_direct",
                "source_head": self.head,
                "admitted_diff_digest": source_target,
            }
        )
        source_preflight = self.base / "continuation-source-preflight.json"
        source_preflight.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "plan_digest": plan_digest,
                    "review_target_digest": source_target,
                    "review_identity_digest": source_identity,
                    "applicable_specification_digests": [
                        digest((self.repo / "AGENTS.md").read_bytes())
                    ],
                    "cases": [
                        {
                            "id": "source-target",
                            "result": "passed",
                            "evidence_digest": digest("source preflight"),
                        }
                    ],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        source_preflight.chmod(0o600)
        source_preflight_result = self.run_cli(
            "preflight", str(state), "--run-id", run_id,
            "--event-id", "continuation-source-preflight",
            "--implementation-mode", "parent_direct",
            "--preflight-evidence", str(source_preflight),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(
            source_preflight_result.returncode, 0, source_preflight_result.stderr
        )
        for round_value, severities in ((1, []), (2, ["Medium"])):
            receipt = self.review_receipt(
                f"continuation-source-{round_value}",
                plan_digest,
                round_value=round_value,
            )
            arguments = [
                "review", str(state), "--run-id", run_id,
                "--event-id", f"continuation-source-{round_value}",
                "--implementation-mode", "parent_direct",
                "--review-receipt", str(receipt),
                "--review-resource-manifest", str(self.review_manifests[receipt]),
                "--invariant-digest", invariant,
                "--lifecycle-state", str(lifecycle),
            ]
            for severity in severities:
                arguments.extend(("--finding-severity", severity))
            reviewed = self.run_cli(*arguments)
            self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        stopped_bytes = state.read_bytes()
        stopped = json.loads(stopped_bytes)
        self.assertEqual(stopped["state"], "descope_pending")

        registry = self.continuation_registry
        registry_header = json.loads(
            registry.read_text(encoding="utf-8").splitlines()[0]
        )
        child = self.base / "continuation-child.json"
        child_lifecycle = self.base / "continuation-child-lifecycle.json"
        child_run = "run-continuation-child"
        authorization = self.base / "continuation-authorization.json"
        authorization.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "plan_path": "docs/plan/active/001-test.md",
                    "plan_digest": plan_digest,
                    "source_head": self.head,
                    "primary_invariant_digest": invariant,
                    "implementation_mode": "parent_direct",
                    "predecessor_state_digest": digest(stopped_bytes),
                    "predecessor_run_id": run_id,
                    "predecessor_event_chain_digest": stopped["event_chain_digest"],
                    "next_epoch": 1,
                    "child_run_id": child_run,
                    "child_state_path_digest": digest(str(child.absolute())),
                    "continuation_registry_identity_digest": registry_header[
                        "genesis_digest"
                    ],
                    "cumulative_review_limit": 4,
                    "owner_authorization": "Continue this unchanged plan once.",
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        authorization.chmod(0o644)
        insecure = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(insecure.returncode, 0)
        self.assertIn("single-link mode-0600 regular file", insecure.stderr)
        authorization.chmod(0o600)
        copied_registry = self.base / "copied-continuation-registry.jsonl"
        shutil.copyfile(registry, copied_registry)
        copied_registry.chmod(0o600)
        copied = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(copied_registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(copied.returncode, 0)
        self.assertIn("identity mismatch", copied.stderr)
        hard_linked_authorization = self.base / "hard-linked-authorization.json"
        os.link(authorization, hard_linked_authorization)
        hard_linked = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(hard_linked_authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(hard_linked.returncode, 0)
        self.assertIn("single-link mode-0600 regular file", hard_linked.stderr)
        hard_linked_authorization.unlink()
        registry_before_invalid_run = registry.read_bytes()
        invalid_run = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", "invalid/run",
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(invalid_run.returncode, 0)
        self.assertEqual(registry.read_bytes(), registry_before_invalid_run)
        continued = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertEqual(continued.returncode, 0, continued.stderr)
        self.assertEqual(state.read_bytes(), stopped_bytes)
        child_payload = json.loads(child.read_text(encoding="utf-8"))
        epoch = child_payload["events"][0]["execution_epoch"]
        self.assertEqual(epoch["epoch"], 1)
        self.assertEqual(epoch["predecessor_review_count"], 2)
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "already continued",
        ):
            with mock.patch.object(
                STATE_MODULE, "repository_root", return_value=self.repo
            ):
                STATE_MODULE.consume_continuation_authorization(
                    registry,
                    plan_digest=plan_digest,
                    predecessor_state_digest=digest("checkpoint-advanced state"),
                    predecessor_run_id=run_id,
                    predecessor_genesis_digest=stopped["genesis_digest"],
                    predecessor_event_chain_digest=digest(
                        "checkpoint-advanced event chain"
                    ),
                    authorization_digest=digest(authorization.read_bytes()),
                    child_run_id="run-continuation-after-checkpoint",
                    child_state_path_digest=digest(
                        str(
                            (
                                self.base
                                / "continuation-after-checkpoint.json"
                            ).absolute()
                        )
                    ),
                    child_genesis_digest=digest("another child genesis"),
                    expected_registry_identity_digest=registry_header[
                        "genesis_digest"
                    ],
                )
        registry_before_wrong_identity = registry.read_bytes()
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "differs from the predecessor execution",
        ):
            with mock.patch.object(
                STATE_MODULE, "repository_root", return_value=self.repo
            ):
                STATE_MODULE.consume_continuation_authorization(
                    registry,
                    plan_digest=plan_digest,
                    predecessor_state_digest=digest("other state"),
                    predecessor_run_id="run-other-predecessor",
                    predecessor_genesis_digest=digest("other predecessor genesis"),
                    predecessor_event_chain_digest=digest("other event chain"),
                    authorization_digest=digest("other authorization"),
                    child_run_id="run-other-child",
                    child_state_path_digest=digest("other child path"),
                    child_genesis_digest=digest("other child genesis"),
                    expected_registry_identity_digest=digest("wrong registry"),
                )
        self.assertEqual(registry.read_bytes(), registry_before_wrong_identity)
        child.unlink()
        recovered = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        repeated = self.run_cli(
            "continue", str(child),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        forked_path = self.run_cli(
            "continue", str(self.base / "same-child-different-state.json"),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(forked_path.returncode, 0)
        self.assertIn("authorization differs", forked_path.stderr)
        reformatted_predecessor = self.base / "reformatted-predecessor.json"
        reformatted_predecessor.write_text(
            json.dumps(stopped, sort_keys=True, indent=4) + "\n",
            encoding="utf-8",
        )
        reformatted = self.run_cli(
            "continue", str(self.base / "reformatted-child.json"),
            "--predecessor-state", str(reformatted_predecessor),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", child_run,
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(reformatted.returncode, 0)
        self.assertIn("not canonical", reformatted.stderr)
        rogue_registry = self.base / "rogue-continuation-registry.jsonl"
        rogue_initialized = self.run_cli(
            "continuation-registry-init", "--output", str(rogue_registry)
        )
        self.assertEqual(rogue_initialized.returncode, 0, rogue_initialized.stderr)
        rogue_header = json.loads(
            rogue_registry.read_text(encoding="utf-8").splitlines()[0]
        )
        rogue_authorization = self.base / "rogue-continuation-authorization.json"
        rogue_payload = json.loads(authorization.read_text(encoding="utf-8"))
        rogue_payload["child_run_id"] = "run-continuation-rogue"
        rogue_payload["child_state_path_digest"] = digest(
            str((self.base / "continuation-rogue.json").absolute())
        )
        rogue_payload["continuation_registry_identity_digest"] = rogue_header[
            "genesis_digest"
        ]
        rogue_authorization.write_text(
            json.dumps(rogue_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rogue_authorization.chmod(0o600)
        rogue = self.run_cli(
            "continue", str(self.base / "continuation-rogue.json"),
            "--predecessor-state", str(state),
            "--continuation-registry", str(rogue_registry),
            "--authorization", str(rogue_authorization),
            "--run-id", "run-continuation-rogue",
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(self.base / "continuation-rogue-lifecycle.json"),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(rogue.returncode, 0)
        self.assertIn("differs from the predecessor execution", rogue.stderr)

        receipt = self.review_receipt(
            "continuation-child-review", plan_digest, round_value=1
        )
        blocked = self.run_cli(
            "review", str(child), "--run-id", child_run,
            "--event-id", "continuation-child-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", invariant,
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("requires a passing adversarial preflight", blocked.stderr)

        target = digest(
            subprocess.check_output(
                [
                    "git", "diff", "--binary", "--full-index",
                    self.head, "--", "allowed.txt",
                ],
                cwd=self.repo,
            )
        )
        identity = STATE_MODULE.canonical_digest(
            {
                "implementation_mode": "parent_direct",
                "source_head": self.head,
                "admitted_diff_digest": target,
            }
        )
        evidence = self.base / "continuation-preflight.json"
        evidence.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "plan_digest": plan_digest,
                    "review_target_digest": target,
                    "review_identity_digest": identity,
                    "applicable_specification_digests": [
                        digest((self.repo / "AGENTS.md").read_bytes())
                    ],
                    "cases": [
                        {
                            "id": "stopped-ledger-immutable",
                            "result": "passed",
                            "evidence_digest": digest("preflight result"),
                        }
                    ],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        evidence.chmod(0o600)
        preflight = self.run_cli(
            "preflight", str(child), "--run-id", child_run,
            "--event-id", "continuation-preflight",
            "--implementation-mode", "parent_direct",
            "--preflight-evidence", str(evidence),
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertEqual(preflight.returncode, 0, preflight.stderr)
        reviewed = self.run_cli(
            "review", str(child), "--run-id", child_run,
            "--event-id", "continuation-child-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", invariant,
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)

        replay_authorization = self.base / "continuation-replay.json"
        replay_payload = json.loads(authorization.read_text(encoding="utf-8"))
        replay_payload["child_run_id"] = "run-continuation-fork"
        replay_payload["child_state_path_digest"] = digest(
            str((self.base / "continuation-fork.json").absolute())
        )
        replay_authorization.write_text(
            json.dumps(replay_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        replay_authorization.chmod(0o600)
        replayed = self.run_cli(
            "continue", str(self.base / "continuation-fork.json"),
            "--predecessor-state", str(state),
            "--continuation-registry", str(registry),
            "--authorization", str(replay_authorization),
            "--run-id", "run-continuation-fork",
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(self.base / "continuation-fork-lifecycle.json"),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(replayed.returncode, 0)
        self.assertIn("already continued", replayed.stderr)

        second_receipt = self.review_receipt(
            "continuation-child-review-2", plan_digest, round_value=2
        )
        second_review = self.run_cli(
            "review", str(child), "--run-id", child_run,
            "--event-id", "continuation-child-review-2",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(second_receipt),
            "--review-resource-manifest", str(self.review_manifests[second_receipt]),
            "--invariant-digest", invariant,
            "--finding-severity", "Medium",
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertEqual(second_review.returncode, 0, second_review.stderr)
        exhausted = self.run_cli(
            "continue", str(self.base / "continuation-epoch-2.json"),
            "--predecessor-state", str(child),
            "--continuation-registry", str(registry),
            "--authorization", str(authorization),
            "--run-id", "run-continuation-epoch-2",
            "--plan", "docs/plan/active/001-test.md",
            "--lifecycle-state", str(self.base / "continuation-epoch-2-lifecycle.json"),
            "--implementation-mode", "parent_direct",
        )
        self.assertNotEqual(exhausted.returncode, 0)
        self.assertIn("epoch limit is exhausted", exhausted.stderr)

    def test_preflight_is_bound_to_the_exact_current_target(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "preflight-target",
            mode="parent_direct",
            require_preflight=True,
        )
        (self.repo / "allowed.txt").write_text("first target\n", encoding="utf-8")
        payload = json.loads(state.read_text(encoding="utf-8"))
        target = digest(
            subprocess.check_output(
                [
                    "git", "diff", "--binary", "--full-index",
                    self.head, "--", "allowed.txt",
                ],
                cwd=self.repo,
            )
        )
        identity = STATE_MODULE.canonical_digest(
            {
                "implementation_mode": "parent_direct",
                "source_head": self.head,
                "admitted_diff_digest": target,
            }
        )
        evidence = self.base / "preflight-target.json"
        evidence.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "plan_digest": digest(self.plan.read_text()),
                    "review_target_digest": target,
                    "review_identity_digest": identity,
                    "applicable_specification_digests": [
                        digest((self.repo / "AGENTS.md").read_bytes())
                    ],
                    "cases": [
                        {
                            "id": "target-one",
                            "result": "passed",
                            "evidence_digest": digest("target one"),
                        }
                    ],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        evidence.chmod(0o600)
        recorded = self.run_cli(
            "preflight", str(state), "--run-id", run_id,
            "--event-id", "target-one",
            "--implementation-mode", "parent_direct",
            "--preflight-evidence", str(evidence),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        tampered = json.loads(state.read_text(encoding="utf-8"))
        preflight_event = tampered["events"][-1]
        preflight_event["preflight_evidence_digest"] = digest("forged evidence")
        preflight_event["event_digest"] = STATE_MODULE.canonical_digest(
            {
                key: preflight_event[key]
                for key in preflight_event
                if key != "event_digest"
            }
        )
        tampered["event_chain_digest"] = preflight_event["event_digest"]
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "preflight evidence digest mismatch",
        ):
            STATE_MODULE.validate_state(tampered)
        forged = self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "forged-preflight",
            "--event-type", "adversarial_preflight",
            "--implementation-mode", "parent_direct",
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(forged.returncode, 0)
        policy = self.repo / "AGENTS.md"
        original_policy = policy.read_text(encoding="utf-8")
        policy.write_text("changed policy\n", encoding="utf-8")
        changed_spec_receipt = self.review_receipt(
            "preflight-changed-spec",
            digest(self.plan.read_text()),
            round_value=1,
        )
        changed_spec = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "changed-spec-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(changed_spec_receipt),
            "--review-resource-manifest",
            str(self.review_manifests[changed_spec_receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(changed_spec.returncode, 0)
        self.assertIn(
            "specifications differ from adversarial preflight",
            changed_spec.stderr,
        )
        policy.write_text(original_policy, encoding="utf-8")
        (self.repo / "allowed.txt").write_text("second target\n", encoding="utf-8")
        receipt = self.review_receipt(
            "preflight-stale-target",
            digest(self.plan.read_text()),
            round_value=1,
        )
        stale = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "stale-preflight-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("requires a passing adversarial preflight", stale.stderr)

    def test_candidate_preflight_binds_admitted_candidate_identity(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "candidate-preflight",
            mode="candidate",
            require_preflight=True,
        )
        attempt_id = "candidate-preflight-attempt"
        started = self.start_writable_attempt(
            state, lifecycle, run_id, attempt_id
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        manifest = self.base / "candidate-preflight-manifest.json"
        manifest.write_text("{}\n", encoding="utf-8")
        target = digest("candidate patch")
        candidate_digest = digest(manifest.read_bytes())
        identity = STATE_MODULE.review_candidate_identity_digest(
            attempt_id, candidate_digest, target
        )
        evidence = self.base / "candidate-preflight-evidence.json"
        evidence.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "plan_digest": digest(self.plan.read_text()),
                    "review_target_digest": target,
                    "review_identity_digest": identity,
                    "applicable_specification_digests": [
                        digest((self.repo / "AGENTS.md").read_bytes())
                    ],
                    "cases": [
                        {
                            "id": "candidate-identity",
                            "result": "passed",
                            "evidence_digest": digest("candidate evidence"),
                        }
                    ],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        evidence.chmod(0o600)
        args = SimpleNamespace(
            state=str(state),
            run_id=run_id,
            event_id="candidate-preflight",
            implementation_mode="candidate",
            preflight_evidence=str(evidence),
            candidate_manifest=str(manifest),
            lifecycle_state=str(lifecycle),
        )
        with (
            mock.patch.object(STATE_MODULE, "repository_root", return_value=self.repo),
            mock.patch.object(
                STATE_MODULE,
                "candidate_review_identity",
                return_value=(
                    target,
                    identity,
                    attempt_id,
                    candidate_digest,
                    [digest("worker receipt")],
                ),
            ),
        ):
            STATE_MODULE.record_adversarial_preflight(args)
        payload = json.loads(state.read_text(encoding="utf-8"))
        event = payload["events"][-1]
        self.assertEqual(event["event_type"], "adversarial_preflight")
        self.assertEqual(event["attempt_id"], attempt_id)
        self.assertEqual(event["candidate_digest"], candidate_digest)
        self.assertEqual(event["candidate_lifecycle_digest"], identity)

    def test_reviewer_registry_is_required_for_review_and_checkpoint(self) -> None:
        review = subprocess.run(
            [
                sys.executable, str(STATE_SCRIPT), "review", str(self.state),
                "--run-id", "run-1", "--event-id", "missing-registry",
                "--implementation-mode", "candidate",
                "--review-receipt", "missing-receipt",
                "--review-resource-manifest", "missing-manifest",
                "--candidate-manifest", "missing-candidate",
                "--invariant-digest", digest("one invariant"),
                "--lifecycle-state", str(self.lifecycle),
            ],
            cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(review.returncode, 0)
        self.assertIn("--reviewer-registry", review.stderr)

        checkpoint = subprocess.run(
            [
                sys.executable, str(STATE_SCRIPT), "checkpoint", str(self.state),
                "--run-id", "run-1", "--output", str(self.base / "missing.json"),
                "--boundary", "checked", "--resource-manifest", "missing-manifest",
            ],
            cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(checkpoint.returncode, 0)
        self.assertIn("--reviewer-registry", checkpoint.stderr)

    def test_reviewer_registry_supports_long_chains_and_rejects_copies(self) -> None:
        for index in range(80):
            STATE_MODULE.admit_reviewer_session(
                self.registry,
                reviewer_session_digest=digest(f"reviewer-{index}"),
                plan_digest=digest(f"plan-{index}"),
                run_id=f"run-{index}",
                event_id=f"review-{index}",
                execution_genesis_digest=digest(f"genesis-{index}"),
                review_receipt_digest=digest(f"receipt-{index}"),
                predecessor_reference=None,
            )
        registry = STATE_MODULE.read_reviewer_registry(self.registry)
        self.assertEqual(len(registry["events"]), 80)
        self.assertEqual(
            STATE_MODULE.reviewer_registry_reference(registry)["event_count"],
            80,
        )

        copied = self.base / "copied-registry.jsonl"
        shutil.copyfile(self.registry, copied)
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "copied to another path",
        ):
            STATE_MODULE.read_reviewer_registry(copied)

    def test_reviewer_registry_recovers_an_admission_without_a_ledger_event(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "registry-crash-recovery", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("registry recovery\n", encoding="utf-8")
        receipt = self.review_receipt(
            "registry-recovery",
            digest(self.plan.read_text()),
            round_value=1,
        )
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        state_payload = json.loads(state.read_text(encoding="utf-8"))
        STATE_MODULE.admit_reviewer_session(
            self.registry,
            reviewer_session_digest=receipt_payload["reviewer_session_digest"],
            plan_digest=digest(self.plan.read_text()),
            run_id=run_id,
            event_id="registry-recovery",
            execution_genesis_digest=state_payload["genesis_digest"],
            review_receipt_digest=digest(receipt.read_bytes()),
            predecessor_reference=None,
        )
        recovered = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "registry-recovery",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        registry = STATE_MODULE.read_reviewer_registry(self.registry)
        self.assertEqual(len(registry["events"]), 1)
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "reviewer session cannot be reused across numbered plans",
        ):
            STATE_MODULE.admit_reviewer_session(
                self.registry,
                reviewer_session_digest=receipt_payload["reviewer_session_digest"],
                plan_digest=digest(self.plan.read_text()),
                run_id=run_id,
                event_id="registry-recovery",
                execution_genesis_digest=digest("different-ledger-genesis"),
                review_receipt_digest=digest(receipt.read_bytes()),
                predecessor_reference=None,
            )

    def test_invalid_review_event_does_not_modify_the_registry(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "invalid-registry-event", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("invalid registry event\n", encoding="utf-8")
        receipt = self.review_receipt(
            "invalid-registry-event",
            digest(self.plan.read_text()),
            round_value=1,
        )
        rejected = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "invalid/event",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("invalid event_id", rejected.stderr)
        registry = STATE_MODULE.read_reviewer_registry(self.registry)
        self.assertEqual(registry["events"], [])

    def test_checkpoint_binds_registry_and_rejects_reviewer_reuse(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "registry-parent", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("registry parent\n", encoding="utf-8")
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "authoritative", "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest("authoritative\n"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        review = self.review_receipt(
            "registry-shared",
            digest(self.plan.read_text()),
            round_value=1,
            reviewer_session="shared-reviewer",
        )
        self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "registry-shared",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(review),
            "--review-resource-manifest", str(self.review_manifests[review]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "registry parent"], cwd=self.repo, check=True)
        checkpoint = self.base / "registry-checkpoint.json"
        self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(checkpoint), "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("registry-parent")),
            "--review-receipt", str(review),
            check=True,
        )
        checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(
            set(checkpoint_payload["reviewer_registry"]),
            STATE_MODULE.REVIEWER_REGISTRY_REFERENCE_KEYS,
        )
        self.assertNotIn("reviewer_session_digests", checkpoint_payload)

        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "reviewer session cannot be reused across numbered plans",
        ):
            STATE_MODULE.admit_reviewer_session(
                self.registry,
                reviewer_session_digest=digest("shared-reviewer"),
                plan_digest=digest(self.child_plan.read_text()),
                run_id="registry-child",
                event_id="registry-child-review",
                execution_genesis_digest=digest("registry-child-genesis"),
                review_receipt_digest=digest("child-receipt"),
                predecessor_reference=checkpoint_payload["reviewer_registry"],
            )

    def test_checkpoint_claim_rejects_a_registry_advanced_after_issuance(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "stale-registry-checkpoint", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("stale registry\n", encoding="utf-8")
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "authoritative", "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest("authoritative\n"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        review = self.review_receipt(
            "stale-registry-review",
            digest(self.plan.read_text()),
            round_value=1,
        )
        self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "stale-registry-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(review),
            "--review-resource-manifest", str(self.review_manifests[review]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "stale registry"], cwd=self.repo, check=True)
        checked_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        checkpoint = self.base / "stale-registry-checkpoint.json"
        self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(checkpoint), "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("stale-registry")),
            "--review-receipt", str(review),
            check=True,
        )
        STATE_MODULE.admit_reviewer_session(
            self.registry,
            reviewer_session_digest=digest("later-reviewer"),
            plan_digest=digest("later-plan"),
            run_id="later-run",
            event_id="later-review",
            execution_genesis_digest=digest("later-genesis"),
            review_receipt_digest=digest("later-receipt"),
            predecessor_reference=None,
        )
        rejected = self.run_cli(
            "init", str(self.base / "stale-child.json"),
            "--run-id", "stale-child",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text()),
            "--source-head", checked_head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "stale-child-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(checkpoint),
            "--root-session-manifest", str(
                self.resource_manifest("stale-child", session="stale-child")
            ),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("advanced or diverged", rejected.stderr)

    def test_normal_checkpoint_reserves_capacity_before_writing_output(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "checkpoint-capacity", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("checkpoint capacity\n", encoding="utf-8")
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "authoritative", "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest("authoritative\n"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        review = self.review_receipt(
            "checkpoint-capacity-review",
            digest(self.plan.read_text()),
            round_value=1,
        )
        self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "checkpoint-capacity-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(review),
            "--review-resource-manifest", str(self.review_manifests[review]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "checkpoint capacity"], cwd=self.repo, check=True)
        payload = json.loads(state.read_text(encoding="utf-8"))
        while len(payload["events"]) < STATE_MODULE.MAX_EVENTS - 2:
            last = payload["events"][-1]
            event = dict(payload["events"][0])
            sequence = len(payload["events"]) + 1
            event.update({
                "sequence": sequence,
                "event_id": f"capacity-padding-{sequence}",
                "event_type": "elapsed_checkpoint",
                "invariant_digests": [],
                "finding_severities": [],
                "independent_review_receipt_digest": "",
                "candidate_lifecycle_digest": "",
                "elapsed_seconds": 0.0,
                "monotonic_ns": last["monotonic_ns"] + 1,
                "previous_event_digest": last["event_digest"],
            })
            event["event_digest"] = digest(json.dumps(
                {key: value for key, value in event.items() if key != "event_digest"},
                sort_keys=True,
                separators=(",", ":"),
            ))
            payload["events"].append(event)
        payload["last_monotonic_ns"] = payload["events"][-1]["monotonic_ns"]
        payload["event_chain_digest"] = payload["events"][-1]["event_digest"]
        STATE_MODULE.validate_state(payload)
        state.write_text(json.dumps(payload), encoding="utf-8")
        output = self.base / "capacity-checkpoint.json"
        rejected = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(output), "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("checkpoint-capacity")),
            "--review-receipt", str(review),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("reserved event capacity", rejected.stderr)
        self.assertFalse(output.exists())

    def test_migration_compatibility_suffix_crosses_each_budget_boundary(self) -> None:
        sequence = [
            "session_checkpoint_migrated",
            "session_checkpoint_claimed",
            "successor_claimed",
        ]
        for migration_sequence in (62, 63, 64):
            with self.subTest(migration_sequence=migration_sequence):
                events = [
                    {"event_type": "elapsed_checkpoint"}
                    for _ in range(migration_sequence - 1)
                ]
                events.extend({"event_type": event_type} for event_type in sequence)
                STATE_MODULE.validate_event_budget(events)
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "compatibility suffix",
        ):
            STATE_MODULE.validate_event_budget(
                [{"event_type": "elapsed_checkpoint"} for _ in range(64)]
                + [{"event_type": "session_checkpoint_claimed"}]
            )

    def test_legacy_checkpoint_migrates_into_the_reviewer_registry(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "legacy-checkpoint", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("legacy checkpoint\n", encoding="utf-8")
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.run_cli(
            "record", str(state), "--run-id", run_id,
            "--event-id", "authoritative", "--event-type", "authoritative_validation",
            "--implementation-mode", "parent_direct",
            "--candidate-lifecycle-digest", digest("authoritative\n"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        review = self.review_receipt(
            "legacy-checkpoint-review",
            digest(self.plan.read_text()),
            round_value=1,
        )
        self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "legacy-checkpoint-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(review),
            "--review-resource-manifest", str(self.review_manifests[review]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
            check=True,
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "legacy checkpoint"], cwd=self.repo, check=True)
        current_checkpoint = self.base / "current-checkpoint.json"
        self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(current_checkpoint), "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("legacy-checkpoint")),
            "--review-receipt", str(review),
            check=True,
        )
        current = json.loads(current_checkpoint.read_text(encoding="utf-8"))
        legacy = {
            key: value for key, value in current.items()
            if key not in {"schema_version", "reviewer_registry", "checkpoint_digest"}
        }
        legacy["schema_version"] = 1
        legacy["reviewer_session_digests"] = [
            json.loads(review.read_text(encoding="utf-8"))["reviewer_session_digest"]
        ]
        legacy["checkpoint_digest"] = ""
        legacy["checkpoint_digest"] = STATE_MODULE.checkpoint_payload_digest(legacy)
        legacy_path = self.base / "legacy-checkpoint.json"
        legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

        state_payload = json.loads(state.read_text(encoding="utf-8"))
        issuance = state_payload["events"][-1]
        self.assertEqual(issuance["event_type"], "session_checkpoint_emitted")
        issuance["candidate_digest"] = legacy["checkpoint_digest"]
        issuance["review_target_digest"] = legacy["checkpoint_digest"]
        issuance["event_digest"] = digest(json.dumps(
            {key: value for key, value in issuance.items() if key != "event_digest"},
            sort_keys=True,
            separators=(",", ":"),
        ))
        prior_events = state_payload["events"][:-1]
        padded_events = list(prior_events)
        for index in range(
            len(prior_events) + 1,
            STATE_MODULE.MAX_EVENTS,
        ):
            elapsed = dict(prior_events[0])
            elapsed.update({
                "sequence": index,
                "event_id": f"legacy-padding-{index}",
                "event_type": "elapsed_checkpoint",
                "invariant_digests": [],
                "finding_severities": [],
                "independent_review_receipt_digest": "",
                "candidate_lifecycle_digest": "",
                "elapsed_seconds": 0.0,
                "monotonic_ns": padded_events[-1]["monotonic_ns"] + 1,
                "previous_event_digest": padded_events[-1]["event_digest"],
            })
            elapsed["event_digest"] = digest(json.dumps(
                {key: value for key, value in elapsed.items() if key != "event_digest"},
                sort_keys=True,
                separators=(",", ":"),
            ))
            padded_events.append(elapsed)
        legacy["execution_event_chain_digest"] = padded_events[-1]["event_digest"]
        legacy["checkpoint_digest"] = ""
        legacy["checkpoint_digest"] = STATE_MODULE.checkpoint_payload_digest(legacy)
        legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
        issuance["candidate_digest"] = legacy["checkpoint_digest"]
        issuance["review_target_digest"] = legacy["checkpoint_digest"]
        issuance["sequence"] = STATE_MODULE.MAX_EVENTS
        issuance["monotonic_ns"] = padded_events[-1]["monotonic_ns"] + 1
        issuance["previous_event_digest"] = padded_events[-1]["event_digest"]
        issuance["event_digest"] = digest(json.dumps(
            {key: value for key, value in issuance.items() if key != "event_digest"},
            sort_keys=True,
            separators=(",", ":"),
        ))
        padded_events.append(issuance)
        state_payload["events"] = padded_events
        state_payload["last_monotonic_ns"] = issuance["monotonic_ns"]
        state_payload["event_chain_digest"] = issuance["event_digest"]
        state.write_text(json.dumps(state_payload), encoding="utf-8")
        STATE_MODULE.validate_state(state_payload)

        claimed_state = self.base / "claimed-legacy-state.json"
        claimed_payload = json.loads(json.dumps(state_payload))
        claimed_issuance = dict(claimed_payload["events"][-1])
        claimed_payload["events"] = claimed_payload["events"][:2]
        claimed_legacy = dict(legacy)
        claimed_legacy["execution_event_chain_digest"] = claimed_payload["events"][-1][
            "event_digest"
        ]
        claimed_legacy["checkpoint_digest"] = ""
        claimed_legacy["checkpoint_digest"] = STATE_MODULE.checkpoint_payload_digest(
            claimed_legacy
        )
        claimed_legacy_path = self.base / "claimed-legacy-checkpoint.json"
        claimed_legacy_path.write_text(json.dumps(claimed_legacy), encoding="utf-8")
        claimed_issuance["sequence"] = 3
        claimed_issuance["monotonic_ns"] = (
            claimed_payload["events"][-1]["monotonic_ns"] + 1
        )
        claimed_issuance["previous_event_digest"] = claimed_payload["events"][-1][
            "event_digest"
        ]
        claimed_issuance["candidate_digest"] = claimed_legacy["checkpoint_digest"]
        claimed_issuance["review_target_digest"] = claimed_legacy["checkpoint_digest"]
        claimed_issuance["event_digest"] = digest(json.dumps(
            {
                key: value for key, value in claimed_issuance.items()
                if key != "event_digest"
            },
            sort_keys=True,
            separators=(",", ":"),
        ))
        claimed_payload["events"].append(claimed_issuance)
        claimed_payload["last_monotonic_ns"] = claimed_issuance["monotonic_ns"]
        claimed_payload["event_chain_digest"] = claimed_issuance["event_digest"]
        STATE_MODULE.append_checkpoint_event(
            claimed_payload,
            event_type="session_checkpoint_claimed",
            checkpoint=claimed_legacy,
            successor={
                "run_id": "claimed-child",
                "plan_digest": digest("claimed child plan"),
                "source_head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
                ).strip(),
                "primary_invariant_digest": digest("claimed child invariant"),
                "genesis_digest": digest("claimed child genesis"),
            },
        )
        claimed_state.write_text(json.dumps(claimed_payload), encoding="utf-8")
        claimed = self.run_cli(
            "migrate-checkpoint",
            "--legacy-checkpoint", str(claimed_legacy_path),
            "--state", str(claimed_state),
            "--reviewer-registry", str(self.registry),
            "--review-receipt", str(review),
            "--checkpoint-review-receipt", str(review),
            "--output", str(self.base / "claimed-migration.json"),
        )
        self.assertNotEqual(claimed.returncode, 0)
        self.assertIn("claimed legacy checkpoint cannot be migrated", claimed.stderr)

        migrated = self.base / "migrated-checkpoint.json"
        result = self.run_cli(
            "migrate-checkpoint",
            "--legacy-checkpoint", str(legacy_path),
            "--state", str(state),
            "--reviewer-registry", str(self.registry),
            "--review-receipt", str(review),
            "--checkpoint-review-receipt", str(review),
            "--output", str(migrated),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        migrated_payload = json.loads(migrated.read_text(encoding="utf-8"))
        self.assertEqual(
            migrated_payload["schema_version"],
            STATE_MODULE.SESSION_CHECKPOINT_SCHEMA_VERSION,
        )
        self.assertIn("reviewer_registry", migrated_payload)
        verified = self.run_cli(
            "verify-checkpoint", str(migrated), "--state", str(state)
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        accepted_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        child_state = self.base / "legacy-migration-child.json"
        child_lifecycle = self.base / "legacy-migration-child-lifecycle.json"
        child_manifest = self.resource_manifest(
            "legacy-migration-child",
            session="legacy-migration-child",
        )
        initialized = self.run_cli(
            "init", str(child_state), "--run-id", "legacy-migration-child",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text()),
            "--source-head", accepted_head,
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(child_lifecycle),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(migrated),
            "--root-session-manifest", str(child_manifest),
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        parent_after_claim = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(
            [event["event_type"] for event in parent_after_claim["events"][-2:]],
            ["session_checkpoint_migrated", "session_checkpoint_claimed"],
        )
        started = self.run_cli(
            "start", str(child_state), "--run-id", "legacy-migration-child",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--attempt-id", "legacy-migration-child-attempt",
            "--attempt-kind", "initial",
            "--predecessor-state", str(state),
            "--predecessor-checkpoint", str(migrated),
            "--root-session-manifest", str(child_manifest),
            "--lifecycle-state", str(child_lifecycle),
        )
        self.assertEqual(started.returncode, 0, started.stderr)

        parsed = STATE_MODULE.parser().parse_args([
            "migrate-checkpoint",
            "--legacy-checkpoint", str(legacy_path),
            "--state", str(state),
            "--reviewer-registry", str(self.registry),
            "--output", str(self.base / "zero-review-migration.json"),
        ])
        self.assertEqual(parsed.review_receipt, [])
        self.assertEqual(parsed.checkpoint_review_receipt, [])

    def test_review_turn_zero_requires_matching_runtime_packet_evidence(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "runtime-review-evidence", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("runtime review\n", encoding="utf-8")
        invariant = digest("one invariant")

        session_start_only = self.review_receipt(
            "session-start-only", digest(self.plan.read_text()), round_value=1
        )
        no_observation = self.resource_manifest(
            "session-start-only-runtime", session="session-start-only"
        )
        no_observation_payload = json.loads(no_observation.read_text(encoding="utf-8"))
        session_start_payload = json.loads(session_start_only.read_text(encoding="utf-8"))
        session_start_payload["inheritance_evidence_digest"] = no_observation_payload[
            "resource_observations"
        ]["evidence_digests"]["codex_hooks"]
        session_start_only.write_text(json.dumps(session_start_payload), encoding="utf-8")
        missing = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "session-start-only", "--implementation-mode", "parent_direct",
            "--review-receipt", str(session_start_only),
            "--review-resource-manifest", str(no_observation),
            "--invariant-digest", invariant, "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("exactly one packet turn observation", missing.stderr)

        fabricated = self.review_receipt(
            "fabricated-runtime", digest(self.plan.read_text()), round_value=1
        )
        fabricated_payload = json.loads(fabricated.read_text(encoding="utf-8"))
        fabricated_payload["inheritance_evidence_digest"] = digest("caller supplied")
        fabricated.write_text(json.dumps(fabricated_payload), encoding="utf-8")
        rejected_fabricated = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "fabricated-runtime", "--implementation-mode", "parent_direct",
            "--review-receipt", str(fabricated),
            "--review-resource-manifest", str(self.review_manifests[fabricated]),
            "--invariant-digest", invariant, "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected_fabricated.returncode, 0)
        self.assertIn("not bound by the runtime manifest", rejected_fabricated.stderr)

        mismatched = self.review_receipt(
            "mismatched-packet", digest(self.plan.read_text()), round_value=1
        )
        review_manifest = self.review_manifests[mismatched]
        manifest_payload = json.loads(review_manifest.read_text(encoding="utf-8"))
        event_path = review_manifest.parent / manifest_payload["hook_event_log"]
        records = [
            json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        records[-1]["payload"]["review_packet_digest"] = digest("other packet")
        event_path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
            encoding="utf-8",
        )
        changed_digest = digest(event_path.read_bytes())
        manifest_payload["resource_observations"]["evidence_digests"][
            "codex_hooks"
        ] = changed_digest
        review_manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
        mismatched_payload = json.loads(mismatched.read_text(encoding="utf-8"))
        mismatched_payload["inheritance_evidence_digest"] = changed_digest
        mismatched.write_text(json.dumps(mismatched_payload), encoding="utf-8")
        rejected_mismatch = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "mismatched-packet", "--implementation-mode", "parent_direct",
            "--review-receipt", str(mismatched),
            "--review-resource-manifest", str(review_manifest),
            "--invariant-digest", invariant, "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected_mismatch.returncode, 0)
        self.assertIn("does not observe this review packet", rejected_mismatch.stderr)

        changed = self.review_receipt(
            "changed-runtime", digest(self.plan.read_text()), round_value=1
        )
        changed_manifest = self.review_manifests[changed]
        changed_payload = json.loads(changed_manifest.read_text(encoding="utf-8"))
        changed_event = changed_manifest.parent / changed_payload["hook_event_log"]
        changed_event.write_text(
            changed_event.read_text(encoding="utf-8") + "{}\n", encoding="utf-8"
        )
        rejected_changed = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "changed-runtime", "--implementation-mode", "parent_direct",
            "--review-receipt", str(changed),
            "--review-resource-manifest", str(changed_manifest),
            "--invariant-digest", invariant, "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected_changed.returncode, 0)
        self.assertIn("does not match recomputed source file digest", rejected_changed.stderr)

    def test_execution_state_rejects_more_than_two_reviews_for_one_candidate_identity(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("review-state-budget")
        attempt_id = "review-state-budget-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt_id).returncode,
            0,
        )
        candidate_digest = digest("candidate")
        patch_digest = hashlib.sha256(b"patch").hexdigest()
        invariant = digest("one invariant")
        self.append_candidate_review_fixture(
            state, lifecycle, run_id, attempt_id, candidate_digest, patch_digest,
            invariant, label="review-budget-1",
        )
        self.append_candidate_review_fixture(
            state, lifecycle, run_id, attempt_id, candidate_digest, patch_digest,
            invariant, label="review-budget-2",
        )
        with self.assertRaisesRegex(
            STATE_MODULE.StateError,
            "one initial review and one bounded rereview",
        ):
            self.append_candidate_review_fixture(
                state, lifecycle, run_id, attempt_id, candidate_digest, patch_digest,
                invariant, label="review-budget-3",
            )

    def test_review_receipt_must_bind_applicable_specs_and_worker_receipts(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "review-packet", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("review packet\n", encoding="utf-8")
        bad_specs = self.review_receipt(
            "bad-specs", digest(self.plan.read_text()), round_value=1
        )
        payload = json.loads(bad_specs.read_text(encoding="utf-8"))
        payload["applicable_specification_digests"] = [digest("wrong spec")]
        packet = {
            key: payload[key]
            for key in (
                "plan_digest", "review_target_digest", "admitted_diff_digest",
                "worker_receipt_digests", "applicable_specification_digests",
            )
        }
        payload["packet_digest"] = STATE_MODULE.canonical_digest(packet)
        bad_specs.write_text(json.dumps(payload), encoding="utf-8")
        self.rebind_review_runtime(bad_specs)
        rejected_specs = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "bad-specs", "--implementation-mode", "parent_direct",
            "--review-receipt", str(bad_specs),
            "--review-resource-manifest", str(self.review_manifests[bad_specs]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected_specs.returncode, 0)
        self.assertIn("applicable specifications", rejected_specs.stderr)

        bad_worker = self.review_receipt(
            "bad-worker", digest(self.plan.read_text()), round_value=1
        )
        payload = json.loads(bad_worker.read_text(encoding="utf-8"))
        payload["worker_receipt_digests"] = [digest("unexpected worker")]
        packet = {
            key: payload[key]
            for key in (
                "plan_digest", "review_target_digest", "admitted_diff_digest",
                "worker_receipt_digests", "applicable_specification_digests",
            )
        }
        payload["packet_digest"] = STATE_MODULE.canonical_digest(packet)
        bad_worker.write_text(json.dumps(payload), encoding="utf-8")
        self.rebind_review_runtime(bad_worker)
        rejected_worker = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "bad-worker", "--implementation-mode", "parent_direct",
            "--review-receipt", str(bad_worker),
            "--review-resource-manifest", str(self.review_manifests[bad_worker]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected_worker.returncode, 0)
        self.assertIn("verified worker receipt", rejected_worker.stderr)

    def test_candidate_review_identity_survives_phase_and_serialization_changes(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("candidate-review")
        attempt_id = "candidate-review-attempt"
        started = self.start_writable_attempt(state, lifecycle, run_id, attempt_id)
        self.assertEqual(started.returncode, 0, started.stderr)
        state_payload = json.loads(state.read_text(encoding="utf-8"))
        patch_digest = hashlib.sha256(b"candidate patch").hexdigest()
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
        manifest_path = self.base / "candidate-review-manifest.json"
        manifest_path.write_text(manifest_content, encoding="utf-8")
        lifecycle_payload = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt_id,
            "current_manifest_digest": hashlib.sha256(
                manifest_content.encode()
            ).hexdigest(),
            "current_patch_digest": patch_digest,
            "correction_round": 0,
            "candidate_generations": 1,
            "phase": "admitted",
            "focused_required": True,
            "focused_validation_count": 0,
            "authoritative_validation_count": 0,
            "parent_review_rejections": 0,
        }
        lifecycle.write_text(json.dumps(lifecycle_payload), encoding="utf-8")
        review_target = f"sha256:{patch_digest}"
        first = self.review_receipt(
            "candidate-review-1",
            digest(self.plan.read_text()),
            round_value=1,
            review_target=review_target,
        )
        reviewed = self.run_candidate_review(
            state, lifecycle, run_id, "candidate-review-1", first, manifest_path,
            digest("one invariant"),
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        lifecycle.write_text(
            json.dumps(lifecycle_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        second = self.review_receipt(
            "candidate-review-2",
            digest(self.plan.read_text()),
            round_value=2,
            review_target=review_target,
        )
        rereviewed = self.run_candidate_review(
            state, lifecycle, run_id, "candidate-review-2", second, manifest_path,
            digest("one invariant"),
        )
        self.assertEqual(rereviewed.returncode, 0, rereviewed.stderr)
        reset = self.review_receipt(
            "candidate-review-reset",
            digest(self.plan.read_text()),
            round_value=1,
            review_target=review_target,
        )
        reset_result = self.run_candidate_review(
            state, lifecycle, run_id, "candidate-review-reset", reset, manifest_path,
            digest("one invariant"),
        )
        self.assertNotEqual(reset_result.returncode, 0)
        self.assertIn("one initial review and one bounded rereview", reset_result.stderr)

    def test_candidate_review_rejects_a_manifest_without_runner_admission_evidence(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("unverified-candidate")
        attempt_id = "unverified-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt_id).returncode,
            0,
        )
        state_payload = json.loads(state.read_text(encoding="utf-8"))
        patch_digest = hashlib.sha256(b"candidate patch").hexdigest()
        manifest = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt_id,
            "plan_path": state_payload["plan_path"],
            "plan_digest": state_payload["plan_digest"].removeprefix("sha256:"),
            "source_head": state_payload["source_head"],
            "patch_digest": patch_digest,
        }
        content = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        manifest_path = self.base / "unverified-manifest.json"
        manifest_path.write_text(content, encoding="utf-8")
        lifecycle.write_text(json.dumps({
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt_id,
            "current_manifest_digest": hashlib.sha256(content.encode()).hexdigest(),
            "current_patch_digest": patch_digest,
            "correction_round": 0,
            "candidate_generations": 1,
            "phase": "admitted",
            "focused_required": False,
            "focused_validation_count": 0,
            "authoritative_validation_count": 0,
            "parent_review_rejections": 0,
        }), encoding="utf-8")
        receipt = self.review_receipt(
            "unverified-candidate", digest(self.plan.read_text()), round_value=1,
            review_target=f"sha256:{patch_digest}",
        )
        rejected = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "unverified-candidate", "--implementation-mode", "candidate",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--candidate-manifest", str(manifest_path),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("failed admission verification", rejected.stderr)

    def test_candidate_review_rejects_manifest_substitution_for_one_attempt(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("candidate-substitution")
        attempt_id = "candidate-substitution-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt_id).returncode,
            0,
        )
        state_payload = json.loads(state.read_text(encoding="utf-8"))
        patch_digest = hashlib.sha256(b"candidate patch").hexdigest()

        def write_manifest(label: str) -> Path:
            path = self.base / f"{label}.json"
            path.write_text(json.dumps({
                "schema_version": 2,
                "orchestration_run_id": run_id,
                "plan_execution_attempt_id": attempt_id,
                "plan_path": state_payload["plan_path"],
                "plan_digest": state_payload["plan_digest"].removeprefix("sha256:"),
                "source_head": state_payload["source_head"],
                "patch_digest": patch_digest,
                "label": label,
            }, sort_keys=True), encoding="utf-8")
            lifecycle.write_text(json.dumps({
                "schema_version": 2,
                "orchestration_run_id": run_id,
                "plan_execution_attempt_id": attempt_id,
                "current_manifest_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                "current_patch_digest": patch_digest,
                "correction_round": 0,
                "candidate_generations": 1,
                "phase": "admitted",
                "focused_required": False,
                "focused_validation_count": 0,
                "authoritative_validation_count": 0,
                "parent_review_rejections": 0,
            }), encoding="utf-8")
            return path

        first_manifest = write_manifest("first-candidate")
        first_receipt = self.review_receipt(
            "first-candidate", digest(self.plan.read_text()), round_value=1,
            review_target=f"sha256:{patch_digest}",
        )
        self.assertEqual(
            self.run_candidate_review(
                state, lifecycle, run_id, "first-candidate", first_receipt,
                first_manifest, digest("one invariant"),
            ).returncode,
            0,
        )
        replacement_manifest = write_manifest("replacement-candidate")
        replacement_receipt = self.review_receipt(
            "replacement-candidate", digest(self.plan.read_text()), round_value=1,
            review_target=f"sha256:{patch_digest}",
        )
        rejected = self.run_candidate_review(
            state, lifecycle, run_id, "replacement-candidate", replacement_receipt,
            replacement_manifest, digest("one invariant"),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("already bound to another admitted candidate", rejected.stderr)

    def test_candidate_identity_change_does_not_reset_the_review_budget(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("same-patch-correction")
        invariant = digest("one invariant")
        first_attempt = "first-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, first_attempt).returncode,
            0,
        )
        state_payload = json.loads(state.read_text(encoding="utf-8"))
        original = (self.repo / "allowed.txt").read_text(encoding="utf-8")
        accepted_content = "same reviewed patch\n"
        (self.repo / "allowed.txt").write_text(accepted_content, encoding="utf-8")
        patch = subprocess.check_output(
            ["git", "diff", "--binary", "--full-index", self.head, "--", "allowed.txt"],
            cwd=self.repo,
        )
        patch_digest = hashlib.sha256(patch).hexdigest()
        (self.repo / "allowed.txt").write_text(original, encoding="utf-8")

        def candidate(attempt_id: str, round_value: int) -> tuple[Path, str]:
            manifest = {
                "schema_version": 2,
                "orchestration_run_id": run_id,
                "plan_execution_attempt_id": attempt_id,
                "plan_path": state_payload["plan_path"],
                "plan_digest": state_payload["plan_digest"].removeprefix("sha256:"),
                "source_head": state_payload["source_head"],
                "patch_digest": patch_digest,
            }
            content = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
            path = self.base / f"{attempt_id}-manifest.json"
            path.write_text(content, encoding="utf-8")
            lifecycle.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "orchestration_run_id": run_id,
                        "plan_execution_attempt_id": attempt_id,
                        "current_manifest_digest": hashlib.sha256(content.encode()).hexdigest(),
                        "current_patch_digest": patch_digest,
                        "correction_round": round_value,
                        "candidate_generations": round_value + 1,
                        "phase": "admitted",
                        "focused_required": False,
                        "focused_validation_count": 0,
                        "authoritative_validation_count": 0,
                        "parent_review_rejections": round_value,
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            return path, digest(content)

        first_manifest, first_digest = candidate(first_attempt, 0)
        first_receipt = self.review_receipt(
            "same-patch-first", digest(self.plan.read_text()), round_value=1,
            review_target=f"sha256:{patch_digest}",
        )
        self.assertEqual(
            self.run_candidate_review(
                state, lifecycle, run_id, "same-patch-first", first_receipt,
                first_manifest, invariant,
            ).returncode,
            0,
        )
        first_lifecycle_digest = digest(lifecycle.read_bytes())
        closed = self.run_cli(
            "close", str(state), "--run-id", run_id, "--attempt-id", first_attempt,
            "--outcome", "correction_requested", "--review-author", "parent",
            "--review-reason-code", "acceptance_unmet",
            "--review-evidence-digest", digest("correction"),
            "--invariant-digest", invariant, "--candidate-digest", first_digest,
            "--candidate-manifest", str(first_manifest),
            "--candidate-lifecycle-digest", first_lifecycle_digest,
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        second_attempt = "second-attempt"
        self.assertEqual(
            self.start_writable_attempt(
                state, lifecycle, run_id, second_attempt, kind="correction"
            ).returncode,
            0,
        )
        second_manifest, _ = candidate(second_attempt, 1)
        second_receipt = self.review_receipt(
            "same-patch-second", digest(self.plan.read_text()), round_value=2,
            review_target=f"sha256:{patch_digest}",
        )
        second_review = self.run_candidate_review(
            state, lifecycle, run_id, "same-patch-second", second_receipt,
            second_manifest, invariant,
        )
        self.assertEqual(second_review.returncode, 0, second_review.stderr)
        third_receipt = self.review_receipt(
            "same-patch-third", digest(self.plan.read_text()), round_value=2,
            review_target=f"sha256:{patch_digest}",
        )
        third_review = self.run_candidate_review(
            state, lifecycle, run_id, "same-patch-third", third_receipt,
            second_manifest, invariant,
        )
        self.assertNotEqual(third_review.returncode, 0)
        self.assertIn(
            "review budget permits one initial review and one bounded rereview",
            third_review.stderr,
        )
        second_manifest_content = second_manifest.read_text(encoding="utf-8")
        lifecycle_payload = json.loads(lifecycle.read_text(encoding="utf-8"))
        lifecycle_payload.update({
            "phase": "applied",
            "authoritative_validation_count": 1,
        })
        lifecycle_content = json.dumps(lifecycle_payload, sort_keys=True, indent=2) + "\n"
        lifecycle.write_text(lifecycle_content, encoding="utf-8")
        (self.repo / "allowed.txt").write_text(accepted_content, encoding="utf-8")
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "accept same patch correction"], cwd=self.repo, check=True)
        accepted_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        accepted = self.run_cli(
            "close", str(state), "--run-id", run_id, "--attempt-id", second_attempt,
            "--outcome", "accepted", "--review-author", "parent",
            "--review-evidence-digest", digest("accepted correction"),
            "--invariant-digest", invariant,
            "--candidate-digest", digest(second_manifest_content),
            "--candidate-manifest", str(second_manifest),
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--accepted-source-head", accepted_head,
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        checkpoint = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(self.base / "same-patch-checkpoint.json"),
            "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("same-patch")),
            "--review-receipt", str(second_receipt),
        )
        self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)

    def test_checked_candidate_matches_the_reviewed_leaf_after_apply(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("accepted-review-leaf")
        attempt_id = "accepted-review-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt_id).returncode,
            0,
        )
        target = self.repo / "allowed.txt"
        target.write_text("reviewed accepted candidate\n", encoding="utf-8")
        patch = subprocess.check_output(
            ["git", "diff", "--binary", "--full-index", self.head, "--", "allowed.txt"],
            cwd=self.repo,
        )
        patch_digest = hashlib.sha256(patch).hexdigest()
        state_payload = json.loads(state.read_text(encoding="utf-8"))
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
        manifest_path = self.base / "accepted-review-manifest.json"
        manifest_path.write_text(manifest_content, encoding="utf-8")
        lifecycle_payload = {
            "schema_version": 2,
            "orchestration_run_id": run_id,
            "plan_execution_attempt_id": attempt_id,
            "current_manifest_digest": hashlib.sha256(manifest_content.encode()).hexdigest(),
            "current_patch_digest": patch_digest,
            "correction_round": 0,
            "candidate_generations": 1,
            "phase": "admitted",
            "focused_required": False,
            "focused_validation_count": 0,
            "authoritative_validation_count": 0,
            "parent_review_rejections": 0,
        }
        lifecycle.write_text(
            json.dumps(lifecycle_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        receipt = self.review_receipt(
            "accepted-review",
            digest(self.plan.read_text()),
            round_value=1,
            review_target=f"sha256:{patch_digest}",
        )
        reviewed = self.run_candidate_review(
            state, lifecycle, run_id, "accepted-review", receipt, manifest_path,
            digest("one invariant"),
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        lifecycle_payload.update({
            "phase": "applied",
            "authoritative_validation_count": 1,
        })
        lifecycle_content = json.dumps(lifecycle_payload, sort_keys=True, indent=2) + "\n"
        lifecycle.write_text(lifecycle_content, encoding="utf-8")
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "accept reviewed candidate"], cwd=self.repo, check=True)
        accepted_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        closed = self.run_cli(
            "close", str(state), "--run-id", run_id, "--attempt-id", attempt_id,
            "--outcome", "accepted", "--review-author", "parent",
            "--review-evidence-digest", digest("accepted review"),
            "--invariant-digest", digest("one invariant"),
            "--candidate-digest", digest(manifest_content),
            "--candidate-manifest", str(manifest_path),
            "--candidate-lifecycle-digest", digest(lifecycle_content),
            "--accepted-source-head", accepted_head,
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        checkpoint = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(self.base / "accepted-review-checkpoint.json"),
            "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("accepted-review")),
            "--review-receipt", str(receipt),
        )
        self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)

    def test_accepted_candidate_closure_requires_a_matching_review(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("accepted-without-review")
        attempt_id = "accepted-without-review-attempt"
        self.assertEqual(
            self.start_writable_attempt(state, lifecycle, run_id, attempt_id).returncode,
            0,
        )
        target = self.repo / "allowed.txt"
        target.write_text("unreviewed accepted candidate\n", encoding="utf-8")
        patch = subprocess.check_output(
            ["git", "diff", "--binary", "--full-index", self.head, "--", "allowed.txt"],
            cwd=self.repo,
        )
        patch_digest = hashlib.sha256(patch).hexdigest()
        state_payload = json.loads(state.read_text(encoding="utf-8"))
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
        manifest_path = self.base / "accepted-without-review-manifest.json"
        manifest_path.write_text(manifest_content, encoding="utf-8")
        candidate_digest = digest(manifest_content)
        lifecycle_digest = self.write_applied_lifecycle(
            lifecycle, run_id, attempt_id, candidate_digest, patch_digest
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "accept without review"], cwd=self.repo, check=True)
        accepted_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        rejected = self.run_cli(
            "close", str(state), "--run-id", run_id, "--attempt-id", attempt_id,
            "--outcome", "accepted", "--review-author", "parent",
            "--review-evidence-digest", digest("unreviewed"),
            "--invariant-digest", digest("one invariant"),
            "--candidate-digest", candidate_digest,
            "--candidate-manifest", str(manifest_path),
            "--candidate-lifecycle-digest", lifecycle_digest,
            "--accepted-source-head", accepted_head,
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("lacks a bounded review", rejected.stderr)
        self.append_candidate_review_fixture(
            state, lifecycle, run_id, attempt_id, candidate_digest, patch_digest,
            digest("one invariant"), finding_severities=["High"],
        )
        unresolved = self.run_cli(
            "close", str(state), "--run-id", run_id, "--attempt-id", attempt_id,
            "--outcome", "accepted", "--review-author", "parent",
            "--review-evidence-digest", digest("unresolved"),
            "--invariant-digest", digest("one invariant"),
            "--candidate-digest", candidate_digest,
            "--candidate-manifest", str(manifest_path),
            "--candidate-lifecycle-digest", lifecycle_digest,
            "--accepted-source-head", accepted_head,
            "--lifecycle-state", str(lifecycle),
        )
        self.assertNotEqual(unresolved.returncode, 0)
        self.assertIn("unresolved findings", unresolved.stderr)

    def test_checked_parent_direct_diff_must_equal_reviewed_target(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "post-review-mutation", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("reviewed candidate\n", encoding="utf-8")
        receipt = self.review_receipt(
            "post-review-mutation", digest(self.plan.read_text()), round_value=1
        )
        reviewed = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "post-review-mutation",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.assertEqual(
            self.run_cli(
                "record", str(state), "--run-id", run_id,
                "--event-id", "authoritative",
                "--event-type", "authoritative_validation",
                "--implementation-mode", "parent_direct",
                "--candidate-lifecycle-digest", digest("authoritative\n"),
                "--lifecycle-state", str(lifecycle),
            ).returncode,
            0,
        )
        (self.repo / "allowed.txt").write_text("mutated after review\n", encoding="utf-8")
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "mutate reviewed candidate"], cwd=self.repo, check=True)
        checkpoint = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(self.base / "mutated-checkpoint.json"),
            "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("mutated-checkpoint")),
            "--review-receipt", str(receipt),
        )
        self.assertNotEqual(checkpoint.returncode, 0)
        self.assertIn("differs from the checked target", checkpoint.stderr)

    def test_checked_parent_direct_commit_rejects_out_of_scope_changes(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "out-of-scope-commit", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("reviewed candidate\n", encoding="utf-8")
        receipt = self.review_receipt(
            "out-of-scope-commit", digest(self.plan.read_text()), round_value=1
        )
        reviewed = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "out-of-scope-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(receipt),
            "--review-resource-manifest", str(self.review_manifests[receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.assertEqual(
            self.run_cli(
                "record", str(state), "--run-id", run_id,
                "--event-id", "out-of-scope-authoritative",
                "--event-type", "authoritative_validation",
                "--implementation-mode", "parent_direct",
                "--candidate-lifecycle-digest", digest("authoritative\n"),
                "--lifecycle-state", str(lifecycle),
            ).returncode,
            0,
        )
        (self.repo / "AGENTS.md").write_text("unreviewed policy change\n", encoding="utf-8")
        subprocess.run(["git", "add", "allowed.txt", "AGENTS.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "commit out of scope"], cwd=self.repo, check=True)
        rejected = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(self.base / "out-of-scope-checkpoint.json"),
            "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("out-of-scope")),
            "--review-receipt", str(receipt),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("outside write_scope", rejected.stderr)

    def test_parent_direct_checkpoint_requires_receipts_for_final_reviewed_patch(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "final-parent-review", mode="parent_direct"
        )
        (self.repo / "allowed.txt").write_text("first review\n", encoding="utf-8")
        first_receipt = self.review_receipt(
            "first-parent-review", digest(self.plan.read_text()), round_value=1
        )
        first = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "first-parent-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(first_receipt),
            "--review-resource-manifest", str(self.review_manifests[first_receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.repo / "allowed.txt").write_text("final review\n", encoding="utf-8")
        second_receipt = self.review_receipt(
            "final-parent-review", digest(self.plan.read_text()), round_value=2
        )
        second = self.run_cli(
            "review", str(state), "--run-id", run_id,
            "--event-id", "final-parent-review",
            "--implementation-mode", "parent_direct",
            "--review-receipt", str(second_receipt),
            "--review-resource-manifest", str(self.review_manifests[second_receipt]),
            "--invariant-digest", digest("one invariant"),
            "--lifecycle-state", str(lifecycle),
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        lifecycle.write_text("authoritative\n", encoding="utf-8")
        self.assertEqual(
            self.run_cli(
                "record", str(state), "--run-id", run_id,
                "--event-id", "final-parent-authoritative",
                "--event-type", "authoritative_validation",
                "--implementation-mode", "parent_direct",
                "--candidate-lifecycle-digest", digest("authoritative\n"),
                "--lifecycle-state", str(lifecycle),
            ).returncode,
            0,
        )
        subprocess.run(["git", "add", "allowed.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "commit final reviewed patch"], cwd=self.repo, check=True)
        rejected = self.run_cli(
            "checkpoint", str(state), "--run-id", run_id,
            "--output", str(self.base / "wrong-parent-receipt-checkpoint.json"),
            "--boundary", "checked",
            "--resource-manifest", str(self.resource_manifest("wrong-parent-receipt")),
            "--review-receipt", str(first_receipt),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("differs from the checked target", rejected.stderr)

    def test_parent_direct_revision_does_not_reset_the_review_budget(self) -> None:
        state, lifecycle, run_id = self.initialize_execution(
            "parent-review-budget", mode="parent_direct"
        )
        invariant = digest("one invariant")

        def parent_review(label: str, round_value: int) -> subprocess.CompletedProcess[str]:
            receipt = self.review_receipt(
                label, digest(self.plan.read_text()), round_value=round_value
            )
            return self.run_cli(
                "review", str(state), "--run-id", run_id,
                "--event-id", label,
                "--implementation-mode", "parent_direct",
                "--review-receipt", str(receipt),
                "--review-resource-manifest", str(self.review_manifests[receipt]),
                "--invariant-digest", invariant,
                "--lifecycle-state", str(lifecycle),
            )

        (self.repo / "allowed.txt").write_text("budget review one\n", encoding="utf-8")
        first = parent_review("parent-budget-1", 1)
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.repo / "allowed.txt").write_text("budget review two\n", encoding="utf-8")
        second = parent_review("parent-budget-2", 2)
        self.assertEqual(second.returncode, 0, second.stderr)
        (self.repo / "allowed.txt").write_text("budget review three\n", encoding="utf-8")
        third = parent_review("parent-budget-3", 2)
        self.assertNotEqual(third.returncode, 0)
        self.assertIn(
            "review budget permits one initial review and one bounded rereview",
            third.stderr,
        )

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
        require_preflight: bool = False,
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
        if require_preflight:
            arguments.extend(
                (
                    "--require-adversarial-preflight",
                    "--continuation-registry",
                    str(self.continuation_registry),
                )
            )
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
            if outcome == "accepted":
                current = json.loads(state.read_text(encoding="utf-8"))
                identity = STATE_MODULE.review_candidate_identity_digest(
                    attempt_id, candidate, f"sha256:{patch_digest}"
                )
                if not any(
                    event["event_type"] == "parent_review"
                    and event["candidate_lifecycle_digest"] == identity
                    for event in current["events"]
                ):
                    self.append_candidate_review_fixture(
                        state, lifecycle, run_id, attempt_id, candidate, patch_digest,
                        invariant,
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

    def synthetic_attempt_events_for_reasons(
        self,
        reasons: list[str],
        *,
        outcome: str = "correction_requested",
    ) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        last_digest = digest("synthetic-genesis")
        for index, reason in enumerate(reasons, start=1):
            attempt_id = f"synthetic-attempt-{index}"
            start_event = {
                "event_type": "writable_attempt_started",
                "attempt_id": attempt_id,
                "attempt_kind": "initial" if index == 1 else "correction",
                "review_outcome": "",
            }
            close_event = {
                "event_type": "attempt_closed",
                "attempt_id": attempt_id,
                "review_outcome": outcome,
                "review_reason_code": reason,
                "candidate_digest": digest(f"candidate-{index}"),
                "accepted_source_head": self.head if outcome == "accepted" else "",
                "event_digest": digest(f"close-{index}:{last_digest}"),
            }
            events.extend([start_event, close_event])
            last_digest = str(close_event["event_digest"])
        return events

    def exhaust_boundary_finding_budget(
        self,
        *,
        reason: str = "required_spec_missed",
    ) -> None:
        invariant = digest("one invariant")
        for index in (1,):
            attempt_id = f"boundary-budget-{index}"
            started = self.start_writable_attempt(
                self.state, self.lifecycle, "run-1", attempt_id,
                kind="initial" if index == 1 else "correction",
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            closed = self.close_writable_attempt(
                self.state, self.lifecycle, "run-1", attempt_id,
                invariant=invariant, outcome="correction_requested", reason=reason,
            )
            self.assertEqual(closed.returncode, 0, closed.stderr)

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

    def test_issued_checkpoint_cannot_be_omitted_by_init_or_start(self) -> None:
        predecessor, _, _ = self.accepted_execution("issued-checkpoint")
        child_state, child_lifecycle, child_run = self.initialize_execution(
            "pre-issued-child",
            plan=self.child_plan,
            predecessor=predecessor,
        )
        predecessor_payload = STATE_MODULE.read_state(predecessor)
        STATE_MODULE.append_checkpoint_event(
            predecessor_payload,
            event_type="session_checkpoint_emitted",
            checkpoint={"checkpoint_digest": digest("issued-checkpoint")},
        )
        STATE_MODULE.atomic_write(predecessor, predecessor_payload)

        denied_init = self.run_cli(
            "init", str(self.base / "omitted-checkpoint.json"),
            "--run-id", "omitted-checkpoint",
            "--plan", self.child_plan.relative_to(self.repo).as_posix(),
            "--plan-digest", digest(self.child_plan.read_text(encoding="utf-8")),
            "--source-head", subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
            ).strip(),
            "--primary-invariant-digest", digest("child invariant"),
            "--lifecycle-state", str(self.base / "omitted-lifecycle.json"),
            "--implementation-mode", "candidate",
            "--predecessor-state", str(predecessor),
        )
        self.assertNotEqual(denied_init.returncode, 0)
        self.assertIn("requires checkpoint and root-session evidence", denied_init.stderr)

        denied_start = self.start_writable_attempt(
            child_state,
            child_lifecycle,
            child_run,
            "omitted-attempt",
            plan=self.child_plan,
            predecessor=predecessor,
        )
        self.assertNotEqual(denied_start.returncode, 0)
        self.assertIn("is not claimed by this successor", denied_start.stderr)

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

    def write_descope_evidence(
        self,
        event_id: str,
        receipt: str,
        invariant: str,
        **overrides: object,
    ) -> Path:
        state = self.payload()
        source = [digest("acceptance-a"), digest("acceptance-b"), digest("acceptance-c")]
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
            "source_acceptance_digests": source,
            "retained_acceptance_digests": [source[0]],
            "deferred_acceptance_digests": [source[1], source[2]],
            "deferred_backlog_path": "docs/plan/backlog/300-deferred-acceptance.md",
            "bounded_write_scope": True,
            "source_scope_unchanged": True,
            "validation_authority_unchanged": True,
            "invariant_boundaries_unchanged": True,
            "primary_invariant_unchanged": True,
            "safety_conditions_unchanged": True,
            "external_effect_authority_unchanged": True,
            "independent_invariant_count": 1,
        }
        value.update(overrides)
        evidence = self.base / f"{event_id}-descope-evidence.json"
        evidence.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return evidence

    def record_descope(
        self,
        event_id: str,
        receipt_label: str,
        **overrides: object,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        invariant_digest = digest("one invariant")
        receipt_digest = digest(receipt_label)
        self.lifecycle.write_text(event_id + "\n", encoding="utf-8")
        evidence = self.write_descope_evidence(
            event_id, receipt_digest, invariant_digest, **overrides
        )
        recorded = self.record(
            event_id, "descope_classification",
            "--invariant-digest", invariant_digest,
            "--independent-review-receipt-digest", receipt_digest,
            "--descope-evidence-file", str(evidence),
        )
        return recorded, invariant_digest

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

    def test_one_rejected_correction_stops_and_replay_is_rejected(self) -> None:
        self.assertEqual(self.record("generation-1", "candidate_generation").returncode, 0)
        self.assertEqual(self.record("correction-1", "correction_rejected").returncode, 0)
        replay = self.record("correction-1", "correction_rejected")
        self.assertNotEqual(replay.returncode, 0)
        self.assertNotEqual(self.record("correction-2", "correction_rejected").returncode, 0)
        state = self.payload()
        self.assertEqual(state["state"], "replan_required")
        self.assertEqual(state["candidate_generations"], 2)
        self.assertEqual(state["correction_rounds"], 1)
        self.assertNotEqual(self.record("generation-3", "candidate_generation").returncode, 0)
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
        for index in (1,):
            result = parent_record(
                f"parent-{index}", "--invariant-digest", invariant,
                "--finding-severity", "Medium", "--independent-review-receipt-digest",
                digest(f"receipt-{index}"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "descope_pending")
        self.assertEqual(
            payload["descope_pending_reason_codes"],
            ["parent_remediation_budget_exhausted"],
        )
        self.assertEqual(payload["replan_reason_codes"], [])

    def test_implementation_review_reason_repeats_below_budget_remain_active(self) -> None:
        with mock.patch.object(STATE_MODULE, "MAX_CORRECTIONS", 10):
            summary = STATE_MODULE.derive_summary(
                self.synthetic_attempt_events_for_reasons(["acceptance_unmet"] * 1)
            )
        self.assertEqual(summary["state"], "active")
        self.assertEqual(summary["replan_reason_codes"], [])
        self.assertEqual(summary["descope_pending_reason_codes"], [])
        self.assertEqual(summary["review_reason_codes"], ["acceptance_unmet"])

    def test_implementation_review_reason_budget_enters_descope_pending(self) -> None:
        with mock.patch.object(STATE_MODULE, "MAX_CORRECTIONS", 10):
            summary = STATE_MODULE.derive_summary(
                self.synthetic_attempt_events_for_reasons(["evidence_incomplete"] * 2)
            )
        self.assertEqual(summary["state"], "descope_pending")
        self.assertEqual(
            summary["descope_pending_reason_codes"],
            ["implementation_finding_budget_exhausted"],
        )
        self.assertEqual(summary["replan_reason_codes"], [])

    def test_boundary_review_reason_budget_enters_descope_pending(self) -> None:
        self.exhaust_boundary_finding_budget(reason="integration_contract_mismatch")
        payload = self.payload()
        self.assertEqual(payload["state"], "descope_pending")
        self.assertEqual(
            payload["descope_pending_reason_codes"],
            ["boundary_finding_budget_exhausted"],
        )
        self.assertEqual(payload["replan_reason_codes"], [])

    def test_descope_pending_allows_only_descope_or_drift(self) -> None:
        self.exhaust_boundary_finding_budget()
        blocked = self.record("pending-focused", "focused_validation")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("pending a bounded descope classification", blocked.stderr)
        recorded, _ = self.record_descope("pending-descope", "pending-descope-review")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], "descope_required")
        self.assertEqual(
            payload["descope_reason_codes"], ["bounded_acceptance_reduction_required"]
        )
        self.assertEqual(
            payload["descope_pending_reason_codes"],
            ["boundary_finding_budget_exhausted"],
        )

    def test_descope_pending_drift_escalates_to_replan(self) -> None:
        self.exhaust_boundary_finding_budget()
        recorded = self.record(
            "pending-scope-drift", "scope_drift",
            "--invariant-digest", digest("one invariant"),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], "replan_required")
        self.assertEqual(payload["replan_reason_codes"], ["scope_drift"])
        self.assertEqual(
            payload["descope_pending_reason_codes"],
            ["boundary_finding_budget_exhausted"],
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

    def test_bounded_descope_preserves_acceptance_without_restructuring(self) -> None:
        recorded, _ = self.record_descope("descope-1", "descope-review-1")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], "descope_required")
        self.assertEqual(
            payload["descope_reason_codes"], ["bounded_acceptance_reduction_required"]
        )
        self.assertEqual(payload["replan_reason_codes"], [])
        self.assertEqual(payload["repair_reason_codes"], [])
        execution_gate = self.run_cli(
            "check", str(self.state), "--run-id", "run-1",
            "--operation", "execution", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(execution_gate.returncode, 0)
        descope_gate = self.run_cli(
            "check", str(self.state), "--run-id", "run-1",
            "--operation", "descope_plan", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertEqual(descope_gate.returncode, 0, descope_gate.stderr)
        repair_gate = self.run_cli(
            "check", str(self.state), "--run-id", "run-1",
            "--operation", "repair_plan", "--lifecycle-state", str(self.lifecycle),
        )
        self.assertNotEqual(repair_gate.returncode, 0)
        blocked = self.record("descope-after", "focused_validation")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("bounded acceptance reduction", blocked.stderr)

    def test_descope_rejects_an_incomplete_acceptance_partition(self) -> None:
        source = [digest("acceptance-a"), digest("acceptance-b"), digest("acceptance-c")]
        dropped, _ = self.record_descope(
            "descope-dropped", "descope-review-dropped",
            retained_acceptance_digests=[source[0]],
            deferred_acceptance_digests=[source[1]],
        )
        self.assertNotEqual(dropped.returncode, 0)
        self.assertIn("partition every source acceptance digest", dropped.stderr)
        overlapping, _ = self.record_descope(
            "descope-overlap", "descope-review-overlap",
            retained_acceptance_digests=[source[0], source[1]],
            deferred_acceptance_digests=[source[1], source[2]],
        )
        self.assertNotEqual(overlapping.returncode, 0)
        empty_retained, _ = self.record_descope(
            "descope-empty", "descope-review-empty",
            retained_acceptance_digests=[],
            deferred_acceptance_digests=source,
        )
        self.assertNotEqual(empty_retained.returncode, 0)
        self.assertIn("retain at least one acceptance item", empty_retained.stderr)
        no_reduction, _ = self.record_descope(
            "descope-none", "descope-review-none",
            retained_acceptance_digests=source,
            deferred_acceptance_digests=[],
        )
        self.assertNotEqual(no_reduction.returncode, 0)
        self.assertIn("defer at least one acceptance item", no_reduction.stderr)
        self.assertEqual(self.payload()["state"], "active")

    def test_boundary_drift_escalates_a_descope_attempt_to_replan(self) -> None:
        recorded, _ = self.record_descope(
            "descope-drift", "descope-review-drift", source_scope_unchanged=False,
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], "replan_required")
        self.assertEqual(payload["replan_reason_codes"], ["scope_drift"])
        self.assertEqual(payload["descope_reason_codes"], [])

    def test_security_boundary_drift_blocks_a_bounded_descope(self) -> None:
        recorded, _ = self.record_descope(
            "descope-security", "descope-review-security",
            safety_conditions_unchanged=False,
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.payload()
        self.assertEqual(payload["state"], "replan_required")
        self.assertEqual(payload["replan_reason_codes"], ["security_boundary_drift"])
        self.assertEqual(payload["descope_reason_codes"], [])

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
                elif reason == "parent_remediation_budget_exhausted":
                    for round_number in (1,):
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
                if reason == "parent_remediation_budget_exhausted":
                    self.assertEqual(payload["state"], "descope_pending")
                    self.assertEqual(payload["replan_reason_codes"], [])
                    self.assertEqual(
                        payload["descope_pending_reason_codes"],
                        ["parent_remediation_budget_exhausted"],
                    )
                    stopped_fragment = "pending a bounded descope classification"
                else:
                    self.assertEqual(payload["state"], "replan_required")
                    self.assertIn(reason, payload["replan_reason_codes"])
                    stopped_fragment = "stopped for restructuring"
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
                    self.assertIn(stopped_fragment, denied.stderr)
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
        self.assertEqual(
            payload["replan_reason_codes"], ["candidate_correction_budget_exhausted"]
        )
        self.assertEqual(
            payload["descope_pending_reason_codes"],
            ["implementation_finding_budget_exhausted"],
        )
        exhausted = self.start_writable_attempt(
            state, lifecycle, run_id, "classification-3", kind="correction"
        )
        self.assertNotEqual(exhausted.returncode, 0)

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

    def test_changed_reasons_use_one_correction_then_budget_and_coupling_stop(self) -> None:
        state, lifecycle, run_id = self.initialize_execution("changed-reasons")
        invariant = digest("one invariant")
        reasons = ("acceptance_unmet", "required_spec_missed")
        kinds = ("initial", "correction")
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
        self.assertEqual(payload["correction_rounds"], 1)

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
        self.assertEqual(
            json.loads(coupled_state.read_text(encoding="utf-8"))["replan_reason_codes"],
            ["multiple_invariants_coupled"],
        )

        rejected_state, rejected_lifecycle, rejected_run = self.initialize_execution(
            "final-correction-rejected"
        )
        for index, outcome in enumerate(
            ("correction_requested", "rejected"), start=1
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
                reason=("acceptance_unmet", "evidence_incomplete")[index - 1],
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

    def test_runner_rejects_checkpoint_controls_without_predecessor_state(self) -> None:
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.invalid/test/repo.git"],
            cwd=self.repo, check=True,
        )
        state, lifecycle, run_id = self.initialize_execution(
            "runner-checkpoint-controls", plan=self.child_plan
        )
        result = subprocess.run(
            [
                sys.executable, str(RUNNER), "run",
                self.child_plan.relative_to(self.repo).as_posix(),
                "--orchestration-run-id", run_id,
                "--lifecycle-state", str(lifecycle),
                "--plan-execution-state", str(state),
                "--predecessor-session-checkpoint", str(self.base / "checkpoint.json"),
                "--root-session-manifest", str(
                    self.resource_manifest("runner-current", session="runner-current")
                ),
                "--bwrap-bin", "definitely-missing-bwrap",
            ],
            cwd=self.repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "require --predecessor-plan-execution-state",
            result.stderr,
        )

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


class ParallelPlanGroupTest(unittest.TestCase):
    """Group description admission and parent-owned parallel execution authority."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        (self.repo / "docs/plan/active").mkdir(parents=True)
        (self.repo / "docs/plan/execution-groups").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True
        )
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.invalid/owner/repo.git"],
            cwd=self.repo,
            check=True,
        )
        self.alpha = self.write_plan("284", "alpha", ["src/alpha.py"])
        self.beta = self.write_plan("285", "beta", ["src/beta.py"])
        self.solo = self.write_plan("290", "solo", ["src/solo.py"])
        self.alpha_path = "docs/plan/active/284-alpha.md"
        self.beta_path = "docs/plan/active/285-beta.md"
        self.solo_path = "docs/plan/active/290-solo.md"
        self.description = self.repo / "docs/plan/execution-groups/alpha-beta.json"
        self.write_description(self.group_document())
        self.commit()
        self.state = self.base / "group-state.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    # -- fixture helpers ------------------------------------------------

    def write_plan(
        self,
        plan_id: str,
        slug: str,
        write_scope: list[str],
        *,
        extra: str = "",
    ) -> Path:
        body = (
            f"# Plan {plan_id}\n\n"
            "status: in_progress\n"
            "plan_purpose: implementation\n"
            f"primary_invariant: invariant {plan_id}\n"
            "write_scope:\n"
            + "".join(f"  - {entry}\n" for entry in write_scope)
            + extra
            + "context_files:\n  - AGENTS.md\n"
            "\n## Tasks\n\n- [ ] implement\n"
        )
        path = self.repo / f"docs/plan/active/{plan_id}-{slug}.md"
        path.write_text(body, encoding="utf-8")
        return path

    def write_description(self, document: dict) -> None:
        self.description.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )

    def scope_digest(self, entries: list[str]) -> str:
        canonical = json.dumps(
            [entry.rstrip("/") for entry in entries],
            sort_keys=True,
            separators=(",", ":"),
        )
        return digest(canonical)

    def group_document(self) -> dict:
        return {
            "schema_version": 1,
            "group_id": "alpha-beta",
            "target_ref": "refs/heads/main",
            "declared_independence": "disjoint product modules with no shared interface",
            "members": [
                {
                    "plan_id": "284",
                    "plan_path": self.alpha_path,
                    "plan_digest": digest(self.alpha.read_bytes()),
                    "write_scope_digest": self.scope_digest(["src/alpha.py"]),
                },
                {
                    "plan_id": "285",
                    "plan_path": self.beta_path,
                    "plan_digest": digest(self.beta.read_bytes()),
                    "write_scope_digest": self.scope_digest(["src/beta.py"]),
                },
            ],
        }

    def commit(self, message: str = "fixture") -> str:
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", message], cwd=self.repo, check=True
        )
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()

    def run_group(self, *arguments: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GROUP_SCRIPT), *arguments],
            cwd=self.repo,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def initialize_group(self) -> str:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        completed = self.run_group(
            "group-init",
            str(self.state),
            "--group-description",
            "docs/plan/execution-groups/alpha-beta.json",
            "--target-ref",
            "refs/heads/main",
            "--start-commit",
            head,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return head

    def issue_permit(self, member: str, permit_id: str, workspace: str) -> Path:
        output = self.base / f"{permit_id}.json"
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            member,
            "--permit-id",
            permit_id,
            "--workspace-digest",
            digest(workspace),
            "--output",
            str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return output

    def payload(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))

    # -- committed group description admission --------------------------

    def test_valid_group_description_is_admitted(self) -> None:
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("alpha-beta.json", completed.stdout)

    def test_group_description_rejects_unsound_membership(self) -> None:
        overlapping = self.write_plan("285", "beta", ["src/alpha.py/inner.py"])
        document = self.group_document()
        document["members"][1]["plan_digest"] = digest(overlapping.read_bytes())
        document["members"][1]["write_scope_digest"] = self.scope_digest(
            ["src/alpha.py/inner.py"]
        )
        self.write_description(document)
        self.commit("overlap")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("overlapping write scope", completed.stderr)

    def test_group_description_rejects_validation_authority_scope(self) -> None:
        self.write_plan("285", "beta", ["scripts/plan-execution-state.py"])
        document = self.group_document()
        document["members"][1]["plan_digest"] = digest(
            (self.repo / self.beta_path).read_bytes()
        )
        document["members"][1]["write_scope_digest"] = self.scope_digest(
            ["scripts/plan-execution-state.py"]
        )
        self.write_description(document)
        self.commit("authority")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("validation or specification authority", completed.stderr)

    def test_group_description_rejects_member_to_member_dependency(self) -> None:
        self.write_plan(
            "284",
            "alpha",
            ["src/alpha.py"],
            extra=f"predecessor_plans:\n  - {self.beta_path}\n",
        )
        document = self.group_document()
        document["members"][0]["plan_digest"] = digest(self.alpha.read_bytes())
        self.write_description(document)
        self.commit("dependency")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("member-to-member predecessor edge", completed.stderr)

    def test_group_description_rejects_duplicate_and_short_membership(self) -> None:
        duplicated = self.group_document()
        duplicated["members"][1] = dict(duplicated["members"][0])
        self.write_description(duplicated)
        self.commit("duplicate")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("duplicate member", completed.stderr)

        single = self.group_document()
        single["members"] = single["members"][:1]
        self.write_description(single)
        self.commit("single")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("exactly 2 independent members", completed.stderr)

    def test_group_description_cannot_contain_its_own_commit_or_digest(self) -> None:
        embedded = self.group_document()
        embedded["target_ref"] = "0" * 40
        self.write_description(embedded)
        self.commit("embedded commit")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("exact local branch ref", completed.stderr)

        self_referential = self.group_document()
        self_referential["description_digest"] = digest("self")
        self.write_description(self_referential)
        self.commit("self digest")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("unexpected keys", completed.stderr)

    def test_group_description_rejects_stale_member_digests(self) -> None:
        document = self.group_document()
        self.write_plan("284", "alpha", ["src/alpha.py", "src/alpha-extra.py"])
        self.write_description(document)
        self.commit("stale")
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("plan digest does not match live bytes", completed.stderr)

    def test_uncommitted_group_description_is_refused(self) -> None:
        pending = self.group_document()
        pending["group_id"] = "pending-group"
        (self.repo / "docs/plan/execution-groups/pending.json").write_text(
            json.dumps(pending, indent=2) + "\n", encoding="utf-8"
        )
        completed = self.run_group("validate-descriptions")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("committed", completed.stderr)

    def test_invalid_description_fails_every_enrollment_gate_closed(self) -> None:
        broken = self.group_document()
        broken["declared_independence"] = "   "
        self.write_description(broken)
        self.commit("blank independence")
        completed = self.run_group(
            "check-enrollment", "--plan", self.solo_path, "--operation", "run"
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("declared_independence", completed.stderr)

    # -- parent-owned runtime authority ---------------------------------

    def test_group_state_is_private_and_bound_to_repository_identity(self) -> None:
        self.initialize_group()
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)
        payload = self.payload()
        self.assertEqual(payload["group_id"], "alpha-beta")
        self.assertEqual(payload["target_ref"], "refs/heads/main")
        self.assertEqual(sorted(payload["members"]), [self.alpha_path, self.beta_path])
        self.assertNotIn("example.invalid/owner/repo.git", json.dumps(payload))

    def test_group_state_rejects_a_foreign_clone(self) -> None:
        self.initialize_group()
        subprocess.run(
            ["git", "remote", "set-url", "origin", "https://example.invalid/other/repo.git"],
            cwd=self.repo,
            check=True,
        )
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--workspace-digest",
            digest("workspace"),
            "--output",
            str(self.base / "permit.json"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("repository", completed.stderr)

    def test_group_state_rejects_description_drift_after_admission(self) -> None:
        self.initialize_group()
        drifted = self.group_document()
        drifted["declared_independence"] = "changed rationale after admission"
        self.write_description(drifted)
        self.commit("drift")
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--workspace-digest",
            digest("workspace"),
            "--output",
            str(self.base / "permit.json"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("changed after admission", completed.stderr)

    def test_member_permit_is_exclusive_and_not_replayable(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a2",
            "--workspace-digest",
            digest("workspace-a"),
            "--output",
            str(self.base / "second.json"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("already holds an exclusive candidate permit", completed.stderr)

        self.issue_permit(self.beta_path, "permit-b1", "workspace-b")
        self.run_group(
            "permit-release",
            str(self.state),
            "--member",
            self.beta_path,
            "--permit-id",
            "permit-b1",
            check=True,
        )
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            self.beta_path,
            "--permit-id",
            "permit-b1",
            "--workspace-digest",
            digest("workspace-b"),
            "--output",
            str(self.base / "replay.json"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("replay", completed.stderr)

    def test_independent_members_hold_separate_permits(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.issue_permit(self.beta_path, "permit-b1", "workspace-b")
        payload = self.payload()
        self.assertTrue(payload["members"][self.alpha_path]["permit"]["open"])
        self.assertTrue(payload["members"][self.beta_path]["permit"]["open"])

    def test_upstream_claim_is_consumed_exactly_once(self) -> None:
        self.initialize_group()
        self.run_group(
            "claim-upstream", str(self.state), "--leaf-digest", digest("leaf"), check=True
        )
        completed = self.run_group(
            "claim-upstream", str(self.state), "--leaf-digest", digest("other-leaf")
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("upstream accepted chain leaf", completed.stderr)

    def test_publication_lease_has_one_owner_across_workspaces(self) -> None:
        self.initialize_group()
        self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.alpha_path,
            "--owner",
            "parent-one",
            check=True,
        )
        completed = self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.beta_path,
            "--owner",
            "parent-two",
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("publication lease", completed.stderr)
        self.run_group(
            "lease-release", str(self.state), "--owner", "parent-one", check=True
        )
        completed = self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.beta_path,
            "--owner",
            "parent-two",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_group_state_rejects_a_foreign_member(self) -> None:
        self.initialize_group()
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            self.solo_path,
            "--permit-id",
            "permit-x",
            "--workspace-digest",
            digest("workspace"),
            "--output",
            str(self.base / "foreign.json"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn(self.solo_path, completed.stderr)

    def test_group_events_stay_bounded_and_hash_chained(self) -> None:
        self.initialize_group()
        payload = self.payload()
        self.assertLessEqual(len(payload["events"]), 64)
        self.assertTrue(payload["events"][0]["event_chain_digest"].startswith("sha256:"))
        tampered = self.payload()
        tampered["events"][0]["event_type"] = "forged"
        self.state.write_text(json.dumps(tampered), encoding="utf-8")
        completed = self.run_group("show", str(self.state))
        self.assertEqual(completed.returncode, 1)
        self.assertIn("event chain", completed.stderr)

    # -- per-member bounded budgets -------------------------------------

    def test_member_budgets_are_bounded_and_independent(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        for index in range(2):
            completed = self.run_group(
                "record-review",
                str(self.state),
                "--member",
                self.alpha_path,
                "--registry-path-digest",
                digest("registry"),
                "--registry-event-count",
                str(index + 1),
                "--registry-event-chain-digest",
                digest(f"chain-{index}"),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "3",
            "--registry-event-chain-digest",
            digest("chain-3"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("exhausted its independent review budget", completed.stderr)

        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.beta_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "4",
            "--registry-event-chain-digest",
            digest("chain-4"),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_parent_adjustment_has_one_exclusive_unresolved_slot(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "adjust-reserve",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--incoming-candidate-digest",
            digest("candidate"),
            "--base-digest",
            digest("base"),
            check=True,
        )
        completed = self.run_group(
            "adjust-reserve",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--incoming-candidate-digest",
            digest("other-candidate"),
            "--base-digest",
            digest("base"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("already reserved and unresolved", completed.stderr)

        completed = self.run_group(
            "adjust-close",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--incoming-candidate-digest",
            digest("other-candidate"),
            "--patch-digest",
            digest("patch"),
        )
        self.assertEqual(completed.returncode, 1)

        self.run_group(
            "adjust-close",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--incoming-candidate-digest",
            digest("candidate"),
            "--patch-digest",
            digest("patch"),
            check=True,
        )
        completed = self.run_group(
            "adjust-reserve",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            "--incoming-candidate-digest",
            digest("third"),
            "--base-digest",
            digest("base"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("single correction slot", completed.stderr)

    def test_initial_generation_is_spent_once_per_logical_member(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "permit-release",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            check=True,
        )
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a2",
            "--workspace-digest",
            digest("workspace-a-second"),
            "--output",
            str(self.base / "second-generation.json"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("single initial generation", completed.stderr)

    # -- baseline transfer ----------------------------------------------

    def test_baseline_transfer_carries_counters_and_registry_proof(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "1",
            "--registry-event-chain-digest",
            digest("chain-1"),
            check=True,
        )
        before = self.payload()["members"][self.alpha_path]
        head = self.commit("new baseline")
        completed = self.run_group(
            "transfer-baseline",
            str(self.state),
            "--member",
            self.alpha_path,
            "--prior-permit-id",
            "permit-a1",
            "--new-permit-id",
            "permit-a2",
            "--new-base-commit",
            head,
            "--workspace-digest",
            digest("workspace-a-transferred"),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        after = self.payload()["members"][self.alpha_path]
        self.assertEqual(after["counters"], before["counters"])
        self.assertEqual(
            after["reviewer_registry_proof"], before["reviewer_registry_proof"]
        )
        self.assertEqual(after["baseline_generation"], before["baseline_generation"] + 1)
        self.assertEqual(after["permit"]["permit_id"], "permit-a2")
        self.assertNotEqual(
            after["permit"]["workspace_digest"], before["permit"]["workspace_digest"]
        )

        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "2",
            "--registry-event-chain-digest",
            digest("chain-2"),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "3",
            "--registry-event-chain-digest",
            digest("chain-3"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("exhausted its independent review budget", completed.stderr)

    def test_baseline_transfer_requires_the_exact_prior_permit(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        head = self.commit("new baseline")
        completed = self.run_group(
            "transfer-baseline",
            str(self.state),
            "--member",
            self.alpha_path,
            "--prior-permit-id",
            "permit-unknown",
            "--new-permit-id",
            "permit-a2",
            "--new-base-commit",
            head,
            "--workspace-digest",
            digest("workspace"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("prior", completed.stderr)

    def test_stopped_member_is_terminal_for_transfer_and_permits(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "member-stop",
            str(self.state),
            "--member",
            self.alpha_path,
            "--reason",
            "replan_required",
            check=True,
        )
        head = self.commit("new baseline")
        completed = self.run_group(
            "transfer-baseline",
            str(self.state),
            "--member",
            self.alpha_path,
            "--prior-permit-id",
            "permit-a1",
            "--new-permit-id",
            "permit-a2",
            "--new-base-commit",
            head,
            "--workspace-digest",
            digest("workspace"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("terminal", completed.stderr)
        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "1",
            "--registry-event-chain-digest",
            digest("chain"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("stopped", completed.stderr)

    def test_member_stop_rejects_an_unknown_reason(self) -> None:
        self.initialize_group()
        completed = self.run_group(
            "member-stop",
            str(self.state),
            "--member",
            self.alpha_path,
            "--reason",
            "looks_fine",
        )
        self.assertEqual(completed.returncode, 1)

    # -- fail-closed legacy gates ---------------------------------------

    def test_every_gated_operation_refuses_an_enrolled_member(self) -> None:
        for operation in (
            "run",
            "correct",
            "validate",
            "apply",
            "execution",
            "completion",
            "finalization",
            "archive",
        ):
            with self.subTest(operation=operation):
                completed = self.run_group(
                    "check-enrollment",
                    "--plan",
                    self.alpha_path,
                    "--operation",
                    operation,
                )
                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertIn("enrolled in execution group", completed.stderr)

    def test_valid_permit_still_refuses_until_the_adapter_exists(self) -> None:
        self.initialize_group()
        permit = self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        completed = self.run_group(
            "check-enrollment",
            "--plan",
            self.alpha_path,
            "--operation",
            "run",
            "--group-permit",
            str(permit),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("grouped execution adapter", completed.stderr)

    def test_forged_permit_is_refused_before_the_adapter_check(self) -> None:
        self.initialize_group()
        permit = self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        forged = json.loads(permit.read_text(encoding="utf-8"))
        forged["group_description_digest"] = digest("forged")
        forged_path = self.base / "forged.json"
        forged_path.write_text(json.dumps(forged), encoding="utf-8")
        completed = self.run_group(
            "check-enrollment",
            "--plan",
            self.alpha_path,
            "--operation",
            "run",
            "--group-permit",
            str(forged_path),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("different committed bytes", completed.stderr)

    def test_ungrouped_plan_keeps_existing_behavior(self) -> None:
        completed = self.run_group(
            "check-enrollment", "--plan", self.solo_path, "--operation", "completion"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("ungrouped", completed.stdout)

    def test_repository_without_group_directory_is_ungrouped(self) -> None:
        shutil.rmtree(self.repo / "docs/plan/execution-groups")
        self.commit("remove groups")
        completed = self.run_group(
            "check-enrollment", "--plan", self.alpha_path, "--operation", "run"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("ungrouped", completed.stdout)

    def test_legacy_ledger_entrypoints_refuse_an_enrolled_member(self) -> None:
        state = self.base / "execution.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(STATE_SCRIPT),
                "init",
                str(state),
                "--run-id",
                "run-1",
                "--plan",
                self.alpha_path,
                "--plan-digest",
                digest(self.alpha.read_text(encoding="utf-8")),
                "--source-head",
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
                ).strip(),
                "--primary-invariant-digest",
                digest("invariant 284"),
                "--lifecycle-state",
                str(self.base / "lifecycle.json"),
                "--implementation-mode",
                "candidate",
            ],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("enrolled in execution group", completed.stderr)
        self.assertFalse(state.exists())

    def test_legacy_ledger_gate_check_refuses_an_enrolled_member(self) -> None:
        """The gate must refuse on enrolment, not merely on a missing ledger."""

        ledger = self.base / "execution.json"
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        opened = subprocess.run(
            [
                sys.executable,
                str(STATE_SCRIPT),
                "init",
                str(ledger),
                "--run-id",
                "run-1",
                "--plan",
                self.solo_path,
                "--plan-digest",
                digest(self.solo.read_text(encoding="utf-8")),
                "--source-head",
                head,
                "--primary-invariant-digest",
                digest("invariant 290"),
                "--lifecycle-state",
                str(self.base / "lifecycle.json"),
                "--implementation-mode",
                "candidate",
            ],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(opened.returncode, 0, opened.stderr)

        enrolling = self.group_document()
        enrolling["group_id"] = "solo-group"
        enrolling["members"][1] = {
            "plan_id": "290",
            "plan_path": self.solo_path,
            "plan_digest": digest(self.solo.read_bytes()),
            "write_scope_digest": self.scope_digest(["src/solo.py"]),
        }
        (self.repo / "docs/plan/execution-groups/solo-group.json").write_text(
            json.dumps(enrolling, indent=2) + "\n", encoding="utf-8"
        )
        (self.repo / "docs/plan/execution-groups/alpha-beta.json").unlink()
        self.commit("enroll the previously ungrouped plan")

        completed = subprocess.run(
            [
                sys.executable,
                str(STATE_SCRIPT),
                "check",
                str(ledger),
                "--run-id",
                "run-1",
                "--plan",
                self.solo_path,
                "--operation",
                "execution",
            ],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("enrolled in execution group", completed.stderr)

    # -- regressions from independent review ----------------------------

    def test_uncommitted_worktree_deletion_does_not_unenroll_a_member(self) -> None:
        """A tracked description removed only in the worktree must fail closed."""

        self.description.unlink()
        completed = self.run_group(
            "check-enrollment", "--plan", self.alpha_path, "--operation", "completion"
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("tracked but missing from the working tree", completed.stderr)

    def test_staged_removal_does_not_unenroll_a_member(self) -> None:
        """A committed description keeps enrolling until its removal is committed."""

        subprocess.run(
            ["git", "rm", "-q", "docs/plan/execution-groups/alpha-beta.json"],
            cwd=self.repo,
            check=True,
        )
        completed = self.run_group(
            "check-enrollment", "--plan", self.alpha_path, "--operation", "completion"
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("tracked but missing from the working tree", completed.stderr)

        self.commit("commit the group removal")
        completed = self.run_group(
            "check-enrollment", "--plan", self.alpha_path, "--operation", "completion"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("ungrouped", completed.stdout)

    def test_truncated_description_fails_closed(self) -> None:
        self.description.write_text("", encoding="utf-8")
        completed = self.run_group(
            "check-enrollment", "--plan", self.alpha_path, "--operation", "run"
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("differs from its committed bytes", completed.stderr)

    def test_stray_files_do_not_block_ungrouped_plan_lifecycle(self) -> None:
        """A scratch file beside a description must not brick serial execution."""

        directory = self.repo / "docs/plan/execution-groups"
        for stray in (".alpha-beta.json.swp", ".DS_Store", "notes.md", "alpha-beta.json.bak"):
            with self.subTest(stray=stray):
                scratch = directory / stray
                scratch.write_text("scratch\n", encoding="utf-8")
                try:
                    completed = self.run_group(
                        "check-enrollment",
                        "--plan",
                        self.solo_path,
                        "--operation",
                        "completion",
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertIn("ungrouped", completed.stdout)
                    enrolled = self.run_group(
                        "check-enrollment",
                        "--plan",
                        self.alpha_path,
                        "--operation",
                        "completion",
                    )
                    self.assertEqual(enrolled.returncode, 1, enrolled.stdout)
                    self.assertIn("enrolled in execution group", enrolled.stderr)
                finally:
                    scratch.unlink()

    def test_worktree_rename_does_not_unenroll_a_member(self) -> None:
        self.description.rename(self.description.with_suffix(".json.bak"))
        completed = self.run_group(
            "check-enrollment", "--plan", self.alpha_path, "--operation", "run"
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("tracked but missing from the working tree", completed.stderr)

    def test_baseline_transfer_cannot_replenish_generation_budget(self) -> None:
        """Transfers must advance a real baseline, not mint fresh permits."""

        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()

        def transfer(prior: str, new: str, commit: str) -> subprocess.CompletedProcess[str]:
            return self.run_group(
                "transfer-baseline",
                str(self.state),
                "--member",
                self.alpha_path,
                "--prior-permit-id",
                prior,
                "--new-permit-id",
                new,
                "--new-base-commit",
                commit,
                "--workspace-digest",
                digest(new),
            )

        completed = transfer("permit-a1", "permit-a2", head)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("advance the recorded member baseline", completed.stderr)

        completed = transfer("permit-a1", "permit-a2", "b" * 40)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("does not name a commit", completed.stderr)

        unrelated = subprocess.check_output(
            ["git", "commit-tree", f"{head}^{{tree}}", "-m", "unrelated"],
            cwd=self.repo,
            text=True,
        ).strip()
        completed = transfer("permit-a1", "permit-a2", unrelated)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("descendant of the recorded member baseline", completed.stderr)

        advanced = self.commit("advance the baseline")
        completed = transfer("permit-a1", "permit-a2", advanced)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        self.run_group(
            "permit-release",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a2",
            check=True,
        )
        further = self.commit("advance again")
        completed = transfer("permit-a2", "permit-a3", further)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("exact open prior member permit", completed.stderr)

    def test_terminal_stop_stays_recordable_after_event_pressure(self) -> None:
        self.initialize_group()
        for index in range(64):
            acquired = self.run_group(
                "lease-acquire",
                str(self.state),
                "--member",
                self.alpha_path,
                "--owner",
                f"parent-{index}",
            )
            released = self.run_group(
                "lease-release", str(self.state), "--owner", f"parent-{index}"
            )
            if acquired.returncode != 0 or released.returncode != 0:
                break
        completed = self.run_group(
            "member-stop",
            str(self.state),
            "--member",
            self.alpha_path,
            "--reason",
            "owner_stop",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self.payload()["members"][self.alpha_path]["state"], "stopped"
        )

    def test_publication_lease_rejects_an_idempotent_reacquire(self) -> None:
        self.initialize_group()
        self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.alpha_path,
            "--owner",
            "parent-one",
            check=True,
        )
        completed = self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.alpha_path,
            "--owner",
            "parent-one",
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("already holds the publication lease", completed.stderr)

    def test_group_state_must_live_outside_the_repository(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        traversal = outside / ".." / "repo" / "state.json"
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()
        completed = self.run_group(
            "group-init",
            str(traversal),
            "--group-description",
            "docs/plan/execution-groups/alpha-beta.json",
            "--target-ref",
            "refs/heads/main",
            "--start-commit",
            head,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("must be outside the repository", completed.stderr)
        self.assertFalse((self.repo / "state.json").exists())

    def test_non_canonical_write_scope_spellings_are_refused(self) -> None:
        for spelling in ("./src/alpha.py", "src//alpha.py", "src/./alpha.py", "/src/alpha.py"):
            with self.subTest(spelling=spelling):
                self.write_plan("284", "alpha", [spelling])
                document = self.group_document()
                document["members"][0]["plan_digest"] = digest(self.alpha.read_bytes())
                document["members"][0]["write_scope_digest"] = self.scope_digest([spelling])
                self.write_description(document)
                self.commit(f"scope {spelling}")
                completed = self.run_group("validate-descriptions")
                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertIn("write scope entries must", completed.stderr)

    def test_reviews_must_advance_one_canonical_reviewer_registry(self) -> None:
        self.initialize_group()
        self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "2",
            "--registry-event-chain-digest",
            digest("chain-2"),
            check=True,
        )
        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("other-registry"),
            "--registry-event-count",
            "3",
            "--registry-event-chain-digest",
            digest("chain-3"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("one canonical reviewer registry", completed.stderr)

        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            self.alpha_path,
            "--registry-path-digest",
            digest("registry"),
            "--registry-event-count",
            "2",
            "--registry-event-chain-digest",
            digest("chain-9"),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("event count must advance", completed.stderr)

    def test_released_permit_is_refused_against_the_runtime_record(self) -> None:
        self.initialize_group()
        permit = self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "permit-release",
            str(self.state),
            "--member",
            self.alpha_path,
            "--permit-id",
            "permit-a1",
            check=True,
        )
        completed = self.run_group(
            "check-enrollment",
            "--plan",
            self.alpha_path,
            "--operation",
            "run",
            "--group-permit",
            str(permit),
            "--group-state",
            str(self.state),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("not the current open permit", completed.stderr)

    def test_stopped_member_permit_is_refused_against_the_runtime_record(self) -> None:
        self.initialize_group()
        permit = self.issue_permit(self.alpha_path, "permit-a1", "workspace-a")
        self.run_group(
            "member-stop",
            str(self.state),
            "--member",
            self.alpha_path,
            "--reason",
            "owner_stop",
            check=True,
        )
        completed = self.run_group(
            "check-enrollment",
            "--plan",
            self.alpha_path,
            "--operation",
            "run",
            "--group-permit",
            str(permit),
            "--group-state",
            str(self.state),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("stopped", completed.stderr)

    def test_root_and_generated_group_authority_stay_identical(self) -> None:
        generated = ROOT / "template/.project-agent-workflow/scripts/parallel-plan-state.py"
        self.assertTrue(generated.exists())
        self.assertEqual(GROUP_SCRIPT.read_bytes(), generated.read_bytes())
        self.assertTrue(os.access(generated, os.X_OK))


if __name__ == "__main__":
    unittest.main()
