#!/usr/bin/env python3
"""Behavior tests for the pre-v1 direct-update guard."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATOR = ROOT / "scripts/migrate-to-namespaced-layout.py"
WORKER_MIGRATOR = ROOT / "scripts/migrate-sequential-plan-worker.py"
VALIDATOR_PATH = ROOT / "scripts/validate-copier-update.py"
PROFILE_UPDATER_PATH = ROOT / "scripts/update_agent_model_profiles.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_copier_update", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator_module()


def load_profile_updater_module():
    spec = importlib.util.spec_from_file_location("update_agent_model_profiles_for_migration_test", PROFILE_UPDATER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROFILE_UPDATER = load_profile_updater_module()

LEGACY_SEQUENTIAL_WORKER = '''name = "sequential_plan_worker"
description = "Bounded implementation worker for one assigned active plan with structured evidence and no descendant delegation."
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"

developer_instructions = """
Implement only the one active plan assigned by the parent.
Read the assigned plan and its required specs before editing.
Stay inside the explicit write scope; stop and report if the required change exceeds it.
Preserve unrelated user changes and do not weaken tests or validation.
Run every validation command required by the assigned plan.
Do not edit the assigned plan's status, ready_to_archive state, or archive location.
Do not process the next active plan.
Do not spawn descendant agents.
Do not commit changes.
Return changed paths, implementation summary, validation results, blockers, cross-plan impacts, and remaining risks.
"""
'''


class NamespacedLayoutMigrationTest(unittest.TestCase):
    def test_before_stage_fails_without_changing_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            legacy = repo / "AGENTS.md"
            legacy.write_text("legacy project policy\n", encoding="utf-8")
            subprocess.run(["git", "add", "AGENTS.md"], cwd=repo, check=True)
            before = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout

            result = subprocess.run(
                ["python3", str(MIGRATOR), "--stage", "before"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("destination was not changed", result.stderr)
            self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy project policy\n")
            after = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout
            self.assertEqual(after, before)
            self.assertFalse((repo / ".project-agent-workflow-migration").exists())

    def test_after_stage_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            result = subprocess.run(
                ["python3", str(MIGRATOR), "--stage", "after"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertIn("update guard completed", result.stdout)
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain=v1"],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    check=True,
                ).stdout,
                "",
            )


class SequentialPlanWorkerMigrationTest(unittest.TestCase):
    def run_migration(self, destination: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(WORKER_MIGRATOR), "--destination", str(destination)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_replaces_only_the_exact_v121_generated_profile_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / ".codex/agents/sequential_plan_worker.toml"
            target.parent.mkdir(parents=True)
            target.write_text(LEGACY_SEQUENTIAL_WORKER, encoding="utf-8")

            first = self.run_migration(destination)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = (ROOT / "template/.codex/agents/sequential_plan_worker.toml").read_text(
                encoding="utf-8"
            )
            self.assertEqual(target.read_text(encoding="utf-8"), expected)
            self.assertIn("migrated", first.stdout)

            second = self.run_migration(destination)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), expected)
            self.assertIn("already read-only", second.stdout)

    def test_refuses_customized_workspace_write_profile_without_changing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / ".codex/agents/sequential_plan_worker.toml"
            target.parent.mkdir(parents=True)
            customized = LEGACY_SEQUENTIAL_WORKER.replace(
                "Read the assigned plan and its required specs before editing.",
                "Preserve this project-owned instruction.",
            )
            target.write_text(customized, encoding="utf-8")

            result = self.run_migration(destination)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customized workspace-write", result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), customized)

    def test_preserves_a_custom_read_only_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / ".codex/agents/sequential_plan_worker.toml"
            target.parent.mkdir(parents=True)
            customized = '''name = "sequential_plan_worker"
description = "Project-owned read-only worker."
model = "gpt-5.3-codex-spark"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """Preserve this instruction."""
'''
            target.write_text(customized, encoding="utf-8")

            result = self.run_migration(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), customized)


class CopierOwnedContentValidationTest(unittest.TestCase):
    def test_validator_fixed_profiles_match_the_normalizer(self) -> None:
        self.assertEqual(VALIDATOR.FIXED_AGENT_PROFILES, PROFILE_UPDATER.PROFILES)

    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        repository = Path(temporary.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
        (repository / ".project-agent-workflow").mkdir()
        (repository / ".project-agent-workflow/ownership.yaml").write_bytes(
            (ROOT / "template/.project-agent-workflow/ownership.yaml").read_bytes()
        )
        (repository / "AGENTS.md").write_text("project policy\n", encoding="utf-8")
        (repository / ".copier-answers.yml").write_text("_commit: v1.2.1\n", encoding="utf-8")
        agents = repository / ".codex/agents"
        agents.mkdir(parents=True)
        (agents / "repo_explorer.toml").write_text(
            '''name = "repo_explorer"
description = "Project helper."
model = "old-model"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """Preserve this instruction."""
''',
            encoding="utf-8",
        )
        (agents / "sequential_plan_worker.toml").write_text(
            LEGACY_SEQUENTIAL_WORKER, encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repository, check=True)
        return temporary, repository

    def test_rejects_project_owned_and_unclassified_content_changes(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        for relative in ("AGENTS.md", "product.txt"):
            with self.subTest(relative=relative):
                path = repository / relative
                if relative == "product.txt":
                    path.write_text("baseline\n", encoding="utf-8")
                    subprocess.run(["git", "add", relative], cwd=repository, check=True)
                    subprocess.run(["git", "commit", "-qm", "add product"], cwd=repository, check=True)
                path.write_text("unexpected update\n", encoding="utf-8")
                with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "project-owned"):
                    VALIDATOR.validate(repository)
                subprocess.run(["git", "restore", relative], cwd=repository, check=True)

    def test_rejects_a_git_repository_without_a_committed_ownership_inventory(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        subprocess.run(
            ["git", "rm", "-q", ".project-agent-workflow/ownership.yaml"],
            cwd=repository,
            check=True,
        )
        subprocess.run(["git", "commit", "-qm", "remove ownership inventory"], cwd=repository, check=True)
        (repository / "AGENTS.md").write_text("unexpected update\n", encoding="utf-8")
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "ownership inventory"):
            VALIDATOR.validate(repository)

    def test_allows_managed_changes_and_exact_model_field_normalization(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (repository / ".project-agent-workflow/managed.txt").write_text("managed\n", encoding="utf-8")
        agent = repository / ".codex/agents/repo_explorer.toml"
        agent.write_text(
            agent.read_text(encoding="utf-8")
            .replace('model = "old-model"', 'model = "gpt-5.6-luna"')
            .replace('model_reasoning_effort = "medium"', 'model_reasoning_effort = "low"'),
            encoding="utf-8",
        )
        VALIDATOR.validate(repository)

    def test_allows_model_normalization_when_project_owns_a_custom_profile_name(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        customized = agent.read_text(encoding="utf-8").replace(
            'name = "repo_explorer"', 'name = "project_repository_reader"'
        )
        agent.write_text(customized, encoding="utf-8")
        subprocess.run(["git", "add", str(agent.relative_to(repository))], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "customize profile name"], cwd=repository, check=True)

        normalized = PROFILE_UPDATER.render_profile(
            customized, *PROFILE_UPDATER.PROFILES["repo_explorer"]
        )
        agent.write_text(normalized, encoding="utf-8")

        VALIDATOR.validate(repository)

    def test_rejects_agent_instruction_changes_but_allows_exact_worker_transition(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        original = agent.read_text(encoding="utf-8")
        agent.write_text(original.replace("Preserve this instruction.", "Changed instruction."), encoding="utf-8")
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "agent profile"):
            VALIDATOR.validate(repository)
        agent.write_text(original, encoding="utf-8")

        worker = repository / ".codex/agents/sequential_plan_worker.toml"
        worker.write_text(
            (ROOT / "template/.codex/agents/sequential_plan_worker.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        VALIDATOR.validate(repository)

    def test_model_like_instruction_lines_remain_project_owned(self) -> None:
        temporary, repository = self.make_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / ".codex/agents/repo_explorer.toml"
        original = agent.read_text(encoding="utf-8").replace(
            'developer_instructions = """Preserve this instruction."""',
            'developer_instructions = """\nmodel = \\"instruction text\\"\n"""',
        )
        agent.write_text(original, encoding="utf-8")
        subprocess.run(["git", "add", str(agent.relative_to(repository))], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "add model-like instruction"], cwd=repository, check=True)
        normalized = (
            original.replace('model = "old-model"', 'model = "gpt-5.6-luna"', 1)
            .replace('model_reasoning_effort = "medium"', 'model_reasoning_effort = "low"', 1)
        )
        agent.write_text(normalized, encoding="utf-8")
        VALIDATOR.validate(repository)

        agent.write_text(
            normalized.replace('model = \\"instruction text\\"', 'model = \\"changed text\\"'),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(VALIDATOR.UpdateValidationError, "agent profile"):
            VALIDATOR.validate(repository)


if __name__ == "__main__":
    unittest.main()
