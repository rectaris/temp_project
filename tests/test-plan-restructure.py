#!/usr/bin/env python3
"""Behavior tests for the parent-owned plan restructuring transaction."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import copy
import subprocess
import sys
import tempfile
import unittest
import shutil
from datetime import date
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/restructure-plan.py"
SCENARIOS = ROOT / "tests/fixtures/orchestration/plan-restructuring-scenarios.json"
HOLDOUT = ROOT / "tests/fixtures/orchestration/plan-restructuring-holdout.json"


SHELVED_FIELDS = "\nshelved_reason: deprioritized by the owner\nshelved_at: 2026-08-30"


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
        self.original_dont_write_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
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
        publisher_path = "docs/plan/active/190-migrate-live-plan-contracts.md"
        (self.repo / publisher_path).write_text(
            "# Publish companion baseline\n\n"
            "status: deferred\n"
            "write_scope:\n"
            "  - docs/plan/replanned/baselines/live-validation-successors-v1.json\n"
            "context_files:\n"
            "  - none\n",
            encoding="utf-8",
        )
        (self.repo / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nid\tpath\tstatus\n"
            f"001\t{self.source_path}\treplan_required\n"
            f"190\t{publisher_path}\tdeferred\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "stopped source plan")
        self.spec_path = self.base / "restructure.json"
        self.spec = self.make_spec()
        self.write_spec()

    def tearDown(self) -> None:
        self.temporary.cleanup()
        sys.dont_write_bytecode = self.original_dont_write_bytecode

    def test_repository_active_predecessors_are_valid(self) -> None:
        old_cwd = Path.cwd()
        try:
            os.chdir(ROOT)
            spec = importlib.util.spec_from_file_location(
                "root_predecessor_validation", SCRIPT
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.validate_repository_active_predecessors()
        finally:
            os.chdir(old_cwd)

    def test_empty_contract_repository_does_not_require_companion(self) -> None:
        (self.repo / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nNo active development items.\n",
            encoding="utf-8",
        )
        (self.repo / self.source_path).unlink()
        publisher = self.repo / "docs/plan/active/190-migrate-live-plan-contracts.md"
        publisher.unlink()
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def publisher_plan(self) -> Path:
        return self.repo / "docs/plan/active/190-migrate-live-plan-contracts.md"

    def reserve_ids(self, plan: Path, block: str) -> None:
        text = plan.read_text(encoding="utf-8")
        assert "reserved_plan_ids" not in text
        plan.write_text(
            text.replace("write_scope:\n", block + "write_scope:\n", 1),
            encoding="utf-8",
        )

    def set_context_files(self, plan: Path, entries: list[str]) -> None:
        text = plan.read_text(encoding="utf-8")
        rendered = "context_files:\n" + "".join(f"  - {entry}\n" for entry in entries)
        start = text.index("context_files:\n")
        end = start + len("context_files:\n")
        while text[end:].startswith("  - "):
            end = text.index("\n", end) + 1
        plan.write_text(text[:start] + rendered + text[end:], encoding="utf-8")

    def test_repository_rejects_an_unresolved_active_plan_context_file(self) -> None:
        publisher = self.publisher_plan()
        for case, entries, fragment in (
            (
                "missing plan",
                ["docs/plan/active/197-absent.md"],
                "context file does not resolve: docs/plan/active/197-absent.md",
            ),
            (
                "missing document",
                ["docs/agent/SPEC_ABSENT.md"],
                "context file does not resolve: docs/agent/SPEC_ABSENT.md",
            ),
            (
                "directory instead of file",
                ["docs/plan/active"],
                "context file does not resolve: docs/plan/active",
            ),
            (
                "one stale entry beside resolving entries",
                [self.source_path, "docs/plan/active/197-absent.md"],
                "context file does not resolve: docs/plan/active/197-absent.md",
            ),
        ):
            with self.subTest(case=case):
                self.set_context_files(publisher, entries)
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(
                    f"active plan docs/plan/active/190-migrate-live-plan-contracts.md "
                    f"{fragment}",
                    verified.stderr,
                )
                self.set_context_files(publisher, ["none"])
                self.assertEqual(self.run_verify().returncode, 0)

    def test_repository_accepts_resolving_active_plan_context_files(self) -> None:
        publisher = self.publisher_plan()
        for case, entries in (
            ("none sentinel", ["none"]),
            ("resolving plan path", [self.source_path]),
            ("resolving index path", ["docs/plan/plan.md", self.source_path]),
        ):
            with self.subTest(case=case):
                self.set_context_files(publisher, entries)
                verified = self.run_verify()
                self.assertEqual(verified.returncode, 0, verified.stderr)

    def archive_context_target(self) -> str:
        checked_relative = "docs/plan/checked/2026/08/16-31/077-archived.md"
        checked_file = self.repo / checked_relative
        checked_file.parent.mkdir(parents=True, exist_ok=True)
        checked_file.write_text(
            "# Archived\n\nstatus: checked\nwrite_scope:\n  - docs/plan/\n"
            "context_files:\n  - none\n",
            encoding="utf-8",
        )
        (self.repo / "docs/plan/checked.md").write_text(
            f"# Checked Plan Index\n\nid\tpath\n077\t{checked_relative}\n",
            encoding="utf-8",
        )
        return "docs/plan/active/077-archived.md"

    def test_a_live_plan_may_not_name_an_archived_former_active_path(self) -> None:
        pending = self.archive_context_target()
        self.set_context_files(self.publisher_plan(), [pending])
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(
            "active plan docs/plan/active/190-migrate-live-plan-contracts.md context "
            f"file names the archived former active path: {pending}",
            verified.stderr,
        )

    def test_a_backlog_resident_may_not_name_an_archived_former_active_path(
        self,
    ) -> None:
        pending = self.archive_context_target()
        backlog = self.repo / "docs/plan/backlog/181-deferred-referrer.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            "# Deferred referrer\n\n"
            "status: backlog\n"
            "write_scope:\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "context_files:\n"
            f"  - {pending}\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(
            "live plan docs/plan/backlog/181-deferred-referrer.md context file names "
            f"the archived former active path: {pending}",
            verified.stderr,
        )
        backlog.write_text(
            backlog.read_text(encoding="utf-8").replace(
                pending, "docs/plan/checked/2026/08/16-31/077-archived.md", 1
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_a_transaction_may_archive_a_referenced_context_plan(self) -> None:
        self.set_context_files(self.publisher_plan(), [self.source_path])
        self.assertEqual(self.run_verify().returncode, 0)
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        archive = str(self.spec["archive_path"])
        self.assertIn(
            f"context_files:\n  - {archive}\n",
            self.publisher_plan().read_text(encoding="utf-8"),
        )

    def test_a_transaction_rebinds_a_backlog_referrer_context_entry(self) -> None:
        backlog = self.repo / "docs/plan/backlog/181-deferred-referrer.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            "# Deferred referrer\n\n"
            "status: backlog\n"
            "write_scope:\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "context_files:\n"
            f"  - {self.source_path}\n",
            encoding="utf-8",
        )
        git(self.repo, "add", "docs/plan/backlog")
        git(self.repo, "commit", "-qm", "add deferred referrer")
        self.spec["source"]["head"] = git(  # type: ignore[index]
            self.repo, "rev-parse", "HEAD"
        )
        self.write_spec()
        self.assertEqual(self.run_verify().returncode, 0)
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        archive = str(self.spec["archive_path"])
        self.assertIn(
            f"context_files:\n  - {archive}\n",
            backlog.read_text(encoding="utf-8"),
        )

    def test_finalization_rebinds_every_live_referrer_context_entry(self) -> None:
        finalizer = self.repo / "scripts/finalize-active-plan.sh"
        shutil.copy2(ROOT / "scripts/finalize-active-plan.sh", finalizer)
        source = "docs/plan/active/077-finalized.md"
        (self.repo / source).write_text(
            "# Finalized\n\n"
            "status: ready_to_archive\n"
            "checked_summary_ja: 参照つきの計画を完了する。\n"
            "write_scope:\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "context_files:\n"
            "  - none\n"
            "\n"
            "## Validation Notes\n"
            "\n"
            "- finalization referrer rebinding checked.\n",
            encoding="utf-8",
        )
        backlog = self.repo / "docs/plan/backlog/181-deferred-referrer.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            "# Deferred referrer\n\n"
            "status: backlog\n"
            "write_scope:\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "context_files:\n"
            f"  - {source}\n"
            "predecessor_plans:\n"
            f"  - {source}\n",
            encoding="utf-8",
        )
        loose = self.repo / "docs/plan/backlog/182-loose-referrer.md"
        loose.write_text(
            "# Loose referrer\n\n"
            "status: backlog\n"
            "write_scope:\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "context_files:\n"
            f"  -   {source}\n",
            encoding="utf-8",
        )
        self.set_context_files(self.publisher_plan(), [source])
        index = self.repo / "docs/plan/plan.md"
        index.write_text(
            index.read_text(encoding="utf-8") + f"077\t{source}\tready_to_archive\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)
        finalized = subprocess.run(
            ["sh", "scripts/finalize-active-plan.sh", source],
            cwd=self.repo,
            text=True,
            capture_output=True,
        )
        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        archive = finalized.stdout.strip()
        self.assertTrue((self.repo / archive).is_file(), archive)
        self.assertIn(
            f"context_files:\n  - {archive}\n",
            self.publisher_plan().read_text(encoding="utf-8"),
        )
        backlog_text = backlog.read_text(encoding="utf-8")
        self.assertIn(f"context_files:\n  - {archive}\n", backlog_text)
        self.assertIn(f"predecessor_plans:\n  - {source}\n", backlog_text)
        self.assertIn(
            f"context_files:\n  - {archive}\n",
            loose.read_text(encoding="utf-8"),
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_context_relocation_projects_only_unambiguous_archived_entries(
        self,
    ) -> None:
        module = self.load_restructure_module("context_relocation_module")
        pending = self.archive_context_target()
        checked = "docs/plan/checked/2026/08/16-31/077-archived.md"
        content = (
            "# Referrer\n\n"
            "status: deferred\n"
            "context_files:\n"
            f"  - {pending}\n"
            "  - docs/agent/spec-index.yaml\n"
            f"  - {self.source_path}\n"
            "  - docs/plan/active/198-never-archived.md\n"
            "predecessor_plans:\n"
            f"  - {pending}\n"
            "\n"
            "## Body\n"
            "\n"
            f"- {pending}\n"
        )
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            projected = module.project_context_archive_relocation(content)
        finally:
            os.chdir(old_cwd)
        self.assertEqual(
            projected,
            content.replace(f"context_files:\n  - {pending}\n", f"context_files:\n  - {checked}\n", 1),
        )

    def test_a_protected_referrer_is_rebound_and_stays_lifecycle_comparable(
        self,
    ) -> None:
        self.set_context_files(self.publisher_plan(), [self.source_path])
        module = self.load_restructure_module("protected_referrer_module")
        publisher = "docs/plan/active/190-migrate-live-plan-contracts.md"
        archive = str(self.spec["archive_path"])
        original = (self.repo / publisher).read_text(encoding="utf-8")
        state = {"archived_plans": {self.source_path: archive}, "updated_files": []}
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            module.apply_referrer_context_rebinds(state)
        finally:
            os.chdir(old_cwd)
        rebound = original.replace(
            f"context_files:\n  - {self.source_path}\n",
            f"context_files:\n  - {archive}\n",
            1,
        )
        self.assertEqual(state["updated_files"], [(publisher, original, rebound)])
        declared = {
            "archived_plans": {self.source_path: archive},
            "updated_files": [(publisher, original, original)],
        }
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            module.apply_referrer_context_rebinds(declared)
        finally:
            os.chdir(old_cwd)
        self.assertEqual(declared["updated_files"], [(publisher, original, original)])

    def test_a_rebound_referrer_passes_lifecycle_comparison(self) -> None:
        module = self.load_restructure_module("rebound_lifecycle_module")
        pending = self.archive_context_target()
        checked = "docs/plan/checked/2026/08/16-31/077-archived.md"
        baseline = (
            "# Successor\n\n"
            "status: deferred\n"
            "completion_deferred_reason: predecessor must be checked\n"
            "context_files:\n"
            f"  - {pending}\n"
        )
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            module.validate_lifecycle_evolution(
                baseline, baseline.replace(pending, checked, 1), "probe"
            )
            with self.assertRaises(module.RestructureError) as raised:
                module.validate_lifecycle_evolution(
                    baseline,
                    baseline.replace(pending, "docs/agent/spec-index.yaml", 1),
                    "probe",
                )
        finally:
            os.chdir(old_cwd)
        self.assertIn("deferred projection changed", str(raised.exception))

    def test_a_surviving_archived_context_reference_is_rejected(self) -> None:
        self.set_context_files(self.publisher_plan(), [self.source_path])
        module = self.load_restructure_module("surviving_reference_module")
        publisher = "docs/plan/active/190-migrate-live-plan-contracts.md"
        archived = {self.source_path: str(self.spec["archive_path"])}
        with self.assertRaises(module.RestructureError) as raised:
            module.verify_no_surviving_archived_context_references(
                {"archived_plans": archived}, []
            )
        self.assertIn("would still name the archived plan path", str(raised.exception))
        module.verify_no_surviving_archived_context_references(
            {"archived_plans": archived},
            [{"path": publisher, "target_content": None}],
        )

    def test_created_plan_context_is_enforced_before_any_mutation(self) -> None:
        extra = self.repo / "docs/agent/EXTRA.md"
        extra.write_text("# Extra\n", encoding="utf-8")
        git(self.repo, "add", "docs/agent/EXTRA.md")
        git(self.repo, "commit", "-qm", "add extra context document")
        git(self.repo, "rm", "-q", "docs/agent/EXTRA.md")
        self.spec = self.make_spec()
        self.spec["dirty_product_paths"] = ["docs/agent/EXTRA.md"]
        self.spec["integration"]["content"] = str(
            self.spec["integration"]["content"]
        ).replace(
            "preservation_scope:\n  - none\n",
            "preservation_scope:\n  - docs/agent/EXTRA.md\n",
            1,
        ).replace(
            "context_files:\n  - none\n",
            "context_files:\n  - docs/agent/EXTRA.md\n",
            1,
        )
        self.write_spec()
        result = self.run_command()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "active plan docs/plan/active/003-integration.md "
            "context file does not resolve: docs/agent/EXTRA.md",
            result.stderr,
        )
        self.assertNotIn("prospective repository verification failed", result.stderr)
        self.assertEqual(list(self.journal_directory().glob("*.json")), [])
        self.assert_source_unchanged()

    def test_created_plan_context_may_name_a_path_the_transaction_writes(self) -> None:
        self.spec["integration"]["content"] = str(
            self.spec["integration"]["content"]
        ).replace(
            "context_files:\n  - none\n",
            "context_files:\n  - docs/plan/active/002-data.md\n",
            1,
        )
        self.write_spec()
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_context_exemption_requires_an_existing_archive_file(self) -> None:
        pending = self.archive_context_target()
        (self.repo / "docs/plan/checked/2026/08/16-31/077-archived.md").unlink()
        self.set_context_files(self.publisher_plan(), [pending])
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(f"context file does not resolve: {pending}", verified.stderr)

    def test_context_exemption_requires_matching_archive_identity(self) -> None:
        publisher = self.publisher_plan()
        entry = "docs/plan/active/077-archived.md"
        for name in ("077-archived.md", "077-other-name.md"):
            archive = self.repo / "docs/plan/checked/2026/08/16-31" / name
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_text(
                "# Other\n\nstatus: checked\nwrite_scope:\n  - docs/plan/\n"
                "context_files:\n  - none\n",
                encoding="utf-8",
            )
        index = self.repo / "docs/plan/checked.md"
        self.set_context_files(publisher, [entry])
        for case, row in (
            (
                "same id, different file name",
                "077\tdocs/plan/checked/2026/08/16-31/077-other-name.md\n",
            ),
            (
                "same file name, different id",
                "078\tdocs/plan/checked/2026/08/16-31/077-archived.md\n",
            ),
        ):
            with self.subTest(case=case):
                index.write_text(
                    f"# Checked Plan Index\n\nid\tpath\n{row}", encoding="utf-8"
                )
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(f"context file does not resolve: {entry}", verified.stderr)

    def test_repository_rejects_context_files_outside_the_repository(self) -> None:
        publisher = self.publisher_plan()
        link = self.repo / "docs/plan/linked.md"
        link.symlink_to(self.repo / "docs/plan/plan.md")
        for case, entry, fragment in (
            ("absolute", "/etc/hostname", "is not repository relative: /etc/hostname"),
            (
                "parent escape",
                "docs/../../outside.md",
                "is not repository relative: docs/../../outside.md",
            ),
            (
                "symlink target",
                "docs/plan/linked.md",
                "symlink path component is not allowed: docs/plan/linked.md",
            ),
        ):
            with self.subTest(case=case):
                self.set_context_files(publisher, [entry])
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(fragment, verified.stderr)
                self.set_context_files(publisher, ["none"])
                self.assertEqual(self.run_verify().returncode, 0)

    def test_context_resolution_ignores_body_references_and_backlog_plans(self) -> None:
        publisher = self.publisher_plan()
        publisher.write_text(
            publisher.read_text(encoding="utf-8")
            + "\n## Decisions\n\n"
            "- Create docs/plan/active/211-unborn.md in this transaction.\n",
            encoding="utf-8",
        )
        backlog = self.repo / "docs/plan/backlog/047-later.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            "# Later\n\nstatus: backlog\nwrite_scope:\n  - docs/plan/\n"
            "context_files:\n  - docs/plan/active/197-absent.md\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_repository_rejects_malformed_plan_id_reservations(self) -> None:
        publisher = self.publisher_plan()
        original = publisher.read_text(encoding="utf-8")
        for case, block, fragment in (
            (
                "inline scalar",
                "reserved_plan_ids: 002\n",
                "malformed reserved plan id list",
            ),
            (
                "empty list",
                "reserved_plan_ids:\n",
                "malformed reserved plan id list",
            ),
            (
                "short id",
                "reserved_plan_ids:\n  - 02\n",
                "malformed reserved plan id: 02",
            ),
            (
                "non-numeric id",
                "reserved_plan_ids:\n  - abc\n",
                "malformed reserved plan id: abc",
            ),
            (
                "duplicate id",
                "reserved_plan_ids:\n  - 002\n  - 002\n",
                "duplicate reserved plan id",
            ),
            (
                "descending ids",
                "reserved_plan_ids:\n  - 003\n  - 002\n",
                "reserved plan ids out of order",
            ),
            (
                "own id",
                "reserved_plan_ids:\n  - 190\n",
                "reserves its own plan id",
            ),
        ):
            with self.subTest(case=case):
                publisher.write_text(
                    original.replace("write_scope:\n", block + "write_scope:\n", 1),
                    encoding="utf-8",
                )
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(fragment, verified.stderr)
                publisher.write_text(original, encoding="utf-8")
        self.assertEqual(self.run_verify().returncode, 0)

    def test_repository_rejects_conflicting_plan_id_reservations(self) -> None:
        self.reserve_ids(
            self.publisher_plan(), "reserved_plan_ids:\n  - 002\n  - 003\n"
        )
        self.reserve_ids(
            self.repo / self.source_path, "reserved_plan_ids:\n  - 003\n"
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("plan id 003 is reserved by two live plans", verified.stderr)

    def test_repository_rejects_unauthorized_use_of_a_reserved_plan_id(self) -> None:
        publisher = self.publisher_plan()
        self.reserve_ids(publisher, "reserved_plan_ids:\n  - 042\n")
        occupant = self.repo / "docs/plan/backlog/042-occupant.md"
        occupant.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "# Occupant\n\nstatus: backlog\nwrite_scope:\n  - docs/plan/\n"
            "context_files:\n  - none\n"
        )
        for case, manifest, fragment in (
            ("no reserved_by", body, "uses plan id 042 reserved by"),
            (
                "wrong reserved_by",
                body.replace("status: backlog\n", "status: backlog\nreserved_by: 001\n"),
                "uses plan id 042 reserved by",
            ),
            (
                "malformed reserved_by",
                body.replace("status: backlog\n", "status: backlog\nreserved_by: 19\n"),
                "malformed reserved_by plan id",
            ),
        ):
            with self.subTest(case=case):
                occupant.write_text(manifest, encoding="utf-8")
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(fragment, verified.stderr)
        occupant.write_text(
            body.replace("status: backlog\n", "status: backlog\nreserved_by: 190\n"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_a_backlog_plan_reserves_plan_ids_and_an_archive_releases_them(
        self,
    ) -> None:
        backlog = self.repo / "docs/plan/backlog/046-reserver.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            "# Reserver\n\nstatus: backlog\nreserved_plan_ids:\n  - 002\n"
            "write_scope:\n  - docs/plan/\ncontext_files:\n  - none\n",
            encoding="utf-8",
        )
        occupant = self.repo / "docs/plan/checked/2026/08/16-31/002-occupant.md"
        occupant.parent.mkdir(parents=True, exist_ok=True)
        occupant.write_text(
            "# Occupant\n\nstatus: checked\n", encoding="utf-8"
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("uses plan id 002 reserved by", verified.stderr)
        nested = self.repo / "docs/plan/backlog/deferred/046-reserver.md"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text(backlog.read_text(encoding="utf-8"), encoding="utf-8")
        backlog.unlink()
        nested_verified = self.run_verify()
        self.assertNotEqual(nested_verified.returncode, 0, nested_verified.stdout)
        self.assertIn(
            "uses plan id 002 reserved by "
            "docs/plan/backlog/deferred/046-reserver.md",
            nested_verified.stderr,
        )
        nested.unlink()
        self.assertEqual(self.run_verify().returncode, 0)

    def test_transaction_rejects_creating_a_reserved_plan_id(self) -> None:
        self.reserve_ids(
            self.publisher_plan(), "reserved_plan_ids:\n  - 002\n  - 003\n"
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "reserve successor ids")
        self.spec = self.make_spec()
        self.write_spec()
        result = self.run_command()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "created plan docs/plan/active/002-data.md "
            "uses plan id 002 reserved by",
            result.stderr,
        )
        self.assert_source_unchanged()
        self.assertEqual(self.run_verify().returncode, 0)

        for entry in (
            self.spec["successors"][0],  # type: ignore[index]
            self.spec["integration"],  # type: ignore[index]
        ):
            entry["content"] = str(entry["content"]).replace(  # type: ignore[index]
                "status: ", "reserved_by: 001\nstatus: ", 1
            )
        self.write_spec()
        mismatched = self.run_command()
        self.assertNotEqual(mismatched.returncode, 0, mismatched.stdout)
        self.assertIn(
            "created plan docs/plan/active/002-data.md "
            "uses plan id 002 reserved by",
            mismatched.stderr,
        )
        self.assert_source_unchanged()
        self.assertEqual(self.run_verify().returncode, 0)

        self.spec = self.make_spec()
        for entry in (
            self.spec["successors"][0],  # type: ignore[index]
            self.spec["integration"],  # type: ignore[index]
        ):
            entry["content"] = str(entry["content"]).replace(  # type: ignore[index]
                "status: ", "reserved_by: 19\nstatus: ", 1
            )
        self.write_spec()
        malformed = self.run_command()
        self.assertNotEqual(malformed.returncode, 0, malformed.stdout)
        self.assertIn(
            "created plan docs/plan/active/002-data.md "
            "declares a malformed reserved_by plan id",
            malformed.stderr,
        )
        self.assert_source_unchanged()
        self.assertEqual(self.run_verify().returncode, 0)

    def test_coupled_transaction_rejects_creating_a_reserved_plan_id(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        self.reserve_ids(
            self.publisher_plan(), "reserved_plan_ids:\n  - 005\n"
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "reserve the coupled successor id")
        coupled["source_head"] = git(self.repo, "rev-parse", "HEAD")
        result = self.run_spec_data(coupled, "coupled-reserved.json")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "created plan docs/plan/active/005-coupled-integration.md "
            "uses plan id 005 reserved by",
            result.stderr,
        )
        self.assertFalse(
            (self.repo / "docs/plan/active/005-coupled-integration.md").exists()
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_transaction_accepts_a_declared_reserved_plan_id_consumption(
        self,
    ) -> None:
        self.reserve_ids(
            self.publisher_plan(), "reserved_plan_ids:\n  - 002\n  - 003\n"
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "reserve successor ids")
        self.spec = self.make_spec()
        for entry in (
            self.spec["successors"][0],  # type: ignore[index]
            self.spec["integration"],  # type: ignore[index]
        ):
            entry["content"] = str(entry["content"]).replace(  # type: ignore[index]
                "status: ", "reserved_by: 190\nstatus: ", 1
            )
        self.write_spec()
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        created = self.repo / "docs/plan/active/002-data.md"
        self.assertIn("reserved_by: 190", created.read_text(encoding="utf-8"))
        self.assertEqual(self.run_verify().returncode, 0)

    def test_a_manifest_without_reservation_fields_stays_valid(self) -> None:
        publisher = self.publisher_plan().read_text(encoding="utf-8")
        self.assertNotIn("reserved_plan_ids", publisher)
        self.assertNotIn("reserved_by", publisher)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_repository_validates_reserved_by_on_every_plan_file(self) -> None:
        publisher = self.publisher_plan()
        original = publisher.read_text(encoding="utf-8")
        for case, line in (
            ("bare reserved_by", "reserved_by:\n"),
            ("four-digit id", "reserved_by: 1900\n"),
            ("non-numeric id", "reserved_by: abc\n"),
        ):
            with self.subTest(case=case):
                publisher.write_text(
                    original.replace("write_scope:\n", line + "write_scope:\n", 1),
                    encoding="utf-8",
                )
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn("malformed reserved_by plan id", verified.stderr)
        publisher.write_text(original, encoding="utf-8")
        self.assertEqual(self.run_verify().returncode, 0)

    def test_repository_rejects_reserved_plan_ids_in_every_plan_directory(
        self,
    ) -> None:
        self.reserve_ids(
            self.publisher_plan(), "reserved_plan_ids:\n  - 042\n  - 043\n"
        )
        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        for case, relative in (
            ("active", "docs/plan/active/042-occupant.md"),
            (
                "replanned",
                f"docs/plan/replanned/{today.year:04d}/{today.month:02d}"
                f"/{half}/043-occupant.md",
            ),
        ):
            with self.subTest(case=case):
                occupant = self.repo / relative
                occupant.parent.mkdir(parents=True, exist_ok=True)
                occupant.write_text(
                    "# Occupant\n\nstatus: replan_required\n", encoding="utf-8"
                )
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(f"plan {relative} uses plan id", verified.stderr)
                occupant.unlink()
        self.assertEqual(self.run_verify().returncode, 0)

    def test_activation_cannot_forge_plan_id_reservations(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "coupled-reservation-forge.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(successor_path)
        module = self.load_restructure_module("reservation_activation_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        record = activation["rebindings"][0]  # type: ignore[index]
        original = (self.repo / target_path).read_text(encoding="utf-8")
        honest = json.dumps(record["replacements"], sort_keys=True)
        for case, forged in (
            ("reserved_plan_ids", "reserved_plan_ids:\n  - 050\n"),
            ("reserved_by", "reserved_by: 001\n"),
        ):
            with self.subTest(case=case):
                record["replacements"] = json.loads(honest)
                reason = ""
                for replacement in record["replacements"]:
                    if replacement["field"] == "completion_deferred_reason":
                        reason = str(replacement["old"])
                        replacement["new"] = forged
                        break
                self.assertTrue(reason)
                updated = (
                    original.replace(
                        "status: deferred\n", "status: in_progress\n", 1
                    )
                    .replace(reason, forged, 1)
                    .replace(successor_path, checked_path, 1)
                )
                record["updated_content_digest"] = digest(updated)
                forged_result = self.run_spec_data(
                    activation, f"activation-forge-{case}.json"
                )
                self.assertNotEqual(forged_result.returncode, 0, forged_result.stdout)
                self.assertIn(
                    "activation changes protected plan identity",
                    forged_result.stderr,
                )
                live = (self.repo / target_path).read_text(encoding="utf-8")
                self.assertEqual(live, original)
                self.assertNotIn("reserved_plan_ids", live)
                self.assertNotIn("reserved_by", live)
                self.assertEqual(self.run_verify().returncode, 0)

    def test_repository_active_predecessors_reject_cross_id_index_rows(self) -> None:
        active_index = self.repo / "docs/plan/plan.md"
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                f"001\t{self.source_path}\treplan_required",
                f"999\t{self.source_path}\treplan_required",
            ),
            encoding="utf-8",
        )
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            spec = importlib.util.spec_from_file_location(
                "cross_id_predecessor_validation",
                self.repo / "scripts/restructure-plan.py",
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.assertRaisesRegex(
                module.RestructureError, "active plan identity mismatch"
            ):
                module.validate_repository_active_predecessors()
        finally:
            os.chdir(old_cwd)

    def source_text(self) -> str:
        accepted = "\n".join(f"  - {item}" for item in self.acceptance)
        return (
            "# Source\n\n"
            "status: replan_required\n"
            "# Preserve this source annotation.\n"
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
        acceptance = [value for value in self.acceptance if digest(value) in mapped]
        acceptance_lines = "\n".join(f"  - {value}" for value in acceptance)
        witness_lines = "\n".join(
            "  - "
            + json.dumps(
                {
                    "acceptance_sha256": digest(value),
                    "stage": "focused",
                    "witness": "git diff --check",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for value in acceptance
        )
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
            "preservation_scope:\n  - none\n"
            "context_files:\n  - none\n"
            "required_specs:\n"
            "  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md\n"
            "  - docs/agent/SPEC_USER_COMMUNICATION.md\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "focused_validation:\n  - git diff --check\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n{acceptance_lines}\n"
            "validation_witness_schema: 1\n"
            f"validation_witness_map:\n{witness_lines}\n"
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

    def add_sequential_successor(self) -> None:
        successors = self.spec["successors"]
        integration = self.spec["integration"]
        assert isinstance(successors, list)
        assert isinstance(integration, dict)
        extra = copy.deepcopy(successors[0])
        extra["id"] = "004"
        extra["path"] = "docs/plan/active/004-follow-up.md"
        successors.append(extra)
        old_paths = (
            "successor_plans:\n"
            "  - docs/plan/active/002-data.md\n"
            "  - docs/plan/active/003-integration.md\n"
        )
        new_paths = (
            "successor_plans:\n"
            "  - docs/plan/active/002-data.md\n"
            "  - docs/plan/active/004-follow-up.md\n"
            "  - docs/plan/active/003-integration.md\n"
        )
        for entry in [*successors, integration]:
            entry["content"] = str(entry["content"]).replace(old_paths, new_paths)

    def convert_contract_to_schema_one(
        self,
        scopes: list[list[str] | None],
        dirty_paths: list[str],
    ) -> dict[str, object]:
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["schema_version"] = 1
        contract["dirty_product_paths"] = dirty_paths
        self.assertEqual(len(scopes), len(contract["successors"]))
        for successor, scope in zip(contract["successors"], scopes, strict=True):
            for key in (
                "authoritative_validation",
                "authoritative_validation_digest",
                "validation_witness_schema",
                "validation_witness_map_digest",
            ):
                successor.pop(key)
            replacement = ""
            if scope is not None:
                values = scope or ["none"]
                replacement = "preservation_scope:\n" + "".join(
                    f"  - {value}\n" for value in values
                )
            successor["content"] = successor["content"].replace(
                "preservation_scope:\n  - none\n",
                replacement,
            )
            successor["content_digest"] = digest(successor["content"])
            live = self.repo / successor["path"]
            live.write_text(
                live.read_text(encoding="utf-8").replace(
                    "preservation_scope:\n  - none\n",
                    replacement,
                ),
                encoding="utf-8",
            )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return contract

    def load_restructure_module(self, label: str):
        old_cwd = Path.cwd()
        old_dont_write_bytecode = sys.dont_write_bytecode
        try:
            os.chdir(self.repo)
            sys.dont_write_bytecode = True
            spec = importlib.util.spec_from_file_location(
                label,
                self.repo / "scripts/restructure-plan.py",
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            sys.dont_write_bytecode = old_dont_write_bytecode
            os.chdir(old_cwd)

    def coupled_successor_content(
        self,
        *,
        path: str,
        contract_path: str,
        source_paths: list[str],
        source_records: list[tuple[str, list[dict[str, str]]]],
        predecessor: str | None,
    ) -> tuple[str, list[dict[str, object]]]:
        mappings = [
            {
                "source_id": source_id,
                "acceptance_digests": [record["digest"] for record in records],
            }
            for source_id, records in source_records
        ]
        unique_records: list[dict[str, str]] = []
        seen: set[str] = set()
        for _, records in source_records:
            for record in records:
                if record["digest"] not in seen:
                    seen.add(record["digest"])
                    unique_records.append(record)
        digest_lines = "\n".join(
            f"  - {record['digest']}" for record in unique_records
        )
        acceptance_lines = "\n".join(
            f"  - {record['text']}" for record in unique_records
        )
        witness_lines = "\n".join(
            "  - "
            + json.dumps(
                {
                    "acceptance_sha256": record["digest"],
                    "stage": "focused",
                    "witness": "git diff --check",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for record in unique_records
        )
        status = (
            "status: deferred\n"
            "completion_deferred_reason: coupled prerequisite must be checked\n"
            if predecessor
            else "status: in_progress\n"
        )
        predecessor_block = (
            f"predecessor_plans:\n  - {predecessor}\n" if predecessor else ""
        )
        content = (
            "# Coupled Integration\n\n"
            f"{status}"
            "primary_invariant: integrate every coupled source acceptance mapping\n"
            "replan_sources:\n"
            + "".join(f"  - {source}\n" for source in source_paths)
            + f"replan_contract: {contract_path}\n"
            "integration_gates:\n"
            "  - verify every coupled source through one shared integration successor\n"
            f"successor_plans:\n  - {path}\n"
            f"inherited_acceptance_digests:\n{digest_lines}\n"
            "integration_source_ids:\n"
            + "".join(f"  - {source_id}\n" for source_id, _ in source_records)
            + predecessor_block
            + "task_types:\n  - planning_docs\n"
            "review_class: C\n"
            "human_design_required: yes\n"
            "human_approval_status: approved\n"
            "write_scope:\n  - coupled/\n"
            "preservation_scope:\n  - none\n"
            "context_files:\n  - none\n"
            "required_specs:\n"
            "  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md\n"
            "  - docs/agent/SPEC_USER_COMMUNICATION.md\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "focused_validation:\n  - git diff --check\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n{acceptance_lines}\n"
            "validation_witness_schema: 1\n"
            f"validation_witness_map:\n{witness_lines}\n"
            "checked_summary_ja: 結合後続計画。\n\n"
            "## Tasks\n\n- [ ] integrate\n"
        )
        return content, mappings

    def prerequisite_content(self) -> str:
        acceptance = "Prepare the coupled reconstruction prerequisite."
        witness = json.dumps(
            {
                "acceptance_sha256": digest(acceptance),
                "stage": "focused",
                "witness": "git diff --check",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return (
            "# Coupled Prerequisite\n\n"
            "status: in_progress\n"
            "primary_invariant: prepare one separately authorized prerequisite\n"
            "task_types:\n  - planning_docs\n"
            "review_class: C\n"
            "human_design_required: yes\n"
            "human_approval_status: approved\n"
            "write_scope:\n  - prerequisite/\n"
            "preservation_scope:\n  - none\n"
            "context_files:\n  - none\n"
            "required_specs:\n"
            "  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md\n"
            "  - docs/agent/SPEC_USER_COMMUNICATION.md\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "focused_validation:\n  - git diff --check\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n  - {acceptance}\n"
            "validation_witness_schema: 1\n"
            f"validation_witness_map:\n  - {witness}\n"
            "checked_summary_ja: 結合前提計画。\n\n"
            "## Tasks\n\n- [ ] prepare\n"
        )

    def direct_source_content(
        self,
        *,
        title: str,
        acceptance: list[str],
        stopped: bool,
        predecessor: str | None,
        lineage_field: str | None = None,
    ) -> str:
        acceptance_lines = "\n".join(f"  - {value}" for value in acceptance)
        if stopped:
            status = "status: replan_required\n"
            reason_block = (
                "replan_reason_codes:\n  - multiple_independent_invariants\n"
            )
        elif predecessor:
            status = (
                "status: deferred\n"
                "completion_deferred_reason: the earlier direct source must be checked\n"
            )
            reason_block = ""
        else:
            status = "status: in_progress\n"
            reason_block = ""
        predecessor_block = (
            f"predecessor_plans:\n  - {predecessor}\n" if predecessor else ""
        )
        lineage_block = f"{lineage_field}\n" if lineage_field else ""
        return (
            f"# {title}\n\n"
            f"{status}"
            "primary_invariant: preserve one direct active source invariant\n"
            + predecessor_block
            + lineage_block
            + "task_types:\n  - planning_docs\n"
            "review_class: C\n"
            "human_design_required: yes\n"
            "human_approval_status: approved\n"
            "write_scope:\n  - direct/\n"
            "preservation_scope:\n  - none\n"
            "context_files:\n  - none\n"
            "required_specs:\n"
            "  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md\n"
            "  - docs/agent/SPEC_USER_COMMUNICATION.md\n"
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md\n"
            "focused_validation:\n  - git diff --check\n"
            "validation:\n  - git diff --check\n"
            f"acceptance:\n{acceptance_lines}\n"
            + reason_block
            + "checked_summary_ja: 直接能動元計画。\n\n## Tasks\n\n- [ ] implement\n"
        )

    def prepare_direct_active_sources(
        self,
        *,
        stop_primary: bool = True,
        link_dependent: bool = True,
        lineage_field: str | None = None,
    ) -> list[str]:
        primary = "docs/plan/active/010-direct-primary.md"
        dependent = "docs/plan/active/011-direct-dependent.md"
        (self.repo / primary).write_text(
            self.direct_source_content(
                title="Direct Primary",
                acceptance=["Keep the direct primary requirement."],
                stopped=stop_primary,
                predecessor=None,
                lineage_field=lineage_field,
            ),
            encoding="utf-8",
        )
        (self.repo / dependent).write_text(
            self.direct_source_content(
                title="Direct Dependent",
                acceptance=["Keep the direct dependent requirement."],
                stopped=False,
                predecessor=primary if link_dependent else None,
            ),
            encoding="utf-8",
        )
        active = self.repo / "docs/plan/plan.md"
        primary_status = "replan_required" if stop_primary else "in_progress"
        dependent_status = "deferred" if link_dependent else "in_progress"
        active.write_text(
            active.read_text(encoding="utf-8")
            + f"010\t{primary}\t{primary_status}\n"
            + f"011\t{dependent}\t{dependent_status}\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "add direct active sources")
        return [primary, dependent]

    def direct_active_spec(
        self,
        module,
        source_paths: list[str],
        *,
        kinds: list[str] | None = None,
        successor_id: str = "012",
        contract_name: str | None = None,
    ) -> dict[str, object]:
        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        sources: list[dict[str, object]] = []
        source_records: list[tuple[str, list[dict[str, str]]]] = []
        for index, path in enumerate(source_paths):
            content = (self.repo / path).read_text(encoding="utf-8")
            records = module.acceptance_records(content)
            source_records.append((Path(path).name[:3], records))
            stopped = module.derive_stopped_source_content(
                content,
                ["multiple_independent_invariants"],
            )
            sources.append(
                {
                    "path": path,
                    "source_kind": (
                        kinds[index] if kinds else "direct_active"
                    ),
                    "original_plan_digest": digest(content),
                    "stopped_plan_digest": digest(stopped),
                    "acceptance": records,
                    "reason_codes": ["multiple_independent_invariants"],
                    "archive_path": (
                        f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/"
                        f"{half}/{Path(path).name}"
                    ),
                }
            )
        first_id = Path(source_paths[0]).name[:3]
        contract_path = (
            "docs/plan/replanned/contracts/"
            + (contract_name or f"{first_id}-direct-active.json")
        )
        successor_path = f"docs/plan/active/{successor_id}-direct-integration.md"
        content, mappings = self.coupled_successor_content(
            path=successor_path,
            contract_path=contract_path,
            source_paths=source_paths,
            source_records=source_records,
            predecessor=None,
        )
        return {
            "schema_version": 3,
            "operation": "reconstruct",
            "source_head": git(self.repo, "rev-parse", "HEAD"),
            "sources": sources,
            "dirty_product_paths": [],
            "contract_path": contract_path,
            "successors": [
                {
                    "id": successor_id,
                    "path": successor_path,
                    "content": content,
                    "acceptance_mappings": mappings,
                    "integration_source_ids": [
                        source_id for source_id, _ in source_records
                    ],
                }
            ],
            "prerequisite_plans": [],
            "rebindings": [],
        }

    def prepare_coupled_spec(
        self,
        *,
        include_rebind: bool = False,
        include_prerequisite: bool = False,
        promotion_path: str | None = None,
        validation_rebind: bool = False,
        target_body_reference: bool = False,
    ) -> tuple[dict[str, object], object, str | None, str]:
        if include_rebind:
            self.add_sequential_successor()
        first = self.spec["successors"][0]  # type: ignore[index]
        integration = self.spec["integration"]  # type: ignore[assignment]
        integration["content"] = str(integration["content"]).replace(
            "status: in_progress\n",
            "status: deferred\n"
            "completion_deferred_reason: first successor must be checked\n",
            1,
        ).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {first['path']}\nprimary_invariant:",
            1,
        )
        target_path: str | None = None
        if include_rebind:
            target = self.spec["successors"][1]  # type: ignore[index]
            target_path = str(target["path"])
            target["content"] = str(target["content"]).replace(
                "status: in_progress\n",
                "status: deferred\n"
                "completion_deferred_reason: integration successor must be checked\n",
                1,
            ).replace(
                "primary_invariant:",
                f"predecessor_plans:\n  - {integration['path']}\nprimary_invariant:",
                1,
            )
            if validation_rebind:
                target["content"] = str(target["content"]).replace(
                    "git diff --check",
                    "python3 tests/test-copier-fixture.py",
                )
            if target_body_reference:
                target["content"] = (
                    str(target["content"])
                    + f"\nOperational dependency: {integration['path']}\n"
                )
            if promotion_path:
                product = self.repo / promotion_path
                product.parent.mkdir(parents=True)
                product.write_text("generated: true\n", encoding="utf-8")
                self.spec["dirty_product_paths"] = [promotion_path]
                target["content"] = str(target["content"]).replace(
                    "preservation_scope:\n  - none",
                    f"preservation_scope:\n  - {promotion_path}",
                ).replace(
                    "context_files:\n  - none",
                    "context_files:\n  - docs/agent/spec-index.yaml",
                )
        self.write_spec()
        initial = self.run_command()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        module = self.load_restructure_module("coupled_fixture_module")
        first_path = self.repo / str(first["path"])
        first_path.write_text(
            module.derive_stopped_source_content(
                first_path.read_text(encoding="utf-8"),
                ["multiple_independent_invariants"],
            ),
            encoding="utf-8",
        )
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"{first['id']}\t{first['path']}\tin_progress",
                f"{first['id']}\t{first['path']}\treplan_required",
            ),
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "prepare coupled sources")
        module = self.load_restructure_module("coupled_spec_module")
        source_paths = [str(first["path"]), str(integration["path"])]
        source_records: list[tuple[str, list[dict[str, str]]]] = []
        sources: list[dict[str, object]] = []
        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        for path in source_paths:
            content = (self.repo / path).read_text(encoding="utf-8")
            records = module.acceptance_records(content)
            source_id = Path(path).name[:3]
            source_records.append((source_id, records))
            stopped = module.derive_stopped_source_content(
                content,
                ["multiple_independent_invariants"],
            )
            sources.append(
                {
                    "path": path,
                    "source_kind": "contract_successor",
                    "original_plan_digest": digest(content),
                    "stopped_plan_digest": digest(stopped),
                    "acceptance": records,
                    "reason_codes": ["multiple_independent_invariants"],
                    "archive_path": (
                        f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/"
                        f"{half}/{Path(path).name}"
                    ),
                }
            )
        contract_path = "docs/plan/replanned/contracts/002-data-coupled.json"
        prerequisite_path = (
            "docs/plan/active/005-coupled-prerequisite.md"
            if include_prerequisite
            else None
        )
        successor_path = (
            "docs/plan/active/006-coupled-integration.md"
            if include_prerequisite
            else "docs/plan/active/005-coupled-integration.md"
        )
        successor_content, mappings = self.coupled_successor_content(
            path=successor_path,
            contract_path=contract_path,
            source_paths=source_paths,
            source_records=source_records,
            predecessor=prerequisite_path,
        )
        if validation_rebind:
            successor_content = successor_content.replace(
                "write_scope:\n  - coupled/\n",
                "write_scope:\n"
                "  - coupled/\n"
                "  - tests/test-copier-fixture-validator.py\n",
                1,
            )
        rebindings: list[dict[str, object]] = []
        if target_path:
            original = (self.repo / target_path).read_text(encoding="utf-8")
            updated = original.replace(
                str(integration["path"]),
                successor_path,
                1,
            )
            replacements: list[dict[str, object]] = [
                {
                    "scope": "manifest",
                    "field": "predecessor_plans",
                    "old": str(integration["path"]),
                    "new": successor_path,
                    "count": 1,
                }
            ]
            if validation_rebind:
                old_validation = "tests/test-copier-fixture.py"
                new_validation = "tests/test-copier-fixture-validator.py"
                updated = updated.replace(old_validation, new_validation)
                replacements.extend(
                    {
                        "scope": "manifest",
                        "field": field,
                        "old": old_validation,
                        "new": new_validation,
                        "count": 1,
                    }
                    for field in (
                        "focused_validation",
                        "validation",
                        "validation_witness_map",
                    )
                )
            state = module.verify_repository_contracts()
            owner = state["live_successors"][target_path]["contract_path"]
            rebindings.append(
                {
                    "kind": "rebind",
                    "plan_path": target_path,
                    "owning_contract_path": owner,
                    "original_content_digest": digest(original),
                    "prior_effective_projection_digest": module.projection_digest(
                        state["effective_projections"][target_path]
                    ),
                    "updated_content_digest": digest(updated),
                    "replacements": replacements,
                    "promoted_preservation_path": None,
                }
            )
        coupled = {
            "schema_version": 3,
            "operation": "reconstruct",
            "source_head": git(self.repo, "rev-parse", "HEAD"),
            "sources": sources,
            "dirty_product_paths": [],
            "contract_path": contract_path,
            "successors": [
                {
                    "id": Path(successor_path).name[:3],
                    "path": successor_path,
                    "content": successor_content,
                    "acceptance_mappings": mappings,
                    "integration_source_ids": [
                        source_id for source_id, _ in source_records
                    ],
                }
            ],
            "prerequisite_plans": (
                [
                    {
                        "id": Path(prerequisite_path).name[:3],
                        "path": prerequisite_path,
                        "content": self.prerequisite_content(),
                        "authorization": "parent_owned_prerequisite",
                    }
                ]
                if prerequisite_path
                else []
            ),
            "rebindings": rebindings,
        }
        return coupled, module, target_path, successor_path

    def add_aggregate_coverage_successor(
        self,
        coupled: dict[str, object],
    ) -> tuple[str, str]:
        sources = coupled["sources"]
        successors = coupled["successors"]
        assert isinstance(sources, list)
        assert isinstance(successors, list)
        integration = successors[0]
        assert isinstance(integration, dict)
        source = next(
            source
            for source in sources
            if isinstance(source, dict)
            and isinstance(source.get("acceptance"), list)
            and len(source["acceptance"]) > 1
        )
        source_id = Path(str(source["path"])).name[:3]
        acceptance = source["acceptance"]
        assert isinstance(acceptance, list)
        missing_record = acceptance[0]
        assert isinstance(missing_record, dict)
        auxiliary_path = "docs/plan/active/007-aggregate-coverage.md"
        integration_path = str(integration["path"])
        source_paths = [str(source["path"]) for source in sources]
        auxiliary_content, auxiliary_mappings = self.coupled_successor_content(
            path=auxiliary_path,
            contract_path=str(coupled["contract_path"]),
            source_paths=source_paths,
            source_records=[(source_id, [missing_record])],
            predecessor=None,
        )
        old_integration_paths = f"successor_plans:\n  - {integration_path}\n"
        new_paths = (
            "successor_plans:\n"
            f"  - {integration_path}\n"
            f"  - {auxiliary_path}\n"
        )
        integration["content"] = str(integration["content"]).replace(
            old_integration_paths,
            new_paths,
            1,
        )
        auxiliary_content = auxiliary_content.replace(
            f"successor_plans:\n  - {auxiliary_path}\n",
            new_paths,
            1,
        ).replace(
            f"integration_source_ids:\n  - {source_id}\n",
            "",
            1,
        )
        successors.append(
            {
                "id": "007",
                "path": auxiliary_path,
                "content": auxiliary_content,
                "acceptance_mappings": auxiliary_mappings,
                "integration_source_ids": [],
            }
        )
        return source_id, str(missing_record["digest"])

    def run_spec_data(
        self,
        value: dict[str, object],
        name: str,
    ) -> subprocess.CompletedProcess[str]:
        path = self.base / name
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return subprocess.run(
            [sys.executable, "scripts/restructure-plan.py", str(path)],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_success_preserves_requirements_and_switches_indexes(self) -> None:
        result = self.run_command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.repo / self.source_path).exists())
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], 2)
        for successor in contract["successors"]:
            manifest = successor["content"]
            self.assertEqual(successor["validation_witness_schema"], 1)
            self.assertEqual(
                successor["authoritative_validation"],
                ["git diff --check"],
            )
            self.assertEqual(
                successor["authoritative_validation_digest"],
                digest('["git diff --check"]'),
            )
            self.assertIn("validation_witness_map:", manifest)
        self.assertEqual(
            {key: contract["source"][key] for key in self.spec["source"]},
            self.spec["source"],
        )
        self.assertEqual(digest(contract["source"]["content"]), contract["source"]["plan_digest"])
        archive = self.repo / str(self.spec["archive_path"])
        archive_text = archive.read_text(encoding="utf-8")
        self.assertIn("status: replanned", archive_text)
        self.assertIn("# Preserve this source annotation.", archive_text)
        self.assertIn("001\t", (self.repo / "docs/plan/replanned.md").read_text(encoding="utf-8"))
        active = (self.repo / "docs/plan/plan.md").read_text(encoding="utf-8")
        self.assertNotIn("001\t", active)
        self.assertIn("002\tdocs/plan/active/002-data.md\tin_progress", active)
        self.assertIn("003\tdocs/plan/active/003-integration.md\tin_progress", active)
        verified = self.run_verify()
        self.assertEqual(
            verified.returncode,
            0,
            verified.stderr,
        )

        successor_path = self.repo / "docs/plan/active/002-data.md"
        clean_successor = successor_path.read_text(encoding="utf-8")
        active_index = self.repo / "docs/plan/plan.md"
        clean_active_index = active_index.read_text(encoding="utf-8")
        successor_path.write_text(
            clean_successor.replace("status: in_progress", "status: garbage", 1),
            encoding="utf-8",
        )
        active_index.write_text(
            clean_active_index.replace(
                "002\tdocs/plan/active/002-data.md\tin_progress",
                "002\tdocs/plan/active/002-data.md\tgarbage",
                1,
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        successor_path.write_text(clean_successor, encoding="utf-8")
        active_index.write_text(clean_active_index, encoding="utf-8")

    def test_predecessor_chain_requires_deferred_then_exact_checked_refresh(self) -> None:
        first = self.spec["successors"][0]  # type: ignore[index]
        integration = self.spec["integration"]  # type: ignore[assignment]
        integration["content"] = str(integration["content"]).replace(
            "status: in_progress\n",
            "status: deferred\n"
            "completion_deferred_reason: predecessor must be checked\n",
            1,
        ).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {first['path']}\nprimary_invariant:",
            1,
        )
        self.write_spec()
        transitioned = self.run_command()
        self.assertEqual(transitioned.returncode, 0, transitioned.stderr)
        self.assertEqual(self.run_verify().returncode, 0)

        integration_path = self.repo / str(integration["path"])
        active_index = self.repo / "docs/plan/plan.md"
        integration_path.write_text(
            integration_path.read_text(encoding="utf-8").replace(
                "status: deferred", "status: in_progress", 1
            ),
            encoding="utf-8",
        )
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                f"{integration['id']}\t{integration['path']}\tdeferred",
                f"{integration['id']}\t{integration['path']}\tin_progress",
            ),
            encoding="utf-8",
        )
        premature = self.run_verify()
        self.assertNotEqual(premature.returncode, 0)
        self.assertIn("must remain deferred", premature.stderr)

        integration_path.write_text(
            integration_path.read_text(encoding="utf-8").replace(
                "status: in_progress", "status: deferred", 1
            ),
            encoding="utf-8",
        )
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                f"{integration['id']}\t{integration['path']}\tin_progress",
                f"{integration['id']}\t{integration['path']}\tdeferred",
            ),
            encoding="utf-8",
        )
        first_path = self.repo / str(first["path"])
        checked_relative = "docs/plan/checked/2026/08/16-31/002-data.md"
        checked = self.repo / checked_relative
        checked.parent.mkdir(parents=True)
        checked.write_text(
            first_path.read_text(encoding="utf-8").replace(
                "status: in_progress", "status: checked", 1
            ),
            encoding="utf-8",
        )
        first_path.unlink()
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                f"{first['id']}\t{first['path']}\tin_progress\n", ""
            ),
            encoding="utf-8",
        )
        (self.repo / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n"
            f"{first['id']}\t{checked_relative}\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "check predecessor")
        module = self.load_restructure_module("predecessor_activation_module")
        activation = self.activation_spec(
            module=module,
            target_path=str(integration["path"]),
            successor_path=str(first["path"]),
            checked_path=checked_relative,
            promoted_path=None,
            deferred_reason="predecessor must be checked",
        )
        activated = self.run_spec_data(
            activation,
            "predecessor-activation.json",
        )
        self.assertEqual(activated.returncode, 0, activated.stderr)
        self.assertEqual(self.run_verify().returncode, 0)

    def prepare_checked_predecessor(self, first, integration) -> str:
        self.write_spec()
        transitioned = self.run_command()
        self.assertEqual(transitioned.returncode, 0, transitioned.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        first_path = self.repo / str(first["path"])
        active_index = self.repo / "docs/plan/plan.md"
        checked_relative = "docs/plan/checked/2026/08/16-31/002-data.md"
        checked = self.repo / checked_relative
        checked.parent.mkdir(parents=True)
        checked.write_text(
            first_path.read_text(encoding="utf-8").replace(
                "status: in_progress", "status: checked", 1
            ),
            encoding="utf-8",
        )
        first_path.unlink()
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                f"{first['id']}\t{first['path']}\tin_progress\n", ""
            ),
            encoding="utf-8",
        )
        (self.repo / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n"
            f"{first['id']}\t{checked_relative}\n",
            encoding="utf-8",
        )
        self.rebind_referrer_context(str(integration["path"]), str(first["path"]), checked_relative)
        self.assertEqual(self.run_verify().returncode, 0)
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "check predecessor")
        return checked_relative

    def rebind_referrer_context(
        self,
        referrer_path: str,
        active_path: str,
        checked_path: str,
    ) -> None:
        """Reproduce the referrer rebinding that finalization performs on archival."""
        referrer = self.repo / referrer_path
        original = referrer.read_text(encoding="utf-8")
        rebound = original.replace(
            f"context_files:\n  - {active_path}\n",
            f"context_files:\n  - {checked_path}\n",
            1,
        )
        if rebound != original:
            referrer.write_text(rebound, encoding="utf-8")

    def defer_integration_behind(self, first, integration, *, context: bool) -> None:
        content = str(integration["content"]).replace(
            "status: in_progress\n",
            "status: deferred\n"
            "completion_deferred_reason: predecessor must be checked\n",
            1,
        ).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {first['path']}\nprimary_invariant:",
            1,
        )
        if context:
            content = content.replace(
                "context_files:\n  - none\n",
                f"context_files:\n  - {first['path']}\n",
                1,
            )
        integration["content"] = content

    def test_finalization_rebinds_context_before_activation_resolves_predecessors(
        self,
    ) -> None:
        first = self.spec["successors"][0]  # type: ignore[index]
        integration = self.spec["integration"]  # type: ignore[assignment]
        self.defer_integration_behind(first, integration, context=True)
        checked_relative = self.prepare_checked_predecessor(first, integration)
        deferred_text = (self.repo / str(integration["path"])).read_text(
            encoding="utf-8"
        )
        self.assertIn(f"context_files:\n  - {checked_relative}\n", deferred_text)
        self.assertIn(f"predecessor_plans:\n  - {first['path']}\n", deferred_text)
        module = self.load_restructure_module("context_activation_module")
        activation = self.activation_spec(
            module=module,
            target_path=str(integration["path"]),
            successor_path=str(first["path"]),
            checked_path=checked_relative,
            promoted_path=None,
            deferred_reason="predecessor must be checked",
        )
        activated = self.run_spec_data(activation, "context-activation.json")
        self.assertEqual(activated.returncode, 0, activated.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        activated_text = (self.repo / str(integration["path"])).read_text(
            encoding="utf-8"
        )
        self.assertIn(f"context_files:\n  - {checked_relative}\n", activated_text)
        self.assertIn(
            f"predecessor_plans:\n  - {checked_relative}\n", activated_text
        )

    def test_activation_rejects_unrelated_context_changes(self) -> None:
        first = self.spec["successors"][0]  # type: ignore[index]
        integration = self.spec["integration"]  # type: ignore[assignment]
        self.defer_integration_behind(first, integration, context=False)
        checked_relative = self.prepare_checked_predecessor(first, integration)
        target = self.repo / str(integration["path"])
        original = target.read_text(encoding="utf-8")
        module = self.load_restructure_module("unrelated_context_module")
        activation = self.activation_spec(
            module=module,
            target_path=str(integration["path"]),
            successor_path=str(first["path"]),
            checked_path=checked_relative,
            promoted_path=None,
            deferred_reason="predecessor must be checked",
        )
        rebinding = activation["rebindings"][0]  # type: ignore[index]
        rebinding["replacements"].append(  # type: ignore[index]
            {
                "scope": "manifest",
                "field": "context_files",
                "old": "context_files:\n  - none\n",
                "new": "context_files:\n  - docs/agent/spec-index.yaml\n",
                "count": 1,
            }
        )
        updated = (
            original.replace("status: deferred\n", "status: in_progress\n", 1)
            .replace(
                "completion_deferred_reason: predecessor must be checked\n", "", 1
            )
            .replace(str(first["path"]), checked_relative, 1)
            .replace(
                "context_files:\n  - none\n",
                "context_files:\n  - docs/agent/spec-index.yaml\n",
                1,
            )
        )
        rebinding["updated_content_digest"] = digest(updated)  # type: ignore[index]
        rejected = self.run_spec_data(activation, "unrelated-context.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "is not an exact active-to-checked transition", rejected.stderr
        )

    def test_activation_promotion_rejects_context_drift(self) -> None:
        first = self.spec["successors"][0]  # type: ignore[index]
        integration = self.spec["integration"]  # type: ignore[assignment]
        self.defer_integration_behind(first, integration, context=True)
        checked_relative = self.prepare_checked_predecessor(first, integration)
        module = self.load_restructure_module("promotion_guard_module")
        rebound = (self.repo / str(integration["path"])).read_text(encoding="utf-8")
        self.assertIn(f"context_files:\n  - {checked_relative}\n", rebound)
        before = module.parse_manifest(rebound)
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            module.validate_activation_promotion(
                before, module.parse_manifest(rebound), None, "probe"
            )
            drifted = {
                "stale active reference": rebound.replace(
                    f"context_files:\n  - {checked_relative}\n",
                    f"context_files:\n  - {first['path']}\n",
                    1,
                ),
                "added context entry": rebound.replace(
                    f"context_files:\n  - {checked_relative}\n",
                    f"context_files:\n  - {checked_relative}\n"
                    "  - docs/agent/spec-index.yaml\n",
                    1,
                ),
                "removed context entry": rebound.replace(
                    f"context_files:\n  - {checked_relative}\n",
                    "context_files:\n  - none\n",
                    1,
                ),
                "changed preservation scope": rebound.replace(
                    "preservation_scope:\n  - none\n",
                    "preservation_scope:\n  - src/keep.py\n",
                    1,
                ),
            }
            for case, text in drifted.items():
                with self.subTest(case=case):
                    self.assertNotEqual(text, rebound)
                    with self.assertRaises(module.RestructureError) as raised:
                        module.validate_activation_promotion(
                            before, module.parse_manifest(text), None, "probe"
                        )
                    self.assertIn(
                        "activation changes preservation or context without promotion",
                        str(raised.exception),
                    )
        finally:
            os.chdir(old_cwd)

    def test_lifecycle_projection_removes_only_parsed_lifecycle_bytes(self) -> None:
        module = self.load_restructure_module("lifecycle_projection_module")
        fields = {"status", "completion_deferred_reason", "replan_reason_codes"}
        text = (
            "# Plan\n\n"
            "status: replan_required\n"
            "# keep this annotation\n"
            "\n"
            "primary_invariant: keep every byte\n"
            "replan_reason_codes:\n"
            "  - spec_drift\n"
            "# keep this trailing annotation\n"
            "  - scope_drift\n"
            "context_files:\n"
            "  - none\n"
            "unknown instruction without a colon\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n"
            "## Tasks\n\n- [ ] work\n"
        )
        self.assertEqual(
            module.project_lifecycle_fields(text, fields),
            "# Plan\n\n"
            "# keep this annotation\n"
            "\n"
            "primary_invariant: keep every byte\n"
            "# keep this trailing annotation\n"
            "context_files:\n"
            "  - none\n"
            "unknown instruction without a colon\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n"
            "## Tasks\n\n- [ ] work\n",
        )
        swallowed = module.remove_manifest_fields(text, fields)
        self.assertNotIn("# keep this annotation", swallowed)
        self.assertNotIn("# keep this trailing annotation", swallowed)

    def test_lifecycle_evolution_rejects_unparsed_byte_loss(self) -> None:
        module = self.load_restructure_module("lifecycle_evolution_module")
        baseline = (
            "# Plan\n\nstatus: in_progress\n"
            "# keep this annotation\n"
            "primary_invariant: keep every byte\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n## Tasks\n\n- [ ] work\n"
        )
        module.validate_lifecycle_evolution(
            baseline,
            baseline.replace("status: in_progress", "status: ready_to_archive", 1),
            "probe",
        )
        with self.assertRaises(module.RestructureError) as raised:
            module.validate_lifecycle_evolution(
                baseline,
                baseline.replace("status: in_progress", "status: ready_to_archive", 1)
                .replace("# keep this annotation\n", "", 1),
                "probe",
            )
        self.assertIn("changes non-validation-note line count", str(raised.exception))

    def test_lifecycle_evolution_rejects_reattached_list_items(self) -> None:
        module = self.load_restructure_module("lifecycle_reattach_module")
        baseline = (
            "# Plan\n\nstatus: deferred\n"
            "write_scope:\n"
            "  - src/\n"
            "completion_deferred_reason: waiting\n"
            "  - tests/\n"
            "primary_invariant: keep every parsed field\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n## Tasks\n\n- [ ] work\n"
        )
        live = (
            "# Plan\n\nstatus: replan_required\n"
            "write_scope:\n"
            "  - src/\n"
            "  - tests/\n"
            "primary_invariant: keep every parsed field\n"
            "replan_reason_codes:\n  - spec_drift\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n## Tasks\n\n- [ ] work\n"
        )
        self.assertEqual(
            module.parse_manifest(baseline)["write_scope"], ["src/"]
        )
        self.assertEqual(
            module.parse_manifest(live)["write_scope"], ["src/", "tests/"]
        )
        fields = {"status", "completion_deferred_reason", "replan_reason_codes"}
        self.assertEqual(
            module.project_lifecycle_fields(baseline, fields),
            module.project_lifecycle_fields(live, fields),
        )
        with self.assertRaises(module.RestructureError) as raised:
            module.validate_lifecycle_evolution(baseline, live, "probe")
        self.assertIn("changes protected manifest field: write_scope", str(raised.exception))

    def test_stopping_preserves_unparsed_bytes(self) -> None:
        module = self.load_restructure_module("stopping_projection_module")
        text = (
            "# Plan\n\nstatus: in_progress\n"
            "# keep the status annotation\n"
            "primary_invariant: keep every byte\n"
            "completion_deferred_reason: waiting\n"
            "# keep the deferred annotation\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n## Tasks\n\n- [ ] work\n"
        )
        stopped = module.derive_stopped_source_content(text, ["spec_drift"])
        self.assertIn("# keep the status annotation\n", stopped)
        self.assertIn("# keep the deferred annotation\n", stopped)
        self.assertNotIn("completion_deferred_reason", stopped)
        self.assertIn("status: replan_required\n", stopped)
        self.assertIn("replan_reason_codes:\n  - spec_drift\n", stopped)
        self.assertEqual(
            module.derive_stopped_source_content(stopped, ["spec_drift"]), stopped
        )

    def test_canonical_stopped_state_rejects_noncanonical_metadata(self) -> None:
        module = self.load_restructure_module("canonical_stopped_module")
        base = (
            "# Plan\n\nstatus: replan_required\n"
            "replan_reason_codes:\n  - spec_drift\n"
            "checked_summary_ja: \u8a18\u9332\u3002\n\n## Tasks\n\n- [ ] work\n"
        )
        module.validate_canonical_stopped_manifest(
            module.parse_manifest(base),
            "probe",
            expected_reason_codes=["spec_drift"],
        )
        bounded = "must be a non-empty unique bounded list"
        cases = {
            "not stopped": (
                base.replace("status: replan_required", "status: in_progress", 1),
                None,
                "must already be canonically stopped",
            ),
            "stale deferred reason": (
                base.replace(
                    "status: replan_required\n",
                    "status: replan_required\ncompletion_deferred_reason: waiting\n",
                    1,
                ),
                None,
                "carries stale completion_deferred_reason",
            ),
            "missing reason codes": (
                base.replace("replan_reason_codes:\n  - spec_drift\n", "", 1),
                None,
                bounded,
            ),
            "empty reason codes": (base.replace("  - spec_drift\n", "", 1), None, bounded),
            "duplicate reason codes": (
                base.replace("  - spec_drift\n", "  - spec_drift\n  - spec_drift\n", 1),
                None,
                bounded,
            ),
            "unknown reason code": (
                base.replace("  - spec_drift\n", "  - not_a_reason\n", 1),
                None,
                bounded,
            ),
            "non-string contract reason code": (base, [1], bounded),
            "contract reason code mismatch": (
                base,
                ["scope_drift"],
                "do not match the canonical source manifest",
            ),
        }
        for case, (text, expected, message) in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(module.RestructureError) as raised:
                    module.validate_canonical_stopped_manifest(
                        module.parse_manifest(text),
                        "probe",
                        expected_reason_codes=expected,
                    )
                self.assertIn(message, str(raised.exception))

    def test_schema_one_preflight_rejects_stale_deferred_reason(self) -> None:
        source = self.repo / self.source_path
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "status: replan_required\n",
                "status: replan_required\ncompletion_deferred_reason: waiting\n",
                1,
            ),
            encoding="utf-8",
        )
        self.spec["source"]["plan_digest"] = digest(  # type: ignore[index]
            source.read_text(encoding="utf-8")
        )
        self.write_spec()
        result = self.run_command()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("carries stale completion_deferred_reason", result.stderr)
        self.assert_source_unchanged()

    def test_durable_contract_reason_codes_bind_to_the_source_manifest(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        self.assertEqual(self.run_verify().returncode, 0)
        contract = self.repo / str(self.spec["contract_path"])
        original = json.loads(contract.read_text(encoding="utf-8"))
        cases = {
            "mismatched reason code": ["scope_drift"],
            "empty reason codes": [],
            "duplicate reason codes": [
                "multiple_independent_invariants",
                "multiple_independent_invariants",
            ],
            "unknown reason code": ["not_a_reason"],
            "non-string reason code": [1],
            "non-list reason codes": "multiple_independent_invariants",
        }
        for case, reasons in cases.items():
            with self.subTest(case=case):
                mutated = dict(original)
                mutated["reason_codes"] = reasons
                contract.write_text(
                    json.dumps(mutated, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                failed = self.run_verify()
                self.assertNotEqual(failed.returncode, 0)
                self.assertNotIn("Traceback", failed.stderr)
        contract.write_text(
            json.dumps(original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_durable_contract_rejects_stale_deferred_reason_in_the_source(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        self.assertEqual(self.run_verify().returncode, 0)
        contract = self.repo / str(self.spec["contract_path"])
        original = json.loads(contract.read_text(encoding="utf-8"))
        mutated = json.loads(json.dumps(original))
        mutated["source"]["content"] = str(mutated["source"]["content"]).replace(
            "status: replan_required\n",
            "status: replan_required\ncompletion_deferred_reason: waiting\n",
            1,
        )
        mutated["source"]["plan_digest"] = digest(mutated["source"]["content"])
        contract.write_text(
            json.dumps(mutated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        failed = self.run_verify()
        self.assertNotEqual(failed.returncode, 0)
        self.assertNotIn("Traceback", failed.stderr)
        self.assertIn("carries stale completion_deferred_reason", failed.stderr)
        contract.write_text(
            json.dumps(original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_durable_schema_three_reason_codes_bind_to_the_source_manifest(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        result = self.run_spec_data(coupled, "coupled-reason-codes.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        contract = self.repo / str(coupled["contract_path"])
        original = json.loads(contract.read_text(encoding="utf-8"))
        self.assertGreater(len(original["sources"]), 1)
        for case, reasons in {
            "mismatched reason code": ["scope_drift"],
            "empty reason codes": [],
            "unknown reason code": ["not_a_reason"],
            "non-string reason code": [1],
            "non-list reason codes": "scope_drift",
        }.items():
            with self.subTest(case=case):
                mutated = json.loads(json.dumps(original))
                mutated["sources"][0]["reason_codes"] = reasons
                contract.write_text(
                    json.dumps(mutated, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                failed = self.run_verify()
                self.assertNotEqual(failed.returncode, 0)
                self.assertNotIn("Traceback", failed.stderr)
        bounded = "contract reason_codes must be a non-empty unique bounded list"
        dependent_id = original["sources"][1]["id"]
        for case, (reasons, message) in {
            "dependent empty reason codes": ([], bounded),
            "dependent unknown reason code": (["not_a_reason"], bounded),
            "dependent non-string reason code": ([1], bounded),
            "dependent non-list reason codes": ("scope_drift", bounded),
            "dependent duplicate reason codes": (
                ["scope_drift", "scope_drift"],
                bounded,
            ),
            "dependent mismatched reason code": (
                ["scope_drift"],
                "reason codes do not match the canonical source manifest",
            ),
        }.items():
            with self.subTest(case=case):
                mutated = json.loads(json.dumps(original))
                mutated["sources"][1]["reason_codes"] = reasons
                contract.write_text(
                    json.dumps(mutated, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                failed = self.run_verify()
                self.assertNotEqual(failed.returncode, 0)
                self.assertNotIn("Traceback", failed.stderr)
                self.assertIn(
                    f"replanned schema-3 stopped source {dependent_id} {message}",
                    failed.stderr,
                )
        contract.write_text(
            json.dumps(original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_predecessor_cycles_and_duplicate_edges_are_rejected_before_writes(self) -> None:
        first = self.spec["successors"][0]  # type: ignore[index]
        integration = self.spec["integration"]  # type: ignore[assignment]
        for entry, predecessor in ((first, integration["path"]), (integration, first["path"])):
            entry["content"] = str(entry["content"]).replace(
                "status: in_progress\n",
                "status: deferred\ncompletion_deferred_reason: predecessor is active\n",
                1,
            ).replace(
                "primary_invariant:",
                f"predecessor_plans:\n  - {predecessor}\nprimary_invariant:",
                1,
            )
        self.write_spec()
        cycle = self.run_command()
        self.assertNotEqual(cycle.returncode, 0)
        self.assertIn("cycle", cycle.stderr)
        self.assert_source_unchanged()

        self.spec = self.make_spec()
        integration = self.spec["integration"]  # type: ignore[assignment]
        predecessor = self.spec["successors"][0]["path"]  # type: ignore[index]
        integration["content"] = str(integration["content"]).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {predecessor}\n  - {predecessor}\nprimary_invariant:",
            1,
        )
        self.write_spec()
        duplicate = self.run_command()
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("must not contain duplicates", duplicate.stderr)
        self.assert_source_unchanged()

    def test_stale_or_cross_id_checked_predecessor_is_rejected(self) -> None:
        integration = self.spec["integration"]  # type: ignore[assignment]
        stale = "docs/plan/checked/2026/08/01-15/009-predecessor.md"
        current = "docs/plan/checked/2026/08/16-31/009-predecessor.md"
        current_path = self.repo / current
        current_path.parent.mkdir(parents=True)
        current_path.write_text("status: checked\n", encoding="utf-8")
        (self.repo / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n"
            f"009\t{current}\n",
            encoding="utf-8",
        )
        integration["content"] = str(integration["content"]).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {stale}\nprimary_invariant:",
            1,
        )
        self.write_spec()
        stale_result = self.run_command()
        self.assertNotEqual(stale_result.returncode, 0)
        self.assertIn("missing or stale", stale_result.stderr)
        self.assert_source_unchanged()

        (self.repo / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n"
            f"999\t{stale}\n",
            encoding="utf-8",
        )
        stale_path = self.repo / stale
        stale_path.parent.mkdir(parents=True, exist_ok=True)
        stale_path.write_text("status: checked\n", encoding="utf-8")
        self.write_spec()
        cross_id = self.run_command()
        self.assertNotEqual(cross_id.returncode, 0)
        self.assertIn("identity mismatch", cross_id.stderr)
        self.assert_source_unchanged()

    def test_durable_contract_tampering_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["successors"][0]["content"] = contract["successors"][0]["content"].replace(
            "Preserve user data.", "Discard user data."
        )
        contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_committed_replanned_history_is_immutable(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "publish replanned history")
        contract = self.repo / str(self.spec["contract_path"])
        archive = self.repo / str(self.spec["archive_path"])
        for path in (contract, archive):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                rejected = self.run_verify()
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn(
                    "historical contract or archive differs from committed bytes",
                    rejected.stderr,
                )
                path.write_bytes(original)

        replanned = self.repo / "docs/plan/replanned.md"
        original_index = replanned.read_text(encoding="utf-8")
        for tampered in (
            original_index.replace(
                "# Replanned Plan Index",
                "# Replanned Plan Ledger",
                1,
            ),
            original_index + "\nUnbound historical note.\n",
        ):
            with self.subTest(index_bytes=digest(tampered)):
                replanned.write_text(tampered, encoding="utf-8")
                rejected = self.run_verify()
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn(
                    "replanned plan index bytes are not canonical",
                    rejected.stderr,
                )
        replanned.write_text(
            "# Replanned Plan Index\n\nid\tpath\tcontract\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "replanned plan index rewrites committed history",
            rejected.stderr,
        )
        replanned.write_text(original_index, encoding="utf-8")
        self.assertEqual(self.run_verify().returncode, 0)

    def test_validation_projection_tampering_and_live_reordering_are_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["successors"][0]["authoritative_validation_digest"] = "sha256:" + "0" * 64
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        mismatch = self.run_verify()
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("validation projection mismatch", mismatch.stderr)

        contract = json.loads(
            (self.repo / str(self.spec["contract_path"])).read_text(encoding="utf-8")
        )
        contract["successors"][0]["authoritative_validation_digest"] = digest(
            '["git diff --check"]'
        )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        successor_path = self.repo / str(self.spec["successors"][0]["path"])  # type: ignore[index]
        successor_path.write_text(
            successor_path.read_text(encoding="utf-8").replace(
                "validation:\n  - git diff --check",
                "validation:\n  - python3 tests/test-plan-restructure.py\n  - git diff --check",
            ),
            encoding="utf-8",
        )
        reordered = self.run_verify()
        self.assertNotEqual(reordered.returncode, 0)
        self.assertIn("validation projection mismatch", reordered.stderr)

    def test_missing_or_invalid_integration_witness_rejects_before_writes(self) -> None:
        integration = self.spec["integration"]  # type: ignore[assignment]
        integration["content"] = str(integration["content"]).replace(
            "validation_witness_schema: 1\n"
            "validation_witness_map:\n",
            "validation_witness_map:\n",
            1,
        )
        self.write_spec()
        missing = self.run_command()
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("requires validation_witness_schema: 1", missing.stderr)
        self.assert_source_unchanged()

        self.spec = self.make_spec()
        integration = self.spec["integration"]  # type: ignore[assignment]
        integration["content"] = str(integration["content"]).replace(
            '"witness":"git diff --check"',
            '"witness":"python3 tests/test-plan-restructure.py"',
            1,
        )
        self.write_spec()
        invalid = self.run_command()
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("focused witness is not declared", invalid.stderr)
        self.assert_source_unchanged()

    def test_rehashed_source_status_tampering_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        source = contract["source"]
        source["content"] = source["content"].replace(
            "status: replan_required", "status: checked", 1
        )
        source["plan_digest"] = digest(source["content"])
        contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_durable_contract_rehashed_added_acceptance_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        successor = contract["successors"][0]
        successor["content"] = successor["content"].replace(
            "  - Preserve user data.\nvalidation_witness_schema:",
            "  - Preserve user data.\n  - Clarification: discard user data.\nvalidation_witness_schema:",
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
                "  - Preserve user data.\nvalidation_witness_schema:",
                "  - Preserve user data.\n  - Clarification: discard user data.\nvalidation_witness_schema:",
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
        active_index = self.repo / "docs/plan/plan.md"
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                "002\tdocs/plan/active/002-data.md\tin_progress\n", ""
            ),
            encoding="utf-8",
        )
        (self.repo / "docs/plan/checked.md").write_text(
            "# Checked Plan Index\n\nid\tpath\n002\t" + checked_relative + "\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)
        clean_checked = checked.read_text(encoding="utf-8")
        checked.write_text(
            clean_checked.replace("status: checked", "status: in_progress", 1),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        checked.write_text(clean_checked, encoding="utf-8")
        checked_index = self.repo / "docs/plan/checked.md"
        clean_checked_index = checked_index.read_text(encoding="utf-8")
        checked_index.write_text(
            clean_checked_index + "999\t" + checked_relative + "\n",
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        checked_index.write_text(clean_checked_index, encoding="utf-8")
        renamed_relative = "docs/plan/checked/2026/08/01-15/002-other.md"
        renamed = self.repo / renamed_relative
        checked.rename(renamed)
        checked_index.write_text(
            clean_checked_index.replace(checked_relative, renamed_relative),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        renamed.rename(checked)
        checked_index.write_text(clean_checked_index, encoding="utf-8")
        checked.write_text(
            checked.read_text(encoding="utf-8").replace(
                "  - Preserve user data.\nvalidation_witness_schema:",
                "  - Preserve user data.\n  - Clarification: discard user data.\nvalidation_witness_schema:",
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def move_successor_to_backlog(
        self,
        active_relative: str,
        plan_id: str,
        *,
        status: str = "backlog",
        from_status: str = "in_progress",
        location: str = "docs/plan/backlog",
        extra_fields: str = "",
    ) -> Path:
        active = self.repo / active_relative
        name = Path(active_relative).name
        backlog_relative = f"{location}/{name}"
        backlog = self.repo / backlog_relative
        backlog.parent.mkdir(parents=True, exist_ok=True)
        content = active.read_text(encoding="utf-8").replace(
            f"status: {from_status}",
            f"status: {status}{extra_fields}",
            1,
        )
        content = re.sub(
            r"^completion_deferred_reason: .*\n", "", content, flags=re.MULTILINE
        )
        backlog.write_text(content, encoding="utf-8")
        active.unlink()
        active_index = self.repo / "docs/plan/plan.md"
        active_index.write_text(
            "".join(
                line
                for line in active_index.read_text(encoding="utf-8").splitlines(
                    keepends=True
                )
                if not line.startswith(f"{plan_id}\t")
            ),
            encoding="utf-8",
        )
        return backlog

    def test_deferred_successor_with_rebind_record_can_defer_to_backlog(self) -> None:
        coupled, _, target_path, _ = self.prepare_coupled_spec(include_rebind=True)
        result = self.run_spec_data(coupled, "coupled-deferred-backlog.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        self.assertIsNotNone(target_path)
        assert target_path is not None
        backlog = self.move_successor_to_backlog(
            target_path, Path(target_path).name[:3], from_status="deferred"
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)
        text = backlog.read_text(encoding="utf-8")
        self.assertIn("status: backlog", text)
        self.assertNotIn("completion_deferred_reason:", text)

    def test_deferred_successor_backlog_move_rejects_acceptance_drift(self) -> None:
        coupled, _, target_path, _ = self.prepare_coupled_spec(include_rebind=True)
        result = self.run_spec_data(coupled, "coupled-deferred-backlog-drift.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(target_path)
        assert target_path is not None
        backlog = self.move_successor_to_backlog(
            target_path, Path(target_path).name[:3], from_status="deferred"
        )
        text = backlog.read_text(encoding="utf-8")
        acceptance = re.search(r"^acceptance:\n  - (.*)$", text, re.MULTILINE)
        self.assertIsNotNone(acceptance)
        assert acceptance is not None
        backlog.write_text(
            text.replace(acceptance.group(1), acceptance.group(1) + " drifted", 1),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_schema_three_successor_can_defer_to_backlog(self) -> None:
        coupled, _, _, successor_path = self.prepare_coupled_spec()
        result = self.run_spec_data(coupled, "coupled-backlog.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        plan_id = Path(successor_path).name[:3]
        backlog = self.move_successor_to_backlog(successor_path, plan_id)
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(backlog.is_file())
        self.assertIn("status: backlog", backlog.read_text(encoding="utf-8"))
        contract = json.loads(
            (self.repo / str(coupled["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(contract["successors"][0]["path"], successor_path)

    def test_schema_three_successor_can_be_shelved(self) -> None:
        coupled, _, _, successor_path = self.prepare_coupled_spec()
        result = self.run_spec_data(coupled, "coupled-shelved.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)
        plan_id = Path(successor_path).name[:3]
        shelved = self.move_successor_to_shelved(successor_path, plan_id)
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(shelved.is_file())
        self.assertIn("status: shelved", shelved.read_text(encoding="utf-8"))
        contract = json.loads(
            (self.repo / str(coupled["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(contract["successors"][0]["path"], successor_path)

    def test_backlog_successor_is_verified_as_fourth_lifecycle(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        backlog = self.move_successor_to_backlog(
            "docs/plan/active/002-data.md", "002"
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(backlog.is_file())
        self.assertIn("status: backlog", backlog.read_text(encoding="utf-8"))
        contract = json.loads(
            (self.repo / str(self.spec["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertIn(
            "docs/plan/active/002-data.md",
            [successor["path"] for successor in contract["successors"]],
        )

    def move_successor_to_shelved(
        self, active_relative: str, plan_id: str, **overrides: str
    ) -> Path:
        fields = overrides.pop("extra_fields", SHELVED_FIELDS)
        return self.move_successor_to_backlog(
            active_relative,
            plan_id,
            status=overrides.pop("status", "shelved"),
            location="docs/plan/shelved",
            extra_fields=fields,
            **overrides,
        )

    def test_shelved_successor_is_verified_as_a_lifecycle_location(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        shelved = self.move_successor_to_shelved(
            "docs/plan/active/002-data.md", "002"
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(shelved.is_file())
        self.assertIn("status: shelved", shelved.read_text(encoding="utf-8"))
        contract = json.loads(
            (self.repo / str(self.spec["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertIn(
            "docs/plan/active/002-data.md",
            [successor["path"] for successor in contract["successors"]],
        )

    def test_shelved_successor_requires_a_reason_and_a_date(self) -> None:
        for fields, expected in (
            ("\nshelved_at: 2026-08-30", "requires shelved_reason"),
            ("\nshelved_reason: \nshelved_at: 2026-08-30", "requires shelved_reason"),
            ("\nshelved_reason: deprioritized", "requires shelved_at"),
            (
                "\nshelved_reason: deprioritized\nshelved_at: 30-08-2026",
                "requires shelved_at",
            ),
        ):
            with self.subTest(fields=fields):
                self.setUp()
                self.assertEqual(self.run_command().returncode, 0)
                self.move_successor_to_shelved(
                    "docs/plan/active/002-data.md", "002", extra_fields=fields
                )
                verified = self.run_verify()
                self.assertNotEqual(verified.returncode, 0, verified.stdout)
                self.assertIn(expected, verified.stderr)

    def test_a_shelved_plan_reserves_its_plan_id(self) -> None:
        shelved = self.repo / "docs/plan/shelved/046-reserver.md"
        shelved.parent.mkdir(parents=True, exist_ok=True)
        shelved.write_text(
            "# Reserver\n\nstatus: shelved"
            f"{SHELVED_FIELDS}\nreserved_plan_ids:\n  - 002\n"
            "write_scope:\n  - docs/plan/\ncontext_files:\n  - none\n",
            encoding="utf-8",
        )
        occupant = self.repo / "docs/plan/checked/2026/08/16-31/002-occupant.md"
        occupant.parent.mkdir(parents=True, exist_ok=True)
        occupant.write_text("# Occupant\n\nstatus: checked\n", encoding="utf-8")
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(
            "uses plan id 002 reserved by docs/plan/shelved/046-reserver.md",
            verified.stderr,
        )
        shelved.unlink()
        self.assertEqual(self.run_verify().returncode, 0)

    def test_a_shelved_plan_is_seen_as_a_plan_id_occupant(self) -> None:
        backlog = self.repo / "docs/plan/backlog/046-reserver.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            "# Reserver\n\nstatus: backlog\nreserved_plan_ids:\n  - 047\n"
            "write_scope:\n  - docs/plan/\ncontext_files:\n  - none\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)
        shelved = self.repo / "docs/plan/shelved/047-occupant.md"
        shelved.parent.mkdir(parents=True, exist_ok=True)
        shelved.write_text(
            f"# Occupant\n\nstatus: shelved{SHELVED_FIELDS}\n", encoding="utf-8"
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(
            "plan docs/plan/shelved/047-occupant.md uses plan id 047 reserved by "
            "docs/plan/backlog/046-reserver.md",
            verified.stderr,
        )

    def test_a_live_plan_may_not_carry_stale_shelved_fields(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        self.move_successor_to_backlog(
            "docs/plan/active/002-data.md",
            "002",
            extra_fields=SHELVED_FIELDS,
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("carries stale shelved fields", verified.stderr)

    def test_a_shelved_plan_must_carry_the_shelved_status(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        self.move_successor_to_shelved(
            "docs/plan/active/002-data.md", "002", status="backlog"
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("shelved plan status must be shelved", verified.stderr)

    def test_shelved_successor_rejects_acceptance_drift(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        shelved = self.move_successor_to_shelved(
            "docs/plan/active/002-data.md", "002"
        )
        self.assertEqual(self.run_verify().returncode, 0)
        shelved.write_text(
            shelved.read_text(encoding="utf-8").replace(
                "  - Preserve user data.", "  - Discard user data.", 1
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_shelved_and_backlog_presence_is_ambiguous(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        active_text = (self.repo / "docs/plan/active/002-data.md").read_text(
            encoding="utf-8"
        )
        self.move_successor_to_shelved("docs/plan/active/002-data.md", "002")
        backlog = self.repo / "docs/plan/backlog/002-data.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            active_text.replace("status: in_progress", "status: backlog", 1),
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("ambiguous durable records", verified.stderr)

    def test_shelved_status_is_rejected_outside_the_shelved_location(self) -> None:
        stray = self.repo / "docs/plan/backlog/046-stray.md"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text(
            f"# Stray\n\nstatus: shelved{SHELVED_FIELDS}\n"
            "write_scope:\n  - docs/plan/\ncontext_files:\n  - none\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(
            "shelved status is written only under docs/plan/shelved: "
            "docs/plan/backlog/046-stray.md",
            verified.stderr,
        )
        stray.unlink()
        self.assertEqual(self.run_verify().returncode, 0)

    def test_a_shelved_plan_may_not_be_a_symlink(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        shelved = self.move_successor_to_shelved(
            "docs/plan/active/002-data.md", "002"
        )
        self.assertEqual(self.run_verify().returncode, 0)
        real = self.repo / "docs/plan/shelved-source.md"
        shelved.rename(real)
        shelved.symlink_to(Path("..") / real.name)
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn(
            "symlink path component is not allowed: docs/plan/shelved/002-data.md",
            verified.stderr,
        )

    def test_a_shelved_successor_may_not_change_a_protected_field(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        shelved = self.move_successor_to_shelved(
            "docs/plan/active/002-data.md", "002"
        )
        self.assertEqual(self.run_verify().returncode, 0)
        text = shelved.read_text(encoding="utf-8")
        self.assertIn("write_scope:\n", text)
        shelved.write_text(
            text.replace("write_scope:\n", "write_scope:\n  - docs/agent/\n", 1),
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("write_scope", verified.stderr)

    def test_backlog_successor_rejects_acceptance_drift(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        backlog = self.move_successor_to_backlog(
            "docs/plan/active/002-data.md", "002"
        )
        clean = backlog.read_text(encoding="utf-8")
        self.assertEqual(self.run_verify().returncode, 0)
        backlog.write_text(
            clean.replace("  - Preserve user data.", "  - Discard user data.", 1),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_backlog_successor_rejects_inherited_digest_drift(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        backlog = self.move_successor_to_backlog(
            "docs/plan/active/002-data.md", "002"
        )
        clean = backlog.read_text(encoding="utf-8")
        self.assertEqual(self.run_verify().returncode, 0)
        good_digest = digest(self.acceptance[0])
        bad_digest = "sha256:" + "0" * 64
        backlog.write_text(
            clean.replace(
                f"inherited_acceptance_digests:\n  - {good_digest}",
                f"inherited_acceptance_digests:\n  - {bad_digest}",
                1,
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_backlog_successor_rejects_non_backlog_status(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        self.move_successor_to_backlog(
            "docs/plan/active/002-data.md", "002", status="in_progress"
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_backlog_and_active_presence_is_ambiguous(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        active = self.repo / "docs/plan/active/002-data.md"
        backlog = self.repo / "docs/plan/backlog/002-data.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(
            active.read_text(encoding="utf-8").replace(
                "status: in_progress", "status: backlog", 1
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)

    def test_missing_backlog_and_active_successor_is_rejected(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        active = self.repo / "docs/plan/active/002-data.md"
        active.unlink()
        active_index = self.repo / "docs/plan/plan.md"
        active_index.write_text(
            "".join(
                line
                for line in active_index.read_text(encoding="utf-8").splitlines(
                    keepends=True
                )
                if not line.startswith("002\t")
            ),
            encoding="utf-8",
        )
        result = self.run_verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing live successor plan", result.stderr)

    def test_alternate_contract_filename_executes_and_verifies(self) -> None:
        alternate = "docs/plan/replanned/contracts/001-contract.json"
        original = str(self.spec["contract_path"])
        self.spec["contract_path"] = alternate
        for successor in [*self.spec["successors"], self.spec["integration"]]:  # type: ignore[index]
            successor["content"] = str(successor["content"]).replace(original, alternate)
        self.write_spec()
        transitioned = self.run_command()
        self.assertEqual(transitioned.returncode, 0, transitioned.stderr)
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_replanned_successor_preserves_ancestor_contract_evidence(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        source_path = "docs/plan/active/002-data.md"
        source = self.repo / source_path
        successor_digest = digest(self.acceptance[0])
        body_fixture = (
            "\n```yaml\n"
            "primary_invariant: this is body content\n"
            "integration_gates:\n  - preserve this example\n"
            "successor_plans:\n  - preserve this path\n"
            "inherited_acceptance_digests:\n  - preserve this digest example\n"
            "```\n"
        )
        nested_source = (
            source.read_text(encoding="utf-8")
            .replace("status: in_progress", "status: replan_required", 1)
            .replace(
                "primary_invariant: preserve one independently validatable invariant",
                "primary_invariant : preserve the literal checked_summary_ja: token",
                1,
            )
            .replace(
                "\nchecked_summary_ja:",
                "\nreplan_reason_codes:\n  - multiple_independent_invariants\nchecked_summary_ja :",
                1,
            )
            .replace(
                "integration_gates:\n  - verify the combined source acceptance\n",
                "integration_gates:\n\n    - verify the combined source acceptance\n\n",
            )
            .replace(
                "successor_plans:\n  - docs/plan/active/002-data.md\n"
                "  - docs/plan/active/003-integration.md\n",
                "successor_plans:\n\n    - docs/plan/active/002-data.md\n\n"
                "    - docs/plan/active/003-integration.md\n\n",
            )
            .replace(
                f"inherited_acceptance_digests:\n  - {successor_digest}\n",
                f"inherited_acceptance_digests:\n\n    - {successor_digest}\n\n",
            )
            + body_fixture
        )
        summary_line = "checked_summary_ja : 後続計画。\n"
        self.assertIn(summary_line, nested_source)
        nested_source = nested_source.replace(summary_line, "", 1).replace(
            "primary_invariant : preserve the literal checked_summary_ja: token\n",
            summary_line
            + "primary_invariant : preserve the literal checked_summary_ja: token\n",
            1,
        )
        source.write_text(
            nested_source,
            encoding="utf-8",
        )
        active_index = self.repo / "docs/plan/plan.md"
        active_index.write_text(
            active_index.read_text(encoding="utf-8").replace(
                "002\tdocs/plan/active/002-data.md\tin_progress",
                "002\tdocs/plan/active/002-data.md\treplan_required",
            ),
            encoding="utf-8",
        )
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "stop nested successor plan")

        source_text = source.read_text(encoding="utf-8")
        source_records = [{"text": self.acceptance[0], "digest": digest(self.acceptance[0])}]
        self.assertEqual(source_records[0]["digest"], successor_digest)
        replacements = {
            "docs/plan/replanned/contracts/001-source.json": "docs/plan/replanned/contracts/002-data.json",
            "docs/plan/active/002-data.md": "docs/plan/active/004-data.md",
            "docs/plan/active/003-integration.md": "docs/plan/active/005-integration.md",
        }

        def nested_content(integration: bool) -> str:
            content = self.plan_content("", [successor_digest], integration=integration).replace(
                self.source_path, "__NESTED_SOURCE__"
            )
            for old, new in replacements.items():
                content = content.replace(old, new)
            return content.replace("__NESTED_SOURCE__", source_path).replace(
                "  - Preserve user data.\n  - Run the integration check.\nvalidation_witness_schema:",
                "  - Preserve user data.\nvalidation_witness_schema:",
            )

        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        nested_spec = {
            "schema_version": 1,
            "source": {
                "path": source_path,
                "head": git(self.repo, "rev-parse", "HEAD"),
                "plan_digest": digest(source_text),
                "acceptance": source_records,
            },
            "reason_codes": ["multiple_independent_invariants"],
            "dirty_product_paths": [],
            "contract_path": "docs/plan/replanned/contracts/002-data.json",
            "archive_path": (
                f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{half}/002-data.md"
            ),
            "successors": [{
                "id": "004",
                "path": "docs/plan/active/004-data.md",
                "content": nested_content(False),
                "acceptance_digests": [successor_digest],
            }],
            "integration": {
                "id": "005",
                "path": "docs/plan/active/005-integration.md",
                "content": nested_content(True),
                "acceptance_digests": [successor_digest],
            },
        }
        nested_spec_path = self.base / "nested-restructure.json"
        nested_spec_path.write_text(
            json.dumps(nested_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        nested_result = subprocess.run(
            [sys.executable, "scripts/restructure-plan.py", str(nested_spec_path)],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(nested_result.returncode, 0, nested_result.stderr)

        archive = self.repo / str(nested_spec["archive_path"])
        archive_text = archive.read_text(encoding="utf-8")
        source_body = source_text[source_text.index("## Tasks\n"):]
        archive_body = archive_text[archive_text.index("## Tasks\n"):]
        archive_manifest = archive_text[:archive_text.index("## Tasks\n")]
        self.assertEqual(archive_body, source_body)
        self.assertNotIn("docs/plan/replanned/contracts/001-source.json", archive_manifest)
        self.assertNotIn("verify the combined source acceptance", archive_manifest)
        self.assertIn(
            "replan_contract: docs/plan/replanned/contracts/002-data.json",
            archive_manifest,
        )
        self.assertEqual(self.run_verify().returncode, 0)

        replanned_index = self.repo / "docs/plan/replanned.md"
        clean_replanned_index = replanned_index.read_text(encoding="utf-8")
        replanned_index.write_text(
            clean_replanned_index
            + "999\t"
            + str(nested_spec["archive_path"])
            + "\t"
            + str(nested_spec["contract_path"])
            + "\n",
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        replanned_index.write_text(clean_replanned_index, encoding="utf-8")

        active_index = self.repo / "docs/plan/plan.md"
        clean_active_index = active_index.read_text(encoding="utf-8")
        active_index.write_text(
            clean_active_index
            + "002\tdocs/plan/active/002-data.md\treplan_required\n",
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        active_index.write_text(clean_active_index, encoding="utf-8")

        archive.write_text(
            archive_text.replace(
                f"  - {successor_digest}", "  - sha256:" + "0" * 64, 1
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
            "  - Preserve user data.\nvalidation_witness_schema:",
            "  - Preserve user data.\n  - Clarification: discard user data.\nvalidation_witness_schema:",
        )
        self.write_spec()
        self.assertNotEqual(self.run_command().returncode, 0)
        self.assert_source_unchanged()

        self.spec = self.make_spec()
        successor = self.spec["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            "  - Preserve user data.\nvalidation_witness_schema:",
            "  - Preserve user data.\n  - Add an unrelated requirement.\nvalidation_witness_schema:",
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
            "preservation_scope:\n  - none",
            f"preservation_scope:\n  - {dirty_relative}",
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

    def test_dirty_product_path_requires_preservation_scope(self) -> None:
        dirty = self.repo / "config/user.yaml"
        dirty.parent.mkdir()
        dirty.write_text("user: true\n", encoding="utf-8")
        self.spec["dirty_product_paths"] = ["config/user.yaml"]
        self.write_spec()
        result = self.run_command()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preservation_scope must exactly match", result.stderr)
        self.assertEqual(dirty.read_text(encoding="utf-8"), "user: true\n")
        self.assert_source_unchanged()

    def test_preservation_scope_requires_exact_path_and_rejects_write_overlap(self) -> None:
        dirty = self.repo / "config/project-owned.yaml"
        dirty.parent.mkdir()
        dirty.write_text("user: true\n", encoding="utf-8")
        self.spec["dirty_product_paths"] = ["config/project-owned.yaml"]
        integration = self.spec["integration"]  # type: ignore[assignment]
        integration["content"] = str(integration["content"]).replace(
            "preservation_scope:\n  - none", "preservation_scope:\n  - config/"
        )
        self.write_spec()
        rejected = self.run_command()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unique normalized exact paths", rejected.stderr)
        self.assertEqual(dirty.read_text(encoding="utf-8"), "user: true\n")
        self.assert_source_unchanged()

        integration["content"] = str(integration["content"]).replace(
            "preservation_scope:\n  - config/",
            "preservation_scope:\n  - config/project-owned.yaml",
        ).replace(
            "write_scope:\n  - tests/", "write_scope:\n  - config/"
        )
        self.write_spec()
        overlap = self.run_command()
        self.assertNotEqual(overlap.returncode, 0)
        self.assertIn("preservation_scope overlaps write_scope", overlap.stderr)
        self.assert_source_unchanged()

        integration["content"] = str(integration["content"]).replace(
            "write_scope:\n  - config/", "write_scope:\n  - tests/"
        )
        self.write_spec()
        accepted = self.run_command()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(dirty.read_text(encoding="utf-8"), "user: true\n")

    def test_duplicate_and_dropped_preservation_scope_are_rejected(self) -> None:
        dirty = self.repo / "config/project-owned.yaml"
        dirty.parent.mkdir()
        dirty.write_text("user: true\n", encoding="utf-8")
        self.spec["dirty_product_paths"] = ["config/project-owned.yaml"]
        for successor in [self.spec["successors"][0], self.spec["integration"]]:  # type: ignore[index]
            successor["content"] = str(successor["content"]).replace(
                "preservation_scope:\n  - none",
                "preservation_scope:\n  - config/project-owned.yaml",
            )
        self.write_spec()
        duplicate = self.run_command()
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("assigned exactly once", duplicate.stderr)
        self.assert_source_unchanged()

        self.spec = self.make_spec()
        self.spec["dirty_product_paths"] = ["config/project-owned.yaml"]
        integration = self.spec["integration"]  # type: ignore[assignment]
        integration["content"] = str(integration["content"]).replace(
            "preservation_scope:\n  - none",
            "preservation_scope:\n  - config/project-owned.yaml",
        )
        self.write_spec()
        self.assertEqual(self.run_command().returncode, 0)
        integration_path = self.repo / str(integration["path"])
        integration_path.write_text(
            integration_path.read_text(encoding="utf-8").replace(
                "preservation_scope:\n  - config/project-owned.yaml",
                "preservation_scope:\n  - none",
            ),
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("live successor preservation_scope mismatch", verified.stderr)

    def test_legacy_schema_one_contract_without_preservation_scope_still_verifies(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["schema_version"] = 1
        for successor in contract["successors"]:
            for key in (
                "authoritative_validation",
                "authoritative_validation_digest",
                "validation_witness_schema",
                "validation_witness_map_digest",
            ):
                successor.pop(key)
            successor["content"] = successor["content"].replace(
                "preservation_scope:\n  - none\n", ""
            )
            successor["content_digest"] = digest(successor["content"])
            live = self.repo / successor["path"]
            live.write_text(
                live.read_text(encoding="utf-8").replace(
                    "preservation_scope:\n  - none\n", ""
                ),
                encoding="utf-8",
            )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_schema_one_partial_repeated_preservation_scope_verifies(self) -> None:
        self.add_sequential_successor()
        self.write_spec()
        self.assertEqual(self.run_command().returncode, 0)
        first = "config/first-owned.yaml"
        second = "config/second-owned.yaml"
        contract = self.convert_contract_to_schema_one(
            [[first], [first, second], None],
            [first, second],
        )
        omitted = contract["successors"][2]
        omitted["content"] = omitted["content"].replace(
            "write_scope:\n  - tests/",
            "write_scope:\n  - config/",
        )
        omitted["content_digest"] = digest(omitted["content"])
        live = self.repo / omitted["path"]
        live.write_text(
            live.read_text(encoding="utf-8").replace(
                "write_scope:\n  - tests/",
                "write_scope:\n  - config/",
            ),
            encoding="utf-8",
        )
        contract_path = self.repo / str(self.spec["contract_path"])
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_schema_one_declared_preservation_requires_complete_coverage(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        self.convert_contract_to_schema_one(
            [[], None],
            ["config/project-owned.yaml"],
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn(
            "contract preservation_scope does not match dirty paths",
            verified.stderr,
        )

    def test_schema_one_preservation_rejects_cross_successor_write_overlap(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        first = "config/first/project-owned.yaml"
        second = "config/second/project-owned.yaml"
        contract = self.convert_contract_to_schema_one(
            [[first], [second]],
            [first, second],
        )
        successor = contract["successors"][1]
        successor["content"] = successor["content"].replace(
            "write_scope:\n  - tests/",
            "write_scope:\n  - config/first/",
        )
        successor["content_digest"] = digest(successor["content"])
        live = self.repo / successor["path"]
        live.write_text(
            live.read_text(encoding="utf-8").replace(
                "write_scope:\n  - tests/",
                "write_scope:\n  - config/first/",
            ),
            encoding="utf-8",
        )
        contract_path = self.repo / str(self.spec["contract_path"])
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("preservation_scope overlaps write_scope", verified.stderr)

    def test_schema_two_still_rejects_mixed_preservation_metadata(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        successor = contract["successors"][0]
        successor["content"] = successor["content"].replace(
            "preservation_scope:\n  - none\n",
            "",
        )
        successor["content_digest"] = digest(successor["content"])
        live = self.repo / successor["path"]
        live.write_text(
            live.read_text(encoding="utf-8").replace(
                "preservation_scope:\n  - none\n",
                "",
            ),
            encoding="utf-8",
        )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("contract successors mix preservation schemas", verified.stderr)

    def test_schema_two_verifier_still_requires_exact_once_preservation(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        preserved = "config/project-owned.yaml"
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["dirty_product_paths"] = [preserved]
        for successor in contract["successors"]:
            successor["content"] = successor["content"].replace(
                "preservation_scope:\n  - none\n",
                f"preservation_scope:\n  - {preserved}\n",
            )
            successor["content_digest"] = digest(successor["content"])
            live = self.repo / successor["path"]
            live.write_text(
                live.read_text(encoding="utf-8").replace(
                    "preservation_scope:\n  - none\n",
                    f"preservation_scope:\n  - {preserved}\n",
                ),
                encoding="utf-8",
            )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn(
            "contract preservation_scope does not match dirty paths",
            verified.stderr,
        )

    def run_nested_restructure(
        self,
        source_path: str,
    ) -> subprocess.CompletedProcess[str]:
        """Stop one live schema-1 contract successor and restructure it in place."""
        module = self.load_restructure_module("nested_companion_module")
        source = self.repo / source_path
        source.write_text(
            module.derive_stopped_source_content(
                source.read_text(encoding="utf-8"),
                ["multiple_independent_invariants"],
            ),
            encoding="utf-8",
        )
        source_id = Path(source_path).name[:3]
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"{source_id}\t{source_path}\tin_progress",
                f"{source_id}\t{source_path}\treplan_required",
            ),
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "stop the nested successor")
        source_text = source.read_text(encoding="utf-8")
        records = module.acceptance_records(source_text)
        mapped = [record["digest"] for record in records]
        replacements = {
            "docs/plan/replanned/contracts/001-source.json": (
                f"docs/plan/replanned/contracts/{source_id}-nested.json"
            ),
            "docs/plan/active/002-data.md": "docs/plan/active/004-nested.md",
            "docs/plan/active/003-integration.md": "docs/plan/active/005-nested-integration.md",
        }

        def nested_content(integration: bool) -> str:
            content = self.plan_content("", mapped, integration=integration).replace(
                self.source_path, "__NESTED_SOURCE__"
            )
            for old, new in replacements.items():
                content = content.replace(old, new)
            return content.replace("__NESTED_SOURCE__", source_path)

        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        spec = {
            "schema_version": 1,
            "source": {
                "path": source_path,
                "head": git(self.repo, "rev-parse", "HEAD"),
                "plan_digest": digest(source_text),
                "acceptance": records,
            },
            "reason_codes": ["multiple_independent_invariants"],
            "dirty_product_paths": [],
            "contract_path": f"docs/plan/replanned/contracts/{source_id}-nested.json",
            "archive_path": (
                f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{half}/"
                f"{Path(source_path).name}"
            ),
            "successors": [
                {
                    "id": "004",
                    "path": "docs/plan/active/004-nested.md",
                    "content": nested_content(False),
                    "acceptance_digests": mapped,
                }
            ],
            "integration": {
                "id": "005",
                "path": "docs/plan/active/005-nested-integration.md",
                "content": nested_content(True),
                "acceptance_digests": mapped,
            },
        }
        return self.run_spec_data(spec, f"nested-{source_id}.json")

    def companion_path(self) -> Path:
        return (
            self.repo
            / "docs/plan/replanned/baselines/live-validation-successors-v1.json"
        )

    def publish_schema_one_companion(self) -> dict[str, object]:
        """Turn the fixture contract into a schema-1 contract and publish its companion.

        Only a schema-1 contract contributes companion records, so a reconstruction
        that archives one of its live successors is the case the projection must cover.
        """
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["schema_version"] = 1
        companion_successors = []
        for successor in contract["successors"]:
            projection = {
                key: successor.pop(key)
                for key in (
                    "authoritative_validation",
                    "authoritative_validation_digest",
                    "validation_witness_schema",
                    "validation_witness_map_digest",
                )
            }
            companion_successors.append(
                {
                    "path": successor["path"],
                    "acceptance_digests": successor["acceptance_digests"],
                    **projection,
                }
            )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        companion = {
            "schema_version": 1,
            "records": [
                {
                    "contract_path": str(self.spec["contract_path"]),
                    "contract_digest": digest(contract_path.read_bytes()),
                    "successors": companion_successors,
                }
            ],
        }
        path = self.companion_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(companion, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "publish schema-1 companion baseline")
        published = self.run_verify()
        self.assertEqual(published.returncode, 0, published.stderr)
        return companion

    def test_reconstruction_drops_only_the_archived_companion_successor(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        companion = self.publish_schema_one_companion()
        retained = [
            successor
            for successor in companion["records"][0]["successors"]
            if successor["path"] != "docs/plan/active/002-data.md"
        ]
        self.assertTrue(retained)
        result = self.run_nested_restructure("docs/plan/active/002-data.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        projected = json.loads(self.companion_path().read_text(encoding="utf-8"))
        self.assertEqual(projected["schema_version"], 1)
        self.assertEqual(len(projected["records"]), 1)
        self.assertEqual(projected["records"][0]["successors"], retained)
        self.assertEqual(
            projected["records"][0]["contract_digest"],
            companion["records"][0]["contract_digest"],
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_reconstruction_removes_a_companion_record_without_live_successors(
        self,
    ) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        companion = self.publish_schema_one_companion()
        self.assertEqual(len(companion["records"][0]["successors"]), 2)
        coupled["source_head"] = git(self.repo, "rev-parse", "HEAD")
        result = self.run_spec_data(coupled, "companion-emptied.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        projected = json.loads(self.companion_path().read_text(encoding="utf-8"))
        self.assertEqual(projected, {"schema_version": 1, "records": []})
        self.assertEqual(self.run_verify().returncode, 0)

    def test_reconstruction_rejects_a_companion_replaced_after_verification(
        self,
    ) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        companion = self.publish_schema_one_companion()
        module = self.load_restructure_module("companion_binding_module")
        state = {
            "archived_plans": {
                "docs/plan/active/002-data.md": (
                    "docs/plan/replanned/2026/08/16-31/002-data.md"
                )
            }
        }
        projected = [
            {
                **companion["records"][0],
                "successors": [
                    successor
                    for successor in companion["records"][0]["successors"]
                    if successor["path"] != "docs/plan/active/002-data.md"
                ],
            }
        ]
        self.companion_path().write_text(
            json.dumps(
                {"schema_version": 1, "records": projected},
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        original = json.dumps(
            {"schema_version": 1, "records": companion["records"]},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
        with self.assertRaises(module.RestructureError) as raised:
            module.project_companion_baseline(state, {"companion_text": original})
        self.assertIn("changed during the transaction", str(raised.exception))

    def test_reconstruction_rejects_a_published_companion_disagreement(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        companion = self.publish_schema_one_companion()
        successors = companion["records"][0]["successors"]
        untouched = next(
            successor
            for successor in successors
            if successor["path"] != "docs/plan/active/002-data.md"
        )
        untouched["acceptance_digests"] = ["sha256:" + "0" * 64]
        self.companion_path().write_text(
            json.dumps(companion, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "publish a disagreeing companion baseline")
        result = self.run_nested_restructure("docs/plan/active/002-data.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("companion baseline mismatch", result.stderr)

    def test_schema_one_companion_is_exact_ordered_and_terminal_after_publication(self) -> None:
        self.assertEqual(self.run_command().returncode, 0)
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["schema_version"] = 1
        companion_successors = []
        for index, successor in enumerate(contract["successors"]):
            projection = {
                key: successor.pop(key)
                for key in (
                    "authoritative_validation",
                    "authoritative_validation_digest",
                    "validation_witness_schema",
                    "validation_witness_map_digest",
                )
            }
            companion_successors.append(
                {
                    "path": successor["path"],
                    "acceptance_digests": successor["acceptance_digests"],
                    **projection,
                }
            )
            if index == 0:
                successor["content"] = successor["content"].replace(
                    '"witness":"git diff --check"',
                    '"witness":"python3 tests/test-plan-restructure.py"',
                    1,
                )
                successor["content_digest"] = digest(successor["content"])
                live = self.repo / successor["path"]
                live.write_text(
                    live.read_text(encoding="utf-8").replace(
                        '"witness":"git diff --check"',
                        '"witness":"python3 tests/test-plan-restructure.py"',
                        1,
                    ),
                    encoding="utf-8",
                )
                companion_successors[-1]["validation_witness_map_digest"] = digest(
                    '[{"acceptance_sha256":"'
                    + digest(self.acceptance[0])
                    + '","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}]'
                )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        companion = {
            "schema_version": 1,
            "records": [
                {
                    "contract_path": str(self.spec["contract_path"]),
                    "contract_digest": digest(contract_path.read_bytes()),
                    "successors": companion_successors,
                }
            ],
        }
        companion_path = (
            self.repo
            / "docs/plan/replanned/baselines/live-validation-successors-v1.json"
        )
        companion_path.parent.mkdir(parents=True)
        companion_path.write_text(
            json.dumps(companion, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        accepted = self.run_verify()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

        companion["records"][0]["successors"].reverse()
        companion_path.write_text(
            json.dumps(companion, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        reordered = self.run_verify()
        self.assertNotEqual(reordered.returncode, 0)
        self.assertIn("companion baseline mismatch", reordered.stderr)

        companion["records"][0]["successors"].reverse()
        companion_path.write_text(
            json.dumps(companion, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "publish companion baseline")
        companion_path.unlink()
        missing = self.run_verify()
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing live validation successor companion baseline", missing.stderr)

    def test_schema_three_reconstructs_coupled_sources_with_prerequisite(self) -> None:
        coupled, _, _, successor_path = self.prepare_coupled_spec(
            include_prerequisite=True
        )
        result = self.run_spec_data(coupled, "coupled.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract_path = self.repo / str(coupled["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], 3)
        self.assertEqual(
            [source["id"] for source in contract["sources"]],
            ["002", "003"],
        )
        self.assertEqual(
            contract["successors"][0]["integration_source_ids"],
            ["002", "003"],
        )
        for source, mapping in zip(
            contract["sources"],
            contract["successors"][0]["acceptance_mappings"],
            strict=True,
        ):
            self.assertEqual(
                mapping["acceptance_digests"],
                source["acceptance_digests"],
            )
        for source in contract["sources"]:
            self.assertFalse((self.repo / source["path"]).exists())
            self.assertTrue((self.repo / source["archive_path"]).is_file())
            self.assertEqual(
                digest(source["stopped_content"]),
                source["stopped_plan_digest"],
            )
        active = (self.repo / "docs/plan/plan.md").read_text(encoding="utf-8")
        self.assertIn(
            "005\tdocs/plan/active/005-coupled-prerequisite.md\tin_progress",
            active,
        )
        self.assertIn(f"006\t{successor_path}\tdeferred", active)
        self.assertEqual(self.run_verify().returncode, 0)

    def check_successor(
        self,
        successor_path: str,
        *,
        product_path: str | None = None,
    ) -> str:
        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        checked_path = (
            f"docs/plan/checked/{today.year:04d}/{today.month:02d}/{half}/"
            f"{Path(successor_path).name}"
        )
        source = self.repo / successor_path
        checked = self.repo / checked_path
        checked.parent.mkdir(parents=True, exist_ok=True)
        checked.write_text(
            source.read_text(encoding="utf-8").replace(
                "status: in_progress",
                "status: checked",
                1,
            ),
            encoding="utf-8",
        )
        source.unlink()
        plan_id = Path(successor_path).name[:3]
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            "".join(
                line
                for line in active.read_text(encoding="utf-8").splitlines(
                    keepends=True
                )
                if not line.startswith(f"{plan_id}\t")
            ),
            encoding="utf-8",
        )
        checked_index = self.repo / "docs/plan/checked.md"
        with checked_index.open("a", encoding="utf-8") as handle:
            handle.write(f"{plan_id}\t{checked_path}\n")
        if product_path:
            self.assertTrue((self.repo / product_path).is_file())
            (self.repo / product_path).write_text(
                "generated: checked\n",
                encoding="utf-8",
            )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "check coupled successor")
        return checked_path

    def activation_spec(
        self,
        *,
        module,
        target_path: str,
        successor_path: str,
        checked_path: str,
        promoted_path: str | None,
        deferred_reason: str = "integration successor must be checked",
    ) -> dict[str, object]:
        original = (self.repo / target_path).read_text(encoding="utf-8")
        reason_line = (
            f"completion_deferred_reason: {deferred_reason}\n"
        )
        replacements: list[dict[str, object]] = [
            {
                "scope": "manifest",
                "field": "status",
                "old": "status: deferred\n",
                "new": "status: in_progress\n",
                "count": 1,
            },
            {
                "scope": "manifest",
                "field": "completion_deferred_reason",
                "old": reason_line,
                "new": "",
                "count": 1,
            },
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": successor_path,
                "new": checked_path,
                "count": 1,
            },
        ]
        updated = (
            original.replace("status: deferred\n", "status: in_progress\n", 1)
            .replace(reason_line, "", 1)
            .replace(successor_path, checked_path, 1)
        )
        if promoted_path:
            replacements.extend(
                [
                    {
                        "scope": "manifest",
                        "field": "preservation_scope",
                        "old": f"  - {promoted_path}\n",
                        "new": "  - none\n",
                        "count": 1,
                    },
                    {
                        "scope": "manifest",
                        "field": "context_files",
                        "old": "  - docs/agent/spec-index.yaml\n",
                        "new": (
                            "  - docs/agent/spec-index.yaml\n"
                            f"  - {promoted_path}\n"
                        ),
                        "count": 1,
                    },
                ]
            )
            updated = updated.replace(
                f"  - {promoted_path}\n",
                "  - none\n",
                1,
            ).replace(
                "  - docs/agent/spec-index.yaml\n",
                "  - docs/agent/spec-index.yaml\n"
                f"  - {promoted_path}\n",
                1,
            )
        state = module.verify_repository_contracts()
        return {
            "schema_version": 3,
            "operation": "rebind",
            "source_head": git(self.repo, "rev-parse", "HEAD"),
            "rebindings": [
                {
                    "kind": "activation",
                    "plan_path": target_path,
                    "owning_contract_path": state["live_successors"][target_path][
                        "contract_path"
                    ],
                    "original_content_digest": digest(original),
                    "prior_effective_projection_digest": module.projection_digest(
                        state["effective_projections"][target_path]
                    ),
                    "updated_content_digest": digest(updated),
                    "replacements": replacements,
                    "promoted_preservation_path": promoted_path,
                }
            ],
        }

    def test_rebind_overlay_and_activation_form_one_digest_chain(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "coupled-rebind.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.repo / target_path
        self.assertIn(successor_path, target.read_text(encoding="utf-8"))
        baseline_path = (
            self.repo
            / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
        )
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertEqual(len(baseline["records"]), 1)
        self.assertEqual(self.run_verify().returncode, 0)

        checked_path = self.check_successor(successor_path)
        module = self.load_restructure_module("activation_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        activated = self.run_spec_data(activation, "activation.json")
        self.assertEqual(activated.returncode, 0, activated.stderr)
        self.assertIn(
            "status: in_progress",
            target.read_text(encoding="utf-8"),
        )
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertEqual(len(baseline["records"]), 2)
        self.assertEqual(
            baseline["records"][1]["original_content_digest"],
            baseline["records"][0]["updated_content_digest"],
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_durable_activation_record_is_reauthorized(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "durable-activation-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(successor_path)
        module = self.load_restructure_module("durable_activation_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        activated = self.run_spec_data(
            activation,
            "durable-activation.json",
        )
        self.assertEqual(activated.returncode, 0, activated.stderr)

        unrelated_checked = checked_path.replace(
            Path(checked_path).name,
            "099-unrelated.md",
        )
        unrelated = self.repo / unrelated_checked
        unrelated.write_text(
            "# Unrelated\n\nstatus: checked\nwrite_scope:\n  - none\n",
            encoding="utf-8",
        )
        with (self.repo / "docs/plan/checked.md").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(f"099\t{unrelated_checked}\n")
        baseline_path = (
            self.repo
            / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
        )
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        record = baseline["records"][-1]
        for replacement in record["replacements"]:
            if replacement["field"] == "predecessor_plans":
                replacement["new"] = unrelated_checked
        record["updated_content"] = record["updated_content"].replace(
            checked_path,
            unrelated_checked,
            1,
        )
        record["updated_content_digest"] = digest(record["updated_content"])
        record["record_digest"] = module.canonical_digest(
            {
                key: value
                for key, value in record.items()
                if key != "record_digest"
            }
        )
        baseline_path.write_text(
            json.dumps(
                baseline,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.repo / target_path).write_text(
            record["updated_content"],
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("exact checked references", rejected.stderr)

    def prepare_reservation(self, label: str):
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, f"{label}-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(successor_path)
        module = self.load_restructure_module(f"{label}_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        activated = self.run_spec_data(activation, f"{label}-activation.json")
        self.assertEqual(activated.returncode, 0, activated.stderr)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "activate the reservation target")
        return module, target_path

    def authorize_plan_edit(self, target_path: str, old: str, new: str) -> str:
        plan = self.repo / target_path
        text = plan.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        plan.write_text(text.replace(old, new, 1), encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "authorize the reservation change")
        return git(self.repo, "rev-parse", "HEAD")

    def reserve_spec(
        self,
        *,
        target_path: str,
        authorizing_commit: str,
        replacements: list[dict[str, object]],
    ) -> dict[str, object]:
        baseline = json.loads(
            (
                self.repo
                / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
            ).read_text(encoding="utf-8")
        )
        chained = [
            record
            for record in baseline["records"]
            if record["plan_path"] == target_path
        ]
        module = self.load_restructure_module("reserve_spec_module")
        return {
            "schema_version": 3,
            "operation": "reserve",
            "source_head": git(self.repo, "rev-parse", "HEAD"),
            "reservations": [
                {
                    "plan_path": target_path,
                    "owning_contract_path": chained[-1]["owning_contract_path"],
                    "authorizing_commit": authorizing_commit,
                    "prior_effective_projection_digest": module.projection_digest(
                        chained[-1]["resulting_validation_projection"]
                    ),
                    "replacements": replacements,
                }
            ],
        }

    def test_reserve_operation_records_an_authorized_write_scope_change(
        self,
    ) -> None:
        _, target_path = self.prepare_reservation("reserve-success")
        original_scope = "write_scope:\n  - src/\n"
        extended_scope = "write_scope:\n  - src/\n  - extension/\n"
        plan_text = (self.repo / target_path).read_text(encoding="utf-8")
        self.assertIn(original_scope, plan_text)
        commit = self.authorize_plan_edit(
            target_path,
            original_scope,
            extended_scope,
        )
        spec = self.reserve_spec(
            target_path=target_path,
            authorizing_commit=commit,
            replacements=[
                {
                    "scope": "manifest",
                    "field": "write_scope",
                    "old": "  - src/\n",
                    "new": "  - src/\n  - extension/\n",
                    "count": 1,
                }
            ],
        )
        reserved = self.run_spec_data(spec, "reserve-success.json")
        self.assertEqual(reserved.returncode, 0, reserved.stderr)
        baseline = json.loads(
            (
                self.repo
                / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
            ).read_text(encoding="utf-8")
        )
        record = baseline["records"][-1]
        self.assertEqual(record["kind"], "reservation")
        self.assertEqual(record["authorizing_commit"], commit)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_reserve_operation_rejects_an_unauthorized_reservation_change(
        self,
    ) -> None:
        _, target_path = self.prepare_reservation("reserve-unauthorized")
        commit = self.authorize_plan_edit(
            target_path,
            "  - src/\n",
            "  - src/\n  - extension/\n",
        )
        spec = self.reserve_spec(
            target_path=target_path,
            authorizing_commit=commit,
            replacements=[
                {
                    "scope": "manifest",
                    "field": "write_scope",
                    "old": "  - src/\n",
                    "new": "  - src/\n  - unauthorized/\n",
                    "count": 1,
                }
            ],
        )
        rejected = self.run_spec_data(spec, "reserve-unauthorized.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("replacement reproduction mismatch", rejected.stderr)

    def test_durable_reservation_record_rejects_a_forged_authorizing_commit(
        self,
    ) -> None:
        module, target_path = self.prepare_reservation("reserve-forged")
        commit = self.authorize_plan_edit(
            target_path,
            "write_scope:\n  - src/\n",
            "write_scope:\n  - src/\n  - extension/\n",
        )
        spec = self.reserve_spec(
            target_path=target_path,
            authorizing_commit=commit,
            replacements=[
                {
                    "scope": "manifest",
                    "field": "write_scope",
                    "old": "  - src/\n",
                    "new": "  - src/\n  - extension/\n",
                    "count": 1,
                }
            ],
        )
        reserved = self.run_spec_data(spec, "reserve-forged.json")
        self.assertEqual(reserved.returncode, 0, reserved.stderr)
        baseline_path = (
            self.repo
            / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
        )
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        record = baseline["records"][-1]
        record["authorizing_commit"] = git(self.repo, "rev-parse", f"{commit}^")
        record["record_digest"] = module.canonical_digest(
            {
                key: value
                for key, value in record.items()
                if key != "record_digest"
            }
        )
        baseline_path.write_text(
            json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "authorizing commit does not carry the reservation change",
            rejected.stderr,
        )

    def test_rebind_validation_uses_only_admitted_semantic_path_pairs(self) -> None:
        coupled, _, target_path, _ = self.prepare_coupled_spec(
            include_rebind=True,
            validation_rebind=True,
        )
        assert target_path
        result = self.run_spec_data(coupled, "validation-rebind.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.repo / target_path).read_text(encoding="utf-8")
        self.assertIn("python3 tests/test-copier-fixture-validator.py", content)
        self.assertNotIn("python3 tests/test-copier-fixture.py", content)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_rebind_rejects_allowlisted_but_unadmitted_validation_path(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True,
            validation_rebind=True,
        )
        assert target_path
        admitted = "tests/test-copier-fixture-validator.py"
        weaker = "tests/test-validation-tools.py"
        successor = coupled["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            admitted,
            weaker,
        )
        rebind = coupled["rebindings"][0]  # type: ignore[index]
        for replacement in rebind["replacements"]:
            if replacement["new"] == admitted:
                replacement["new"] = weaker
        original = (self.repo / target_path).read_text(encoding="utf-8")
        integration_path = str(self.spec["integration"]["path"])  # type: ignore[index]
        updated = original.replace(integration_path, successor_path, 1).replace(
            "tests/test-copier-fixture.py",
            weaker,
        )
        rebind["updated_content_digest"] = digest(updated)
        rejected = self.run_spec_data(coupled, "unadmitted-validation-rebind.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("semantic-preserving path substitutions", rejected.stderr)

    def test_activation_rejects_unrelated_checked_plan_and_header_rewrite(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "activation-security-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(successor_path)
        unrelated_checked = checked_path.replace(
            Path(checked_path).name,
            "099-unrelated.md",
        )
        unrelated = self.repo / unrelated_checked
        unrelated.write_text(
            "# Unrelated\n\n"
            "status: checked\n"
            "write_scope:\n  - none\n",
            encoding="utf-8",
        )
        with (self.repo / "docs/plan/checked.md").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(f"099\t{unrelated_checked}\n")
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "add unrelated checked plan")
        module = self.load_restructure_module("activation_security_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        rebind = activation["rebindings"][0]  # type: ignore[index]
        for replacement in rebind["replacements"]:
            if replacement["field"] == "predecessor_plans":
                replacement["new"] = unrelated_checked
        original = (self.repo / target_path).read_text(encoding="utf-8")
        updated = (
            original.replace("status: deferred\n", "status: in_progress\n", 1)
            .replace(
                "completion_deferred_reason: integration successor must be checked\n",
                "",
                1,
            )
            .replace(successor_path, unrelated_checked, 1)
        )
        rebind["updated_content_digest"] = digest(updated)
        unrelated_result = self.run_spec_data(
            activation,
            "unrelated-activation.json",
        )
        self.assertNotEqual(unrelated_result.returncode, 0)
        self.assertIn("exact checked references", unrelated_result.stderr)

        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        rebind = activation["rebindings"][0]  # type: ignore[index]
        rebind["replacements"].append(
            {
                "scope": "manifest",
                "field": "integration_gates",
                "old": "integration_gates:\n",
                "new": "",
                "count": 1,
            }
        )
        rebind["updated_content_digest"] = digest(
            module.apply_exact_replacements(
                original,
                rebind["replacements"],
                kind="activation",
                label="header rewrite",
            )
        )
        header_result = self.run_spec_data(
            activation,
            "header-rewrite-activation.json",
        )
        self.assertNotEqual(header_result.returncode, 0)
        self.assertIn("exact active-to-checked transition", header_result.stderr)

    def test_activation_rejects_unresolved_active_plan_reference_in_body(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True,
            target_body_reference=True,
        )
        assert target_path
        result = self.run_spec_data(coupled, "activation-body-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(successor_path)
        module = self.load_restructure_module("activation_body_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        rejected = self.run_spec_data(
            activation,
            "unresolved-body-activation.json",
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "activation leaves active plan references unresolved",
            rejected.stderr,
        )

    def test_standalone_activation_rejects_initial_rebind_kind(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "standalone-kind-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(successor_path)
        module = self.load_restructure_module("standalone_kind_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=None,
        )
        activation["rebindings"][0]["kind"] = "rebind"  # type: ignore[index]
        rejected = self.run_spec_data(activation, "wrong-activation-kind.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not permitted for this operation", rejected.stderr)

    def test_unrebound_schema_two_and_three_successors_reject_body_drift(self) -> None:
        coupled, module, _, successor_path = self.prepare_coupled_spec()
        schema_two = self.repo / str(self.spec["integration"]["path"])  # type: ignore[index]
        schema_two_original = schema_two.read_text(encoding="utf-8")
        schema_two.write_text(
            schema_two_original.replace(
                "preserve one independently validatable invariant",
                "drift the schema two invariant",
                1,
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("live successor lifecycle", rejected.stderr)
        schema_two.write_text(schema_two_original, encoding="utf-8")
        stopped_schema_two = self.repo / str(self.spec["successors"][0]["path"])  # type: ignore[index]
        stopped_schema_two_original = stopped_schema_two.read_text(encoding="utf-8")
        stopped_schema_two.write_text(
            stopped_schema_two_original.replace(
                "- [ ] implement",
                "- [ ] drift stopped schema two work",
                1,
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("live successor lifecycle", rejected.stderr)
        stopped_schema_two.write_text(
            stopped_schema_two_original,
            encoding="utf-8",
        )

        result = self.run_spec_data(coupled, "unrebound-lifecycle-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        schema_three = self.repo / successor_path
        schema_three_original = schema_three.read_text(encoding="utf-8")
        schema_three.write_text(
            schema_three_original.replace(
                "integrate every coupled source acceptance mapping",
                "drift the schema three invariant",
                1,
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("live successor lifecycle", rejected.stderr)
        stopped_schema_three = module.derive_stopped_source_content(
            schema_three_original,
            ["multiple_independent_invariants"],
        ).replace(
            "- [ ] integrate",
            "- [ ] drift stopped schema three work",
            1,
        )
        schema_three.write_text(stopped_schema_three, encoding="utf-8")
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"{Path(successor_path).name[:3]}\t{successor_path}\tin_progress",
                f"{Path(successor_path).name[:3]}\t{successor_path}\treplan_required",
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("live successor lifecycle", rejected.stderr)

    def test_rebound_plan_allows_only_exact_normal_lifecycle_changes(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "lifecycle-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_predecessor = self.check_successor(successor_path)
        module = self.load_restructure_module("lifecycle_activation_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_predecessor,
            promoted_path=None,
        )
        activated = self.run_spec_data(activation, "lifecycle-activation.json")
        self.assertEqual(activated.returncode, 0, activated.stderr)
        target = self.repo / target_path
        ready_content = (
            target.read_text(encoding="utf-8")
            .replace("status: in_progress\n", "status: ready_to_archive\n", 1)
            .replace("- [ ] implement\n", "- [x] implement\n", 1)
            + "\n## Validation Notes\n\n- focused validation passed.\n"
        )
        target.write_text(ready_content, encoding="utf-8")
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"{Path(target_path).name[:3]}\t{target_path}\tin_progress",
                f"{Path(target_path).name[:3]}\t{target_path}\tready_to_archive",
            ),
            encoding="utf-8",
        )
        ready_verified = self.run_verify()
        self.assertEqual(
            ready_verified.returncode,
            0,
            ready_verified.stderr,
        )
        target.write_text(
            ready_content.replace(
                "preserve one independently validatable invariant",
                "change the invariant after review",
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.run_verify().returncode, 0)
        target.write_text(ready_content, encoding="utf-8")

        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        checked_path = (
            f"docs/plan/checked/{today.year:04d}/{today.month:02d}/{half}/"
            f"{Path(target_path).name}"
        )
        checked = self.repo / checked_path
        checked.parent.mkdir(parents=True, exist_ok=True)
        checked.write_text(
            ready_content.replace(
                "status: ready_to_archive\n",
                "status: checked\n",
                1,
            ),
            encoding="utf-8",
        )
        target.unlink()
        plan_id = Path(target_path).name[:3]
        active.write_text(
            "".join(
                line
                for line in active.read_text(encoding="utf-8").splitlines(
                    keepends=True
                )
                if not line.startswith(f"{plan_id}\t")
            ),
            encoding="utf-8",
        )
        with (self.repo / "docs/plan/checked.md").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(f"{plan_id}\t{checked_path}\n")
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "complete rebound plan")
        self.assertEqual(self.run_verify().returncode, 0)

    def test_rebound_plan_accepts_canonical_replan_required_state(self) -> None:
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        result = self.run_spec_data(coupled, "replan-state-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_predecessor = self.check_successor(successor_path)
        module = self.load_restructure_module("replan_state_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_predecessor,
            promoted_path=None,
        )
        activated = self.run_spec_data(
            activation,
            "replan-state-activation.json",
        )
        self.assertEqual(activated.returncode, 0, activated.stderr)
        target = self.repo / target_path
        stopped = module.derive_stopped_source_content(
            target.read_text(encoding="utf-8"),
            ["multiple_independent_invariants"],
        )
        self.assertNotIn("completion_deferred_reason:", stopped)
        target.write_text(stopped, encoding="utf-8")
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"{Path(target_path).name[:3]}\t{target_path}\tin_progress",
                f"{Path(target_path).name[:3]}\t{target_path}\treplan_required",
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.run_verify().returncode, 0)

        target.write_text(
            stopped.replace(
                "replan_reason_codes:\n",
                "completion_deferred_reason: stale deferred reason\n"
                "replan_reason_codes:\n",
                1,
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "stale completion_deferred_reason",
            rejected.stderr,
        )
        empty_stale = stopped.replace(
            "replan_reason_codes:\n",
            "completion_deferred_reason:\nreplan_reason_codes:\n",
            1,
        )
        target.write_text(empty_stale, encoding="utf-8")
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "stale completion_deferred_reason",
            rejected.stderr,
        )
        with self.assertRaisesRegex(
            module.RestructureError,
            "stale completion_deferred_reason",
        ):
            module.derive_stopped_source_content(
                empty_stale,
                ["multiple_independent_invariants"],
            )

    def test_schema_three_successor_can_be_replanned_by_schema_three(self) -> None:
        coupled, module, _, successor_path = self.prepare_coupled_spec()
        first = self.run_spec_data(coupled, "first-coupled.json")
        self.assertEqual(first.returncode, 0, first.stderr)
        source = self.repo / successor_path
        original = source.read_text(encoding="utf-8")
        stopped = module.derive_stopped_source_content(
            original,
            ["multiple_independent_invariants"],
        )
        source.write_text(stopped, encoding="utf-8")
        plan_id = Path(successor_path).name[:3]
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"{plan_id}\t{successor_path}\tin_progress",
                f"{plan_id}\t{successor_path}\treplan_required",
            ),
            encoding="utf-8",
        )
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "stop schema three successor")
        records = module.acceptance_records(original)
        next_path = "docs/plan/active/007-recursive-integration.md"
        next_contract = (
            "docs/plan/replanned/contracts/"
            f"{plan_id}-recursive-integration.json"
        )
        next_content, mappings = self.coupled_successor_content(
            path=next_path,
            contract_path=next_contract,
            source_paths=[successor_path],
            source_records=[(plan_id, records)],
            predecessor=None,
        )
        today = date.today()
        half = "01-15" if today.day <= 15 else "16-31"
        recursive = {
            "schema_version": 3,
            "operation": "reconstruct",
            "source_head": git(self.repo, "rev-parse", "HEAD"),
            "sources": [
                {
                    "path": successor_path,
                    "source_kind": "contract_successor",
                    "original_plan_digest": digest(stopped),
                    "stopped_plan_digest": digest(stopped),
                    "acceptance": records,
                    "reason_codes": ["multiple_independent_invariants"],
                    "archive_path": (
                        f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/"
                        f"{half}/{Path(successor_path).name}"
                    ),
                }
            ],
            "dirty_product_paths": [],
            "contract_path": next_contract,
            "successors": [
                {
                    "id": "007",
                    "path": next_path,
                    "content": next_content,
                    "acceptance_mappings": mappings,
                    "integration_source_ids": [plan_id],
                }
            ],
            "prerequisite_plans": [],
            "rebindings": [],
        }
        transitioned = self.run_spec_data(recursive, "recursive-coupled.json")
        self.assertEqual(transitioned.returncode, 0, transitioned.stderr)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_direct_active_sources_reconstruct_without_contract_ownership(self) -> None:
        module = self.load_restructure_module("direct_active_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "direct-active.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract = json.loads(
            (self.repo / str(spec["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [source["source_kind"] for source in contract["sources"]],
            ["direct_active", "direct_active"],
        )
        for source in contract["sources"]:
            self.assertNotIn("source_contract_path", source)
            self.assertNotIn("source_contract_digest", source)
        active = (self.repo / "docs/plan/plan.md").read_text(encoding="utf-8")
        for path in source_paths:
            self.assertFalse((self.repo / path).exists())
            self.assertNotIn(path, active)
            archive = self.repo / str(
                next(
                    source["archive_path"]
                    for source in contract["sources"]
                    if source["path"] == path
                )
            )
            self.assertIn("status: replanned", archive.read_text(encoding="utf-8"))
        self.assertIn("012\t", active)
        self.assertEqual(self.run_verify().returncode, 0)

    def test_mixed_source_routes_share_one_transaction(self) -> None:
        initial = self.run_command()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        module = self.load_restructure_module("mixed_route_module")
        owned = "docs/plan/active/002-data.md"
        owned_file = self.repo / owned
        owned_file.write_text(
            module.derive_stopped_source_content(
                owned_file.read_text(encoding="utf-8"),
                ["multiple_independent_invariants"],
            ),
            encoding="utf-8",
        )
        dependent = "docs/plan/active/010-direct-primary.md"
        (self.repo / dependent).write_text(
            self.direct_source_content(
                title="Direct Dependent",
                acceptance=["Keep the direct dependent requirement."],
                stopped=False,
                predecessor=owned,
            ),
            encoding="utf-8",
        )
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8").replace(
                f"002\t{owned}\tin_progress",
                f"002\t{owned}\treplan_required",
            )
            + f"010\t{dependent}\tdeferred\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "prepare mixed sources")
        spec = self.direct_active_spec(
            module,
            [owned, dependent],
            kinds=["contract_successor", "direct_active"],
            contract_name="002-mixed-routes.json",
        )
        result = self.run_spec_data(spec, "mixed-routes.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract = json.loads(
            (self.repo / str(spec["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [source["source_kind"] for source in contract["sources"]],
            ["contract_successor", "direct_active"],
        )
        self.assertEqual(
            contract["sources"][0]["source_contract_path"],
            str(self.spec["contract_path"]),
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_direct_active_route_rejects_contract_owned_source(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        sources = coupled["sources"]
        assert isinstance(sources, list)
        sources[0]["source_kind"] = "direct_active"  # type: ignore[index]
        result = self.run_spec_data(coupled, "forged-direct.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already claimed by a verified durable contract", result.stderr)

    def test_contract_route_rejects_unowned_active_source(self) -> None:
        module = self.load_restructure_module("unowned_contract_route_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(
            module,
            source_paths,
            kinds=["contract_successor", "direct_active"],
        )
        result = self.run_spec_data(spec, "unowned-contract-route.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not an exact live contract successor", result.stderr)
        self.assertTrue((self.repo / source_paths[0]).is_file())

    def test_direct_active_source_requires_declared_kind(self) -> None:
        module = self.load_restructure_module("missing_kind_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        sources = spec["sources"]
        assert isinstance(sources, list)
        del sources[0]["source_kind"]  # type: ignore[index]
        result = self.run_spec_data(spec, "missing-kind.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sources[0]", result.stderr)

    def test_direct_active_source_rejects_unknown_kind(self) -> None:
        module = self.load_restructure_module("unknown_kind_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(
            module,
            source_paths,
            kinds=["direct_active", "inferred_fallback"],
        )
        result = self.run_spec_data(spec, "unknown-kind.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source_kind must be", result.stderr)

    def test_nonstring_source_kind_fails_with_a_structured_error(self) -> None:
        module = self.load_restructure_module("nonstring_kind_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        sources = spec["sources"]
        assert isinstance(sources, list)
        sources[0]["source_kind"] = {"kind": "direct_active"}  # type: ignore[index]
        rejected = self.run_spec_data(spec, "nonstring-kind.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("plan restructuring failed", rejected.stderr)
        self.assertNotIn("Traceback", rejected.stderr)
        sources[0]["source_kind"] = "direct_active"  # type: ignore[index]
        accepted = self.run_spec_data(spec, "nonstring-kind-fixed.json")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        contract_file = self.repo / str(spec["contract_path"])
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        contract["sources"][0]["source_kind"] = []
        contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertNotEqual(verified.returncode, 0)
        self.assertIn("plan restructuring failed", verified.stderr)
        self.assertNotIn("Traceback", verified.stderr)

    def test_direct_active_source_rejects_missing_dependency(self) -> None:
        module = self.load_restructure_module("unlinked_direct_module")
        source_paths = self.prepare_direct_active_sources(link_dependent=False)
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "unlinked-direct.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not depend on an earlier coupled source", result.stderr)

    def test_direct_active_source_rejects_noncanonical_stopping(self) -> None:
        module = self.load_restructure_module("unstopped_direct_module")
        source_paths = self.prepare_direct_active_sources(stop_primary=False)
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "unstopped-direct.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("first coupled source must already be stopped", result.stderr)

    def test_direct_active_source_rejects_replan_lineage_fields(self) -> None:
        module = self.load_restructure_module("lineage_direct_module")
        source_paths = self.prepare_direct_active_sources(
            lineage_field=(
                "replan_contract: docs/plan/replanned/contracts/001-source.json"
            ),
        )
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "lineage-direct.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("carries replan lineage field: replan_contract", result.stderr)

    def test_direct_active_source_rejects_duplicate_index_rows(self) -> None:
        module = self.load_restructure_module("duplicate_index_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8")
            + f"010\t{source_paths[0]}\treplan_required\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "duplicate active index row")
        spec["source_head"] = git(self.repo, "rev-parse", "HEAD")
        result = self.run_spec_data(spec, "duplicate-index.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must appear exactly once in the active index", result.stderr)

    def test_historical_schema_three_sources_verify_without_discriminant(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        result = self.run_spec_data(coupled, "historical-coupled.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract_file = self.repo / str(coupled["contract_path"])
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        for source in contract["sources"]:
            self.assertEqual(source.pop("source_kind"), "contract_successor")
        contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_durable_verification_rejects_unknown_and_forged_source_kinds(self) -> None:
        module = self.load_restructure_module("durable_kind_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "durable-kind.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract_file = self.repo / str(spec["contract_path"])
        original = json.loads(contract_file.read_text(encoding="utf-8"))
        unknown = copy.deepcopy(original)
        unknown["sources"][0]["source_kind"] = "inferred_fallback"
        contract_file.write_text(
            json.dumps(unknown, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unknown source kind", rejected.stderr)
        forged = copy.deepcopy(original)
        forged["sources"][0]["source_kind"] = "contract_successor"
        contract_file.write_text(
            json.dumps(forged, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        missing_lineage = self.run_verify()
        self.assertNotEqual(missing_lineage.returncode, 0)
        self.assertIn("schema-3 source 0", missing_lineage.stderr)

    def test_durable_verification_rejects_double_claimed_direct_source(self) -> None:
        module = self.load_restructure_module("double_claim_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "double-claim.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract_file = self.repo / str(spec["contract_path"])
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        contract["sources"][1] = copy.deepcopy(contract["sources"][0])
        contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("direct active source is reconstructed twice", rejected.stderr)

    def test_durable_verification_rejects_contract_owned_direct_claim(self) -> None:
        self.test_mixed_source_routes_share_one_transaction()
        contract_file = self.repo / "docs/plan/replanned/contracts/002-mixed-routes.json"
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        owned = contract["sources"][0]
        owned["source_kind"] = "direct_active"
        owned.pop("source_contract_path")
        owned.pop("source_contract_digest")
        contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "direct active source is also a contract successor",
            rejected.stderr,
        )

    def test_durable_verification_rejects_unstopped_first_source(self) -> None:
        module = self.load_restructure_module("durable_unstopped_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "durable-unstopped.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract_file = self.repo / str(spec["contract_path"])
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        unstopped = self.direct_source_content(
            title="Direct Primary",
            acceptance=["Keep the direct primary requirement."],
            stopped=False,
            predecessor=None,
        )
        source = contract["sources"][0]
        source["original_content"] = unstopped
        source["original_plan_digest"] = digest(unstopped)
        stopped = module.derive_stopped_source_content(
            unstopped,
            source["reason_codes"],
        )
        source["stopped_content"] = stopped
        source["stopped_plan_digest"] = digest(stopped)
        contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "first source must already be canonically stopped",
            rejected.stderr,
        )

    def test_schema_three_allows_ordered_prerequisite_chains(self) -> None:
        coupled, _, _, successor_path = self.prepare_coupled_spec(
            include_prerequisite=True
        )
        second_path = "docs/plan/active/007-second-prerequisite.md"
        first_path = "docs/plan/active/005-coupled-prerequisite.md"
        second_content = self.prerequisite_content().replace(
            "# Coupled Prerequisite",
            "# Second Coupled Prerequisite",
            1,
        ).replace(
            "status: in_progress\n",
            "status: deferred\n"
            "completion_deferred_reason: first prerequisite must be checked\n",
            1,
        ).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {first_path}\nprimary_invariant:",
            1,
        )
        coupled["prerequisite_plans"].append(  # type: ignore[union-attr]
            {
                "id": "007",
                "path": second_path,
                "content": second_content,
                "authorization": "parent_owned_prerequisite",
            }
        )
        successor = coupled["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            first_path,
            second_path,
        )
        result = self.run_spec_data(coupled, "prerequisite-chain.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"007\t{second_path}\tdeferred",
            (self.repo / "docs/plan/plan.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_prerequisite_validation_projection_cannot_drift(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec(
            include_prerequisite=True
        )
        result = self.run_spec_data(coupled, "prerequisite-drift.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        prerequisite = (
            self.repo / "docs/plan/active/005-coupled-prerequisite.md"
        )
        original = prerequisite.read_text(encoding="utf-8")
        prerequisite.write_text(
            original.replace(
                "git diff --check",
                "python3 tests/test-plan-restructure.py",
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("validation projection mismatch", rejected.stderr)
        prerequisite.write_text(
            original.replace(
                "- [ ] prepare",
                "- [ ] rewrite prerequisite work",
                1,
            ),
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("live successor lifecycle", rejected.stderr)

    def test_deferred_prerequisite_can_use_checked_activation_overlay(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec(
            include_prerequisite=True
        )
        external_path = "docs/plan/active/099-external-prerequisite.md"
        external = self.repo / external_path
        external.write_text(
            "# External prerequisite\n\n"
            "status: in_progress\n"
            "write_scope:\n  - external/\n",
            encoding="utf-8",
        )
        active = self.repo / "docs/plan/plan.md"
        with active.open("a", encoding="utf-8") as handle:
            handle.write(f"099\t{external_path}\tin_progress\n")
        prerequisite = coupled["prerequisite_plans"][0]  # type: ignore[index]
        prerequisite["content"] = str(prerequisite["content"]).replace(
            "status: in_progress\n",
            "status: deferred\n"
            "completion_deferred_reason: external prerequisite must be checked\n",
            1,
        ).replace(
            "primary_invariant:",
            f"predecessor_plans:\n  - {external_path}\nprimary_invariant:",
            1,
        )
        git(self.repo, "add", "docs/plan")
        git(self.repo, "commit", "-qm", "add external prerequisite")
        coupled["source_head"] = git(self.repo, "rev-parse", "HEAD")
        result = self.run_spec_data(
            coupled,
            "deferred-prerequisite-source.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_external = self.check_successor(external_path)
        module = self.load_restructure_module("prerequisite_activation_module")
        target_path = str(prerequisite["path"])
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=external_path,
            checked_path=checked_external,
            promoted_path=None,
            deferred_reason="external prerequisite must be checked",
        )
        activated = self.run_spec_data(
            activation,
            "deferred-prerequisite-activation.json",
        )
        self.assertEqual(activated.returncode, 0, activated.stderr)
        self.assertIn(
            "status: in_progress",
            (self.repo / target_path).read_text(encoding="utf-8"),
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_reconstruct_and_activation_rebind_kinds_are_phase_bound(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec(include_rebind=True)
        coupled["rebindings"][0]["kind"] = "activation"  # type: ignore[index]
        rejected = self.run_spec_data(coupled, "wrong-reconstruct-kind.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not permitted for this operation", rejected.stderr)

    def test_activation_promotes_checked_product_to_context(self) -> None:
        product = "coupled/generated.txt"
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True,
            promotion_path=product,
        )
        assert target_path
        result = self.run_spec_data(coupled, "coupled-promotion.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(
            successor_path,
            product_path=product,
        )
        module = self.load_restructure_module("promotion_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=product,
        )
        promoted = self.run_spec_data(activation, "promotion.json")
        self.assertEqual(promoted.returncode, 0, promoted.stderr)
        content = (self.repo / target_path).read_text(encoding="utf-8")
        manifest = module.parse_manifest(content)
        self.assertNotIn(product, module.preservation_scope(
            manifest, target_path, required=True
        ))
        self.assertIn(product, module.items(manifest, "context_files"))
        self.assertEqual(self.run_verify().returncode, 0)

    def test_activation_promotion_rejects_nonowner_and_stale_product_bytes(self) -> None:
        product = "config/unowned.txt"
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True,
            promotion_path=product,
        )
        assert target_path
        result = self.run_spec_data(coupled, "unowned-promotion-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(
            successor_path,
            product_path=product,
        )
        module = self.load_restructure_module("unowned_promotion_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=product,
        )
        rejected = self.run_spec_data(activation, "unowned-promotion.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("exact checked producer", rejected.stderr)

    def test_activation_promotion_rejects_stale_product_bytes(self) -> None:
        product = "coupled/stale.txt"
        coupled, _, target_path, successor_path = self.prepare_coupled_spec(
            include_rebind=True,
            promotion_path=product,
        )
        assert target_path
        result = self.run_spec_data(coupled, "stale-promotion-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        checked_path = self.check_successor(
            successor_path,
            product_path=product,
        )
        (self.repo / product).write_text("stale worktree bytes\n", encoding="utf-8")
        module = self.load_restructure_module("stale_promotion_module")
        activation = self.activation_spec(
            module=module,
            target_path=target_path,
            successor_path=successor_path,
            checked_path=checked_path,
            promoted_path=product,
        )
        rejected = self.run_spec_data(activation, "stale-promotion.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("exact checked producer", rejected.stderr)

    def admission_block(
        self,
        conditions: list[str],
        witness: str,
        *,
        evidence_kind: str = "existing_mechanism",
        evidence: str = "Reconstruction preflight already validates successor manifests.",
    ) -> str:
        """Render the numbered-plan admission fields for a created successor."""

        evidence_record = json.dumps(
            {"kind": evidence_kind, "evidence": evidence},
            sort_keys=True,
            separators=(",", ":"),
        )
        witness_lines = "".join(
            "  - "
            + json.dumps(
                {"condition_sha256": digest(item), "witness": witness},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for item in conditions
        )
        return (
            "plan_purpose: implementation\n"
            f"feasibility_evidence:\n  - {evidence_record}\n"
            "completion_conditions:\n"
            + "".join(f"  - {item}\n" for item in conditions)
            + f"completion_witness_map:\n{witness_lines}"
        )

    def schema_four_spec(
        self,
        module,
        source_paths: list[str],
        *,
        authorization: object = "Continue the implementation through the reconstructed successors.",
        admission: str | None = None,
        write_scope: str | None = None,
    ) -> dict[str, object]:
        """Build a schema-4 reconstruction specification from the direct-active route."""

        spec = self.direct_active_spec(module, source_paths)
        spec["schema_version"] = 4
        if authorization is not None:
            spec["owner_continuation_authorization"] = authorization
        successor = spec["successors"][0]  # type: ignore[index]
        conditions = [
            "Refuse a reconstruction successor without owner continuation authorization.",
            "Refuse a successor whose write scope stays inside plan-lifecycle records.",
        ]
        block = self.admission_block(conditions, "git diff --check") if admission is None else admission
        content = str(successor["content"]).replace(
            "focused_validation:\n", block + "focused_validation:\n", 1
        )
        if write_scope is not None:
            content = content.replace("write_scope:\n  - coupled/\n", write_scope, 1)
        successor["content"] = content
        return spec

    def test_schema_four_records_owner_continuation_and_admitted_successors(self) -> None:
        module = self.load_restructure_module("schema_four_module")
        source_paths = self.prepare_direct_active_sources()
        spec = self.schema_four_spec(module, source_paths)
        result = self.run_spec_data(spec, "schema-four.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        contract = json.loads(
            (self.repo / str(spec["contract_path"])).read_text(encoding="utf-8")
        )
        self.assertEqual(contract["schema_version"], 4)
        self.assertEqual(
            contract["owner_continuation_authorization"],
            "Continue the implementation through the reconstructed successors.",
        )
        self.assertEqual(self.run_verify().returncode, 0)

    def test_schema_four_refuses_unauthorized_or_inadmissible_successors(self) -> None:
        module = self.load_restructure_module("schema_four_refusal_module")
        source_paths = self.prepare_direct_active_sources()
        conditions = [
            "Refuse a reconstruction successor without owner continuation authorization.",
            "Refuse a successor whose write scope stays inside plan-lifecycle records.",
        ]
        cases: list[tuple[str, dict[str, object], str]] = [
            (
                "missing authorization",
                {"authorization": None},
                "owner_continuation_authorization",
            ),
            (
                "placeholder authorization",
                {"authorization": "TBD"},
                "owner_continuation_authorization",
            ),
            (
                "non-text authorization",
                {"authorization": 1},
                "owner_continuation_authorization",
            ),
            (
                "missing admission record",
                {"admission": ""},
                "plan_purpose: implementation",
            ),
            (
                "unsupported evidence kind",
                {
                    "admission": self.admission_block(
                        conditions, "git diff --check", evidence_kind="future_plan"
                    )
                },
                "feasibility_evidence",
            ),
            (
                "placeholder evidence",
                {
                    "admission": self.admission_block(
                        conditions, "git diff --check", evidence="TBD"
                    )
                },
                "feasibility_evidence",
            ),
            (
                "undeclared witness",
                {"admission": self.admission_block(conditions, "python3 tests/absent.py")},
                "completion_witness_map",
            ),
            (
                "plan lifecycle only successor",
                {"write_scope": "write_scope:\n  - docs/plan/active/013-record.md\n"},
                "plan-lifecycle-only successor",
            ),
        ]
        for index, (label, overrides, fragment) in enumerate(cases, start=1):
            with self.subTest(case=label):
                spec = self.schema_four_spec(module, source_paths, **overrides)
                rejected = self.run_spec_data(spec, f"schema-four-refusal-{index}.json")
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn(fragment, rejected.stderr)
                for path in source_paths:
                    self.assertTrue((self.repo / path).is_file())
                self.assertFalse((self.repo / str(spec["contract_path"])).exists())

    def test_schema_three_rejects_partial_sources_and_duplicate_integrations(self) -> None:
        coupled, _, _, successor_path = self.prepare_coupled_spec()
        partial = copy.deepcopy(coupled)
        partial["sources"] = partial["sources"][:1]  # type: ignore[index]
        rejected = self.run_spec_data(partial, "partial-source.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unknown source", rejected.stderr)

        duplicate = copy.deepcopy(coupled)
        second_path = "docs/plan/active/007-duplicate-integration.md"
        first_successor = duplicate["successors"][0]  # type: ignore[index]
        second = copy.deepcopy(first_successor)
        second["id"] = "007"
        second["path"] = second_path
        old_successors = f"successor_plans:\n  - {successor_path}\n"
        new_successors = (
            "successor_plans:\n"
            f"  - {successor_path}\n"
            f"  - {second_path}\n"
        )
        first_successor["content"] = str(first_successor["content"]).replace(
            old_successors,
            new_successors,
        )
        second["content"] = str(second["content"]).replace(
            old_successors,
            new_successors,
        )
        duplicate["successors"].append(second)  # type: ignore[union-attr]
        rejected = self.run_spec_data(duplicate, "duplicate-integration.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("exactly one integration successor", rejected.stderr)

    def test_schema_three_rejects_invalid_integration_source_mappings(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        integration = coupled["successors"][0]  # type: ignore[index]
        mapping = next(
            mapping
            for mapping in integration["acceptance_mappings"]
            if len(mapping["acceptance_digests"]) > 1
        )
        mapping_index = integration["acceptance_mappings"].index(mapping)
        original = list(mapping["acceptance_digests"])

        cases = (
            (
                "partial",
                original[1:],
                "integration successor does not map every acceptance",
            ),
            (
                "reordered",
                list(reversed(original)),
                "must preserve source order",
            ),
            (
                "duplicate",
                [*original, original[-1]],
                "invalid source acceptance mapping",
            ),
            (
                "foreign",
                [original[0], "sha256:" + "f" * 64],
                "invalid source acceptance mapping",
            ),
        )
        for label, digests, message in cases:
            with self.subTest(label=label):
                mutated = copy.deepcopy(coupled)
                mutated["successors"][0]["acceptance_mappings"][mapping_index][  # type: ignore[index]
                    "acceptance_digests"
                ] = digests
                rejected = self.run_spec_data(
                    mutated,
                    f"invalid-integration-{label}.json",
                )
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn(message, rejected.stderr)

    def test_schema_three_rejects_aggregate_only_integration_coverage(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        source_id, missing_digest = self.add_aggregate_coverage_successor(coupled)
        integration = coupled["successors"][0]  # type: ignore[index]
        integration_mapping = next(
            mapping
            for mapping in integration["acceptance_mappings"]
            if mapping["source_id"] == source_id
        )
        integration_mapping["acceptance_digests"].remove(missing_digest)

        rejected = self.run_spec_data(
            coupled,
            "aggregate-only-integration.json",
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            f"integration successor does not map every acceptance for source {source_id}",
            rejected.stderr,
        )

    def test_durable_schema_three_rejects_aggregate_only_coverage(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        source_id, missing_digest = self.add_aggregate_coverage_successor(coupled)
        result = self.run_spec_data(coupled, "durable-aggregate-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_verify().returncode, 0)

        contract_path = self.repo / str(coupled["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        integration = contract["successors"][0]
        integration_mapping = next(
            mapping
            for mapping in integration["acceptance_mappings"]
            if mapping["source_id"] == source_id
        )
        integration_mapping["acceptance_digests"].remove(missing_digest)
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )

        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            f"integration successor does not map every acceptance for source {source_id}",
            rejected.stderr,
        )

    def test_rebind_rejects_protected_and_weakening_changes(self) -> None:
        coupled, _, target_path, _ = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        protected = copy.deepcopy(coupled)
        rebind = protected["rebindings"][0]  # type: ignore[index]
        original = (self.repo / target_path).read_text(encoding="utf-8")
        updated = original.replace("write_scope:\n  - src/", "write_scope:\n  - other/")
        rebind["updated_content_digest"] = digest(updated)
        rebind["replacements"] = [
            {
                "scope": "manifest",
                "field": "write_scope",
                "old": "  - src/\n",
                "new": "  - other/\n",
                "count": 1,
            }
        ]
        rejected = self.run_spec_data(protected, "protected-rebind.json")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unauthorized field", rejected.stderr)

        weakening = copy.deepcopy(coupled)
        rebind = weakening["rebindings"][0]  # type: ignore[index]
        updated = original.replace("validation:\n  - git diff --check\n", "validation:\n")
        rebind["updated_content_digest"] = digest(updated)
        rebind["replacements"] = [
            {
                "scope": "manifest",
                "field": "validation",
                "old": "  - git diff --check\n",
                "new": "",
                "count": 1,
            }
        ]
        rejected = self.run_spec_data(weakening, "weakening-rebind.json")
        self.assertNotEqual(rejected.returncode, 0)

    def test_rebind_baseline_fork_is_rejected(self) -> None:
        coupled, module, _, _ = self.prepare_coupled_spec(include_rebind=True)
        result = self.run_spec_data(coupled, "fork-source.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        baseline_path = (
            self.repo
            / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
        )
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        fork = copy.deepcopy(baseline["records"][0])
        fork["transaction_id"] = digest("fork")
        fork["record_digest"] = module.canonical_digest(
            {key: value for key, value in fork.items() if key != "record_digest"}
        )
        baseline["records"].append(fork)
        baseline_path.write_text(
            json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        rejected = self.run_verify()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("gap or fork", rejected.stderr)

    def test_rebind_admits_legacy_contract_successor_without_preservation_baseline(
        self,
    ) -> None:
        coupled, _module, target_path, _ = self.prepare_coupled_spec(
            include_rebind=True
        )
        assert target_path
        contract_path = self.repo / str(self.spec["contract_path"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["schema_version"] = 1
        contract["dirty_product_paths"] = []
        converted = False
        for successor in contract["successors"]:
            for key in (
                "authoritative_validation",
                "authoritative_validation_digest",
                "validation_witness_schema",
                "validation_witness_map_digest",
            ):
                successor.pop(key, None)
            if successor["path"] == target_path:
                successor["content"] = successor["content"].replace(
                    "preservation_scope:\n  - none\n", "", 1
                )
                successor["content_digest"] = digest(successor["content"])
                converted = True
        self.assertTrue(converted)
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertIn(
            "preservation_scope:\n  - none\n",
            (self.repo / target_path).read_text(encoding="utf-8"),
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "convert owning contract to schema one")
        coupled["source_head"] = git(self.repo, "rev-parse", "HEAD")
        result = self.run_spec_data(coupled, "legacy-contract-rebind.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        verified = self.run_verify()
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_contract_identity_ignores_only_the_declared_field(self) -> None:
        module = self.load_restructure_module("contract_identity_module")
        base = {"preservation_scope": ["none"], "write_scope": ["src/"]}
        preservation_drift = {
            "preservation_scope": ["config/project-owned.yaml"],
            "write_scope": ["src/"],
        }
        with self.assertRaises(module.RestructureError):
            module.compare_contract_identity(preservation_drift, base, "identity")
        module.compare_contract_identity(
            preservation_drift,
            base,
            "identity",
            ignore_fields=frozenset({"preservation_scope"}),
        )
        scope_drift = {
            "preservation_scope": ["config/project-owned.yaml"],
            "write_scope": ["other/"],
        }
        with self.assertRaises(module.RestructureError):
            module.compare_contract_identity(
                scope_drift,
                base,
                "identity",
                ignore_fields=frozenset({"preservation_scope"}),
            )

    def journal_directory(self) -> Path:
        raw = git(
            self.repo,
            "rev-parse",
            "--git-path",
            "project-agent-workflow/restructure-journals",
        )
        directory = Path(raw)
        if not directory.is_absolute():
            directory = self.repo / directory
        return directory

    def journal_path(self) -> Path:
        directory = self.journal_directory()
        journals = list(directory.glob("*.json"))
        self.assertEqual(len(journals), 1)
        return journals[0]

    def test_crash_recovery_rolls_back_each_precommit_phase_and_rolls_forward(self) -> None:
        module = self.load_restructure_module("crash_recovery_module")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            for phase in ("after_journal", "after_temps", "after_operation_1"):
                with self.subTest(phase=phase):
                    with self.assertRaises(module.SimulatedCrash):
                        module.execute(self.spec_path, crash_phase=phase)
                    journal = self.journal_path()
                    payload = json.loads(journal.read_text(encoding="utf-8"))
                    self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
                    module.recover_transaction(
                        journal,
                        payload["journal_identity"],
                    )
                    self.assert_source_unchanged()
                    self.assertEqual(
                        json.loads(journal.read_text(encoding="utf-8"))["phase"],
                        "rolled_back",
                    )
                    journal.unlink()
            state = module.validate_spec(copy.deepcopy(self.spec))
            operations, _ = module.build_transaction_operations(state)
            with self.assertRaises(module.SimulatedCrash):
                module.execute(
                    self.spec_path,
                    crash_phase=f"after_operation_{len(operations)}",
                )
            journal = self.journal_path()
            payload = json.loads(journal.read_text(encoding="utf-8"))
            with self.assertRaises(module.SimulatedCrash):
                module.recover_transaction(
                    journal,
                    payload["journal_identity"],
                    crash_phase="rollback_after_operation_1",
                )
            interrupted_rollback = json.loads(
                journal.read_text(encoding="utf-8")
            )
            self.assertEqual(interrupted_rollback["phase"], "rolling_back")
            self.assertEqual(interrupted_rollback["next_operation"], 1)
            module.recover_transaction(
                journal,
                payload["journal_identity"],
            )
            self.assert_source_unchanged()
            self.assertEqual(
                json.loads(journal.read_text(encoding="utf-8"))["phase"],
                "rolled_back",
            )
            journal.unlink()
            with self.assertRaises(module.SimulatedCrash):
                module.execute(
                    self.spec_path,
                    crash_phase="after_commit_point",
                )
            journal = self.journal_path()
            payload = json.loads(journal.read_text(encoding="utf-8"))
            with self.assertRaises(module.SimulatedCrash):
                module.recover_transaction(
                    journal,
                    payload["journal_identity"],
                    crash_phase="replay_after_operation_1",
                )
            replay = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(replay["phase"], "replaying")
            module.recover_transaction(journal, payload["journal_identity"])
        finally:
            os.chdir(old_cwd)
        self.assertFalse((self.repo / self.source_path).exists())
        self.assertEqual(self.run_verify().returncode, 0)

    def test_recovery_rejects_replaced_transaction_file_identity(self) -> None:
        module = self.load_restructure_module("identity_recovery_module")
        old_cwd = Path.cwd()

        def swap_inode(path: Path) -> None:
            data = path.read_bytes()
            mode = path.stat().st_mode & 0o777
            replacement = path.with_name(path.name + ".swap")
            replacement.write_bytes(data)
            os.chmod(replacement, mode)
            os.replace(replacement, path)

        def replacing_operation(payload: dict, *, unsnapshotted: bool = False) -> dict:
            snapshotted = {
                entry["path"] for entry in payload["historical_contract_snapshot"]
            }
            for operation in payload["operations"]:
                if (
                    operation["target_content"] is not None
                    and operation["original_digest"] != operation["target_digest"]
                    and not (unsnapshotted and operation["path"] in snapshotted)
                ):
                    return operation
            self.fail("no content-replacing operation in the transaction")

        def crash_at(phase: str) -> tuple[Path, dict]:
            with self.assertRaises(module.SimulatedCrash):
                module.execute(self.spec_path, crash_phase=phase)
            journal = self.journal_path()
            return journal, json.loads(journal.read_text(encoding="utf-8"))

        def reset_repository(journal: Path, payload: dict) -> None:
            journal.unlink()
            for entry in payload["operations"]:
                (self.repo / entry["temporary_path"]).unlink(missing_ok=True)
            git(self.repo, "checkout", "-q", "--", ".")
            git(self.repo, "clean", "-qfdx", "--", "docs")

        def expect_rejected(journal: Path, payload: dict, fragment: str) -> None:
            with self.assertRaises(module.RestructureError) as raised:
                module.recover_transaction(journal, payload["journal_identity"])
            self.assertIn(fragment, str(raised.exception))

        try:
            os.chdir(self.repo)
            for case, mutate, fragment in (
                (
                    "temp inode swap",
                    lambda path: swap_inode(path),
                    "identity was externally replaced",
                ),
                (
                    "temp mode drift",
                    lambda path: os.chmod(path, 0o600),
                    "identity was externally replaced",
                ),
                (
                    "temp removal",
                    lambda path: path.unlink(),
                    "identity is absent from disk",
                ),
            ):
                with self.subTest(case=case):
                    journal, payload = crash_at("after_temps")
                    self.assertEqual(payload["phase"], "temps_prepared")
                    operation = replacing_operation(payload)
                    self.assertIsNotNone(
                        payload["replacement_identities"][
                            payload["operations"].index(operation)
                        ]["temporary"]
                    )
                    mutate(self.repo / operation["temporary_path"])
                    expect_rejected(journal, payload, fragment)
                    reset_repository(journal, payload)
                    self.assert_source_unchanged()

            for case, mutate, fragment in (
                (
                    "post-rename same-content inode swap",
                    lambda path: swap_inode(path),
                    "identity was externally replaced",
                ),
                (
                    "post-rename mode drift",
                    lambda path: os.chmod(path, 0o600),
                    "identity was externally replaced",
                ),
            ):
                with self.subTest(case=case):
                    journal, payload = crash_at("after_commit_point")
                    self.assertEqual(payload["phase"], "commit_point")
                    operation = replacing_operation(payload, unsnapshotted=True)
                    self.assertNotIn(
                        operation["path"],
                        {
                            entry["path"]
                            for entry in payload["historical_contract_snapshot"]
                        },
                    )
                    target = self.repo / operation["path"]
                    before = target.stat()
                    mutate(target)
                    expect_rejected(journal, payload, fragment)
                    after = target.stat()
                    self.assertEqual(
                        target.read_bytes(),
                        operation["target_content"].encode("utf-8"),
                    )
                    self.assertNotEqual(
                        (before.st_ino, before.st_mode),
                        (after.st_ino, after.st_mode),
                    )
                    reset_repository(journal, payload)

            journal, payload = crash_at("after_commit_point")
            with self.assertRaises(module.SimulatedCrash):
                module.recover_transaction(
                    journal,
                    payload["journal_identity"],
                    crash_phase="replay_after_operation_1",
                )
            replaying = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(replaying["phase"], "replaying")
            self.assertLess(0, replaying["next_operation"])
            self.assertLess(
                replaying["next_operation"], len(replaying["operations"])
            )
            swap_inode(
                self.repo / replacing_operation(payload, unsnapshotted=True)["path"]
            )
            expect_rejected(journal, payload, "identity was externally replaced")
            stopped = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(stopped["phase"], "replaying")
            self.assertEqual(
                stopped["next_operation"], replaying["next_operation"]
            )
            reset_repository(journal, payload)

            state = module.validate_spec(copy.deepcopy(self.spec))
            operations, _ = module.build_transaction_operations(state)
            journal, payload = crash_at(f"after_operation_{len(operations)}")
            with self.assertRaises(module.SimulatedCrash):
                module.recover_transaction(
                    journal,
                    payload["journal_identity"],
                    crash_phase="rollback_after_operation_1",
                )
            interrupted = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(interrupted["phase"], "rolling_back")
            restored = [
                index
                for index, entry in enumerate(interrupted["replacement_identities"])
                if entry["restored"] is not None
            ]
            self.assertTrue(restored)
            target = self.repo / interrupted["operations"][restored[0]]["path"]
            swap_inode(target)
            with self.assertRaises(module.RestructureError) as raised:
                module.recover_transaction(journal, payload["journal_identity"])
            self.assertIn(
                "restored transaction target", str(raised.exception)
            )
            self.assertIn("identity was externally replaced", str(raised.exception))
            reset_repository(journal, payload)
        finally:
            os.chdir(old_cwd)

    def test_transaction_rejects_unsafe_target_modes_before_the_journal(self) -> None:
        module = self.load_restructure_module("target_mode_module")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            for case, mode in (
                ("setgid", 0o2644),
                ("setuid", 0o4644),
                ("sticky", 0o1644),
            ):
                with self.subTest(case=case):
                    os.chmod(self.repo / self.source_path, mode)
                    with self.assertRaises(module.RestructureError) as raised:
                        module.execute(self.spec_path)
                    self.assertIn(
                        "transaction path has an unsafe file mode",
                        str(raised.exception),
                    )
                    self.assertEqual(
                        list(self.journal_directory().glob("*.json")), []
                    )
            os.chmod(self.repo / self.source_path, 0o644)
        finally:
            os.chdir(old_cwd)
        self.assert_source_unchanged()
        self.assertEqual(self.run_verify().returncode, 0)

    def test_recovery_rejects_stale_head_stale_content_and_hardlinked_journal(self) -> None:
        module = self.load_restructure_module("recovery_rejection_module")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            with self.assertRaises(module.SimulatedCrash):
                module.execute(self.spec_path, crash_phase="after_journal")
            journal = self.journal_path()
            payload = json.loads(journal.read_text(encoding="utf-8"))
            hardlink = journal.with_suffix(".hardlink")
            os.link(journal, hardlink)
            with self.assertRaises(module.RestructureError):
                module.recover_transaction(journal, payload["journal_identity"])
            hardlink.unlink()
            git(self.repo, "commit", "--allow-empty", "-qm", "advance head")
            with self.assertRaises(module.RestructureError):
                module.recover_transaction(journal, payload["journal_identity"])
        finally:
            os.chdir(old_cwd)

        stale_repo = self.base / "stale-content"
        subprocess.run(["git", "clone", "-q", str(self.repo), str(stale_repo)], check=True)
        git(stale_repo, "config", "user.name", "Test")
        git(stale_repo, "config", "user.email", "test@example.invalid")
        stale_spec = copy.deepcopy(self.spec)
        stale_spec["source"]["head"] = git(stale_repo, "rev-parse", "HEAD")  # type: ignore[index]
        stale_path = self.base / "stale-content.json"
        stale_path.write_text(
            json.dumps(stale_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        old_cwd = Path.cwd()
        try:
            os.chdir(stale_repo)
            spec = importlib.util.spec_from_file_location(
                "stale_content_module",
                stale_repo / "scripts/restructure-plan.py",
            )
            assert spec and spec.loader
            stale_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(stale_module)
            with self.assertRaises(stale_module.SimulatedCrash):
                stale_module.execute(stale_path, crash_phase="after_operation_1")
            raw = git(
                stale_repo,
                "rev-parse",
                "--git-path",
                "project-agent-workflow/restructure-journals",
            )
            directory = Path(raw)
            if not directory.is_absolute():
                directory = stale_repo / directory
            journal = next(directory.glob("*.json"))
            payload = json.loads(journal.read_text(encoding="utf-8"))
            changed = stale_repo / payload["operations"][0]["path"]
            changed.write_text("stale\n", encoding="utf-8")
            with self.assertRaises(stale_module.RestructureError):
                stale_module.recover_transaction(
                    journal,
                    payload["journal_identity"],
                )
        finally:
            os.chdir(old_cwd)

    def test_recovery_rejects_historical_contract_mutation(self) -> None:
        coupled, _, _, _ = self.prepare_coupled_spec()
        coupled_path = self.base / "historical-recovery.json"
        coupled_path.write_text(
            json.dumps(
                coupled,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        module = self.load_restructure_module("historical_recovery_module")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            with self.assertRaises(module.SimulatedCrash):
                module.execute(coupled_path, crash_phase="after_journal")
            raw = git(
                self.repo,
                "rev-parse",
                "--git-path",
                "project-agent-workflow/restructure-journals",
            )
            directory = Path(raw)
            if not directory.is_absolute():
                directory = self.repo / directory
            journal_payloads = [
                (path, json.loads(path.read_text(encoding="utf-8")))
                for path in directory.glob("*.json")
            ]
            journal, payload = next(
                (path, value)
                for path, value in journal_payloads
                if value["phase"] == "prepared"
            )
            self.assertTrue(payload["historical_contract_snapshot"])
            self.assertIn(
                "docs/plan/replanned.md",
                {
                    entry["path"]
                    for entry in payload["historical_contract_snapshot"]
                },
            )
            historical = self.repo / next(
                entry["path"]
                for entry in payload["historical_contract_snapshot"]
                if entry["path"] != "docs/plan/replanned.md"
            )
            historical.write_bytes(historical.read_bytes() + b"\n")
            with self.assertRaisesRegex(
                module.RestructureError,
                "historical contract or archive|replanned plan index",
            ):
                module.recover_transaction(
                    journal,
                    payload["journal_identity"],
                )
        finally:
            os.chdir(old_cwd)

    def test_schema_one_preflight_rejects_corrupt_repository_before_journal(self) -> None:
        baseline = (
            self.repo
            / "docs/plan/replanned/baselines/live-successor-rebinds-v1.json"
        )
        baseline.parent.mkdir(parents=True)
        baseline.write_text('{"schema_version":1,"records":"invalid"}\n', encoding="utf-8")
        rejected = self.run_command()
        self.assertNotEqual(rejected.returncode, 0)
        self.assert_source_unchanged()
        raw = git(
            self.repo,
            "rev-parse",
            "--git-path",
            "project-agent-workflow/restructure-journals",
        )
        journal_dir = Path(raw)
        if not journal_dir.is_absolute():
            journal_dir = self.repo / journal_dir
        self.assertFalse(journal_dir.exists())

    def test_transaction_rechecks_exact_dirty_candidate_snapshot(self) -> None:
        candidate_path = "candidate/preserved.txt"
        candidate = self.repo / candidate_path
        candidate.parent.mkdir()
        candidate.write_text("candidate one\n", encoding="utf-8")
        self.spec["dirty_product_paths"] = [candidate_path]
        successor = self.spec["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            "preservation_scope:\n  - none\n",
            f"preservation_scope:\n  - {candidate_path}\n",
            1,
        )
        self.write_spec()
        module = self.load_restructure_module("dirty_snapshot_module")
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            state = module.validate_spec(copy.deepcopy(self.spec))
            operations, _ = module.build_transaction_operations(state)
            candidate.write_text("candidate two\n", encoding="utf-8")
            with self.assertRaisesRegex(
                module.RestructureError,
                "dirty product candidates changed",
            ):
                module.require_transaction_repository_state(
                    state,
                    operations,
                    targets_written=False,
                )
        finally:
            os.chdir(old_cwd)

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

    def test_transaction_rejects_orphaning_an_unaffected_predecessor_edge(self) -> None:
        module = self.load_restructure_module("orphan_predecessor_module")
        source_paths = self.prepare_direct_active_sources()
        dependent = "docs/plan/active/013-unaffected-dependent.md"
        (self.repo / dependent).write_text(
            self.direct_source_content(
                title="Unaffected Dependent",
                acceptance=["Keep the unaffected downstream requirement."],
                stopped=False,
                predecessor=source_paths[0],
            ),
            encoding="utf-8",
        )
        active = self.repo / "docs/plan/plan.md"
        active.write_text(
            active.read_text(encoding="utf-8") + f"013\t{dependent}\tdeferred\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "add unaffected dependent plan")
        spec = self.direct_active_spec(module, source_paths)
        result = self.run_spec_data(spec, "orphan-predecessor.json")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            f"{dependent} predecessor is missing: {source_paths[0]}",
            result.stderr,
        )
        self.assertEqual(list(self.journal_directory().glob("*.json")), [])
        for path in source_paths:
            self.assertTrue((self.repo / path).is_file())
        self.assertFalse((self.repo / str(spec["contract_path"])).exists())
        self.assertEqual(self.run_verify().returncode, 0)

    def test_rejected_coupled_transaction_leaves_no_mutation_or_journal(self) -> None:
        module = self.load_restructure_module("rejected_coupled_module")
        source_paths = self.prepare_direct_active_sources()
        before = {
            path: (self.repo / path).read_text(encoding="utf-8")
            for path in (
                *source_paths,
                "docs/plan/plan.md",
                "docs/plan/replanned.md",
                "docs/plan/checked.md",
            )
        }
        head = git(self.repo, "rev-parse", "HEAD")
        spec = self.direct_active_spec(module, source_paths)
        successor = spec["successors"][0]  # type: ignore[index]
        successor["content"] = str(successor["content"]).replace(
            "write_scope:\n  - coupled/\n",
            "write_scope:\n  - coupled/\n  - coupled/\n",
            1,
        )
        result = self.run_spec_data(spec, "rejected-coupled.json")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("write_scope must contain unique normalized relative paths", result.stderr)
        self.assertEqual(list(self.journal_directory().glob("*.json")), [])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(
            [
                line
                for line in git(self.repo, "status", "--porcelain").splitlines()
                if ".agent-artifacts/" not in line
            ],
            [],
        )
        for path, content in before.items():
            self.assertEqual((self.repo / path).read_text(encoding="utf-8"), content, path)
        self.assertFalse((self.repo / str(spec["contract_path"])).exists())
        self.assertFalse((self.repo / str(successor["path"])).exists())
        self.assertEqual(self.run_verify().returncode, 0)

    def prepare_replanned_source_with_checked_successor(
        self, label: str
    ) -> tuple[object, str, str]:
        """Replan the source and archive its first successor as a committed state."""
        self.assertEqual(self.run_command().returncode, 0)
        successor_path = "docs/plan/active/002-data.md"
        checked_path = self.check_successor(successor_path)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        return self.load_restructure_module(label), successor_path, checked_path

    def write_pre_boundary_registry(
        self,
        module,
        entries: list[dict[str, str]],
        boundary: str,
    ) -> Path:
        path = self.repo / module.PRE_BOUNDARY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "boundary_commit": boundary,
                    "reconciliations": entries,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_pre_boundary_registry_admits_only_frozen_committed_archives(self) -> None:
        module, successor_path, checked_path = (
            self.prepare_replanned_source_with_checked_successor("pre_boundary_module")
        )
        boundary = git(self.repo, "rev-parse", "HEAD")
        archive = self.repo / checked_path
        archive_bytes = archive.read_bytes()
        entry = {
            "plan_path": successor_path,
            "baseline_digest": digest(b"deferred baseline"),
            "archive_path": checked_path,
            "archive_digest": digest(archive_bytes),
            "reason": "archived before the activation record was enforced",
        }
        registry = self.write_pre_boundary_registry(module, [entry], boundary)
        loaded = module.load_pre_boundary_reconciliations()
        self.assertEqual(loaded[successor_path]["archive_path"], checked_path)
        archive.write_bytes(archive_bytes + b"\ndrift\n")
        with self.assertRaises(module.RestructureError) as drifted:
            module.load_pre_boundary_reconciliations()
        self.assertIn("archive bytes changed", str(drifted.exception))
        archive.write_bytes(archive_bytes)
        self.write_pre_boundary_registry(
            module, [entry], git(self.repo, "rev-parse", "HEAD~1")
        )
        with self.assertRaises(module.RestructureError) as early:
            module.load_pre_boundary_reconciliations()
        self.assertIn("not committed before the boundary", str(early.exception))
        self.write_pre_boundary_registry(module, [entry], boundary)
        (self.repo / successor_path).write_text("status: deferred\n", encoding="utf-8")
        with self.assertRaises(module.RestructureError) as live:
            module.load_pre_boundary_reconciliations()
        self.assertIn("still live at its active path", str(live.exception))
        (self.repo / successor_path).unlink()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "record the reconciliation registry")
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                "activation record", "activation  record", 1
            ),
            encoding="utf-8",
        )
        with self.assertRaises(module.RestructureError) as rewritten:
            module.load_pre_boundary_reconciliations()
        self.assertIn("not write-once", str(rewritten.exception))

    def test_pre_boundary_reconciliation_binds_the_baseline_and_archive(self) -> None:
        module, successor_path, checked_path = (
            self.prepare_replanned_source_with_checked_successor("pre_boundary_bind")
        )
        archive_bytes = (self.repo / checked_path).read_bytes()
        baseline = "status: deferred\n"
        self.write_pre_boundary_registry(
            module,
            [
                {
                    "plan_path": successor_path,
                    "baseline_digest": digest(baseline),
                    "archive_path": checked_path,
                    "archive_digest": digest(archive_bytes),
                    "reason": "archived before the activation record was enforced",
                }
            ],
            git(self.repo, "rev-parse", "HEAD"),
        )
        reconciliations = module.load_pre_boundary_reconciliations()
        state = {
            "lifecycle": "checked",
            "live_path": checked_path,
            "live_content": archive_bytes.decode("utf-8"),
        }
        self.assertTrue(
            module.reconciled_pre_boundary_archive(
                reconciliations, successor_path, baseline, state
            )
        )
        self.assertFalse(
            module.reconciled_pre_boundary_archive(
                reconciliations, "docs/plan/active/404-other.md", baseline, state
            )
        )
        with self.assertRaises(module.RestructureError) as mismatched:
            module.reconciled_pre_boundary_archive(
                reconciliations, successor_path, "status: in_progress\n", state
            )
        self.assertIn("baseline digest mismatch", str(mismatched.exception))
        with self.assertRaises(module.RestructureError) as relocated:
            module.reconciled_pre_boundary_archive(
                reconciliations,
                successor_path,
                baseline,
                {**state, "lifecycle": "active", "live_path": successor_path},
            )
        self.assertIn("does not describe the live archive", str(relocated.exception))

    def test_lineage_rebinding_admits_only_checked_successors_of_that_source(
        self,
    ) -> None:
        module, _, checked_path = (
            self.prepare_replanned_source_with_checked_successor("lineage_module")
        )
        self.assertEqual(
            module.replan_lineage_pairs(), {self.source_path: {checked_path}}
        )
        before = {
            "status": "backlog",
            "predecessor_plans": [self.source_path],
            "write_scope": ["docs/agent/spec-index.yaml"],
        }
        after = {**before, "predecessor_plans": [checked_path]}
        accepted = [
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": f"  - {self.source_path}\n",
                "new": f"  - {checked_path}\n",
                "count": 1,
            },
            {
                "scope": "body",
                "field": "body",
                "old": "Plan 001 acceptance",
                "new": "Plan 002 acceptance",
                "count": 1,
            },
        ]
        module.validate_lineage_reference_transition(
            before, after, accepted, "lineage"
        )
        unrelated = copy.deepcopy(accepted)
        unrelated[0]["new"] = "  - docs/plan/checked/2020/01/01-15/099-other.md\n"
        with self.assertRaises(module.RestructureError) as target:
            module.validate_lineage_reference_transition(
                before, after, unrelated, "lineage"
            )
        self.assertIn("checked successor of that source", str(target.exception))
        unadmitted = copy.deepcopy(accepted)
        unadmitted[1]["new"] = "Plan 099 acceptance"
        with self.assertRaises(module.RestructureError) as identifier:
            module.validate_lineage_reference_transition(
                before, after, unadmitted, "lineage"
            )
        self.assertIn("restate one replanned source", str(identifier.exception))
        with self.assertRaises(module.RestructureError) as protected:
            module.validate_lineage_reference_transition(
                before,
                {**after, "write_scope": ["docs/agent/other.md"]},
                accepted,
                "lineage",
            )
        self.assertIn("protected plan identity", str(protected.exception))
        with self.assertRaises(module.RestructureError) as started:
            module.validate_lineage_reference_transition(
                {**before, "status": "in_progress"},
                {**after, "status": "in_progress"},
                accepted,
                "lineage",
            )
        self.assertIn("requires an unstarted plan", str(started.exception))

    def test_lineage_rebinding_admits_a_checked_archive_of_the_same_plan(
        self,
    ) -> None:
        """A backlog successor cannot reach an activation record, so it rebinds here."""

        module, successor_path, checked_path = (
            self.prepare_replanned_source_with_checked_successor("checked_lineage")
        )
        self.assertEqual(
            module.activation_checked_pairs().get(successor_path), checked_path
        )
        self.assertNotIn(successor_path, module.replan_lineage_pairs())
        before = {
            "status": "backlog",
            "predecessor_plans": [successor_path],
            "write_scope": ["docs/agent/spec-index.yaml"],
        }
        after = {**before, "predecessor_plans": [checked_path]}
        accepted = [
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": f"  - {successor_path}\n",
                "new": f"  - {checked_path}\n",
                "count": 1,
            }
        ]
        module.validate_lineage_reference_transition(
            before, after, accepted, "lineage"
        )

        wrong = copy.deepcopy(accepted)
        wrong[0]["new"] = "  - docs/plan/checked/2020/01/01-15/099-other.md\n"
        with self.assertRaises(module.RestructureError) as target:
            module.validate_lineage_reference_transition(
                before, after, wrong, "lineage"
            )
        self.assertIn("restate that reference as its checked archive", str(target.exception))

        absent = copy.deepcopy(accepted)
        absent[0]["old"] = "  - docs/plan/active/099-absent.md\n"
        with self.assertRaises(module.RestructureError) as missing:
            module.validate_lineage_reference_transition(
                before, after, absent, "lineage"
            )
        self.assertIn("names no checked archive", str(missing.exception))

        paired = copy.deepcopy(accepted)
        paired[0]["old"] = f"  - {successor_path}\n  - {self.source_path}\n"
        with self.assertRaises(module.RestructureError) as several:
            module.validate_lineage_reference_transition(
                before, after, paired, "lineage"
            )
        self.assertIn("exactly one unresolvable reference", str(several.exception))

        with mock.patch.object(
            module,
            "replan_lineage_pairs",
            return_value={successor_path: {checked_path}},
        ):
            with self.assertRaises(module.RestructureError) as both:
                module.validate_lineage_reference_transition(
                    before, after, accepted, "lineage"
                )
        self.assertIn("both a replanned source and a checked archive", str(both.exception))

        resident = self.repo / successor_path
        resident.parent.mkdir(parents=True, exist_ok=True)
        resident.write_text("# resident\n", encoding="utf-8")
        try:
            with self.assertRaises(module.RestructureError) as live:
                module.validate_lineage_reference_transition(
                    before, after, accepted, "lineage"
                )
        finally:
            resident.unlink()
        self.assertIn("still resolves", str(live.exception))

        with self.assertRaises(module.RestructureError) as started:
            module.validate_lineage_reference_transition(
                {**before, "status": "in_progress"},
                {**after, "status": "in_progress"},
                accepted,
                "lineage",
            )
        self.assertIn("requires an unstarted plan", str(started.exception))

        repeated = [
            {
                "scope": "manifest",
                "field": "context_files",
                "old": f"  - {successor_path}\n  - {successor_path}\n",
                "new": f"  - {checked_path}\n  - {checked_path}\n",
                "count": 1,
            }
        ]
        module.validate_lineage_reference_transition(
            before, after, repeated, "lineage"
        )
        partial = copy.deepcopy(repeated)
        partial[0]["new"] = f"  - {checked_path}\n  - {successor_path}\n"
        with self.assertRaises(module.RestructureError) as half_moved:
            module.validate_lineage_reference_transition(
                before, after, partial, "lineage"
            )
        self.assertIn(
            "restate that reference as its checked archive", str(half_moved.exception)
        )

        longer = copy.deepcopy(accepted)
        longer[0]["old"] = f"  - {successor_path}.bak\n"
        longer[0]["new"] = f"  - {checked_path}.bak\n"
        with self.assertRaises(module.RestructureError) as token:
            module.validate_lineage_reference_transition(
                before, after, longer, "lineage"
            )
        self.assertIn("extends that reference into a longer path token", str(token.exception))

        mixed = copy.deepcopy(accepted)
        mixed[0]["old"] = f"  - {successor_path}\n  - {successor_path}.bak\n"
        mixed[0]["new"] = f"  - {checked_path}\n  - {checked_path}.bak\n"
        with self.assertRaises(module.RestructureError) as sibling:
            module.validate_lineage_reference_transition(
                before, after, mixed, "lineage"
            )
        self.assertIn(
            "extends that reference into a longer path token", str(sibling.exception)
        )

        leading = copy.deepcopy(accepted)
        leading[0]["old"] = f"  - some/{successor_path}\n"
        leading[0]["new"] = f"  - some/{checked_path}\n"
        with self.assertRaises(module.RestructureError) as prefix:
            module.validate_lineage_reference_transition(
                before, after, leading, "lineage"
            )
        self.assertIn(
            "extends that reference into a longer path token", str(prefix.exception)
        )

        sentence = copy.deepcopy(accepted)
        sentence[0]["scope"] = "body"
        sentence[0]["field"] = "body"
        sentence[0]["old"] = f"The contract is defined by {successor_path}. Follow it.\n"
        sentence[0]["new"] = f"The contract is defined by {checked_path}. Follow it.\n"
        module.validate_lineage_reference_transition(
            before, after, sentence, "lineage"
        )

    def test_a_reference_with_two_checked_archives_is_ambiguous(self) -> None:
        """An active path that names two archives proves no single target."""

        module, successor_path, checked_path = (
            self.prepare_replanned_source_with_checked_successor("ambiguous_lineage")
        )
        duplicate = (
            f"docs/plan/checked/1999/01/01-15/{Path(successor_path).name}"
        )
        target = self.repo / duplicate
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (self.repo / checked_path).read_text(encoding="utf-8"), encoding="utf-8"
        )
        index = self.repo / "docs/plan/checked.md"
        index.write_text(
            index.read_text(encoding="utf-8")
            + f"{Path(successor_path).name[:3]}\t{duplicate}\n",
            encoding="utf-8",
        )
        with self.assertRaises(module.RestructureError) as ambiguous:
            module.activation_checked_pairs()
        self.assertIn("multiple checked archives", str(ambiguous.exception))
        with self.assertRaises(module.RestructureError) as rebinding:
            module.validate_lineage_reference_transition(
                {
                    "status": "backlog",
                    "predecessor_plans": [successor_path],
                    "write_scope": ["docs/agent/spec-index.yaml"],
                },
                {
                    "status": "backlog",
                    "predecessor_plans": [checked_path],
                    "write_scope": ["docs/agent/spec-index.yaml"],
                },
                [
                    {
                        "scope": "manifest",
                        "field": "predecessor_plans",
                        "old": f"  - {successor_path}\n",
                        "new": f"  - {checked_path}\n",
                        "count": 1,
                    }
                ],
                "lineage",
            )
        self.assertIn("multiple checked archives", str(rebinding.exception))

    def test_lifecycle_evolution_admits_a_rebound_backlog_baseline(self) -> None:
        module = self.load_restructure_module("lifecycle_backlog_module")
        baseline = (
            "# Plan\n\nstatus: backlog\nwrite_scope:\n  - docs/agent/spec-index.yaml\n"
        )
        module.validate_lifecycle_evolution(baseline, baseline, "backlog")
        module.validate_lifecycle_evolution(
            baseline,
            baseline.replace("status: backlog", "status: in_progress", 1),
            "backlog",
        )
        with self.assertRaises(module.RestructureError) as drift:
            module.validate_lifecycle_evolution(
                baseline,
                baseline.replace(
                    "  - docs/agent/spec-index.yaml", "  - docs/agent/other.md", 1
                ),
                "backlog",
            )
        self.assertIn("changes protected manifest field", str(drift.exception))
        with self.assertRaises(module.RestructureError) as terminal:
            module.validate_lifecycle_evolution(
                baseline.replace("status: backlog", "status: checked", 1),
                baseline,
                "backlog",
            )
        self.assertIn("invalid lifecycle transition", str(terminal.exception))

    def legacy_lineage_state(
        self, module, checked_path: str, lifecycle: str = "backlog"
    ) -> tuple[dict[str, object], str, str]:
        """Build one unstarted referrer and the state a lineage rebinding needs."""
        plan_path = "docs/plan/active/181-legacy-referrer.md"
        live_path = f"docs/plan/{lifecycle}/181-legacy-referrer.md"
        fields = SHELVED_FIELDS if lifecycle == "shelved" else ""
        content = (
            (self.repo / checked_path)
            .read_text(encoding="utf-8")
            .replace("status: checked", f"status: {lifecycle}{fields}", 1)
        )
        content = re.sub(r"^replan_source.*\n(  - .*\n)*", "", content, flags=re.M)
        content = re.sub(r"^inherited_acceptance_digests:\n(  - .*\n)*", "", content, flags=re.M)
        content = content.replace(
            "context_files:",
            f"predecessor_plans:\n  - {self.source_path}\ncontext_files:",
            1,
        )
        target = self.repo / live_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        manifest = module.parse_manifest(content)
        projection = module.validation_projection(
            manifest,
            "referrer",
            require_witness=False,
            enforce_witness_semantics=False,
        )
        state = {
            "rebind_records": [],
            "effective_projections": {plan_path: projection},
            "live_successors": {
                plan_path: {
                    "lifecycle": lifecycle,
                    "live_path": live_path,
                    "contract_path": "docs/plan/replanned/contracts/legacy.json",
                    "contract_digest": digest(b"legacy"),
                    "enforce_projection_semantics": False,
                }
            },
        }
        return state, plan_path, content

    def test_legacy_lineage_baseline_must_be_committed(self) -> None:
        module, _, checked_path = (
            self.prepare_replanned_source_with_checked_successor("legacy_lineage")
        )
        state, plan_path, content = self.legacy_lineage_state(module, checked_path)
        replacements = [
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": f"  - {self.source_path}\n",
                "new": f"  - {checked_path}\n",
                "count": 1,
            }
        ]
        updated = module.apply_exact_replacements(
            content, replacements, kind="lineage_rebind", label="referrer"
        )
        spec = {
            "kind": "lineage_rebind",
            "plan_path": plan_path,
            "owning_contract_path": "docs/plan/replanned/contracts/legacy.json",
            "original_content_digest": digest(content),
            "prior_effective_projection_digest": module.projection_digest(
                state["effective_projections"][plan_path]  # type: ignore[index]
            ),
            "updated_content_digest": digest(updated),
            "replacements": replacements,
            "promoted_preservation_path": None,
        }
        arguments = {
            "repository_state": state,
            "transaction_id": digest(b"transaction"),
            "authorized_old_references": set(),
            "authorized_new_references": set(),
            "allowed_kinds": {"lineage_rebind"},
        }
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            with self.assertRaises(module.RestructureError) as uncommitted:
                module.validate_rebinding_specs([spec], **arguments)
            self.assertIn(
                "legacy lineage baseline is not committed", str(uncommitted.exception)
            )
            git(self.repo, "add", "docs/plan/backlog")
            git(self.repo, "commit", "-qm", "add the legacy backlog referrer")
            records, updated_files, statuses = module.validate_rebinding_specs(
                [spec], **arguments
            )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "lineage_rebind")
        self.assertEqual(statuses[plan_path], "backlog")
        self.assertEqual(
            updated_files, [("docs/plan/backlog/181-legacy-referrer.md", content, updated)]
        )
        self.assertIn(checked_path, updated)

    def test_lineage_rebinding_admits_a_shelved_referrer(self) -> None:
        module, _, checked_path = (
            self.prepare_replanned_source_with_checked_successor("legacy_lineage")
        )
        state, plan_path, content = self.legacy_lineage_state(
            module, checked_path, lifecycle="shelved"
        )
        replacements = [
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": f"  - {self.source_path}\n",
                "new": f"  - {checked_path}\n",
                "count": 1,
            }
        ]
        updated = module.apply_exact_replacements(
            content, replacements, kind="lineage_rebind", label="referrer"
        )
        spec = {
            "kind": "lineage_rebind",
            "plan_path": plan_path,
            "owning_contract_path": "docs/plan/replanned/contracts/legacy.json",
            "original_content_digest": digest(content),
            "prior_effective_projection_digest": module.projection_digest(
                state["effective_projections"][plan_path]  # type: ignore[index]
            ),
            "updated_content_digest": digest(updated),
            "replacements": replacements,
            "promoted_preservation_path": None,
        }
        arguments = {
            "repository_state": state,
            "transaction_id": digest(b"transaction"),
            "authorized_old_references": set(),
            "authorized_new_references": set(),
            "allowed_kinds": {"lineage_rebind"},
        }
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            git(self.repo, "add", "docs/plan/shelved")
            git(self.repo, "commit", "-qm", "add the legacy shelved referrer")
            records, updated_files, statuses = module.validate_rebinding_specs(
                [spec], **arguments
            )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(len(records), 1)
        self.assertEqual(statuses[plan_path], "shelved")
        self.assertEqual(
            updated_files,
            [("docs/plan/shelved/181-legacy-referrer.md", content, updated)],
        )

    def test_lineage_rebinding_accepts_a_shelved_unstarted_plan(self) -> None:
        module = self.load_restructure_module("shelved_lineage_module")
        before = {
            "status": "shelved",
            "predecessor_plans": ["docs/plan/active/099-absent.md"],
            "write_scope": ["docs/agent/spec-index.yaml"],
        }
        module.validate_lineage_reference_transition(
            before, dict(before), [], "lineage"
        )
        started = {**before, "status": "in_progress"}
        with self.assertRaises(module.RestructureError) as failure:
            module.validate_lineage_reference_transition(
                started, dict(started), [], "lineage"
            )
        self.assertIn("requires an unstarted plan", str(failure.exception))

    def test_lineage_rebinding_restates_a_shelved_reference(self) -> None:
        module = self.load_restructure_module("shelved_reference_module")
        shelved = self.repo / "docs/plan/shelved/099-absent.md"
        shelved.parent.mkdir(parents=True, exist_ok=True)
        shelved.write_text(
            f"# Absent\n\nstatus: shelved{SHELVED_FIELDS}\n", encoding="utf-8"
        )
        active_path = "docs/plan/active/099-absent.md"
        shelved_path = "docs/plan/shelved/099-absent.md"
        before = {
            "status": "backlog",
            "predecessor_plans": [active_path],
            "write_scope": ["docs/agent/spec-index.yaml"],
        }
        after = {**before, "predecessor_plans": [shelved_path]}
        accepted = [
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": f"  - {active_path}\n",
                "new": f"  - {shelved_path}\n",
                "count": 1,
            }
        ]
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            module.validate_lineage_reference_transition(
                before, after, accepted, "lineage"
            )
            wrong = copy.deepcopy(accepted)
            wrong[0]["new"] = "  - docs/plan/backlog/099-absent.md\n"
            with self.assertRaises(module.RestructureError) as target:
                module.validate_lineage_reference_transition(
                    before, after, wrong, "lineage"
                )
            self.assertIn("restate that reference as its shelved plan", str(target.exception))
            resident = self.repo / active_path
            resident.parent.mkdir(parents=True, exist_ok=True)
            resident.write_text("# resident\n", encoding="utf-8")
            try:
                with self.assertRaises(module.RestructureError) as live:
                    module.validate_lineage_reference_transition(
                        before, after, accepted, "lineage"
                    )
            finally:
                resident.unlink()
            self.assertIn("still resolves", str(live.exception))
            shelved.unlink()
            with self.assertRaises(module.RestructureError) as gone:
                module.validate_lineage_reference_transition(
                    before, after, accepted, "lineage"
                )
            self.assertIn("names no checked archive, no shelved plan", str(gone.exception))
            shelved.write_text(
                f"# Absent\n\nstatus: backlog{SHELVED_FIELDS}\n", encoding="utf-8"
            )
            with self.assertRaises(module.RestructureError) as status:
                module.validate_lineage_reference_transition(
                    before, after, accepted, "lineage"
                )
            self.assertIn("shelved reference is not shelved", str(status.exception))
            shelved.write_text(
                f"# Absent\n\nstatus: shelved{SHELVED_FIELDS}\n", encoding="utf-8"
            )
            extended = copy.deepcopy(accepted)
            extended[0]["old"] = f"  - {active_path}.bak\n"
            extended[0]["new"] = f"  - {shelved_path}.bak\n"
            with self.assertRaises(module.RestructureError) as token:
                module.validate_lineage_reference_transition(
                    before, after, extended, "lineage"
                )
            self.assertIn("longer path token", str(token.exception))
            archive = self.repo / "docs/plan/checked/2026/01/01-15/099-absent.md"
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_text("# Absent\n\nstatus: checked\n", encoding="utf-8")
            index = self.repo / "docs/plan/checked.md"
            index.write_text(
                "# Checked Plan Index\n\nid\tpath\n"
                "099\tdocs/plan/checked/2026/01/01-15/099-absent.md\n",
                encoding="utf-8",
            )
            try:
                with self.assertRaises(module.RestructureError) as both:
                    module.validate_lineage_reference_transition(
                        before, after, accepted, "lineage"
                    )
            finally:
                index.unlink()
                archive.unlink()
            self.assertIn("names both a shelved plan", str(both.exception))
        finally:
            os.chdir(old_cwd)

    def test_active_predecessors_resolve_one_shelved_plan(self) -> None:
        module = self.load_restructure_module("shelved_predecessor_module")
        shelved = self.repo / "docs/plan/shelved/099-absent.md"
        shelved.parent.mkdir(parents=True, exist_ok=True)
        shelved.write_text(
            f"# Absent\n\nstatus: shelved{SHELVED_FIELDS}\n", encoding="utf-8"
        )
        records = {
            "docs/plan/active/098-consumer.md": (
                "in_progress",
                {"predecessor_plans": ["docs/plan/shelved/099-absent.md"]},
            )
        }
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            module.validate_active_predecessors(records)
            shelved.write_text(
                f"# Absent\n\nstatus: backlog{SHELVED_FIELDS}\n", encoding="utf-8"
            )
            with self.assertRaises(module.RestructureError) as status:
                module.validate_active_predecessors(records)
            self.assertIn("predecessor is not shelved", str(status.exception))
            shelved.unlink()
            with self.assertRaises(module.RestructureError) as gone:
                module.validate_active_predecessors(records)
            self.assertIn("shelved predecessor is missing", str(gone.exception))
            stray = {
                "docs/plan/active/098-consumer.md": (
                    "in_progress",
                    {"predecessor_plans": ["docs/plan/shelved/nested/099-absent.md"]},
                )
            }
            with self.assertRaises(module.RestructureError) as invalid:
                module.validate_active_predecessors(stray)
            self.assertIn("invalid predecessor path", str(invalid.exception))
        finally:
            os.chdir(old_cwd)

    def test_lineage_rebinding_keeps_the_record_chain_and_live_bytes_apart(
        self,
    ) -> None:
        module, _, checked_path = (
            self.prepare_replanned_source_with_checked_successor("divergent_lineage")
        )
        state, plan_path, content = self.legacy_lineage_state(module, checked_path)
        git(self.repo, "add", "docs/plan/backlog")
        git(self.repo, "commit", "-qm", "add the divergent backlog referrer")
        deferred = content.replace(
            "status: backlog\n",
            "status: deferred\ncompletion_deferred_reason: the source must be checked\n",
            1,
        )
        state["rebind_records"] = [  # type: ignore[index]
            {
                "plan_path": plan_path,
                "updated_content": deferred,
            }
        ]
        replacements = [
            {
                "scope": "manifest",
                "field": "predecessor_plans",
                "old": f"  - {self.source_path}\n",
                "new": f"  - {checked_path}\n",
                "count": 1,
            }
        ]
        updated_baseline = module.apply_exact_replacements(
            deferred, replacements, kind="lineage_rebind", label="referrer"
        )
        updated_live = module.apply_exact_replacements(
            content, replacements, kind="lineage_rebind", label="referrer"
        )
        spec = {
            "kind": "lineage_rebind",
            "plan_path": plan_path,
            "owning_contract_path": "docs/plan/replanned/contracts/legacy.json",
            "original_content_digest": digest(deferred),
            "prior_effective_projection_digest": module.projection_digest(
                state["effective_projections"][plan_path]  # type: ignore[index]
            ),
            "updated_content_digest": digest(updated_baseline),
            "replacements": replacements,
            "promoted_preservation_path": None,
        }
        old_cwd = Path.cwd()
        try:
            os.chdir(self.repo)
            records, updated_files, statuses = module.validate_rebinding_specs(
                [spec],
                repository_state=state,
                transaction_id=digest(b"transaction"),
                authorized_old_references=set(),
                authorized_new_references=set(),
                allowed_kinds={"lineage_rebind"},
            )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(records[0]["original_content"], deferred)
        self.assertEqual(records[0]["updated_content"], updated_baseline)
        self.assertEqual(statuses[plan_path], "backlog")
        self.assertEqual(
            updated_files,
            [("docs/plan/backlog/181-legacy-referrer.md", content, updated_live)],
        )

    def test_prospective_verification_runs_from_a_generated_project_layout(self) -> None:
        authority = self.repo / ".project-agent-workflow/scripts"
        authority.mkdir(parents=True)
        shutil.copy2(SCRIPT, authority / "restructure-plan.py")
        shutil.copy2(
            ROOT / "scripts/plan_validation_commands.py",
            authority / "plan_validation_commands.py",
        )
        (self.repo / "scripts/restructure-plan.py").unlink()
        (self.repo / "scripts/plan_validation_commands.py").unlink()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "generated project authority layout")
        self.spec["source"]["head"] = git(  # type: ignore[index]
            self.repo, "rev-parse", "HEAD"
        )
        self.write_spec()
        completed = subprocess.run(
            [
                sys.executable,
                ".project-agent-workflow/scripts/restructure-plan.py",
                str(self.spec_path),
            ],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse((self.repo / "scripts/restructure-plan.py").exists())
        self.assertTrue((self.repo / str(self.spec["contract_path"])).is_file())

    def test_lineage_rebinding_cannot_edit_fields_outside_its_kind(self) -> None:
        module = self.load_restructure_module("lineage_fields_module")
        self.assertEqual(
            module.LINEAGE_REBIND_FIELDS,
            {"context_files", "predecessor_plans", "integration_gates"},
        )
        original = "status: backlog\nwrite_scope:\n  - docs/agent/spec-index.yaml\n\n# Plan\n"
        with self.assertRaises(module.RestructureError) as rejected:
            module.apply_exact_replacements(
                original,
                [
                    {
                        "scope": "manifest",
                        "field": "write_scope",
                        "old": "  - docs/agent/spec-index.yaml\n",
                        "new": "  - docs/agent/other.md\n",
                        "count": 1,
                    }
                ],
                kind="lineage_rebind",
                label="lineage",
            )
        self.assertIn("unauthorized field", str(rejected.exception))


COUPLED_ACCEPTANCE_CLAUSES: tuple[dict[str, object], ...] = (
    {
        "id": "atomic_transaction",
        "enforcement": (
            "hold_git_mutation_locks",
            "execute",
            "apply_operation",
            "rollback_journal",
            "roll_forward_journal",
            "atomic_replace_text",
        ),
        "tests": (
            "test_crash_recovery_rolls_back_each_precommit_phase_and_rolls_forward",
            "test_injected_midwrite_failure_rolls_back_metadata",
            "test_concurrent_transition_has_one_winner",
        ),
    },
    {
        "id": "fail_closed_preflight",
        "enforcement": (
            "validate_schema_three_spec",
            "verify_prospective_repository",
            "require_transaction_repository_state",
            "validate_prospective_plan_context_files",
        ),
        "tests": (
            "test_created_plan_context_is_enforced_before_any_mutation",
            "test_schema_one_preflight_rejects_corrupt_repository_before_journal",
            "test_tampered_source_digest_is_rejected_without_writes",
            "test_rejected_coupled_transaction_leaves_no_mutation_or_journal",
        ),
    },
    {
        "id": "stopped_source_replacement",
        "enforcement": (
            "derive_stopped_source_content",
            "validate_canonical_stopped_manifest",
            "build_multi_archive",
        ),
        "tests": (
            "test_direct_active_source_rejects_noncanonical_stopping",
            "test_durable_verification_rejects_unstopped_first_source",
            "test_canonical_stopped_state_rejects_noncanonical_metadata",
            "test_direct_active_sources_reconstruct_without_contract_ownership",
        ),
    },
    {
        "id": "immutable_dependent_replacement",
        "enforcement": (
            "source_dependency_reaches",
            "validate_direct_active_source",
            "validate_schema_three_integration_coverage",
        ),
        "tests": (
            "test_schema_three_reconstructs_coupled_sources_with_prerequisite",
            "test_direct_active_source_rejects_missing_dependency",
            "test_schema_three_rejects_partial_sources_and_duplicate_integrations",
            "test_mixed_source_routes_share_one_transaction",
        ),
    },
    {
        "id": "bounded_dependent_rebinding",
        "enforcement": (
            "apply_exact_replacements",
            "bounded_occurrences",
            "validate_rebind_reference_transition",
            "validate_validation_transition",
            "validate_rebinding_specs",
        ),
        "tests": (
            "test_rebind_rejects_protected_and_weakening_changes",
            "test_rebind_baseline_fork_is_rejected",
            "test_rebind_rejects_allowlisted_but_unadmitted_validation_path",
            "test_activation_rejects_unrelated_context_changes",
        ),
    },
    {
        "id": "historical_preservation",
        "enforcement": (
            "require_historical_contract_snapshot",
            "validate_lifecycle_evolution",
            "validate_projection",
            "compare_contract_identity",
        ),
        "tests": (
            "test_durable_contract_tampering_is_rejected",
            "test_committed_replanned_history_is_immutable",
            "test_live_successor_acceptance_drift_is_rejected_without_contract_change",
            "test_validation_projection_tampering_and_live_reordering_are_rejected",
            "test_lifecycle_evolution_rejects_reattached_list_items",
            "test_recovery_rejects_historical_contract_mutation",
        ),
    },
    {
        "id": "predecessor_graph_preservation",
        "enforcement": (
            "validate_active_predecessors",
            "validate_repository_active_predecessors",
            "matching_checked_paths",
        ),
        "tests": (
            "test_predecessor_cycles_and_duplicate_edges_are_rejected_before_writes",
            "test_stale_or_cross_id_checked_predecessor_is_rejected",
            "test_predecessor_chain_requires_deferred_then_exact_checked_refresh",
            "test_transaction_rejects_orphaning_an_unaffected_predecessor_edge",
        ),
    },
)

CLAUSE_POLICY_HEADING = "#### Acceptance Clauses"
CLAUSE_POLICY_FILES = (
    ROOT / "docs/agent/SPEC_PLAN_WORKFLOW.md",
    ROOT / "template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md",
)


class CoupledLineageAcceptanceCoverageTest(unittest.TestCase):
    """Bind the coupled reconstruction acceptance clauses to enforcement and tests."""

    @staticmethod
    def clause_ids() -> list[str]:
        return [str(clause["id"]) for clause in COUPLED_ACCEPTANCE_CLAUSES]

    @staticmethod
    def policy_clause_ids(text: str) -> list[str]:
        start = text.index(CLAUSE_POLICY_HEADING) + len(CLAUSE_POLICY_HEADING)
        end = len(text)
        for index in range(start, len(text)):
            if text.startswith("\n#", index) and not text.startswith("\n#####", index):
                end = index
                break
        return re.findall(r"^- `([a-z_]+)`:", text[start:end], re.MULTILINE)

    def test_clause_ids_are_unique_and_ordered_with_bound_evidence(self) -> None:
        ids = self.clause_ids()
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 7)
        for clause in COUPLED_ACCEPTANCE_CLAUSES:
            self.assertEqual(set(clause), {"id", "enforcement", "tests"})
            enforcement = tuple(clause["enforcement"])  # type: ignore[arg-type]
            covering = tuple(clause["tests"])  # type: ignore[arg-type]
            self.assertTrue(enforcement, clause["id"])
            self.assertTrue(covering, clause["id"])
            self.assertEqual(len(enforcement), len(set(enforcement)), clause["id"])
            self.assertEqual(len(covering), len(set(covering)), clause["id"])

    def test_every_clause_binds_existing_enforcement_functions(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        defined = set(re.findall(r"^def ([a-zA-Z_][a-zA-Z0-9_]*)\(", source, re.MULTILINE))
        for clause in COUPLED_ACCEPTANCE_CLAUSES:
            for name in clause["enforcement"]:  # type: ignore[union-attr]
                self.assertIn(
                    name,
                    defined,
                    f"clause {clause['id']} lost its enforcement function {name}",
                )
                self.assertGreater(
                    len(re.findall(rf"(?<![a-zA-Z0-9_]){re.escape(name)}\(", source)),
                    1,
                    f"clause {clause['id']} enforcement function {name} lost every call site",
                )

    def test_every_clause_binds_existing_regression_tests(self) -> None:
        available = {
            name for name in dir(PlanRestructureTest) if name.startswith("test_")
        }
        for clause in COUPLED_ACCEPTANCE_CLAUSES:
            for name in clause["tests"]:  # type: ignore[union-attr]
                self.assertIn(
                    name,
                    available,
                    f"clause {clause['id']} lost its covering test {name}",
                )

    def test_clause_decomposition_matches_root_and_generated_policy(self) -> None:
        expected = self.clause_ids()
        for path in CLAUSE_POLICY_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertIn(CLAUSE_POLICY_HEADING, text, str(path))
            self.assertEqual(self.policy_clause_ids(text), expected, str(path))


if __name__ == "__main__":
    unittest.main()
