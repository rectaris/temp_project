#!/usr/bin/env python3
"""Behavior tests for the parent-owned plan restructuring transaction."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import copy
import subprocess
import sys
import tempfile
import unittest
import shutil
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/restructure-plan.py"
SCENARIOS = ROOT / "tests/fixtures/orchestration/plan-restructuring-scenarios.json"
HOLDOUT = ROOT / "tests/fixtures/orchestration/plan-restructuring-holdout.json"


def digest(value: bytes | str) -> str:
    data = value.encode() if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    )
    return result.stdout.strip()


class PlanRestructureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "docs/plan/active").mkdir(parents=True)
        (self.repo / "docs/agent").mkdir(parents=True)
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "docs/agent/spec-index.yaml", self.repo / "docs/agent/spec-index.yaml")
        shutil.copy2(ROOT / "scripts/plan_validation_commands.py", self.repo / "scripts/plan_validation_commands.py")
        shutil.copy2(SCRIPT, self.repo / "scripts/restructure-plan.py")
        (self.repo / "docs/plan").joinpath("replanned.md").write_text(
            "# Replanned Plan Index\n\nid\tpath\tcontract\n", encoding="utf-8"
        )
        (self.repo / "docs/plan").joinpath("checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n", encoding="utf-8"
        )
        self.source_path = "docs/plan/active/001-source.md"
        self.acceptance = ["Preserve user data.", "Run the integration check."]
        source = self.source_text()
        (self.repo / self.source_path).write_text(source, encoding="utf-8")
        (self.repo / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nid\tpath\tstatus\n"
            f"001\t{self.source_path}\treplan_required\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "stopped source plan")
        self.spec_path = self.base / "restructure.json"
        self.spec = self.make_spec()
        self.write_spec()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def source_text(self) -> str:
        accepted = "\n".join(f"  - {item}" for item in self.acceptance)
        return (
            "# Source\n\n"
            "status: replan_required\n"
            "task_types:\n  - planning_docs\n"
            "review_class: C\n"
            "human_design_required: yes\n"
            "human_approval_status: approved\n"
            "write_scope:\n  - src/\n"
            "context_files:\n  - none\n"
            "required_specs:\n"
            "  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md\n"
            "  - docs/agent/SPEC_USER_COMMUNICATION.md\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n{accepted}\n"
            "replan_reason_codes:\n  - multiple_independent_invariants\n"
            "checked_summary_ja: 元計画。\n\n## Tasks\n\n- [ ] stopped\n"
        )

    def plan_content(self, path: str, mapped: list[str], *, integration: bool) -> str:
        all_paths = ["docs/plan/active/002-data.md", "docs/plan/active/003-integration.md"]
        successor_lines = "\n".join(f"  - {value}" for value in all_paths)
        digest_lines = "\n".join(f"  - {value}" for value in mapped)
        acceptance = self.acceptance if integration else [self.acceptance[0]]
        acceptance_lines = "\n".join(f"  - {value}" for value in acceptance)
        scope = "src/" if not integration else "tests/"
        return (
            f"# {'Integration' if integration else 'Data'}\n\n"
            "status: in_progress\n"
            "primary_invariant: preserve one independently validatable invariant\n"
            f"replan_source: {self.source_path}\n"
            "replan_contract: docs/plan/replanned/contracts/001-source.json\n"
            "integration_gates:\n  - verify the combined source acceptance\n"
            f"successor_plans:\n{successor_lines}\n"
            f"inherited_acceptance_digests:\n{digest_lines}\n"
            "task_types:\n  - planning_docs\n"
            "review_class: C\n"
            "human_design_required: yes\n"
            "human_approval_status: approved\n"
            f"write_scope:\n  - {scope}\n"
            "context_files:\n  - none\n"
            "required_specs:\n"
            "  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md\n"
            "  - docs/agent/SPEC_USER_COMMUNICATION.md\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n{acceptance_lines}\n"
            "checked_summary_ja: 後続計画。\n\n## Tasks\n\n- [ ] implement\n"
        )

    def make_spec(self) -> dict[str, object]:
        source_bytes = (self.repo / self.source_path).read_bytes()
        records = [{"text": text, "digest": digest(text)} for text in self.acceptance]
        digests = [record["digest"] for record in records]
        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        data_content = self.plan_content("docs/plan/active/002-data.md", [digests[0]], integration=False)
        integration_content = self.plan_content(
            "docs/plan/active/003-integration.md", digests, integration=True
        )
        return {
            "schema_version": 1,
            "source": {
                "path": self.source_path,
                "head": git(self.repo, "rev-parse", "HEAD"),
                "plan_digest": digest(source_bytes),
                "acceptance": records,
            },
            "reason_codes": ["multiple_independent_invariants"],
            "dirty_product_paths": [],
            "contract_path": "docs/plan/replanned/contracts/001-source.json",
            "archive_path": (
                f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{half}/001-source.md"
            ),
            "successors": [
                {
                    "id": "002",
                    "path": "docs/plan/active/002-data.md",
                    "content": data_content,
                    "acceptance_digests": [digests[0]],
                }
            ],
            "integration": {
                "id": "003",
                "path": "docs/plan/active/003-integration.md",
                "content": integration_content,
                "acceptance_digests": digests,
            },
        }

    def write_spec(self) -> None:
        self.spec_path.write_text(
            json.dumps(self.spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def run_command(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/restructure-plan.py", str(self.spec_path)],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_verify(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/restructure-plan.py", "--verify"],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def assert_source_unchanged(self) -> None:
        self.assertTrue((self.repo / self.source_path).is_file())
        self.assertFalse((self.repo / str(self.spec["contract_path"])).exists())
        self.assertIn("001\t", (self.repo / "docs/plan/plan.md").read_text(encoding="utf-8"))

    def test_success_preserves_requirements_and_switches_indexes(self) -> None:
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.repo / self.source_path).exists())
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(
            {key: contract["source"][key] for key in self.spec["source"]},
            self.spec["source"],
        )
        self.assertEqual(digest(contract["source"]["content"]), contract["source"]["plan_digest"])
        archive = self.repo / str(self.spec["archive_path"])
        self.assertIn("status: replanned", archive.read_text(encoding="utf-8"))
        self.assertIn("001\t", (self.repo / "docs/plan/replanned.md").read_text(encoding="utf-8"))
        active = (self.repo / "docs/plan/plan.md").read_text(encoding="utf-8")
        self.assertNotIn("001\t", active)
        self.assertIn("002\tdocs/plan/active/002-data.md\tin_progress", active)
        self.assertIn("003\tdocs/plan/active/003-integration.md\tin_progress", active)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_durable_contract_tampering_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["successors"][0]["content"] = contract["successors"][0]["content"].replace(
            "Preserve user data.", "Discard user data."
        )
        contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_durable_contract_rehashed_added_acceptance_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        successor = contract["successors"][0]
        successor["content"] = successor["content"].replace(
            "  - Preserve user data.\nchecked_summary_ja:",
            "  - Preserve user data.\n  - Clarification: discard user data.\nchecked_summary_ja:",
        )
        successor["content_digest"] = digest(successor["content"])
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_live_successor_acceptance_drift_is_rejected_without_contract_change(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        successor_path = self.repo / str(self.spec["successors"][0]["path"])  # type: ignore[index]
        successor_path.write_text(
            successor_path.read_text(encoding="utf-8").replace(
                "  - Preserve user data.\nchecked_summary_ja:",
                "  - Preserve user data.\n  - Clarification: discard user data.\nchecked_summary_ja:",
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_checked_successor_is_verified_and_checked_drift_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        successor = self.spec["successors"][0]  # type: ignore[index]
        active = self.repo / str(successor["path"])
        checked_relative = "docs/plan/checked/2026/08/01-15/002-data.md"
        checked = self.repo / checked_relative
        checked.parent.mkdir(parents=True)
        checked.write_text(
            active.read_text(encoding="utf-8").replace("status: in_progress", "status: checked", 1),
            encoding="utf-8",
        )
        active.unlink()
        (self.repo / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n002\t" + checked_relative + "\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)
        checked.write_text(
            checked.read_text(encoding="utf-8").replace(
                "  - Preserve user data.\nchecked_summary_ja:",
                "  - Preserve user data.\n  - Clarification: discard user data.\nchecked_summary_ja:",
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_tampered_source_digest_is_rejected_without_writes(self) -> None:
        self.spec["source"]["plan_digest"] = "sha256:" + "0" * 64  # type: ignore[index]
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

    def test_incomplete_acceptance_mapping_is_rejected(self) -> None:
        integration = self.spec["integration"]  # type: ignore[assignment]
        assert isinstance(integration, dict)
        integration["acceptance_digests"] = integration["acceptance_digests"][:1]
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

    def test_replaced_acceptance_text_and_duplicate_plan_id_are_rejected(self) -> None:
        fixture = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        requirement_case = next(
            item for item in fixture["scenarios"]
            if item["id"] == "negative-unauthorized-requirement-replacement"
        )
        self.assertEqual(
            requirement_case["input"],
            {"operation": "replace_source_acceptance_text", "explicit_user_authorization": False},
        )
        self.assertEqual(requirement_case["expected"]["next_action"], "reject_transition")
        integration = self.spec["integration"]
        assert isinstance(integration, dict)
        integration["content"] = str(integration["content"]).replace(
            "Run the integration check.", "Skip the integration check."
        )
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()
        self.spec = self.make_spec()
        successor = self.spec["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            "Preserve user data.", "Discard user data."
        )
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()
        self.spec = self.make_spec()
        integration = self.spec["integration"]
        assert isinstance(integration, dict)
        integration["id"] = "002"
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

    def test_added_clarification_requirement_and_reordered_mapping_are_rejected(self) -> None:
        successor = self.spec["successors"][0]  # type: ignore[index]
        original = str(successor["content"])
        successor["content"] = original.replace(
            "  - Preserve user data.\nchecked_summary_ja:",
            "  - Preserve user data.\n  - Clarification: discard user data.\nchecked_summary_ja:",
        )
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

        self.spec = self.make_spec()
        successor = self.spec["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            "  - Preserve user data.\nchecked_summary_ja:",
            "  - Preserve user data.\n  - Add an unrelated requirement.\nchecked_summary_ja:",
        )
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

        self.spec = self.make_spec()
        successor = self.spec["successors"][0]  # type: ignore[index]
        records = self.spec["source"]["acceptance"]  # type: ignore[index]
        second_digest = records[1]["digest"]
        successor["acceptance_digests"] = [second_digest, records[0]["digest"]]
        successor["content"] = str(successor["content"]).replace(
            f"inherited_acceptance_digests:\n  - {records[0]['digest']}",
            f"inherited_acceptance_digests:\n  - {second_digest}\n  - {records[0]['digest']}",
        ).replace(
            "acceptance:\n  - Preserve user data.",
            "acceptance:\n  - Run the integration check.\n  - Preserve user data.",
        )
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

    def test_fixed_hard_trigger_scenarios_complete_atomic_restructuring(self) -> None:
        fixture = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        hard_scenarios = [
            scenario for scenario in fixture["scenarios"]
            if scenario["expected"]["next_action"] == "atomic_restructure"
        ]
        self.assertEqual(len(hard_scenarios), 7)
        for index, scenario in enumerate(hard_scenarios, start=1):
            with self.subTest(scenario=scenario["id"]):
                scenario_repo = self.base / f"scenario-{index}"
                subprocess.run(
                    ["git", "clone", "-q", str(self.repo), str(scenario_repo)], check=True
                )
                git(scenario_repo, "config", "user.name", "Test")
                git(scenario_repo, "config", "user.email", "test@example.invalid")
                reason = scenario["expected"]["reason_code"]
                source = scenario_repo / self.source_path
                if reason != "multiple_independent_invariants":
                    source.write_text(
                        source.read_text(encoding="utf-8").replace(
                            "  - multiple_independent_invariants", f"  - {reason}"
                        ),
                        encoding="utf-8",
                    )
                    git(scenario_repo, "add", self.source_path)
                    git(scenario_repo, "commit", "-qm", f"stop for {reason}")
                scenario_spec = copy.deepcopy(self.spec)
                scenario_spec["source"]["head"] = git(scenario_repo, "rev-parse", "HEAD")
                scenario_spec["source"]["plan_digest"] = digest(source.read_bytes())
                scenario_spec["reason_codes"] = [reason]
                spec_path = self.base / f"scenario-{index}.json"
                spec_path.write_text(
                    json.dumps(scenario_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                transitioned = subprocess.run(
                    [sys.executable, "scripts/restructure-plan.py", str(spec_path)],
                    cwd=scenario_repo, check=False, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(transitioned.returncode, 0, transitioned.stderr)
                verified = subprocess.run(
                    [sys.executable, "scripts/restructure-plan.py", "--verify"],
                    cwd=scenario_repo, check=False, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(verified.returncode, 0, verified.stderr)
                self.assertFalse(source.exists())
                self.assertTrue((scenario_repo / str(scenario_spec["archive_path"])).is_file())
                self.assertTrue((scenario_repo / str(scenario_spec["contract_path"])).is_file())
                integration = scenario_spec["integration"]
                self.assertTrue((scenario_repo / str(integration["path"])).is_file())
                active_index = (scenario_repo / "docs/plan/plan.md").read_text(encoding="utf-8")
                self.assertIn(f"{integration['id']}\t{integration['path']}\tin_progress", active_index)

    def test_untuned_holdout_preserves_dirty_product_path_during_transition(self) -> None:
        scenario = json.loads(HOLDOUT.read_text(encoding="utf-8"))["scenarios"][0]
        self.assertIs(scenario["used_for_tuning"], False)
        self.assertEqual(
            scenario["expected"]["next_action"],
            "atomic_restructure_preserving_dirty_path",
        )
        dirty_relative = scenario["input"]["dirty_product_path"]
        dirty = self.repo / dirty_relative
        dirty.parent.mkdir(parents=True)
        dirty_bytes = b"project_owned: true\n"
        dirty.write_bytes(dirty_bytes)
        self.spec["dirty_product_paths"] = [dirty_relative]
        integration = self.spec["integration"]
        integration["content"] = str(integration["content"]).replace(
            "write_scope:\n  - tests/",
            "write_scope:\n  - tests/\n  - config/",
        )
        self.spec["reason_codes"] = [scenario["expected"]["reason_code"]]
        source = self.repo / self.source_path
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "  - multiple_independent_invariants",
                f"  - {scenario['expected']['reason_code']}",
            ),
            encoding="utf-8",
        )
        git(self.repo, "add", self.source_path)
        git(self.repo, "commit", "-qm", "record holdout security drift")
        self.spec["source"]["head"] = git(self.repo, "rev-parse", "HEAD")
        self.spec["source"]["plan_digest"] = digest(source.read_bytes())
        self.write_spec()
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(dirty.read_bytes(), dirty_bytes)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_collision_and_path_traversal_are_rejected(self) -> None:
        destination = self.repo / "docs/plan/active/002-data.md"
        destination.write_text("collision\n", encoding="utf-8")
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()
        destination.unlink()
        self.spec["contract_path"] = "docs/plan/replanned/contracts/../escape.json"
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

    def test_dirty_product_path_requires_successor_scope(self) -> None:
        dirty = self.repo / "config/user.yaml"
        dirty.parent.mkdir()
        dirty.write_text("user: true\n", encoding="utf-8")
        self.spec["dirty_product_paths"] = ["config/user.yaml"]
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assertEqual(dirty.read_text(encoding="utf-8"), "user: true\n")
        self.assert_source_unchanged()

    def test_injected_midwrite_failure_rolls_back_metadata(self) -> None:
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            spec = importlib.util.spec_from_file_location("restructure_test_module", SCRIPT)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.assertRaises(OSError):
                module.execute(self.spec_path, fail_after_writes=2)
        finally:
            os.chdir(old_cwd)
        self.assert_source_unchanged()
        self.assertEqual(
            (self.repo / "docs/plan/replanned.md").read_text(encoding="utf-8"),
            "# Replanned Plan Index\n\nid\tpath\tcontract\n",
        )
        self.assertFalse((self.repo / "docs/plan/replanned/contracts").exists())

    def test_symlinked_destination_ancestor_is_rejected(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        replanned = self.repo / "docs/plan/replanned"
        replanned.symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assertTrue((self.repo / self.source_path).is_file())
        self.assertEqual(list(outside.iterdir()), [])

    def test_concurrent_transition_has_one_winner(self) -> None:
        commands = [
            subprocess.Popen(
                [sys.executable, str(SCRIPT), str(self.spec_path)],
                cwd=self.repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(2)
        ]
        results = [process.communicate()[0:2] + (process.returncode,) for process in commands]
        self.assertEqual(sum(returncode == 0 for _, _, returncode in results), 1, results)


if __name__ == "__main__":
    unittest.main()
