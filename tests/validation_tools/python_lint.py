"""Real-tool checks for the bounded Python lint command."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from .support import ROOT, load_module


class PythonLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="python-lint-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.module = load_module(ROOT / "scripts/lint-python.py", "python_lint_test")
        self.module.check_version(self.module.ruff_executable())

    def fixture(self, name: str, *, generated: bool = False) -> tuple[Path, Path]:
        root = self.base / name
        workflow = root / ".project-agent-workflow" if generated else root
        for scope in (
            (".project-agent-workflow/scripts",) if generated
            else ("scripts", "tests", "template/.project-agent-workflow/scripts")
        ):
            (root / scope).mkdir(parents=True)
        for relative in (
            "scripts/lint-python.py",
            "tools/python-quality/ruff.toml",
            "tools/python-quality/requirements.txt",
        ):
            target = workflow / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        guard = workflow / (
            "scripts/worktree_guard.py" if generated else "scripts/project_workflow/worktree_guard.py"
        )
        guard.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts/project_workflow/worktree_guard.py", guard)
        return root, workflow

    def run_lint(self, root: Path, workflow: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(workflow / "scripts/lint-python.py"), *args],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    @staticmethod
    def snapshot(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()
        }

    def test_real_rules_have_defects_and_valid_counterparts(self) -> None:
        cases = {
            "F541": ('message = f"hello"\n', 'message = "hello"\n'),
            "F631": ('assert (False, "message")\n', 'assert False, "message"\n'),
            "F634": ("if (False,):\n    pass\n", "if False:\n    pass\n"),
            "F821": ("value = missing\n", "missing = 1\nvalue = missing\n"),
            "F822": ('__all__ = ["missing"]\n', 'missing = 1\n__all__ = ["missing"]\n'),
            "F823": (
                "value = 1\ndef run():\n    print(value)\n    value = 2\n",
                "value = 1\ndef run():\n    value = 2\n    print(value)\n",
            ),
        }
        for generated in (False, True):
            root, workflow = self.fixture(f"rules-{generated}", generated=generated)
            target = workflow / "scripts/example.py"
            for code, (bad, good) in cases.items():
                with self.subTest(generated=generated, rule=code):
                    target.write_text(bad)
                    before = self.snapshot(root)
                    result = self.run_lint(root, workflow)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(code, result.stdout)
                    self.assertEqual(before, self.snapshot(root))
                    target.write_text(good)
                    accepted = self.run_lint(root, workflow)
                    self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            target.unlink()
            raw = subprocess.run(
                [
                    str(self.module.ruff_executable()), "check", "--no-cache",
                    "--config", str(workflow / "tools/python-quality/ruff.toml"),
                    "--output-format", "json", str(target),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                env=self.module.ruff_environment(),
            )
            self.assertEqual(raw.returncode, 1, raw.stderr)
            self.assertEqual([entry["code"] for entry in json.loads(raw.stdout)], ["E902"])
            target.write_text("value = 1\n")
            self.assertEqual(self.run_lint(root, workflow).returncode, 0)
            target.write_text("def broken(\n")
            self.assertNotEqual(self.run_lint(root, workflow).returncode, 0)

    def test_generated_scope_ignores_product_and_project_configuration(self) -> None:
        root, workflow = self.fixture("generated", generated=True)
        (root / "src").mkdir()
        (root / "src/product.py").write_text("value = unknown_product_symbol\n")
        (root / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["ALL"]\n')
        (root / ".ruff.toml").write_text("not valid toml\n")
        target = workflow / "scripts/example.py"
        target.write_text('message = f"hello"\n')
        (workflow / "scripts/.gitignore").write_text("example.py\n")
        before = self.snapshot(root)
        result = self.run_lint(root, workflow)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("F541", result.stdout)
        self.assertNotIn("unknown_product_symbol", result.stdout)
        self.assertEqual(before, self.snapshot(root))

    def test_checkout_name_does_not_determine_the_distribution(self) -> None:
        root, workflow = self.fixture(".project-agent-workflow")
        for index, scope in enumerate((
            "scripts", "tests", "template/.project-agent-workflow/scripts",
        )):
            (root / scope / "defect.py").write_text(f"value = missing_{index}\n")
        result = self.run_lint(root, workflow)
        self.assertEqual(result.returncode, 1, result.stderr)
        for index in range(3):
            self.assertIn(f"missing_{index}", result.stdout)
        root, workflow = self.fixture(
            "generated-parent/.project-agent-workflow", generated=True,
        )
        (root / "product.py").write_text("value = missing_product_symbol\n")
        self.assertEqual(self.run_lint(root, workflow).returncode, 0)

    def test_ruff_environment_cannot_redirect_check_output(self) -> None:
        for generated in (False, True):
            root, workflow = self.fixture(f"output-{generated}", generated=generated)
            target = workflow / "scripts/example.py"
            outside = self.base / f"outside-output-{generated}.txt"
            outside.write_text("preserve this file\n")
            absent = self.base / f"absent-output-{generated}.txt"
            for content, expected in (
                ('message = f"hello"\n', 1), ('message = "hello"\n', 0),
            ):
                target.write_text(content)
                for destination in (outside, absent, target):
                    with self.subTest(generated=generated, destination=destination, exit=expected):
                        before = self.snapshot(self.base)
                        with mock.patch.dict(os.environ, {"RUFF_OUTPUT_FILE": str(destination)}):
                            result = self.run_lint(root, workflow)
                        self.assertEqual(result.returncode, expected, result.stderr)
                        self.assertIn("F541" if expected else "All checks passed", result.stdout)
                        self.assertEqual(before, self.snapshot(self.base))

    def test_ruff_settings_environment_is_ignored_without_dropping_caller_environment(self) -> None:
        for generated in (False, True):
            root, workflow = self.fixture(f"settings-{generated}", generated=generated)
            (workflow / "scripts/example.py").write_text('message = f"hello"\n')
            cache = self.base / f"outside-cache-{generated}"
            before = self.snapshot(self.base)
            with mock.patch.dict(os.environ, {
                "RUFF_OUTPUT_FORMAT": "not-a-format",
                "RUFF_CACHE_DIR": str(cache),
                "RUFF_NO_CACHE": "not-a-boolean",
                "PYTHON_LINT_TEST_PASSTHROUGH": "preserved",
            }):
                environment = self.module.ruff_environment()
                self.assertEqual(environment["PYTHON_LINT_TEST_PASSTHROUGH"], "preserved")
                self.assertFalse(any(name.startswith("RUFF_") for name in environment))
                result = self.run_lint(root, workflow)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("F541", result.stdout)
            self.assertFalse(cache.exists())
            self.assertEqual(before, self.snapshot(self.base))

    def test_invalid_settings_and_operand_preflight_never_fix_a_valid_operand(self) -> None:
        root, workflow = self.fixture("preflight")
        target = root / "scripts/example.py"
        target.write_text('message = f"hello"\n')
        outside = self.base / "outside.py"
        outside.write_text('message = f"outside"\n')
        (root / "scripts/link.py").symlink_to(outside)
        (root / "scripts/linked-directory").symlink_to(self.base, target_is_directory=True)
        for operand in (
            "scripts", "../outside.py", str(outside), "scripts/./example.py",
            "scripts/link.py", "scripts/linked-directory/outside.py", "product.py",
            "scripts/missing.py", "scripts/example.py",
        ):
            with self.subTest(operand=operand):
                result = self.run_lint(root, workflow, "--fix", "scripts/example.py", operand)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(target.read_text(), 'message = f"hello"\n')
                self.assertEqual(outside.read_text(), 'message = f"outside"\n')
        self.assertEqual(self.run_lint(root, workflow, "--fix").returncode, 2)
        self.assertEqual(self.run_lint(root, workflow).returncode, 2)
        (root / "scripts/link.py").unlink()
        (root / "scripts/linked-directory").unlink()
        config = workflow / "tools/python-quality/ruff.toml"
        original = config.read_text()
        for invalid in (
            "invalid = [",
            original.replace('ignore = []', 'ignore = ["F821"]'),
            original.replace('fixable = ["F541"]', 'fixable = ["ALL"]'),
            original + '\n[lint.per-file-ignores]\n"*.py" = ["ALL"]\n',
        ):
            config.write_text(invalid)
            result = self.run_lint(root, workflow, "--fix", "scripts/example.py")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(target.read_text(), 'message = f"hello"\n')
        config.write_text(original)
        requirement = workflow / "tools/python-quality/requirements.txt"
        requirement.write_text("ruff\n")
        self.assertEqual(self.run_lint(root, workflow).returncode, 2)

    def test_missing_or_wrong_version_is_an_explicit_error(self) -> None:
        executable = self.module.ruff_executable()
        with mock.patch.object(self.module, "RUFF_VERSION", "0.0.0"):
            with self.assertRaisesRegex(self.module.LintError, "version mismatch"):
                self.module.check_version(executable)
        environment = self.base / "without-ruff"
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(environment)], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        with mock.patch.object(
            self.module.sysconfig, "get_path", return_value=str(environment / "bin")
        ):
            with self.assertRaisesRegex(self.module.LintError, "Ruff is unavailable"):
                self.module.ruff_executable()
        for scripts in ("", None, "relative/bin"):
            with self.subTest(scripts=scripts):
                with mock.patch.object(
                    self.module.sysconfig, "get_path", return_value=scripts
                ):
                    with self.assertRaisesRegex(self.module.LintError, "Ruff is unavailable"):
                        self.module.ruff_executable()

    def test_pinned_ruff_is_not_shadowed_by_modules_or_path(self) -> None:
        """A repository module, a PYTHONPATH package, and a PATH executable must
        never be selected in place of the environment's pinned Ruff."""

        root, workflow = self.fixture("shadowed")
        target = workflow / "scripts/example.py"
        target.write_text('message = f"hello"\n')
        shadow = self.base / "shadow"
        shadow.mkdir()
        source = (
            "import sys\n"
            "print('ruff 0.15.7' if '--version' in sys.argv else 'SHADOW_RUFF_RAN')\n"
        )
        (shadow / "ruff.py").write_text(source)
        (root / "ruff.py").write_text(source)
        package = shadow / "ruff"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "__main__.py").write_text(source)
        launcher = shadow / "bin"
        launcher.mkdir()
        (launcher / "ruff").write_text("#!/bin/sh\nprintf 'SHADOW_PATH_RUFF_RAN\\n'\n")
        (launcher / "ruff").chmod(0o700)
        before = self.snapshot(root)
        result = subprocess.run(
            [sys.executable, str(workflow / "scripts/lint-python.py")],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            env={
                **os.environ,
                "PYTHONPATH": str(shadow),
                "PATH": str(launcher) + os.pathsep + os.environ.get("PATH", ""),
            },
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("F541", result.stdout)
        self.assertNotIn("SHADOW_", result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot(root))

    def test_required_callers_isolate_the_interpreter_from_inherited_startup_code(self) -> None:
        """An inherited PYTHONPATH sitecustomize runs before the wrapper selects
        Ruff, so a non-isolated launch can report success without linting. Every
        required caller must therefore start the wrapper in isolated mode."""

        root, workflow = self.fixture("isolation")
        (workflow / "scripts/example.py").write_text('message = f"hello"\n')
        startup = self.base / "startup"
        startup.mkdir()
        (startup / "sitecustomize.py").write_text("import os\nos._exit(0)\n")
        environment = {**os.environ, "PYTHONPATH": str(startup)}
        script = str(workflow / "scripts/lint-python.py")

        def launch(*prefix: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, *prefix, script], cwd=root, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=environment,
            )

        hijacked = launch()
        self.assertEqual(hijacked.returncode, 0, hijacked.stdout + hijacked.stderr)
        self.assertNotIn("F541", hijacked.stdout)
        isolated = launch("-I")
        self.assertEqual(isolated.returncode, 1, isolated.stdout + isolated.stderr)
        self.assertIn("F541", isolated.stdout)

        root_script = "scripts/lint-python.py"
        managed_script = ".project-agent-workflow/scripts/lint-python.py"
        callers = {
            "scripts/lint-project-workflow.sh": [f'python3 -I {root_script})'],
            "scripts/validate-changes.py": [f'["python3", "-I", "{root_script}"]'],
            "template/.project-agent-workflow/scripts/validate-changes.py": [
                f'["python3", "-I", "{managed_script}"]'
            ],
            "template/.github/workflows/project-agent-workflow.yml": [
                f"python3 -I {managed_script}"
            ],
            "tests/copier-update.sh": [f"python3 -I {managed_script}"],
            "references/validation.md": [
                f"python -I {root_script}", f"python3 -I {managed_script}"
            ],
            "template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja": [
                f"python3 -I {managed_script}"
            ],
        }
        launch_pattern = re.compile(
            r"(?<![-\w])python3?(?:\s+-\S+)*\s+(?:\.project-agent-workflow/)?scripts/lint-python\.py"
        )
        for caller, expected in callers.items():
            text = (ROOT / caller).read_text(encoding="utf-8")
            with self.subTest(caller=caller):
                for spelling in expected:
                    self.assertIn(spelling, text)
                for launch in launch_pattern.findall(text):
                    self.assertIn("-I", launch.split())

    def test_empty_scan_and_cache_exclusions(self) -> None:
        root = self.base / "empty"
        (root / "scripts").mkdir(parents=True)
        with self.assertRaisesRegex(self.module.LintError, "no Python files"):
            self.module.target_paths(root, ("scripts",), [])
        cache = root / "scripts/__pycache__"
        cache.mkdir()
        (cache / "ignored.py").write_text("bad = unknown\n")
        target = root / "scripts/example.py"
        target.write_text("value = 1\n")
        self.assertEqual(self.module.target_paths(root, ("scripts",), []), ["scripts/example.py"])
        with self.assertRaisesRegex(self.module.LintError, "outside"):
            self.module.target_paths(root, ("scripts",), ["scripts/__pycache__/ignored.py"])

    @contextlib.contextmanager
    def bound_fixture(self, *, generated: bool):
        root, workflow = self.fixture(f"bound-{generated}", generated=generated)
        relative = (workflow / "scripts/example.py").relative_to(root)
        (root / relative).write_text('message = f"hello"\n')
        subprocess.run(["git", "init", "-q", "-b", "dev", str(root)], check=True)
        for args in (
            ("config", "user.name", "Lint Test"),
            ("config", "user.email", "lint@example.invalid"),
            ("remote", "add", "origin", "https://github.com/example/python-lint-fixture"),
            ("add", "."),
            ("commit", "-qm", "lint fixture"),
        ):
            subprocess.run(["git", "-C", str(root), *args], check=True)
        allowed = self.base / f"managed-{generated}"
        allowed.mkdir(mode=0o700)
        target = allowed / "lint-task"
        manager = ROOT / "scripts/manage-plan-worktrees.py"
        prepared = subprocess.run(
            [
                sys.executable, str(manager), "prepare", "--direct-task", "lint-fixture",
                "--owner-id", "lint-test", "--worktree", str(target),
                "--allowed-root", str(allowed), "--branch", "task/lint-fixture",
            ],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        originals = self.snapshot(target)
        try:
            yield target, target / workflow.relative_to(root), relative.as_posix()
        finally:
            for name, content in originals.items():
                if ".git" not in Path(name).parts:
                    (target / name).write_bytes(content)
            retired = subprocess.run(
                [
                    sys.executable, str(manager), "retire", "--direct-task", "lint-fixture",
                    "--owner-id", "lint-test", "--allowed-root", str(allowed), "--stopped",
                ],
                cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(retired.returncode, 0, retired.stderr)

    def test_real_safe_fix_requires_binding_and_preserves_other_diagnostics(self) -> None:
        for generated in (False, True):
            root, workflow = self.fixture(f"unbound-{generated}", generated=generated)
            relative = (workflow / "scripts/example.py").relative_to(root).as_posix()
            (root / relative).write_text('message = f"hello"\n')
            refused = self.run_lint(root, workflow, "--fix", relative)
            self.assertEqual(refused.returncode, 2)
            self.assertIn("live task-bound worktree", refused.stderr)
            with self.bound_fixture(generated=generated) as (root, workflow, relative):
                untouched = workflow / "scripts/untouched.py"
                untouched.write_text('message = f"not selected"\n')
                try:
                    target = root / relative
                    outside = self.base / f"outside-hardlink-{generated}.py"
                    outside.write_text('message = f"outside"\n')
                    linked = workflow / "scripts/hardlinked.py"
                    os.link(outside, linked)
                    try:
                        denied = self.run_lint(
                            root, workflow, "--fix", relative, linked.relative_to(root).as_posix(),
                        )
                        self.assertEqual(denied.returncode, 2)
                        self.assertIn("hard-linked", denied.stderr)
                        self.assertEqual(target.read_text(), 'message = f"hello"\n')
                        self.assertEqual(outside.read_text(), 'message = f"outside"\n')
                    finally:
                        linked.unlink()
                    target.write_text('message = f"hello"\nmissing_name\n')
                    fixed = self.run_lint(root, workflow, "--fix", relative)
                    self.assertEqual(fixed.returncode, 1, fixed.stderr)
                    self.assertEqual(target.read_text(), 'message = "hello"\nmissing_name\n')
                    self.assertIn("F821", fixed.stdout)
                    self.assertEqual(untouched.read_text(), 'message = f"not selected"\n')
                    before = target.read_bytes()
                    self.assertEqual(self.run_lint(root, workflow, "--fix", relative).returncode, 1)
                    self.assertEqual(before, target.read_bytes())
                    target.write_text('message = f"hello"\n')
                    self.assertEqual(self.run_lint(root, workflow, "--fix", relative).returncode, 0)
                finally:
                    untouched.unlink()

    def test_ruff_environment_cannot_redirect_a_bound_fix(self) -> None:
        for generated in (False, True):
            with (
                self.subTest(generated=generated),
                self.bound_fixture(generated=generated) as (root, workflow, relative),
            ):
                outside = self.base / f"outside-fix-output-{generated}.txt"
                outside.write_text("preserve this file\n")
                untouched = workflow / "scripts/untouched.py"
                untouched.write_text('message = f"not selected"\n')
                try:
                    before = self.snapshot(root)
                    with mock.patch.dict(os.environ, {"RUFF_OUTPUT_FILE": str(outside)}):
                        fixed = self.run_lint(root, workflow, "--fix", relative)
                    self.assertEqual(fixed.returncode, 0, fixed.stderr)
                    self.assertEqual(outside.read_text(), "preserve this file\n")
                    before[relative] = b'message = "hello"\n'
                    self.assertEqual(before, self.snapshot(root))
                finally:
                    untouched.unlink()

    def test_inherited_startup_code_cannot_forge_the_fix_worktree_guard(self) -> None:
        """The guard's verdict authorizes writes, so its interpreter is isolated
        too. A sitecustomize module that prints an enforced result and exits
        must not unlock --fix in a checkout that is not task-bound."""

        root, workflow = self.fixture("forged-guard")
        target = workflow / "scripts/example.py"
        original = 'message = f"hello"\n'
        target.write_text(original)
        startup = self.base / "forged-startup"
        startup.mkdir()
        (startup / "sitecustomize.py").write_text(
            "import json, os, sys\n"
            "if any(argument == 'require' for argument in sys.argv):\n"
            "    sys.stdout.write(json.dumps({'enforced': True}))\n"
            "    sys.stdout.flush()\n"
            "    os._exit(0)\n"
        )
        relative = target.relative_to(root).as_posix()
        before = self.snapshot(root)
        result = subprocess.run(
            [sys.executable, "-I", str(workflow / "scripts/lint-python.py"), "--fix", relative],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            env={**os.environ, "PYTHONPATH": str(startup)},
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("live task-bound worktree", result.stderr)
        self.assertEqual(target.read_text(), original)
        self.assertEqual(before, self.snapshot(root))

    def test_current_complete_initial_scope_passes_and_bindings_are_defined(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/lint-python.py")], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for prefix in ("scripts", "template/.project-agent-workflow/scripts"):
            state = load_module(ROOT / prefix / "plan-execution-state.py", f"lint_state_{prefix}")
            self.assertEqual(state.EMPTY_CHAIN_DIGEST, state.digest(b""))
            restructure = load_module(ROOT / prefix / "restructure-plan.py", f"lint_restructure_{prefix}")
            self.assertIn("ModuleType", restructure.load_worktree_guard_module.__globals__)

    def test_documented_uv_run_uses_the_prepared_environment_without_activation(self) -> None:
        uv = shutil.which("uv")
        if uv is None:
            self.fail("root development validation requires uv")
        environment = os.environ.copy()
        environment.pop("VIRTUAL_ENV", None)
        root_environment_bin = (ROOT / ".venv/bin").resolve()
        environment["PATH"] = os.pathsep.join(
            entry for entry in environment.get("PATH", "").split(os.pathsep)
            if entry and Path(entry).resolve() != root_environment_bin
        )
        result = subprocess.run(
            [uv, "run", "--locked", "python", "scripts/lint-python.py"],
            cwd=ROOT, env=environment, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
