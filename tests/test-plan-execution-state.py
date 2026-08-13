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

    def test_post_authoritative_change_requires_authoritative_event(self) -> None:
        affected = ("--invariant-digest", digest("one invariant"))
        self.assertNotEqual(self.record("design-early", "post_authoritative_design_change", *affected).returncode, 0)
        self.assertEqual(self.record("authoritative-1", "authoritative_validation").returncode, 0)
        self.assertEqual(self.record("design-1", "post_authoritative_design_change", *affected).returncode, 0)
        self.assertEqual(self.payload()["state"], "replan_required")

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


if __name__ == "__main__":
    unittest.main()
