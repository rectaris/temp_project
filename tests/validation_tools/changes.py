"""Change-selection tests."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from .support import PLAN_COMMAND_MODULES, ROOT, VALIDATE_CHANGE_MODULES, load_module


SELECTOR = ROOT / "tests/select-copier-fixture-validator-tests.py"
AGGREGATE_ENTRYPOINT = ROOT / "tests/test-copier-fixture-validator.py"
DOMAIN_MODULE_NAMES = ("contract", "inventory", "execution", "grammar", "placement")
AGGREGATE_ARGV = ["python3", "tests/test-copier-fixture-validator.py"]


def load_selector(name: str) -> object:
    return load_module(SELECTOR, name)


def domain_test_ids(module_name: str) -> set[str]:
    """Collect the unittest ids a Copier fixture validator module contributes."""
    path = (
        AGGREGATE_ENTRYPOINT
        if module_name == "aggregate"
        else ROOT / f"tests/copier_fixture_validator/{module_name}.py"
    )
    tests_dir = str(ROOT / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    module = load_module(path, f"copier_fixture_validator_inventory_{module_name}")
    ids: set[str] = set()

    def walk(suite: unittest.TestSuite) -> None:
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                walk(item)
            else:
                ids.add(item.id().rsplit(".", 2)[-2] + "." + item.id().rsplit(".", 1)[-1])

    walk(unittest.defaultTestLoader.loadTestsFromModule(module))
    return ids


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

    # --- Copier fixture validator selector -------------------------------
    # The root-only selector maps Git-visible changes to fixed test commands.

    def selector(self, name: str):
        return load_selector(f"copier_fixture_validator_selector_{name}")

    def test_a_domain_module_change_selects_only_its_own_command(self) -> None:
        module = self.selector("domain")
        for name in DOMAIN_MODULE_NAMES:
            with self.subTest(domain=name):
                path = f"tests/copier_fixture_validator/{name}.py"
                self.assertEqual(
                    module.select_commands([path]),
                    [["python3", path]],
                )

    def test_several_domain_changes_select_each_command_once(self) -> None:
        module = self.selector("dedupe")
        paths = [
            "tests/copier_fixture_validator/grammar.py",
            "tests/copier_fixture_validator/grammar.py",
            "tests/copier_fixture_validator/contract.py",
            "README.md",
        ]
        self.assertEqual(
            module.select_commands(paths),
            [
                ["python3", "tests/copier_fixture_validator/grammar.py"],
                ["python3", "tests/copier_fixture_validator/contract.py"],
            ],
        )

    def test_shared_and_unclassified_relevant_paths_select_the_complete_suite(self) -> None:
        module = self.selector("shared")
        shared = [
            "tests/copier_fixture_validator/support.py",
            "tests/copier_fixture_validator/__init__.py",
            "tests/test-copier-fixture-validator.py",
            "tests/select-copier-fixture-validator-tests.py",
            "tests/validation_tools/changes.py",
            "tests/validation_tools/plan.py",
            "scripts/plan_validation_commands.py",
            "scripts/project_workflow/copier_fixture_validator.py",
            "scripts/project_workflow/shell_lexical.py",
            "scripts/project_workflow/shell_functions.py",
            "scripts/project_workflow/shell_execution.py",
            "tests/copier_fixture_validator/unclassified.py",
            "scripts/project_workflow/unclassified.py",
        ]
        for path in shared:
            with self.subTest(path=path):
                self.assertEqual(module.select_commands([path]), [AGGREGATE_ARGV])
        self.assertEqual(
            module.select_commands(
                ["tests/copier_fixture_validator/contract.py", "tests/copier_fixture_validator/support.py"]
            ),
            [AGGREGATE_ARGV],
        )

    def test_a_missing_domain_module_falls_back_to_the_complete_suite(self) -> None:
        module = self.selector("missing")
        module.ROOT = Path("/nonexistent-selector-root")
        self.assertEqual(
            module.select_commands(["tests/copier_fixture_validator/contract.py"]),
            [AGGREGATE_ARGV],
        )

    def test_unrelated_paths_select_no_command(self) -> None:
        module = self.selector("unrelated")
        self.assertEqual(module.select_commands(["README.md", "docs/plan/plan.md"]), [])

    def test_unsafe_changed_paths_never_reach_a_selected_command(self) -> None:
        module = self.selector("unsafe")
        unsafe = [
            "tests/copier_fixture_validator/contract.py; rm -rf .",
            "tests/copier_fixture_validator/$(id).py",
            "../tests/copier_fixture_validator/contract.py",
            "/etc/passwd",
        ]
        for path in unsafe:
            with self.subTest(path=path):
                commands = module.select_commands([path])
                self.assertIn(commands, ([], [AGGREGATE_ARGV]))
                module.validate_selected_commands(commands)
                for command in commands:
                    for word in command:
                        self.assertNotIn(path, word)

    def test_selected_commands_stay_allowlisted(self) -> None:
        module = self.selector("allowlisted")
        commands = [AGGREGATE_ARGV, *(list(value) for value in module.DOMAIN_COMMANDS.values())]
        module.validate_selected_commands(commands)

    def test_staged_paths_take_precedence_over_unstaged_paths(self) -> None:
        module = self.selector("staged")

        def fake_git(args: list[str]) -> list[str]:
            if args[:2] == ["diff", "--cached"]:
                return ["tests/copier_fixture_validator/contract.py"]
            if args[:1] == ["diff"]:
                return ["README.md"]
            return []

        module.git = fake_git
        self.assertEqual(
            module.changed_files("auto"),
            (["tests/copier_fixture_validator/contract.py"], "staged", ["README.md"]),
        )
        self.assertEqual(
            module.changed_files("all"),
            (["README.md", "tests/copier_fixture_validator/contract.py"], "all", []),
        )

    def test_a_relevant_unstaged_path_still_forces_the_complete_suite(self) -> None:
        module = self.selector("deferred")
        self.assertEqual(
            module.select_commands(
                ["tests/copier_fixture_validator/contract.py"],
                ["tests/copier_fixture_validator/support.py"],
            ),
            [AGGREGATE_ARGV],
        )
        self.assertEqual(
            module.select_commands(["tests/copier_fixture_validator/contract.py"], ["README.md"]),
            [["python3", "tests/copier_fixture_validator/contract.py"]],
        )

    def test_git_paths_are_read_unquoted_and_null_separated(self) -> None:
        module = self.selector("quoting")
        recorded: list[list[str]] = []

        def fake_run(argv, **kwargs):
            recorded.append(list(argv))
            return SimpleNamespace(
                returncode=0,
                stdout="tests/copier_fixture_validator/\u65e5\u672c\u8a9e.py\0README.md\0",
            )

        module.subprocess = SimpleNamespace(run=fake_run, PIPE=subprocess.PIPE, DEVNULL=subprocess.DEVNULL)
        self.assertEqual(
            module.git(["diff", "--name-only"]),
            ["tests/copier_fixture_validator/\u65e5\u672c\u8a9e.py", "README.md"],
        )
        self.assertEqual(
            recorded[0],
            ["git", "-c", "core.quotePath=false", "diff", "--name-only", "-z"],
        )
        self.assertEqual(
            module.select_commands(["tests/copier_fixture_validator/\u65e5\u672c\u8a9e.py"]),
            [AGGREGATE_ARGV],
        )

    def test_a_rejected_command_exits_nonzero_without_running_tests(self) -> None:
        module = self.selector("rejected_command")

        def forbidden_run(*args: object, **kwargs: object) -> None:
            raise AssertionError("no test command may run after command validation fails")

        module.git = lambda args: []
        module.select_commands = lambda paths, deferred=None: [["python3", "tests/unlisted.py"]]
        module.subprocess = SimpleNamespace(run=forbidden_run)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main(["--all", "--json"]), 1)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["status"], "command_rejected")
        self.assertEqual(payload["commands"], [])

    def test_a_failed_git_query_exits_nonzero_without_running_tests(self) -> None:
        module = self.selector("git_failure")

        def failing_git(args: list[str]) -> list[str]:
            raise module.GitQueryError("Git query failed (128): git diff --cached --name-only")

        def forbidden_run(*args: object, **kwargs: object) -> None:
            raise AssertionError("no test command may run after a Git query failure")

        module.git = failing_git
        module.subprocess = SimpleNamespace(run=forbidden_run)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main(["--all", "--json"]), 1)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["status"], "git_query_failed")
        self.assertEqual(payload["commands"], [])

    def test_json_selection_reports_the_changed_paths_and_commands(self) -> None:
        module = self.selector("json")
        module.git = lambda args: (
            ["tests/copier_fixture_validator/execution.py"] if args[:2] == ["diff", "--cached"] else []
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main(["--print-only", "--json"]), 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["status"], "selected")
        self.assertEqual(payload["diff_mode"], "staged")
        self.assertEqual(payload["changed_files"], ["tests/copier_fixture_validator/execution.py"])
        self.assertEqual(
            [record["argv"] for record in payload["commands"]],
            [["python3", "tests/copier_fixture_validator/execution.py"]],
        )

    def test_unrelated_changes_report_no_required_test(self) -> None:
        module = self.selector("no_match")
        module.git = lambda args: ["README.md"] if args[:2] == ["diff", "--cached"] else []
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main(["--json"]), 0)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "no_matching_tests")

    def test_the_aggregate_inventory_is_the_disjoint_union_of_the_domains(self) -> None:
        aggregate = domain_test_ids("aggregate")
        collected: set[str] = set()
        for name in DOMAIN_MODULE_NAMES:
            ids = domain_test_ids(name)
            with self.subTest(domain=name):
                self.assertTrue(ids)
                self.assertTrue(ids < aggregate, f"{name} must be a strict subset")
                self.assertFalse(ids & collected, f"{name} duplicates an inherited case")
            collected |= ids
        self.assertEqual(collected, aggregate)

    def test_each_domain_module_runs_directly(self) -> None:
        for name in DOMAIN_MODULE_NAMES:
            with self.subTest(domain=name):
                selected = sorted(domain_test_ids(name))[0]
                path = ROOT / f"tests/copier_fixture_validator/{name}.py"
                result = subprocess.run(
                    [sys.executable, "-B", str(path), selected],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Ran 1 test", result.stderr)


if __name__ == "__main__":
    unittest.main()
