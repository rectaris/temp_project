#!/usr/bin/env python3
"""Deterministic tests for the Bubblewrap sandboxed plan worker."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run-sandboxed-plan-worker.py"
ENV_PREFIX = "SANDBOXED_PLAN_WORKER_"
TEMPLATE_SCRIPT = ROOT / "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("sandboxed_plan_worker", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import runner module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner_module()


def run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    child_env = dict(os.environ)
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def write_worker(path: Path, body: str) -> None:
    header = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        from __future__ import annotations

        import os
        from pathlib import Path


        prefix = "{ENV_PREFIX}"
        worker_repo = Path(os.environ[prefix + "WORKER_REPO"])
        source_repo = Path(os.environ[prefix + "SOURCE_REPO"])
        scratch_dir = Path(os.environ[prefix + "SCRATCH_DIR"])
        plan_path = os.environ[prefix + "PLAN_PATH"]
        """
    )
    path.write_text(header + textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(0o755)


class SandboxedPlanWorkerTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("git") is None:
            raise RuntimeError("git is required for sandboxed plan worker tests")
        bwrap = shutil.which("bwrap")
        if bwrap is None:
            raise RuntimeError("bwrap is required for sandboxed plan worker tests")
        RUNNER.ensure_bwrap_usable(bwrap)

    def make_repo(self, write_scope: list[str], files: dict[str, str] | None = None) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory()
        repo = Path(temporary.name) / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        (repo / "AGENTS.md").write_text("sandboxed test repo\n", encoding="utf-8")
        (repo / "docs/plan/active").mkdir(parents=True, exist_ok=True)
        (repo / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nid\tpath\tstatus\n001\tdocs/plan/active/001-sandboxed.md\tin_progress\n",
            encoding="utf-8",
        )
        for relative, content in (files or {"allowed.txt": "original\n"}).items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        plan = repo / "docs/plan/active/001-sandboxed.md"
        lines = [
            "# Sandboxed worker test",
            "",
            "status: in_progress",
            "task_types:",
            "  - template_workflow",
            "review_class: B",
            "human_design_required: no",
            "human_approval_status: not_required",
            "write_scope:",
            *(f"  - {entry}" for entry in write_scope),
            "context_files:",
            "  - docs/agent/SPEC_USER_COMMUNICATION.md",
            "required_specs:",
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md",
            "validation:",
            "  - python3 tests/test-sandboxed-plan-worker.py",
            "acceptance:",
            "  - Test fixture.",
            "checked_summary_ja: fixture",
            "",
            "## Tasks",
            "",
            "- [ ] Fixture.",
            "",
        ]
        plan.write_text("\n".join(lines), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "baseline")
        return temporary, repo, "docs/plan/active/001-sandboxed.md"

    def run_with_worker(
        self,
        repo: Path,
        plan_path: str,
        worker_body: str,
        *,
        output_dir: Path | None = None,
        worker_env: dict[str, str] | None = None,
        parent_env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temp_root = output_dir.parent if output_dir is not None else Path(tempfile.mkdtemp(prefix="sandboxed-worker-run-"))
        actual_output = output_dir if output_dir is not None else temp_root / "output"
        worker_path = temp_root / "worker.py"
        write_worker(worker_path, worker_body)
        args = [
            "run",
            plan_path,
            "--output-dir",
            str(actual_output),
            "--worker-binary",
            sys.executable,
            "--worker-arg",
            str(worker_path),
        ]
        for key, value in (worker_env or {}).items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env=parent_env), actual_output, worker_path

    def assert_no_workspace_directories(self, tmpdir_root: Path) -> None:
        leftovers = sorted(path.name for path in tmpdir_root.glob("sandboxed-plan-worker-workspace-*"))
        self.assertEqual(leftovers, [])

    def test_default_worker_command_uses_supported_external_sandbox_flags(self) -> None:
        command = RUNNER.default_worker_command(
            codex_bin="/usr/bin/codex",
            clone_dir=Path("/tmp/clone"),
            scratch_dir=Path("/tmp/scratch"),
            last_message_path=Path("/tmp/last-message.txt"),
            model="model",
            reasoning="medium",
        )
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ephemeral", command)
        self.assertNotIn("--sandbox", command)
        self.assertNotIn("--ask-for-approval", command)
        self.assertNotIn("--dangerously-bypass-hook-trust", command)

    def test_default_worker_stages_minimal_private_codex_home_under_scratch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_codex_home = root / "host-codex-home"
            host_codex_home.mkdir()
            (host_codex_home / "auth.json").write_text('{"token":"secret"}\n', encoding="utf-8")
            for excluded in ("config.toml", "history.jsonl", "models_cache.json"):
                (host_codex_home / excluded).write_text("excluded\n", encoding="utf-8")
            for excluded_dir in ("logs", "sessions", "skills", "hooks", "databases"):
                (host_codex_home / excluded_dir).mkdir()
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()

            with mock.patch.dict(os.environ, {"CODEX_HOME": str(host_codex_home)}):
                env = RUNNER.prepare_worker_environment(
                    source_repo=root / "source",
                    clone_dir=root / "clone",
                    scratch_dir=scratch_dir,
                    plan_rel="docs/plan/active/001-test.md",
                    extra_env=(),
                    include_codex_home=True,
                )

            staged_home = Path(env["CODEX_HOME"])
            self.assertEqual(staged_home, scratch_dir / "codex-home")
            self.assertEqual(staged_home.stat().st_mode & 0o777, 0o700)
            self.assertEqual({path.name for path in staged_home.iterdir()}, {"auth.json"})
            self.assertEqual((staged_home / "auth.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((staged_home / "auth.json").read_text(encoding="utf-8"), '{"token":"secret"}\n')

    def test_default_worker_fails_closed_when_host_auth_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_codex_home = root / "host-codex-home"
            host_codex_home.mkdir()
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(host_codex_home)}):
                with self.assertRaisesRegex(RUNNER.RunnerError, "default Codex worker requires an auth file"):
                    RUNNER.prepare_worker_environment(
                        source_repo=root / "source",
                        clone_dir=root / "clone",
                        scratch_dir=scratch_dir,
                        plan_rel="docs/plan/active/001-test.md",
                        extra_env=(),
                        include_codex_home=True,
                    )

    def test_custom_worker_does_not_receive_or_stage_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(root / "host-codex-home")}):
                env = RUNNER.prepare_worker_environment(
                    source_repo=root / "source",
                    clone_dir=root / "clone",
                    scratch_dir=scratch_dir,
                    plan_rel="docs/plan/active/001-test.md",
                    extra_env=(),
                    include_codex_home=False,
                )
            self.assertNotIn("CODEX_HOME", env)
            self.assertFalse((scratch_dir / "codex-home").exists())

    def test_workspace_temporary_directory_cleanup_removes_staged_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_codex_home = root / "host-codex-home"
            host_codex_home.mkdir()
            (host_codex_home / "auth.json").write_text("secret\n", encoding="utf-8")
            workspace_tmp = tempfile.TemporaryDirectory(dir=root)
            workspace = Path(workspace_tmp.name)
            scratch_dir = workspace / "scratch"
            scratch_dir.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(host_codex_home)}):
                staged_home = RUNNER.stage_codex_home(scratch_dir)
            self.assertTrue((staged_home / "auth.json").is_file())
            workspace_tmp.cleanup()
            self.assertFalse(workspace.exists())

    def test_runner_scripts_have_matching_executable_modes(self) -> None:
        root_mode = SCRIPT.stat().st_mode & 0o777
        template_mode = TEMPLATE_SCRIPT.stat().st_mode & 0o777
        self.assertEqual(root_mode, template_mode)
        self.assertTrue(root_mode & 0o111)

    def test_run_rejects_missing_prerequisites(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        cases = (
            ("git", ("run", plan_path, "--git-bin", "/missing/git")),
            ("bwrap", ("run", plan_path, "--bwrap-bin", "/missing/bwrap", "--worker-binary", sys.executable)),
            ("codex", ("run", plan_path, "--codex-bin", "/missing/codex")),
        )
        for label, argv in cases:
            with self.subTest(prerequisite=label):
                result = run_cli(repo, *argv)
                self.assertEqual(result.returncode, 1)
                self.assertIn("executable is unavailable", result.stderr)

    def test_run_refuses_dirty_source_repo(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must be clean", result.stderr)

    def test_run_rejects_reserved_worker_env_override(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        for env_key in ("HOME", f"{ENV_PREFIX}SOURCE_REPO"):
            with self.subTest(env_key=env_key):
                result, _output_dir, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
                    worker_env={env_key: "/tmp/override"},
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("must not override reserved environment variable", result.stderr)

    def test_run_and_apply_in_scope_patch(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt", "dir/"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _worker_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "allowed.txt").write_text("updated\\n", encoding="utf-8")
                target = worker_repo / "dir" / "nested.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("created\\n", encoding="utf-8")
                (scratch_dir / "note.txt").write_text(plan_path + "\\n", encoding="utf-8")
                """
            ),
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt", "dir/nested.txt"])
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        self.assertFalse((repo / "dir" / "nested.txt").exists())
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "updated\n")
        self.assertEqual((repo / "dir" / "nested.txt").read_text(encoding="utf-8"), "created\n")
        self.assertEqual(git(repo, "diff", "--cached", "--name-only").stdout.strip(), "")
        self.assertEqual(
            git(repo, "status", "--porcelain=1", "--untracked-files=all").stdout.splitlines(),
            [" M allowed.txt", "?? dir/nested.txt"],
        )

    def test_run_rejects_empty_candidate_patch(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output_dir, _worker = self.run_with_worker(repo, plan_path, "pass")
        self.assertEqual(result.returncode, 1)
        self.assertIn("produced no candidate changes", result.stderr)

    def test_run_rejects_out_of_scope_change(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "forbidden.txt").write_text("oops\\n", encoding="utf-8")',
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("outside write_scope", result.stderr)

    def test_apply_rejects_mismatched_head(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("head mismatch\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        (repo / "second.txt").write_text("next head\n", encoding="utf-8")
        git(repo, "add", "second.txt")
        git(repo, "commit", "-qm", "advance head")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("source HEAD no longer matches", apply.stderr)

    def test_run_rejects_worker_commit_or_ref_change(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                import subprocess

                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=Worker",
                        "-c",
                        "user.email=worker@example.invalid",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "malicious commit",
                    ],
                    cwd=worker_repo,
                    check=True,
                )
                """
            ),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("clone HEAD", result.stderr)

    def test_apply_rejects_mismatched_plan_digest(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("digest mismatch\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        plan_file = repo / plan_path
        plan_file.write_text(plan_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        git(repo, "add", plan_path)
        git(repo, "commit", "-qm", "change plan digest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_head"] = git(repo, "rev-parse", "HEAD").stdout.strip()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("active plan digest no longer matches", apply.stderr)

    def test_apply_rejects_mismatched_patch_digest(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("patch mismatch\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        patch_path = Path(manifest["patch_path"])
        patch_path.write_bytes(patch_path.read_bytes() + b"\n")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("candidate patch digest no longer matches", apply.stderr)

    def test_bubblewrap_probe_blocks_source_and_host_temp_writes(self) -> None:
        temporary, repo, plan_path = self.make_repo(["probe.txt"])
        self.addCleanup(temporary.cleanup)
        outside_path = Path(temporary.name) / "outside-host.txt"
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "probe.txt").write_text("inside clone\\n", encoding="utf-8")
                (scratch_dir / "probe-scratch.txt").write_text("inside scratch\\n", encoding="utf-8")
                if os.environ.get("PARENT_ONLY_SENTINEL") is not None:
                    raise SystemExit("parent sentinel leaked into the sandbox")
                denied = []
                for target, label in (
                    (source_repo / "source-write.txt", "source"),
                    (Path(os.environ[prefix + "OUTSIDE_PROBE"]), "outside"),
                ):
                    try:
                        target.write_text("blocked\\n", encoding="utf-8")
                    except OSError:
                        denied.append(label)
                    else:
                        raise SystemExit(f"unexpected write success: {label}")
                if denied != ["source", "outside"]:
                    raise SystemExit(f"unexpected denied set: {denied}")
                """
            ),
            output_dir=output_dir,
            worker_env={f"{ENV_PREFIX}OUTSIDE_PROBE": str(outside_path)},
            parent_env={"PARENT_ONLY_SENTINEL": "host-only"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((repo / "source-write.txt").exists())
        self.assertFalse(outside_path.exists())
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["probe.txt"])

    def test_patch_collection_keeps_clean_filter_inside_bubblewrap(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        outside_path = Path(temporary.name) / "outside-host.txt"
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                f"""\
                import subprocess

                filter_script = scratch_dir / "clean-filter.py"
                filter_script.write_text(
                    {repr(textwrap.dedent(f'''\
                    #!/usr/bin/env python3
                    from __future__ import annotations

                    import os
                    import sys
                    from pathlib import Path


                    target = Path(os.environ["{ENV_PREFIX}OUTSIDE_PROBE"])
                    try:
                        target.write_text("blocked\\n", encoding="utf-8")
                    except OSError:
                        pass
                    else:
                        raise SystemExit("unexpected host write success")
                    sys.stdout.write(sys.stdin.read())
                    '''))},
                    encoding="utf-8",
                )
                filter_script.chmod(0o755)
                subprocess.run(["git", "config", "filter.leak.clean", str(filter_script)], cwd=worker_repo, check=True)
                info_dir = worker_repo / ".git" / "info"
                info_dir.mkdir(parents=True, exist_ok=True)
                (info_dir / "attributes").write_text("allowed.txt filter=leak\\n", encoding="utf-8")
                (worker_repo / "allowed.txt").write_text("through filter\\n", encoding="utf-8")
                """
            ),
            output_dir=output_dir,
            worker_env={f"{ENV_PREFIX}OUTSIDE_PROBE": str(outside_path)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(outside_path.exists())
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])

    def test_run_rejects_symlinked_or_preexisting_output_artifacts(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)

        real_dir = Path(temporary.name) / "real-output"
        real_dir.mkdir()
        symlink_dir = Path(temporary.name) / "output-link"
        symlink_dir.symlink_to(real_dir, target_is_directory=True)
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
            output_dir=symlink_dir,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("symlink", result.stderr)

        preexisting_dir = Path(temporary.name) / "preexisting-output"
        preexisting_dir.mkdir()
        (preexisting_dir / "manifest.json").write_text("occupied\n", encoding="utf-8")
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
            output_dir=preexisting_dir,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not already exist", result.stderr)

    def test_workspace_cleanup_removes_temporary_clone_and_scratch(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        cleanup_root = Path(temporary.name) / "cleanup-root"
        cleanup_root.mkdir()

        for label, worker_body, expected_code in (
            ("success", '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")', 0),
            ("failure", '(worker_repo / "forbidden.txt").write_text("blocked\\n", encoding="utf-8")', 1),
        ):
            with self.subTest(case=label):
                output_dir = Path(temporary.name) / f"{label}-output"
                result, _output, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    worker_body,
                    output_dir=output_dir,
                    parent_env={"TMPDIR": str(cleanup_root)},
                )
                self.assertEqual(result.returncode, expected_code, result.stderr)
                self.assert_no_workspace_directories(cleanup_root)


if __name__ == "__main__":
    unittest.main()
