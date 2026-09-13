#!/usr/bin/env python3
"""Prove what the stale-record retirement command will and will not remove.

Every case runs against its own temporary record directory. Nothing here
reads or writes the account's real directory, so a failing test cannot cost
another run its ownership records.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / "scripts/retire-stale-worktree-records.py"
GUARD = ROOT / "scripts/project_workflow/worktree_guard.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = load("worktree_guard", GUARD)
retire = load("retire_stale_worktree_records", COMMAND)


class RecordFixture:
    """One record directory holding records this test wrote itself."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.directory = base / "records"
        self.directory.mkdir(mode=0o700, parents=True)
        self.directory.chmod(0o700)
        self.gone = base / "gone"

    def key_for(self, repository: Path, task_id: str, *, device: int, inode: int) -> str:
        return hashlib.sha256(
            guard.canonical_json(
                {
                    "common_git_dir": str(repository),
                    "common_git_dir_device": device,
                    "common_git_dir_inode": inode,
                    "direct_task": task_id,
                }
            )
        ).hexdigest()

    def write(
        self,
        task_id: str = "gone-task",
        *,
        repository: Path | None = None,
        worktree: Path | None = None,
        repository_device: int | None = None,
        worktree_device: int | None = None,
        lease_offset: int = -7_200,
        key: str | None = None,
        siblings: bool = True,
    ) -> str:
        """Write one record describing a task in a repository that is gone."""

        repository = repository or (self.gone / f"{task_id}/source/.git")
        worktree = worktree or (self.gone / f"{task_id}/worktree")
        device = (
            repository_device
            if repository_device is not None
            else self.directory.stat().st_dev
        )
        worktree_dev = (
            worktree_device if worktree_device is not None else self.directory.stat().st_dev
        )
        repository_inode = 4242
        worktree_inode = 4343
        if repository.exists():
            metadata = repository.stat()
            device, repository_inode = metadata.st_dev, metadata.st_ino
        if worktree.exists():
            metadata = worktree.stat()
            worktree_dev, worktree_inode = metadata.st_dev, metadata.st_ino
        record = {
            "accepted_tip": "f" * 40,
            "allowed_root": str(self.gone / task_id),
            "branch_ref": f"refs/heads/task/{task_id}",
            "owner": {
                "id": "test-owner",
                "lease_expires_at": int(time.time()) + lease_offset,
            },
            "repository_identity": {
                "common_git_dir": str(repository),
                "common_git_dir_device": device,
                "common_git_dir_inode": repository_inode,
                "origin_identity": "sha256:" + "a" * 64,
            },
            "schema_version": 2,
            "source_ref": "refs/heads/main",
            "start_commit": "f" * 40,
            "task": {"identity": {"id": task_id, "purpose": "exercise retirement"}, "kind": "direct"},
            "worktree_identity": {
                "git_dir": str(repository / "worktrees/1"),
                "git_dir_device": worktree_dev,
                "git_dir_inode": 4444,
                "worktree_device": worktree_dev,
                "worktree_inode": worktree_inode,
                "worktree_mode": 448,
                "worktree_owner": os.getuid(),
            },
            "worktree_path": str(worktree),
        }
        if key is None:
            key = self.key_for(repository, task_id, device=device, inode=repository_inode)
        self.put(key, record)
        if siblings:
            for suffix in (".journal.json", ".publish.journal.json", ".lock"):
                sibling = self.directory / f"{key}{suffix}"
                sibling.write_text("{}\n", encoding="utf-8")
                sibling.chmod(0o600)
        return key

    def put(self, key: str, record: dict) -> Path:
        """Write a record the guard will accept, digest included."""

        signed = guard.add_content_digest(record)
        path = self.directory / f"{key}.json"
        path.write_text(json.dumps(signed, sort_keys=True) + "\n", encoding="utf-8")
        path.chmod(0o600)
        return path

    def read(self, key: str) -> dict:
        return json.loads((self.directory / f"{key}.json").read_text(encoding="utf-8"))

    def present(self, key: str) -> list[str]:
        return sorted(
            path.name for path in self.directory.iterdir() if path.name.startswith(key)
        )

    def manifest_path(self) -> Path:
        return retire.validate_manifest_output(
            f".agent-artifacts/git-retirement/test-{os.getpid()}-{id(self)}.json", ROOT
        )

    def scan(self, *, now: int | None = None) -> dict:
        return retire.scan_directory(
            retire.validate_state_directory(str(self.directory)),
            now=int(time.time()) if now is None else now,
        )

    def apply(self, manifest: dict, *, now: int | None = None) -> dict:
        return retire.apply_manifest(
            manifest,
            retire.validate_state_directory(str(self.directory)),
            now=int(time.time()) if now is None else now,
        )

    def candidate(self, manifest: dict, key: str) -> dict:
        for item in manifest["candidates"]:
            if item["key"] == key:
                return item
        raise AssertionError(f"scan did not report {key}")


class RecordRetirementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = RecordFixture(Path(self.tmp.name))

    def test_a_record_whose_repository_is_gone_is_retirable(self) -> None:
        key = self.fixture.write()
        manifest = self.fixture.scan()
        self.assertTrue(self.fixture.candidate(manifest, key)["eligible"])

    def test_applying_moves_every_record_file_the_key_owns_aside(self) -> None:
        key = self.fixture.write()
        report = self.fixture.apply(self.fixture.scan())
        self.assertEqual(report["retired"], [key])
        self.assertEqual(self.fixture.present(key), [f"{key}.lock"])
        retired = self.fixture.directory / retire.RETIRED_DIRECTORY_NAME
        self.assertEqual(
            sorted(path.name for path in retired.iterdir()),
            sorted(f"{key}{suffix}" for suffix in retire.KEY_SUFFIXES),
        )

    def test_a_retired_record_can_be_put_back_byte_for_byte(self) -> None:
        """A wrong verdict must cost an operator a move, not the ownership bytes."""

        key = self.fixture.write()
        before = (self.fixture.directory / f"{key}.json").read_bytes()
        self.fixture.apply(self.fixture.scan())
        retired = self.fixture.directory / retire.RETIRED_DIRECTORY_NAME / f"{key}.json"
        restored = self.fixture.directory / f"{key}.json"
        retired.rename(restored)
        self.assertEqual(restored.read_bytes(), before)
        self.assertEqual(guard.read_record(restored)["owner"]["id"], "test-owner")

    def test_the_lock_the_key_uses_is_never_moved_or_unlinked(self) -> None:
        """Moving a held lock lets a second process lock a new file of that name."""

        key = self.fixture.write()
        lock = self.fixture.directory / f"{key}.lock"
        lock.touch()
        before = lock.stat().st_ino
        self.fixture.apply(self.fixture.scan())
        self.assertTrue(lock.exists())
        self.assertEqual(lock.stat().st_ino, before)
        self.assertNotIn(".lock", "".join(retire.KEY_SUFFIXES))

    def test_a_second_apply_leaves_no_new_lock_behind(self) -> None:
        key = self.fixture.write()
        manifest = self.fixture.scan()
        self.fixture.apply(manifest)
        (self.fixture.directory / f"{key}.lock").unlink()
        self.fixture.apply(manifest)
        self.assertEqual(self.fixture.present(key), [])

    def test_a_name_already_taken_in_the_retired_directory_is_refused(self) -> None:
        key = self.fixture.write()
        manifest = self.fixture.scan()
        retired = self.fixture.directory / retire.RETIRED_DIRECTORY_NAME
        retired.mkdir(mode=0o700)
        (retired / f"{key}.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(retire.RecordRetirementError):
            self.fixture.apply(manifest)
        self.assertTrue((self.fixture.directory / f"{key}.json").exists())

    def test_a_live_lease_holds_the_record(self) -> None:
        key = self.fixture.write(lease_offset=3_600)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["lease_expired"])
        self.assertFalse(candidate["eligible"])

    def test_a_lease_inside_the_clock_skew_allowance_holds_the_record(self) -> None:
        key = self.fixture.write(lease_offset=-(retire.CLOCK_SKEW_SECONDS // 2))
        self.assertFalse(self.fixture.candidate(self.fixture.scan(), key)["eligible"])

    def test_a_repository_that_still_exists_holds_the_record(self) -> None:
        repository = Path(self.tmp.name) / "live/source/.git"
        repository.mkdir(parents=True)
        key = self.fixture.write(repository=repository)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["repository_absent"])
        self.assertFalse(candidate["eligible"])

    def test_a_worktree_that_still_exists_holds_the_record(self) -> None:
        worktree = Path(self.tmp.name) / "live/worktree"
        worktree.mkdir(parents=True)
        key = self.fixture.write(worktree=worktree)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["worktree_absent"])
        self.assertFalse(candidate["eligible"])

    def test_a_repository_present_under_a_different_identity_is_kept(self) -> None:
        """Device numbers do not survive a reboot, so a present path is never death."""

        repository = Path(self.tmp.name) / "reused/source/.git"
        repository.mkdir(parents=True)
        key = self.fixture.write(repository=repository)
        record = self.fixture.read(key)
        record["repository_identity"]["common_git_dir_inode"] += 1
        record["repository_identity"]["common_git_dir_device"] += 1
        self.fixture.put(key, record)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["repository_absent"])
        self.assertFalse(candidate["eligible"])

    def test_a_worktree_present_under_a_different_identity_is_kept(self) -> None:
        worktree = Path(self.tmp.name) / "reused/worktree"
        worktree.mkdir(parents=True)
        key = self.fixture.write(worktree=worktree)
        record = self.fixture.read(key)
        record["worktree_identity"]["worktree_device"] += 1
        record["worktree_identity"]["worktree_inode"] += 1
        self.fixture.put(key, record)
        self.assertFalse(self.fixture.candidate(self.fixture.scan(), key)["eligible"])

    def test_an_absent_path_no_mount_covers_holds_the_record(self) -> None:
        """The ancestor may sit on the device by accident; the mount must say so."""

        missing = Path(self.tmp.name) / "gone/source/.git"
        device = Path(self.tmp.name).stat().st_dev
        absent, proved = retire.absent_and_proved(missing, device, [])
        self.assertTrue(absent)
        self.assertFalse(proved)

    def test_an_absent_path_a_mount_covers_is_proved(self) -> None:
        missing = Path(self.tmp.name) / "gone/source/.git"
        device = Path(self.tmp.name).stat().st_dev
        absent, proved = retire.absent_and_proved(missing, device, [(Path("/"), device)])
        self.assertTrue(absent)
        self.assertTrue(proved)

    def test_the_deepest_covering_mount_decides(self) -> None:
        path = Path("/a/b/c")
        self.assertEqual(
            retire.covering_mount_device(path, [(Path("/"), 1), (Path("/a/b"), 2)]), 2
        )
        self.assertEqual(
            retire.covering_mount_device(path, [(Path("/a/b"), 2), (Path("/"), 1)]), 2
        )
        self.assertEqual(
            retire.covering_mount_device(path, [(Path("/a/b"), 2), (Path("/a/b"), 3)]), 3
        )
        self.assertIsNone(retire.covering_mount_device(path, [(Path("/x"), 9)]))

    def test_a_symlinked_path_component_holds_the_record(self) -> None:
        """A symlink can point anywhere, so it proves nothing about the filesystem."""

        base = Path(self.tmp.name) / "linked"
        base.mkdir()
        (base / "link").symlink_to(self.fixture.gone)
        key = self.fixture.write(repository=base / "link/source/.git")
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["repository_absent"])
        self.assertFalse(candidate["eligible"])

    def test_an_absent_path_on_an_unseen_filesystem_holds_the_record(self) -> None:
        """An absent path cannot tell a deleted repository from an unmounted disk."""

        key = self.fixture.write(repository_device=999_999)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertTrue(candidate["eligibility_results"]["repository_absent"])
        self.assertFalse(candidate["eligibility_results"]["repository_filesystem_present"])
        self.assertFalse(candidate["eligible"])

    def test_an_absent_worktree_on_an_unseen_filesystem_holds_the_record(self) -> None:
        key = self.fixture.write(worktree_device=999_999)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["worktree_filesystem_present"])
        self.assertFalse(candidate["eligible"])

    def test_a_record_under_a_name_it_did_not_derive_holds(self) -> None:
        """The filename proves the guard wrote the record where it stands."""

        key = self.fixture.write(key="b" * 64)
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertFalse(candidate["eligibility_results"]["record_at_canonical_name"])
        self.assertFalse(candidate["eligible"])

    def test_an_unreadable_record_is_reported_and_left_alone(self) -> None:
        path = self.fixture.directory / ("c" * 64 + ".json")
        path.write_text("not json\n", encoding="utf-8")
        path.chmod(0o600)
        manifest = self.fixture.scan()
        candidate = self.fixture.candidate(manifest, "c" * 64)
        self.assertFalse(candidate["eligibility_results"]["record_readable"])
        self.fixture.apply(manifest)
        self.assertTrue(path.exists())

    def test_a_file_that_is_not_named_like_a_record_is_never_considered(self) -> None:
        stray = self.fixture.directory / "notes.json"
        stray.write_text("{}\n", encoding="utf-8")
        self.fixture.write()
        manifest = self.fixture.scan()
        self.assertNotIn("notes", [item["key"] for item in manifest["candidates"]])
        self.fixture.apply(manifest)
        self.assertTrue(stray.exists())

    def test_a_record_that_changed_after_the_scan_is_not_removed(self) -> None:
        key = self.fixture.write()
        manifest = self.fixture.scan()
        record = self.fixture.read(key)
        record["owner"]["lease_expires_at"] = int(time.time()) + 3_600
        self.fixture.put(key, record)
        report = self.fixture.apply(manifest)
        self.assertEqual(report["changed_since_scan"], [key])
        self.assertEqual(report["retired"], [])
        self.assertTrue((self.fixture.directory / f"{key}.json").exists())

    def test_a_record_absent_since_the_scan_is_reported_separately(self) -> None:
        key = self.fixture.write()
        manifest = self.fixture.scan()
        (self.fixture.directory / f"{key}.json").unlink()
        report = self.fixture.apply(manifest)
        self.assertEqual(report["already_absent"], [key])
        self.assertEqual(report["retired"], [])

    def test_applying_the_same_manifest_twice_removes_nothing_more(self) -> None:
        self.fixture.write()
        manifest = self.fixture.scan()
        first = self.fixture.apply(manifest)
        second = self.fixture.apply(manifest)
        self.assertEqual(second["retired"], [])
        self.assertEqual(second["already_absent"], first["retired"])

    def test_a_removable_record_outside_the_manifest_survives(self) -> None:
        """The manifest chooses the set; a later arrival is not swept in."""

        self.fixture.write("first")
        manifest = self.fixture.scan()
        holdout = self.fixture.write("second")
        self.fixture.apply(manifest)
        self.assertTrue((self.fixture.directory / f"{holdout}.json").exists())

    def written_manifest(self, manifest: dict) -> Path:
        path = ROOT / f".agent-artifacts/git-retirement/test-{os.getpid()}-{id(self)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.addCleanup(path.unlink, True)
        return path

    def test_a_manifest_whose_contents_were_edited_is_refused(self) -> None:
        self.fixture.write()
        manifest = self.fixture.scan()
        manifest["candidates"][0]["eligibility_results"]["lease_expired"] = False
        with self.assertRaises(retire.RecordRetirementError) as caught:
            retire.read_manifest(self.written_manifest(manifest), ROOT)
        self.assertIn("content digest", str(caught.exception))

    def test_a_manifest_whose_verdict_disagrees_with_its_evidence_is_refused(self) -> None:
        """A digest proves the bytes were not edited, not that they are coherent."""

        key = self.fixture.write(lease_offset=3_600)
        manifest = self.fixture.scan()
        manifest["candidates"][0]["eligible"] = True
        manifest["candidates"][0]["retirable_paths"] = [
            key + suffix for suffix in retire.KEY_SUFFIXES
        ]
        with self.assertRaises(retire.RecordRetirementError) as caught:
            retire.read_manifest(self.written_manifest(retire.add_content_digest(manifest)), ROOT)
        self.assertIn("disagrees", str(caught.exception))

    def test_a_manifest_naming_files_outside_its_key_is_refused(self) -> None:
        self.fixture.write()
        manifest = self.fixture.scan()
        manifest["candidates"][0]["retirable_paths"] = ["../escape.json"]
        with self.assertRaises(retire.RecordRetirementError):
            retire.read_manifest(self.written_manifest(retire.add_content_digest(manifest)), ROOT)

    def test_a_manifest_field_of_the_wrong_type_is_refused(self) -> None:
        self.fixture.write()
        manifest = self.fixture.scan()
        manifest["state_directory"] = 17
        with self.assertRaises(retire.RecordRetirementError):
            retire.read_manifest(self.written_manifest(retire.add_content_digest(manifest)), ROOT)

    def test_a_manifest_outside_the_artifact_directory_is_refused(self) -> None:
        self.fixture.write()
        path = Path(self.tmp.name) / "manifest.json"
        path.write_text(json.dumps(self.fixture.scan()), encoding="utf-8")
        with self.assertRaises(retire.RecordRetirementError) as caught:
            retire.read_manifest(path, ROOT)
        self.assertIn(".agent-artifacts/git-retirement", str(caught.exception))

    def test_removal_happens_under_the_key_lock(self) -> None:
        """The manager guards every other operation on this key with that lock."""

        key = self.fixture.write()
        manifest = self.fixture.scan()
        taken: list[Path] = []
        original = guard.locked_file

        def watched(path: Path):
            taken.append(Path(path))
            self.assertTrue((self.fixture.directory / f"{key}.json").exists())
            return original(path)

        guard.locked_file = watched
        self.addCleanup(setattr, guard, "locked_file", original)
        self.fixture.apply(manifest)
        self.assertEqual(taken, [self.fixture.directory / f"{key}.lock"])

    def test_a_failed_move_leaves_the_record_that_accounts_for_the_key(self) -> None:
        """The record moves last, so a failure keeps the key accountable."""

        key = self.fixture.write()
        manifest = self.fixture.scan()
        publication = self.fixture.directory / f"{key}.publish.journal.json"
        original = os.replace

        def refusing(source, target):
            if Path(source) == publication:
                raise OSError("refused")
            return original(source, target)

        os.replace = refusing
        self.addCleanup(setattr, os, "replace", original)
        with self.assertRaises(OSError):
            self.fixture.apply(manifest)
        os.replace = original
        self.assertTrue((self.fixture.directory / f"{key}.json").exists())

    def test_a_sibling_that_is_not_a_regular_file_leaves_the_key_intact(self) -> None:
        """A refusal partway through would leave the key with nothing to account for it."""

        key = self.fixture.write()
        manifest = self.fixture.scan()
        journal = self.fixture.directory / f"{key}.journal.json"
        journal.unlink()
        journal.mkdir()
        with self.assertRaises(retire.RecordRetirementError):
            self.fixture.apply(manifest)
        self.assertTrue((self.fixture.directory / f"{key}.json").exists())
        self.assertTrue((self.fixture.directory / f"{key}.publish.journal.json").exists())

    def test_a_manifest_for_another_directory_is_refused(self) -> None:
        self.fixture.write()
        manifest = self.fixture.scan()
        manifest["state_directory"] = str(Path(self.tmp.name) / "elsewhere")
        with self.assertRaises(retire.RecordRetirementError):
            self.fixture.apply(manifest)

    def test_a_record_directory_others_can_read_is_refused(self) -> None:
        self.fixture.directory.chmod(0o755)
        self.addCleanup(self.fixture.directory.chmod, 0o700)
        with self.assertRaises(guard.WorktreeError):
            retire.validate_state_directory(str(self.fixture.directory))

    def test_the_home_directory_is_refused(self) -> None:
        with self.assertRaises(retire.RecordRetirementError):
            retire.validate_state_directory(str(guard.account_home()))

    def test_a_manifest_records_the_evidence_for_every_decision(self) -> None:
        key = self.fixture.write()
        candidate = self.fixture.candidate(self.fixture.scan(), key)
        self.assertEqual(set(candidate["eligibility_results"]), retire.ELIGIBILITY_KEYS)

    def test_scanning_twice_produces_the_same_digest(self) -> None:
        self.fixture.write()
        now = int(time.time())
        self.assertEqual(
            self.fixture.scan(now=now)["content_digest"],
            self.fixture.scan(now=now)["content_digest"],
        )

    def test_scanning_changes_nothing(self) -> None:
        key = self.fixture.write()
        before = self.fixture.present(key)
        self.fixture.scan()
        self.assertEqual(self.fixture.present(key), before)


class RetiredVisibilityTest(unittest.TestCase):
    """A wrong retirement must stay visible, or a task silently stops existing."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = RecordFixture(Path(self.tmp.name))
        self.directory = self.fixture.directory
        original = guard.state_directory
        guard.state_directory = lambda: self.directory
        self.addCleanup(setattr, guard, "state_directory", original)

    def retired(self) -> Path:
        path = self.directory / guard.RETIRED_DIRECTORY_NAME
        path.mkdir(mode=0o700, exist_ok=True)
        return path

    def test_a_retired_record_is_not_counted_against_the_live_limit(self) -> None:
        retired = self.retired()
        for index in range(guard.MAX_RECORDS_SCANNED + 1):
            (retired / f"{index:064x}.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(guard.candidate_record_paths(), [])
        self.assertEqual(len(guard.retired_record_paths()), guard.MAX_RECORDS_SCANNED + 1)

    def test_a_large_retired_directory_never_stops_a_completion_check(self) -> None:
        """Refusing on this count would stop every repository on the account."""

        retired = self.retired()
        for index in range(guard.MAX_RECORDS_SCANNED * 2):
            (retired / f"{index:064x}.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(
            len(guard.retired_record_paths()), guard.MAX_RECORDS_SCANNED * 2
        )

    def test_a_retired_directory_that_cannot_be_read_is_an_error(self) -> None:
        """An empty answer here would hide the very mistakes it must surface."""

        elsewhere = Path(self.tmp.name) / "elsewhere"
        elsewhere.mkdir(mode=0o700)
        link = self.directory / guard.RETIRED_DIRECTORY_NAME
        link.symlink_to(elsewhere)
        with self.assertRaises(guard.WorktreeError):
            guard.retired_record_paths()
        link.unlink()
        (self.directory / guard.RETIRED_DIRECTORY_NAME).write_text("", encoding="utf-8")
        with self.assertRaises(guard.WorktreeError):
            guard.retired_record_paths()

    def move_during(self, scan: str, source: Path, target: Path) -> None:
        """Move the record as a side effect of the named scan, once."""

        original = getattr(guard, scan)
        moved = []

        def racing():
            result = original()
            if not moved:
                moved.append(True)
                target.parent.mkdir(mode=0o700, exist_ok=True)
                source.rename(target)
            return result

        setattr(guard, scan, racing)
        self.addCleanup(setattr, guard, scan, original)

    def test_a_record_retired_during_enumeration_is_still_reported(self) -> None:
        """Scanning each directory once would lose a record that moves after it."""

        key = self.fixture.write()
        record = guard.read_record(self.directory / f"{key}.json")
        self.move_during(
            "retired_record_paths",
            self.directory / f"{key}.json",
            self.directory / guard.RETIRED_DIRECTORY_NAME / f"{key}.json",
        )
        outstanding = self.outstanding_for(record, key, retired=True)
        self.assertEqual(
            [entry["task"] for entry in outstanding], [guard.task_label(record["task"])]
        )
        self.assertEqual([entry["retired"] for entry in outstanding], [True])

    def test_a_record_restored_during_enumeration_is_reported_once(self) -> None:
        key = self.fixture.write()
        record = guard.read_record(self.directory / f"{key}.json")
        retired = self.retired() / f"{key}.json"
        (self.directory / f"{key}.json").rename(retired)
        self.move_during("candidate_record_paths", retired, self.directory / f"{key}.json")
        outstanding = self.outstanding_for(record, key, retired=False)
        self.assertEqual(len(outstanding), 1)
        self.assertFalse(outstanding[0]["retired"])

    def test_a_record_restored_between_the_two_lookups_is_still_reported(self) -> None:
        """A restore between the live and retired reads would empty both paths."""

        key = self.fixture.write()
        record = guard.read_record(self.directory / f"{key}.json")
        live = self.directory / f"{key}.json"
        retired = self.retired() / f"{key}.json"
        live.rename(retired)
        original = guard.read_record
        moved = []

        def racing(path):
            try:
                return original(path)
            except (OSError, guard.WorktreeError):
                # The restore lands after the live read failed and before the
                # retired read starts, which is what empties both paths.
                if path == live and not moved:
                    moved.append(True)
                    retired.rename(live)
                raise

        guard.read_record = racing
        self.addCleanup(setattr, guard, "read_record", original)
        outstanding = self.outstanding_for(record, key, retired=False)
        self.assertEqual(len(outstanding), 1)
        self.assertFalse(outstanding[0]["retired"])

    def test_a_retired_directory_symlinked_to_nothing_is_an_error(self) -> None:
        """`exists()` follows the link, so a dangling one would read as absent."""

        link = self.directory / guard.RETIRED_DIRECTORY_NAME
        link.symlink_to(Path(self.tmp.name) / "never-created")
        with self.assertRaises(guard.WorktreeError):
            guard.retired_record_paths()

    def test_an_absent_retired_directory_reports_nothing(self) -> None:
        self.assertEqual(guard.retired_record_paths(), [])

    def test_both_creation_paths_refuse_a_retired_task(self) -> None:
        manager = (ROOT / "scripts/manage-plan-worktrees.py").read_text(encoding="utf-8")
        self.assertEqual(manager.count("reject_retired_record(paths)"), 2)
        self.assertIn("retired as unreachable", manager)

    def gate_message(self, entry: dict) -> str:
        import subprocess
        import importlib.util

        path = ROOT / ".project-agent-workflow/hooks/stop_review_gate.py"
        spec = importlib.util.spec_from_file_location("stop_review_gate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = subprocess.run

        def fake(*args, **kwargs):
            return subprocess.CompletedProcess(
                args, 0, json.dumps({"outstanding": [entry], "enforced": True}), ""
            )

        module.subprocess.run = fake
        self.addCleanup(setattr, module.subprocess, "run", original)
        return module.unretired_task(ROOT)

    def entry(self, **overrides: object) -> dict:
        base = {
            "retired": False,
            "task": "plan:332",
            "worktree_path": "/gone/worktree",
            "branch_ref": "refs/heads/task/332",
            "source_ref": "refs/heads/dev",
            "worktree_present": True,
            "lease_expired": False,
        }
        return base | overrides

    def test_the_stop_gate_sends_a_retired_entry_to_the_recovery_it_needs(self) -> None:
        """`publish` and `retire` both need the record that was moved away."""

        message = self.gate_message(self.entry(retired=True))
        self.assertIn("retired as unreachable", message)
        self.assertIn("retired", message)
        self.assertNotIn("publish", message)
        self.assertNotIn("manage-plan-worktrees.py retire", message)

    def test_the_stop_gate_still_names_publish_for_a_live_record(self) -> None:
        message = self.gate_message(self.entry())
        self.assertIn("publish", message)
        self.assertNotIn("retired as unreachable", message)

    def test_retired_journals_are_not_mistaken_for_records(self) -> None:
        retired = self.retired()
        key = "a" * 64
        (retired / f"{key}.journal.json").write_text("{}\n", encoding="utf-8")
        (retired / f"{key}.publish.journal.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(guard.retired_record_paths(), [])

    def test_outstanding_work_reports_a_retired_record_of_a_live_repository(self) -> None:
        """Only a wrong retirement can match a live repository identity."""

        key = self.fixture.write()
        record = guard.read_record(self.directory / f"{key}.json")
        outstanding = self.outstanding_for(record, key, retired=False)
        self.assertEqual([entry["retired"] for entry in outstanding], [False])
        (self.directory / f"{key}.json").rename(self.retired() / f"{key}.json")
        outstanding = self.outstanding_for(record, key, retired=True)
        self.assertEqual([entry["retired"] for entry in outstanding], [True])

    def outstanding_for(self, record: dict, key: str, *, retired: bool) -> list[dict]:
        original_root = guard.repository_root
        original_identity = guard.repository_identity
        guard.repository_root = lambda cwd=None: Path(record["worktree_path"])
        guard.repository_identity = lambda repository: record["repository_identity"]
        self.addCleanup(setattr, guard, "repository_root", original_root)
        self.addCleanup(setattr, guard, "repository_identity", original_identity)
        return guard.outstanding_tasks()

    def test_the_retired_record_path_is_derived_with_every_other_path(self) -> None:
        source = (ROOT / "scripts/project_workflow/worktree_guard.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"retired_record": directory / RETIRED_DIRECTORY_NAME / f"{key}.json"', source
        )

    def test_the_command_and_the_guard_agree_on_the_directory_name(self) -> None:
        self.assertEqual(retire.RETIRED_DIRECTORY_NAME, guard.RETIRED_DIRECTORY_NAME)


class GuardDiagnosticTest(unittest.TestCase):
    """The refusal that stops every command must say how to clear it."""

    def test_the_record_count_refusal_names_the_removal_command(self) -> None:
        message = guard.IMPLAUSIBLE_RECORD_COUNT_MESSAGE
        self.assertIn("retire-stale-worktree-records.py", message)
        self.assertIn("scan", message)

    def test_the_refusal_carries_that_exact_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "records"
            directory.mkdir(mode=0o700)
            for index in range(guard.MAX_RECORDS_SCANNED + 1):
                (directory / f"{index:064x}.json").write_text("{}\n", encoding="utf-8")
            original = guard.state_directory
            guard.state_directory = lambda: directory
            self.addCleanup(setattr, guard, "state_directory", original)
            with self.assertRaises(guard.WorktreeError) as caught:
                guard.candidate_record_paths()
        self.assertEqual(str(caught.exception), guard.IMPLAUSIBLE_RECORD_COUNT_MESSAGE)


class RegistrationTest(unittest.TestCase):
    def test_the_command_and_its_tests_run_in_validation(self) -> None:
        lint = (ROOT / "scripts/lint-project-workflow.sh").read_text(encoding="utf-8")
        self.assertIn("tests/test-stale-record-retirement.py", lint)

    def test_the_command_is_a_required_source_file(self) -> None:
        inventory = (ROOT / "scripts/project_workflow/copier_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/retire-stale-worktree-records.py", inventory)

    def test_the_command_reports_a_refusal_on_its_own_exit_status(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(COMMAND),
                "scan",
                "--state-directory",
                str(guard.account_home()),
                "--manifest-output",
                ".agent-artifacts/git-retirement/unused.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("retire stale worktree records failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
