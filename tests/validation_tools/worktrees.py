"""Disposable-repository tests for parent-owned worktrees."""

from __future__ import annotations

import importlib.util
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

from .support import ROOT


SCRIPT = ROOT / "scripts/manage-plan-worktrees.py"


def load_worktree_module():
    spec = importlib.util.spec_from_file_location("manage_plan_worktrees", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load managed-worktree module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKTREE_MODULE = load_worktree_module()
GUARD_MODULE = WORKTREE_MODULE.guard
SOURCE_REF = "refs/heads/dev"


def plan_selector(plan_path: str) -> dict:
    """Name one plan task the way the ownership records key it."""

    return {"kind": GUARD_MODULE.PLAN_TASK, "identity": {"path": plan_path}}


def git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class ManagedPlanWorktreesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repository = self.base / "repository"
        self.allowed_root = self.base / "managed"
        self.home = self.base / "home"
        self.repository.mkdir()
        self.allowed_root.mkdir(mode=0o700)
        self.allowed_root.chmod(0o700)
        self.home.mkdir(mode=0o700)
        git(self.repository, "init", "-q", "-b", "dev")
        git(self.repository, "config", "user.name", "Worktree Test")
        git(self.repository, "config", "user.email", "worktree@example.invalid")
        git(self.repository, "remote", "add", "origin", "git@github.com:example/project.git")
        plan = self.repository / "docs/plan/active/278-example.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "status: in_progress\nprimary_invariant: example\nwrite_scope:\n  - file.txt\n",
            encoding="utf-8",
        )
        (self.repository / "file.txt").write_text("baseline\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-qm", "baseline")
        self.plan = "docs/plan/active/278-example.md"
        self.target = self.allowed_root / "plan-278"
        self.metadata_paths = WORKTREE_MODULE.metadata_paths(
            WORKTREE_MODULE.repository_identity(self.repository),
            plan_selector(self.plan),
        )

    def tearDown(self) -> None:
        for key in ("record", "journal", "lock"):
            self.metadata_paths[key].unlink(missing_ok=True)
        try:
            self.metadata_paths["directory"].rmdir()
        except OSError:
            pass
        self.temp.cleanup()

    def run_command(
        self,
        *arguments: str,
        cwd: Path | None = None,
        home: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=cwd or self.repository,
            env={**os.environ, "HOME": str(home or self.home)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def create(self, *, owner: str = "owner-a") -> subprocess.CompletedProcess[str]:
        return self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--worktree",
            str(self.target),
            "--branch",
            "plan/278",
            "--owner-id",
            owner,
        )

    def record_path(self, result: subprocess.CompletedProcess[str]) -> Path:
        return Path(json.loads(result.stdout)["record"])

    def test_create_preserves_dirty_primary_and_supports_linked_invocation(self) -> None:
        (self.repository / "file.txt").write_text("dirty tracked\n", encoding="utf-8")
        (self.repository / "untracked.txt").write_text("dirty untracked\n", encoding="utf-8")
        before = git(
            self.repository, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        ).stdout
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(
            git(self.repository, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout,
            before,
        )
        record_path = self.record_path(created)
        self.assertEqual(record_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(git(self.target, "branch", "--show-current").stdout.strip(), "plan/278")
        inspected = self.run_command(
            "inspect", self.plan, "--allowed-root", str(self.allowed_root), cwd=self.target
        )
        self.assertEqual(inspected.returncode, 0, inspected.stderr)

    def test_create_rejects_collisions_symlinks_and_uncommitted_plan(self) -> None:
        git(self.repository, "branch", "plan/278")
        self.assertNotEqual(self.create().returncode, 0)
        self.assertFalse(self.metadata_paths["journal"].exists())
        git(self.repository, "branch", "-D", "plan/278")
        self.target.mkdir()
        self.assertNotEqual(self.create().returncode, 0)
        self.target.rmdir()
        symlink_root = self.base / "managed-link"
        symlink_root.symlink_to(self.allowed_root, target_is_directory=True)
        result = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(symlink_root),
            "--worktree",
            str(symlink_root / "plan-278"),
            "--branch",
            "plan/278",
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        (self.repository / self.plan).write_text("changed\n", encoding="utf-8")
        self.assertNotEqual(self.create().returncode, 0)

    def test_create_rejects_an_allowed_root_that_contains_the_repository(self) -> None:
        result = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(self.base),
            "--worktree",
            str(self.base / "plan-278"),
            "--branch",
            "plan/278",
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden broad or repository path", result.stderr)

    def test_resume_preserves_dirty_work_and_rejects_duplicate_owner(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        (self.target / "file.txt").write_text("retained\n", encoding="utf-8")
        (self.target / "new.txt").write_text("retained untracked\n", encoding="utf-8")
        before = git(
            self.target, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        ).stdout
        other = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-b",
        )
        self.assertNotEqual(other.returncode, 0)
        resumed = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(
            git(self.target, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout,
            before,
        )

    def test_create_rejects_a_second_owner_across_allowed_roots(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        other_root = self.base / "managed-other"
        other_root.mkdir(mode=0o700)
        other_root.chmod(0o700)
        duplicate = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(other_root),
            "--worktree",
            str(other_root / "plan-278"),
            "--branch",
            "plan/278-other",
            "--owner-id",
            "owner-b",
        )
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("ownership record already exists", duplicate.stderr)

    def test_origin_change_does_not_create_another_ownership_namespace(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        git(self.repository, "remote", "set-url", "origin", "https://github.com/example/project.git")
        other_root = self.base / "managed-origin-change"
        other_root.mkdir(mode=0o700)
        other_root.chmod(0o700)
        duplicate = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(other_root),
            "--worktree",
            str(other_root / "plan-278"),
            "--branch",
            "plan/278-origin-change",
            "--owner-id",
            "owner-b",
        )
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("ownership record already exists", duplicate.stderr)

    def test_home_change_does_not_change_the_ownership_namespace(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        other_home = self.base / "other-home"
        other_home.mkdir(mode=0o700)
        resumed = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
            home=other_home,
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(
            self.record_path(created),
            Path(json.loads(resumed.stdout)["record"]),
        )
        account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
        rejected = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(account_home),
            "--worktree",
            str(account_home / "project-agent-workflow-forbidden-test"),
            "--branch",
            "plan/forbidden-home",
            "--owner-id",
            "owner-a",
            home=other_home,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("forbidden broad or repository path", rejected.stderr)

    def test_resume_rejects_replaced_record_branch_and_worktree(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        record_path = self.record_path(created)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["worktree_path"] = str(self.allowed_root / "other")
        record_path.write_text(json.dumps(record), encoding="utf-8")
        os.chmod(record_path, 0o600)
        replaced = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(replaced.returncode, 0)

        record_path.unlink()
        metadata = self.allowed_root / ".project-agent-workflow-parent-worktrees"
        for path in metadata.glob("*.journal.json"):
            path.unlink()
        git(self.repository, "worktree", "remove", str(self.target))
        git(self.repository, "branch", "-D", "plan/278")
        recreated = self.create()
        self.assertEqual(recreated.returncode, 0, recreated.stderr)
        git(self.target, "checkout", "--detach", "-q")
        switched = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(switched.returncode, 0)

    def test_interrupted_create_journal_is_reported_without_deletion(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        record_path = self.record_path(created)
        journal_path = record_path.with_name(record_path.name.replace(".json", ".journal.json"))
        shutil.copyfile(record_path, journal_path)
        os.chmod(journal_path, 0o600)
        record_path.unlink()
        marker = self.target / "retained.txt"
        marker.write_text("keep\n", encoding="utf-8")
        result = self.run_command(
            "inspect", self.plan, "--allowed-root", str(self.allowed_root)
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interrupted create journal", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")

    def test_expired_lease_allows_new_owner_and_advances_accepted_tip(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        (self.target / "file.txt").write_text("committed\n", encoding="utf-8")
        git(self.target, "add", "file.txt")
        git(self.target, "commit", "-qm", "managed change")
        record_path = self.record_path(created)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["owner"]["lease_expires_at"] = int(time.time()) - 1
        unsigned = dict(record)
        unsigned.pop("content_digest")
        record["content_digest"] = "sha256:" + __import__("hashlib").sha256(
            json.dumps(unsigned, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        record_path.write_text(json.dumps(record), encoding="utf-8")
        os.chmod(record_path, 0o600)
        result = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-b",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(updated["owner"]["id"], "owner-b")
        self.assertEqual(updated["accepted_tip"], git(self.target, "rev-parse", "HEAD").stdout.strip())

    def test_resume_recovers_its_exact_interrupted_journal(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        record_path = self.record_path(created)
        journal_path = record_path.with_name(record_path.name.replace(".json", ".journal.json"))
        pending = json.loads(record_path.read_text(encoding="utf-8"))
        pending["owner"]["lease_expires_at"] += 60
        unsigned = dict(pending)
        unsigned.pop("content_digest")
        pending["content_digest"] = "sha256:" + __import__("hashlib").sha256(
            json.dumps(unsigned, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        journal_path.write_text(json.dumps(pending), encoding="utf-8")
        os.chmod(journal_path, 0o600)
        inspected = self.run_command(
            "inspect", self.plan, "--allowed-root", str(self.allowed_root)
        )
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertTrue(json.loads(inspected.stdout)["pending_resume"])
        resumed = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertFalse(journal_path.exists())

    def test_same_owner_can_advance_past_a_stale_resume_journal(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        record_path = self.record_path(created)
        pending = json.loads(record_path.read_text(encoding="utf-8"))
        pending["owner"]["lease_expires_at"] += 60
        unsigned = dict(pending)
        unsigned.pop("content_digest")
        pending["content_digest"] = "sha256:" + __import__("hashlib").sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        journal_path = record_path.with_name(
            record_path.name.replace(".json", ".journal.json")
        )
        journal_path.write_text(json.dumps(pending), encoding="utf-8")
        os.chmod(journal_path, 0o600)
        (self.target / "file.txt").write_text("advanced\n", encoding="utf-8")
        git(self.target, "add", "file.txt")
        git(self.target, "commit", "-qm", "advance after interrupted resume")
        resumed = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertFalse(journal_path.exists())
        updated = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(
            updated["accepted_tip"],
            git(self.target, "rev-parse", "HEAD").stdout.strip(),
        )

    def test_expired_owner_can_replace_a_stale_resume_journal(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        record_path = self.record_path(created)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["owner"]["lease_expires_at"] = int(time.time()) - 1
        unsigned = dict(record)
        unsigned.pop("content_digest")
        record["content_digest"] = "sha256:" + __import__("hashlib").sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        record_path.write_text(json.dumps(record), encoding="utf-8")
        os.chmod(record_path, 0o600)
        pending = dict(record)
        pending["owner"] = {
            "id": "owner-a",
            "lease_expires_at": int(time.time()) + 3600,
        }
        unsigned = dict(pending)
        unsigned.pop("content_digest")
        pending["content_digest"] = "sha256:" + __import__("hashlib").sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        journal_path = record_path.with_name(
            record_path.name.replace(".json", ".journal.json")
        )
        journal_path.write_text(json.dumps(pending), encoding="utf-8")
        os.chmod(journal_path, 0o600)
        inspected = self.run_command(
            "inspect", self.plan, "--allowed-root", str(self.allowed_root)
        )
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertTrue(json.loads(inspected.stdout)["pending_resume"])
        resumed = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-b",
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertFalse(journal_path.exists())

    def test_create_rejects_checkout_filters(self) -> None:
        (self.repository / ".gitattributes").write_text("file.txt filter=probe\n", encoding="utf-8")
        git(self.repository, "add", ".gitattributes")
        git(self.repository, "commit", "-qm", "add checkout filter")
        (self.repository / ".gitattributes").write_text("", encoding="utf-8")
        marker = self.base / "filter-ran"
        git(
            self.repository,
            "config",
            "filter.probe.smudge",
            f"tee {marker}",
        )
        result = self.create()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejects checkout filters", result.stderr)
        self.assertFalse(marker.exists())

    def test_create_does_not_run_external_diff_drivers(self) -> None:
        (self.repository / ".gitattributes").write_text("file.txt diff=probe\n", encoding="utf-8")
        git(self.repository, "add", ".gitattributes")
        git(self.repository, "commit", "-qm", "add diff driver")
        marker = self.base / "diff-ran"
        git(self.repository, "config", "diff.probe.command", f"touch {marker}")
        (self.repository / "file.txt").write_text("dirty\n", encoding="utf-8")
        result = self.create()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())

    def test_raw_snapshot_ignores_caller_global_excludes(self) -> None:
        config = self.home / ".config/git"
        config.mkdir(parents=True)
        (config / "ignore").write_text("untracked.txt\n", encoding="utf-8")
        untracked = self.repository / "untracked.txt"
        untracked.write_text("first\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            before = WORKTREE_MODULE.raw_worktree_digest(self.repository)
            untracked.write_text("second\n", encoding="utf-8")
            after = WORKTREE_MODULE.raw_worktree_digest(self.repository)
        self.assertNotEqual(before, after)

    def test_create_does_not_run_dirty_clean_filters(self) -> None:
        marker = self.base / "clean-filter-ran"
        git(self.repository, "config", "filter.probe.clean", f"tee {marker}")
        (self.repository / ".gitattributes").write_text("file.txt filter=probe\n", encoding="utf-8")
        (self.repository / "file.txt").write_text("dirty\n", encoding="utf-8")
        result = self.create()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())

    def test_create_rejects_a_registered_worktree_as_allowed_root(self) -> None:
        linked = self.base / "linked"
        git(self.repository, "worktree", "add", "-q", "-b", "linked-root", str(linked), "HEAD")
        linked.chmod(0o700)
        result = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(linked),
            "--worktree",
            str(linked / "nested"),
            "--branch",
            "plan/nested",
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("registered worktree", result.stderr)

    def test_create_rejects_a_target_nested_under_a_registered_worktree(self) -> None:
        linked = self.allowed_root / "linked"
        git(self.repository, "worktree", "add", "-q", "-b", "linked-root", str(linked), "HEAD")
        linked.chmod(0o700)
        result = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--worktree",
            str(linked / "nested"),
            "--branch",
            "plan/nested",
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("registered worktree", result.stderr)

    def test_create_rejects_a_writable_nested_target_parent(self) -> None:
        nested = self.allowed_root / "shared"
        nested.mkdir(mode=0o777)
        nested.chmod(0o777)
        result = self.run_command(
            "create",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--worktree",
            str(nested / "plan-278"),
            "--branch",
            "plan/278",
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("group- or world-writable", result.stderr)

    def test_create_never_populates_a_replacement_target_parent(self) -> None:
        parent = self.allowed_root / "stable-parent"
        parent.mkdir(mode=0o700)
        target = parent / "plan-278"
        moved_parent = self.allowed_root / "moved-parent"
        original_git = WORKTREE_MODULE.git
        exchanged = False

        def racing_git(
            repository: Path,
            *arguments: str,
            check: bool = True,
            pass_fds: tuple[int, ...] = (),
        ) -> subprocess.CompletedProcess[bytes]:
            nonlocal exchanged
            if arguments[:2] == ("worktree", "add") and not exchanged:
                parent.rename(moved_parent)
                parent.mkdir(mode=0o700)
                exchanged = True
            return original_git(
                repository,
                *arguments,
                check=check,
                pass_fds=pass_fds,
            )

        args = SimpleNamespace(
            plan=self.plan,
            direct_task=None,
            purpose=None,
            source_ref=None,
            allowed_root=str(self.allowed_root),
            worktree=str(target),
            branch="plan/278",
            owner_id="owner-a",
            lease_seconds=3600,
        )
        previous = Path.cwd()
        try:
            os.chdir(self.repository)
            with (
                mock.patch.object(
                    WORKTREE_MODULE,
                    "repository_root",
                    return_value=self.repository.resolve(),
                ),
                mock.patch.object(WORKTREE_MODULE, "git", side_effect=racing_git),
            ):
                with self.assertRaisesRegex(
                    WORKTREE_MODULE.WorktreeError,
                    "parent or target changed",
                ):
                    WORKTREE_MODULE.create(args)
        finally:
            os.chdir(previous)
        self.assertFalse(target.exists())
        self.assertTrue((moved_parent / "plan-278").exists())

    def test_create_recovers_after_post_add_verification_failure(self) -> None:
        original_snapshot = WORKTREE_MODULE.snapshot_source
        snapshots = 0

        def changed_snapshot(repository: Path) -> tuple[bytes, bytes]:
            nonlocal snapshots
            snapshots += 1
            observed = original_snapshot(repository)
            if snapshots == 2:
                return observed[0], observed[1] + b"changed"
            return observed

        args = SimpleNamespace(
            plan=self.plan,
            direct_task=None,
            purpose=None,
            source_ref=None,
            allowed_root=str(self.allowed_root),
            worktree=str(self.target),
            branch="plan/278",
            owner_id="owner-a",
            lease_seconds=3600,
        )
        previous = Path.cwd()
        try:
            os.chdir(self.repository)
            with (
                mock.patch.object(
                    WORKTREE_MODULE,
                    "repository_root",
                    return_value=self.repository.resolve(),
                ),
                mock.patch.object(
                    WORKTREE_MODULE,
                    "snapshot_source",
                    side_effect=changed_snapshot,
                ),
            ):
                with self.assertRaisesRegex(
                    WORKTREE_MODULE.WorktreeError,
                    "ordinary checkout state changed",
                ):
                    WORKTREE_MODULE.create(args)
        finally:
            os.chdir(previous)
        recovered = self.create()
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertFalse(
            self.record_path(recovered)
            .with_name(self.record_path(recovered).name.replace(".json", ".journal.json"))
            .exists()
        )

    def test_create_recovers_an_empty_directory_after_journal_write(self) -> None:
        identity = WORKTREE_MODULE.repository_identity(self.repository)
        start = git(self.repository, "rev-parse", "HEAD").stdout.strip()
        plan = WORKTREE_MODULE.plan_identity_at_commit(
            self.repository, self.plan, start
        )
        _, branch_ref = WORKTREE_MODULE.normalize_branch(
            "plan/278", self.repository
        )
        paths = WORKTREE_MODULE.metadata_paths(identity, plan_selector(self.plan))
        WORKTREE_MODULE.ensure_metadata_directory(paths["directory"])
        journal = WORKTREE_MODULE.add_content_digest(
            {
                "schema_version": WORKTREE_MODULE.SCHEMA_VERSION,
                "repository_identity": identity,
                "task": WORKTREE_MODULE.plan_task(plan),
                "start_commit": start,
                "accepted_tip": start,
                "branch_ref": branch_ref,
                "source_ref": SOURCE_REF,
                "allowed_root": str(self.allowed_root),
                "worktree_path": str(self.target),
                "worktree_identity": {
                    "git_dir": None,
                    "git_dir_device": None,
                    "git_dir_inode": None,
                    "worktree_device": None,
                    "worktree_inode": None,
                    "worktree_owner": None,
                    "worktree_mode": None,
                },
                "owner": {
                    "id": "owner-a",
                    "lease_expires_at": int(time.time()) + 1,
                },
            }
        )
        WORKTREE_MODULE.atomic_write(paths["journal"], journal)
        self.target.mkdir(mode=0o500)
        recovered = self.create()
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        self.assertFalse(paths["journal"].exists())

    def test_empty_directory_recovery_survives_post_chmod_interruption(self) -> None:
        identity = WORKTREE_MODULE.repository_identity(self.repository)
        start = git(self.repository, "rev-parse", "HEAD").stdout.strip()
        plan = WORKTREE_MODULE.plan_identity_at_commit(
            self.repository, self.plan, start
        )
        paths = WORKTREE_MODULE.metadata_paths(identity, plan_selector(self.plan))
        WORKTREE_MODULE.ensure_metadata_directory(paths["directory"])
        journal = WORKTREE_MODULE.add_content_digest(
            {
                "schema_version": WORKTREE_MODULE.SCHEMA_VERSION,
                "repository_identity": identity,
                "task": WORKTREE_MODULE.plan_task(plan),
                "start_commit": start,
                "accepted_tip": start,
                "branch_ref": "refs/heads/plan/278",
                "source_ref": SOURCE_REF,
                "allowed_root": str(self.allowed_root),
                "worktree_path": str(self.target),
                "worktree_identity": {
                    "git_dir": None,
                    "git_dir_device": None,
                    "git_dir_inode": None,
                    "worktree_device": None,
                    "worktree_inode": None,
                    "worktree_owner": None,
                    "worktree_mode": None,
                },
                "owner": {
                    "id": "owner-a",
                    "lease_expires_at": int(time.time()) + 3600,
                },
            }
        )
        WORKTREE_MODULE.atomic_write(paths["journal"], journal)
        self.target.mkdir(mode=0o500)
        original_git = WORKTREE_MODULE.git

        def interrupted_git(
            repository: Path,
            *arguments: str,
            check: bool = True,
            pass_fds: tuple[int, ...] = (),
        ) -> subprocess.CompletedProcess[bytes]:
            if arguments[:2] == ("worktree", "add"):
                raise WORKTREE_MODULE.WorktreeError("injected interruption")
            return original_git(
                repository,
                *arguments,
                check=check,
                pass_fds=pass_fds,
            )

        args = SimpleNamespace(
            plan=self.plan,
            direct_task=None,
            purpose=None,
            source_ref=None,
            allowed_root=str(self.allowed_root),
            worktree=str(self.target),
            branch="plan/278",
            owner_id="owner-a",
            lease_seconds=3600,
        )
        previous = Path.cwd()
        try:
            os.chdir(self.repository)
            with (
                mock.patch.object(
                    WORKTREE_MODULE,
                    "repository_root",
                    return_value=self.repository.resolve(),
                ),
                mock.patch.object(
                    WORKTREE_MODULE,
                    "git",
                    side_effect=interrupted_git,
                ),
            ):
                with self.assertRaisesRegex(
                    WORKTREE_MODULE.WorktreeError,
                    "injected interruption",
                ):
                    WORKTREE_MODULE.create(args)
        finally:
            os.chdir(previous)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        recovered = self.create()
        self.assertEqual(recovered.returncode, 0, recovered.stderr)

    def test_expired_effect_free_create_journal_can_be_replaced(self) -> None:
        identity = WORKTREE_MODULE.repository_identity(self.repository)
        start = git(self.repository, "rev-parse", "HEAD").stdout.strip()
        plan = WORKTREE_MODULE.plan_identity_at_commit(
            self.repository, self.plan, start
        )
        paths = WORKTREE_MODULE.metadata_paths(identity, plan_selector(self.plan))
        WORKTREE_MODULE.ensure_metadata_directory(paths["directory"])
        stale_target = self.allowed_root / "stale-target"
        journal = WORKTREE_MODULE.add_content_digest(
            {
                "schema_version": WORKTREE_MODULE.SCHEMA_VERSION,
                "repository_identity": identity,
                "task": WORKTREE_MODULE.plan_task(plan),
                "start_commit": start,
                "accepted_tip": start,
                "branch_ref": "refs/heads/plan/stale",
                "source_ref": SOURCE_REF,
                "allowed_root": str(self.allowed_root),
                "worktree_path": str(stale_target),
                "worktree_identity": {
                    "git_dir": None,
                    "git_dir_device": None,
                    "git_dir_inode": None,
                    "worktree_device": None,
                    "worktree_inode": None,
                    "worktree_owner": None,
                    "worktree_mode": None,
                },
                "owner": {
                    "id": "old-owner",
                    "lease_expires_at": int(time.time()) - 1,
                },
            }
        )
        WORKTREE_MODULE.atomic_write(paths["journal"], journal)
        result = self.create(owner="owner-a")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(paths["journal"].exists())

    def test_prunable_unrelated_worktree_does_not_block_inspect(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        unrelated = self.base / "prunable"
        git(
            self.repository,
            "worktree",
            "add",
            "-q",
            "-b",
            "prunable",
            str(unrelated),
            "HEAD",
        )
        shutil.rmtree(unrelated)
        inspected = self.run_command(
            "inspect",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
        )
        self.assertEqual(inspected.returncode, 0, inspected.stderr)

    def test_resume_allows_retained_plan_edits_in_managed_checkout(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        (self.target / self.plan).write_text("retained plan notes\n", encoding="utf-8")
        resumed = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
            cwd=self.target,
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)

    def test_resume_rejects_recreated_worktree_registration(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        git(self.repository, "worktree", "remove", str(self.target))
        git(self.repository, "worktree", "add", "-q", str(self.target), "plan/278")
        result = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("registration was replaced", result.stderr)

    def test_resume_rejects_changed_target_directory_metadata(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        self.target.chmod(0o755)
        result = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("registration was replaced", result.stderr)

    def test_resume_ignores_git_grafts_for_history(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        start = git(self.target, "rev-parse", "HEAD").stdout.strip()
        (self.target / "file.txt").write_text("managed change\n", encoding="utf-8")
        git(self.target, "add", "file.txt")
        git(self.target, "commit", "-qm", "managed change")
        tip = git(self.target, "rev-parse", "HEAD").stdout.strip()
        unrelated = self.base / "unrelated"
        git(self.repository, "worktree", "add", "--detach", str(unrelated), start)
        git(unrelated, "checkout", "--orphan", "unrelated")
        for path in unrelated.iterdir():
            if path.name != ".git" and path.is_file():
                path.unlink()
        (unrelated / "other.txt").write_text("unrelated\n", encoding="utf-8")
        git(unrelated, "add", ".")
        git(unrelated, "commit", "-qm", "unrelated root")
        unrelated_tip = git(unrelated, "rev-parse", "HEAD").stdout.strip()
        git(self.repository, "worktree", "remove", str(unrelated))
        common = Path(
            git(
                self.repository,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ).stdout.strip()
        )
        (common / "info/grafts").write_text(
            f"{tip} {unrelated_tip}\n",
            encoding="ascii",
        )
        result = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_resume_ignores_git_replacement_refs_for_history(self) -> None:
        created = self.create()
        self.assertEqual(created.returncode, 0, created.stderr)
        orphan = self.base / "orphan"
        git(self.repository, "worktree", "add", "--detach", str(orphan), "HEAD")
        git(orphan, "checkout", "--orphan", "unrelated")
        for path in orphan.iterdir():
            if path.name != ".git" and path.is_file():
                path.unlink()
        (orphan / "other.txt").write_text("unrelated\n", encoding="utf-8")
        git(orphan, "add", ".")
        git(orphan, "commit", "-qm", "unrelated root")
        unrelated = git(orphan, "rev-parse", "HEAD").stdout.strip()
        git(self.repository, "worktree", "remove", str(orphan))
        start = git(self.target, "rev-parse", "HEAD").stdout.strip()
        replacement_tree = git(self.repository, "show", "-s", "--format=%T", unrelated).stdout.strip()
        replacement_commit = subprocess.run(
            ["git", "-C", str(self.repository), "commit-tree", replacement_tree, "-p", start],
            input="synthetic parent\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout.strip()
        git(self.repository, "replace", unrelated, replacement_commit)
        git(self.repository, "update-ref", "refs/heads/plan/278", unrelated)
        git(self.target, "reset", "--hard", "-q", unrelated)
        result = self.run_command(
            "resume",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bound commits", result.stderr)


class TaskWorktreeGuardTest(unittest.TestCase):
    """Disposable-repository tests for the shared task-worktree assertion."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repository = self.base / "repository"
        self.allowed_root = self.base / "managed"
        self.home = self.base / "home"
        self.repository.mkdir()
        self.allowed_root.mkdir(mode=0o700)
        self.allowed_root.chmod(0o700)
        self.home.mkdir(mode=0o700)
        git(self.repository, "init", "-q", "-b", "dev")
        git(self.repository, "config", "user.name", "Guard Test")
        git(self.repository, "config", "user.email", "guard@example.invalid")
        git(self.repository, "remote", "add", "origin", "git@github.com:example/guard.git")
        self.plan = "docs/plan/active/301-guarded.md"
        plan = self.repository / self.plan
        plan.parent.mkdir(parents=True)
        plan.write_text("status: in_progress\n", encoding="utf-8")
        (self.repository / "file.txt").write_text("baseline\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-qm", "baseline")
        self.identity = WORKTREE_MODULE.repository_identity(self.repository)
        self.created: list[dict] = []

    def tearDown(self) -> None:
        for paths in self.created:
            for key in ("record", "journal", "lock"):
                paths[key].unlink(missing_ok=True)
        self.temp.cleanup()

    def track(self, task: dict) -> dict:
        paths = WORKTREE_MODULE.metadata_paths(self.identity, task)
        self.created.append(paths)
        return paths

    def run_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=self.repository,
            env={**os.environ, "HOME": str(self.home)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def prepare_plan(self, owner: str = "owner-a") -> dict:
        self.track(plan_selector(self.plan))
        result = self.run_command(
            "prepare",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            owner,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def prepare_direct(self, task_id: str = "author-plan", owner: str = "owner-a") -> dict:
        self.track({"kind": GUARD_MODULE.DIRECT_TASK, "identity": {"id": task_id}})
        result = self.run_command(
            "prepare",
            "--direct-task",
            task_id,
            "--purpose",
            "author one plan before an identifier exists",
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            owner,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_prepare_places_a_plan_worktree_without_another_prompt(self) -> None:
        created = self.prepare_plan()
        self.assertEqual(created["outcome"], "created")
        self.assertEqual(created["worktree"], str(self.allowed_root / "301-guarded"))
        self.assertEqual(created["branch_ref"], "refs/heads/plan/301-guarded")
        self.assertEqual(created["source_ref"], "refs/heads/dev")

    def test_prepare_is_idempotent_for_the_same_task(self) -> None:
        first = self.prepare_plan()
        second = self.prepare_plan()
        self.assertEqual(second["outcome"], "resumed")
        self.assertEqual(second["worktree"], first["worktree"])
        self.assertEqual(second["branch_ref"], first["branch_ref"])

    def test_guard_binds_the_prepared_worktree(self) -> None:
        created = self.prepare_plan()
        binding = GUARD_MODULE.assert_task_worktree(Path(created["worktree"]))
        self.assertEqual(binding.kind, GUARD_MODULE.PLAN_TASK)
        self.assertEqual(binding.label, self.plan)
        self.assertEqual(binding.source_ref, "refs/heads/dev")

    def test_guard_rejects_the_pre_existing_checkout(self) -> None:
        self.prepare_plan()
        with self.assertRaises(GUARD_MODULE.GuardError) as caught:
            GUARD_MODULE.assert_task_worktree(self.repository)
        self.assertIn("pre-existing checkout", str(caught.exception))
        self.assertIn("prepare", str(caught.exception))

    def test_guard_reports_the_exact_preparation_command(self) -> None:
        self.prepare_plan()
        with self.assertRaises(GUARD_MODULE.GuardError) as caught:
            GUARD_MODULE.assert_task_worktree(self.repository, plan=self.plan)
        self.assertIn("manage-plan-worktrees.py prepare " + self.plan, str(caught.exception))

    def test_guard_rejects_an_expired_owner_lease(self) -> None:
        created = self.prepare_plan()
        expiry = json.loads(
            self.run_command(
                "inspect", self.plan, "--allowed-root", str(self.allowed_root)
            ).stdout
        )["record"]["owner"]["lease_expires_at"]
        with self.assertRaises(GUARD_MODULE.GuardError) as caught:
            GUARD_MODULE.assert_task_worktree(
                Path(created["worktree"]), now=expiry + 1
            )
        self.assertIn("lease expired", str(caught.exception))

    def test_guard_rejects_a_worktree_whose_branch_moved_away(self) -> None:
        created = self.prepare_plan()
        worktree = Path(created["worktree"])
        git(worktree, "checkout", "-q", "--detach")
        with self.assertRaises(GUARD_MODULE.GuardError) as caught:
            GUARD_MODULE.assert_task_worktree(worktree)
        self.assertIn("branch changed or became detached", str(caught.exception))

    def test_direct_task_is_disjoint_from_every_plan_task(self) -> None:
        plan_created = self.prepare_plan()
        direct_created = self.prepare_direct()
        self.assertNotEqual(direct_created["worktree"], plan_created["worktree"])
        self.assertEqual(direct_created["task"], "direct:author-plan")
        self.assertEqual(direct_created["branch_ref"], "refs/heads/task/author-plan")
        binding = GUARD_MODULE.assert_task_worktree(Path(direct_created["worktree"]))
        self.assertEqual(binding.kind, GUARD_MODULE.DIRECT_TASK)

    def test_direct_task_cannot_acquire_plan_implementation_authority(self) -> None:
        self.prepare_plan()
        direct_created = self.prepare_direct()
        with self.assertRaises(GUARD_MODULE.GuardError) as caught:
            GUARD_MODULE.assert_task_worktree(
                Path(direct_created["worktree"]), plan=self.plan
            )
        self.assertIn("bound to direct:author-plan", str(caught.exception))

    def test_plan_worktree_is_not_accepted_as_a_direct_task(self) -> None:
        created = self.prepare_plan()
        with self.assertRaises(GUARD_MODULE.GuardError):
            GUARD_MODULE.assert_task_worktree(
                Path(created["worktree"]), kind=GUARD_MODULE.DIRECT_TASK
            )

    def test_direct_task_id_must_not_imitate_a_numbered_plan(self) -> None:
        for candidate in ("301", "301-guarded"):
            with self.assertRaises(GUARD_MODULE.WorktreeError):
                GUARD_MODULE.normalize_direct_task(candidate)

    def test_prepare_requires_exactly_one_task_selector(self) -> None:
        neither = self.run_command(
            "prepare", "--allowed-root", str(self.allowed_root), "--owner-id", "owner-a"
        )
        self.assertNotEqual(neither.returncode, 0)
        self.assertIn("exactly one", neither.stderr)
        both = self.run_command(
            "prepare",
            self.plan,
            "--direct-task",
            "author-plan",
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertNotEqual(both.returncode, 0)
        self.assertIn("exactly one", both.stderr)

    def test_guard_finds_no_binding_without_a_prepared_worktree(self) -> None:
        self.assertIsNone(GUARD_MODULE.find_binding(self.repository))
        with self.assertRaises(GUARD_MODULE.GuardError):
            GUARD_MODULE.assert_task_worktree(self.repository)

    def test_guard_ignores_a_binding_from_another_clone(self) -> None:
        created = self.prepare_plan()
        other = self.base / "other"
        git(self.base, "clone", "-q", str(self.repository), str(other))
        git(other, "remote", "set-url", "origin", "git@github.com:example/guard.git")
        self.assertIsNone(GUARD_MODULE.find_binding(other))
        self.assertIsNotNone(GUARD_MODULE.find_binding(Path(created["worktree"])))

    def test_guard_resolves_the_account_home_rather_than_caller_home(self) -> None:
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            self.assertEqual(
                GUARD_MODULE.state_directory(),
                GUARD_MODULE.account_home() / GUARD_MODULE.STATE_RELATIVE_DIRECTORY,
            )
            self.assertFalse(
                str(GUARD_MODULE.state_directory()).startswith(str(self.home))
            )

    def test_task_branch_must_differ_from_the_source_ref(self) -> None:
        self.track(plan_selector(self.plan))
        result = self.run_command(
            "prepare",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
            "--branch",
            "dev",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must differ from the source ref", result.stderr)


class TaskPublicationTest(unittest.TestCase):
    """Disposable-repository tests for publication and exact retirement."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repository = self.base / "repository"
        self.allowed_root = self.base / "managed"
        self.home = self.base / "home"
        self.repository.mkdir()
        self.allowed_root.mkdir(mode=0o700)
        self.allowed_root.chmod(0o700)
        self.home.mkdir(mode=0o700)
        git(self.repository, "init", "-q", "-b", "dev")
        git(self.repository, "config", "user.name", "Publish Test")
        git(self.repository, "config", "user.email", "publish@example.invalid")
        git(self.repository, "remote", "add", "origin", "git@github.com:example/publish.git")
        self.plan = "docs/plan/active/311-publish.md"
        plan = self.repository / self.plan
        plan.parent.mkdir(parents=True)
        plan.write_text("status: in_progress\n", encoding="utf-8")
        (self.repository / "file.txt").write_text("baseline\n", encoding="utf-8")
        (self.repository / ".gitignore").write_text(
            ".agent-logs/\n.agent-artifacts/\n", encoding="utf-8"
        )
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-qm", "baseline")
        self.identity = WORKTREE_MODULE.repository_identity(self.repository)
        self.paths = WORKTREE_MODULE.metadata_paths(self.identity, plan_selector(self.plan))

    def tearDown(self) -> None:
        for key in ("record", "journal", "lock"):
            self.paths[key].unlink(missing_ok=True)
        self.temp.cleanup()

    def run_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=self.repository,
            env={**os.environ, "HOME": str(self.home)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def prepare(self) -> Path:
        result = self.run_command(
            "prepare",
            self.plan,
            "--allowed-root",
            str(self.allowed_root),
            "--owner-id",
            "owner-a",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["worktree"])

    def commit_task_work(self, worktree: Path, name: str = "feature.txt") -> str:
        (worktree / name).write_text("task work\n", encoding="utf-8")
        git(worktree, "add", name)
        git(worktree, "commit", "-qm", f"add {name}")
        return git(worktree, "rev-parse", "HEAD").stdout.strip()

    def test_publication_fast_forwards_and_retires_the_exact_task(self) -> None:
        worktree = self.prepare()
        evidence = worktree / ".agent-logs"
        evidence.mkdir()
        (evidence / "run.log").write_text("evidence\n", encoding="utf-8")
        accepted = self.commit_task_work(worktree)
        result = self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["published_commit"], accepted)
        self.assertEqual(
            git(self.repository, "rev-parse", "refs/heads/dev").stdout.strip(), accepted
        )
        self.assertEqual(git(self.repository, "rev-parse", "HEAD").stdout.strip(), accepted)
        self.assertFalse(worktree.exists())
        self.assertNotEqual(
            git(
                self.repository,
                "rev-parse",
                "--verify",
                "refs/heads/plan/311-publish",
                check=False,
            ).returncode,
            0,
        )
        self.assertFalse(self.paths["record"].exists())
        self.assertTrue(
            (self.repository / ".agent-logs/retired-tasks/311-publish/run.log").is_file()
        )

    def test_success_requires_the_worktree_and_branch_to_be_absent(self) -> None:
        worktree = self.prepare()
        self.commit_task_work(worktree)
        self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertIsNone(GUARD_MODULE.find_binding(self.repository))
        listed = git(self.repository, "worktree", "list").stdout
        self.assertNotIn(str(worktree), listed)

    def test_publication_refuses_an_empty_task_branch(self) -> None:
        self.prepare()
        result = self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no commit to publish", result.stderr)

    def test_publication_preserves_a_dirty_source_checkout(self) -> None:
        worktree = self.prepare()
        self.commit_task_work(worktree)
        (self.repository / "uncommitted.txt").write_text("keep me\n", encoding="utf-8")
        result = self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preserved unchanged", result.stderr)
        self.assertTrue((self.repository / "uncommitted.txt").is_file())
        self.assertTrue(worktree.exists())
        self.assertTrue(self.paths["record"].exists())

    def test_publication_refuses_a_dirty_task_worktree(self) -> None:
        worktree = self.prepare()
        self.commit_task_work(worktree)
        (worktree / "scratch.txt").write_text("scratch\n", encoding="utf-8")
        result = self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task worktree is dirty", result.stderr)
        self.assertTrue((worktree / "scratch.txt").is_file())

    def test_publication_refuses_a_drifted_non_fast_forward_source(self) -> None:
        worktree = self.prepare()
        self.commit_task_work(worktree)
        (self.repository / "diverged.txt").write_text("diverged\n", encoding="utf-8")
        git(self.repository, "add", "diverged.txt")
        git(self.repository, "commit", "-qm", "diverge the source")
        result = self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a fast-forward", result.stderr)
        self.assertTrue(worktree.exists())
        self.assertTrue((self.repository / "diverged.txt").is_file())

    def test_publication_resumes_after_an_interrupted_retirement(self) -> None:
        worktree = self.prepare()
        accepted = self.commit_task_work(worktree)
        git(self.repository, "merge", "--ff-only", accepted)
        result = self.run_command("publish", self.plan, "--owner-id", "owner-a")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(worktree.exists())
        self.assertEqual(
            git(self.repository, "rev-parse", "refs/heads/dev").stdout.strip(), accepted
        )

    def test_publication_rejects_an_accepted_commit_that_is_not_the_tip(self) -> None:
        worktree = self.prepare()
        start = git(worktree, "rev-parse", "HEAD").stdout.strip()
        self.commit_task_work(worktree)
        result = self.run_command(
            "publish", self.plan, "--owner-id", "owner-a", "--accepted-commit", start
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact task branch tip", result.stderr)

    def test_retirement_of_unpublished_work_stays_explicit(self) -> None:
        worktree = self.prepare()
        self.commit_task_work(worktree)
        result = self.run_command("retire", self.plan, "--owner-id", "owner-a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("publish it first", result.stderr)
        self.assertTrue(worktree.exists())

    def test_stopped_retirement_keeps_recoverable_commits(self) -> None:
        worktree = self.prepare()
        self.commit_task_work(worktree)
        result = self.run_command("retire", self.plan, "--owner-id", "owner-a", "--stopped")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("recoverable", result.stderr)
        self.assertTrue(worktree.exists())

    def test_stopped_retirement_removes_an_effect_free_worktree(self) -> None:
        worktree = self.prepare()
        result = self.run_command("retire", self.plan, "--owner-id", "owner-a", "--stopped")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(worktree.exists())
        self.assertFalse(self.paths["record"].exists())


class PlanIdentifierReservationTest(unittest.TestCase):
    """Disposable-repository tests for cross-worktree plan-identifier allocation."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repository = self.base / "repository"
        self.repository.mkdir()
        git(self.repository, "init", "-q", "-b", "dev")
        git(self.repository, "config", "user.name", "Reservation Test")
        git(self.repository, "config", "user.email", "reserve@example.invalid")
        git(self.repository, "remote", "add", "origin", "git@github.com:example/reserve.git")
        self.publish_plans(
            "docs/plan/active/001-a.md",
            "docs/plan/backlog/002-b.md",
            "docs/plan/shelved/003-c.md",
            "docs/plan/checked/2026/01/004-d.md",
            "docs/plan/replanned/2026/01/005-e.md",
        )

    def tearDown(self) -> None:
        GUARD_MODULE._HELD_PLAN_LOCKS.clear()
        self.temp.cleanup()

    def publish_plans(self, *relative: str, index_ids: tuple[str, ...] = ("006",)) -> str:
        for item in relative:
            path = self.repository / item
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("status: in_progress\n", encoding="utf-8")
        rows = "".join(f"{value}\tdocs/plan/checked/2026/01/{value}-x.md\n" for value in index_ids)
        (self.repository / "docs/plan/checked.md").write_text(
            f"# Checked Plan Index\n\nid\tpath\n{rows}", encoding="utf-8"
        )
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-qm", "publish plans")
        return git(self.repository, "rev-parse", "HEAD").stdout.strip()

    @staticmethod
    def digest(marker: str) -> str:
        return "sha256:" + (marker * 64)[:64]

    def linked_worktree(self, name: str) -> Path:
        target = self.base / name
        git(self.repository, "worktree", "add", "-q", "-b", f"task/{name}", str(target), "dev")
        return target

    def test_published_scan_reads_every_lifecycle_location(self) -> None:
        commit = GUARD_MODULE.published_source_commit(self.repository)
        self.assertEqual(
            sorted(GUARD_MODULE.plan_ids_in_commit(self.repository, commit)),
            [1, 2, 3, 4, 5, 6],
        )

    def test_reservation_allocates_the_smallest_free_published_identifier(self) -> None:
        reservation = GUARD_MODULE.reserve_plan_id(
            self.repository, input_digest=self.digest("a"), lifecycle="active", slug="next"
        )
        self.assertEqual(reservation["plan_id"], "007")
        self.assertEqual(reservation["relative_path"], "docs/plan/active/007-next.md")

    def test_the_same_checked_input_keeps_its_reserved_identifier(self) -> None:
        first = GUARD_MODULE.reserve_plan_id(self.repository, input_digest=self.digest("a"))
        second = GUARD_MODULE.reserve_plan_id(
            self.repository, input_digest=self.digest("a"), lifecycle="active", slug="named"
        )
        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertEqual(second["relative_path"], "docs/plan/active/007-named.md")

    def test_a_second_linked_worktree_cannot_take_a_reserved_identifier(self) -> None:
        first = GUARD_MODULE.reserve_plan_id(self.repository, input_digest=self.digest("a"))
        linked = self.linked_worktree("second")
        second = GUARD_MODULE.reserve_plan_id(linked, input_digest=self.digest("b"))
        self.assertEqual(first["plan_id"], "007")
        self.assertEqual(second["plan_id"], "008")
        self.assertEqual(
            GUARD_MODULE.reservation_ledger_path(linked),
            GUARD_MODULE.reservation_ledger_path(self.repository),
        )

    def test_an_uncommitted_plan_file_does_not_claim_an_identifier(self) -> None:
        stray = self.repository / "docs/plan/active/007-uncommitted.md"
        stray.write_text("status: in_progress\n", encoding="utf-8")
        reservation = GUARD_MODULE.reserve_plan_id(self.repository, input_digest=self.digest("a"))
        self.assertEqual(reservation["plan_id"], "007")

    def test_publication_consumes_the_reservation(self) -> None:
        reserved = GUARD_MODULE.reserve_plan_id(self.repository, input_digest=self.digest("a"))
        self.assertEqual(GUARD_MODULE.reserved_plan_ids(self.repository), {7})
        self.publish_plans(f"docs/plan/active/{reserved['plan_id']}-published.md")
        self.assertEqual(GUARD_MODULE.reserved_plan_ids(self.repository), set())
        following = GUARD_MODULE.reserve_plan_id(self.repository, input_digest=self.digest("b"))
        self.assertEqual(following["plan_id"], "008")

    def test_an_expired_reservation_without_a_live_worktree_is_released(self) -> None:
        moment = int(time.time())
        GUARD_MODULE.reserve_plan_id(
            self.repository, input_digest=self.digest("a"), now=moment, lease_seconds=60
        )
        ledger = GUARD_MODULE.reservation_ledger_path(self.repository)
        entries = GUARD_MODULE.read_reservations(ledger)
        entries[0]["worktree_path"] = str(self.base / "removed")
        GUARD_MODULE.write_reservations(ledger, entries)
        self.assertEqual(GUARD_MODULE.reserved_plan_ids(self.repository, now=moment + 61), set())

    def test_an_expired_reservation_with_a_live_worktree_is_retained(self) -> None:
        moment = int(time.time())
        GUARD_MODULE.reserve_plan_id(
            self.repository, input_digest=self.digest("a"), now=moment, lease_seconds=60
        )
        self.assertEqual(GUARD_MODULE.reserved_plan_ids(self.repository, now=moment + 61), {7})

    def test_a_malformed_reservation_ledger_is_refused(self) -> None:
        ledger = GUARD_MODULE.reservation_ledger_path(self.repository)
        ledger.write_text('{"schema_version": 1, "reservations": [{"plan_id": "7"}]}', encoding="utf-8")
        with self.assertRaises(GUARD_MODULE.WorktreeError):
            GUARD_MODULE.read_reservations(ledger)

    def test_a_foreign_ledger_schema_is_refused(self) -> None:
        ledger = GUARD_MODULE.reservation_ledger_path(self.repository)
        ledger.write_text('{"schema_version": 99, "reservations": []}', encoding="utf-8")
        with self.assertRaises(GUARD_MODULE.WorktreeError):
            GUARD_MODULE.read_reservations(ledger)

    def test_a_malformed_input_digest_is_refused(self) -> None:
        with self.assertRaises(GUARD_MODULE.WorktreeError):
            GUARD_MODULE.reserve_plan_id(self.repository, input_digest="not-a-digest")

    def test_the_shared_lock_binds_to_the_common_git_directory(self) -> None:
        linked = self.linked_worktree("second")
        shared = GUARD_MODULE.shared_lifecycle_directory(self.repository)
        common = GUARD_MODULE.common_git_directory(self.repository)
        self.assertEqual(shared, GUARD_MODULE.shared_lifecycle_directory(linked))
        self.assertEqual(common, GUARD_MODULE.common_git_directory(linked))
        self.assertTrue(GUARD_MODULE.path_is_strict_descendant(shared, common))
        self.assertFalse(GUARD_MODULE.path_is_strict_descendant(shared, linked))
        tracked = git(self.repository, "ls-files", "--", str(shared), check=False)
        self.assertEqual(tracked.stdout.strip(), "")

    def test_the_shared_lock_nests_within_one_process(self) -> None:
        with GUARD_MODULE.plan_lifecycle_lock(self.repository):
            with GUARD_MODULE.plan_lifecycle_lock(self.repository):
                reservation = GUARD_MODULE.reserve_plan_id(
                    self.repository, input_digest=self.digest("a")
                )
        self.assertEqual(reservation["plan_id"], "007")
        self.assertEqual(GUARD_MODULE._HELD_PLAN_LOCKS, {})

    def test_an_unbound_checkout_allocates_against_its_own_committed_state(self) -> None:
        linked = self.linked_worktree("second")
        self.publish_plans("docs/plan/active/007-later.md")
        self.assertEqual(
            sorted(GUARD_MODULE.plan_ids_in_commit(linked, GUARD_MODULE.published_source_commit(linked))),
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(
            sorted(
                GUARD_MODULE.plan_ids_in_commit(
                    self.repository, GUARD_MODULE.published_source_commit(self.repository)
                )
            ),
            [1, 2, 3, 4, 5, 6, 7],
        )
