#!/usr/bin/env python3
"""Deterministic tests for the Bubblewrap sandboxed plan worker."""

from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import math
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
    command_args = list(args)
    operations = {"run", "correct", "validate", "apply", "finalize-apply"}
    manifest_path = None
    if command_args and command_args[0] in operations:
        if command_args[0] == "correct" and len(command_args) >= 3:
            manifest_path = Path(command_args[2])
        elif command_args[0] in {"validate", "apply", "finalize-apply"} and len(command_args) >= 2:
            manifest_path = Path(command_args[1])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path and manifest_path.is_file() else None
        if "--lifecycle-state" not in command_args:
            if manifest:
                lifecycle_path = manifest["lifecycle_state_path"]
                run_id = manifest["orchestration_run_id"]
            else:
                output_path = (
                    Path(command_args[command_args.index("--output-dir") + 1]).absolute()
                    if "--output-dir" in command_args
                    else Path(tempfile.mkdtemp(prefix="test-lifecycle-")) / "output"
                )
                lifecycle_path = str(output_path.with_name(output_path.name + ".lifecycle.json"))
                run_id = hashlib.sha256(lifecycle_path.encode()).hexdigest()[:24]
            command_args.extend(["--lifecycle-state", lifecycle_path])
            if "--orchestration-run-id" not in command_args:
                command_args.extend(["--orchestration-run-id", run_id])
        lifecycle_path = command_args[command_args.index("--lifecycle-state") + 1]
        run_id = command_args[command_args.index("--orchestration-run-id") + 1]
        if "--plan-execution-state" not in command_args:
            execution_state = str(Path(lifecycle_path).with_name(Path(lifecycle_path).name + f".{run_id}.plan-execution.json"))
            plan_rel = manifest["plan_path"] if manifest else command_args[1]
            plan_file = repo / plan_rel
            if not Path(execution_state).exists():
                plan_text = plan_file.read_text(encoding="utf-8")
                invariant_match = __import__("re").search(r"^primary_invariant: (.+)$", plan_text, flags=__import__("re").MULTILINE)
                invariant = invariant_match.group(1) if invariant_match else "legacy candidate invariant"
                initialized = subprocess.run(
                    [
                        sys.executable, str(ROOT / "scripts/plan-execution-state.py"), "init", execution_state,
                        "--run-id", run_id, "--plan", plan_rel,
                        "--plan-digest", "sha256:" + hashlib.sha256(plan_file.read_bytes()).hexdigest(),
                        "--source-head", git(repo, "rev-parse", "HEAD").stdout.strip(),
                        "--primary-invariant-digest", "sha256:" + hashlib.sha256(invariant.encode()).hexdigest(),
                        "--lifecycle-state", lifecycle_path, "--implementation-mode", "candidate",
                    ], cwd=repo, env=dict(os.environ), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if initialized.returncode != 0:
                    return initialized
            command_args.extend(["--plan-execution-state", execution_state])
        else:
            execution_state = command_args[command_args.index("--plan-execution-state") + 1]
        if command_args[0] == "apply" and manifest_path is not None and manifest_path.is_file():
            try:
                lifecycle = json.loads(Path(lifecycle_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                lifecycle = {}
            validation_base = [
                sys.executable, str(SCRIPT), "validate", str(manifest_path),
                "--parent-diff-approved", "--critical-invariants-approved",
                "--lifecycle-state", lifecycle_path, "--orchestration-run-id", run_id,
                "--plan-execution-state", execution_state,
            ]
            if lifecycle.get("phase") == "admitted" and lifecycle.get("focused_required"):
                focused = subprocess.run(
                    [*validation_base, "--suite", "focused", "--output-dir", tempfile.mkdtemp(prefix="auto-focused-", dir=manifest_path.parent)],
                    cwd=repo, env=child_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if focused.returncode != 0:
                    return focused
                lifecycle = json.loads(Path(lifecycle_path).read_text(encoding="utf-8"))
            if lifecycle.get("phase") in {"admitted", "focused_passed"}:
                authoritative = subprocess.run(
                    [*validation_base, "--suite", "authoritative", "--output-dir", tempfile.mkdtemp(prefix="auto-authoritative-", dir=manifest_path.parent)],
                    cwd=repo, env=child_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if authoritative.returncode != 0:
                    return authoritative
    return subprocess.run(
        [sys.executable, str(SCRIPT), *command_args],
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


def object_directory(repo: Path) -> Path:
    output = git(repo, "rev-parse", "--path-format=absolute", "--git-path", "objects").stdout.strip()
    return Path(output).resolve()


def object_database_snapshot(repo: Path) -> dict[str, bytes]:
    objects = object_directory(repo)
    return {
        str(path.relative_to(objects)): path.read_bytes()
        for path in objects.rglob("*")
        if path.is_file()
    }


def execution_state_path(manifest: dict[str, object]) -> Path:
    lifecycle = Path(str(manifest["lifecycle_state_path"]))
    run_id = str(manifest["orchestration_run_id"])
    return lifecycle.with_name(lifecycle.name + f".{run_id}.plan-execution.json")


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


def write_fake_codex(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            from __future__ import annotations

            import os
            import sys
            from pathlib import Path


            args = sys.argv[1:]
            model = args[args.index("--model") + 1]
            config = args[args.index("--config") + 1]
            reasoning = config.split('=', 1)[1].strip('"')
            scenario = os.environ["FAKE_CODEX_SCENARIO"]
            primary_model = os.environ.get("FAKE_PRIMARY_MODEL", "gpt-5.3-codex-spark")
            fallback_model = os.environ.get("FAKE_FALLBACK_MODEL", "gpt-5.6-luna")
            primary_reasoning = os.environ.get("FAKE_PRIMARY_REASONING", "medium")
            fallback_reasoning = os.environ.get("FAKE_FALLBACK_REASONING", "max")
            worker_repo = Path(os.environ["{ENV_PREFIX}WORKER_REPO"])
            scratch_dir = Path(os.environ["{ENV_PREFIX}SCRATCH_DIR"])
            target = worker_repo / "allowed.txt"
            last_message = None
            if "--output-last-message" in args:
                last_message = Path(args[args.index("--output-last-message") + 1])

            if model == primary_model:
                if reasoning != primary_reasoning:
                    raise SystemExit(f"unexpected primary reasoning: {{reasoning}}")
                if scenario == "primary_success":
                    target.write_text("preferred\\n", encoding="utf-8")
                elif scenario in {{"unavailable_then_success", "unavailable_then_failure", "both_unavailable"}}:
                    target.write_text("discarded-primary\\n", encoding="utf-8")
                    if last_message is not None:
                        last_message.write_text("failed preferred output\\n", encoding="utf-8")
                    print("ERROR: You've hit your usage limit for the preferred model.", file=sys.stderr)
                    raise SystemExit(1)
                elif scenario == "nonavailability_failure":
                    target.write_text("discarded-error\\n", encoding="utf-8")
                    print("ERROR: worker validation failed", file=sys.stderr)
                    raise SystemExit(1)
                else:
                    raise SystemExit(f"unexpected scenario: {{scenario}}")
            elif model == fallback_model:
                if reasoning != fallback_reasoning:
                    raise SystemExit(f"unexpected fallback reasoning: {{reasoning}}")
                expected_starts = {{"initial candidate\\n", "fallback\\n"}} if "{ENV_PREFIX}CORRECTION_BRIEF" in os.environ else {{"original\\n"}}
                if target.read_text(encoding="utf-8") not in expected_starts:
                    raise SystemExit("fallback inherited preferred-attempt changes")
                host_codex_home = Path(os.environ["FAKE_HOST_CODEX_HOME"])
                output_dir = Path(os.environ["FAKE_OUTPUT_DIR"])
                primary_root = scratch_dir.parents[1] / "primary"
                for forbidden in (
                    host_codex_home / "auth.json",
                    output_dir / "worker-primary.stderr",
                    primary_root / "clone" / "allowed.txt",
                ):
                    if forbidden.exists():
                        raise SystemExit(f"fallback can read hidden attempt state: {{forbidden}}")
                if scenario == "unavailable_then_success":
                    target.write_text("fallback\\n", encoding="utf-8")
                elif scenario == "unavailable_then_failure":
                    print("ERROR: fallback implementation failed", file=sys.stderr)
                    raise SystemExit(2)
                elif scenario == "both_unavailable":
                    print("FATAL: rate limit exceeded", file=sys.stderr)
                    raise SystemExit(1)
                else:
                    raise SystemExit("fallback ran unexpectedly")
            else:
                raise SystemExit(f"unexpected model: {{model}}")

            if last_message is not None:
                last_message.write_text(f"completed with {{model}}\\n", encoding="utf-8")
            print(f"completed with {{model}}")
            """
        ),
        encoding="utf-8",
    )
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

    def make_repo(
        self,
        write_scope: list[str],
        files: dict[str, str] | None = None,
        *,
        repo_name: str = "repo",
        validation: list[str] | None = None,
        focused_validation: list[str] | None = None,
        validation_authority_scope: list[str] | None = None,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory()
        repo = Path(temporary.name) / repo_name
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
            "implementation_risk: low",
            "implementation_ambiguity: low",
            "write_scope:",
            *(f"  - {entry}" for entry in write_scope),
            "context_files:",
            "  - docs/agent/SPEC_USER_COMMUNICATION.md",
            "required_specs:",
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md",
            "validation:",
            *(f"  - {command}" for command in (validation or ["git diff --check"])),
            *(
                ["focused_validation:", *(f"  - {command}" for command in focused_validation)]
                if focused_validation is not None
                else []
            ),
            *(
                ["validation_authority_scope:", *(f"  - {entry}" for entry in validation_authority_scope)]
                if validation_authority_scope is not None
                else []
            ),
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
        extra_args: tuple[str, ...] = (),
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
            *extra_args,
        ]
        for key, value in (worker_env or {}).items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env=parent_env), actual_output, worker_path

    def run_with_fake_codex(
        self,
        repo: Path,
        plan_path: str,
        scenario: str,
        *,
        output_dir: Path,
        extra_args: tuple[str, ...] = (),
        fake_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        fake_codex = output_dir.parent / f"fake-codex-{scenario}.py"
        write_fake_codex(fake_codex)
        codex_home = output_dir.parent / f"codex-home-{scenario}-{output_dir.name}"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text('{"token":"fixture"}\n', encoding="utf-8")
        args = [
            "run",
            plan_path,
            "--output-dir",
            str(output_dir),
            "--codex-bin",
            str(fake_codex),
            *extra_args,
        ]
        worker_env = {
            "FAKE_CODEX_SCENARIO": scenario,
            "FAKE_HOST_CODEX_HOME": str(codex_home),
            "FAKE_OUTPUT_DIR": str(output_dir),
            **(fake_env or {}),
        }
        for key, value in worker_env.items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env={"CODEX_HOME": str(codex_home)})

    def run_correction_with_worker(
        self,
        repo: Path,
        plan_path: str,
        prior_manifest: Path,
        correction_brief: Path,
        worker_body: str,
        *,
        output_dir: Path,
        extra_args: tuple[str, ...] = (),
        worker_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        worker_root = Path(tempfile.mkdtemp(prefix="sandboxed-correction-worker-"))
        self.addCleanup(shutil.rmtree, worker_root, True)
        worker = worker_root / "worker.py"
        write_worker(worker, worker_body)
        args = [
            "correct",
            plan_path,
            str(prior_manifest),
            str(correction_brief),
            "--output-dir",
            str(output_dir),
            "--worker-binary",
            sys.executable,
            "--worker-arg",
            str(worker),
            *extra_args,
        ]
        for key, value in (worker_env or {}).items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args)

    def run_correction_with_fake_codex(
        self,
        repo: Path,
        plan_path: str,
        prior_manifest: Path,
        correction_brief: Path,
        scenario: str,
        *,
        output_dir: Path,
        extra_args: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        tool_root = Path(tempfile.mkdtemp(prefix="sandboxed-correction-codex-"))
        self.addCleanup(shutil.rmtree, tool_root, True)
        fake_codex = tool_root / "fake-codex.py"
        write_fake_codex(fake_codex)
        codex_home = tool_root / "codex-home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text('{"token":"fixture"}\n', encoding="utf-8")
        args = [
            "correct",
            plan_path,
            str(prior_manifest),
            str(correction_brief),
            "--output-dir",
            str(output_dir),
            "--codex-bin",
            str(fake_codex),
            *extra_args,
        ]
        for key, value in {
            "FAKE_CODEX_SCENARIO": scenario,
            "FAKE_HOST_CODEX_HOME": str(codex_home),
            "FAKE_OUTPUT_DIR": str(output_dir),
        }.items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env={"CODEX_HOME": str(codex_home)})

    def assert_no_workspace_directories(self, tmpdir_root: Path) -> None:
        leftovers = sorted(path.name for path in tmpdir_root.glob("sandboxed-plan-worker-workspace-*"))
        self.assertEqual(leftovers, [])

    def write_availability_state(
        self,
        path: Path,
        run_id: str,
        entries: list[dict[str, str]],
        **extra: object,
    ) -> None:
        payload: dict[str, object] = {
            "schema_version": 1,
            "orchestration_run_id": run_id,
            "unavailable_models": entries,
            **extra,
        }
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

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
        prompt = RUNNER.build_worker_prompt("docs/plan/active/001-test.md", "0" * 64)
        self.assertIn("Do not run plan validation", prompt)
        self.assertNotIn("Run every validation command", prompt)

    def test_codex_unavailability_classifier_is_bounded_to_cli_error_lines(self) -> None:
        cases = (
            (b"", b"ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.", "usage_limit"),
            (b"", b"ERROR: Usage limit exceeded for model GPT-5.3-Codex-Spark.", "usage_limit"),
            (b"", b"FATAL: rate limit exceeded", "rate_limit"),
            (b"", b"ERROR: model preferred is unavailable", "model_unavailable"),
            (b"", b"ERROR: The model gpt-x does not exist or you do not have access to it.", "model_unavailable"),
            (b"", b"ERROR: you don't have access to this model", "model_access_denied"),
            (b"", b"ERROR: Access to model gpt-x is denied.", "model_access_denied"),
            (b"ERROR: worker validation failed", b"", None),
            (b"ERROR: rate limit exceeded", b"", None),
            (b"report says rate limit exceeded", b"", None),
            (b"", b"ERROR: dependency API rate limit exceeded", None),
            (b"", b"ERROR: rate limit exceeded\nERROR: authentication failed", None),
            (b"", b"authentication failed", None),
            (b"", b"network unavailable", None),
        )
        for stdout, stderr, expected in cases:
            with self.subTest(stderr=stderr):
                self.assertEqual(RUNNER.classify_codex_unavailability(stdout, stderr), expected)

    def test_plan_writable_profile_selection_and_invalid_classifications(self) -> None:
        self.assertEqual(
            RUNNER.select_plan_writable_profile(
                {"implementation_risk": "low", "implementation_ambiguity": "low"}
            ),
            ("gpt-5.3-codex-spark", "medium"),
        )
        self.assertEqual(
            RUNNER.select_plan_writable_profile(
                {"implementation_risk": "ordinary", "implementation_ambiguity": "low"}
            ),
            ("gpt-5.6-terra", "medium"),
        )
        self.assertEqual(RUNNER.select_plan_writable_profile({}), ("gpt-5.6-terra", "medium"))
        invalid = (
            {"implementation_risk": "high", "implementation_ambiguity": "low"},
            {"implementation_risk": "low", "implementation_ambiguity": "high"},
            {"implementation_risk": "", "implementation_ambiguity": "low"},
            {"implementation_risk": "   ", "implementation_ambiguity": "low"},
            {"implementation_risk": ["low"], "implementation_ambiguity": "low"},
            {"implementation_risk": "unknown", "implementation_ambiguity": "low"},
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaisesRegex(RUNNER.RunnerError, "implementation"):
                    RUNNER.select_plan_writable_profile(values)

    def test_writable_model_and_reasoning_overrides_are_strict(self) -> None:
        self.assertEqual(RUNNER.require_writable_model("custom-writable", "preferred"), "custom-writable")
        self.assertEqual(RUNNER.require_reasoning_effort("high", "preferred"), "high")
        for model in (None, "", "   ", "gpt-5.6-sol", "GPT-5.6-SOL"):
            with self.subTest(model=model):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.require_writable_model(model, "preferred")
        for reasoning in (None, "", "   "):
            with self.subTest(reasoning=reasoning):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.require_reasoning_effort(reasoning, "preferred")

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

    def test_worker_environment_routes_caches_to_scratch_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()
            env = RUNNER.prepare_worker_environment(
                source_repo=root / "source",
                clone_dir=root / "clone",
                scratch_dir=scratch_dir,
                plan_rel="docs/plan/active/001-test.md",
                extra_env=(),
                include_codex_home=False,
            )
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(env["PYTHONPYCACHEPREFIX"], str(scratch_dir / "python-pycache"))
            self.assertEqual(env["PIP_CACHE_DIR"], str(scratch_dir / "pip-cache"))
            self.assertEqual(env["UV_CACHE_DIR"], str(scratch_dir / "uv-cache"))
            self.assertEqual(env["UV_PROJECT_ENVIRONMENT"], str(scratch_dir / "uv-project-environment"))
            self.assertEqual(len(env), len(set(env)))

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
        self.assertEqual(manifest["worker_result"]["kind"], "custom")
        self.assertNotIn("attempts", manifest["worker_result"])
        self.assertNotIn("fallback_reason", manifest["worker_result"])
        telemetry = manifest["telemetry"]
        self.assertEqual(
            {key: telemetry[key] for key in (
                "schema_version",
                "model_starts",
                "availability_failures",
                "skipped_known_unavailable_starts",
                "candidate_generations",
                "full_validation_count",
                "implementation_risk",
                "implementation_ambiguity",
            )},
            {
                "schema_version": 1,
                "model_starts": 0,
                "availability_failures": 0,
                "skipped_known_unavailable_starts": 0,
                "candidate_generations": 1,
                "full_validation_count": 0,
                "implementation_risk": "low",
                "implementation_ambiguity": "low",
            },
        )
        self.assertEqual(len(telemetry["attempt_durations_seconds"]), 1)
        self.assertGreaterEqual(telemetry["attempt_durations_seconds"][0], 0)
        self.assertGreaterEqual(telemetry["runner_duration_seconds"], telemetry["attempt_durations_seconds"][0])
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

    def test_changed_path_derivation_keeps_candidate_blobs_out_of_source_objects(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        candidate_content = b"unique path-derivation candidate\n"
        (repo / "allowed.txt").write_bytes(candidate_content)
        patch_path = Path(temporary.name) / "candidate.patch"
        patch_path.write_bytes(git(repo, "diff", "--binary", "HEAD").stdout.encode("utf-8"))
        before = object_database_snapshot(repo)
        candidate_oid = subprocess.run(
            ["git", "hash-object", "--stdin"],
            cwd=repo,
            input=candidate_content,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.decode("ascii").strip()

        self.assertEqual(
            RUNNER.derive_changed_paths_from_patch(repo, "git", patch_path.read_bytes(), git(repo, "rev-parse", "HEAD").stdout.strip()),
            ["allowed.txt"],
        )
        self.assertEqual(object_database_snapshot(repo), before)
        self.assertNotIn(f"{candidate_oid[:2]}/{candidate_oid[2:]}", before)

    def test_manifest_generation_isolated_for_colon_path_alternate_and_ambient_git_overrides(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            repo_name="repo:候補",
        )
        self.addCleanup(temporary.cleanup)
        source_objects = object_directory(repo)
        alternate = Path(temporary.name) / "alternate:既存"
        alternate.mkdir()
        (source_objects / "info").mkdir(exist_ok=True)
        (source_objects / "info" / "alternates").write_text(f"{alternate}\n", encoding="utf-8")
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repo,
            env={**os.environ, "GIT_OBJECT_DIRECTORY": str(alternate)},
            input=b"existing alternate object\n",
            stdout=subprocess.PIPE,
            check=True,
        )
        before = object_database_snapshot(repo)
        output_dir = Path(temporary.name) / "artifacts"
        ambient_objects = Path(temporary.name) / "ambient-objects"
        ambient_git_dir = Path(temporary.name) / "ambient-git-dir"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("unique colon candidate\\n", encoding="utf-8")',
            output_dir=output_dir,
            parent_env={
                "GIT_OBJECT_DIRECTORY": str(ambient_objects),
                "GIT_DIR": str(ambient_git_dir),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(RUNNER.resolve_source_object_directory(repo, "git"), source_objects)
        self.assertEqual(object_database_snapshot(repo), before)
        self.assertFalse(ambient_objects.exists())
        quoted = RUNNER.git_c_quote_path(source_objects)
        self.assertTrue(quoted.startswith('"') and quoted.endswith('"'))
        self.assertIn(":", quoted)

    def test_manifest_generation_from_linked_worktree_keeps_common_objects_clean(self) -> None:
        temporary, main_repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        linked_repo = Path(temporary.name) / "linked:worktree"
        git(main_repo, "worktree", "add", "-q", "-b", "linked", str(linked_repo))
        before = object_database_snapshot(main_repo)
        output_dir = Path(temporary.name) / "linked-artifacts"
        result, _output, _worker = self.run_with_worker(
            linked_repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("unique linked candidate\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(object_directory(linked_repo), object_directory(main_repo))
        self.assertEqual(object_database_snapshot(main_repo), before)

    def test_rejected_apply_preflight_keeps_source_objects_clean(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "preflight-artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("unique rejected candidate\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["changed_paths"] = ["unexpected.txt"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        before = object_database_snapshot(repo)
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("changed paths do not match", apply.stderr)
        self.assertEqual(object_database_snapshot(repo), before)

    def test_preferred_codex_success_does_not_start_fallback(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "preferred-output"
        result = self.run_with_fake_codex(
            repo, plan_path, "primary_success", output_dir=output_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        worker_result = manifest["worker_result"]
        self.assertEqual(worker_result["selected_attempt"], "primary")
        self.assertNotIn("fallback_reason", worker_result)
        self.assertEqual(
            [(attempt["model"], attempt["reasoning_effort"], attempt["selected"]) for attempt in worker_result["attempts"]],
            [("gpt-5.3-codex-spark", "medium", True)],
        )
        self.assertFalse((output_dir / "worker-fallback.stdout").exists())

    def test_ordinary_plan_selects_terra_and_explicit_override_is_honored(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        plan = repo / plan_path
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("implementation_risk: low", "implementation_risk: ordinary"),
            encoding="utf-8",
        )
        git(repo, "add", plan_path)
        git(repo, "commit", "-qm", "ordinary classification")
        terra_output = Path(temporary.name) / "terra-output"
        terra = self.run_with_fake_codex(
            repo,
            plan_path,
            "primary_success",
            output_dir=terra_output,
            fake_env={"FAKE_PRIMARY_MODEL": "gpt-5.6-terra"},
        )
        self.assertEqual(terra.returncode, 0, terra.stderr)
        terra_manifest = json.loads(Path(terra.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(terra_manifest["worker_result"]["attempts"][0]["model"], "gpt-5.6-terra")

        override_output = Path(temporary.name) / "override-output"
        override = self.run_with_fake_codex(
            repo,
            plan_path,
            "primary_success",
            output_dir=override_output,
            extra_args=(
                "--codex-model",
                "custom-writable",
                "--codex-reasoning-effort",
                "high",
            ),
            fake_env={"FAKE_PRIMARY_MODEL": "custom-writable", "FAKE_PRIMARY_REASONING": "high"},
        )
        self.assertEqual(override.returncode, 0, override.stderr)
        override_manifest = json.loads(Path(override.stdout.strip()).read_text(encoding="utf-8"))
        attempt = override_manifest["worker_result"]["attempts"][0]
        self.assertEqual((attempt["model"], attempt["reasoning_effort"]), ("custom-writable", "high"))

    def test_cli_refuses_high_classifications_blank_values_and_writable_sol(self) -> None:
        classification_cases = (
            ("implementation_risk: low", "implementation_risk: high"),
            ("implementation_ambiguity: low", "implementation_ambiguity: high"),
            ("implementation_risk: low", "implementation_risk:"),
            ("implementation_risk: low", "implementation_risk:\n  - low"),
            ("implementation_risk: low", "implementation_risk: unknown"),
        )
        for index, (before, after) in enumerate(classification_cases):
            with self.subTest(classification=after):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"])
                self.addCleanup(temporary.cleanup)
                plan = repo / plan_path
                plan.write_text(plan.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
                git(repo, "add", plan_path)
                git(repo, "commit", "-qm", f"invalid classification {index}")
                result, output_dir, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    '(worker_repo / "allowed.txt").write_text("must not run\\n", encoding="utf-8")',
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("implementation_", result.stderr)
                self.assertFalse((output_dir / "candidate.patch").exists())

        override_cases = (
            ("--codex-model", ""),
            ("--codex-reasoning-effort", "  "),
            ("--codex-model", "gpt-5.6-sol"),
            ("--fallback-codex-model", "GPT-5.6-SOL"),
        )
        for index, override in enumerate(override_cases):
            with self.subTest(override=override):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"])
                self.addCleanup(temporary.cleanup)
                output_dir = Path(temporary.name) / f"rejected-override-{index}"
                result = self.run_with_fake_codex(
                    repo,
                    plan_path,
                    "primary_success",
                    output_dir=output_dir,
                    extra_args=override,
                )
                self.assertEqual(result.returncode, 1)
                self.assertRegex(result.stderr, "non-empty|reserved for independent review")
                self.assertFalse((output_dir / "worker-primary.stdout").exists())

    def test_unavailable_preferred_codex_uses_fresh_fallback_clone_and_records_provenance(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "fallback-output"
        result = self.run_with_fake_codex(
            repo, plan_path, "unavailable_then_success", output_dir=output_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        worker_result = manifest["worker_result"]
        self.assertEqual(worker_result["selected_attempt"], "fallback")
        self.assertEqual(worker_result["fallback_reason"], "usage_limit")
        self.assertEqual(
            [
                (attempt["label"], attempt["model"], attempt["reasoning_effort"], attempt["returncode"], attempt["selected"])
                for attempt in worker_result["attempts"]
            ],
            [
                ("primary", "gpt-5.3-codex-spark", "medium", 1, False),
                ("fallback", "gpt-5.6-luna", "max", 0, True),
            ],
        )
        for attempt in worker_result["attempts"]:
            self.assertEqual(len(attempt["stdout_digest"]), 64)
            self.assertEqual(len(attempt["stderr_digest"]), 64)
            self.assertNotIn("usage limit", json.dumps(attempt).lower())
        self.assertFalse((output_dir / "worker-primary-last-message.txt").exists())
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "fallback\n")

    def test_availability_state_records_and_skips_preferred_with_bounded_telemetry(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        state_path = Path(temporary.name) / "availability.json"
        common_args = (
            "--availability-state",
            str(state_path),
            "--orchestration-run-id",
            "run-routing-001",
        )
        first_output = Path(temporary.name) / "availability-first"
        first = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=first_output,
            extra_args=common_args,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state,
            {
                "schema_version": 1,
                "orchestration_run_id": "run-routing-001",
                "unavailable_models": [
                    {"model": "gpt-5.3-codex-spark", "reason": "usage_limit"}
                ],
            },
        )
        self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("prompt", json.dumps(state).lower())
        self.assertNotIn("credential", json.dumps(state).lower())
        first_manifest = json.loads(Path(first.stdout.strip()).read_text(encoding="utf-8"))
        first_telemetry = first_manifest["telemetry"]
        self.assertEqual(first_telemetry["model_starts"], 2)
        self.assertEqual(first_telemetry["availability_failures"], 1)
        self.assertEqual(first_telemetry["skipped_known_unavailable_starts"], 0)
        self.assertEqual(first_telemetry["candidate_generations"], 1)
        self.assertEqual(first_telemetry["full_validation_count"], 0)
        self.assertEqual(len(first_telemetry["attempt_durations_seconds"]), 2)

        second_output = Path(temporary.name) / "availability-second"
        second = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=second_output,
            extra_args=common_args,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        second_manifest = json.loads(Path(second.stdout.strip()).read_text(encoding="utf-8"))
        attempts = second_manifest["worker_result"]["attempts"]
        self.assertEqual([(item["label"], item["model"]) for item in attempts], [("fallback", "gpt-5.6-luna")])
        second_telemetry = second_manifest["telemetry"]
        self.assertEqual(second_telemetry["model_starts"], 1)
        self.assertEqual(second_telemetry["availability_failures"], 0)
        self.assertEqual(second_telemetry["skipped_known_unavailable_starts"], 1)
        self.assertEqual(len(second_telemetry["attempt_durations_seconds"]), 1)
        for value in [
            second_telemetry["runner_duration_seconds"],
            *second_telemetry["attempt_durations_seconds"],
        ]:
            self.assertIsInstance(value, (int, float))
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, RUNNER.TELEMETRY_MAX_DURATION_SECONDS)

    def test_availability_state_records_fallback_failure_and_skips_both_models(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        state_path = Path(temporary.name) / "both-unavailable.json"
        args = (
            "--availability-state",
            str(state_path),
            "--orchestration-run-id",
            "run-both-unavailable",
        )
        first_output = Path(temporary.name) / "both-first"
        first = self.run_with_fake_codex(
            repo,
            plan_path,
            "both_unavailable",
            output_dir=first_output,
            extra_args=args,
        )
        self.assertEqual(first.returncode, 1)
        self.assertIn("fallback worker exited", first.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["unavailable_models"],
            [
                {"model": "gpt-5.3-codex-spark", "reason": "usage_limit"},
                {"model": "gpt-5.6-luna", "reason": "rate_limit"},
            ],
        )
        second_output = Path(temporary.name) / "both-second"
        second = self.run_with_fake_codex(
            repo,
            plan_path,
            "both_unavailable",
            output_dir=second_output,
            extra_args=args,
        )
        self.assertEqual(second.returncode, 1)
        self.assertIn("already recorded unavailable", second.stderr)
        self.assertFalse((second_output / "worker-primary.stdout").exists())
        self.assertFalse((second_output / "worker-fallback.stdout").exists())

    def test_known_unavailable_fallback_is_skipped_after_one_preferred_start(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        state_path = Path(temporary.name) / "fallback-known.json"
        self.write_availability_state(
            state_path,
            "run-fallback-known",
            [{"model": "gpt-5.6-luna", "reason": "rate_limit"}],
        )
        output_dir = Path(temporary.name) / "fallback-known-output"
        result = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=output_dir,
            extra_args=(
                "--availability-state",
                str(state_path),
                "--orchestration-run-id",
                "run-fallback-known",
            ),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("already recorded unavailable", result.stderr)
        self.assertTrue((output_dir / "worker-primary.stdout").is_file())
        self.assertFalse((output_dir / "worker-fallback.stdout").exists())
        entries = json.loads(state_path.read_text(encoding="utf-8"))["unavailable_models"]
        self.assertEqual({entry["model"] for entry in entries}, {"gpt-5.3-codex-spark", "gpt-5.6-luna"})

    def test_availability_state_schema_identity_and_size_bounds_fail_closed(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        cases: list[tuple[str, object, str]] = [
            ("schema", {"schema_version": 2, "orchestration_run_id": "run", "unavailable_models": []}, "schema version"),
            ("shape", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [], "extra": True}, "field shape"),
            ("entries-type", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": {}}, "must be a list"),
            ("duplicates", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m", "reason": "usage_limit"}, {"model": "m", "reason": "rate_limit"}]}, "duplicate model"),
            ("entry-shape", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m", "reason": "usage_limit", "raw": "secret"}]}, "field shape"),
            ("reason", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m", "reason": "validation"}]}, "availability code"),
            ("model-bound", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m" * 129, "reason": "usage_limit"}]}, "byte bound"),
            ("count-bound", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": f"m-{index}", "reason": "usage_limit"} for index in range(17)]}, "entry-count"),
        ]
        for label, payload, message in cases:
            with self.subTest(case=label):
                path = root / f"invalid-{label}.json"
                path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(RUNNER.RunnerError, message):
                    RUNNER.open_availability_state(repo, str(path), "run")

        oversized = root / "oversized.json"
        oversized.write_bytes(b"x" * (RUNNER.AVAILABILITY_STATE_MAX_BYTES + 1))
        with self.assertRaisesRegex(RUNNER.RunnerError, "byte bound"):
            RUNNER.open_availability_state(repo, str(oversized), "run")
        valid = root / "different-run.json"
        self.write_availability_state(valid, "run-a", [])
        with self.assertRaisesRegex(RUNNER.RunnerError, "different orchestration run"):
            RUNNER.open_availability_state(repo, str(valid), "run-b")
        for run_id in ("", "   ", "r" * 129):
            with self.subTest(run_id=run_id):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.open_availability_state(repo, str(root / "missing.json"), run_id)

    def test_availability_state_rejects_symlinks_and_target_swap(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        real = root / "real.json"
        self.write_availability_state(real, "run", [])
        target_link = root / "target-link.json"
        target_link.symlink_to(real)
        with self.assertRaisesRegex(RUNNER.RunnerError, "symlink"):
            RUNNER.open_availability_state(repo, str(target_link), "run")
        real_parent = root / "real-parent"
        real_parent.mkdir()
        ancestor_link = root / "ancestor-link"
        ancestor_link.symlink_to(real_parent, target_is_directory=True)
        with self.assertRaisesRegex(RUNNER.RunnerError, "ancestor"):
            RUNNER.open_availability_state(repo, str(ancestor_link / "state.json"), "run")
        with self.assertRaisesRegex(RUNNER.RunnerError, "outside"):
            RUNNER.open_availability_state(repo, str(repo / "state.json"), "run")

        swapped = root / "swapped.json"
        self.write_availability_state(swapped, "run", [])
        with RUNNER.open_availability_state(repo, str(swapped), "run") as state:
            swapped.unlink()
            swapped.write_text("attacker\n", encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.RunnerError, "target changed"):
                state.record("model-a", "usage_limit")
        self.assertEqual(swapped.read_text(encoding="utf-8"), "attacker\n")

    def test_availability_state_parent_fd_does_not_follow_parent_swap(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        parent = root / "state-parent"
        parent.mkdir()
        moved_parent = root / "state-parent-original"
        attacker = root / "attacker"
        attacker.mkdir()
        with RUNNER.open_availability_state(repo, str(parent / "state.json"), "run-parent") as state:
            parent.rename(moved_parent)
            parent.symlink_to(attacker, target_is_directory=True)
            state.record("model-a", "usage_limit")
        self.assertTrue((moved_parent / "state.json").is_file())
        self.assertFalse((attacker / "state.json").exists())

    def test_telemetry_duration_bounds_are_finite_and_nonnegative(self) -> None:
        self.assertEqual(RUNNER.bounded_duration(4.0, 4.0), 0.0)
        self.assertEqual(RUNNER.bounded_duration(1.0, 2.5), 1.5)
        for started, finished in (
            (2.0, 1.0),
            (0.0, math.inf),
            (0.0, math.nan),
            (0.0, RUNNER.TELEMETRY_MAX_DURATION_SECONDS + 1),
        ):
            with self.subTest(started=started, finished=finished):
                with self.assertRaisesRegex(RUNNER.RunnerError, "finite nonnegative"):
                    RUNNER.bounded_duration(started, finished)

    def test_availability_state_path_and_run_identifier_must_be_paired(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_root = Path(temporary.name)
        cases = (("--availability-state", str(output_root / "state.json")),)
        for index, extra_args in enumerate(cases):
            with self.subTest(extra_args=extra_args):
                worker = output_root / f"paired-worker-{index}.py"
                write_worker(
                    worker,
                    '(worker_repo / "allowed.txt").write_text("must-not-run\\n", encoding="utf-8")',
                )
                command = [
                    "run",
                    plan_path,
                    "--output-dir",
                    str(output_root / f"pair-cli-{index}"),
                    "--worker-binary",
                    sys.executable,
                    "--worker-arg",
                    str(worker),
                    *extra_args,
                ]
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        *command,
                        "--lifecycle-state",
                        str(output_root / "lifecycle.json"),
                    ],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("orchestration-run-id", result.stderr)
                self.assertFalse((output_root / f"pair-cli-{index}" / "candidate.patch").exists())

    def test_correction_emits_verified_aggregate_patch_without_mutating_source_or_objects(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial_output = root / "initial-output"
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial candidate\\n", encoding="utf-8")',
            output_dir=initial_output,
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        prior_manifest = Path(initial.stdout.strip())
        prior_manifest_digest = RUNNER.hash_file(prior_manifest)
        prior_patch_digest = RUNNER.hash_file(initial_output / "candidate.patch")
        brief = root / "correction.txt"
        brief.write_text("Replace the candidate marker with the corrected marker.\n", encoding="utf-8")
        before_objects = object_database_snapshot(repo)
        correction_output = root / "correction-output"
        correction = self.run_correction_with_worker(
            repo,
            plan_path,
            prior_manifest,
            brief,
            textwrap.dedent(
                """\
                brief = Path(os.environ[prefix + "CORRECTION_BRIEF"])
                if brief.read_text(encoding="utf-8") != "Replace the candidate marker with the corrected marker.\\n":
                    raise SystemExit("correction brief mismatch")
                try:
                    brief.write_text("tamper\\n", encoding="utf-8")
                except OSError:
                    pass
                else:
                    raise SystemExit("correction brief was writable")
                if (worker_repo / "allowed.txt").read_text(encoding="utf-8") != "initial candidate\\n":
                    raise SystemExit("verified prior patch was not applied")
                forbidden = Path(os.environ["FORBIDDEN_PRIOR"])
                if forbidden.exists():
                    raise SystemExit("prior attempt state is visible")
                (worker_repo / "allowed.txt").write_text("corrected candidate\\n", encoding="utf-8")
                """
            ),
            output_dir=correction_output,
            worker_env={"FORBIDDEN_PRIOR": str(initial_output / "worker.stdout")},
        )
        self.assertEqual(correction.returncode, 0, correction.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        self.assertEqual(object_database_snapshot(repo), before_objects)
        manifest_path = Path(correction.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])
        self.assertEqual(
            manifest["correction_lineage"],
            {
                "prior_manifest_digest": prior_manifest_digest,
                "prior_patch_digest": prior_patch_digest,
                "correction_round": 1,
                "correction_brief_digest": RUNNER.hash_file(brief),
            },
        )
        self.assertNotIn("Replace the candidate", json.dumps(manifest))
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "corrected candidate\n")

    def test_correction_lineage_allows_two_rounds_and_rejects_third(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("round zero\\n", encoding="utf-8")',
            output_dir=root / "round-zero",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        prior = Path(initial.stdout.strip())
        for round_number in (1, 2):
            brief = root / f"brief-{round_number}.txt"
            brief.write_text(f"Correction round {round_number}.\n", encoding="utf-8")
            result = self.run_correction_with_worker(
                repo,
                plan_path,
                prior,
                brief,
                f'(worker_repo / "allowed.txt").write_text("round {round_number}\\n", encoding="utf-8")',
                output_dir=root / f"round-{round_number}",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            prior = Path(result.stdout.strip())
            manifest = json.loads(prior.read_text(encoding="utf-8"))
            self.assertEqual(manifest["correction_lineage"]["correction_round"], round_number)
        third_brief = root / "brief-3.txt"
        third_brief.write_text("Third correction must be refused.\n", encoding="utf-8")
        third = self.run_correction_with_worker(
            repo,
            plan_path,
            prior,
            third_brief,
            '(worker_repo / "allowed.txt").write_text("round 3\\n", encoding="utf-8")',
            output_dir=root / "round-3",
        )
        self.assertEqual(third.returncode, 1)
        self.assertIn("budget exhausted", third.stderr)
        self.assertFalse((root / "round-3" / "worker.stdout").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_correction_rejects_tampered_prior_manifest_and_brief_boundaries(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "tamper-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        original_manifest = json.loads(Path(initial.stdout.strip()).read_text(encoding="utf-8"))
        brief = root / "brief.txt"
        brief.write_text("Correct it.\n", encoding="utf-8")
        cases = {
            "head": ("source_head", "0" * 40, "source HEAD"),
            "plan": ("plan_digest", "0" * 64, "plan digest"),
            "scope": ("allowed_write_scope", ["other.txt"], "write scope"),
            "patch": ("patch_digest", "0" * 64, "patch digest"),
            "paths": ("changed_paths", ["other.txt"], "changed paths"),
            "schema": ("schema_version", 999, "schema version"),
        }
        for index, (label, (key, value, message)) in enumerate(cases.items()):
            with self.subTest(case=label):
                manifest = dict(original_manifest)
                manifest[key] = value
                path = root / f"tampered-{label}.json"
                path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
                result = self.run_correction_with_worker(
                    repo,
                    plan_path,
                    path,
                    brief,
                    '(worker_repo / "allowed.txt").write_text("must not run\\n", encoding="utf-8")',
                    output_dir=root / f"tampered-output-{index}",
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        lineage_manifest = dict(original_manifest)
        lineage_manifest["correction_lineage"] = {
            "prior_manifest_digest": "0" * 64,
            "prior_patch_digest": "0" * 64,
            "correction_round": 0,
            "correction_brief_digest": "0" * 64,
        }
        lineage_path = root / "bad-lineage.json"
        lineage_path.write_text(json.dumps(lineage_manifest) + "\n", encoding="utf-8")
        lineage = self.run_correction_with_worker(
            repo,
            plan_path,
            lineage_path,
            brief,
            "pass",
            output_dir=root / "bad-lineage-output",
        )
        self.assertEqual(lineage.returncode, 1)
        self.assertIn("invalid correction round", lineage.stderr)

        oversized = root / "oversized-brief.txt"
        oversized.write_bytes(b"x" * (RUNNER.CORRECTION_BRIEF_MAX_BYTES + 1))
        too_large = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            oversized,
            "pass",
            output_dir=root / "oversized-brief-output",
        )
        self.assertEqual(too_large.returncode, 1)
        self.assertIn("byte bound", too_large.stderr)
        brief_link = root / "brief-link.txt"
        brief_link.symlink_to(brief)
        linked = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief_link,
            "pass",
            output_dir=root / "linked-brief-output",
        )
        self.assertEqual(linked.returncode, 1)
        self.assertIn("symlink", linked.stderr)

    def test_correction_failure_leaves_no_candidate_and_keeps_source_clean(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "failure-initial",
        )
        brief = root / "failure-brief.txt"
        brief.write_text("Fail safely.\n", encoding="utf-8")
        output = root / "failure-output"
        failed = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            "raise SystemExit(7)",
            output_dir=output,
        )
        self.assertEqual(failed.returncode, 1)
        self.assertIn("correction worker exited with 7", failed.stderr)
        self.assertFalse((output / "candidate.patch").exists())
        self.assertFalse((output / "manifest.json").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_correction_reuses_same_run_availability_and_only_falls_back_for_availability(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial candidate\\n", encoding="utf-8")',
            output_dir=root / "availability-correction-initial",
            extra_args=("--orchestration-run-id", "same-correction-run"),
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        prior = Path(initial.stdout.strip())
        brief = root / "availability-correction-brief.txt"
        brief.write_text("Correct the candidate.\n", encoding="utf-8")
        state = root / "correction-state.json"
        common = (
            "--availability-state",
            str(state),
            "--orchestration-run-id",
            "same-correction-run",
        )
        first = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            prior,
            brief,
            "unavailable_then_success",
            output_dir=root / "correction-availability-first",
            extra_args=common,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        first_manifest = json.loads(Path(first.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(first_manifest["telemetry"]["model_starts"], 2)
        self.assertEqual(first_manifest["telemetry"]["availability_failures"], 1)

        second = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            Path(first.stdout.strip()),
            brief,
            "unavailable_then_success",
            output_dir=root / "correction-availability-second",
            extra_args=common,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        second_manifest = json.loads(Path(second.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(second_manifest["telemetry"]["model_starts"], 1)
        self.assertEqual(second_manifest["telemetry"]["skipped_known_unavailable_starts"], 1)
        self.assertEqual(
            [attempt["label"] for attempt in second_manifest["worker_result"]["attempts"]],
            ["fallback"],
        )

        mismatched = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            prior,
            brief,
            "primary_success",
            output_dir=root / "correction-run-mismatch",
            extra_args=(
                "--availability-state",
                str(state),
                "--orchestration-run-id",
                "different-run",
            ),
        )
        self.assertEqual(mismatched.returncode, 1)
        self.assertIn("run identifier differs", mismatched.stderr)

        semantic = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            prior,
            brief,
            "nonavailability_failure",
            output_dir=root / "correction-semantic-failure",
        )
        self.assertEqual(semantic.returncode, 1)
        self.assertIn("current lifecycle leaf", semantic.stderr)
        self.assertFalse((root / "correction-semantic-failure" / "worker-fallback.stdout").exists())

    def test_correction_sandbox_denies_source_out_of_scope_and_git_metadata_writes(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial candidate\\n", encoding="utf-8")',
            output_dir=root / "denial-initial",
        )
        brief = root / "denial-brief.txt"
        brief.write_text("Verify correction sandbox denials.\n", encoding="utf-8")
        correction = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            textwrap.dedent(
                """\
                denied = []
                for target, label in (
                    (source_repo / "blocked.txt", "source"),
                    (worker_repo / "outside-scope.txt", "scope"),
                    (worker_repo / ".git" / "refs" / "heads" / "evil", "git"),
                ):
                    try:
                        target.write_text("blocked\\n", encoding="utf-8")
                    except OSError:
                        denied.append(label)
                    else:
                        raise SystemExit(f"unexpected write success: {label}")
                if denied != ["source", "scope", "git"]:
                    raise SystemExit(f"unexpected denial set: {denied}")
                (worker_repo / "allowed.txt").write_text("safe correction\\n", encoding="utf-8")
                """
            ),
            output_dir=root / "denial-correction",
        )
        self.assertEqual(correction.returncode, 0, correction.stderr)
        self.assertFalse((repo / "blocked.txt").exists())
        self.assertFalse((repo / "outside-scope.txt").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_parent_authorized_focused_and_authoritative_validation_use_fresh_clone(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            validation=["git diff --check"],
            focused_validation=["git diff --check"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate for validation\\n", encoding="utf-8")',
            output_dir=root / "validation-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest = Path(initial.stdout.strip())
        for suite, focused_count, authoritative_count in (
            ("focused", 1, 0),
            ("authoritative", 1, 1),
        ):
            with self.subTest(suite=suite):
                output = root / f"validation-{suite}"
                result = run_cli(
                    repo,
                    "validate",
                    str(manifest),
                    "--suite",
                    suite,
                    "--parent-diff-approved",
                    "--critical-invariants-approved",
                    "--output-dir",
                    str(output),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
                self.assertTrue(report["passed"])
                self.assertEqual(report["suite"], suite)
                self.assertEqual(len(report["commands"]), 1)
                self.assertEqual(report["commands"][0]["argv"], ["git", "diff", "--check"])
                self.assertEqual(report["telemetry"]["focused_validation_count"], focused_count)
                self.assertEqual(report["telemetry"]["authoritative_validation_count"], authoritative_count)
                self.assertEqual(report["telemetry"]["full_validation_count"], authoritative_count)
                self.assertNotIn("candidate for validation", json.dumps(report))
                self.assertGreaterEqual(report["telemetry"]["duration_seconds"], 0)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def write_npm_dependency_tree(self, repo: Path) -> None:
        package_record = {
            "version": "1.0.0",
            "dev": True,
            "bin": {"verify-tool": "bin/verify-tool"},
        }
        package_lock = {
            "name": "dependency-snapshot-fixture",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {
                "": {
                    "name": "dependency-snapshot-fixture",
                    "version": "1.0.0",
                    "devDependencies": {"verify-tool": "1.0.0"},
                },
                "node_modules/verify-tool": package_record,
            },
        }
        hidden_lock = {
            "name": "dependency-snapshot-fixture",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {"node_modules/verify-tool": package_record},
        }
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "dependency-snapshot-fixture",
                    "version": "1.0.0",
                    "private": True,
                    "scripts": {"verify": "verify-tool"},
                    "devDependencies": {"verify-tool": "1.0.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (repo / "package-lock.json").write_text(
            json.dumps(package_lock, indent=2) + "\n", encoding="utf-8"
        )
        git(repo, "add", "package.json", "package-lock.json")
        git(repo, "commit", "-qm", "add npm validation fixture")
        dependency = repo / "node_modules/verify-tool"
        (dependency / "bin").mkdir(parents=True)
        (repo / "node_modules/.package-lock.json").write_text(
            json.dumps(hidden_lock, indent=2) + "\n", encoding="utf-8"
        )
        (dependency / "package.json").write_text(
            json.dumps(
                {
                    "name": "verify-tool",
                    "version": "1.0.0",
                    "bin": {"verify-tool": "bin/verify-tool"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        executable = dependency / "bin/verify-tool"
        executable.write_text(
            '''#!/bin/sh
if touch "$(dirname "$0")/unexpected-write" 2>/dev/null; then
  echo "dependency snapshot was writable" >&2
  exit 9
fi
echo dependency-snapshot-verified
''',
            encoding="utf-8",
        )
        executable.chmod(0o755)
        binary_dir = repo / "node_modules/.bin"
        binary_dir.mkdir()
        (binary_dir / "verify-tool").symlink_to("../verify-tool/bin/verify-tool")

    def install_npm_workerd_hardlink_tree(self, repo: Path) -> tuple[Path, Path]:
        platform_package = repo / "fixtures/workerd-linux-64"
        wrapper_package = repo / "fixtures/workerd"
        (platform_package / "bin").mkdir(parents=True)
        (wrapper_package / "bin").mkdir(parents=True)
        (platform_package / "package.json").write_text(
            json.dumps(
                {
                    "name": "@cloudflare/workerd-linux-64",
                    "version": "1.0.0",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (platform_package / "bin/workerd").write_text(
            "workerd fixture\n", encoding="utf-8"
        )
        (wrapper_package / "package.json").write_text(
            json.dumps(
                {
                    "name": "workerd",
                    "version": "1.0.0",
                    "scripts": {"postinstall": "node postinstall.js"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (wrapper_package / "bin/workerd").write_text(
            "replaced during npm ci\n", encoding="utf-8"
        )
        (wrapper_package / "postinstall.js").write_text(
            """const fs = require("node:fs");
const path = require("node:path");
const source = path.join(__dirname, "..", "@cloudflare", "workerd-linux-64", "bin", "workerd");
const target = path.join(__dirname, "bin", "workerd");
fs.rmSync(target, { force: true });
fs.linkSync(source, target);
""",
            encoding="utf-8",
        )
        npm_environment = dict(os.environ)
        npm_environment.update(
            {
                "npm_config_audit": "false",
                "npm_config_cache": str(repo.parent / "npm-cache"),
                "npm_config_fund": "false",
                "npm_config_update_notifier": "false",
            }
        )

        def pack(source: Path) -> str:
            packed = subprocess.run(
                [
                    "npm",
                    "pack",
                    "--ignore-scripts",
                    "--pack-destination",
                    str(repo / "fixtures"),
                ],
                cwd=source,
                env=npm_environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(packed.returncode, 0, packed.stderr)
            return packed.stdout.strip().splitlines()[-1]

        platform_archive = pack(platform_package)
        wrapper_archive = pack(wrapper_package)
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "workerd-hardlink-fixture",
                    "version": "1.0.0",
                    "private": True,
                    "dependencies": {
                        "@cloudflare/workerd-linux-64": f"file:fixtures/{platform_archive}",
                        "workerd": f"file:fixtures/{wrapper_archive}",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        lock = subprocess.run(
            ["npm", "install", "--package-lock-only", "--ignore-scripts", "--offline"],
            cwd=repo,
            env=npm_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(lock.returncode, 0, lock.stderr)
        git(repo, "add", "package.json", "package-lock.json", "fixtures")
        git(repo, "commit", "-qm", "add npm ci Workerd hard-link fixture")
        installed = subprocess.run(
            ["npm", "ci", "--offline"],
            cwd=repo,
            env=npm_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stderr)
        return (
            repo / "node_modules/@cloudflare/workerd-linux-64/bin/workerd",
            repo / "node_modules/workerd/bin/workerd",
        )

    def test_prepare_dependencies_breaks_npm_workerd_hardlinks(self) -> None:
        if shutil.which("npm") is None:
            if os.environ.get("REQUIRE_NPM") == "1":
                self.fail("npm is required for the Workerd hard-link regression")
            self.skipTest("npm is unavailable")
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        platform_binary, wrapper_binary = self.install_npm_workerd_hardlink_tree(repo)
        self.assertTrue(os.path.samefile(platform_binary, wrapper_binary))
        self.assertEqual(platform_binary.stat().st_nlink, 2)
        with self.assertRaisesRegex(RUNNER.RunnerError, "hard-linked file"):
            RUNNER.digest_tree(repo / "node_modules")

        prepared = run_cli(
            repo,
            "prepare-dependencies",
            "--output-dir",
            str(root / "dependency-snapshot"),
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        snapshot_root = Path(prepared.stdout.strip()).parent / "node_modules"
        copied_platform = snapshot_root / "@cloudflare/workerd-linux-64/bin/workerd"
        copied_wrapper = snapshot_root / "workerd/bin/workerd"
        self.assertFalse(os.path.samefile(copied_platform, copied_wrapper))
        self.assertEqual(copied_platform.stat().st_nlink, 1)
        self.assertEqual(copied_wrapper.stat().st_nlink, 1)
        self.assertEqual(copied_platform.read_bytes(), platform_binary.read_bytes())
        self.assertEqual(copied_wrapper.read_bytes(), wrapper_binary.read_bytes())
        RUNNER.verify_dependency_snapshot(repo, Path(prepared.stdout.strip()))

    def test_source_tree_metadata_fingerprint_detects_restored_hardlink_count(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        self.write_npm_dependency_tree(repo)
        dependency_tree = repo / "node_modules"
        executable = dependency_tree / "verify-tool/bin/verify-tool"
        before = RUNNER.source_tree_metadata_fingerprint(dependency_tree)
        external_link = Path(temporary.name) / "temporary-hardlink"
        os.link(executable, external_link)
        external_link.unlink()
        after = RUNNER.source_tree_metadata_fingerprint(dependency_tree)
        self.assertNotEqual(before, after)

    def test_npm_validation_uses_a_lock_bound_read_only_snapshot_in_a_fresh_clone(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"},
            validation=["npm run verify"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        snapshot_dir = root / "dependency-snapshot"
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(snapshot_dir))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        snapshot_manifest = Path(prepared.stdout.strip())
        snapshot = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["package_manager"], "npm")
        self.assertRegex(snapshot["tree_sha256"], r"^[0-9a-f]{64}$")

        shutil.rmtree(repo / "node_modules")
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "npm-validation-initial",
        )
        worker_detail = root / "npm-validation-initial/worker.stderr"
        self.assertEqual(
            initial.returncode,
            0,
            initial.stderr
            + (worker_detail.read_text(encoding="utf-8") if worker_detail.is_file() else ""),
        )
        result = run_cli(
            repo,
            "validate",
            initial.stdout.strip(),
            "--suite",
            "authoritative",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "npm-validation-output"),
            "--dependency-snapshot",
            str(snapshot_manifest),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(report["commands"][0]["argv"], ["npm", "run", "verify"])
        self.assertEqual(report["dependency_snapshot"]["tree_sha256"], snapshot["tree_sha256"])
        self.assertFalse((repo / "node_modules").exists())

    def test_dependency_snapshot_rejects_tree_and_lockfile_tampering(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot"))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = Path(prepared.stdout.strip())
        (manifest.parent / "node_modules/verify-tool/bin/verify-tool").write_text(
            "#!/bin/sh\necho tampered\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RUNNER.RunnerError, "tree digest"):
            RUNNER.verify_dependency_snapshot(repo, manifest)

        shutil.rmtree(manifest.parent)
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot-two"))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = Path(prepared.stdout.strip())
        (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(RUNNER.RunnerError, "package-lock.json digest"):
            RUNNER.verify_dependency_snapshot(repo, manifest)

    def test_dependency_snapshot_rejects_reused_output_hardlinks_and_path_swap(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)

        existing = root / "existing-output"
        existing.mkdir()
        rejected = run_cli(repo, "prepare-dependencies", "--output-dir", str(existing))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("must not already exist", rejected.stderr)

        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot"))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = Path(prepared.stdout.strip())
        manifest_link = root / "manifest-hardlink.json"
        os.link(manifest, manifest_link)
        with self.assertRaisesRegex(RUNNER.RunnerError, "regular file"):
            RUNNER.verify_dependency_snapshot(repo, manifest)
        manifest_link.unlink()

        snapshot = RUNNER.verify_dependency_snapshot(repo, manifest)
        original_tree = manifest.parent / "node_modules"
        moved_tree = manifest.parent / "verified-before-swap"
        original_tree.rename(moved_tree)
        shutil.copytree(moved_tree, original_tree, symlinks=True)
        (original_tree / "verify-tool/bin/verify-tool").write_text(
            "#!/bin/sh\necho path-swapped\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RUNNER.RunnerError, "verified tree digest"):
            RUNNER.materialize_verified_dependency_tree(
                repo, snapshot, root / "private-dependency-copy"
            )

    def test_dependency_snapshot_rejects_a_symlink_that_escapes_node_modules(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        (repo / "node_modules/.bin/escape").symlink_to("../../outside-node-modules")
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot"))
        self.assertEqual(prepared.returncode, 1)
        self.assertIn("symlink escapes node_modules", prepared.stderr)
        self.assertFalse((root / "snapshot").exists())

    def test_focused_validation_absence_is_compatible_and_requires_parent_approvals(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"], validation=["git diff --check"]
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "optional-focused-initial",
        )
        manifest = Path(initial.stdout.strip())
        denied = run_cli(
            repo,
            "validate",
            str(manifest),
            "--suite",
            "focused",
            "--output-dir",
            str(root / "approval-denied"),
        )
        self.assertEqual(denied.returncode, 1)
        self.assertIn("explicit parent diff", denied.stderr)
        approved = run_cli(
            repo,
            "validate",
            str(manifest),
            "--suite",
            "focused",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "optional-focused-approved"),
        )
        self.assertEqual(approved.returncode, 1)
        self.assertIn("no focused validation stage", approved.stderr)

    def test_validation_rejects_candidate_modified_plan_and_records_bounded_failure(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt", "docs/plan/"],
            validation=["git diff --check"],
            focused_validation=["python3 -m pytest tests/missing-focused.py"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        modified_plan, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                plan = worker_repo / plan_path
                plan.write_text(plan.read_text(encoding="utf-8") + "\\nworker change\\n", encoding="utf-8")
                """
            ),
            output_dir=root / "modified-plan-candidate",
        )
        self.assertEqual(modified_plan.returncode, 0, modified_plan.stderr)
        rejected = run_cli(
            repo,
            "validate",
            modified_plan.stdout.strip(),
            "--suite",
            "focused",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "modified-plan-validation"),
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("must not change the active plan", rejected.stderr)

        failing, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("failing validation candidate\\n", encoding="utf-8")',
            output_dir=root / "failing-validation-candidate",
        )
        failure_output = root / "failing-validation-report"
        failed = run_cli(
            repo,
            "validate",
            failing.stdout.strip(),
            "--suite",
            "focused",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(failure_output),
        )
        self.assertEqual(failed.returncode, 1)
        self.assertIn("bounded report saved", failed.stderr)
        report = json.loads((failure_output / "validation.json").read_text(encoding="utf-8"))
        self.assertFalse(report["passed"])
        self.assertNotEqual(report["commands"][0]["returncode"], 0)
        self.assertNotIn("stdout_body", report["commands"][0])
        self.assertNotIn("stderr_body", report["commands"][0])
        self.assertIn("stdout_digest", report["commands"][0])
        self.assertIn("stderr_digest", report["commands"][0])
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_nonavailability_failure_and_disabled_fallback_do_not_retry(self) -> None:
        for scenario, extra_args in (
            ("nonavailability_failure", ()),
            ("unavailable_then_success", ("--no-model-fallback",)),
        ):
            with self.subTest(scenario=scenario, extra_args=extra_args):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"])
                self.addCleanup(temporary.cleanup)
                output_dir = Path(temporary.name) / f"no-fallback-{scenario}"
                result = self.run_with_fake_codex(
                    repo,
                    plan_path,
                    scenario,
                    output_dir=output_dir,
                    extra_args=extra_args,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("worker exited", result.stderr)
                self.assertFalse((output_dir / "worker-fallback.stdout").exists())
                self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_fallback_failure_stops_without_candidate_and_cli_overrides_are_honored(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "failed-fallback-output"
        result = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_failure",
            output_dir=output_dir,
            extra_args=(
                "--codex-model",
                "preferred-override",
                "--codex-reasoning-effort",
                "high",
                "--fallback-codex-model",
                "fallback-override",
                "--fallback-codex-reasoning-effort",
                "xhigh",
            ),
            fake_env={
                "FAKE_PRIMARY_MODEL": "preferred-override",
                "FAKE_PRIMARY_REASONING": "high",
                "FAKE_FALLBACK_MODEL": "fallback-override",
                "FAKE_FALLBACK_REASONING": "xhigh",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("fallback worker exited with 2", result.stderr)
        self.assertTrue((output_dir / "worker-primary.stderr").is_file())
        self.assertTrue((output_dir / "worker-fallback.stderr").is_file())
        self.assertFalse((output_dir / "candidate.patch").exists())
        self.assertFalse((output_dir / "manifest.json").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

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
        self.assertIn("worker exited", result.stderr)

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
        self.assertIn("worker exited", result.stderr)

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
        temporary, repo, plan_path = self.make_repo(["probe.txt"], {"probe.txt": "original\\n"})
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
                subprocess.run(["git", "config", "--global", "filter.leak.clean", str(filter_script)], cwd=worker_repo, check=True)
                attributes = Path(os.environ["HOME"]) / "global-attributes"
                attributes.write_text("allowed.txt filter=leak\\n", encoding="utf-8")
                subprocess.run(["git", "config", "--global", "core.attributesfile", str(attributes)], cwd=worker_repo, check=True)
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

    def test_exact_scope_denies_all_unscoped_mutations_during_worker_execution(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"], {"allowed.txt": "original\n", "outside.txt": "outside\n"}
        )
        self.addCleanup(temporary.cleanup)
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                denied = []
                targets = (
                    (worker_repo / "outside.txt", lambda p: p.write_text("changed\\n", encoding="utf-8")),
                    (worker_repo / "created.txt", lambda p: p.write_text("created\\n", encoding="utf-8")),
                    (worker_repo / "outside.txt", lambda p: p.unlink()),
                    (worker_repo / "outside.txt", lambda p: p.chmod(0o755)),
                    (worker_repo / "outside.txt", lambda p: p.rename(worker_repo / "renamed.txt")),
                )
                for target, operation in targets:
                    try:
                        operation(target)
                    except OSError:
                        denied.append(target.name)
                    else:
                        raise SystemExit("unscoped mutation unexpectedly succeeded")
                if len(denied) != 5:
                    raise SystemExit(f"unexpected denied operations: {denied}")
                (worker_repo / "allowed.txt").write_text("allowed\\n", encoding="utf-8")
                """
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])

    def test_exact_scope_rejects_removal_and_atomic_replacement(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                replacement = scratch_dir / "replacement.txt"
                replacement.write_text("replacement\\n", encoding="utf-8")
                for operation in (
                    lambda: (worker_repo / "allowed.txt").unlink(),
                    lambda: replacement.replace(worker_repo / "allowed.txt"),
                ):
                    try:
                        operation()
                    except OSError:
                        pass
                    else:
                        raise SystemExit("exact-file replacement unexpectedly succeeded")
                (worker_repo / "allowed.txt").write_text("updated\\n", encoding="utf-8")
                """
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prefix_scope_materializes_creates_modifications_and_deletions_only_below_prefix(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["dir/"], {"allowed.txt": "sibling\n", "dir/keep.txt": "before\n", "dir/remove.txt": "remove\n"}
        )
        self.addCleanup(temporary.cleanup)
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "dir" / "keep.txt").write_text("after\\n", encoding="utf-8")
                (worker_repo / "dir" / "remove.txt").unlink()
                (worker_repo / "dir" / "new.txt").write_text("new\\n", encoding="utf-8")
                try:
                    (worker_repo / "allowed.txt").write_text("blocked\\n", encoding="utf-8")
                except OSError:
                    pass
                else:
                    raise SystemExit("sibling write unexpectedly succeeded")
                """
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["dir/keep.txt", "dir/new.txt", "dir/remove.txt"])
        apply = run_cli(repo, "apply", result.stdout.strip())
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "dir" / "keep.txt").read_text(encoding="utf-8"), "after\n")
        self.assertEqual((repo / "dir" / "new.txt").read_text(encoding="utf-8"), "new\n")
        self.assertFalse((repo / "dir" / "remove.txt").exists())

    def test_shadow_setup_rejects_invalid_exact_targets_and_symlink_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clone = root / "clone"
            scratch = root / "scratch"
            clone.mkdir()
            scratch.mkdir()
            (clone / "directory").mkdir()
            (clone / "regular.txt").write_text("regular\n", encoding="utf-8")
            (clone / "link.txt").symlink_to("regular.txt")
            (clone / "linked-parent").symlink_to(root)
            for scope, expected in (
                (["directory"], "existing regular file"),
                (["link.txt"], "path resolves through a symlink"),
                (["linked-parent/new/"], "path resolves through a symlink"),
            ):
                with self.subTest(scope=scope):
                    with self.assertRaisesRegex(RUNNER.RunnerError, expected):
                        RUNNER.prepare_writable_shadows(clone_dir=clone, scratch_dir=scratch, scope_entries=scope)
            self.assertFalse((root / "new").exists())

    def test_prefix_shadow_copy_preserves_contained_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clone = root / "clone"
            scratch = root / "scratch"
            (clone / "dir").mkdir(parents=True)
            scratch.mkdir()
            (clone / "dir" / "target.txt").write_text("target\n", encoding="utf-8")
            (clone / "dir" / "inside-link").symlink_to("target.txt")
            shadows = RUNNER.prepare_writable_shadows(clone_dir=clone, scratch_dir=scratch, scope_entries=["dir/"])
            self.assertTrue((shadows[0][0] / "inside-link").is_symlink())

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

    def test_apply_requires_digest_bound_authoritative_lifecycle_receipt(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "lifecycle-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        execution_state = str(
            Path(manifest["lifecycle_state_path"]).with_name(
                Path(manifest["lifecycle_state_path"]).name
                + f".{manifest['orchestration_run_id']}.plan-execution.json"
            )
        )
        direct = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "apply",
                str(manifest_path),
                "--lifecycle-state",
                manifest["lifecycle_state_path"],
                "--orchestration-run-id",
                manifest["orchestration_run_id"],
                "--plan-execution-state",
                execution_state,
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(direct.returncode, 1)
        self.assertIn("authoritative validation", direct.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_validation_rejects_candidate_owned_authority_paths(self) -> None:
        temporary, repo, plan_path = self.make_repo(["tests/"], files={"tests/original.py": "pass\n"})
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "tests" / "original.py").write_text("raise SystemExit(0)\\n", encoding="utf-8")',
            output_dir=root / "authority-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        rejected = run_cli(
            repo,
            "validate",
            initial.stdout.strip(),
            "--suite",
            "authoritative",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "authority-validation"),
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("validation authority", rejected.stderr)

    def test_validation_authority_classifier_covers_indirect_and_generated_paths(self) -> None:
        for path in (
            ".project-agent-workflow/scripts/validate-changes.py",
            "template/app/tests/check.py",
            "nested/conftest.py",
            "src/widget.test.ts",
            "pytest.ini",
            "Cargo.toml",
            "webpack.config.js",
            "tsconfig.build.json",
            "build.rs",
            "packages/app/package.json",
            "packages/app/pyproject.toml",
            "packages/app/pnpm-lock.yaml",
        ):
            with self.subTest(path=path):
                self.assertTrue(RUNNER.is_validation_authority_path(path))
        self.assertFalse(RUNNER.is_validation_authority_path("src/widget.ts"))

    def test_validation_rejects_nested_workspace_manifest_bypass(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["packages/"],
            files={
                "package.json": '{"scripts":{"test":"npm --prefix packages/app test"}}\n',
                "packages/app/package.json": '{"scripts":{"test":"exit 1"}}\n',
            },
            validation=["npm run test"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "packages" / "app" / "package.json").write_text(\'{"scripts":{"test":"exit 0"}}\\n\', encoding="utf-8")',
            output_dir=root / "workspace-authority-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        rejected = run_cli(
            repo, "validate", initial.stdout.strip(), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "workspace-authority-validation"),
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("validation authority", rejected.stderr)

    def test_plan_declared_validation_authority_rejects_transitive_harness(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["tools/"],
            files={
                "package.json": '{"scripts":{"test":"node tools/harness.js"}}\n',
                "tools/harness.js": "process.exit(1)\n",
            },
            validation=["npm run test"],
            validation_authority_scope=["tools/"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "tools" / "harness.js").write_text("process.exit(0)\\n", encoding="utf-8")',
            output_dir=root / "declared-authority-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        rejected = run_cli(
            repo, "validate", initial.stdout.strip(), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "declared-authority-validation"),
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("validation authority", rejected.stderr)

    def test_manifest_operations_reject_execution_ledger_for_another_plan(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        other_plan = "docs/plan/active/002-other.md"
        (repo / other_plan).write_text(
            (repo / plan_path).read_text(encoding="utf-8").replace(
                "# Sandboxed worker test", "# Other plan"
            ),
            encoding="utf-8",
        )
        with (repo / "docs/plan/plan.md").open("a", encoding="utf-8") as handle:
            handle.write(f"002\t{other_plan}\tin_progress\n")
        git(repo, "add", other_plan, "docs/plan/plan.md")
        git(repo, "commit", "-qm", "add another active plan")

        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "wrong-ledger-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        wrong_state = root / "wrong-plan-execution.json"
        other_bytes = (repo / other_plan).read_bytes()
        initialized = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/plan-execution-state.py"),
                "init",
                str(wrong_state),
                "--run-id",
                manifest["orchestration_run_id"],
                "--plan",
                other_plan,
                "--plan-digest",
                "sha256:" + hashlib.sha256(other_bytes).hexdigest(),
                "--source-head",
                manifest["source_head"],
                "--primary-invariant-digest",
                "sha256:" + hashlib.sha256(b"other invariant").hexdigest(),
                "--lifecycle-state",
                manifest["lifecycle_state_path"],
                "--implementation-mode",
                "candidate",
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)

        common = [
            "--orchestration-run-id",
            manifest["orchestration_run_id"],
            "--lifecycle-state",
            manifest["lifecycle_state_path"],
            "--plan-execution-state",
            str(wrong_state),
        ]
        commands = (
            ["finalize-apply", str(manifest_path), *common],
            ["apply", str(manifest_path), *common],
            [
                "validate",
                str(manifest_path),
                "--suite",
                "authoritative",
                "--parent-diff-approved",
                "--critical-invariants-approved",
                "--output-dir",
                str(root / "wrong-ledger-validation"),
                *common,
            ],
        )
        for command in commands:
            with self.subTest(operation=command[0]):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *command],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("plan path mismatch", result.stderr)

    def test_verified_patch_bytes_survive_path_swap_before_apply(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("safe\\n", encoding="utf-8")',
            output_dir=root / "swap-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validated = run_cli(
            repo,
            "validate",
            str(manifest_path),
            "--suite",
            "authoritative",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "swap-validation"),
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        original_verify = RUNNER.verify_candidate_manifest

        def swap_after_verify(**kwargs):
            verified = original_verify(**kwargs)
            Path(manifest["patch_path"]).write_text(
                "diff --git a/blocked.txt b/blocked.txt\nnew file mode 100644\nindex 0000000..e69de29\n",
                encoding="utf-8",
            )
            return verified

        previous_cwd = Path.cwd()
        try:
            os.chdir(repo)
            with mock.patch.object(RUNNER, "verify_candidate_manifest", side_effect=swap_after_verify):
                RUNNER.apply_worker_result(
                    argparse.Namespace(
                        manifest=str(manifest_path),
                        git_bin="git",
                        lifecycle_state=manifest["lifecycle_state_path"],
                        orchestration_run_id=manifest["orchestration_run_id"],
                        plan_execution_state=str(execution_state_path(manifest)),
                    )
                )
        finally:
            os.chdir(previous_cwd)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "safe\n")
        self.assertFalse((repo / "blocked.txt").exists())

    def test_validation_head_mutation_consumes_exactly_once_attempt(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={
                "allowed.txt": "original\n",
                "tests/smoke.sh": "#!/bin/sh\ngit -c user.name=Test -c user.email=test@example.invalid commit --allow-empty -qm validation-mutation\n",
            },
            validation=["tests/smoke.sh"],
        )
        self.addCleanup(temporary.cleanup)
        (repo / "tests/smoke.sh").chmod(0o755)
        git(repo, "add", "tests/smoke.sh")
        git(repo, "commit", "-qm", "make smoke executable")
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "head-mutation-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        args = (
            "validate", initial.stdout.strip(), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "head-mutation-validation"),
        )
        first = run_cli(repo, *args)
        self.assertEqual(first.returncode, 1)
        self.assertIn("changed review-clone HEAD", first.stderr)
        replay = run_cli(repo, *args[:-1], str(root / "head-mutation-replay"))
        self.assertEqual(replay.returncode, 1)
        self.assertIn("already been attempted", replay.stderr)

    def test_validation_ignores_ambient_home_toolchain_path(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={"allowed.txt": "original\n", "scripts/check.py": "value = 1\n"},
            validation=["python3 -m py_compile scripts/check.py"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fake_bin = root / "home" / ".local" / "bin"
        fake_bin.mkdir(parents=True)
        sentinel = root / "ambient-python-used"
        fake_python = fake_bin / "python3"
        fake_python.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n", encoding="utf-8")
        fake_python.chmod(0o755)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "trusted-path-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        result = run_cli(
            repo, "validate", initial.stdout.strip(), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "trusted-path-validation"),
            env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(sentinel.exists())

    def test_apply_finalization_failure_leaves_recoverable_applying_state(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("applied\\n", encoding="utf-8")',
            output_dir=root / "apply-recovery-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validated = run_cli(
            repo, "validate", str(manifest_path), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "apply-recovery-validation"),
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        original_persist = RUNNER.LifecycleState.persist

        def fail_finalization(state, data):
            if data.get("phase") == "applied":
                raise OSError("injected finalization failure")
            return original_persist(state, data)

        previous_cwd = Path.cwd()
        try:
            os.chdir(repo)
            with mock.patch.object(RUNNER.LifecycleState, "persist", new=fail_finalization):
                with self.assertRaisesRegex(RUNNER.RunnerError, "source patch was applied"):
                    RUNNER.apply_worker_result(
                        argparse.Namespace(
                            manifest=str(manifest_path), git_bin="git",
                            lifecycle_state=manifest["lifecycle_state_path"],
                            orchestration_run_id=manifest["orchestration_run_id"],
                            plan_execution_state=str(execution_state_path(manifest)),
                        )
                    )
        finally:
            os.chdir(previous_cwd)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "applied\n")
        lifecycle = json.loads(Path(manifest["lifecycle_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual(lifecycle["phase"], "applying")
        previous_cwd = Path.cwd()
        try:
            os.chdir(repo)
            RUNNER.finalize_apply(
                argparse.Namespace(
                    manifest=str(manifest_path), git_bin="git",
                    lifecycle_state=manifest["lifecycle_state_path"],
                    orchestration_run_id=manifest["orchestration_run_id"],
                    plan_execution_state=str(execution_state_path(manifest)),
                )
            )
        finally:
            os.chdir(previous_cwd)
        lifecycle = json.loads(Path(manifest["lifecycle_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual(lifecycle["phase"], "applied")

    def test_apply_recovery_allows_only_exact_patch_created_symlink_target(self) -> None:
        for tamper in ("none", "ancestor", "target"):
            with self.subTest(tamper=tamper):
                temporary, repo, plan_path = self.make_repo(
                    ["links/"],
                    files={"target.txt": "target\n", "other.txt": "other\n"},
                    repo_name=f"repo-{tamper}",
                )
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                initial, _output, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    '(worker_repo / "links").mkdir(exist_ok=True)\n'
                    '(worker_repo / "links" / "created").symlink_to("../target.txt")',
                    output_dir=root / f"symlink-recovery-{tamper}",
                )
                self.assertEqual(initial.returncode, 0, initial.stderr)
                manifest_path = Path(initial.stdout.strip())
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                validated = run_cli(
                    repo,
                    "validate",
                    str(manifest_path),
                    "--suite",
                    "authoritative",
                    "--parent-diff-approved",
                    "--critical-invariants-approved",
                    "--output-dir",
                    str(root / f"symlink-validation-{tamper}"),
                )
                self.assertEqual(validated.returncode, 0, validated.stderr)
                original_persist = RUNNER.LifecycleState.persist

                def fail_finalization(state, data):
                    if data.get("phase") == "applied":
                        raise OSError("injected finalization failure")
                    return original_persist(state, data)

                args = argparse.Namespace(
                    manifest=str(manifest_path),
                    git_bin="git",
                    lifecycle_state=manifest["lifecycle_state_path"],
                    orchestration_run_id=manifest["orchestration_run_id"],
                    plan_execution_state=str(execution_state_path(manifest)),
                )
                previous_cwd = Path.cwd()
                try:
                    os.chdir(repo)
                    with mock.patch.object(
                        RUNNER.LifecycleState, "persist", new=fail_finalization
                    ):
                        with self.assertRaisesRegex(RUNNER.RunnerError, "source patch was applied"):
                            RUNNER.apply_worker_result(args)
                    created = repo / "links/created"
                    self.assertTrue(created.is_symlink())
                    if tamper == "ancestor":
                        outside = root / "outside-links"
                        (repo / "links").rename(outside)
                        (repo / "links").symlink_to(outside, target_is_directory=True)
                    elif tamper == "target":
                        created.unlink()
                        created.symlink_to("../other.txt")

                    if tamper == "none":
                        RUNNER.finalize_apply(args)
                        lifecycle = json.loads(
                            Path(manifest["lifecycle_state_path"]).read_text(encoding="utf-8")
                        )
                        self.assertEqual(lifecycle["phase"], "applied")
                    elif tamper == "ancestor":
                        with self.assertRaisesRegex(RUNNER.RunnerError, "symlink"):
                            RUNNER.finalize_apply(args)
                    else:
                        with self.assertRaisesRegex(RUNNER.RunnerError, "does not exactly match"):
                            RUNNER.finalize_apply(args)
                finally:
                    os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
