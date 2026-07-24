#!/usr/bin/env python3
"""Focused tests for root and generated-project validation tooling."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
PLAN_COMMAND_MODULES = (
    ROOT / "scripts/plan_validation_commands.py",
    ROOT / "template/scripts/plan_validation_commands.py",
)
VALIDATE_CHANGE_MODULES = (
    ROOT / "scripts/validate-changes.py",
    ROOT / "template/scripts/validate-changes.py",
)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PlanValidationCommandsTest(unittest.TestCase):
    def test_title_does_not_hide_manifest_validation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "# Plan title\n\nstatus: in_progress\nvalidation:\n"
                "  - npm run typecheck\n"
                "  - python3 -m pytest\n\n"
                "## Tasks\n\n- [ ] example\n",
                encoding="utf-8",
            )
            for index, module_path in enumerate(PLAN_COMMAND_MODULES):
                with self.subTest(module=module_path):
                    module = load_module(module_path, f"plan_validation_commands_{index}")
                    commands = module.check_plan(plan)
                    self.assertEqual(
                        [command.argv for command in commands],
                        [("npm", "run", "typecheck"), ("python3", "-m", "pytest")],
                    )

    def test_argv_rules_accept_declared_families_and_reject_expansion(self) -> None:
        accepted = (
            "git diff --cached --check",
            "npm run typecheck",
            "python3 -m pytest",
            "python3 -m pytest tests/test-validation-tools.py",
            "python3 scripts/validate-changes.py --all --print-only --json",
        )
        rejected = (
            "npm run prepublish",
            "python3 -m pytest -q",
            "python3 -m pytest ../outside.py",
            "python3 scripts/validate-changes.py --all --staged",
            "git diff --check; rm -rf .",
        )
        for index, module_path in enumerate(PLAN_COMMAND_MODULES):
            module = load_module(module_path, f"plan_validation_rules_{index}")
            for command in accepted:
                with self.subTest(module=module_path, accepted=command):
                    module.parse_validation_command(command)
            for command in rejected:
                with self.subTest(module=module_path, rejected=command):
                    with self.assertRaises(module.ValidationCommandError):
                        module.parse_validation_command(command)

    def test_root_and_template_specific_commands_stay_separate(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_plan_validation_commands")
        template_module = load_module(PLAN_COMMAND_MODULES[1], "template_plan_validation_commands")
        root_module.parse_validation_command("scripts/lint-project-workflow.sh")
        root_module.parse_validation_command("tests/smoke.sh")
        template_module.parse_validation_command("python3 scripts/check-external-service-policy.py check")
        template_module.parse_validation_command("scripts/check-agent-completion.sh")
        with self.assertRaises(root_module.ValidationCommandError):
            root_module.parse_validation_command("python3 scripts/check-external-service-policy.py check")
        with self.assertRaises(template_module.ValidationCommandError):
            template_module.parse_validation_command("tests/smoke.sh")


class ValidateChangesTest(unittest.TestCase):
    def test_all_mode_checks_staged_and_unstaged_whitespace(self) -> None:
        for index, (plan_path, validate_path) in enumerate(
            zip(PLAN_COMMAND_MODULES, VALIDATE_CHANGE_MODULES, strict=True)
        ):
            with self.subTest(module=validate_path):
                dependency = load_module(plan_path, "plan_validation_commands")
                sys.modules["plan_validation_commands"] = dependency
                module = load_module(validate_path, f"validate_changes_{index}")
                self.assertEqual(
                    module.select_commands(["README.md"], "all")[:2],
                    [
                        ["git", "diff", "--cached", "--check"],
                        ["git", "diff", "--check"],
                    ],
                )
                self.assertEqual(
                    module.select_commands(["README.md"], "staged")[:1],
                    [["git", "diff", "--cached", "--check"]],
                )

    def test_template_selects_external_service_policy_check(self) -> None:
        dependency = load_module(PLAN_COMMAND_MODULES[1], "plan_validation_commands")
        sys.modules["plan_validation_commands"] = dependency
        module = load_module(VALIDATE_CHANGE_MODULES[1], "template_validate_changes_external_service")
        module.existing = lambda path: path == "scripts/check-external-service-policy.py"
        command = ["python3", "scripts/check-external-service-policy.py", "check"]
        self.assertIn(command, module.select_commands(["docs/agent/external-services.yaml"], "all"))
        self.assertIn(command, module.select_commands(["docs/agent/SPEC_EXTERNAL_SERVICES.md"], "all"))
        self.assertIn(command, module.select_commands(["scripts/check-external-service-policy.py"], "all"))

    def test_all_mode_runs_both_whitespace_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scripts = repo / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts/validate-changes.py", scripts)
            shutil.copy2(ROOT / "scripts/plan_validation_commands.py", scripts)
            staged = repo / "staged.md"
            unstaged = repo / "unstaged.md"
            staged.write_text("clean\n", encoding="utf-8")
            unstaged.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Validation Test",
                    "-c",
                    "user.email=validation@example.invalid",
                    "commit",
                    "-qm",
                    "initial",
                ],
                cwd=repo,
                check=True,
            )

            staged.write_text("staged trailing whitespace \n", encoding="utf-8")
            subprocess.run(["git", "add", "staged.md"], cwd=repo, check=True)
            unstaged.write_text("unstaged trailing whitespace \n", encoding="utf-8")
            first = self.run_validate_all(repo)
            self.assertEqual(first.returncode, 2)
            first_result = json.loads(first.stdout)
            self.assertEqual(first_result["results"][0]["argv"], ["git", "diff", "--cached", "--check"])
            self.assertEqual(first_result["results"][0]["returncode"], 2)

            staged.write_text("staged clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "staged.md"], cwd=repo, check=True)
            second = self.run_validate_all(repo)
            self.assertEqual(second.returncode, 2)
            second_result = json.loads(second.stdout)
            self.assertEqual(
                [result["argv"] for result in second_result["results"]],
                [
                    ["git", "diff", "--cached", "--check"],
                    ["git", "diff", "--check"],
                ],
            )
            self.assertEqual(second_result["results"][0]["returncode"], 0)
            self.assertEqual(second_result["results"][1]["returncode"], 2)

    @staticmethod
    def run_validate_all(repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "scripts/validate-changes.py", "--all", "--json"],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


class GeneratedCiTest(unittest.TestCase):
    def test_whitespace_check_uses_event_commit_range(self) -> None:
        root_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        workflow = (ROOT / "template/.github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn('git diff --check "$BASE_SHA...$PR_HEAD_SHA"', root_workflow)
        self.assertIn('git diff --check "$BEFORE_SHA..$HEAD_SHA"', root_workflow)
        self.assertIn('git diff --check "$EMPTY_TREE" "$HEAD_SHA"', root_workflow)
        self.assertIn('git diff --check "${PR_BASE_SHA}...${PR_HEAD_SHA}"', workflow)
        self.assertIn('git diff --check "${PUSH_BEFORE_SHA}..${HEAD_SHA}"', workflow)
        self.assertIn('git diff --check "$EMPTY_TREE" "$HEAD_SHA"', workflow)
        self.assertIn('git cat-file -e "$PUSH_BEFORE_SHA^{commit}"', workflow)
        self.assertIn("fetch-depth: 0", workflow)

    def test_empty_tree_range_checks_the_full_initial_push_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            bad = repo / "bad.md"
            bad.write_text("trailing whitespace \n", encoding="utf-8")
            subprocess.run(["git", "add", "bad.md"], cwd=repo, check=True)
            self.commit(repo, "first")
            (repo / "clean.md").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "clean.md"], cwd=repo, check=True)
            self.commit(repo, "second")
            empty_tree = subprocess.run(
                ["git", "hash-object", "-t", "tree", "/dev/null"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            result = subprocess.run(
                ["git", "diff", "--check", empty_tree, "HEAD"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("bad.md:1: trailing whitespace", result.stdout)

    @staticmethod
    def commit(repo: Path, message: str) -> None:
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Validation Test",
                "-c",
                "user.email=validation@example.invalid",
                "commit",
                "-qm",
                message,
            ],
            cwd=repo,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
