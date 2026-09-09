#!/usr/bin/env python3
"""Behavior tests for the pre-v1 direct-update guard."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATOR = ROOT / "scripts/migrate-to-namespaced-layout.py"
WORKER_MIGRATOR = ROOT / "scripts/migrate-sequential-plan-worker.py"
VALIDATOR_PATH = ROOT / "scripts/validate-copier-update.py"
PROFILE_UPDATER_PATH = ROOT / "scripts/update_agent_model_profiles.py"
WITNESS_PROVENANCE_SNAPSHOTTER = ROOT / "scripts/snapshot-validation-witness-provenance.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_copier_update", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator_module()


def load_profile_updater_module():
    spec = importlib.util.spec_from_file_location("update_agent_model_profiles_for_migration_test", PROFILE_UPDATER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROFILE_UPDATER = load_profile_updater_module()


def load_witness_provenance_module():
    spec = importlib.util.spec_from_file_location(
        "snapshot_validation_witness_provenance_for_migration_test",
        WITNESS_PROVENANCE_SNAPSHOTTER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WITNESS_PROVENANCE = load_witness_provenance_module()

LEGACY_SEQUENTIAL_WORKER = '''name = "sequential_plan_worker"
description = "Bounded implementation worker for one assigned active plan with structured evidence and no descendant delegation."
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"

developer_instructions = """
Implement only the one active plan assigned by the parent.
Read the assigned plan and its required specs before editing.
Stay inside the explicit write scope; stop and report if the required change exceeds it.
Preserve unrelated user changes and do not weaken tests or validation.
Run every validation command required by the assigned plan.
Do not edit the assigned plan's status, ready_to_archive state, or archive location.
Do not process the next active plan.
Do not spawn descendant agents.
Do not commit changes.
Return changed paths, implementation summary, validation results, blockers, cross-plan impacts, and remaining risks.
"""
'''


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


class SequentialPlanWorkerMigrationTest(unittest.TestCase):
    def run_migration(self, destination: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(WORKER_MIGRATOR), "--destination", str(destination)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_replaces_only_the_exact_v121_generated_profile_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / ".codex/agents/sequential_plan_worker.toml"
            target.parent.mkdir(parents=True)
            target.write_text(LEGACY_SEQUENTIAL_WORKER, encoding="utf-8")

            first = self.run_migration(destination)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = (ROOT / "template/.codex/agents/sequential_plan_worker.toml").read_text(
                encoding="utf-8"
            )
            self.assertEqual(target.read_text(encoding="utf-8"), expected)
            self.assertIn("migrated", first.stdout)

            second = self.run_migration(destination)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), expected)
            self.assertIn("already read-only", second.stdout)

    def test_refuses_customized_workspace_write_profile_without_changing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / ".codex/agents/sequential_plan_worker.toml"
            target.parent.mkdir(parents=True)
            customized = LEGACY_SEQUENTIAL_WORKER.replace(
                "Read the assigned plan and its required specs before editing.",
                "Preserve this project-owned instruction.",
            )
            target.write_text(customized, encoding="utf-8")

            result = self.run_migration(destination)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customized workspace-write", result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), customized)

    def test_preserves_a_custom_read_only_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / ".codex/agents/sequential_plan_worker.toml"
            target.parent.mkdir(parents=True)
            customized = '''name = "sequential_plan_worker"
description = "Project-owned read-only worker."
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """Preserve this instruction."""
'''
            target.write_text(customized, encoding="utf-8")

            result = self.run_migration(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), customized)


class ValidationWitnessProvenanceMigrationTest(unittest.TestCase):
    RECORD = Path(
        ".project-agent-workflow-migration/validation-witness-provenance-v1.json"
    )
    POLICY = Path(".project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md")
    MARKER = "validation-witness-migration-provenance-schema: 1"
    ATTEMPT_STATE = Path(
        "project-agent-workflow/validation-witness-provenance-v1.attempt.json"
    )

    @staticmethod
    def sha(raw: bytes) -> str:
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repository = Path(temporary.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=repository, check=True
        )
        (repository / self.POLICY).parent.mkdir(parents=True)
        (repository / self.POLICY).write_text(
            "# Orchestration\n\nPre-migration policy.\n", encoding="utf-8"
        )
        (repository / ".copier-answers.yml").write_text(
            "_commit: v1.4.3\nproject_slug: fixture\n", encoding="utf-8"
        )
        plan_path = Path("docs/plan/active/902-pre-schema-integration.md")
        contract_path = Path("docs/plan/replanned/contracts/901-source.json")
        archive_path = Path("docs/plan/replanned/2026/08/16-31/901-source.md")
        plan = f"""# Pre-schema integration

status: in_progress
primary_invariant: preserve the committed integration identity
replan_contract: {contract_path.as_posix()}
acceptance:
  - Preserve the pre-schema acceptance.
validation:
  - python3 scripts/validate-changes.py --all
checked_summary_ja: 移行前の統合計画を保持する。

## Tasks

- [ ] Preserve the integration boundary.
"""
        plan_raw = plan.encode("utf-8")
        acceptance_digest = self.sha(b"Preserve the pre-schema acceptance.")
        contract = {
            "archive_path": archive_path.as_posix(),
            "contract_path": contract_path.as_posix(),
            "schema_version": 1,
            "successors": [
                {
                    "acceptance_digests": [acceptance_digest],
                    "content": plan,
                    "content_digest": self.sha(plan_raw),
                    "integration": True,
                    "path": plan_path.as_posix(),
                }
            ],
        }
        (repository / plan_path).parent.mkdir(parents=True)
        (repository / plan_path).write_bytes(plan_raw)
        (repository / contract_path).parent.mkdir(parents=True)
        (repository / contract_path).write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (repository / archive_path).parent.mkdir(parents=True)
        (repository / archive_path).write_text(
            "# Replanned source\n\nstatus: replanned\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "pre-migration baseline"],
            cwd=repository,
            check=True,
        )
        return temporary, repository

    def git_directory(self, repository: Path) -> Path:
        return Path(
            subprocess.check_output(
                ["git", "rev-parse", "--path-format=absolute", "--absolute-git-dir"],
                cwd=repository,
                text=True,
            ).strip()
        )

    def attempt_state_path(self, repository: Path) -> Path:
        return self.git_directory(repository) / self.ATTEMPT_STATE

    def attempt_state(self, repository: Path) -> dict[str, object]:
        return json.loads(self.attempt_state_path(repository).read_text(encoding="utf-8"))

    def stop_guardian(self, repository: Path, pid: int | None = None) -> None:
        if pid is None:
            try:
                pid = int(self.attempt_state(repository)["guardian_pid"])
            except (FileNotFoundError, KeyError, TypeError, ValueError):
                return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.01)

    def run_stage(
        self,
        repository: Path,
        stage: str,
        *,
        lifetime: float = 5,
        failpoint: str | None = None,
        environment_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "python3",
            str(WITNESS_PROVENANCE_SNAPSHOTTER),
            "--destination",
            str(repository),
            "--stage",
            stage,
            "--guardian-lifetime-seconds",
            str(lifetime),
        ]
        environment = os.environ.copy()
        if environment_overrides:
            environment.update(environment_overrides)
        if failpoint is not None:
            command.extend(("--test-failpoint", failpoint))
            environment["PROJECT_AGENT_WORKFLOW_TESTING"] = "1"
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=environment,
        )
        if stage == "before" and result.returncode == 0:
            pid = int(self.attempt_state(repository)["guardian_pid"])
            self.addCleanup(self.stop_guardian, repository, pid)
        return result

    @staticmethod
    def protocol_message(value: dict[str, object]) -> bytes:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("ascii")

    @staticmethod
    def receive_protocol(channel: socket.socket) -> dict[str, object]:
        raw = b""
        while not raw.endswith(b"\n"):
            chunk = channel.recv(4096)
            if not chunk:
                break
            raw += chunk
        return json.loads(raw)

    def install_policy_marker(self, repository: Path) -> None:
        (repository / self.POLICY).write_text(
            f"# Orchestration\n\n`{self.MARKER}` is installed.\n",
            encoding="utf-8",
        )

    def test_captures_and_verifies_exact_committed_integration_provenance(self) -> None:
        _temporary, repository = self.make_repository()
        before = self.run_stage(repository, "before")
        self.assertEqual(before.returncode, 0, before.stderr)
        record = json.loads((repository / self.RECORD).read_text(encoding="utf-8"))
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["migration_version"], "v1.4.5")
        self.assertEqual(record["copier_answers"]["previous_template_ref"], "v1.4.3")
        self.assertEqual(
            [item["path"] for item in record["plans"]],
            ["docs/plan/active/902-pre-schema-integration.md"],
        )
        self.assertEqual(
            record["plans"][0]["acceptance"][0]["sha256"],
            self.sha(b"Preserve the pre-schema acceptance."),
        )
        self.assertNotIn("capability", record)
        state = self.attempt_state(repository)
        self.assertEqual(state["state"], "pending")
        self.assertRegex(str(state["capability_commitment"]), r"^sha256:[0-9a-f]{64}$")
        self.install_policy_marker(repository)
        after = self.run_stage(repository, "after")
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(self.attempt_state(repository)["state"], "consumed")
        same_guardian_retry = self.run_stage(repository, "after")
        self.assertEqual(same_guardian_retry.returncode, 0, same_guardian_retry.stderr)
        pid = int(state["guardian_pid"])
        self.stop_guardian(repository, pid)
        replay = self.run_stage(repository, "after")
        self.assertNotEqual(replay.returncode, 0)
        self.assertIn("guardian", replay.stderr)

    def test_after_stage_rejects_missing_and_forged_provenance(self) -> None:
        with self.subTest(case="missing"):
            _temporary, repository = self.make_repository()
            self.install_policy_marker(repository)
            result = self.run_stage(repository, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("attempt state is missing", result.stderr)
        with self.subTest(case="forged"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            (repository / self.RECORD).write_text("{}\n", encoding="utf-8")
            self.install_policy_marker(repository)
            result = self.run_stage(repository, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("snapshot digest", result.stderr)

    def test_rejects_stale_dirty_untracked_and_replayed_provenance(self) -> None:
        with self.subTest(case="stale"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            plan = repository / "docs/plan/active/902-pre-schema-integration.md"
            plan.write_text(plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            subprocess.run(["git", "add", str(plan)], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "change plan"], cwd=repository, check=True)
            self.install_policy_marker(repository)
            result = self.run_stage(repository, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source HEAD is stale", result.stderr)
        for case, relative in (
            ("dirty", ".copier-answers.yml"),
            ("untracked", "docs/plan/active/999-untracked.md"),
        ):
            with self.subTest(case=case):
                _temporary, repository = self.make_repository()
                path = repository / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("unexpected worktree state\n", encoding="utf-8")
                result = self.run_stage(repository, "before")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("clean committed worktree", result.stderr)
        with self.subTest(case="replayed"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            result = self.run_stage(repository, "before")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot be replayed", result.stderr)

    def test_rejects_symlinked_input_and_post_boundary_capture(self) -> None:
        with self.subTest(case="symlink"):
            _temporary, repository = self.make_repository()
            contract = repository / "docs/plan/replanned/contracts/901-source.json"
            saved = contract.with_name("saved-source.json")
            contract.rename(saved)
            contract.symlink_to(saved.name)
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "symlink contract"], cwd=repository, check=True
            )
            result = self.run_stage(repository, "before")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-symlink regular file", result.stderr)
        with self.subTest(case="post-boundary"):
            _temporary, repository = self.make_repository()
            self.install_policy_marker(repository)
            subprocess.run(["git", "add", str(self.POLICY)], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "install migration boundary"],
                cwd=repository,
                check=True,
            )
            result = self.run_stage(repository, "before")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already contains", result.stderr)

    def test_rejects_cross_clone_and_unsafe_record_replay(self) -> None:
        with self.subTest(case="cross-clone"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            clone_temporary = tempfile.TemporaryDirectory()
            self.addCleanup(clone_temporary.cleanup)
            clone = Path(clone_temporary.name) / "clone"
            subprocess.run(
                ["git", "clone", "-q", str(repository), str(clone)], check=True
            )
            copied_record = clone / self.RECORD
            copied_record.parent.mkdir(parents=True)
            copied_record.write_bytes((repository / self.RECORD).read_bytes())
            copied_state = self.attempt_state_path(clone)
            copied_state.parent.mkdir(parents=True)
            copied_state.parent.chmod(0o700)
            copied_state.write_bytes(self.attempt_state_path(repository).read_bytes())
            copied_state.chmod(0o600)
            self.install_policy_marker(clone)
            result = self.run_stage(clone, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("another repository clone", result.stderr)
        with self.subTest(case="consumed-cross-clone"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            self.install_policy_marker(repository)
            consumed = self.run_stage(repository, "after")
            self.assertEqual(consumed.returncode, 0, consumed.stderr)
            source_state = self.attempt_state_path(repository).read_bytes()
            source_record = (repository / self.RECORD).read_bytes()
            source_pid = int(json.loads(source_state)["guardian_pid"])
            self.stop_guardian(repository, source_pid)
            clone_temporary = tempfile.TemporaryDirectory()
            self.addCleanup(clone_temporary.cleanup)
            clone = Path(clone_temporary.name) / "clone"
            subprocess.run(
                ["git", "clone", "-q", str(repository), str(clone)], check=True
            )
            copied_record = clone / self.RECORD
            copied_record.parent.mkdir(parents=True)
            copied_record.write_bytes(source_record)
            copied_state = self.attempt_state_path(clone)
            copied_state.parent.mkdir(parents=True)
            copied_state.parent.chmod(0o700)
            copied_state.write_bytes(source_state)
            copied_state.chmod(0o600)
            self.install_policy_marker(clone)
            result = self.run_stage(clone, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("another repository clone", result.stderr)
        for case in ("symlink", "hardlink", "oversize"):
            with self.subTest(case=case):
                _temporary, repository = self.make_repository()
                self.assertEqual(self.run_stage(repository, "before").returncode, 0)
                record = repository / self.RECORD
                saved = record.with_name(f"saved-{case}.json")
                record.rename(saved)
                if case == "symlink":
                    record.symlink_to(saved.name)
                elif case == "hardlink":
                    record.hardlink_to(saved)
                else:
                    record.write_bytes(b"x" * (512 * 1024 + 1))
                self.install_policy_marker(repository)
                result = self.run_stage(repository, "after")
                self.assertNotEqual(result.returncode, 0)
                if case == "symlink":
                    self.assertIn("missing or unsafe", result.stderr)
                elif case == "hardlink":
                    self.assertIn("single-link regular file", result.stderr)
                else:
                    self.assertIn("byte bound", result.stderr)

    def test_rejects_challenge_and_consume_acknowledgement_mismatch(self) -> None:
        _temporary, repository = self.make_repository()
        self.assertEqual(self.run_stage(repository, "before").returncode, 0)
        self.install_policy_marker(repository)
        state_raw = self.attempt_state_path(repository).read_bytes()
        state = json.loads(state_raw)
        git_dir = self.git_directory(repository)
        socket_path = WITNESS_PROVENANCE.PurePosixPath(str(state["socket_path"]))

        with WITNESS_PROVENANCE.connect_guardian_socket(git_dir, socket_path) as channel:
            channel.sendall(
                self.protocol_message(
                    {
                        "attempt_id": state["attempt_id"],
                        "challenge": "11" * 31,
                        "protocol_version": 1,
                        "state_sha256": self.sha(state_raw),
                        "type": "challenge",
                    }
                )
            )
            self.assertEqual(self.receive_protocol(channel), {"type": "error"})

        with WITNESS_PROVENANCE.connect_guardian_socket(git_dir, socket_path) as channel:
            channel.sendall(
                self.protocol_message(
                    {
                        "attempt_id": state["attempt_id"],
                        "challenge": "22" * 32,
                        "protocol_version": 1,
                        "state_sha256": self.sha(state_raw),
                        "type": "challenge",
                    }
                )
            )
            response = self.receive_protocol(channel)
            self.assertEqual(response["type"], "challenge_response")
            channel.sendall(
                self.protocol_message({"proof": "00" * 32, "type": "consume_ack"})
            )
            self.assertEqual(self.receive_protocol(channel), {"type": "error"})
        self.assertEqual(self.attempt_state(repository)["state"], "pending")

    def test_rejects_cross_clone_with_poisoned_git_environment(self) -> None:
        _temporary, source = self.make_repository()
        self.assertEqual(self.run_stage(source, "before").returncode, 0)
        clone_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(clone_temporary.cleanup)
        clone = Path(clone_temporary.name) / "clone"
        subprocess.run(["git", "clone", "-q", str(source), str(clone)], check=True)
        copied_record = clone / self.RECORD
        copied_record.parent.mkdir(parents=True)
        copied_record.write_bytes((source / self.RECORD).read_bytes())
        copied_state = self.attempt_state_path(clone)
        copied_state.parent.mkdir(parents=True)
        copied_state.parent.chmod(0o700)
        copied_state.write_bytes(self.attempt_state_path(source).read_bytes())
        copied_state.chmod(0o600)
        self.install_policy_marker(clone)
        result = self.run_stage(
            clone,
            "after",
            environment_overrides={
                "GIT_DIR": str(self.git_directory(source)),
                "GIT_WORK_TREE": str(clone),
                "GIT_COMMON_DIR": str(self.git_directory(source)),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.worktree",
                "GIT_CONFIG_VALUE_0": str(clone),
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another repository clone", result.stderr)

    def test_same_guardian_recovers_from_lost_consume_response(self) -> None:
        _temporary, repository = self.make_repository()
        before = self.run_stage(
            repository, "before", failpoint="drop_final_response"
        )
        self.assertEqual(before.returncode, 0, before.stderr)
        self.install_policy_marker(repository)
        lost = self.run_stage(repository, "after")
        self.assertNotEqual(lost.returncode, 0)
        self.assertIn("response was lost", lost.stderr)
        self.assertEqual(self.attempt_state(repository)["state"], "consumed")
        retry = self.run_stage(repository, "after")
        self.assertEqual(retry.returncode, 0, retry.stderr)

    def test_recovers_every_interrupted_publication_before_pending_authority(self) -> None:
        for failpoint in (
            "after_prepared",
            "after_listen",
            "after_snapshot",
            "after_pending",
        ):
            with self.subTest(failpoint=failpoint):
                _temporary, repository = self.make_repository()
                interrupted = self.run_stage(
                    repository, "before", failpoint=failpoint
                )
                self.assertNotEqual(interrupted.returncode, 0)
                state_path = self.attempt_state_path(repository)
                self.assertTrue(state_path.is_file())
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if failpoint == "after_prepared":
                    preparing = state_path.with_name(f".{state_path.name}.preparing")
                    raw = state_path.read_bytes()
                    state_path.rename(preparing)
                    preparing.write_bytes(raw[: len(raw) // 2])
                    preparing.chmod(0o600)
                if failpoint == "after_snapshot":
                    record = repository / self.RECORD
                    record_raw = record.read_bytes()
                    record.write_bytes(record_raw[: len(record_raw) // 2])
                    temporary = state_path.with_name(
                        f".{state_path.name}.{state['attempt_id']}.tmp"
                    )
                    pending = {**state, "state": "pending"}
                    pending_bytes = (
                        json.dumps(pending, sort_keys=True, indent=2) + "\n"
                    ).encode("utf-8")
                    temporary.write_bytes(pending_bytes[: len(pending_bytes) // 2])
                    temporary.chmod(0o600)
                if failpoint == "after_pending":
                    temporary = state_path.with_name(
                        f".{state_path.name}.{state['attempt_id']}.tmp"
                    )
                    consumed = {**state, "state": "consumed"}
                    consumed_bytes = (
                        json.dumps(consumed, sort_keys=True, indent=2) + "\n"
                    ).encode("utf-8")
                    temporary.write_bytes(consumed_bytes[: len(consumed_bytes) // 2])
                    temporary.chmod(0o600)
                recovered = self.run_stage(repository, "recover")
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assertFalse(state_path.exists())
                self.assertFalse((repository / self.RECORD).exists())

    def test_consumed_publication_is_terminal_after_guardian_dies(self) -> None:
        _temporary, repository = self.make_repository()
        before = self.run_stage(repository, "before", failpoint="after_consumed")
        self.assertEqual(before.returncode, 0, before.stderr)
        self.install_policy_marker(repository)
        interrupted = self.run_stage(repository, "after")
        self.assertNotEqual(interrupted.returncode, 0)
        self.assertEqual(self.attempt_state(repository)["state"], "consumed")
        (repository / self.POLICY).write_text(
            "# Orchestration\n\nPre-migration policy.\n", encoding="utf-8"
        )
        recovery = self.run_stage(repository, "recover")
        self.assertNotEqual(recovery.returncode, 0)
        self.assertIn("terminal", recovery.stderr)
        replay = self.run_stage(repository, "after")
        self.assertNotEqual(replay.returncode, 0)

    def test_recovery_is_idempotent_at_every_durable_cleanup_point(self) -> None:
        for failpoint in (
            "recover_after_state",
            "recover_after_snapshot",
            "recover_after_lock",
        ):
            with self.subTest(failpoint=failpoint):
                _temporary, repository = self.make_repository()
                interrupted_before = self.run_stage(
                    repository, "before", failpoint="after_pending"
                )
                self.assertNotEqual(interrupted_before.returncode, 0)
                interrupted_recovery = self.run_stage(
                    repository, "recover", failpoint=failpoint
                )
                self.assertNotEqual(interrupted_recovery.returncode, 0)
                resumed = self.run_stage(repository, "recover")
                self.assertEqual(resumed.returncode, 0, resumed.stderr)
                self.assertFalse(self.attempt_state_path(repository).exists())
                self.assertFalse((repository / self.RECORD).exists())

    def test_recovery_rejects_changed_boundary_and_mismatched_snapshot(self) -> None:
        with self.subTest(case="changed-source-head"):
            _temporary, repository = self.make_repository()
            interrupted = self.run_stage(
                repository, "before", failpoint="after_pending"
            )
            self.assertNotEqual(interrupted.returncode, 0)
            plan = repository / "docs/plan/active/902-pre-schema-integration.md"
            plan.write_text(
                plan.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", str(plan)], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "change recovery source"],
                cwd=repository,
                check=True,
            )
            recovery = self.run_stage(repository, "recover")
            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("source HEAD changed", recovery.stderr)

        with self.subTest(case="migration-boundary-present"):
            _temporary, repository = self.make_repository()
            interrupted = self.run_stage(
                repository, "before", failpoint="after_pending"
            )
            self.assertNotEqual(interrupted.returncode, 0)
            self.install_policy_marker(repository)
            subprocess.run(["git", "add", str(self.POLICY)], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "install migration boundary"],
                cwd=repository,
                check=True,
            )
            recovery = self.run_stage(repository, "recover")
            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("forbidden after the migration boundary", recovery.stderr)

        for failpoint in ("after_snapshot", "after_pending"):
            with self.subTest(case="mismatched-snapshot", failpoint=failpoint):
                _temporary, repository = self.make_repository()
                interrupted = self.run_stage(
                    repository, "before", failpoint=failpoint
                )
                self.assertNotEqual(interrupted.returncode, 0)
                (repository / self.RECORD).write_bytes(b"not-a-snapshot-prefix\n")
                recovery = self.run_stage(repository, "recover")
                self.assertNotEqual(recovery.returncode, 0)
                self.assertIn("snapshot does not match", recovery.stderr)

    def test_guardian_timeout_rejects_after_stage_and_allows_verified_recovery(self) -> None:
        _temporary, repository = self.make_repository()
        before = self.run_stage(repository, "before", lifetime=0.1)
        self.assertEqual(before.returncode, 0, before.stderr)
        time.sleep(0.35)
        self.install_policy_marker(repository)
        expired = self.run_stage(repository, "after")
        self.assertNotEqual(expired.returncode, 0)
        self.assertIn("expired", expired.stderr)
        (repository / self.POLICY).write_text(
            "# Orchestration\n\nPre-migration policy.\n", encoding="utf-8"
        )
        recovered = self.run_stage(repository, "recover")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)

    def test_guardian_lifetime_and_threat_boundary_are_fixed(self) -> None:
        self.assertEqual(
            WITNESS_PROVENANCE.validate_lifetime(60 * 60),
            WITNESS_PROVENANCE.DEFAULT_GUARDIAN_LIFETIME_SECONDS,
        )
        for invalid in (0, -1, 60 * 60 + 0.001):
            with self.subTest(invalid=invalid):
                with self.assertRaises(WITNESS_PROVENANCE.ProvenanceError):
                    WITNESS_PROVENANCE.validate_lifetime(invalid)
        expected_boundary = (
            "Copying repository and Git-local files without the original live guardian "
            "fails; an unrestricted same-user actor that can replace every local process "
            "and file is outside this guarantee."
        )
        self.assertEqual(WITNESS_PROVENANCE.THREAT_BOUNDARY, expected_boundary)
        self.assertIn(expected_boundary, WITNESS_PROVENANCE.__doc__)

    def test_guardian_rechecks_expiry_before_consuming_acknowledgement(self) -> None:
        _temporary, repository = self.make_repository()
        before = self.run_stage(repository, "before", lifetime=0.8)
        self.assertEqual(before.returncode, 0, before.stderr)
        self.install_policy_marker(repository)
        state_raw = self.attempt_state_path(repository).read_bytes()
        state = json.loads(state_raw)
        challenge = "44" * 32
        git_dir = self.git_directory(repository)
        socket_path = WITNESS_PROVENANCE.PurePosixPath(str(state["socket_path"]))
        with WITNESS_PROVENANCE.connect_guardian_socket(
            git_dir, socket_path
        ) as channel:
            channel.sendall(
                self.protocol_message(
                    {
                        "attempt_id": state["attempt_id"],
                        "challenge": challenge,
                        "protocol_version": 1,
                        "state_sha256": self.sha(state_raw),
                        "type": "challenge",
                    }
                )
            )
            response = self.receive_protocol(channel)
            self.assertEqual(response["type"], "challenge_response")
            capability = bytes.fromhex(str(response["capability"]))
            remaining = max(
                0,
                (int(state["expires_at_unix_ns"]) - time.time_ns()) / 1_000_000_000,
            )
            time.sleep(remaining + 0.05)
            channel.sendall(
                self.protocol_message(
                    {
                        "proof": WITNESS_PROVENANCE.protocol_mac(
                            capability,
                            WITNESS_PROVENANCE.ACK_DOMAIN,
                            challenge,
                            self.sha(state_raw),
                        ),
                        "type": "consume_ack",
                    }
                )
            )
            self.assertEqual(self.receive_protocol(channel), {"type": "error"})
        self.assertEqual(self.attempt_state(repository)["state"], "pending")

    def test_guardian_rejects_expiry_crossed_during_final_revalidation(self) -> None:
        _temporary, repository = self.make_repository()
        before = self.run_stage(
            repository,
            "before",
            lifetime=0.8,
            failpoint="delay_after_final_revalidation",
        )
        self.assertEqual(before.returncode, 0, before.stderr)
        self.install_policy_marker(repository)
        result = self.run_stage(repository, "after")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("guardian", result.stderr)
        self.assertEqual(self.attempt_state(repository)["state"], "pending")

    def test_rejects_pid_state_mutation_and_socket_pathname_replacement(self) -> None:
        with self.subTest(case="pid-state-mutation"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            self.install_policy_marker(repository)
            state_path = self.attempt_state_path(repository)
            original = state_path.read_bytes()
            state = json.loads(original)
            original_pid = int(state["guardian_pid"])
            state["guardian_pid"] = original_pid + 1
            state_path.write_text(
                json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            result = self.run_stage(repository, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("guardian", result.stderr)
            state_path.write_bytes(original)
            state_path.chmod(0o600)
            self.stop_guardian(repository, original_pid)

        with self.subTest(case="socket-pathname-replacement"):
            _temporary, repository = self.make_repository()
            self.assertEqual(self.run_stage(repository, "before").returncode, 0)
            self.install_policy_marker(repository)
            state = self.attempt_state(repository)
            socket_path = self.git_directory(repository) / str(state["socket_path"])
            socket_path.unlink()
            socket_path.write_text("replacement\n", encoding="utf-8")
            result = self.run_stage(repository, "after")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a socket", result.stderr)

    def test_rejects_every_normalized_path_class_and_symlink_boundary(self) -> None:
        invalid = (
            "/absolute",
            "../traversal",
            "a/../traversal",
            "a/./dot",
            "a\\backslash",
            "nul\0byte",
            "a//double",
        )
        for value in invalid:
            with self.subTest(value=repr(value)):
                with self.assertRaises(WITNESS_PROVENANCE.ProvenanceError):
                    WITNESS_PROVENANCE.normalize_path(value, "test path")
        exact = "a" * 4096
        self.assertEqual(WITNESS_PROVENANCE.normalize_path(exact, "test path"), exact)
        with self.assertRaises(WITNESS_PROVENANCE.ProvenanceError):
            WITNESS_PROVENANCE.normalize_path(exact + "a", "test path")

        with self.subTest(case="symlink-ancestor"):
            _temporary, repository = self.make_repository()
            git_dir = self.git_directory(repository)
            outside = Path(tempfile.mkdtemp())
            self.addCleanup(outside.rmdir)
            (git_dir / "project-agent-workflow").symlink_to(outside, target_is_directory=True)
            result = self.run_stage(repository, "before")
            self.assertNotEqual(result.returncode, 0)

        with self.subTest(case="final-symlink"):
            _temporary, repository = self.make_repository()
            interrupted = self.run_stage(
                repository, "before", failpoint="after_prepared"
            )
            self.assertNotEqual(interrupted.returncode, 0)
            state_path = self.attempt_state_path(repository)
            saved = state_path.with_name("saved-attempt.json")
            state_path.rename(saved)
            state_path.symlink_to(saved.name)
            result = self.run_stage(repository, "recover")
            self.assertNotEqual(result.returncode, 0)

    def test_enforces_declared_byte_and_plan_count_boundaries(self) -> None:
        _temporary, repository = self.make_repository()
        limits = {
            "plan": WITNESS_PROVENANCE.MAX_PLAN_BYTES,
            "contract": WITNESS_PROVENANCE.MAX_CONTRACT_BYTES,
            "policy": WITNESS_PROVENANCE.MAX_POLICY_BYTES,
            "answers": WITNESS_PROVENANCE.MAX_ANSWERS_BYTES,
        }
        for label, maximum in limits.items():
            exact = repository / f"limits/{label}-exact.bin"
            overflow = repository / f"limits/{label}-overflow.bin"
            exact.parent.mkdir(parents=True, exist_ok=True)
            exact.write_bytes(b"x" * maximum)
            overflow.write_bytes(b"x" * (maximum + 1))
        subprocess.run(["git", "add", "limits"], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "add byte limits"], cwd=repository, check=True)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
        for label, maximum in limits.items():
            with self.subTest(label=label, boundary="exact"):
                raw = WITNESS_PROVENANCE.committed_file(
                    repository,
                    head,
                    f"limits/{label}-exact.bin",
                    maximum,
                    label,
                )
                self.assertEqual(len(raw), maximum)
            with self.subTest(label=label, boundary="overflow"):
                with self.assertRaises(WITNESS_PROVENANCE.ProvenanceError):
                    WITNESS_PROVENANCE.committed_file(
                        repository,
                        head,
                        f"limits/{label}-overflow.bin",
                        maximum,
                        label,
                    )

        with tempfile.TemporaryDirectory() as local:
            local_root = Path(local)
            for label, maximum, mode in (
                ("snapshot", WITNESS_PROVENANCE.MAX_RECORD_BYTES, 0o644),
                ("attempt", WITNESS_PROVENANCE.MAX_ATTEMPT_STATE_BYTES, 0o600),
            ):
                relative = WITNESS_PROVENANCE.PurePosixPath(f"{label}/exact")
                WITNESS_PROVENANCE.write_exclusive(
                    local_root,
                    relative,
                    b"x" * maximum,
                    maximum,
                    label,
                    mode=mode,
                    directory_mode=0o700,
                )
                self.assertEqual((local_root / relative).stat().st_size, maximum)
                with self.assertRaises(WITNESS_PROVENANCE.ProvenanceError):
                    WITNESS_PROVENANCE.write_exclusive(
                        local_root,
                        WITNESS_PROVENANCE.PurePosixPath(f"{label}/overflow"),
                        b"x" * (maximum + 1),
                        maximum,
                        label,
                        mode=mode,
                        directory_mode=0o700,
                    )

        left, right = socket.socketpair()
        with left, right:
            overhead = len(WITNESS_PROVENANCE.compact_json({"payload": ""}))
            exact_message = WITNESS_PROVENANCE.compact_json(
                {"payload": "x" * (WITNESS_PROVENANCE.MAX_PROTOCOL_MESSAGE_BYTES - overhead)}
            )
            self.assertEqual(
                len(exact_message), WITNESS_PROVENANCE.MAX_PROTOCOL_MESSAGE_BYTES
            )
            left.sendall(exact_message)
            self.assertEqual(
                len(WITNESS_PROVENANCE.receive_message(right, "exact")["payload"]),
                WITNESS_PROVENANCE.MAX_PROTOCOL_MESSAGE_BYTES - overhead,
            )
        left, right = socket.socketpair()
        with left, right:
            left.sendall(b"x" * (WITNESS_PROVENANCE.MAX_PROTOCOL_MESSAGE_BYTES + 1))
            with self.assertRaisesRegex(
                WITNESS_PROVENANCE.ProvenanceError, "byte bound"
            ):
                WITNESS_PROVENANCE.receive_message(right, "overflow")

        capability = b"c" * WITNESS_PROVENANCE.CAPABILITY_BYTES
        self.assertRegex(
            WITNESS_PROVENANCE.capability_commitment(
                "a" * 64,
                head,
                "sha256:" + "b" * 64,
                "sha256:" + "d" * 64,
                capability,
            ),
            r"^sha256:[0-9a-f]{64}$",
        )
        for wrong in (capability[:-1], capability + b"c"):
            with self.assertRaises(WITNESS_PROVENANCE.ProvenanceError):
                WITNESS_PROVENANCE.capability_commitment(
                    "a" * 64,
                    head,
                    "sha256:" + "b" * 64,
                    "sha256:" + "d" * 64,
                    wrong,
                )

        contract_path = Path("docs/plan/replanned/contracts/plan-count-limit.json")
        archive_path = Path("docs/plan/replanned/2026/08/16-31/901-source.md")
        acceptance_text = "Preserve the bounded plan inventory."
        acceptance_digest = self.sha(acceptance_text.encode("utf-8"))
        successors: list[dict[str, object]] = []

        def add_counted_plan(number: int) -> None:
            plan_path = Path(f"docs/plan/active/{number}-counted-integration.md")
            plan = f"""# Counted integration {number}

status: in_progress
primary_invariant: preserve counted integration {number}
replan_contract: {contract_path.as_posix()}
acceptance:
  - {acceptance_text}
validation:
  - python3 scripts/validate-changes.py --all
checked_summary_ja: 件数境界を検証する。

## Tasks

- [ ] Preserve the counted integration.
"""
            raw = plan.encode("utf-8")
            (repository / plan_path).write_bytes(raw)
            successors.append(
                {
                    "acceptance_digests": [acceptance_digest],
                    "content": plan,
                    "content_digest": self.sha(raw),
                    "integration": True,
                    "path": plan_path.as_posix(),
                }
            )

        def write_count_contract() -> None:
            (repository / contract_path).write_text(
                json.dumps(
                    {
                        "archive_path": archive_path.as_posix(),
                        "contract_path": contract_path.as_posix(),
                        "schema_version": 1,
                        "successors": successors,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        for number in range(903, 966):
            add_counted_plan(number)
        write_count_contract()
        subprocess.run(["git", "add", "docs/plan"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "add exact plan-count boundary"],
            cwd=repository,
            check=True,
        )
        exact_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        self.assertEqual(
            len(WITNESS_PROVENANCE.build_record(repository, exact_head)["plans"]),
            WITNESS_PROVENANCE.MAX_CAPTURED_PLANS,
        )

        add_counted_plan(966)
        write_count_contract()
        subprocess.run(["git", "add", "docs/plan"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "overflow plan-count boundary"],
            cwd=repository,
            check=True,
        )
        overflow_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        with self.assertRaisesRegex(
            WITNESS_PROVENANCE.ProvenanceError, "64-plan bound"
        ):
            WITNESS_PROVENANCE.build_record(repository, overflow_head)


class CopierOwnedContentValidationTest(unittest.TestCase):
    def test_validator_seeded_profiles_match_the_normalizer(self) -> None:
        self.assertEqual(VALIDATOR.SEEDED_AGENT_PROFILES, PROFILE_UPDATER.PROFILES)

    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        repository = Path(temporary.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
        (repository / ".project-agent-workflow").mkdir()
        (repository / ".project-agent-workflow/ownership.yaml").write_bytes(
            (ROOT / "template/.project-agent-workflow/ownership.yaml").read_bytes()
        )
        (repository / "AGENTS.md").write_text("project policy\n", encoding="utf-8")
        (repository / ".copier-answers.yml").write_text("_commit: v1.2.1\n", encoding="utf-8")
        agents = repository / ".codex/agents"
        agents.mkdir(parents=True)
        (agents / "repo_explorer.toml").write_text(
            '''name = "repo_explorer"
description = "Project helper."
model = "old-model"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """Preserve this instruction."""
''',
            encoding="utf-8",
        )
        (agents / "sequential_plan_worker.toml").write_text(
            LEGACY_SEQUENTIAL_WORKER, encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repository, check=True)
        return temporary, repository

    def test_rejects_project_owned_and_unclassified_content_changes(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        for relative in ("AGENTS.md", "product.txt"):
            with self.subTest(relative=relative):
                path = repository / relative
                if relative == "product.txt":
                    path.write_text("baseline\n", encoding="utf-8")
                    subprocess.run(["git", "add", relative], cwd=repository, check=True)
                    subprocess.run(["git", "commit", "-qm", "add product"], cwd=repository, check=True)
                path.write_text("unexpected update\n", encoding="utf-8")
                with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "project-owned"):
                    VALIDATOR.validate(repository)
                subprocess.run(["git", "restore", relative], cwd=repository, check=True)

    def test_rejects_a_git_repository_without_a_committed_ownership_inventory(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        subprocess.run(
            ["git", "rm", "-q", ".project-agent-workflow/ownership.yaml"],
            cwd=repository,
            check=True,
        )
        subprocess.run(["git", "commit", "-qm", "remove ownership inventory"], cwd=repository, check=True)
        (repository / "AGENTS.md").write_text("unexpected update\n", encoding="utf-8")
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "ownership inventory"):
            VALIDATOR.validate(repository)

    def test_rejects_replacement_of_a_declared_project_owned_model_field(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (repository / ".project-agent-workflow/managed.txt").write_text("managed\n", encoding="utf-8")
        agent = repository / ".codex/agents/repo_explorer.toml"
        original = agent.read_text(encoding="utf-8")
        for before, after in (
            ('model = "old-model"', 'model = "gpt-5.6-luna"'),
            ('model_reasoning_effort = "medium"', 'model_reasoning_effort = "low"'),
        ):
            with self.subTest(field=before):
                agent.write_text(original.replace(before, after, 1), encoding="utf-8")
                with self.assertRaisesRegex(
                    VALIDATOR.UpdateValidationError, "project-owned agent profile field"
                ):
                    VALIDATOR.validate(repository)
        agent.write_text(original, encoding="utf-8")
        VALIDATOR.validate(repository)

    def test_allows_inserting_only_an_absent_default(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        without_effort = agent.read_text(encoding="utf-8").replace(
            'model_reasoning_effort = "medium"\n', ""
        )
        agent.write_text(without_effort, encoding="utf-8")
        subprocess.run(["git", "add", str(agent.relative_to(repository))], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "drop the effort field"], cwd=repository, check=True)

        filled = PROFILE_UPDATER.render_profile(
            without_effort, *PROFILE_UPDATER.PROFILES["repo_explorer"]
        )
        self.assertIn('model = "old-model"', filled)
        self.assertIn('model_reasoning_effort = "low"', filled)
        agent.write_text(filled, encoding="utf-8")
        VALIDATOR.validate(repository)

        agent.write_text(
            filled.replace('model_reasoning_effort = "low"', 'model_reasoning_effort = "high"', 1),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "unexpected default"):
            VALIDATOR.validate(repository)

    def test_preserves_model_fields_when_project_owns_a_custom_profile_name(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        customized = agent.read_text(encoding="utf-8").replace(
            'name = "repo_explorer"', 'name = "project_repository_reader"'
        )
        agent.write_text(customized, encoding="utf-8")
        subprocess.run(["git", "add", str(agent.relative_to(repository))], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "customize profile name"], cwd=repository, check=True)

        rendered = PROFILE_UPDATER.render_profile(
            customized, *PROFILE_UPDATER.PROFILES["repo_explorer"]
        )
        self.assertEqual(rendered, customized)
        agent.write_text(rendered, encoding="utf-8")

        VALIDATOR.validate(repository)

    def test_rejects_any_change_to_an_unseeded_agent_profile(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/project_custom.toml"
        agent.write_text(
            'name = "project_custom"\n'
            'description = "Project profile."\n'
            'model = "project-model"\n'
            'model_reasoning_effort = "high"\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "add", str(agent.relative_to(repository))], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "add project profile"], cwd=repository, check=True)

        # Both declared fields keep their parsed values, so only an
        # unconditional unseeded-profile rejection can stop this diff.
        agent.write_text(
            'name = "project_custom"\n'
            'description = "Project profile."\n'
            'model  =  "project-model"\n'
            'model_reasoning_effort = "high"\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            VALIDATOR.UpdateValidationError, "not a seeded profile"
        ):
            VALIDATOR.validate(repository)

    def test_rejects_agent_instruction_changes_but_allows_exact_worker_transition(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        original = agent.read_text(encoding="utf-8")
        agent.write_text(original.replace("Preserve this instruction.", "Changed instruction."), encoding="utf-8")
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "agent profile"):
            VALIDATOR.validate(repository)
        agent.write_text(original, encoding="utf-8")

        worker = repository / ".codex/agents/sequential_plan_worker.toml"
        worker.write_text(
            (ROOT / "template/.codex/agents/sequential_plan_worker.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        VALIDATOR.validate(repository)

    def test_model_like_instruction_lines_remain_project_owned(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        original = agent.read_text(encoding="utf-8").replace(
            'developer_instructions = """Preserve this instruction."""',
            'developer_instructions = """\nmodel = \\"instruction text\\"\n"""',
        )
        agent.write_text(original, encoding="utf-8")
        subprocess.run(["git", "add", str(agent.relative_to(repository))], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "add model-like instruction"], cwd=repository, check=True)
        agent.write_text(
            original.replace('model = \\"instruction text\\"', 'model = \\"changed text\\"'),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "agent profile"):
            VALIDATOR.validate(repository)


if __name__ == "__main__":
    unittest.main()
