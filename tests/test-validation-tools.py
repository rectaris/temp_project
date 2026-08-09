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
    ROOT / "template/.project-agent-workflow/scripts/plan_validation_commands.py",
)
VALIDATE_CHANGE_MODULES = (
    ROOT / "scripts/validate-changes.py",
    ROOT / "template/.project-agent-workflow/scripts/validate-changes.py",
)
SECURITY_RULE_MODULE = ROOT / "template/.project-agent-workflow/scripts/security_rules.py"
SECURITY_CHECK_MODULE = ROOT / "template/.project-agent-workflow/scripts/security-static-check.py"
LEGACY_MIGRATOR = ROOT / "template/.project-agent-workflow/scripts/migrate-legacy-template-files.py"


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
        common_accepted = (
            "git diff --cached --check",
            "npm run typecheck",
            "python3 -m pytest",
            "python3 -m pytest tests/test-validation-tools.py",
        )
        common_rejected = (
            "npm run prepublish",
            "python3 -m pytest -q",
            "python3 -m pytest ../outside.py",
            "git diff --check; rm -rf .",
        )
        for index, module_path in enumerate(PLAN_COMMAND_MODULES):
            module = load_module(module_path, f"plan_validation_rules_{index}")
            prefix = "scripts" if index == 0 else ".project-agent-workflow/scripts"
            accepted = (*common_accepted, f"python3 {prefix}/validate-changes.py --all --print-only --json")
            rejected = (*common_rejected, f"python3 {prefix}/validate-changes.py --all --staged")
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
        template_module.parse_validation_command(
            "python3 .project-agent-workflow/scripts/check-external-service-policy.py check"
        )
        template_module.parse_validation_command(".project-agent-workflow/scripts/check-agent-completion.sh")
        with self.assertRaises(root_module.ValidationCommandError):
            root_module.parse_validation_command("python3 scripts/check-external-service-policy.py check")
        with self.assertRaises(template_module.ValidationCommandError):
            template_module.parse_validation_command("tests/smoke.sh")

    def test_template_accepts_namespaced_hook_and_script_compilation(self) -> None:
        template_module = load_module(PLAN_COMMAND_MODULES[1], "template_namespaced_compile")
        template_module.parse_validation_command(
            "python3 -m py_compile "
            ".project-agent-workflow/hooks/stop_review_gate.py "
            ".project-agent-workflow/scripts/validate-changes.py"
        )
        template_module.parse_validation_command(
            "python3 .project-agent-workflow/scripts/security-static-check.py --changed"
        )
        template_module.parse_validation_command(
            "python3 .project-agent-workflow/scripts/security-static-check.py --managed"
        )

    def test_root_accepts_namespaced_template_shell_syntax_check(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_namespaced_shell")
        root_module.parse_validation_command(
            "sh -n template/.project-agent-workflow/scripts/check-agent-completion.sh"
        )
        root_module.parse_validation_command(
            "python3 -m py_compile .project-agent-workflow/hooks/stop_review_gate.py"
        )

    def test_template_lint_compatibility_uses_exact_v050_bridged_aliases(self) -> None:
        module = load_module(PLAN_COMMAND_MODULES[1], "template_legacy_plan_commands")
        commands = (
            "python3 scripts/check-external-service-policy.py check",
            "python3 scripts/check-codex-toml.py",
            "python3 scripts/lint-plan-docs.py",
            "python3 scripts/format-plan-docs.py --check",
            "python3 scripts/security-static-check.py",
            "python3 scripts/structure-map.py --check",
            "python3 scripts/validate-changes.py --all --print-only --json",
            "sh scripts/lint-plan-docs.sh",
            "sh scripts/format-plan-docs.sh --check",
            "sh scripts/check-agent-completion.sh",
            "scripts/lint-plan-docs.sh",
            "scripts/format-plan-docs.sh --check",
            "scripts/check-agent-completion.sh",
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bridged_paths = sorted(
                {
                    script
                    for command in commands
                    if (script := module.legacy_bridge_script(tuple(command.split()))) is not None
                }
            )
            manifest = repo / ".project-agent-workflow-migration/v1-pre-namespace/manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "bridged_legacy_cli_paths": bridged_paths,
                        "operation": "recopy_adoption",
                        "previous_ref": "v0.5.0",
                    }
                ),
                encoding="utf-8",
            )
            for command in commands:
                argv = tuple(command.split())
                script = module.legacy_bridge_script(argv)
                self.assertIsNotNone(script)
                assert script is not None
                bridge = repo / script
                managed = repo / ".project-agent-workflow/scripts" / bridge.name
                bridge.parent.mkdir(parents=True, exist_ok=True)
                managed.parent.mkdir(parents=True, exist_ok=True)
                managed.write_text("managed helper\n", encoding="utf-8")
                managed.chmod(0o755)
                content = (
                    module.python_bridge_content(bridge.name)
                    if bridge.suffix == ".py"
                    else module.shell_bridge_content(bridge.name)
                )
                bridge.write_text(content, encoding="utf-8")
                bridge.chmod(0o755)

                with self.subTest(compatible=command):
                    module.parse_validation_command(command, legacy_bridge_root=repo)
                    with self.assertRaises(module.ValidationCommandError):
                        module.parse_validation_command(command)

            manifest.write_text(
                json.dumps(
                    {
                        "bridged_legacy_cli_paths": [],
                        "operation": "recopy_adoption",
                        "previous_ref": "v0.5.0",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(module.ValidationCommandError):
                module.parse_validation_command(
                    "python3 scripts/check-codex-toml.py",
                    legacy_bridge_root=repo,
                )
            manifest.write_text(
                json.dumps(
                    {
                        "bridged_legacy_cli_paths": bridged_paths,
                        "operation": "recopy_adoption",
                        "previous_ref": "v0.5.0",
                    }
                ),
                encoding="utf-8",
            )
            modified = repo / "scripts/lint-plan-docs.py"
            modified.write_text(modified.read_text(encoding="utf-8") + "# modified\n", encoding="utf-8")
            with self.assertRaises(module.ValidationCommandError):
                module.parse_validation_command(
                    "python3 scripts/lint-plan-docs.py",
                    legacy_bridge_root=repo,
                )
            with self.assertRaises(module.ValidationCommandError):
                module.parse_validation_command(
                    "python3 scripts/security-static-check.py --changed",
                    legacy_bridge_root=repo,
                )
            with self.assertRaises(module.ValidationCommandError):
                module.parse_validation_command(
                    "python3 scripts/plan_validation_commands.py --self-test",
                    legacy_bridge_root=repo,
                )
            direct_shell = repo / "scripts/check-agent-completion.sh"
            direct_shell.chmod(0o644)
            with self.assertRaises(module.ValidationCommandError):
                module.parse_validation_command(
                    "scripts/check-agent-completion.sh",
                    legacy_bridge_root=repo,
                )

    def test_run_plan_rejects_checked_archive_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            archive = repo / "docs/plan/checked/2026/08/01-15/001-history.md"
            archive.parent.mkdir(parents=True)
            archive.write_text(
                "# History\n\nvalidation:\n  - git diff --check\n\n## Tasks\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(PLAN_COMMAND_MODULES[1]),
                    "run-plan",
                    str(archive),
                ],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("run-plan requires a numbered active plan path", result.stderr)


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
                "authentication: environment\ncredential_reference: CURRENT_TOKEN\n",
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
    def test_generated_workflow_is_namespaced_and_workflow_scoped(self) -> None:
        root_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        workflow = (ROOT / "template/.github/workflows/project-agent-workflow.yml").read_text(encoding="utf-8")
        self.assertIn('git diff --check "$BASE_SHA...$PR_HEAD_SHA"', root_workflow)
        self.assertIn('[ "$REF_TYPE" = tag ]', root_workflow)
        self.assertIn('git diff --check "$HEAD_SHA^..$HEAD_SHA"', root_workflow)
        self.assertIn('git diff --check "$BEFORE_SHA..$HEAD_SHA"', root_workflow)
        self.assertIn('git diff --check "$EMPTY_TREE" "$HEAD_SHA"', root_workflow)
        self.assertIn('name: Project agent workflow', workflow)
        self.assertIn('      - ".project-agent-workflow/**"', workflow)
        self.assertIn('python3 .project-agent-workflow/scripts/lint-plan-docs.py', workflow)
        self.assertIn('python3 .project-agent-workflow/scripts/security-static-check.py --managed', workflow)
        self.assertNotIn('npm run test', workflow)
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

    def test_tag_range_checks_only_the_tagged_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            historical = repo / "historical.md"
            historical.write_text("historical trailing whitespace \n", encoding="utf-8")
            subprocess.run(["git", "add", "historical.md"], cwd=repo, check=True)
            self.commit(repo, "historical")
            (repo / "clean.md").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "clean.md"], cwd=repo, check=True)
            self.commit(repo, "release")

            clean_result = subprocess.run(
                ["git", "diff", "--check", "HEAD^..HEAD"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(clean_result.returncode, 0)

            (repo / "new.md").write_text("new trailing whitespace \n", encoding="utf-8")
            subprocess.run(["git", "add", "new.md"], cwd=repo, check=True)
            self.commit(repo, "bad release")
            bad_result = subprocess.run(
                ["git", "diff", "--check", "HEAD^..HEAD"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(bad_result.returncode, 2)
            self.assertIn("new.md:1: trailing whitespace", bad_result.stdout)

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


class SecurityStaticCheckTest(unittest.TestCase):
    def test_changed_and_managed_scopes_exclude_unchanged_project_fixtures(self) -> None:
        rules = load_module(SECURITY_RULE_MODULE, "security_rules")
        sys.modules["security_rules"] = rules
        module = load_module(SECURITY_CHECK_MODULE, "security_static_check")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = repo / "tests/security-fixture.md"
            fixture.parent.mkdir(parents=True)
            fixture.write_text("curl https://example.invalid/install | sh\n", encoding="utf-8")
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
            managed = repo / ".project-agent-workflow/docs/new.md"
            managed.parent.mkdir(parents=True)
            managed.write_text("managed workflow change\n", encoding="utf-8")
            module.ROOT = repo

            self.assertEqual(module.iter_files("changed"), [managed])
            self.assertEqual(module.iter_files("managed"), [managed])
            self.assertIn(fixture, module.iter_files("repository"))
            fixture.write_text(
                "curl https://example.invalid/install | sh\nchanged fixture\n",
                encoding="utf-8",
            )
            self.assertIn(fixture, module.iter_files("changed"))


class LegacyExternalServiceMigrationTest(unittest.TestCase):
    def test_ambiguous_credential_description_is_preserved_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            policy = repo / "docs/agent/external-services.yaml"
            policy.parent.mkdir(parents=True)
            policy.write_text(
                "external_services:\n  mcp:\n    credential_env: provider-specific credentials\n",
                encoding="utf-8",
            )
            (repo / ".copier-answers.yml").write_text(
                "skillspector_mode: disabled\n",
                encoding="utf-8",
            )
            before = policy.read_text(encoding="utf-8")
            result = subprocess.run(
                ["python3", str(LEGACY_MIGRATOR)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("cannot be represented as one environment-variable reference", result.stderr)
            self.assertEqual(policy.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
