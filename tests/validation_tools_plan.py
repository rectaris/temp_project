"""Plan validation-command tests."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validation_tools_support import PLANLIB, PLAN_COMMAND_MODULES, ROOT, load_module


class PlanValidationCommandsTest(unittest.TestCase):
    def test_planlib_parses_optional_focused_validation_without_requiring_it(self) -> None:
        module = load_module(PLANLIB, "focused_validation_planlib")
        self.assertNotIn("focused_validation", module.LEGACY_REQUIRED_FIELDS)
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
            legacy = Path(tmp) / "legacy-checked.md"
            legacy.write_text(
                "status: checked\n"
                "task_type: planning_docs\n"
                "review_class: B\n"
                "human_design_required: no\n"
                "human_approval_status: not_required\n"
                "target_files:\n  - docs/plan/\n"
                "required_specs:\n  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
                "validation:\n  - git diff --check\n"
                "acceptance:\n  - Preserve the legacy archive.\n"
                "expected_output: Historical record.\n"
                "checked_summary_ja: 旧形式の完了記録。\n\n## Tasks\n",
                encoding="utf-8",
            )
            values = module.require_manifest_fields(legacy, module.LEGACY_REQUIRED_FIELDS)
            self.assertEqual(values["focused_validation"], [])

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
            "git diff --check; rm " + "-rf .",
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



if __name__ == "__main__":
    unittest.main()
