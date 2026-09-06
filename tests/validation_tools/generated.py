"""Generated CI and security tests."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import (
    LEGACY_MIGRATOR,
    ROOT,
    SECURITY_CHECK_MODULE,
    SECURITY_RULE_MODULE,
    load_module,
)


class GeneratedCiTest(unittest.TestCase):
    GENERATED_LINT = ROOT / "template/.project-agent-workflow/scripts/lint-plan-docs.py"
    GENERATED_GROUP_AUTHORITY = (
        ROOT / "template/.project-agent-workflow/scripts/parallel-plan-state.py"
    )

    def build_generated_group_project(self, directory: Path, *, valid: bool = True) -> None:
        """Create a generated-layout project holding one execution group description."""

        import hashlib
        import json

        workflow = directory / ".project-agent-workflow"
        (directory / "docs/plan/active").mkdir(parents=True)
        (directory / "docs/plan/execution-groups").mkdir(parents=True)
        (workflow / "scripts").mkdir(parents=True)
        for name in (
            "parallel-plan-state.py",
            "lint-plan-docs.py",
            "planlib.py",
            "plan_validation_commands.py",
        ):
            source = ROOT / "template/.project-agent-workflow/scripts" / name
            (workflow / "scripts" / name).write_bytes(source.read_bytes())
        subprocess.run(["git", "init", "-q", "-b", "main", str(directory)], check=True)
        subprocess.run(["git", "-C", str(directory), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(directory), "config", "user.email", "test@example.invalid"],
            check=True,
        )

        def group_digest(value) -> str:
            data = value if isinstance(value, bytes) else str(value).encode("utf-8")
            return "sha256:" + hashlib.sha256(data).hexdigest()

        members = []
        for plan_id, slug, scope in (("284", "alpha", "src/alpha.py"), ("285", "beta", "src/beta.py")):
            relative = f"docs/plan/active/{plan_id}-{slug}.md"
            body = (
                f"# Plan {plan_id}\n\n"
                "status: in_progress\n"
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
                    "plan_digest": group_digest(body.encode("utf-8")),
                    "write_scope_digest": group_digest(
                        json.dumps([scope], sort_keys=True, separators=(",", ":"))
                    ),
                }
            )
        if not valid:
            members[1]["write_scope_digest"] = group_digest("wrong")
        description = {
            "schema_version": 1,
            "group_id": "alpha-beta",
            "target_ref": "refs/heads/main",
            "declared_independence": "disjoint modules with no shared interface",
            "members": members,
        }
        (
            directory / "docs/plan/execution-groups/alpha-beta.json"
        ).write_text(json.dumps(description, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(directory), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(directory), "commit", "-qm", "fixture"], check=True)

    def run_generated_group_lint(self, directory: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                ".project-agent-workflow/scripts/lint-plan-docs.py",
                "--check-execution-groups",
            ],
            cwd=directory,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_generated_lint_accepts_a_valid_execution_group(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "project"
            directory.mkdir()
            self.build_generated_group_project(directory)
            completed = self.run_generated_group_lint(directory)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_generated_lint_rejects_an_invalid_execution_group(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "project"
            directory.mkdir()
            self.build_generated_group_project(directory, valid=False)
            completed = self.run_generated_group_lint(directory)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("write scope digest", completed.stderr)

    def test_generated_lint_accepts_a_project_without_execution_groups(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "project"
            directory.mkdir()
            self.build_generated_group_project(directory)
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
                ["git", "-C", str(directory), "commit", "-qm", "remove groups"], check=True
            )
            completed = self.run_generated_group_lint(directory)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_generated_lint_fails_closed_on_a_worktree_only_group_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "project"
            directory.mkdir()
            self.build_generated_group_project(directory)
            (directory / "docs/plan/execution-groups/alpha-beta.json").unlink()
            completed = self.run_generated_group_lint(directory)
            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn("tracked but missing from the working tree", completed.stderr)

    def test_generated_group_authority_matches_the_root_authority(self) -> None:
        root_authority = ROOT / "scripts/parallel-plan-state.py"
        self.assertEqual(
            root_authority.read_bytes(), self.GENERATED_GROUP_AUTHORITY.read_bytes()
        )
        self.assertTrue(os.access(self.GENERATED_GROUP_AUTHORITY, os.X_OK))

    def test_group_authority_is_registered_in_the_install_inventory(self) -> None:
        inventory = load_module(
            ROOT / "scripts/project_workflow/copier_inventory.py", "group_inventory"
        )
        self.assertIn("scripts/parallel-plan-state.py", inventory.SOURCE_REQUIRED)
        self.assertIn(
            "template/.project-agent-workflow/scripts/parallel-plan-state.py",
            inventory.SOURCE_REQUIRED,
        )
        self.assertIn(
            ".project-agent-workflow/scripts/parallel-plan-state.py",
            inventory.GENERATED_REQUIRED,
        )

    def test_default_generated_lint_checks_execution_groups(self) -> None:
        text = self.GENERATED_LINT.read_text(encoding="utf-8")
        self.assertIn("--check-execution-groups", text)
        self.assertIn("lint_execution_groups()", text)

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

    def test_large_python_suites_run_as_independent_root_ci_jobs(self) -> None:
        jobs = self.root_workflow_jobs()
        dedicated = {
            "plan-restructure": "python3 tests/test-plan-restructure.py",
            "plan-execution-state": "python3 tests/test-plan-execution-state.py",
            "sandboxed-plan-worker": "python3 tests/test-sandboxed-plan-worker.py",
        }
        for job, command in dedicated.items():
            with self.subTest(job=job):
                self.assertIn(job, jobs)
                self.assertIn(f"        run: {command}\n", jobs[job])
                self.assertIn("    runs-on: ubuntu-latest\n", jobs[job])
                self.assertIn("        uses: actions/checkout@v4\n", jobs[job])
                self.assertNotIn("    needs:", jobs[job])
                self.assertNotIn(command, jobs["validate"])
        self.assertIn("bubblewrap", jobs["sandboxed-plan-worker"])

    def test_existing_ci_jobs_and_commands_are_preserved(self) -> None:
        jobs = self.root_workflow_jobs()
        for job in ("validate", "copier-fixture-validator", "minimum-compatibility"):
            self.assertIn(job, jobs)
        for command in (
            "scripts/lint-project-workflow.sh",
            "tests/smoke.sh",
            "tests/test-hooks.py",
            "tests/copier-update.sh",
            "scripts/check-yaml.py",
            "scripts/lint-github-actions.sh",
        ):
            with self.subTest(command=command):
                self.assertIn(command, jobs["validate"])
        self.assertIn("python3 tests/test-copier-fixture-validator.py", jobs["copier-fixture-validator"])
        self.assertIn("tests/copier-minimum.sh", jobs["minimum-compatibility"])

    @staticmethod
    def root_workflow_jobs() -> dict[str, str]:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        jobs: dict[str, list[str]] = {}
        current: str | None = None
        seen_jobs_key = False
        for line in text.splitlines(keepends=True):
            if not seen_jobs_key:
                seen_jobs_key = line.rstrip("\n") == "jobs:"
                continue
            match = re.fullmatch(r"  ([A-Za-z0-9_-]+):\n", line)
            if match:
                current = match.group(1)
                jobs[current] = []
            elif current is not None:
                jobs[current].append(line)
        return {name: "".join(body) for name, body in jobs.items()}

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
            fixture.write_text("curl https://example.invalid/install " + "|" + " sh\n", encoding="utf-8")
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
                "curl https://example.invalid/install " + "|" + " sh\nchanged fixture\n",
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
