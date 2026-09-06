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
    ROOT_POLICY = ROOT / "scripts/check-root-agent-policy.py"
    GROUP_AUTHORITY = ROOT / "scripts/parallel-plan-state.py"

    @staticmethod
    def group_digest(value) -> str:
        data = value if isinstance(value, bytes) else str(value).encode("utf-8")
        return "sha256:" + hashlib.sha256(data).hexdigest()

    def build_group_fixture(self, directory: Path, *, statuses=("in_progress", "in_progress")):
        """Create a minimal repository with one valid two-member execution group."""

        (directory / "docs/plan/active").mkdir(parents=True)
        (directory / "docs/plan/execution-groups").mkdir(parents=True)
        (directory / "scripts").mkdir(parents=True)
        (directory / "scripts/parallel-plan-state.py").write_bytes(
            self.GROUP_AUTHORITY.read_bytes()
        )
        subprocess.run(["git", "init", "-q", "-b", "main", str(directory)], check=True)
        subprocess.run(["git", "-C", str(directory), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(directory), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        members = []
        rows = []
        for index, (plan_id, slug, scope) in enumerate(
            (("284", "alpha", "src/alpha.py"), ("285", "beta", "src/beta.py"))
        ):
            relative = f"docs/plan/active/{plan_id}-{slug}.md"
            body = (
                f"# Plan {plan_id}\n\n"
                f"status: {statuses[index]}\n"
                "plan_purpose: implementation\n"
                f"primary_invariant: invariant {plan_id}\n"
                "execution_group: docs/plan/execution-groups/alpha-beta.json\n"
                f"write_scope:\n  - {scope}\n"
                "context_files:\n  - AGENTS.md\n"
                "\n## Tasks\n\n- [ ] implement\n"
            )
            (directory / relative).write_text(body, encoding="utf-8")
            members.append(
                {
                    "plan_id": plan_id,
                    "plan_path": relative,
                    "plan_digest": self.group_digest(body.encode("utf-8")),
                    "write_scope_digest": self.group_digest(
                        json.dumps([scope], sort_keys=True, separators=(",", ":"))
                    ),
                }
            )
            rows.append(f"{plan_id}\t{relative}\t{statuses[index]}")
        description = {
            "schema_version": 1,
            "group_id": "alpha-beta",
            "target_ref": "refs/heads/main",
            "declared_independence": "disjoint modules with no shared interface",
            "members": members,
        }
        (directory / "docs/plan/execution-groups/alpha-beta.json").write_text(
            json.dumps(description, indent=2) + "\n", encoding="utf-8"
        )
        (directory / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nid\tpath\tstatus\n" + "\n".join(rows) + "\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(directory), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(directory), "commit", "-qm", "fixture"], check=True)
        return description

    def load_root_policy(self, directory: Path):
        module = load_module(self.ROOT_POLICY, f"root_policy_{directory.name}")
        module.ROOT = directory
        return module

    def rewrite_group(self, directory: Path, description) -> None:
        (directory / "docs/plan/execution-groups/alpha-beta.json").write_text(
            json.dumps(description, indent=2) + "\n", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(directory), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(directory), "commit", "-qm", "update"], check=True)

    def test_root_policy_accepts_a_valid_execution_group(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            self.build_group_fixture(directory)
            module = self.load_root_policy(directory)
            module.check_execution_groups()
            self.assertEqual(
                sorted(module.execution_group_members()),
                [
                    "docs/plan/active/284-alpha.md",
                    "docs/plan/active/285-beta.md",
                ],
            )

    def test_root_policy_rejects_a_manifest_group_reference_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            description = self.build_group_fixture(directory)
            plan = directory / "docs/plan/active/284-alpha.md"
            text = plan.read_text(encoding="utf-8").replace(
                "execution_group: docs/plan/execution-groups/alpha-beta.json",
                "execution_group: docs/plan/execution-groups/absent.json",
            )
            plan.write_text(text, encoding="utf-8")
            description["members"][0]["plan_digest"] = self.group_digest(
                text.encode("utf-8")
            )
            self.rewrite_group(directory, description)
            module = self.load_root_policy(directory)
            with self.assertRaises(SystemExit):
                module.check_execution_groups()

    def test_root_policy_rejects_non_description_files_in_the_group_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            self.build_group_fixture(directory)
            (directory / "docs/plan/execution-groups/notes.md").write_text(
                "notes\n", encoding="utf-8"
            )
            module = self.load_root_policy(directory)
            with self.assertRaises(SystemExit):
                module.check_execution_groups()

    def test_root_policy_rejects_an_invalid_group_description(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            description = self.build_group_fixture(directory)
            description["members"][1]["write_scope_digest"] = self.group_digest("wrong")
            self.rewrite_group(directory, description)
            module = self.load_root_policy(directory)
            with self.assertRaises(SystemExit):
                module.check_execution_groups()

    def test_multiple_runnable_rows_need_exact_group_membership(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            self.build_group_fixture(directory)
            module = self.load_root_policy(directory)
            module.check_active_plans()

    def test_multiple_runnable_rows_stay_ambiguous_without_a_group(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            self.build_group_fixture(directory)
            for path in (directory / "docs/plan/execution-groups").iterdir():
                path.unlink()
            for plan_id, slug in (("284", "alpha"), ("285", "beta")):
                plan = directory / f"docs/plan/active/{plan_id}-{slug}.md"
                plan.write_text(
                    plan.read_text(encoding="utf-8").replace(
                        "execution_group: docs/plan/execution-groups/alpha-beta.json\n",
                        "",
                    ),
                    encoding="utf-8",
                )
            subprocess.run(["git", "-C", str(directory), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(directory), "commit", "-qm", "ungrouped"], check=True
            )
            module = self.load_root_policy(directory)
            with self.assertRaises(SystemExit):
                module.check_active_plans()

    def test_runnable_rows_must_cover_every_group_member(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "repo"
            directory.mkdir()
            self.build_group_fixture(directory)
            index = directory / "docs/plan/plan.md"
            plan = directory / "docs/plan/active/290-solo.md"
            plan.write_text(
                "# Plan 290\n\nstatus: in_progress\n"
                "plan_purpose: implementation\n"
                "primary_invariant: invariant 290\n"
                "write_scope:\n  - src/solo.py\n"
                "context_files:\n  - AGENTS.md\n"
                "\n## Tasks\n\n- [ ] implement\n",
                encoding="utf-8",
            )
            index.write_text(
                index.read_text(encoding="utf-8")
                + "290\tdocs/plan/active/290-solo.md\tin_progress\n",
                encoding="utf-8",
            )
            module = self.load_root_policy(directory)
            with self.assertRaises(SystemExit):
                module.check_active_plans()

    def test_execution_group_is_a_recognized_manifest_scalar(self) -> None:
        root_policy = load_module(self.ROOT_POLICY, "root_policy_scalars")
        self.assertIn("execution_group", root_policy.ADMISSION_SCALAR_KEYS)
        planlib = load_module(PLANLIB, "planlib_group_scalar")
        self.assertIn("execution_group", planlib.SCALAR_KEYS)

    def test_root_semantic_test_commands_accept_only_fixed_invocations(self) -> None:
        module = load_module(ROOT / "scripts/plan_validation_commands.py", "root_semantic_commands")
        for script in ("tests/test-referent-contract.py", "tests/test-hooks.py"):
            command = f"python3 {script}"
            module.parse_validation_command(command)
            for suffix in (" --help", " extra", " ; true", " && true", " | cat"):
                with self.subTest(command=command + suffix):
                    with self.assertRaises(module.ValidationCommandError):
                        module.parse_validation_command(command + suffix)

    MIGRATION_POLICY = ".project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
    MIGRATION_RECORD = (
        ".project-agent-workflow-migration/validation-witness-provenance-v1.json"
    )

    @staticmethod
    def witness_digest(text: str) -> str:
        return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def compact_digest(value: object) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    @classmethod
    def indented_json(cls, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    @classmethod
    def indented_digest(cls, value: object) -> str:
        return cls.witness_digest(cls.indented_json(value))

    def write_pre_schema_project(self, root: Path) -> str:
        """Build a pre-schema integration plan with its captured migration evidence."""

        plan_relative = "docs/plan/active/991-integration.md"
        contract_relative = "docs/plan/replanned/contracts/990-source.json"
        archive_relative = "docs/plan/replanned/2026/08/16-31/990-source.md"
        acceptance = "Preserve the pre-schema integration plan."
        archive_text = "status: replanned\n"
        validation = ["git diff --check"]
        plan_text = (
            "status: in_progress\n"
            f"replan_contract: {contract_relative}\n"
            "integration_gates:\n  - preserved predecessor is checked\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n  - {acceptance}\n\n## Tasks\n"
        )

        def write(relative: str, text: str) -> None:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        write(plan_relative, plan_text)
        write(archive_relative, archive_text)
        write(
            self.MIGRATION_POLICY,
            "validation-witness-migration-provenance-schema: 1\n",
        )
        contract_text = self.indented_json(
            {
                "archive_path": archive_relative,
                "contract_path": contract_relative,
                "schema_version": 1,
                "successors": [
                    {
                        "acceptance_digests": [self.witness_digest(acceptance)],
                        "content": plan_text,
                        "content_digest": self.witness_digest(plan_text),
                        "integration": True,
                        "path": plan_relative,
                    }
                ],
            }
        )
        write(contract_relative, contract_text)
        write(
            self.MIGRATION_RECORD,
            self.indented_json(
                {
                    "copier_answers": {
                        "path": ".copier-answers.yml",
                        "previous_template_ref": "v1.4.4",
                        "sha256": self.witness_digest("_commit: v1.4.4\n"),
                    },
                    "migration_version": "v1.4.5",
                    "operation": "validation_witness_migration_snapshot",
                    "plans": [
                        {
                            "acceptance": [
                                {
                                    "sha256": self.witness_digest(acceptance),
                                    "text": acceptance,
                                }
                            ],
                            "path": plan_relative,
                            "plan_sha256": self.witness_digest(plan_text),
                            "replan_contract": {
                                "path": contract_relative,
                                "schema_version": 1,
                                "sha256": self.witness_digest(contract_text),
                            },
                            "replanned_source": {
                                "path": archive_relative,
                                "sha256": self.witness_digest(archive_text),
                            },
                            "validation": validation,
                            "validation_sha256": self.indented_digest(validation),
                        }
                    ],
                    "pre_update_policy": {
                        "path": self.MIGRATION_POLICY,
                        "sha256": self.witness_digest("orchestration policy\n"),
                    },
                    "schema_version": 1,
                    "source_head": "0" * 40,
                }
            ),
        )
        return plan_text

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

    def admission_plan_text(self, **overrides: str) -> str:
        """Render one admitted numbered plan manifest with optional field overrides."""

        conditions = [
            "Refuse a numbered plan without bounded feasibility evidence.",
            "Bind every completion condition to one focused witness.",
        ]
        fields = {
            "plan_purpose": "plan_purpose: implementation\n",
            "feasibility_evidence": (
                "feasibility_evidence:\n"
                '  - {"kind":"existing_mechanism","evidence":"planlib already parses plan manifests."}\n'
            ),
            "completion_conditions": (
                "completion_conditions:\n" + "".join(f"  - {item}\n" for item in conditions)
            ),
            "completion_witness_map": (
                "completion_witness_map:\n"
                + "".join(
                    '  - {"condition_sha256":"%s","witness":"python3 tests/focused.py"}\n'
                    % self.witness_digest(item)
                    for item in conditions
                )
            ),
            "write_scope": "write_scope:\n  - scripts/tool.py\n",
            "focused_validation": "focused_validation:\n  - python3 tests/focused.py\n",
        }
        fields.update(overrides)
        return (
            "status: in_progress\n"
            + "".join(fields[key] for key in fields)
            + "validation:\n  - git diff --check\n\n## Tasks\n"
        )

    def test_planlib_admits_a_bounded_implementation_plan(self) -> None:
        module = load_module(PLANLIB, "admission_planlib")
        for field in (
            "plan_purpose",
            "feasibility_evidence",
            "completion_conditions",
            "completion_witness_map",
        ):
            self.assertIn(field, module.ADMISSION_FIELDS)
            self.assertNotIn(field, module.REQUIRED_FIELDS)
            self.assertNotIn(field, module.LEGACY_REQUIRED_FIELDS)
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(self.admission_plan_text(), encoding="utf-8")
            values = module.parse_manifest(plan)
            self.assertTrue(module.has_admission_record(values))
            records = module.validate_admission_record(values)
            self.assertEqual([record["witness"] for record in records], [
                "python3 tests/focused.py", "python3 tests/focused.py"
            ])

    def test_planlib_rejects_every_admission_mutation(self) -> None:
        module = load_module(PLANLIB, "admission_mutation_planlib")
        conditions = [
            "Refuse a numbered plan without bounded feasibility evidence.",
            "Bind every completion condition to one focused witness.",
        ]
        mutations = {
            "unsupported purpose": {"plan_purpose": "plan_purpose: investigation\n"},
            "placeholder purpose": {"plan_purpose": "plan_purpose: TBD\n"},
            "unsupported evidence kind": {
                "feasibility_evidence": (
                    "feasibility_evidence:\n"
                    '  - {"kind":"future_plan","evidence":"A separate plan will prove this."}\n'
                )
            },
            "placeholder evidence": {
                "feasibility_evidence": (
                    'feasibility_evidence:\n  - {"kind":"existing_mechanism","evidence":"TBD"}\n'
                )
            },
            "missing evidence": {"feasibility_evidence": "feasibility_evidence:\n  - none\n"},
            "oversized evidence": {
                "feasibility_evidence": (
                    'feasibility_evidence:\n  - {"kind":"existing_mechanism","evidence":"%s"}\n'
                    % ("e" * 401)
                )
            },
            "placeholder condition": {
                "completion_conditions": "completion_conditions:\n  - TODO\n"
            },
            "reordered witness map": {
                "completion_witness_map": (
                    "completion_witness_map:\n"
                    + "".join(
                        '  - {"condition_sha256":"%s","witness":"python3 tests/focused.py"}\n'
                        % self.witness_digest(item)
                        for item in reversed(conditions)
                    )
                )
            },
            "missing witness coverage": {
                "completion_witness_map": (
                    'completion_witness_map:\n  - {"condition_sha256":"%s","witness":"python3 tests/focused.py"}\n'
                    % self.witness_digest(conditions[0])
                )
            },
            "authoritative witness": {
                "completion_witness_map": (
                    "completion_witness_map:\n"
                    + "".join(
                        '  - {"condition_sha256":"%s","witness":"git diff --check"}\n'
                        % self.witness_digest(item)
                        for item in conditions
                    )
                )
            },
            "plan lifecycle only scope": {
                "write_scope": "write_scope:\n  - docs/plan/active/900-record.md\n"
            },
            "placeholder scope": {"write_scope": "write_scope:\n  - TBD\n"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            for label, overrides in mutations.items():
                with self.subTest(mutation=label):
                    plan.write_text(self.admission_plan_text(**overrides), encoding="utf-8")
                    values = module.parse_manifest(plan)
                    with self.assertRaises(module.PlanError):
                        module.validate_admission_record(values)

    def test_lint_keeps_pre_policy_plans_readable_and_checks_admission_on_demand(self) -> None:
        lint = ROOT / "template/.project-agent-workflow/scripts/lint-plan-docs.py"
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "legacy.md"
            legacy.write_text(
                "status: backlog\nwrite_scope:\n  - scripts/tool.py\n"
                "validation:\n  - git diff --check\n"
                "acceptance:\n  - Preserve the pre-policy backlog plan.\n\n## Tasks\n",
                encoding="utf-8",
            )
            refused = subprocess.run(
                [sys.executable, str(lint), "--check-admission", str(legacy)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("plan_purpose", refused.stdout + refused.stderr)
            admitted = Path(tmp) / "admitted.md"
            admitted.write_text(self.admission_plan_text(), encoding="utf-8")
            accepted = subprocess.run(
                [sys.executable, str(lint), "--check-admission", str(admitted)],
                capture_output=True, text=True,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

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

            legacy_text = self.write_pre_schema_project(root)
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

    def test_pre_schema_exception_requires_the_captured_migration_boundary(self) -> None:
        module = load_module(PLANLIB, "migration_bound_witness_planlib")
        record_relative = self.MIGRATION_RECORD
        policy_relative = self.MIGRATION_POLICY

        def mutate_captured_plan(root: Path, changes: dict[str, object]) -> None:
            record_path = root / record_relative
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["plans"][0].update(changes)
            record_path.write_text(
                json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )

        def remove_record(root: Path) -> None:
            (root / record_relative).unlink()

        def clear_boundary_marker(root: Path) -> None:
            (root / policy_relative).write_text("orchestration policy\n", encoding="utf-8")

        def drop_schema_version(root: Path) -> None:
            record_path = root / record_relative
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["schema_version"] = 2
            record_path.write_text(
                json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )

        def link_record(root: Path) -> None:
            record_path = root / record_relative
            moved = root / "captured-provenance.json"
            record_path.rename(moved)
            record_path.symlink_to(moved)

        def link_record_parent(root: Path) -> None:
            parent = (root / record_relative).parent
            moved = root / "captured-migration"
            parent.rename(moved)
            parent.symlink_to(moved, target_is_directory=True)

        breakers = (
            ("missing record", remove_record),
            ("uncrossed boundary", clear_boundary_marker),
            ("unsupported schema", drop_schema_version),
            ("symlinked record", link_record),
            ("symlinked record parent", link_record_parent),
            ("foreign plan digest", lambda root: mutate_captured_plan(
                root, {"plan_sha256": "sha256:" + "0" * 64}
            )),
            ("weakened validation", lambda root: mutate_captured_plan(
                root, {"validation": ["git diff --cached --check"]}
            )),
            ("foreign captured path", lambda root: mutate_captured_plan(
                root, {"path": "docs/plan/active/992-integration.md"}
            )),
        )
        for label, breaker in breakers:
            with self.subTest(breaker=label):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.write_pre_schema_project(root)
                    plan = root / "docs/plan/active/991-integration.md"
                    values = module.parse_manifest(plan)
                    module.validate_validation_witness_map(values, plan_path=plan)
                    breaker(root)
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(values, plan_path=plan)

        with self.subTest(breaker="unresolvable context path"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_pre_schema_project(root)
                plan = root / "docs/plan/active/991-integration.md"
                values = module.parse_manifest(plan)
                module.validate_validation_witness_map(values, plan_path=plan)
                with self.assertRaises(module.PlanError):
                    module.validate_validation_witness_map(
                        dict(values, context_files=["docs/agent/DOES_NOT_EXIST.md"]),
                        plan_path=plan,
                    )

    def test_witness_map_requires_the_published_companion_validation_authority(self) -> None:
        module = load_module(PLANLIB, "companion_baseline_witness_planlib")
        acceptance = "Preserve the contracted validation authority."
        contract_relative = "docs/plan/replanned/contracts/990-source.json"
        baseline_relative = "docs/plan/replanned/baselines/live-validation-successors-v1.json"
        plan_relative = "docs/plan/active/991-integration.md"
        validation = ["python3 -m pytest tests/focused.py", "git diff --check"]
        record = {
            "acceptance_sha256": self.witness_digest(acceptance),
            "stage": "focused",
            "witness": "python3 -m pytest tests/focused.py",
        }
        values = {
            "status": "in_progress",
            "validation_witness_schema": "1",
            "replan_contract": contract_relative,
            "integration_gates": ["the integration predecessor is checked"],
            "acceptance": [acceptance],
            "focused_validation": ["python3 -m pytest tests/focused.py"],
            "validation": validation,
            "validation_witness_map": [json.dumps(record, separators=(",", ":"))],
        }
        successor = {
            "acceptance_digests": [self.witness_digest(acceptance)],
            "authoritative_validation": validation,
            "authoritative_validation_digest": self.compact_digest(validation),
            "path": plan_relative,
            "validation_witness_map_digest": self.compact_digest([record]),
            "validation_witness_schema": 1,
        }

        def self_projecting_successor(schema: int, **changes: object) -> dict[str, object]:
            content = "status: in_progress\n"
            projected = {
                "authoritative_validation": validation,
                "authoritative_validation_digest": self.compact_digest(validation),
                "content": content,
                "content_digest": self.witness_digest(content),
                "id": "991",
                "path": plan_relative,
                "validation_witness_map_digest": self.compact_digest([record]),
                "validation_witness_schema": 1,
            }
            if schema == 2:
                projected["acceptance_digests"] = [self.witness_digest(acceptance)]
                projected["integration"] = {}
            else:
                projected["acceptance_mappings"] = [
                    {
                        "acceptance_digests": [self.witness_digest(acceptance)],
                        "source_id": "990",
                    }
                ]
                projected["integration_source_ids"] = ["990"]
            projected.update(changes)
            return projected

        def self_projecting_contract(schema: int, **changes: object) -> dict[str, object]:
            shared = {
                "contract_path": contract_relative,
                "created_at": "2026-08-27T23:49:22.747941+00:00",
                "dirty_product_paths": [],
                "schema_version": schema,
                "successors": [self_projecting_successor(schema)],
            }
            if schema == 2:
                shared.update(
                    {
                        "archive_path": "docs/plan/replanned/2026/08/16-31/990-source.md",
                        "reason_codes": ["scope_drift"],
                        "source": {"id": "990"},
                    }
                )
            else:
                shared.update(
                    {
                        "prerequisite_plans": [],
                        "rebind_record_digests": [],
                        "source_head": "0" * 40,
                        "sources": [{"id": "990"}],
                    }
                )
            shared.update(changes)
            return shared

        def prepare(root: Path, contract_schema: int = 1) -> Path:
            plan = root / plan_relative
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("status: in_progress\n", encoding="utf-8")
            contract = root / contract_relative
            contract.parent.mkdir(parents=True, exist_ok=True)
            body = (
                self_projecting_contract(contract_schema)
                if contract_schema in (2, 3)
                else {
                    "contract_path": contract_relative,
                    "schema_version": contract_schema,
                    "successors": [{"path": plan_relative}],
                }
            )
            contract.write_text(self.indented_json(body), encoding="utf-8")
            return plan

        def contract_digest(root: Path) -> str:
            return self.witness_digest(
                (root / contract_relative).read_text(encoding="utf-8")
            )

        def write_baseline(root: Path, records: list[dict[str, object]]) -> None:
            target = root / baseline_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                self.indented_json({"schema_version": 1, "records": records}),
                encoding="utf-8",
            )

        def publish(root: Path, **changes: object) -> None:
            write_baseline(
                root,
                [
                    {
                        "contract_digest": contract_digest(root),
                        "contract_path": contract_relative,
                        "successors": [successor],
                        **changes,
                    }
                ],
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = prepare(root)
            publish(root)
            self.assertEqual(
                module.validate_validation_witness_map(values, plan_path=plan)[0]["stage"],
                "focused",
            )

        weakened = dict(values, validation=["git diff --check"], focused_validation=[])
        weakened["validation_witness_map"] = [
            json.dumps(
                {
                    "acceptance_sha256": self.witness_digest(acceptance),
                    "stage": "authoritative",
                    "witness": "git diff --check",
                    "authoritative_only_reason": "requires the complete integrated candidate",
                },
                separators=(",", ":"),
            )
        ]
        unbound = {key: item for key, item in values.items() if key != "replan_contract"}

        def keep_baseline(root: Path) -> None:
            publish(root)

        def delete_baseline(root: Path) -> None:
            publish(root)
            (root / baseline_relative).unlink()

        def dangle_baseline(root: Path) -> None:
            target = root / baseline_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(root / "never-published.json")

        def rename_owning_contract(root: Path) -> None:
            publish(root, contract_path="docs/plan/replanned/contracts/900-other.json")

        def empty_records(root: Path) -> None:
            write_baseline(root, [])

        def duplicate_contract(root: Path) -> None:
            write_baseline(
                root,
                [
                    {
                        "contract_digest": contract_digest(root),
                        "contract_path": contract_relative,
                        "successors": [successor],
                    }
                ]
                * 2,
            )

        def drop_successor(root: Path) -> None:
            publish(root, successors=[])

        def remap_witness(root: Path) -> None:
            write_baseline(
                root,
                [
                    {
                        "contract_digest": contract_digest(root),
                        "contract_path": contract_relative,
                        "successors": [
                            dict(successor, validation_witness_map_digest="sha256:" + "0" * 64)
                        ],
                    }
                ],
            )

        def drift_contract(root: Path) -> None:
            publish(root)
            (root / contract_relative).write_text("{}\n", encoding="utf-8")

        def malform_record(root: Path) -> None:
            write_baseline(root, ["not-a-record"])

        def strip_successor_list(root: Path) -> None:
            write_baseline(
                root,
                [
                    {
                        "contract_digest": contract_digest(root),
                        "contract_path": contract_relative,
                    }
                ],
            )

        def duplicate_plan_ownership(root: Path) -> None:
            write_baseline(
                root,
                [
                    {
                        "contract_digest": contract_digest(root),
                        "contract_path": contract_relative,
                        "successors": [successor],
                    },
                    {
                        "contract_digest": "sha256:" + "0" * 64,
                        "contract_path": "docs/plan/replanned/contracts/900-other.json",
                        "successors": [successor],
                    },
                ],
            )

        def delete_baseline_keeping_schema_one_lineage(root: Path) -> None:
            surviving = root / "docs/plan/replanned/contracts/900-published.json"
            surviving.parent.mkdir(parents=True, exist_ok=True)
            surviving.write_text(
                self.indented_json({"contract_path": str(surviving), "schema_version": 1}),
                encoding="utf-8",
            )

        rejected = (
            ("weakened authority", weakened, keep_baseline),
            ("deleted baseline", values, delete_baseline),
            ("dangling baseline", values, dangle_baseline),
            ("renamed owning contract", values, rename_owning_contract),
            ("emptied records", values, empty_records),
            ("duplicated contract", values, duplicate_contract),
            ("dropped successor", values, drop_successor),
            ("remapped witness", values, remap_witness),
            ("drifted contract bytes", values, drift_contract),
            ("dropped contract lineage", unbound, keep_baseline),
            ("malformed baseline record", values, malform_record),
            ("stripped successor list", values, strip_successor_list),
            ("duplicate plan ownership", values, duplicate_plan_ownership),
            (
                "deleted baseline under surviving schema-1 lineage",
                unbound,
                delete_baseline_keeping_schema_one_lineage,
            ),
        )
        for label, candidate, publisher in rejected:
            with self.subTest(rejected=label):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    plan = prepare(root)
                    publisher(root)
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(candidate, plan_path=plan)

        for schema in (2, 3):
            with self.subTest(rejected=f"unpublished schema-{schema} contract"):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    plan = prepare(root, contract_schema=schema)
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(values, plan_path=plan)

        for residue_field, residue_value in (
            ("inherited_acceptance_digests", [self.witness_digest(acceptance)]),
            ("replan_sources", ["docs/plan/replanned/2026/08/16-31/990-source.md"]),
            ("replan_source", "docs/plan/replanned/2026/08/16-31/990-source.md"),
        ):
            with self.subTest(rejected="lineage residue", field=residue_field):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    plan = prepare(root)
                    residual = dict(unbound, **{residue_field: residue_value})
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(residual, plan_path=plan)

    def test_self_projecting_contract_authority_requires_published_history(self) -> None:
        """A schema-2 or schema-3 contract authorizes only as committed publication."""

        module = load_module(PLANLIB, "self_projecting_authority_planlib")
        plan_relative = "docs/plan/active/991-integration.md"
        contract_relative = "docs/plan/replanned/contracts/990-source.json"
        archive_relative = "docs/plan/replanned/2026/08/16-31/990-source.md"
        plan_text = "status: in_progress\n"
        first = "Preserve the contracted validation authority."
        second = "Preserve the coupled source acceptance baseline."
        focused_witness = "python3 -m pytest tests/focused.py"
        validation = [focused_witness, "git diff --check"]

        def witness_record(acceptance: str) -> dict[str, str]:
            return {
                "acceptance_sha256": self.witness_digest(acceptance),
                "stage": "focused",
                "witness": focused_witness,
            }

        def plan_values(acceptance: list[str], **changes: object) -> dict[str, object]:
            records = [witness_record(item) for item in acceptance]
            values = {
                "status": "in_progress",
                "validation_witness_schema": "1",
                "replan_contract": contract_relative,
                "integration_gates": ["the integration predecessor is checked"],
                "acceptance": acceptance,
                "focused_validation": [focused_witness],
                "validation": validation,
                "validation_witness_map": [
                    json.dumps(record, separators=(",", ":")) for record in records
                ],
            }
            values.update(changes)
            return values

        def successor(
            schema: int, mappings: list[dict[str, object]], acceptance: list[str], **changes: object
        ) -> dict[str, object]:
            records = [witness_record(item) for item in acceptance]
            projected = {
                "authoritative_validation": validation,
                "authoritative_validation_digest": self.compact_digest(validation),
                "content": plan_text,
                "content_digest": self.witness_digest(plan_text),
                "id": "991",
                "path": plan_relative,
                "validation_witness_map_digest": self.compact_digest(records),
                "validation_witness_schema": 1,
            }
            if schema == 2:
                projected["acceptance_digests"] = [
                    self.witness_digest(item) for item in acceptance
                ]
                projected["integration"] = True
            else:
                projected["acceptance_mappings"] = mappings
                projected["integration_source_ids"] = [
                    mapping["source_id"] for mapping in mappings
                ]
            projected.update(changes)
            return projected

        def contract(
            schema: int,
            *,
            acceptance: list[str] | None = None,
            mappings: list[dict[str, object]] | None = None,
            source_ids: list[str] | None = None,
            successors: list[dict[str, object]] | None = None,
            **changes: object,
        ) -> dict[str, object]:
            acceptance = acceptance or [first]
            mappings = mappings or [
                {
                    "acceptance_digests": [self.witness_digest(item) for item in acceptance],
                    "source_id": "990",
                }
            ]
            body = {
                "contract_path": contract_relative,
                "created_at": "2026-08-27T23:49:22.747941+00:00",
                "dirty_product_paths": [],
                "schema_version": schema,
                "successors": (
                    successors
                    if successors is not None
                    else [successor(schema, mappings, acceptance)]
                ),
            }
            if schema == 2:
                body.update(
                    {
                        "archive_path": archive_relative,
                        "reason_codes": ["scope_drift"],
                        "source": {"id": "990"},
                    }
                )
            else:
                body.update(
                    {
                        "prerequisite_plans": [],
                        "rebind_record_digests": [],
                        "source_head": "0" * 40,
                        "sources": [{"id": value} for value in (source_ids or ["990"])],
                    }
                )
            body.update(changes)
            return body

        archive_text = (
            "# Stopped source\n\n"
            "status: replanned\n"
            f"replan_contract: {contract_relative}\n"
            "successor_plans:\n"
            f"  - {plan_relative}\n"
            "\n## Tasks\n"
        )
        index_text = (
            "# Replanned Plan Index\n\nid\tpath\tcontract\n"
            f"990\t{archive_relative}\t{contract_relative}\n"
        )

        def write(root: Path, relative: str, text: str) -> None:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        def commit_repository(root: Path) -> None:
            for args in (
                ("init", "-q"),
                ("config", "user.email", "test@example.invalid"),
                ("config", "user.name", "Test"),
                ("add", "-A"),
                ("-c", "commit.gpgsign=false", "commit", "-qm", "publish restructuring"),
            ):
                subprocess.run(["git", *args], cwd=root, check=True)

        def publish(
            root: Path,
            schema: int,
            *,
            files: dict[str, str | None] | None = None,
            commit: bool = True,
            after: dict[str, str] | None = None,
        ) -> Path:
            published: dict[str, str | None] = {
                plan_relative: plan_text,
                contract_relative: self.indented_json(contract(schema)),
                archive_relative: archive_text,
                "docs/plan/replanned.md": index_text,
            }
            published.update(files or {})
            for relative, text in published.items():
                if text is None:
                    continue
                write(root, relative, text)
            if commit:
                commit_repository(root)
            for relative, text in (after or {}).items():
                write(root, relative, text)
            return root / plan_relative

        for schema in (2, 3):
            with self.subTest(admitted=f"published schema-{schema} contract"):
                with tempfile.TemporaryDirectory() as tmp:
                    plan = publish(Path(tmp), schema)
                    self.assertEqual(
                        module.validate_validation_witness_map(
                            plan_values([first]), plan_path=plan
                        )[0]["stage"],
                        "focused",
                    )

        with self.subTest(admitted="schema-3 acceptance mapped across coupled sources"):
            with tempfile.TemporaryDirectory() as tmp:
                mappings = [
                    {"acceptance_digests": [self.witness_digest(first)], "source_id": "990"},
                    {"acceptance_digests": [self.witness_digest(second)], "source_id": "989"},
                ]
                plan = publish(
                    Path(tmp),
                    3,
                    files={
                        contract_relative: self.indented_json(
                            contract(
                                3,
                                acceptance=[first, second],
                                mappings=mappings,
                                source_ids=["990", "989"],
                            )
                        )
                    },
                )
                self.assertEqual(
                    len(
                        module.validate_validation_witness_map(
                            plan_values([first, second]), plan_path=plan
                        )
                    ),
                    2,
                )

        forged = self.indented_json(
            contract(
                3,
                created_at="not-a-timestamp",
                source_head="not-a-commit",
                successors=[
                    successor(
                        3,
                        [
                            {
                                "acceptance_digests": [self.witness_digest(first)],
                                "source_id": "990",
                            }
                        ],
                        [first],
                        authoritative_validation=["git diff --check"],
                        authoritative_validation_digest=self.compact_digest(
                            ["git diff --check"]
                        ),
                    )
                ],
            )
        )
        weakened = plan_values(
            [first],
            validation=["git diff --check"],
            focused_validation=[],
            validation_witness_map=[
                json.dumps(
                    {
                        "acceptance_sha256": self.witness_digest(first),
                        "stage": "authoritative",
                        "witness": "git diff --check",
                        "authoritative_only_reason": "requires the complete integrated candidate",
                    },
                    separators=(",", ":"),
                )
            ],
        )
        with self.subTest(admitted="published lineage under a redirected Git environment"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "repository"
                root.mkdir()
                plan = publish(root, 3)
                foreign = Path(tmp) / "foreign"
                foreign.mkdir()
                for relative, text in (
                    (contract_relative, forged),
                    (archive_relative, archive_text),
                    ("docs/plan/replanned.md", index_text),
                ):
                    write(foreign, relative, text)
                commit_repository(foreign)
                previous = os.environ.get("GIT_DIR")
                os.environ["GIT_DIR"] = str(foreign / ".git")
                try:
                    self.assertEqual(
                        module.validate_validation_witness_map(
                            plan_values([first]), plan_path=plan
                        )[0]["stage"],
                        "focused",
                    )
                finally:
                    if previous is None:
                        os.environ.pop("GIT_DIR", None)
                    else:
                        os.environ["GIT_DIR"] = previous

        rejected: tuple[tuple[str, int, dict[str, object], dict[str, object]], ...] = (
            ("no repository history", 3, {"commit": False}, {}),
            (
                "full-shaped forged contract substituted after publication",
                3,
                {"after": {contract_relative: forged}},
                {"values": weakened},
            ),
            (
                "full-shaped forged contract present only in the working tree",
                3,
                {
                    "files": {contract_relative: None},
                    "after": {contract_relative: forged},
                },
                {"values": weakened},
            ),
            (
                "full-shaped forged contract committed without lineage",
                3,
                {
                    "files": {
                        contract_relative: forged,
                        "docs/plan/replanned.md": "# Replanned Plan Index\n\nid\tpath\tcontract\n",
                    }
                },
                {"values": weakened},
            ),
            (
                "contract left uncommitted",
                3,
                {"files": {contract_relative: None}, "after": {
                    contract_relative: self.indented_json(contract(3))
                }},
                {},
            ),
            (
                "contract drifted after publication",
                3,
                {
                    "after": {
                        contract_relative: self.indented_json(
                            contract(3, created_at="2026-08-28T00:00:00+00:00")
                        )
                    }
                },
                {},
            ),
            (
                "contract unregistered in the published index",
                3,
                {"files": {"docs/plan/replanned.md": "# Replanned Plan Index\n\nid\tpath\tcontract\n"}},
                {},
            ),
            (
                "index row added only in the working tree",
                3,
                {
                    "files": {
                        "docs/plan/replanned.md": "# Replanned Plan Index\n\nid\tpath\tcontract\n"
                    },
                    "after": {"docs/plan/replanned.md": index_text},
                },
                {},
            ),
            (
                "archive is not terminal replanned history",
                3,
                {"files": {archive_relative: archive_text.replace("status: replanned", "status: deferred")}},
                {},
            ),
            (
                "archive names another contract",
                3,
                {
                    "files": {
                        archive_relative: archive_text.replace(
                            contract_relative,
                            "docs/plan/replanned/contracts/900-other.json",
                        )
                    }
                },
                {},
            ),
            (
                "archive does not create this plan",
                3,
                {
                    "files": {
                        archive_relative: archive_text.replace(
                            plan_relative, "docs/plan/active/992-other.md"
                        )
                    }
                },
                {},
            ),
            (
                "contract identity differs from its published path",
                3,
                {
                    "files": {
                        contract_relative: self.indented_json(
                            contract(
                                3,
                                contract_path="docs/plan/replanned/contracts/900-other.json",
                            )
                        )
                    }
                },
                {},
            ),
            ("weakened authoritative sequence", 3, {}, {"values": weakened}),
            (
                "remapped witness digest",
                3,
                {
                    "files": {
                        contract_relative: self.indented_json(
                            contract(
                                3,
                                successors=[
                                    successor(
                                        3,
                                        [
                                            {
                                                "acceptance_digests": [
                                                    self.witness_digest(first)
                                                ],
                                                "source_id": "990",
                                            }
                                        ],
                                        [first],
                                        validation_witness_map_digest="sha256:" + "0" * 64,
                                    )
                                ],
                            )
                        )
                    }
                },
                {},
            ),
            (
                "duplicate successor entries",
                3,
                {
                    "files": {
                        contract_relative: self.indented_json(
                            contract(
                                3,
                                successors=[
                                    successor(
                                        3,
                                        [
                                            {
                                                "acceptance_digests": [
                                                    self.witness_digest(first)
                                                ],
                                                "source_id": "990",
                                            }
                                        ],
                                        [first],
                                    )
                                ]
                                * 2,
                            )
                        )
                    }
                },
                {},
            ),
            (
                "acceptance mapped from an unknown source",
                3,
                {
                    "files": {
                        contract_relative: self.indented_json(
                            contract(
                                3,
                                mappings=[
                                    {
                                        "acceptance_digests": [self.witness_digest(first)],
                                        "source_id": "999",
                                    }
                                ],
                            )
                        )
                    }
                },
                {},
            ),
            (
                "acceptance mappings out of published source order",
                3,
                {
                    "files": {
                        contract_relative: self.indented_json(
                            contract(
                                3,
                                acceptance=[first, second],
                                mappings=[
                                    {
                                        "acceptance_digests": [self.witness_digest(second)],
                                        "source_id": "989",
                                    },
                                    {
                                        "acceptance_digests": [self.witness_digest(first)],
                                        "source_id": "990",
                                    },
                                ],
                                source_ids=["990", "989"],
                            )
                        )
                    }
                },
                {"values": plan_values([first, second])},
            ),
            (
                "schema-2 acceptance projection drift",
                2,
                {
                    "files": {
                        contract_relative: self.indented_json(
                            contract(
                                2,
                                successors=[
                                    successor(
                                        2,
                                        [],
                                        [first],
                                        acceptance_digests=[self.witness_digest(second)],
                                    )
                                ],
                            )
                        )
                    }
                },
                {},
            ),
        )
        for label, schema, published, expectation in rejected:
            with self.subTest(rejected=label):
                with tempfile.TemporaryDirectory() as tmp:
                    plan = publish(Path(tmp), schema, **published)  # type: ignore[arg-type]
                    candidate = expectation.get("values") or plan_values([first])
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(candidate, plan_path=plan)

        with self.subTest(rejected="contract outside the published contract directory"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                stray = "docs/plan/replanned/990-source.json"
                publish(
                    root,
                    3,
                    files={
                        stray: self.indented_json(contract(3, contract_path=stray)),
                        "docs/plan/replanned.md": (
                            "# Replanned Plan Index\n\nid\tpath\tcontract\n"
                            f"990\t{archive_relative}\t{stray}\n"
                        ),
                        archive_relative: archive_text.replace(contract_relative, stray),
                    },
                )
                with self.assertRaises(module.PlanError):
                    module.validate_validation_witness_map(
                        plan_values([first], replan_contract=stray),
                        plan_path=root / plan_relative,
                    )

        with self.subTest(rejected="history from an enclosing repository"):
            with tempfile.TemporaryDirectory() as tmp:
                outer = Path(tmp)
                nested = outer / "project"
                nested.mkdir()
                publish(nested, 3, commit=False)
                commit_repository(outer)
                with self.assertRaises(module.PlanError):
                    module.validate_validation_witness_map(
                        plan_values([first]), plan_path=nested / plan_relative
                    )

    def test_context_path_identity_holds_without_a_static_witness(self) -> None:
        module = load_module(PLANLIB, "focused_context_identity_planlib")
        acceptance = "Prove context identity under a focused witness."
        record = {
            "acceptance_sha256": self.witness_digest(acceptance),
            "stage": "focused",
            "witness": "python3 -m pytest tests/focused.py",
        }
        values = {
            "status": "in_progress",
            "validation_witness_schema": "1",
            "integration_gates": ["the context input is resolved"],
            "context_files": ["docs/agent/SPEC_PLAN_WORKFLOW.md"],
            "acceptance": [acceptance],
            "focused_validation": ["python3 -m pytest tests/focused.py"],
            "validation": ["python3 -m pytest tests/focused.py", "git diff --check"],
            "validation_witness_map": [json.dumps(record, separators=(",", ":"))],
        }

        def prepare(root: Path) -> Path:
            plan_path = root / "docs/plan/active/991-integration.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text("status: in_progress\n", encoding="utf-8")
            context = root / "docs/agent/SPEC_PLAN_WORKFLOW.md"
            context.parent.mkdir(parents=True)
            context.write_text("policy\n", encoding="utf-8")
            return plan_path

        with tempfile.TemporaryDirectory() as tmp:
            plan_path = prepare(Path(tmp))
            self.assertEqual(
                module.validate_validation_witness_map(values, plan_path=plan_path)[0]["stage"],
                "focused",
            )

        rejected = (
            ("missing file", ["docs/agent/DOES_NOT_EXIST.md"]),
            ("traversal", ["docs/agent/../agent/SPEC_PLAN_WORKFLOW.md"]),
            ("absolute path", ["/etc/passwd"]),
            (
                "duplicate path",
                ["docs/agent/SPEC_PLAN_WORKFLOW.md", "docs/agent/SPEC_PLAN_WORKFLOW.md"],
            ),
        )
        for label, context_files in rejected:
            with self.subTest(rejected=label):
                with tempfile.TemporaryDirectory() as tmp:
                    plan_path = prepare(Path(tmp))
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(
                            dict(values, context_files=context_files), plan_path=plan_path
                        )

        with self.subTest(rejected="symlinked ancestor"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan_path = prepare(root)
                (root / "docs/linked-agent").symlink_to(root / "docs/agent")
                with self.assertRaises(module.PlanError):
                    module.validate_validation_witness_map(
                        dict(
                            values,
                            context_files=["docs/linked-agent/SPEC_PLAN_WORKFLOW.md"],
                        ),
                        plan_path=plan_path,
                    )

        with self.subTest(accepted="none sentinel"):
            with tempfile.TemporaryDirectory() as tmp:
                plan_path = prepare(Path(tmp))
                self.assertEqual(
                    module.validate_validation_witness_map(
                        dict(values, context_files=["none"]), plan_path=plan_path
                    )[0]["stage"],
                    "focused",
                )

        with self.subTest(rejected="none mixed with a path"):
            with tempfile.TemporaryDirectory() as tmp:
                plan_path = prepare(Path(tmp))
                with self.assertRaises(module.PlanError):
                    module.validate_validation_witness_map(
                        dict(
                            values,
                            context_files=["none", "docs/agent/SPEC_PLAN_WORKFLOW.md"],
                        ),
                        plan_path=plan_path,
                    )

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

            outside = root.parent / "outside.md"
            outside.write_text("policy\n", encoding="utf-8")
            escape = root / "docs/agent/ESCAPE.md"
            escape.symlink_to(outside)
            values["context_files"] = ["docs/agent/ESCAPE.md"]
            with self.assertRaises(module.PlanError):
                module.validate_validation_witness_map(values, plan_path=plan_path)
            outside.unlink()

            linked_parent = root / "docs/linked-agent"
            linked_parent.symlink_to(context.parent, target_is_directory=True)
            values["context_files"] = ["docs/linked-agent/SPEC_PLAN_WORKFLOW.md"]
            with self.assertRaises(module.PlanError):
                module.validate_validation_witness_map(values, plan_path=plan_path)

            checked = root / "docs/plan/checked/2026/08/16-31/990-source.md"
            checked.parent.mkdir(parents=True)
            values["context_files"] = [
                "docs/plan/checked/2026/08/16-31/990-source.md"
            ]
            stale_statuses = (
                ("wrong status", "status: in_progress\n"),
                ("body-only status", "id: 990\n\n## Notes\n\nstatus: checked\n"),
                ("conflicting duplicates", "status: checked\nstatus: in_progress\n"),
                ("no status", "id: 990\n"),
            )
            for label, text in stale_statuses:
                with self.subTest(stale_status=label):
                    checked.write_text(text, encoding="utf-8")
                    with self.assertRaises(module.PlanError):
                        module.validate_validation_witness_map(values, plan_path=plan_path)

            checked.write_text("status: checked\n\n## Notes\n", encoding="utf-8")
            self.assertEqual(
                module.validate_validation_witness_map(values, plan_path=plan_path)[0][
                    "witness"
                ],
                "resolved-context-files",
            )

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

    ACTIVE_INDEX_ROW = "281\tdocs/plan/active/281-example.md\tin_progress"
    ACTIVE_INDEX_EMPTY = "# Active Plan\n\nNo active development items.\n"
    ACTIVE_INDEX_POPULATED = f"# Active Plan\n\nid\tpath\tstatus\n{ACTIVE_INDEX_ROW}\n"
    ACTIVE_INDEX_GRAMMAR_MODULES = (
        ("planlib", PLANLIB),
        ("root policy", ROOT / "scripts/check-root-agent-policy.py"),
        ("restructure", ROOT / "scripts/restructure-plan.py"),
        (
            "generated restructure",
            ROOT / "template/.project-agent-workflow/scripts/restructure-plan.py",
        ),
    )

    @classmethod
    def accepted_active_indexes(cls) -> dict[str, tuple[str, list[tuple[str, str, str]]]]:
        second = "282\tdocs/plan/active/282-second.md\tready_to_archive"
        return {
            "canonical empty document": (cls.ACTIVE_INDEX_EMPTY, []),
            "one canonical row": (
                cls.ACTIVE_INDEX_POPULATED,
                [("281", "docs/plan/active/281-example.md", "in_progress")],
            ),
            "two canonical rows": (
                f"# Active Plan\n\nid\tpath\tstatus\n{cls.ACTIVE_INDEX_ROW}\n{second}\n",
                [
                    ("281", "docs/plan/active/281-example.md", "in_progress"),
                    ("282", "docs/plan/active/282-second.md", "ready_to_archive"),
                ],
            ),
        }

    @classmethod
    def rejected_active_indexes(cls) -> dict[str, str]:
        header = "id\tpath\tstatus"
        row = cls.ACTIVE_INDEX_ROW
        return {
            "literal backslash-t text": cls.ACTIVE_INDEX_POPULATED.replace("\t", "\\t"),
            "blank file": "",
            "newline only": "\n",
            "title only": "# Active Plan\n",
            "missing blank line": f"# Active Plan\n{header}\n{row}\n",
            "header without rows": f"# Active Plan\n\n{header}\n",
            "rows without the header": f"# Active Plan\n\n{row}\n",
            "repeated header": f"# Active Plan\n\n{header}\n{header}\n{row}\n",
            "content before the title": f"note\n# Active Plan\n\n{header}\n{row}\n",
            "content after the rows": cls.ACTIVE_INDEX_POPULATED + "note\n",
            "content after the empty marker": cls.ACTIVE_INDEX_EMPTY + "note\n",
            "repeated empty markers": (
                "# Active Plan\n\nNo active development items.\n"
                "No active development items.\n"
            ),
            "empty marker with a row": (
                f"# Active Plan\n\nNo active development items.\n{row}\n"
            ),
            "empty marker under the header": (
                f"# Active Plan\n\n{header}\nNo active development items.\n"
            ),
            "two columns": (
                "# Active Plan\n\n"
                f"{header}\n281\tdocs/plan/active/281-example.md\n"
            ),
            "four columns": f"# Active Plan\n\n{header}\n{row}\textra\n",
            "duplicate id": (
                f"# Active Plan\n\n{header}\n{row}\n"
                "281\tdocs/plan/active/281-other.md\tdeferred\n"
            ),
            "duplicate row": f"# Active Plan\n\n{header}\n{row}\n{row}\n",
            "id that does not match its file": (
                f"# Active Plan\n\n{header}\n"
                "999\tdocs/plan/active/281-example.md\tin_progress\n"
            ),
            "two-digit id": (
                f"# Active Plan\n\n{header}\n28\tdocs/plan/active/28-example.md\tin_progress\n"
            ),
            "unsupported status": (
                f"# Active Plan\n\n{header}\n"
                "281\tdocs/plan/active/281-example.md\tbacklog\n"
            ),
            "path outside the active directory": (
                f"# Active Plan\n\n{header}\n"
                "281\tdocs/plan/backlog/281-example.md\tin_progress\n"
            ),
            "unnormalized path": (
                f"# Active Plan\n\n{header}\n"
                "281\tdocs/plan/active/281_Example.md\tin_progress\n"
            ),
            "carriage returns": cls.ACTIVE_INDEX_POPULATED.replace("\n", "\r\n"),
            "missing trailing newline": cls.ACTIVE_INDEX_POPULATED.rstrip("\n"),
            "extra trailing newline": cls.ACTIVE_INDEX_POPULATED + "\n",
            "leading blank line": "\n" + cls.ACTIVE_INDEX_POPULATED,
            "indented row": f"# Active Plan\n\n{header}\n  {row}\n",
        }

    def test_every_enforcing_command_reads_one_active_index_grammar(self) -> None:
        accepted = self.accepted_active_indexes()
        rejected = self.rejected_active_indexes()
        for label, path in self.ACTIVE_INDEX_GRAMMAR_MODULES:
            module = load_module(path, f"active_index_grammar_{label.replace(' ', '_')}")
            for case, (text, rows) in accepted.items():
                with self.subTest(command=label, accepted=case):
                    self.assertEqual(module.parse_active_index(text), rows)
            for case, text in rejected.items():
                with self.subTest(command=label, rejected=case):
                    with self.assertRaises(module.ActiveIndexError):
                        module.parse_active_index(text)

    def test_every_canonical_writer_emits_one_active_index_form(self) -> None:
        rows = [
            ("281", "docs/plan/active/281-example.md", "in_progress"),
            ("282", "docs/plan/active/282-second.md", "ready_to_archive"),
        ]
        for label, path in self.ACTIVE_INDEX_GRAMMAR_MODULES:
            module = load_module(path, f"active_index_writer_{label.replace(' ', '_')}")
            with self.subTest(command=label):
                self.assertEqual(module.render_active_index([]), self.ACTIVE_INDEX_EMPTY)
                self.assertEqual(
                    module.render_active_index(rows[:1]), self.ACTIVE_INDEX_POPULATED
                )
                self.assertEqual(
                    module.render_active_index(rows),
                    "# Active Plan\n\nid\tpath\tstatus\n"
                    "281\tdocs/plan/active/281-example.md\tin_progress\n"
                    "282\tdocs/plan/active/282-second.md\tready_to_archive\n",
                )
                with self.assertRaises(module.ActiveIndexError):
                    module.render_active_index([("28", "docs/plan/active/28-x.md", "in_progress")])

    def build_generated_index_fixture(self, root: Path, index_text: str) -> Path:
        """Install the generated plan library beside one active plan and index."""

        scripts = root / ".project-agent-workflow/scripts"
        scripts.mkdir(parents=True)
        for name in ("planlib.py", "lint-plan-docs.py", "plan_validation_commands.py"):
            (scripts / name).write_bytes(
                (ROOT / "template/.project-agent-workflow/scripts" / name).read_bytes()
            )
        plan = root / "docs/plan/active/281-example.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "# Example\n\nstatus: in_progress\n\n## Tasks\n\n- [ ] work\n",
            encoding="utf-8",
        )
        (root / "docs/plan/plan.md").write_text(index_text, encoding="utf-8")
        (root / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
        )
        return scripts

    def load_generated_plan_module(self, root: Path, scripts: Path, name: str, module: str):
        previous_cwd = Path.cwd()
        saved = {key: sys.modules.pop(key, None) for key in ("planlib", "plan_validation_commands")}
        os.chdir(root)
        sys.path.insert(0, str(scripts))
        try:
            return load_module(scripts / name, module)
        finally:
            sys.path.remove(str(scripts))
            os.chdir(previous_cwd)
            for key, value in saved.items():
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value

    def test_generated_lifecycle_stops_before_mutating_a_malformed_index(self) -> None:
        for case, text in self.rejected_active_indexes().items():
            if not text:
                continue
            with self.subTest(rejected=case):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    scripts = self.build_generated_index_fixture(root, text)
                    module = self.load_generated_plan_module(
                        root, scripts, "planlib.py", "malformed_index_planlib"
                    )
                    plan = root / "docs/plan/active/281-example.md"
                    before = (
                        (root / "docs/plan/plan.md").read_bytes(),
                        plan.read_bytes(),
                        (root / "docs/plan/checked.md").read_bytes(),
                    )
                    operations = (
                        lambda: module.read_active_rows(),
                        lambda: module.add_active("282", "docs/plan/active/282-new.md"),
                        lambda: module.remove_active("281"),
                        lambda: module.set_active_status(
                            "281",
                            "docs/plan/active/281-example.md",
                            "in_progress",
                            "deferred",
                        ),
                        lambda: module.complete_transition(
                            "281", "docs/plan/active/281-example.md", "in_progress"
                        ),
                        lambda: module.check_promotion(
                            "282",
                            "docs/plan/backlog/282-new.md",
                            "docs/plan/active/282-new.md",
                        ),
                    )
                    for operation in operations:
                        with self.assertRaises(module.PlanError):
                            operation()
                    self.assertEqual(
                        (
                            (root / "docs/plan/plan.md").read_bytes(),
                            plan.read_bytes(),
                            (root / "docs/plan/checked.md").read_bytes(),
                        ),
                        before,
                    )

    def test_generated_lint_rejects_broken_index_identities(self) -> None:
        missing_file = (
            "# Active Plan\n\nid\tpath\tstatus\n"
            "282\tdocs/plan/active/282-absent.md\tin_progress\n"
        )
        mismatched_status = (
            "# Active Plan\n\nid\tpath\tstatus\n"
            "281\tdocs/plan/active/281-example.md\tdeferred\n"
        )
        cases = {
            "malformed document": self.ACTIVE_INDEX_POPULATED.replace("\t", "\\t"),
            "missing plan file": missing_file,
            "manifest status mismatch": mismatched_status,
        }
        for case, text in cases.items():
            with self.subTest(rejected=case):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    scripts = self.build_generated_index_fixture(root, text)
                    module = self.load_generated_plan_module(
                        root, scripts, "lint-plan-docs.py", f"index_lint_{case.replace(' ', '_')}"
                    )
                    with self.assertRaises(SystemExit):
                        module.lint_plan_index()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = self.build_generated_index_fixture(root, self.ACTIVE_INDEX_POPULATED)
            module = self.load_generated_plan_module(
                root, scripts, "lint-plan-docs.py", "index_lint_accepted"
            )
            module.lint_plan_index()

    def test_root_policy_rejects_broken_active_index_identities(self) -> None:
        cases = {
            "malformed document": self.ACTIVE_INDEX_POPULATED.replace("\t", "\\t"),
            "missing plan file": (
                "# Active Plan\n\nid\tpath\tstatus\n"
                "282\tdocs/plan/active/282-absent.md\tin_progress\n"
            ),
            "plan status mismatch": (
                "# Active Plan\n\nid\tpath\tstatus\n"
                "281\tdocs/plan/active/281-example.md\tdeferred\n"
            ),
        }
        for case, text in cases.items():
            with self.subTest(rejected=case):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.build_generated_index_fixture(root, text)
                    module = load_module(self.ROOT_POLICY, f"root_index_{case.replace(' ', '_')}")
                    module.ROOT = root
                    with self.assertRaises(SystemExit):
                        module.check_active_plans()
        for case, (text, _) in self.accepted_active_indexes().items():
            with self.subTest(accepted=case):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.build_generated_index_fixture(root, text)
                    (root / "docs/plan/active/282-second.md").write_text(
                        "# Second\n\nstatus: ready_to_archive\n", encoding="utf-8"
                    )
                    module = load_module(
                        self.ROOT_POLICY, f"root_index_ok_{case.replace(' ', '_')}"
                    )
                    module.ROOT = root
                    module.check_active_plans()

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

    COMPLETION_PLAN = "docs/plan/active/900-example.md"
    COMPLETION_SPEC = ".project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md"
    COMPLETION_GATE_VARIANTS = (
        {
            "name": "root",
            "source": "scripts",
            "install": "scripts",
            "linted": False,
            "rejects_extra_arguments": False,
            "ready_returncode": 1,
            "ready_message": "cannot mark plan ready from status: ready_to_archive",
        },
        {
            "name": "generated",
            "source": "template/.project-agent-workflow/scripts",
            "install": ".project-agent-workflow/scripts",
            "linted": True,
            "rejects_extra_arguments": True,
            "ready_returncode": 0,
            "ready_message": "plan is already ready_to_archive",
        },
    )

    @classmethod
    def completion_plan_text(
        cls,
        *,
        status: str = "in_progress",
        tasks: str = "- [x] Did the work.",
        notes: str = "- Focused validation passed.",
        summary: bool = True,
    ) -> str:
        summary_line = "checked_summary_ja: 例の作業を記録する。\n" if summary else ""
        return (
            "# Example\n\n"
            f"status: {status}\n"
            "task_types:\n  - planning_docs\n"
            "review_class: B\n"
            "human_design_required: no\n"
            "human_approval_status: approved\n"
            "write_scope:\n  - src/example.ts\n"
            "context_files:\n  - AGENTS.md\n"
            f"required_specs:\n  - {cls.COMPLETION_SPEC}\n"
            "validation:\n  - git diff --check\n"
            "acceptance:\n  - Record the example work.\n"
            f"{summary_line}"
            f"\n## Tasks\n\n{tasks}\n\n## Validation Notes\n\n{notes}\n"
        )

    def build_completion_repo(
        self,
        repo: Path,
        variant: dict[str, object],
        *,
        plan_status: str = "in_progress",
        index_status: str | None = None,
        plan_present: bool = True,
        index_rows: bool = True,
        index_text: str | None = None,
        **plan_fields: object,
    ) -> None:
        """Install one completion gate with its plan lifecycle records."""

        install = repo / str(variant["install"])
        install.mkdir(parents=True, exist_ok=True)
        names = ["check-agent-completion.sh", "complete-plan.sh", "parallel-plan-state.py"]
        if variant["linted"]:
            names += ["lint-plan-docs.py", "planlib.py", "plan_validation_commands.py"]
        for name in names:
            target = install / name
            target.write_bytes((ROOT / str(variant["source"]) / name).read_bytes())
            target.chmod(0o755)
        if variant["linted"]:
            spec = repo / self.COMPLETION_SPEC
            spec.parent.mkdir(parents=True, exist_ok=True)
            spec.write_text("Generated plan workflow policy.\n", encoding="utf-8")
            (spec.parent / "spec-index.yaml").write_text(
                "version: 1\n\ntask_types:\n"
                "  planning_docs:\n"
                "    summary: Plan documents.\n"
                f"    required:\n      - {self.COMPLETION_SPEC}\n",
                encoding="utf-8",
            )
        # The completion gate consults the parallel group authority, which
        # resolves enrolment from the repository, so the fixture is a Git repo.
        if not (repo / ".git").exists():
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test"], check=True
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
                check=True,
            )
        if plan_present:
            plan = repo / self.COMPLETION_PLAN
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                self.completion_plan_text(status=plan_status, **plan_fields),
                encoding="utf-8",
            )
        index = repo / "docs/plan/plan.md"
        index.parent.mkdir(parents=True, exist_ok=True)
        if index_text is None:
            index_text = (
                "# Active Plan\n\nid\tpath\tstatus\n"
                f"900\t{self.COMPLETION_PLAN}\t{index_status or plan_status}\n"
                if index_rows
                else "# Active Plan\n\nNo active development items.\n"
            )
        index.write_text(index_text, encoding="utf-8")
        for args in (
            ("init", "-q"),
            ("config", "user.email", "test@example.invalid"),
            ("config", "user.name", "Test"),
            ("add", "-A"),
            ("-c", "commit.gpgsign=false", "commit", "-qm", "install completion gate"),
        ):
            subprocess.run(["git", *args], cwd=repo, check=True)

    @staticmethod
    def run_in_repo(repo: Path, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", *argv],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    @classmethod
    def run_completion_gate(
        cls, repo: Path, variant: dict[str, object], *argv: str
    ) -> subprocess.CompletedProcess:
        gate = f"{variant['install']}/check-agent-completion.sh"
        return cls.run_in_repo(repo, gate, *argv)

    @classmethod
    def run_completion_plan(
        cls, repo: Path, variant: dict[str, object], *argv: str
    ) -> subprocess.CompletedProcess:
        completer = f"{variant['install']}/complete-plan.sh"
        return cls.run_in_repo(repo, completer, *argv)

    @staticmethod
    def repository_state(repo: Path) -> tuple[tuple[str, str], ...]:
        entries = []
        for path in sorted(repo.rglob("*")):
            parts = path.relative_to(repo).parts
            if ".git" in parts or "__pycache__" in parts or not path.is_file():
                continue
            entries.append(
                (
                    "/".join(parts),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        return tuple(entries)

    @classmethod
    def durable_state(cls, repo: Path) -> tuple[tuple[str, str], ...]:
        """Repository state without the transient lifecycle lock artifacts."""

        return tuple(
            entry
            for entry in cls.repository_state(repo)
            if not entry[0].startswith(".agent-artifacts/")
        )

    def test_completion_gate_reports_a_completed_plan_without_mutation(self) -> None:
        for variant in self.COMPLETION_GATE_VARIANTS:
            with self.subTest(gate=variant["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant)
                    before = self.repository_state(repo)
                    result = self.run_completion_gate(repo, variant)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(
                        "completed plan is not marked ready: "
                        f"{self.COMPLETION_PLAN} (status: in_progress)",
                        result.stderr,
                    )
                    self.assertIn(
                        f"Next: {variant['install']}/complete-plan.sh {self.COMPLETION_PLAN}",
                        result.stderr,
                    )
                    if variant["name"] == "root":
                        self.assertNotIn(".project-agent-workflow", result.stderr)
                    self.assertNotIn("finalize-active-plan.sh", result.stderr)
                    self.assertEqual(self.repository_state(repo), before)
                    self.assertEqual(
                        subprocess.run(
                            ["git", "status", "--short"],
                            cwd=repo,
                            text=True,
                            stdout=subprocess.PIPE,
                            check=True,
                        ).stdout,
                        "",
                    )

    def test_completion_gate_stays_silent_for_incomplete_and_stopped_plans(self) -> None:
        cases = {
            "unchecked task": {"tasks": "- [ ] Still open."},
            "mixed tasks": {"tasks": "- [x] Did the work.\n- [ ] Still open."},
            "empty validation notes": {"notes": ""},
            "pending validation notes": {"notes": "- Pending."},
            "pending prefixed validation notes": {"notes": "- pending: implementation"},
            "deferred plan": {"plan_status": "deferred"},
            "replan required plan": {"plan_status": "replan_required"},
            "index row is not in_progress": {
                "plan_status": "in_progress",
                "index_status": "deferred",
            },
            "plan file is not in_progress": {
                "plan_status": "deferred",
                "index_status": "in_progress",
            },
            "plan file is absent": {"plan_present": False},
            "empty active index": {"index_rows": False},
        }
        for variant in self.COMPLETION_GATE_VARIANTS:
            for case, fields in cases.items():
                with self.subTest(gate=variant["name"], silent=case):
                    with tempfile.TemporaryDirectory() as tmp:
                        repo = Path(tmp)
                        self.build_completion_repo(repo, variant, **fields)
                        before = self.repository_state(repo)
                        result = self.run_completion_gate(repo, variant)
                        self.assertEqual(result.returncode, 0)
                        self.assertEqual(result.stdout, "agent completion gate passed\n")
                        self.assertEqual(result.stderr, "")
                        self.assertEqual(self.repository_state(repo), before)

    def test_completion_gate_preserves_its_existing_reports(self) -> None:
        for variant in self.COMPLETION_GATE_VARIANTS:
            finalize = f"{variant['install']}/finalize-active-plan.sh"
            with self.subTest(gate=variant["name"], report="ready to archive with evidence"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant, plan_status="ready_to_archive")
                    before = self.repository_state(repo)
                    result = self.run_completion_gate(repo, variant)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(
                        "ready-to-archive plan blocks completion: "
                        f"{self.COMPLETION_PLAN} (status: ready_to_archive)",
                        result.stderr,
                    )
                    self.assertNotIn("Missing evidence", result.stderr)
                    self.assertNotIn("complete-plan.sh", result.stderr)
                    self.assertIn(f"Next: {finalize} {self.COMPLETION_PLAN}", result.stderr)
                    self.assertEqual(self.repository_state(repo), before)

            with self.subTest(gate=variant["name"], report="ready to archive without evidence"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(
                        repo,
                        variant,
                        plan_status="ready_to_archive",
                        summary=False,
                        notes="",
                    )
                    result = self.run_completion_gate(repo, variant)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("Missing evidence: checked_summary_ja", result.stderr)
                    self.assertIn("Missing evidence: non-empty Validation Notes", result.stderr)
                    self.assertIn(f"Next: {finalize} {self.COMPLETION_PLAN}", result.stderr)

            with self.subTest(gate=variant["name"], report="dirty worktree"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant, tasks="- [ ] Still open.")
                    (repo / "untracked.txt").write_text("generated\n", encoding="utf-8")
                    result = self.run_completion_gate(repo, variant)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("dirty worktree blocks completion report", result.stderr)
                    plans_only = self.run_completion_gate(repo, variant, "--plans-only")
                    self.assertEqual(plans_only.returncode, 0)
                    self.assertEqual(plans_only.stdout, "agent completion gate passed\n")

            with self.subTest(gate=variant["name"], report="completed plan before worktree"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant)
                    (repo / "untracked.txt").write_text("generated\n", encoding="utf-8")
                    result = self.run_completion_gate(repo, variant)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("completed plan is not marked ready", result.stderr)
                    self.assertNotIn("dirty worktree blocks completion report", result.stderr)
                    plans_only = self.run_completion_gate(repo, variant, "--plans-only")
                    self.assertEqual(plans_only.returncode, 1)
                    self.assertIn("completed plan is not marked ready", plans_only.stderr)

            with self.subTest(gate=variant["name"], report="unexpected argument"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant, tasks="- [ ] Still open.")
                    result = self.run_completion_gate(repo, variant, "--plans-only", "extra")
                    if variant["rejects_extra_arguments"]:
                        self.assertEqual(result.returncode, 2)
                        self.assertIn("Usage:", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0)
                        self.assertEqual(result.stdout, "agent completion gate passed\n")

    def test_completion_evidence_mode_reads_without_lifecycle_effects(self) -> None:
        accepted = {
            "checked tasks and settled notes": {},
            "evidence complete while deferred": {"plan_status": "deferred"},
        }
        rejected = {
            "unchecked task": {"tasks": "- [ ] Still open."},
            "empty validation notes": {"notes": ""},
            "pending validation notes": {"notes": "- Pending."},
        }
        for variant in self.COMPLETION_GATE_VARIANTS:
            for case, fields in {**accepted, **rejected}.items():
                with self.subTest(mode=variant["name"], evidence=case):
                    with tempfile.TemporaryDirectory() as tmp:
                        repo = Path(tmp)
                        self.build_completion_repo(repo, variant, **fields)
                        before = self.repository_state(repo)
                        result = self.run_completion_plan(
                            repo, variant, "--check-completion-evidence", self.COMPLETION_PLAN
                        )
                        self.assertEqual(result.returncode, 0 if case in accepted else 1)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(result.stderr, "")
                        self.assertEqual(self.repository_state(repo), before)
                        self.assertFalse((repo / ".agent-artifacts").exists())

            with self.subTest(mode=variant["name"], evidence="invalid invocation"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant)
                    before = self.repository_state(repo)
                    outside = self.run_completion_plan(
                        repo, variant, "--check-completion-evidence", "docs/plan/backlog/900-example.md"
                    )
                    self.assertEqual(outside.returncode, 2)
                    self.assertIn("expected active plan path", outside.stderr)
                    missing = self.run_completion_plan(
                        repo, variant, "--check-completion-evidence", "docs/plan/active/901-absent.md"
                    )
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn("missing plan: docs/plan/active/901-absent.md", missing.stderr)
                    extra = self.run_completion_plan(
                        repo, variant, "--check-completion-evidence", self.COMPLETION_PLAN, "extra"
                    )
                    self.assertEqual(extra.returncode, 2)
                    self.assertIn("Usage:", extra.stderr)
                    self.assertEqual(self.repository_state(repo), before)

    def test_ordinary_completion_transition_stays_unchanged(self) -> None:
        plan_path = self.COMPLETION_PLAN
        rejected = {
            "unchecked task": (
                {"tasks": "- [ ] Still open."},
                f"cannot mark plan ready: unchecked tasks remain in {plan_path}",
            ),
            "empty validation notes": (
                {"notes": ""},
                "cannot mark plan ready: Validation Notes are empty or pending in "
                f"{plan_path}",
            ),
            "pending validation notes": (
                {"notes": "- Pending."},
                "cannot mark plan ready: Validation Notes are empty or pending in "
                f"{plan_path}",
            ),
            "deferred plan": (
                {"plan_status": "deferred"},
                "cannot mark deferred plan ready",
            ),
            "replan required plan": (
                {"plan_status": "replan_required"},
                "cannot complete a plan that requires restructuring",
            ),
        }
        for variant in self.COMPLETION_GATE_VARIANTS:
            for case, (fields, message) in rejected.items():
                with self.subTest(transition=variant["name"], refused=case):
                    with tempfile.TemporaryDirectory() as tmp:
                        repo = Path(tmp)
                        self.build_completion_repo(repo, variant, **fields)
                        plan = repo / self.COMPLETION_PLAN
                        index = repo / "docs/plan/plan.md"
                        before = (plan.read_bytes(), index.read_bytes())
                        result = self.run_completion_plan(repo, variant, self.COMPLETION_PLAN)
                        self.assertEqual(result.returncode, 1)
                        self.assertIn(message, result.stderr)
                        self.assertEqual((plan.read_bytes(), index.read_bytes()), before)

            with self.subTest(transition=variant["name"], accepted="completed plan"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant)
                    result = self.run_completion_plan(repo, variant, self.COMPLETION_PLAN)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, f"{self.COMPLETION_PLAN}\n")
                    self.assertIn(
                        "status: ready_to_archive",
                        (repo / self.COMPLETION_PLAN).read_text(encoding="utf-8"),
                    )
                    self.assertIn(
                        f"900\t{self.COMPLETION_PLAN}\tready_to_archive",
                        (repo / "docs/plan/plan.md").read_text(encoding="utf-8"),
                    )
                    gate = self.run_completion_gate(repo, variant, "--plans-only")
                    self.assertEqual(gate.returncode, 1)
                    self.assertIn("ready-to-archive plan blocks completion", gate.stderr)

            with self.subTest(transition=variant["name"], refused="already ready to archive"):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant, plan_status="ready_to_archive")
                    result = self.run_completion_plan(repo, variant, self.COMPLETION_PLAN)
                    self.assertEqual(result.returncode, variant["ready_returncode"])
                    self.assertIn(str(variant["ready_message"]), result.stderr)

    def test_completion_gate_rejects_a_malformed_active_index(self) -> None:
        for case, malformed in self.rejected_active_indexes().items():
            if not malformed:
                continue
            for variant in self.COMPLETION_GATE_VARIANTS:
                with self.subTest(gate=variant["name"], rejected=case):
                    with tempfile.TemporaryDirectory() as tmp:
                        repo = Path(tmp)
                        self.build_completion_repo(repo, variant, index_text=malformed)
                        before = self.durable_state(repo)
                        result = self.run_completion_gate(repo, variant, "--plans-only")
                        self.assertEqual(result.returncode, 1)
                        self.assertEqual(result.stdout, "")
                        self.assertIn(
                            "malformed active plan index blocks completion", result.stderr
                        )
                        self.assertEqual(self.durable_state(repo), before)

    def test_completion_stops_on_a_malformed_active_index(self) -> None:
        malformed = self.ACTIVE_INDEX_POPULATED.replace("\t", "\\t")
        for variant in self.COMPLETION_GATE_VARIANTS:
            with self.subTest(transition=variant["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(repo, variant, index_text=malformed)
                    before = self.durable_state(repo)
                    result = self.run_completion_plan(repo, variant, self.COMPLETION_PLAN)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("active plan index", result.stderr)
                    self.assertEqual(self.durable_state(repo), before)

    def test_finalized_last_row_leaves_the_canonical_empty_index(self) -> None:
        for variant in self.COMPLETION_GATE_VARIANTS:
            with self.subTest(finalization=variant["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(
                        repo, variant, plan_status="ready_to_archive"
                    )
                    finalizer = Path(str(variant["install"])) / "finalize-active-plan.sh"
                    (repo / finalizer).write_bytes(
                        (ROOT / str(variant["source"]) / "finalize-active-plan.sh").read_bytes()
                    )
                    (repo / "docs/plan/checked.md").write_text(
                        "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
                    )
                    result = self.run_in_repo(repo, str(finalizer), self.COMPLETION_PLAN)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        (repo / "docs/plan/plan.md").read_text(encoding="utf-8"),
                        self.ACTIVE_INDEX_EMPTY,
                    )

    def test_finalization_stops_on_a_malformed_active_index(self) -> None:
        malformed = self.ACTIVE_INDEX_POPULATED.replace("\t", "\\t")
        for variant in self.COMPLETION_GATE_VARIANTS:
            with self.subTest(finalization=variant["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    self.build_completion_repo(
                        repo,
                        variant,
                        plan_status="ready_to_archive",
                        index_text=malformed,
                    )
                    finalizer = Path(str(variant["install"])) / "finalize-active-plan.sh"
                    (repo / finalizer).write_bytes(
                        (ROOT / str(variant["source"]) / "finalize-active-plan.sh").read_bytes()
                    )
                    (repo / "docs/plan/checked.md").write_text(
                        "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
                    )
                    before = self.durable_state(repo)
                    result = self.run_in_repo(repo, str(finalizer), self.COMPLETION_PLAN)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("active plan index", result.stderr)
                    self.assertEqual(self.durable_state(repo), before)

    ROOT_PLAN_COMMAND_MODULE = ROOT / "scripts/plan_validation_commands.py"
    TEMPLATE_PLAN_COMMAND_MODULE = (
        ROOT / "template/.project-agent-workflow/scripts/plan_validation_commands.py"
    )
    COPIER_VALIDATOR_SELECTOR = "python3 tests/select-copier-fixture-validator-tests.py"
    COPIER_VALIDATOR_DOMAINS = ("contract", "inventory", "execution", "grammar", "placement")

    def test_root_allowlist_accepts_the_copier_validator_selector_and_domains(self) -> None:
        module = load_module(self.ROOT_PLAN_COMMAND_MODULE, "copier_selector_allowlist")
        accepted = [
            self.COPIER_VALIDATOR_SELECTOR,
            f"{self.COPIER_VALIDATOR_SELECTOR} --all",
            f"{self.COPIER_VALIDATOR_SELECTOR} --staged",
            f"{self.COPIER_VALIDATOR_SELECTOR} --all --print-only --json",
            "python3 tests/test-copier-fixture-validator.py",
            *(
                f"python3 tests/copier_fixture_validator/{name}.py"
                for name in self.COPIER_VALIDATOR_DOMAINS
            ),
        ]
        module.parse_validation_commands(accepted)

    def test_root_allowlist_rejects_unsafe_copier_validator_commands(self) -> None:
        module = load_module(self.ROOT_PLAN_COMMAND_MODULE, "copier_selector_rejection")
        rejected = [
            f"{self.COPIER_VALIDATOR_SELECTOR} --all --staged",
            f"{self.COPIER_VALIDATOR_SELECTOR} --json --json",
            f"{self.COPIER_VALIDATOR_SELECTOR} --unknown",
            f"{self.COPIER_VALIDATOR_SELECTOR} tests/copier_fixture_validator/contract.py",
            "python3 /tmp/select-copier-fixture-validator-tests.py",
            "python3 ../tests/select-copier-fixture-validator-tests.py",
            "python3 tests/copier_fixture_validator/support.py",
            "python3 tests/copier_fixture_validator/__init__.py",
            "python3 tests/copier_fixture_validator/contract.py --verbose",
        ]
        for command in rejected:
            with self.subTest(command=command):
                with self.assertRaises(module.ValidationCommandError):
                    module.parse_validation_command(command)

    def test_the_generated_counterpart_never_allowlists_the_root_only_selector(self) -> None:
        module = load_module(self.TEMPLATE_PLAN_COMMAND_MODULE, "copier_selector_generated")
        rejected = [
            self.COPIER_VALIDATOR_SELECTOR,
            *(
                f"python3 tests/copier_fixture_validator/{name}.py"
                for name in self.COPIER_VALIDATOR_DOMAINS
            ),
        ]
        for command in rejected:
            with self.subTest(command=command):
                with self.assertRaises(module.ValidationCommandError):
                    module.parse_validation_command(command)


if __name__ == "__main__":
    unittest.main()
