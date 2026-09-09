"""Fixture acceptance, structure, version boundary, and entrypoint tests."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


if __spec__ is None or not __spec__.parent:  # allow direct execution of this module
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copier_fixture_validator.support import (
    COMPLIANT,
    ContractSupportTest,
    CopierFixtureError,
    DECLARED,
    INVENTORY_REGION,
    PROLOGUE,
    ROOT,
    RULES,
    RULE_GUARDIAN,
    RULE_INVENTORY_REGION,
    RULE_STRUCTURE,
    RULE_VERSION_COMMIT,
    VALIDATOR,
    VERSION_COMMITS,
    WITHOUT_TRANSITION,
    check,
    copier_fixture_validator,
    main,
    validate,
)



class AcceptedFixtureTest(ContractSupportTest):
    def test_complete_transition_fixture_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT)

    def test_fixture_without_a_transition_region_is_accepted(self) -> None:
        self.assert_accepted(WITHOUT_TRANSITION)

    def test_supplied_bytes_are_accepted(self) -> None:
        self.assertEqual(check(COMPLIANT.encode("utf-8"), DECLARED), ())

    def test_contract_is_deterministic(self) -> None:
        mutated = self.remove('fixture_git "$update_source" tag v1.4.5\n')
        self.assertEqual(check(mutated, DECLARED), check(mutated, DECLARED))

    def test_validate_raises_only_for_a_broken_contract(self) -> None:
        self.assertIsNone(validate(COMPLIANT, DECLARED))
        with self.assertRaises(CopierFixtureError) as raised:
            validate(
                self.remove('rm -f "$release_file"\n\nrelease_waited=0'), DECLARED
            )
        self.assertIn("bounded operation rule", str(raised.exception))

    def test_rule_identifiers_are_unique_and_documented(self) -> None:
        self.assertEqual(len(RULES), len(set(RULES)))
        exported = set(copier_fixture_validator.__all__)
        for rule in RULES:
            name = f"RULE_{rule.upper()}"
            self.assertIn(name, exported)
            self.assertEqual(getattr(copier_fixture_validator, name), rule)


class StructureRejectionTest(ContractSupportTest):
    def test_unprojectable_bytes_are_rejected_without_partial_validation(self) -> None:
        findings = check("cat <<<here\n")
        self.assertEqual([finding.rule for finding in findings], [RULE_STRUCTURE])

    def test_nested_declaration_is_rejected_by_the_checked_function_table(self) -> None:
        self.assert_rejected(
            self.mutate(
                "cleanup() {\n  result=$?",
                "cleanup() {\n  helper() { :; }\n  result=$?",
            ),
            RULE_STRUCTURE,
            "not at the top level",
        )

    def test_redefined_function_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\nfixture_git() {\n  git "$@"\n}\n',
            RULE_STRUCTURE,
            "duplicate function declaration",
        )

    def test_non_utf8_bytes_are_rejected(self) -> None:
        with self.assertRaises(CopierFixtureError):
            check(b"\xff\xfe")

    def test_unsupported_source_type_is_rejected(self) -> None:
        with self.assertRaises(CopierFixtureError):
            check(17)


class VersionCommitTest(ContractSupportTest):
    def test_version_tag_without_its_own_commit_is_rejected(self) -> None:
        self.assert_rejected(
            self.remove('fixture_git "$update_source" commit -qm "Create the v1.4.5 boundary"\n'),
            RULE_VERSION_COMMIT,
            "share one commit",
        )

    def test_duplicated_commit_message_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'commit -qm "Create the v1.4.5 boundary"',
                'commit -qm "Create the v1.4.4 boundary"',
            ),
            RULE_VERSION_COMMIT,
            "reuse the commit message",
        )

    def test_tag_before_every_commit_is_rejected(self) -> None:
        source = PROLOGUE + INVENTORY_REGION + (
            '\nfixture_git "$update_source" tag v1.4.4\n'
            'fixture_git "$update_source" commit -qm "Create the v1.4.4 boundary"\n'
        )
        self.assert_rejected(source, RULE_VERSION_COMMIT, "no reachable preceding commit")

    def test_unreachable_version_tag_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'fixture_git "$update_source" tag v1.4.5\n',
                'exit 0\nfixture_git "$update_source" tag v1.4.5\n',
            ),
            RULE_VERSION_COMMIT,
            "no reachable execution path",
        )


class VersionTagExistenceTest(ContractSupportTest):
    def test_removing_every_version_tag_is_rejected(self) -> None:
        mutated = self.remove('fixture_git "$update_source" tag v1.4.4\n')
        mutated = self.remove('fixture_git "$update_source" tag v1.4.5\n', mutated)
        self.assert_rejected(
            mutated, RULE_VERSION_COMMIT, "no reachable operation creates a version tag"
        )

    def test_removing_the_whole_version_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(VERSION_COMMITS, "\n"),
            RULE_VERSION_COMMIT,
            "no reachable operation creates a version tag",
        )

    def test_every_annotated_tag_form_is_recognized(self) -> None:
        for form in (
            'tag -m "Create the v1.4.5 boundary" v1.4.5',
            'tag -a -m "Create the v1.4.5 boundary" v1.4.5',
            "tag -u signing-key v1.4.5",
            "tag -- v1.4.5",
        ):
            with self.subTest(form=form):
                self.assert_accepted(self.mutate("tag v1.4.5", form))

    def test_combined_short_tag_options_consume_their_value(self) -> None:
        mutated = self.mutate(
            "tag v1.4.4", 'tag -am "Create the v1.4.4 boundary" v1.4.4'
        )
        mutated = self.mutate(
            "tag v1.4.5", 'tag -am "Create the v1.4.5 boundary" v1.4.5', mutated
        )
        self.assert_accepted(mutated)
        self.assert_rejected(
            self.remove(
                'fixture_git "$update_source" commit -qm "Create the v1.4.5 boundary"\n',
                mutated,
            ),
            RULE_VERSION_COMMIT,
            "share one commit",
        )

    def test_a_tag_named_by_an_expansion_proves_a_tag_exists(self) -> None:
        mutated = self.mutate("tag v1.4.4", 'tag "$first_version"')
        self.assert_accepted(self.mutate("tag v1.4.5", 'tag "$second_version"', mutated))

    def test_tags_that_are_not_version_shaped_are_rejected(self) -> None:
        mutated = self.mutate("tag v1.4.4", "tag boundary-a")
        mutated = self.mutate("tag v1.4.5", "tag boundary-b", mutated)
        self.assert_rejected(
            mutated, RULE_VERSION_COMMIT, "no reachable operation creates a version tag"
        )


class CommandLineTest(unittest.TestCase):
    def run_cli(self, source: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.sh"
            path.write_text(source, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(VALIDATOR), "--check", str(path)],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(ROOT),
            )

    def test_check_accepts_a_complete_fixture(self) -> None:
        result = self.run_cli(COMPLIANT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("copier fixture check passed", result.stdout)

    def test_check_reports_every_broken_rule(self) -> None:
        result = self.run_cli(COMPLIANT.replace('[ "$guardian_pid" -gt 0 ]\n', "", 1))
        self.assertEqual(result.returncode, 1)
        self.assertIn("copier fixture check failed", result.stderr)
        self.assertIn(RULE_GUARDIAN, result.stderr)

    def test_check_reports_a_missing_file(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--check", "missing-fixture.sh"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("copier fixture check failed", result.stderr)

    def test_main_returns_the_same_status_in_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.sh"
            path.write_text(COMPLIANT, encoding="utf-8")
            with redirect_stdout(io.StringIO()) as accepted:
                self.assertEqual(main(["--check", str(path)]), 0)
            self.assertIn("copier fixture check passed", accepted.getvalue())
            path.write_text(WITHOUT_TRANSITION.replace(INVENTORY_REGION, ""), "utf-8")
            with redirect_stderr(io.StringIO()) as rejected:
                self.assertEqual(main(["--check", str(path)]), 1)
            self.assertIn(RULE_INVENTORY_REGION, rejected.getvalue())


class ModuleBoundaryTest(unittest.TestCase):
    def test_module_never_executes_or_imports_the_supplied_script(self) -> None:
        text = VALIDATOR.read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "importlib", "exec(", "eval("):
            self.assertNotIn(forbidden, text)

    def test_module_restates_no_checked_projection_rule(self) -> None:
        text = VALIDATOR.read_text(encoding="utf-8")
        for forbidden in ("def project", "class _Scanner", "def derive("):
            self.assertNotIn(forbidden, text)
        self.assertIn("shell_lexical.project", text)
        self.assertIn("shell_functions.derive", text)
        self.assertIn("shell_execution.derive", text)

    def test_contract_never_reads_the_runtime_candidate(self) -> None:
        self.assertNotIn("copier-update.sh", VALIDATOR.read_text(encoding="utf-8"))
        runtime = ROOT / "tests" / "copier-update.sh"
        package = Path(__file__).parent
        sources = sorted(package.glob("*.py"))
        self.assertIn(package / "support.py", sources)
        for source in sources:
            self.assertNotIn(str(runtime), source.read_text(encoding="utf-8"))
        for fixture in (COMPLIANT, WITHOUT_TRANSITION):
            self.assertTrue(fixture.startswith("#!/bin/sh"))
            self.assertNotIn("copier-update", fixture)


if __name__ == "__main__":
    unittest.main()
