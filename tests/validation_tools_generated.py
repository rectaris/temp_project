"""Generated CI and security tests."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validation_tools_support import (
    LEGACY_MIGRATOR,
    ROOT,
    SECURITY_CHECK_MODULE,
    SECURITY_RULE_MODULE,
    load_module,
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
