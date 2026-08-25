"""Plan validation-command tests."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import PLANLIB, PLAN_COMMAND_MODULES, ROOT, load_module


class PlanValidationCommandsTest(unittest.TestCase):
    @staticmethod
    def witness_digest(text: str) -> str:
        return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

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

    def test_validation_witness_map_binds_acceptance_to_earliest_declared_stage(self) -> None:
        module = load_module(PLANLIB, "validation_witness_planlib")
        acceptance = "Preserve the bounded behavior."
        digest = self.witness_digest(acceptance)
        values = {
            "status": "in_progress",
            "validation_witness_schema": "1",
            "integration_gates": ["the integration predecessor is checked"],
            "acceptance": [acceptance],
            "focused_validation": ["python3 -m pytest tests/focused.py"],
            "validation": [
                "python3 -m pytest tests/focused.py",
                "git diff --check",
            ],
            "validation_witness_map": [
                json.dumps(
                    {
                        "acceptance_sha256": digest,
                        "stage": "focused",
                        "witness": "python3 -m pytest tests/focused.py",
                    },
                    separators=(",", ":"),
                )
            ],
        }
        records = module.validate_validation_witness_map(values)
        self.assertEqual(records[0]["acceptance_sha256"], digest)

        values["validation_witness_map"] = [
            json.dumps(
                {
                    "acceptance_sha256": digest,
                    "stage": "authoritative",
                    "witness": "git diff --check",
                    "authoritative_only_reason": "requires the complete integrated candidate",
                },
                separators=(",", ":"),
            )
        ]
        self.assertEqual(
            module.validate_validation_witness_map(values)[0]["stage"],
            "authoritative",
        )

    def test_validation_witness_map_rejects_missing_coverage_and_late_witnesses(self) -> None:
        module = load_module(PLANLIB, "invalid_validation_witness_planlib")
        acceptance = "Preserve the bounded behavior."
        digest = self.witness_digest(acceptance)
        base = {
            "status": "in_progress",
            "validation_witness_schema": "1",
            "integration_gates": ["the integration predecessor is checked"],
            "acceptance": [acceptance],
            "focused_validation": ["python3 -m pytest tests/focused.py"],
            "validation": ["python3 -m pytest tests/focused.py"],
            "validation_witness_map": [],
        }
        invalid_maps = (
            [],
            ["not-json"],
            [
                json.dumps(
                    {
                        "acceptance_sha256": "sha256:" + "0" * 64,
                        "stage": "focused",
                        "witness": "python3 -m pytest tests/focused.py",
                    }
                )
            ],
            [
                json.dumps(
                    {
                        "acceptance_sha256": digest,
                        "stage": "authoritative",
                        "witness": "python3 -m pytest tests/focused.py",
                        "authoritative_only_reason": "complete suite only",
                    }
                )
            ],
            [
                json.dumps(
                    {
                        "acceptance_sha256": digest,
                        "stage": "authoritative",
                        "witness": "git diff --check",
                    }
                )
            ],
        )
        for witness_map in invalid_maps:
            with self.subTest(witness_map=witness_map):
                values = {**base, "validation_witness_map": witness_map}
                with self.assertRaises(module.PlanError):
                    module.validate_validation_witness_map(values)

    def test_plan_command_check_rejects_open_integration_plan_without_witness_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "docs/plan/active/991-integration.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                "status: in_progress\n"
                "validation_witness_schema: 1\n"
                "integration_gates:\n  - predecessor is checked\n"
                "validation:\n  - git diff --check\n"
                "acceptance:\n  - Preserve the integration.\n\n## Tasks\n",
                encoding="utf-8",
            )
            for index, module_path in enumerate(PLAN_COMMAND_MODULES):
                with self.subTest(module=module_path):
                    command_module = load_module(module_path, f"missing_witness_commands_{index}")
                    with self.assertRaises(command_module.ValidationCommandError):
                        command_module.check_plan(plan)

            legacy_text = (
                "status: in_progress\n"
                "replan_contract: docs/plan/replanned/contracts/990-source.json\n"
                "integration_gates:\n  - preserved predecessor is checked\n"
                "validation:\n  - git diff --check\n"
                "acceptance:\n  - Preserve the pre-schema integration plan.\n\n## Tasks\n"
            )
            plan.write_text(legacy_text, encoding="utf-8")
            archive = root / "docs/plan/replanned/2026/08/16-31/990-source.md"
            archive.parent.mkdir(parents=True)
            archive.write_text("status: replanned\n", encoding="utf-8")
            contract = root / "docs/plan/replanned/contracts/990-source.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "contract_path": "docs/plan/replanned/contracts/990-source.json",
                        "archive_path": "docs/plan/replanned/2026/08/16-31/990-source.md",
                        "successors": [
                            {
                                "path": "docs/plan/active/991-integration.md",
                                "content_digest": self.witness_digest(legacy_text),
                                "acceptance_digests": [
                                    self.witness_digest("Preserve the pre-schema integration plan.")
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            for index, module_path in enumerate(PLAN_COMMAND_MODULES):
                with self.subTest(legacy_module=module_path):
                    command_module = load_module(module_path, f"legacy_witness_commands_{index}")
                    command_module.check_plan(plan)

            plan.write_text(legacy_text.replace("Preserve", "Alter"), encoding="utf-8")
            for index, module_path in enumerate(PLAN_COMMAND_MODULES):
                with self.subTest(mutated_legacy_module=module_path):
                    command_module = load_module(module_path, f"mutated_legacy_commands_{index}")
                    with self.assertRaises(command_module.ValidationCommandError):
                        command_module.check_plan(plan)

    def test_static_witness_requires_its_concrete_context_predicate(self) -> None:
        module = load_module(PLANLIB, "static_validation_witness_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "docs/plan/active/991-integration.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text("status: in_progress\n", encoding="utf-8")
            context = root / "docs/agent/SPEC_PLAN_WORKFLOW.md"
            context.parent.mkdir(parents=True)
            context.write_text("policy\n", encoding="utf-8")
            acceptance = "Use resolved context files."
            record = {
                "acceptance_sha256": self.witness_digest(acceptance),
                "stage": "static",
                "witness": "resolved-context-files",
            }
            values = {
                "status": "in_progress",
                "validation_witness_schema": "1",
                "integration_gates": ["the context input is resolved"],
                "context_files": ["docs/agent/SPEC_PLAN_WORKFLOW.md"],
                "acceptance": [acceptance],
                "focused_validation": [],
                "validation": ["git diff --check"],
                "validation_witness_map": [json.dumps(record, separators=(",", ":"))],
            }
            self.assertEqual(
                module.validate_validation_witness_map(values, plan_path=plan_path)[0]["witness"],
                "resolved-context-files",
            )

            record["witness"] = "plan-manifest"
            values["validation_witness_map"] = [json.dumps(record, separators=(",", ":"))]
            with self.assertRaises(module.PlanError):
                module.validate_validation_witness_map(values, plan_path=plan_path)

            record["witness"] = "resolved-context-files"
            invalid_contexts = (
                ["docs/agent/DOES_NOT_EXIST.md"],
                ["docs/agent/../agent/SPEC_PLAN_WORKFLOW.md"],
            )
            for context_files in invalid_contexts:
                with self.subTest(context_files=context_files):
                    values["context_files"] = context_files
                    values["validation_witness_map"] = [
                        json.dumps(record, separators=(",", ":"))
                    ]
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(values, plan_path=plan_path)

            symlink = root / "docs/agent/LINK.md"
            symlink.symlink_to(context.name)
            values["context_files"] = ["docs/agent/LINK.md"]
            with self.assertRaises(module.PlanError):
                module.validate_validation_witness_map(values, plan_path=plan_path)

            checked = root / "docs/plan/checked/2026/08/16-31/990-source.md"
            checked.parent.mkdir(parents=True)
            checked.write_text("status: in_progress\n", encoding="utf-8")
            values["context_files"] = [
                "docs/plan/checked/2026/08/16-31/990-source.md"
            ]
            with self.assertRaises(module.PlanError):
                module.validate_validation_witness_map(values, plan_path=plan_path)

    def test_copier_update_uses_one_copy_and_stage_inventory(self) -> None:
        inventory_path = ROOT / "tests/fixtures/orchestration/copier-update-source-inventory.txt"
        entries = inventory_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(entries)
        self.assertEqual(len(entries), len(set(entries)))
        root = ROOT.resolve()
        for entry in entries:
            with self.subTest(entry=entry):
                path = Path(entry)
                self.assertTrue(entry)
                self.assertEqual(entry, path.as_posix())
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertNotIn("\\", entry)
                target = ROOT / path
                self.assertTrue(target.is_file())
                self.assertFalse(target.is_symlink())
                target.resolve().relative_to(root)
        script = (ROOT / "tests/copier-update.sh").read_text(encoding="utf-8")
        self.assertEqual(script.count("copier-update-source-inventory.txt"), 1)
        self.assertNotIn('fixture_git "$update_source" add \\\n', script)
        self.assertIn('fixture_git "$update_source" add -- "$candidate_path"', script)

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

    def test_active_predecessor_graph_requires_exact_checked_refresh(self) -> None:
        module = load_module(PLANLIB, "active_predecessor_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "docs/plan/active"
            checked = root / "docs/plan/checked/2026/08/16-31"
            active.mkdir(parents=True)
            checked.mkdir(parents=True)
            module.ROOT = root
            module.PLAN = root / "docs/plan/plan.md"
            module.CHECKED = root / "docs/plan/checked.md"
            module.ACTIVE_DIR = active
            first = "docs/plan/active/001-first.md"
            second = "docs/plan/active/002-second.md"
            (root / first).write_text("status: in_progress\n\n## Tasks\n", encoding="utf-8")
            (root / second).write_text(
                "status: deferred\n"
                "predecessor_plans:\n"
                f"  - {first}\n\n## Tasks\n",
                encoding="utf-8",
            )
            module.PLAN.write_text(
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"001\t{first}\tin_progress\n"
                f"002\t{second}\tdeferred\n",
                encoding="utf-8",
            )
            module.CHECKED.write_text(
                "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
            )
            module.validate_active_plan_predecessors()

            (root / second).write_text(
                (root / second).read_text(encoding="utf-8").replace(
                    "status: deferred", "status: in_progress"
                ),
                encoding="utf-8",
            )
            module.PLAN.write_text(
                module.PLAN.read_text(encoding="utf-8").replace(
                    f"002\t{second}\tdeferred", f"002\t{second}\tin_progress"
                ),
                encoding="utf-8",
            )
            with self.assertRaises(module.PlanError):
                module.check_active_mapping("002", second, "in_progress")
            with self.assertRaises(module.PlanError):
                module.validate_active_plan_predecessors()

            checked_first = "docs/plan/checked/2026/08/16-31/001-first.md"
            (root / checked_first).write_text(
                "status: checked\n\n## Tasks\n", encoding="utf-8"
            )
            (root / first).unlink()
            module.CHECKED.write_text(
                "# Checked Plan Index\n\nid\tpath\n"
                f"001\t{checked_first}\n",
                encoding="utf-8",
            )
            module.PLAN.write_text(
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"002\t{second}\tdeferred\n",
                encoding="utf-8",
            )
            (root / second).write_text(
                "status: deferred\n"
                "predecessor_plans:\n"
                f"  - {first}\n\n## Tasks\n",
                encoding="utf-8",
            )
            module.validate_active_plan_predecessors()
            with self.assertRaises(module.PlanError):
                module.require_predecessors_checked(root / second)

            (root / second).write_text(
                "status: in_progress\n"
                "predecessor_plans:\n"
                f"  - {checked_first}\n\n## Tasks\n",
                encoding="utf-8",
            )
            module.PLAN.write_text(
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"002\t{second}\tin_progress\n",
                encoding="utf-8",
            )
            module.require_predecessors_checked(root / second)
            module.check_active_mapping("002", second, "in_progress")
            module.validate_active_plan_predecessors()

    def test_active_predecessors_reject_cycles_duplicates_and_cross_id_paths(self) -> None:
        module = load_module(PLANLIB, "invalid_active_predecessor_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "docs/plan/active"
            active.mkdir(parents=True)
            module.ROOT = root
            module.PLAN = root / "docs/plan/plan.md"
            module.CHECKED = root / "docs/plan/checked.md"
            module.ACTIVE_DIR = active
            first = "docs/plan/active/001-first.md"
            second = "docs/plan/active/002-second.md"
            module.PLAN.write_text(
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"001\t{first}\tdeferred\n"
                f"002\t{second}\tdeferred\n",
                encoding="utf-8",
            )
            module.CHECKED.write_text(
                "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
            )
            (root / first).write_text(
                "status: deferred\npredecessor_plans:\n"
                f"  - {second}\n\n## Tasks\n",
                encoding="utf-8",
            )
            (root / second).write_text(
                "status: deferred\npredecessor_plans:\n"
                f"  - {first}\n\n## Tasks\n",
                encoding="utf-8",
            )
            with self.assertRaises(module.PlanError):
                module.validate_active_plan_predecessors()

            duplicate_values = {
                "predecessor_plans": [first, first],
            }
            with self.assertRaises(module.PlanError):
                module.validate_predecessor_list(duplicate_values, second)

            wrong = "docs/plan/checked/2026/08/16-31/001-first.md"
            module.CHECKED.write_text(
                "# Checked Plan Index\n\nid\tpath\n"
                f"999\t{wrong}\n",
                encoding="utf-8",
            )
            (root / wrong).parent.mkdir(parents=True, exist_ok=True)
            (root / wrong).write_text("status: checked\n", encoding="utf-8")
            (root / second).write_text(
                "status: in_progress\npredecessor_plans:\n"
                f"  - {wrong}\n\n## Tasks\n",
                encoding="utf-8",
            )
            module.PLAN.write_text(
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"002\t{second}\tin_progress\n",
                encoding="utf-8",
            )
            with self.assertRaises(module.PlanError):
                module.validate_active_plan_predecessors()

    def test_successor_lineage_does_not_create_an_execution_dependency(self) -> None:
        module = load_module(PLANLIB, "successor_lineage_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "docs/plan/active"
            active.mkdir(parents=True)
            module.ROOT = root
            module.PLAN = root / "docs/plan/plan.md"
            module.CHECKED = root / "docs/plan/checked.md"
            module.ACTIVE_DIR = active
            plan = "docs/plan/active/001-first.md"
            (root / plan).write_text(
                "status: in_progress\n"
                "successor_plans:\n"
                "  - docs/plan/active/002-history.md\n\n## Tasks\n",
                encoding="utf-8",
            )
            module.PLAN.write_text(
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"001\t{plan}\tin_progress\n",
                encoding="utf-8",
            )
            module.CHECKED.write_text(
                "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
            )
            module.validate_active_plan_predecessors()

    def test_add_active_remains_a_pure_index_registration_operation(self) -> None:
        module = load_module(PLANLIB, "add_active_index_planlib")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/plan").mkdir(parents=True)
            module.ROOT = root
            module.PLAN = root / "docs/plan/plan.md"
            module.CHECKED = root / "docs/plan/checked.md"
            module.ACTIVE_DIR = root / "docs/plan/active"
            module.add_active(
                "006",
                "docs/plan/active/006-promotion-index.md",
            )
            self.assertEqual(
                module.read_active_rows(),
                [
                    (
                        "006",
                        "docs/plan/active/006-promotion-index.md",
                        "in_progress",
                    )
                ],
            )

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
            "python3 tests/test-verify-copier-update.py",
            "python3 scripts/run-sandboxed-plan-worker.py self-test",
            "python3 scripts/check-copier-template.py",
            "tests/copier-update.sh --require-copier",
        ):
            with self.subTest(command=command):
                root_module.parse_validation_command(command)

        template_module = load_module(PLAN_COMMAND_MODULES[1], "template_root_only_behavior_test")
        with self.assertRaises(template_module.ValidationCommandError):
            template_module.parse_validation_command("python3 tests/test-verify-copier-update.py")

    def test_root_accepts_exact_reconstructed_plan_commands(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_reconstructed_plan_commands")
        for command in (
            "python3 scripts/restructure-plan.py --verify",
            "python3 tests/test-copier-fixture.py",
            "python3 -m py_compile "
            "scripts/project_workflow/copier_fixture.py tests/test-copier-fixture.py",
            "python3 scripts/project_workflow/copier_fixture.py --check tests/copier-update.sh",
        ):
            with self.subTest(command=command):
                root_module.parse_validation_command(command)

    def test_root_rejects_reconstructed_plan_command_near_matches(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_reconstructed_plan_near_matches")
        for command in (
            "python3 scripts/restructure-plan.py",
            "python3 scripts/restructure-plan.py --verify extra",
            "python3 scripts/restructure_plan.py --verify",
            "python scripts/restructure-plan.py --verify",
            "python3 --verify scripts/restructure-plan.py",
            "python3 tests/test-copier-fixture.py --verbose",
            "python3 tests/copier-fixture.py",
            "python tests/test-copier-fixture.py",
            "python3 -m py_compile tests/test-copier-fixture.py "
            "scripts/project_workflow/copier_fixture.py",
            "python3 -m py_compile scripts/project_workflow/copier_fixture.py",
            "python3 -m py_compile scripts/project_workflow/copier_fixture.py "
            "tests/test-copier-fixture.py tests/other.py",
            "python3 -m py_compile scripts/project_workflow/other.py "
            "tests/test-copier-fixture.py",
            "python3 -m py_compile ./scripts/project_workflow/copier_fixture.py "
            "./tests/test-copier-fixture.py",
            "python3 -m py_compile ./scripts/project_workflow/copier_fixture.py "
            "./tests/test-copier-fixture.py tests/other.py",
            "python3 -m py_compile ./tests/test-copier-fixture.py "
            "./scripts/project_workflow/copier_fixture.py",
            "python -m py_compile scripts/project_workflow/copier_fixture.py "
            "tests/test-copier-fixture.py",
            "python3 scripts/project_workflow/copier_fixture.py --check",
            "python3 scripts/project_workflow/copier_fixture.py --check tests/other.sh",
            "python3 scripts/project_workflow/copier_fixture.py "
            "tests/copier-update.sh --check",
            "python3 scripts/project_workflow/copier_fixture.py "
            "--check tests/copier-update.sh extra",
            "python scripts/project_workflow/copier_fixture.py --check tests/copier-update.sh",
            "python3 scripts/restructure-plan.py --verify; git diff --check",
        ):
            with self.subTest(command=command):
                with self.assertRaises(root_module.ValidationCommandError):
                    root_module.parse_validation_command(command)

    def test_generated_policy_keeps_root_only_commands_out(self) -> None:
        template_module = load_module(
            PLAN_COMMAND_MODULES[1],
            "template_reconstructed_plan_commands",
        )
        for command in (
            "python3 scripts/restructure-plan.py --verify",
            "python3 tests/test-copier-fixture.py",
            "python3 scripts/project_workflow/copier_fixture.py --check tests/copier-update.sh",
        ):
            with self.subTest(command=command):
                with self.assertRaises(template_module.ValidationCommandError):
                    template_module.parse_validation_command(command)

        template_module.parse_validation_command(
            "python3 -m py_compile "
            ".project-agent-workflow/scripts/example.py tests/example.py"
        )

    def test_root_accepts_exact_decomposed_shell_validation_commands(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_decomposed_shell_commands")
        for command in (
            "python3 tests/test-shell-lexical.py",
            "python3 tests/test-shell-functions.py",
            "python3 tests/test-shell-execution.py",
            "python3 tests/test-copier-fixture-validator.py",
            "python3 scripts/project_workflow/copier_fixture_validator.py "
            "--check tests/copier-update.sh",
            "python3 -m py_compile "
            "scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py",
            "python3 -m py_compile "
            "scripts/project_workflow/shell_functions.py tests/test-shell-functions.py",
            "python3 -m py_compile "
            "scripts/project_workflow/shell_execution.py tests/test-shell-execution.py",
            "python3 -m py_compile "
            "scripts/project_workflow/copier_fixture_validator.py "
            "tests/test-copier-fixture-validator.py",
            "python3 -m py_compile "
            "scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py "
            "scripts/project_workflow/shell_functions.py tests/test-shell-functions.py "
            "scripts/project_workflow/shell_execution.py tests/test-shell-execution.py "
            "scripts/project_workflow/copier_fixture_validator.py "
            "tests/test-copier-fixture-validator.py",
        ):
            with self.subTest(command=command):
                root_module.parse_validation_command(command)

    def test_root_rejects_decomposed_shell_command_near_matches(self) -> None:
        root_module = load_module(PLAN_COMMAND_MODULES[0], "root_decomposed_shell_near_matches")
        for command in (
            "python3 tests/test-shell-lexical.py --verbose",
            "python tests/test-shell-lexical.py",
            "python3 tests/shell-lexical.py",
            "python3 tests/test-shell-functions.py extra",
            "python tests/test-shell-functions.py",
            "python3 tests/test-shell-execution.py --all",
            "python tests/test-shell-execution.py",
            "python3 tests/test-copier-fixture-validator.py --check",
            "python tests/test-copier-fixture-validator.py",
            "python3 tests/copier-fixture-validator.py",
            "python3 scripts/project_workflow/copier_fixture_validator.py --check",
            "python3 scripts/project_workflow/copier_fixture_validator.py "
            "--check tests/other.sh",
            "python3 scripts/project_workflow/copier_fixture_validator.py "
            "tests/copier-update.sh --check",
            "python3 scripts/project_workflow/copier_fixture_validator.py "
            "--check tests/copier-update.sh extra",
            "python scripts/project_workflow/copier_fixture_validator.py "
            "--check tests/copier-update.sh",
            "python3 -m py_compile tests/test-shell-lexical.py "
            "scripts/project_workflow/shell_lexical.py",
            "python3 -m py_compile scripts/project_workflow/shell_lexical.py",
            "python3 -m py_compile scripts/project_workflow/shell_lexical.py "
            "tests/test-shell-lexical.py tests/other.py",
            "python3 -m py_compile ./scripts/project_workflow/shell_lexical.py "
            "./tests/test-shell-lexical.py",
            "python -m py_compile scripts/project_workflow/shell_lexical.py "
            "tests/test-shell-lexical.py",
            "python3 -m py_compile scripts/project_workflow/shell_functions.py",
            "python3 -m py_compile scripts/project_workflow/shell_execution.py",
            "python3 -m py_compile scripts/project_workflow/copier_fixture_validator.py",
            "python3 -m py_compile "
            "scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py "
            "scripts/project_workflow/shell_functions.py tests/test-shell-functions.py "
            "scripts/project_workflow/shell_execution.py tests/test-shell-execution.py",
            "python3 -m py_compile "
            "scripts/project_workflow/shell_functions.py tests/test-shell-functions.py "
            "scripts/project_workflow/shell_lexical.py tests/test-shell-lexical.py "
            "scripts/project_workflow/shell_execution.py tests/test-shell-execution.py "
            "scripts/project_workflow/copier_fixture_validator.py "
            "tests/test-copier-fixture-validator.py",
        ):
            with self.subTest(command=command):
                with self.assertRaises(root_module.ValidationCommandError):
                    root_module.parse_validation_command(command)

    def test_generated_policy_rejects_decomposed_root_only_commands(self) -> None:
        template_module = load_module(
            PLAN_COMMAND_MODULES[1],
            "template_decomposed_shell_commands",
        )
        for command in (
            "python3 tests/test-shell-lexical.py",
            "python3 tests/test-shell-functions.py",
            "python3 tests/test-shell-execution.py",
            "python3 tests/test-copier-fixture-validator.py",
            "python3 scripts/project_workflow/copier_fixture_validator.py "
            "--check tests/copier-update.sh",
        ):
            with self.subTest(command=command):
                with self.assertRaises(template_module.ValidationCommandError):
                    template_module.parse_validation_command(command)

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

    def test_template_compiles_only_the_exact_generated_copier_verification_helper(self) -> None:
        template_module = load_module(PLAN_COMMAND_MODULES[1], "template_copier_helper_compile")
        helper = (
            ".project-agent-workflow/skills/verify-copier-update/"
            "scripts/verify-copier-update.py"
        )

        template_module.parse_validation_command(f"python3 -m py_compile {helper}")

        for path in (
            ".project-agent-workflow/skills/other/scripts/verify-copier-update.py",
            ".project-agent-workflow/skills/verify-copier-update/scripts/other.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(template_module.ValidationCommandError):
                    template_module.parse_validation_command(f"python3 -m py_compile {path}")

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
