#!/usr/bin/env python3
"""Disposable-repository tests for local Git retirement scanning."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CLI = ROOT / "scripts/retire-merged-worktrees.py"
SCENARIOS = ROOT / "tests/fixtures/git-retirement/scenarios.json"


def run(
    *arguments: str,
    cwd: Path | None = None,
    check: bool = True,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    command_environment = os.environ.copy()
    command_environment.update(
        {"GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
    )
    if environment:
        command_environment.update(environment)
    completed = subprocess.run(
        list(arguments),
        cwd=cwd,
        env=command_environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(arguments)}\n"
            f"stdout={completed.stdout.decode('utf-8', 'replace')}\n"
            f"stderr={completed.stderr.decode('utf-8', 'replace')}"
        )
    return completed


def git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return run("git", "-C", str(repository), *arguments, check=check)


def snapshot_repository(repository: Path) -> tuple[bytes, ...]:
    return (
        git(repository, "worktree", "list", "--porcelain", "-z").stdout,
        git(repository, "for-each-ref", "--format=%(refname)%00%(objectname)").stdout,
        git(repository, "status", "--porcelain=v2", "--branch", "--untracked-files=all").stdout,
        git(repository, "config", "--local", "--list", "--null").stdout,
        git(repository, "diff", "--binary").stdout,
    )


def snapshot_source_repository() -> tuple[bytes, ...]:
    return snapshot_repository(ROOT)


def write_config(
    repository: Path,
    *,
    enabled: bool = True,
    protected: tuple[str, ...] = ("refs/heads/main", "refs/heads/dev"),
) -> None:
    lines = [
        "version: 1",
        f"enabled: {'true' if enabled else 'false'}",
    ]
    if enabled:
        lines.extend(
            [
                "merge_target_refs:",
                "  - refs/heads/dev",
                "protected_local_branch_refs:",
                *[f"  - {ref}" for ref in protected],
            ]
        )
    else:
        lines.extend(["merge_target_refs: []", "protected_local_branch_refs: []"])
    path = repository / "docs/agent/git-retirement.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def initialize_repository(base: Path) -> tuple[Path, Path, Path]:
    repository = base / "repo"
    allowed_root = base / "linked"
    worktree = allowed_root / "feature"
    repository.mkdir()
    allowed_root.mkdir()
    run("git", "init", "-b", "main", str(repository))
    git(repository, "config", "user.name", "Retirement Test")
    git(repository, "config", "user.email", "retirement@example.invalid")
    (repository / "product.txt").write_text("initial\n", encoding="utf-8")
    (repository / ".gitignore").write_text(".agent-artifacts/\n", encoding="utf-8")
    scripts = repository / "scripts"
    scripts.mkdir()
    shutil.copy2(SOURCE_CLI, scripts / SOURCE_CLI.name)
    write_config(repository)
    git(repository, "add", "product.txt", ".gitignore", "scripts", "docs")
    git(repository, "commit", "-m", "initial")
    git(repository, "branch", "feature")
    git(repository, "switch", "-c", "dev")
    (repository / "product.txt").write_text("integrated\n", encoding="utf-8")
    git(repository, "add", "product.txt")
    git(repository, "commit", "-m", "integrate feature")
    git(repository, "config", "branch.feature.remote", ".")
    git(repository, "config", "branch.feature.merge", "refs/heads/dev")
    git(repository, "worktree", "add", str(worktree), "feature")
    return repository, allowed_root, worktree


def scan(
    repository: Path,
    allowed_root: Path,
    *,
    name: str = "scan.json",
    cwd: Path | None = None,
    command_environment: dict[str, str] | None = None,
    script_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    manifest = repository / ".agent-artifacts/git-retirement" / name
    completed = run(
        sys.executable,
        str(script_path or repository / "scripts/retire-merged-worktrees.py"),
        "scan",
        "--allowed-root",
        str(allowed_root),
        "--manifest",
        str(manifest),
        cwd=cwd or repository,
        check=False,
        environment=command_environment,
    )
    return completed, manifest


def load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_for(manifest: dict[str, object], branch_ref: str) -> dict[str, object]:
    matches = [
        candidate
        for candidate in manifest["candidates"]
        if candidate["branch_ref"] == branch_ref
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one candidate for {branch_ref}, found {len(matches)}")
    return matches[0]


def candidate_at(manifest: dict[str, object], path: Path) -> dict[str, object]:
    matches = [
        candidate
        for candidate in manifest["candidates"]
        if candidate["worktree_path"] == str(path.resolve())
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one candidate at {path}, found {len(matches)}")
    return matches[0]


class GitRetirementScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_before = snapshot_source_repository()

    def tearDown(self) -> None:
        self.assertEqual(snapshot_source_repository(), self.source_before)

    def test_fixture_covers_scan_contract(self) -> None:
        fixture = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        self.assertEqual(fixture["schema_version"], 1)
        self.assertEqual(fixture["suite"], "local-git-retirement-scan")
        self.assertEqual(len(fixture["requirements"]), 5)
        scenarios = fixture["scenarios"]
        self.assertEqual(
            {item["class"] for item in scenarios}, {"median", "edge", "negative", "holdout"}
        )
        holdout = [item for item in scenarios if item["class"] == "holdout"]
        self.assertEqual(len(holdout), 1)
        self.assertFalse(holdout[0]["used_for_tuning"])
        self.assertTrue(
            all(item["used_for_tuning"] is True for item in scenarios if item not in holdout)
        )
        self.assertIn("negative-age-or-name-only", {item["id"] for item in scenarios})

    def test_eligible_scan_is_deterministic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            repository_before = snapshot_repository(repository)
            first, first_path = scan(repository, allowed_root, name="first.json")
            second, second_path = scan(repository, allowed_root, name="second.json")
            self.assertEqual(first.returncode, 0, first.stderr.decode())
            self.assertEqual(second.returncode, 0, second.stderr.decode())
            first_manifest = load_manifest(first_path)
            second_manifest = load_manifest(second_path)
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(first_manifest["schema_version"], 1)
            unsigned = dict(first_manifest)
            digest = unsigned.pop("content_digest")
            payload = json.dumps(unsigned, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
            self.assertEqual(digest, f"sha256:{hashlib.sha256(payload).hexdigest()}")
            candidates = first_manifest["candidates"]
            self.assertEqual(len(candidates), 2)
            primary = candidate_for(first_manifest, "refs/heads/dev")
            self.assertFalse(primary["eligibility_results"]["linked_non_primary"])
            self.assertFalse(primary["eligible"])
            candidate = candidate_for(first_manifest, "refs/heads/feature")
            self.assertEqual(candidate["worktree_path"], str(worktree.resolve()))
            self.assertEqual(candidate["branch_ref"], "refs/heads/feature")
            self.assertEqual(candidate["merge_target_ref"], "refs/heads/dev")
            self.assertEqual(candidate["upstream_ref"], "refs/heads/dev")
            self.assertTrue(candidate["eligible"])
            self.assertTrue(all(candidate["eligibility_results"].values()))
            repository_after = snapshot_repository(repository)
            self.assertEqual(repository_after, repository_before)

    def test_dirty_and_untracked_worktree_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            (worktree / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_for(load_manifest(manifest_path), "refs/heads/feature")
            self.assertFalse(candidate["eligibility_results"]["clean"])
            self.assertFalse(candidate["eligible"])

    def test_missing_upstream_is_blocked_without_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            git(repository, "config", "--unset", "branch.feature.remote")
            git(repository, "config", "--unset", "branch.feature.merge")
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_for(load_manifest(manifest_path), "refs/heads/feature")
            self.assertFalse(candidate["eligibility_results"]["upstream_configured"])
            self.assertFalse(candidate["eligibility_results"]["upstream_available"])
            self.assertFalse(candidate["eligible"])

    def test_non_ancestor_and_upstream_ahead_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            (worktree / "feature.txt").write_text("ahead\n", encoding="utf-8")
            git(worktree, "add", "feature.txt")
            git(worktree, "commit", "-m", "feature ahead")
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_for(load_manifest(manifest_path), "refs/heads/feature")
            self.assertFalse(candidate["eligibility_results"]["tip_is_merge_target_ancestor"])
            self.assertFalse(candidate["eligibility_results"]["upstream_ahead_zero"])
            self.assertEqual(candidate["upstream_relation"]["ahead"], 1)
            self.assertFalse(candidate["eligible"])

    def test_protected_branch_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            write_config(
                repository,
                protected=("refs/heads/main", "refs/heads/dev", "refs/heads/feature"),
            )
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_for(load_manifest(manifest_path), "refs/heads/feature")
            self.assertFalse(candidate["eligibility_results"]["branch_not_protected"])
            self.assertFalse(candidate["eligible"])

    def test_linked_invocation_identifies_primary_and_current_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            completed, manifest_path = scan(
                repository,
                allowed_root,
                cwd=worktree,
                script_path=worktree / "scripts/retire-merged-worktrees.py",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            manifest = load_manifest(manifest_path)
            self.assertEqual(
                manifest["repository_identity"]["primary_worktree"], str(repository.resolve())
            )
            self.assertEqual(manifest["current_worktree"], str(worktree.resolve()))
            primary = candidate_at(manifest, repository)
            linked = candidate_at(manifest, worktree)
            self.assertFalse(primary["eligibility_results"]["linked_non_primary"])
            self.assertFalse(linked["eligibility_results"]["non_current"])
            self.assertFalse(primary["eligible"])
            self.assertFalse(linked["eligible"])

    def test_locked_detached_and_outside_root_worktrees_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            git(repository, "worktree", "lock", "--reason", "test", str(worktree))
            completed, manifest_path = scan(repository, allowed_root, name="locked.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            locked = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(locked["eligibility_results"]["unlocked"])
            git(repository, "worktree", "unlock", str(worktree))

            git(worktree, "switch", "--detach")
            completed, manifest_path = scan(repository, allowed_root, name="detached.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            detached = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(detached["eligibility_results"]["attached_local_branch"])

            narrow_root = allowed_root / "narrow"
            narrow_root.mkdir()
            completed, manifest_path = scan(repository, narrow_root, name="outside.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            outside = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(outside["eligibility_results"]["inside_allowed_root"])

    def test_tracked_dirtiness_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            (worktree / "product.txt").write_text("tracked dirty\n", encoding="utf-8")
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(candidate["eligibility_results"]["clean"])

    def test_ambiguous_and_unavailable_upstreams_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            git(repository, "config", "--add", "branch.feature.merge", "refs/heads/main")
            completed, manifest_path = scan(repository, allowed_root, name="ambiguous.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            ambiguous = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(ambiguous["eligibility_results"]["upstream_unambiguous"])
            self.assertFalse(ambiguous["eligible"])

            git(repository, "config", "--unset-all", "branch.feature.merge")
            git(repository, "config", "branch.feature.remote", "origin")
            git(repository, "config", "branch.feature.merge", "refs/heads/missing")
            git(repository, "remote", "add", "origin", "invalid://never-fetch.example/repo")
            completed, manifest_path = scan(repository, allowed_root, name="unavailable.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            unavailable = candidate_at(load_manifest(manifest_path), worktree)
            self.assertTrue(unavailable["eligibility_results"]["upstream_unambiguous"])
            self.assertFalse(unavailable["eligibility_results"]["upstream_available"])
            self.assertFalse(unavailable["eligible"])

    def test_unresolved_protected_ref_disables_scan(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            write_config(
                repository,
                protected=("refs/heads/main", "refs/heads/dev", "refs/heads/missing"),
            )
            completed, manifest_path = scan(repository, allowed_root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("configured local ref is unresolved", completed.stderr.decode())
            self.assertFalse(manifest_path.exists())

    def test_manifest_requires_repository_ignore_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            (repository / ".gitignore").write_text("unrelated/\n", encoding="utf-8")
            completed, manifest_path = scan(repository, allowed_root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must be ignored", completed.stderr.decode())
            self.assertFalse(manifest_path.exists())

    def test_every_git_subprocess_disables_lazy_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            repository, allowed_root, _ = initialize_repository(base)
            git(repository, "config", "extensions.partialClone", "origin")
            git(repository, "config", "remote.origin.promisor", "true")
            wrapper_dir = base / "bin"
            wrapper_dir.mkdir()
            wrapper = wrapper_dir / "git"
            real_git = shutil.which("git")
            self.assertIsNotNone(real_git)
            wrapper.write_text(
                "#!/bin/sh\n"
                "test \"$GIT_NO_LAZY_FETCH\" = 1 || exit 97\n"
                "case \" $* \" in *\" fetch \"*) exit 98;; esac\n"
                f"exec {real_git} \"$@\"\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            completed, manifest_path = scan(
                repository,
                allowed_root,
                command_environment={
                    "GIT_NO_LAZY_FETCH": "",
                    "PATH": f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}",
                },
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertTrue(manifest_path.is_file())

    def test_inherited_repository_environment_cannot_redirect_candidate_reads(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            (worktree / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            completed, manifest_path = scan(
                repository,
                allowed_root,
                command_environment={
                    "GIT_COMMON_DIR": str(repository / ".git"),
                    "GIT_DIR": str(repository / ".git"),
                    "GIT_INDEX_FILE": str(repository / ".git/index"),
                    "GIT_WORK_TREE": str(repository),
                },
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(candidate["eligibility_results"]["clean"])
            self.assertFalse(candidate["eligible"])

    def test_repository_fsmonitor_is_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            repository, allowed_root, _ = initialize_repository(base)
            marker = base / "fsmonitor-ran"
            hook = base / "fsmonitor-hook"
            hook.write_text(
                "#!/bin/sh\n"
                f"printf marker > {marker}\n"
                "printf '\\n'\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)
            git(repository, "config", "core.fsmonitor", str(hook))
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertTrue(manifest_path.is_file())
            self.assertFalse(marker.exists())

    def test_submodule_ignore_configuration_cannot_hide_dirtiness(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            repository, allowed_root, worktree = initialize_repository(base)
            submodule_source = base / "submodule-source"
            run("git", "init", "-b", "main", str(submodule_source))
            git(submodule_source, "config", "user.name", "Retirement Test")
            git(submodule_source, "config", "user.email", "retirement@example.invalid")
            (submodule_source / "content.txt").write_text("content\n", encoding="utf-8")
            git(submodule_source, "add", "content.txt")
            git(submodule_source, "commit", "-m", "submodule initial")
            run(
                "git",
                "-c",
                "protocol.file.allow=always",
                "-C",
                str(worktree),
                "submodule",
                "add",
                str(submodule_source),
                "sm",
            )
            git(worktree, "commit", "-am", "add submodule")
            git(repository, "config", "submodule.sm.ignore", "all")
            (worktree / "sm/untracked.txt").write_text("dirty\n", encoding="utf-8")
            completed, manifest_path = scan(repository, allowed_root)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            candidate = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(candidate["eligibility_results"]["clean"])
            self.assertFalse(candidate["eligible"])

    def test_empty_duplicate_upstream_values_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, worktree = initialize_repository(Path(raw))
            git(repository, "config", "--add", "branch.feature.remote", "")
            completed, manifest_path = scan(repository, allowed_root, name="empty-remote.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            empty_remote = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(empty_remote["eligibility_results"]["upstream_unambiguous"])
            self.assertFalse(empty_remote["eligible"])

            git(repository, "config", "--unset-all", "branch.feature.remote")
            git(repository, "config", "branch.feature.remote", ".")
            git(repository, "config", "--add", "branch.feature.merge", "")
            completed, manifest_path = scan(repository, allowed_root, name="empty-merge.json")
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            empty_merge = candidate_at(load_manifest(manifest_path), worktree)
            self.assertFalse(empty_merge["eligibility_results"]["upstream_unambiguous"])
            self.assertFalse(empty_merge["eligible"])

    def test_disabled_generated_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            write_config(repository, enabled=False)
            completed, manifest_path = scan(repository, allowed_root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("configuration is disabled", completed.stderr.decode())
            self.assertFalse(manifest_path.exists())

    def test_nested_configuration_cannot_shadow_disabled_root_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            write_config(repository, enabled=False)
            write_config(repository / "scripts", enabled=True)
            completed, manifest_path = scan(repository, allowed_root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("configuration is disabled", completed.stderr.decode())
            self.assertFalse(manifest_path.exists())

    def test_symlinked_configuration_ancestor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            repository, allowed_root, _ = initialize_repository(base)
            shutil.rmtree(repository / "docs")
            shadow_root = base / "shadow-root"
            write_config(shadow_root, enabled=True)
            (repository / "docs").symlink_to(shadow_root / "docs", target_is_directory=True)
            completed, manifest_path = scan(repository, allowed_root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("regular non-symlink", completed.stderr.decode())
            self.assertFalse(manifest_path.exists())

    def test_forbidden_and_symlink_allowed_roots_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            for forbidden in (Path("/"), Path.home(), repository):
                completed, manifest_path = scan(repository, forbidden, name=f"{len(str(forbidden))}.json")
                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse(manifest_path.exists())
            symlink = Path(raw) / "linked-alias"
            symlink.symlink_to(allowed_root, target_is_directory=True)
            completed, manifest_path = scan(repository, symlink, name="symlink.json")
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("symlink component", completed.stderr.decode())
            self.assertFalse(manifest_path.exists())

    def test_manifest_output_cannot_escape_local_artifact_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository, allowed_root, _ = initialize_repository(Path(raw))
            escaped = Path(raw) / "escaped.json"
            completed = run(
                sys.executable,
                str(repository / "scripts/retire-merged-worktrees.py"),
                "scan",
                "--allowed-root",
                str(allowed_root),
                "--manifest",
                str(escaped),
                cwd=repository,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(".agent-artifacts/git-retirement", completed.stderr.decode())
            self.assertFalse(escaped.exists())


if __name__ == "__main__":
    unittest.main()
