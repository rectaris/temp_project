"""Change-selection tests."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import PLAN_COMMAND_MODULES, ROOT, VALIDATE_CHANGE_MODULES, load_module


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

    def test_changed_files_exclude_migration_backup(self) -> None:
        for index, (plan_path, validate_path) in enumerate(
            zip(PLAN_COMMAND_MODULES, VALIDATE_CHANGE_MODULES, strict=True)
        ):
            with self.subTest(module=validate_path):
                dependency = load_module(plan_path, "plan_validation_commands")
                sys.modules["plan_validation_commands"] = dependency
                module = load_module(validate_path, f"validate_changes_migration_backup_{index}")

                def fake_git(args: list[str]) -> list[str]:
                    values = {
                        ("diff", "--cached", "--name-only"): [],
                        ("diff", "--name-only"): ["src/current.py"],
                        ("ls-files", "--others", "--exclude-standard"): [
                            ".project-agent-workflow-migration/v1-pre-namespace/scripts/old.sh",
                            "docs/current.md",
                        ],
                    }
                    return values.get(tuple(args), [])

                module.git = fake_git
                paths, mode = module.changed_files("all")
                self.assertEqual(paths, ["docs/current.md", "src/current.py"])
                self.assertEqual(mode, "all")

    def test_git_query_failure_is_reported_in_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scripts = repo / "scripts"
            scripts.mkdir()
            for source in (ROOT / "scripts").glob("*.py"):
                shutil.copy2(source, scripts)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            for validate_path in (
                scripts / "validate-changes.py",
                ROOT / "template/.project-agent-workflow/scripts/validate-changes.py",
            ):
                result = subprocess.run(
                    [sys.executable, "-B", str(validate_path), "--all", "--json"],
                    cwd=repo,
                    env={**os.environ, "GIT_DIR": str(repo / "missing-git-dir")},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                with self.subTest(validator=validate_path):
                    self.assertEqual(result.returncode, 1)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["status"], "git_query_failed")
                    self.assertIn("git diff --cached --name-only", payload["error"])

    def test_managed_plan_validation_requires_managed_index(self) -> None:
        for index, (plan_path, validate_path) in enumerate(
            zip(PLAN_COMMAND_MODULES, VALIDATE_CHANGE_MODULES, strict=True)
        ):
            with self.subTest(module=validate_path), tempfile.TemporaryDirectory() as tmp:
                dependency = load_module(plan_path, "plan_validation_commands")
                sys.modules["plan_validation_commands"] = dependency
                module = load_module(validate_path, f"validate_changes_plan_format_{index}")
                repo = Path(tmp)
                plan_index = repo / "docs/plan/plan.md"
                plan_index.parent.mkdir(parents=True)
                module.ROOT = repo
                module.existing = lambda _path: True

                plan_index.write_text("# アクティブプラン\n\n既存プロジェクト形式\n", encoding="utf-8")
                legacy_commands = module.select_commands(["docs/plan/active/.gitkeep"], "all")
                self.assertFalse(
                    any(any(part.endswith("lint-plan-docs.py") for part in command) for command in legacy_commands)
                )
                self.assertFalse(
                    any(any(part.endswith("format-plan-docs.py") for part in command) for command in legacy_commands)
                )

                plan_index.write_text("# Active Plan\n\nNo active development items.\n", encoding="utf-8")
                managed_commands = module.select_commands(["docs/plan/active/.gitkeep"], "all")
                self.assertTrue(
                    any(any(part.endswith("lint-plan-docs.py") for part in command) for command in managed_commands)
                )
                self.assertTrue(
                    any(any(part.endswith("format-plan-docs.py") for part in command) for command in managed_commands)
                )

    def test_template_selects_external_service_policy_check(self) -> None:
        dependency = load_module(PLAN_COMMAND_MODULES[1], "plan_validation_commands")
        sys.modules["plan_validation_commands"] = dependency
        module = load_module(VALIDATE_CHANGE_MODULES[1], "template_validate_changes_external_service")
        managed_script = ".project-agent-workflow/scripts/check-external-service-policy.py"
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            policy = repo / "docs/agent/external-services.yaml"
            policy.parent.mkdir(parents=True)
            module.ROOT = repo
            module.existing = lambda path: path == managed_script
            command = ["python3", managed_script, "check"]

            policy.write_text("credential_env: LEGACY_TOKEN\n", encoding="utf-8")
            self.assertNotIn(
                command,
                module.select_commands(["docs/agent/external-services.yaml"], "all"),
            )

            policy.write_text(
                "version: 1\nauthentication: environment\ncredential_reference: CURRENT_TOKEN\n",
                encoding="utf-8",
            )
            self.assertIn(command, module.select_commands(["docs/agent/external-services.yaml"], "all"))
            self.assertIn(
                command,
                module.select_commands(
                    [".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"], "all"
                ),
            )
            self.assertIn(command, module.select_commands([managed_script], "all"))

            policy.write_text(
                "version: 2\n"
                "access_profile: task_scoped_default_allow\n"
                "provider_requirement: runtime_configured\n",
                encoding="utf-8",
            )
            self.assertIn(command, module.select_commands(["docs/agent/external-services.yaml"], "all"))

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

    def test_no_change_fixture_remains_git_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scripts = repo / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts/validate-changes.py", scripts)
            shutil.copy2(ROOT / "scripts/plan_validation_commands.py", scripts)
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

            result = subprocess.run(
                [sys.executable, "-B", "scripts/validate-changes.py", "--all", "--json"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "no_changes")
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            )
            self.assertEqual(status.stdout, "")

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



if __name__ == "__main__":
    unittest.main()
