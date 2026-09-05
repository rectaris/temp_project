#!/usr/bin/env python3
"""Behavior tests for the bounded Copier fixture operation contract.

Every fixture used here is written in this file. The runtime candidate
`tests/copier-update.sh` is never read as expected output and is never
executed, so the contract is proven against supplied bytes only.
"""

from __future__ import annotations
import pathlib
import io
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from project_workflow import copier_fixture_validator  # noqa: E402
from project_workflow import shell_execution  # noqa: E402
from project_workflow import shell_functions  # noqa: E402
from project_workflow import shell_lexical  # noqa: E402
from project_workflow.copier_fixture_validator import (  # noqa: E402
    CopierFixtureError,
    INVENTORY_PATH,
    RULE_ALTERNATE_PATH,
    RULE_BOUNDED_POLL,
    RULE_CHILD_PID,
    RULE_CHILD_REAP,
    RULE_COMMAND_SHADOWING,
    RULE_DIRECT_INVOCATION,
    RULE_GUARDIAN,
    RULE_INVENTORY_REGION,
    RULE_RELEASE_PATH,
    RULE_STATE_ORDER,
    RULE_STRUCTURE,
    RULE_UNRESOLVED_DISPATCH,
    RULE_UPDATE_CHILD,
    RULE_VERSION_COMMIT,
    RULES,
    check,
    declared_paths,
    main,
    read_inventory,
    validate,
)


VALIDATOR = ROOT / "scripts/project_workflow/copier_fixture_validator.py"

# The update source paths the inventory every fixture in this file reads
# declares. The contract is proven against these supplied declarations rather
# than against whatever inventory the repository happens to ship.
DECLARED = (
    "copier.yml",
    "template/.project-agent-workflow/README.md",
)

PROLOGUE = """#!/bin/sh
set -eu

root=$1
tmp=$(CDPATH= cd -- "$2" && pwd -P)
project="$tmp/project"
update_source="$tmp/update-source"
inventory="$root/tests/fixtures/fixture-source-inventory.txt"
attempt_state="$project/.git/attempt.json"
ready_file="$tmp/guardian-ready"
release_file="$tmp/guardian-release"
guardian_pid=0
update_pid=

fixture_git() {
  repository=$1
  shift
  git -C "$repository" "$@"
}

cleanup() {
  result=$?
  rm -f "$release_file"
  if [ "$guardian_pid" -gt 0 ]; then
    kill -TERM "$guardian_pid" 2>/dev/null || true
  fi
  exit "$result"
}
trap cleanup EXIT HUP INT TERM
"""

INVENTORY_REGION = """
while IFS= read -r candidate_path || [ -n "$candidate_path" ]; do
  cp "$root/$candidate_path" "$update_source/$candidate_path"
  fixture_git "$update_source" add -- "$candidate_path"
done < "$inventory"
"""

VERSION_COMMITS = """
fixture_git "$update_source" commit -qm "Create the v1.4.4 boundary"
fixture_git "$update_source" tag v1.4.4
fixture_git "$update_source" commit -qm "Create the v1.4.5 boundary"
fixture_git "$update_source" tag v1.4.5
"""

TRANSITION = """
"$project/.project-agent-workflow/scripts/update-from-copier.sh" --defaults --vcs-ref v1.4.5 &
update_pid=$!

ready_waited=0
while [ "$ready_waited" -lt 30 ]; do
  if [ -e "$ready_file" ]; then
    break
  fi
  ready_waited=$((ready_waited + 1))
  sleep 1
done
if [ ! -e "$ready_file" ]; then
  rm -f "$release_file"
  echo "the guardian ready event was not observed" >&2
  exit 1
fi

grep -q '"state": "pending"' "$attempt_state"
guardian_pid=$(cat "$tmp/guardian.pid")
[ "$guardian_pid" -gt 0 ]

rm -f "$release_file"

release_waited=0
while [ "$release_waited" -lt 30 ]; do
  if [ ! -e "$release_file" ]; then
    break
  fi
  release_waited=$((release_waited + 1))
  sleep 1
done

wait "$update_pid"
kill -TERM "$update_pid" 2>/dev/null || true
sleep 5
kill -KILL "$update_pid" 2>/dev/null || true
wait "$update_pid" 2>/dev/null || true
update_pid=

grep -q '"state": "consumed"' "$attempt_state"
"""

COMPLIANT = PROLOGUE + INVENTORY_REGION + VERSION_COMMITS + TRANSITION
WITHOUT_TRANSITION = PROLOGUE + INVENTORY_REGION + VERSION_COMMITS


class ContractSupportTest(unittest.TestCase):
    declared: tuple[str, ...] = DECLARED
    # No library is bound by default, so every fixture written here is proven
    # against its own supplied bytes. The sourced-library cases bind theirs.
    sourced: dict[str, str] = {}

    def rules(self, source: str) -> list[str]:
        return [
            finding.rule for finding in check(source, self.declared, self.sourced)
        ]

    def messages(self, source: str) -> str:
        return "\n".join(
            str(finding) for finding in check(source, self.declared, self.sourced)
        )

    def assert_accepted(self, source: str) -> None:
        findings = check(source, self.declared, self.sourced)
        self.assertEqual(findings, (), self.messages(source))

    def assert_rejected(self, source: str, rule: str, expected: str) -> None:
        findings = check(source, self.declared, self.sourced)
        self.assertTrue(findings, "the mutated fixture was accepted")
        self.assertIn(rule, [finding.rule for finding in findings], self.messages(source))
        matching = [
            finding for finding in findings if finding.rule == rule and expected in finding.message
        ]
        self.assertTrue(matching, self.messages(source))

    def mutate(self, original: str, replacement: str, source: str = COMPLIANT) -> str:
        self.assertIn(original, source)
        return source.replace(original, replacement, 1)

    def remove(self, original: str, source: str = COMPLIANT) -> str:
        return self.mutate(original, "", source)


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


class InventoryRegionTest(ContractSupportTest):
    def test_missing_inventory_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.remove(INVENTORY_REGION),
            RULE_INVENTORY_REGION,
            "no loop reads one inventory",
        )

    def test_duplicated_inventory_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(INVENTORY_REGION, INVENTORY_REGION + INVENTORY_REGION),
            RULE_INVENTORY_REGION,
            "more than one inventory copy and staging region",
        )

    def test_duplicated_copy_inside_the_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n',
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n'
                '  cp "$root/$candidate_path" "$update_source/$candidate_path.copy"\n',
            ),
            RULE_INVENTORY_REGION,
            "copies more than once",
        )

    def test_copy_that_is_not_derived_from_the_inventory_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'cp "$root/$candidate_path" "$update_source/$candidate_path"',
                'cp "$root/AGENTS.md" "$update_source/AGENTS.md"',
            ),
            RULE_INVENTORY_REGION,
            "not derived from `candidate_path`",
        )

    def test_a_region_that_places_files_with_another_command_is_rejected(self) -> None:
        for command in ("ln", "ln -s", "mv", "rsync"):
            with self.subTest(command=command):
                self.assert_rejected(
                    self.mutate(
                        'cp "$root/$candidate_path" "$update_source/$candidate_path"',
                        f'{command} "$root/$candidate_path" '
                        '"$update_source/$candidate_path"',
                    ),
                    RULE_INVENTORY_REGION,
                    "no loop reads one inventory",
                )

    def test_staging_before_copying_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n'
                '  fixture_git "$update_source" add -- "$candidate_path"\n',
                '  fixture_git "$update_source" add -- "$candidate_path"\n'
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n',
            ),
            RULE_INVENTORY_REGION,
            "stages the path before copying it",
        )

    def test_staging_outside_the_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                VERSION_COMMITS,
                '\nfixture_git "$update_source" add -- "$candidate_path"\n' + VERSION_COMMITS,
            ),
            RULE_INVENTORY_REGION,
            "staging outside the inventory region",
        )


    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    def test_a_hard_coded_copy_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('cp "$root/AGENTS.md" "$update_source/AGENTS.md"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_copy_into_the_update_source_under_another_name_is_rejected(
        self,
    ) -> None:
        self.assert_rejected(
            self.outside(
                'mirror="$update_source"\n'
                'cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_redirection_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('printf x >"$update_source/extra.txt"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_helper_written_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('touch "$update_source/extra.txt"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_staging_a_path_nothing_writes_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'fixture_git "$update_source" add -- undeclared/path.txt\n',
                'git -C "$update_source" add -- undeclared/path.txt\n',
                'fixture_git "$update_source" add undeclared/path.txt\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "adds a path nothing writes into the update source",
                )

    def test_staging_the_whole_update_source_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'fixture_git "$update_source" add -A\n',
                'fixture_git "$update_source" add .\n',
                'fixture_git "$update_source" add -u\n',
                'fixture_git "$update_source" add -- .\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "without naming one path",
                )

    def test_staging_a_path_the_fixture_edits_in_place_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
            )
        )

    def test_staging_another_repository_outside_the_region_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'other="$tmp/other"\n'
                'fixture_git "$other" add -A\n'
                'fixture_git "$other" add -- undeclared/path.txt\n'
            )
        )

    def test_a_copy_outside_the_update_source_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside('cp "$root/AGENTS.md" "$tmp/other/AGENTS.md"\n')
        )

    def test_a_write_this_checker_cannot_place_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'extra_destination=$(printf %s "$update_source/AGENTS.md")\n'
                'cp "$root/AGENTS.md" "$extra_destination"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write this checker cannot place",
        )

    def test_a_write_a_loop_head_places_is_read_at_that_path(self) -> None:
        """A loop head says which words the name it binds may hold.

        The write is reported as reaching the update source itself rather than
        as a write this checker cannot place, because the head words settle the
        name every round binds.
        """

        self.assert_rejected(
            self.outside(
                'for extra in AGENTS.md; do\n'
                '  cp "$root/$extra" "$update_source/$extra"\n'
                'done\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside the inventory region",
        )

    def test_a_command_that_puts_files_in_place_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'tar -x -C "$update_source" -f "$root/extra.tar"\n',
                'rsync -a "$root/AGENTS.md" "$update_source/AGENTS.md"\n',
                'fixture_git "$update_source" apply --index "$root/extra.patch"\n',
                'fixture_git "$update_source" checkout -- AGENTS.md\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "puts files in place",
                )

    def test_a_directory_change_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'cd "$update_source"\n'
                'cp "$root/AGENTS.md" AGENTS.md\n'
                'cd "$root"\n'
            ),
            RULE_INVENTORY_REGION,
            "a directory change into the update source",
        )

    def test_staging_written_as_a_synonym_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('fixture_git "$update_source" stage -- undeclared.txt\n'),
            RULE_INVENTORY_REGION,
            "adds a path nothing writes into the update source",
        )

    def test_a_git_run_this_checker_cannot_read_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'printf AGENTS.md | xargs fixture_git "$update_source" add --\n',
                'sh -c \'git -C "$update_source" add -A\'\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a Git run this checker cannot read",
                )

    def test_staging_a_path_only_a_read_names_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'grep -qF marker "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path nothing writes into the update source",
        )

    def test_staging_an_edited_path_written_in_full_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- "$update_source/copier.yml"\n'
            )
        )

    def test_a_directory_change_outside_the_update_source_is_accepted(self) -> None:
        self.assert_accepted(self.outside('cd "$tmp/other"\ncd "$root"\n'))

    def test_an_alias_bound_by_a_loop_is_placed(self) -> None:
        self.assert_rejected(
            self.outside(
                'for mirror in "$update_source"; do\n'
                '  cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
                "done\n"
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside the inventory region",
        )

    def test_an_alias_bound_by_a_loop_head_it_cannot_read_is_reported(self) -> None:
        self.assert_rejected(
            self.outside(
                'for mirror in $(printf %s "$update_source"); do\n'
                '  sed -i "s/a/b/" "$mirror/NOTICE"\n'
                "done\n"
            ),
            RULE_INVENTORY_REGION,
            "takes a destination this checker cannot place",
        )

    def test_an_alias_bound_from_a_parameter_is_placed(self) -> None:
        """A call site says which directory the parameter it writes names.

        The write is reported as reaching the update source itself rather than
        as a write this checker cannot place, because the value the call site
        writes settles the name the body binds from it.
        """

        self.assert_rejected(
            self.outside(
                "seed() {\n"
                "  mirror=$1\n"
                '  cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
                "}\n"
                'seed "$update_source"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside the inventory region",
        )

    def test_staging_written_as_an_index_update_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'fixture_git "$update_source" update-index --add -- undeclared.txt\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path nothing writes into the update source",
        )

    def test_a_call_passing_another_directory_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'seed() {\n'
                '  mirror=$1\n'
                '  cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
                '}\n'
                'seed "$tmp/other"\n'
            )
        )

    def test_a_copy_into_a_directory_destination_is_rejected(self) -> None:
        for command in ("cp", "install"):
            with self.subTest(command=command):
                self.assert_rejected(
                    self.outside(f'{command} "$root/AGENTS.md" "$update_source/"\n'),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside",
                )

    def test_a_directory_destination_resolved_from_a_name_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('slash=/\ncp "$root/AGENTS.md" "$update_source$slash"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_directory_destination_after_a_terminator_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('cp -- "$root/AGENTS.md" "$update_source/"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_every_source_of_a_directory_destination_is_placed(self) -> None:
        self.assert_rejected(
            self.outside(
                'cp "$root/AGENTS.md" "$root/NOTICE" "$update_source/"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_directory_destination_reached_from_every_call_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                "seed() {\n"
                '  cp "$root/AGENTS.md" "$tmp/$1"\n'
                "}\n"
                'seed "update-source/"\n'
                'seed "other-source/"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_source_with_no_name_of_its_own_is_reported_unplaceable(self) -> None:
        for index, source in enumerate(('"$root/."', '"$root/.."', '"$root/$1"')):
            with self.subTest(source=source):
                self.assert_rejected(
                    self.outside(f'cp {source} "$update_source/"\n'),
                    RULE_INVENTORY_REGION,
                    "a write this checker cannot place is written where the "
                    "update source is named",
                )

    def test_a_directory_destination_outside_the_update_source_is_accepted(
        self,
    ) -> None:
        self.assert_accepted(
            self.outside('cp "$root/AGENTS.md" "$tmp/other/"\n')
        )

    def test_a_destination_written_without_a_separator_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside('cp "$root/AGENTS.md" "$tmp/update-source"\n')
        )

    def test_a_destination_carrying_the_separator_in_one_form_is_accepted(
        self,
    ) -> None:
        """One form that writes no separator leaves the destination a file.

        The shell creates the destination word itself whenever the value it
        carries ends in a name, so a word that may carry either form proves no
        directory and keeps the reading it already had.
        """

        self.assert_accepted(
            self.outside(
                "seed() {\n"
                '  cp "$root/AGENTS.md" "$tmp/$1"\n'
                "}\n"
                'seed "update-source/"\n'
                'seed "update-source"\n'
            )
        )

    def test_an_empty_only_name_settles_no_directory_destination(self) -> None:
        """The empty value option classification supplies never places a path.

        The word reaches its command as `$update_source/`, but the binding
        model reports the name unreadable, so the destination stays one this
        checker cannot place rather than becoming a directory it reads.
        """

        self.assert_rejected(
            self.outside('empty=\ncp "$root/AGENTS.md" "$empty$update_source/"\n'),
            RULE_INVENTORY_REGION,
            "takes a destination this checker cannot place",
        )

    def test_an_alias_written_with_a_directory_destination_is_unchanged(self) -> None:
        for command in ("mv", "ln", "ln -s"):
            with self.subTest(command=command):
                self.assert_rejected(
                    self.outside(f'{command} "$root/AGENTS.md" "$update_source/"\n'),
                    RULE_INVENTORY_REGION,
                    "an alias of the update source stands outside",
                )

    def test_an_option_bearing_copy_keeps_its_reading(self) -> None:
        for written in (
            'cp -T "$root/AGENTS.md" "$update_source/"',
            'cp --no-target-directory "$root/AGENTS.md" "$update_source/"',
            'cp --parents "$root/AGENTS.md" "$update_source/"',
            'cp -R "$root/AGENTS.md" "$update_source/"',
            'install -d "$update_source/"',
            'install -d "$root/AGENTS.md" "$update_source/"',
            'install -D "$root/AGENTS.md" "$update_source/"',
            'cp "$root/AGENTS.md" -- "$update_source/"',
        ):
            with self.subTest(written=written):
                self.assert_accepted(self.outside(written + "\n"))

    def test_a_deferred_copy_with_a_directory_destination_is_unchanged(self) -> None:
        self.assert_accepted(
            self.outside(
                "seed() {\n"
                '  cp "$root/AGENTS.md" "$update_source/"\n'
                "}\n"
                "trap seed USR1\n"
            )
        )


class TrailingSeparatorDestinationTest(unittest.TestCase):
    """Place the sources of a copy whose destination is written as a directory.

    A destination written with a trailing separator names a directory, so the
    command creates each source under the name that source ends with. The
    placement is read here from the words one operation records, because the
    rules above report only whether some created path reached a searched
    directory and not which names were placed.
    """

    def build(self, body: str):
        """Return the derived fixture for one written body."""

        text = "#!/bin/sh\nset -eu\n" + body
        records = shell_lexical.project(text)
        table = shell_functions.derive(records)
        graph = shell_execution.derive(records, table)
        return copier_fixture_validator._Fixture(text, records, table, graph)

    def helper_paths(self, body: str):
        """Return what the one helper-writing command of a body creates."""

        fixture = self.build(body)
        for operation in fixture.operations:
            words = copier_fixture_validator._operation_words(operation)
            literals = copier_fixture_validator._word_literals(words)
            index = copier_fixture_validator._command_index(
                literals, copier_fixture_validator.HELPER_WRITING_COMMANDS
            )
            if index >= 0:
                return copier_fixture_validator._helper_paths(fixture, operation)
        raise AssertionError("the body writes no helper-writing command")

    def inside(self, body: str) -> set:
        return set(self.helper_paths(body)[1])

    def unplaceable(self, body: str) -> bool:
        return self.helper_paths(body)[3]

    DEST = (True, ("dest",))

    def test_an_unsettled_source_is_placed_under_the_written_name(self) -> None:
        for command in ("cp", "install"):
            with self.subTest(command=command):
                self.assertEqual(
                    self.inside(f'{command} "$1/one" "/dest/"\n'),
                    {(self.DEST, "one")},
                )

    def test_every_unsettled_source_is_placed(self) -> None:
        self.assertEqual(
            self.inside('cp "$1/one" "$1/two" "/dest/"\n'),
            {(self.DEST, "one"), (self.DEST, "two")},
        )

    def test_a_settled_source_keeps_its_settled_name(self) -> None:
        self.assertEqual(
            self.inside('cp /src/one /src/two "/dest/"\n'),
            {(self.DEST, "one"), (self.DEST, "two")},
        )

    def test_a_separator_carried_by_a_name_places_the_source(self) -> None:
        self.assertEqual(
            self.inside('slash=/\ncp "$1/one" "/dest$slash"\n'),
            {(self.DEST, "one")},
        )

    def test_a_leading_terminator_places_the_source(self) -> None:
        self.assertEqual(
            self.inside('cp -- "$1/one" "/dest/"\n'), {(self.DEST, "one")}
        )

    def test_a_source_that_names_no_file_is_reported_unplaceable(self) -> None:
        for source in ('"$1/."', '"$1/.."', '"$1/$2"'):
            with self.subTest(source=source):
                body = f'cp {source} "/dest/"\n'
                self.assertEqual(self.inside(body), set())
                self.assertTrue(self.unplaceable(body))

    def test_a_destination_written_without_a_separator_places_nothing(self) -> None:
        body = 'cp "$1/one" "/dest"\n'
        self.assertEqual(self.inside(body), set())
        self.assertFalse(self.unplaceable(body))

    def test_an_option_bearing_command_places_nothing(self) -> None:
        for written in (
            'cp -T "$1/one" "/dest/"',
            'cp --no-target-directory "$1/one" "/dest/"',
            'cp --parents "$1/one" "/dest/"',
            'install -d "$1/one" "/dest/"',
            'install -D "$1/one" "/dest/"',
            'cp "$1/one" -- "/dest/"',
            'mv "$1/one" "/dest/"',
            'ln "$1/one" "/dest/"',
        ):
            with self.subTest(written=written):
                body = written + "\n"
                self.assertEqual(self.inside(body), set())
                self.assertFalse(self.unplaceable(body))

    def test_a_deferred_body_places_nothing(self) -> None:
        """No written call site says which values an unmodelled body holds.

        The separator such a body writes is read against the values every
        binding place in the fixture holds, which is a different model from
        the one this reading proves its destination against, so a deferred
        operation keeps the reading it already had.
        """

        fixture = self.build(
            "seed() {\n"
            '  cp "$1/one" "/dest/"\n'
            "}\n"
            "trap seed USR1\n"
        )
        placed = set()
        unplaceable = False
        bodies = copier_fixture_validator._deferred_bodies(fixture)
        self.assertTrue(bodies, "the fixture writes no unmodelled body")
        for declaration in bodies:
            for operation in (
                copier_fixture_validator._deferred_operations(fixture, declaration)
                or ()
            ):
                _created, inside, _words, unknown = (
                    copier_fixture_validator._helper_paths(fixture, operation)
                )
                placed |= set(inside)
                unplaceable = unplaceable or unknown
        self.assertEqual(placed, set())
        self.assertFalse(unplaceable)

    def test_a_target_directory_option_keeps_its_own_placement(self) -> None:
        self.assertEqual(
            self.inside('cp -t "/dest/" "$1/one"\n'), {(self.DEST, "one")}
        )

    def test_an_unresolved_option_word_places_nothing(self) -> None:
        body = 'cp $opt "$1/one" "/dest/"\n'
        self.assertEqual(self.inside(body), set())
        self.assertTrue(self.unplaceable(body))

    def test_an_unreadable_destination_places_nothing(self) -> None:
        for body in (
            'empty=\ncp "$1/one" "$empty/dest/"\n',
            'cp "$1/one" "$(printf %s /dest)/"\n',
        ):
            with self.subTest(body=body):
                self.assertEqual(self.inside(body), set())
                self.assertTrue(self.unplaceable(body))

    def test_a_path_reading_never_takes_the_option_empty_value(self) -> None:
        """The value option classification supplies settles no path here."""

        fixture = self.build('empty=\ncp "$1/one" "$empty/dest/"\n')
        operation = next(
            operation
            for operation in fixture.operations
            if copier_fixture_validator._command_index(
                copier_fixture_validator._word_literals(
                    copier_fixture_validator._operation_words(operation)
                ),
                copier_fixture_validator.HELPER_WRITING_COMMANDS,
            )
            >= 0
        )
        self.assertEqual(
            copier_fixture_validator._resolved_word_texts(
                fixture, operation, '"$empty/dest/"'
            ),
            ("/dest/",),
        )
        self.assertIsNone(
            copier_fixture_validator._path_forms(
                fixture, operation, '"$empty/dest/"'
            )
        )

    def test_mixed_separator_forms_place_nothing(self) -> None:
        body = (
            "seed() {\n"
            '  cp "$3/one" "/dest/$1"\n'
            "}\n"
            'seed "two/"\n'
            "seed two\n"
        )
        self.assertEqual(self.inside(body), set())

    def test_agreeing_separator_forms_place_every_destination(self) -> None:
        body = (
            "seed() {\n"
            '  cp "$3/one" "/dest/$1"\n'
            "}\n"
            'seed "two/"\n'
            'seed "three/"\n'
        )
        self.assertEqual(
            self.inside(body),
            {
                ((True, ("dest", "two")), "one"),
                ((True, ("dest", "three")), "one"),
            },
        )


class InventoryDeclarationTest(ContractSupportTest):
    """Bind the editing carve-out to the paths the inventory declares."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    def test_an_edit_reading_an_undeclared_source_buys_no_staging(self) -> None:
        self.assert_rejected(
            self.outside(
                'sed -i "1r $root/AGENTS.md" "$update_source/NOTICE"\n'
                'fixture_git "$update_source" add -- NOTICE\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path no inventory line declares",
        )

    def test_an_in_place_edit_of_an_undeclared_path_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'sed -i "s/a/b/" "$update_source/NOTICE"\n'
                'fixture_git "$update_source" add -- NOTICE\n',
                'sed -i "s/a/b/" "$update_source/template/README.md.jinja"\n'
                'fixture_git "$update_source" add -- template/README.md.jinja\n',
                'python3 - "$update_source/NOTICE" <<\'PY\'\nPY\n'
                'fixture_git "$update_source" add -- "$update_source/NOTICE"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "adds a path no inventory line declares",
                )

    def test_editing_and_staging_a_declared_path_stays_accepted(self) -> None:
        for index, form in enumerate(
            (
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n',
                'sed -i "s/a/b/"'
                ' "$update_source/template/.project-agent-workflow/README.md"\n'
                'fixture_git "$update_source" add --'
                ' template/.project-agent-workflow/README.md\n',
                'policy="$update_source/copier.yml"\n'
                'sed -i "s/a/b/" "$policy"\n'
                'fixture_git "$update_source" add -- "$policy"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.outside(form))

    def test_a_staged_path_written_with_an_expansion_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'staged=$(printf %s copier.yml)\n'
                'sed -i "s/a/b/" "$update_source/$staged"\n'
                'fixture_git "$update_source" add -- "$staged"\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path no inventory line declares",
        )

    def test_an_inventory_declaring_nothing_rejects_every_staging(self) -> None:
        self.declared = ()
        self.assert_rejected(
            self.outside(
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path no inventory line declares",
        )

    def test_declared_paths_reads_one_written_path_per_line(self) -> None:
        self.assertEqual(
            declared_paths(["copier.yml", "", "  a/b.md  ", "c//d.md"]),
            frozenset({("copier.yml",), ("a", "b.md"), ("c", "d.md")}),
        )

    def test_an_edit_of_an_undeclared_path_is_rejected_without_any_staging(self) -> None:
        for index, form in enumerate(
            (
                'sed -i "s/a/b/" "$update_source/NOTICE"\n',
                'sed -i "1r $root/AGENTS.md" "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -a -qm "sneak"\n',
                'sed -i "s/a/b/" "$update_source/NOTICE"\n'
                'fixture_git "$update_source" commit -qm "sneak" -- NOTICE\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "an edit outside the inventory region writes a path no "
                    "inventory line declares",
                )

    def test_a_staging_written_inside_a_called_body_is_read(self) -> None:
        for index, form in enumerate(
            (
                "sneak_stage() {\n"
                '  fixture_git "$update_source" add -- "$1"\n'
                "}\n"
                "sneak_stage NOTICE\n",
                "sneak_stage() {\n"
                '  fixture_git "$update_source" add -- NOTICE\n'
                "}\n"
                "sneak_stage\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region adds a path",
                )

    def test_a_commit_that_stages_on_its_own_is_read_as_a_staging(self) -> None:
        for index, form in enumerate(
            (
                'dd if="$root/AGENTS.md" of="$update_source/README.md"\n'
                'fixture_git "$update_source" commit -a -qm x\n',
                'weirdtool "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -a -qm x\n',
                'weirdtool "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -m x README.md\n',
                'weirdtool "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -qm x -- README.md\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region adds",
                )

    def test_a_commit_that_stages_nothing_of_its_own_stays_accepted(self) -> None:
        for index, form in enumerate(
            (
                'fixture_git "$update_source" commit --allow-empty -qm "plain"\n',
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
                'fixture_git "$update_source" commit -m "declared"\n',
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" commit -qm x -- copier.yml\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.outside(form))

    def test_committed_operands_reads_the_forms_that_stage(self) -> None:
        for text, expected in (
            ("commit -m x", ((), False)),
            ("commit --allow-empty -qm x", ((), False)),
            ("commit -a -qm x", ((), True)),
            ("commit -qm x -- a.md", (("a.md",), False)),
            ("commit -m x a.md", (("a.md",), False)),
            ("commit --message=x a.md", (("a.md",), False)),
            ("commit --unknown-option -m x", ((), True)),
        ):
            with self.subTest(written=text):
                words = tuple(SimpleNamespace(text=part) for part in text.split())
                operands, everything = copier_fixture_validator._committed_operands(words)
                self.assertEqual(
                    (tuple(token.text for token in operands), everything), expected
                )

    def test_an_unreadable_inventory_declares_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_inventory(Path(directory) / "absent.txt"), frozenset())

    def test_the_shipped_inventory_declares_the_committed_paths(self) -> None:
        declared = read_inventory()
        self.assertIn(("copier.yml",), declared)
        self.assertEqual(declared, read_inventory(INVENTORY_PATH))


class PositionalParameterTest(ContractSupportTest):
    """A word reaches the update source through the parameters a call writes."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    def test_an_update_source_reached_through_a_parameter_is_read(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                "  where=$1\n"
                '  sed -i "s/a/b/" "$where/NOTICE"\n'
                '  fixture_git "$where" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                "  shift\n"
                "  where=$1\n"
                '  sed -i "s/a/b/" "$where/NOTICE"\n'
                '  fixture_git "$where" add -- NOTICE\n'
                "}\n"
                'sneak filler "$update_source"\n',
                "sneak() {\n"
                "  lane=$1\n"
                '  dir="$tmp/$lane"\n'
                '  sed -i "s/a/b/" "$dir/NOTICE"\n'
                '  fixture_git "$dir" add -- NOTICE\n'
                "}\n"
                "sneak update-source\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "no inventory line declares",
                )

    def test_a_parameter_naming_a_declared_path_stays_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "edit_declared() {\n"
                '  sed -i "s/a/b/" "$1/copier.yml"\n'
                '  fixture_git "$1" add -- copier.yml\n'
                "}\n"
                'edit_declared "$update_source"\n'
            )
        )

    def test_a_lane_no_call_site_points_at_the_update_source_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "make_lane() {\n"
                "  lane=$1\n"
                '  out="$tmp/$lane"\n'
                '  mkdir -p "$out"\n'
                '  sed -i "s/a/b/" "$out/NOTICE"\n'
                '  fixture_git "$out" add -- NOTICE\n'
                "}\n"
                "make_lane one\n"
                "make_lane two\n"
            )
        )

    def test_a_parameter_no_call_site_binds_names_no_path(self) -> None:
        for word in ('"$1"', '"$1/x"', '"$0"', '"$9/y"'):
            with self.subTest(word=word):
                self.assertEqual(
                    copier_fixture_validator._settle_word(word, {}, frozenset()),
                    frozenset(),
                )

    def test_an_update_source_passed_down_a_call_chain_is_read(self) -> None:
        self.assert_rejected(
            self.outside(
                "sneak_inner() {\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak_outer() { sneak_inner "$1"; }\n'
                'sneak_outer "$update_source"\n'
            ),
            RULE_INVENTORY_REGION,
            "no inventory line declares",
        )

    def test_a_call_this_checker_cannot_read_hides_no_sibling(self) -> None:
        self.assert_rejected(
            self.outside(
                "sneak() {\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n'
                'sneak "${9-x}"\n'
            ),
            RULE_INVENTORY_REGION,
            "no inventory line declares",
        )

    def test_a_shift_the_shell_may_skip_reads_both_distances(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                '  if [ -n "${NOPE-}" ]; then\n'
                "    shift\n"
                "  fi\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                '  [ -z "${NOPE-}" ] || shift\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                '  [ -n "${NOPE-}" ] && shift\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "no inventory line declares",
                )

    def test_a_shift_a_loop_repeats_reads_every_turn(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                "  for held in a b; do shift; done\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak one two "$update_source"\n',
                "sneak() {\n"
                '  while [ "$#" -gt 0 ]; do\n'
                '    sed -i "s/a/b/" "$1/NOTICE"\n'
                '    fixture_git "$1" add -- NOTICE\n'
                "    shift\n"
                "  done\n"
                "}\n"
                'sneak one two "$update_source"\n',
                "sneak() {\n"
                '  until [ "$#" -le 1 ]; do shift; done\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak one two "$update_source"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "no inventory line declares",
                )

    def test_a_parameter_this_checker_cannot_place_is_reported(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                "  steps=0\n"
                '  shift "$steps"\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                "}\n"
                'sneak "$update_source"\n',
                "reader() { sed -i \"s/a/b/\" \"$1/NOTICE\"; }\n"
                'relay() { reader "$@"; }\n'
                'relay "$update_source"\n',
                "sneak() {\n"
                '  sed -i "s/a/b/" "${1-x}/NOTICE"\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                '  sed -i "s/a/b/" "$@"\n'
                "}\n"
                'sneak "$update_source/NOTICE"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_staging_from_a_parameter_it_cannot_place_is_reported(self) -> None:
        for index, form in enumerate(
            (
                'sneak() { fixture_git "$1" add -- NOTICE; }\n'
                'sneak "${9-x}"\n',
                'sneak() { fixture_git "$update_source" add -- "$@"; }\n'
                "sneak NOTICE\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "names a repository or a path this checker cannot place",
                )

    def test_an_interpreter_handed_the_parameter_list_stays_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "run_helper() {\n"
                "  where=$1\n"
                "  shift\n"
                '  python3 "$root/scripts/adopt-to-namespaced-layout.py" \\\n'
                '    --destination "$where" "$@"\n'
                "}\n"
                'run_helper "$tmp/lane" --dry-run\n'
            )
        )

    def test_a_parameter_that_names_no_path_stays_accepted(self) -> None:
        for index, form in enumerate(
            (
                "bump() {\n"
                '  sed -i "s/^version: .*/version: $1/" "$update_source/copier.yml"\n'
                '  fixture_git "$update_source" add -- copier.yml\n'
                "}\n"
                "label=x1.2.3\n"
                'bump "${label#x}"\n',
                "tag_it() {\n"
                '  sed -i "s/a/b/" "$update_source/copier.yml"\n'
                '  fixture_git "$update_source" commit -qm "$1" -- copier.yml\n'
                "}\n"
                "label=xrelease\n"
                'tag_it "${label#x}"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.outside(form))

    def test_a_guarded_shift_over_a_declared_path_stays_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "edit_declared() {\n"
                '  [ -n "${NOPE-}" ] && shift\n'
                '  sed -i "s/a/b/" "$1/copier.yml"\n'
                '  fixture_git "$1" add -- copier.yml\n'
                "}\n"
                'edit_declared "$update_source"\n'
            )
        )

    def test_a_body_that_calls_itself_places_no_parameter(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                '  if [ -n "${NOPE-}" ]; then sneak "$1"; fi\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                "}\n"
                "sneak one\n",
                "sneak() {\n"
                '  if [ -n "${NOPE-}" ]; then relay "$1"; fi\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                "}\n"
                'relay() { sneak "$1"; }\n'
                "sneak one\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    "structure",
                    "has no bounded graph",
                )


class OperandReadingTest(ContractSupportTest):
    """A rule reads the words a command writes at, not every word it takes."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    UNPLACEABLE = 'seed=xupdate-source\nlane="${seed#x}"\nwhere="$tmp/$lane"\n'

    def test_a_flag_is_not_read_as_an_option_value_that_hides_the_destination(
        self,
    ) -> None:
        for index, form in enumerate(
            (
                'sed -i -r "1r $root/AGENTS.md" "$where/NOTICE"\n',
                'sed -i -s "1r $root/AGENTS.md" "$where/NOTICE"\n',
                'ed -s "$where/NOTICE" </dev/null\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_destination_written_as_an_option_value_is_read(self) -> None:
        for command in ("cp", "install", "ln", "mv"):
            for option in ("-t", "--target-directory"):
                with self.subTest(command=command, option=option):
                    self.assert_rejected(
                        self.outside(
                            self.UNPLACEABLE + f'{command} {option} "$where" copier.yml\n'
                        ),
                        RULE_INVENTORY_REGION,
                        "takes a destination this checker cannot place",
                    )

    def test_a_target_directory_option_is_resolved_before_operand_reading(self) -> None:
        for form in (
            'topt=--target-directory=\nlane=update-source\n'
            'install "$topt$tmp/$lane" AGENTS.md\n',
            'topt=-t\nlane=update-source\n'
            'install "$topt$tmp/$lane" AGENTS.md\n',
            'topt=--target-directory\n'
            'install "$topt" "$tmp/update-source" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                )

    def test_an_option_split_across_resolved_parts_is_read_as_one_option(
        self,
    ) -> None:
        """The option name is read after resolution, not per written part.

        Each form below reaches its command as the same target-directory
        option as a word written with one literal dash run, so each writes
        into the update source and must be reported the same way.
        """

        for form in (
            # A name holding every character after the first dash.
            'opt=-target-directory=\nlane=update-source\n'
            'install "-$opt$tmp/$lane" AGENTS.md\n',
            # A name holding only the short option letter.
            'o=t\nlane=update-source\n'
            'install "-$o$tmp/$lane" AGENTS.md\n',
            # A name holding the first half of the long option name.
            'pre=--target\nlane=update-source\n'
            'install "$pre-directory=$tmp/$lane" AGENTS.md\n',
            # An option name that runs into an unread value with no equals
            # sign: undecided, so the directory it would name is still read.
            'topt=--target-directory\nlane=update-source\n'
            'install "$topt$tmp/$lane" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                )

    def test_an_empty_assignment_does_not_erase_the_words_that_carry_it(
        self,
    ) -> None:
        """`name=` binds the empty string rather than an unreadable value.

        Writing an empty name in front of an option used to leave the whole
        word unreadable, which placed no destination and reported nothing.
        """

        for form in (
            'e=\nlane=update-source\n'
            'install "${e}--target-directory=$tmp/$lane" AGENTS.md\n',
            'e=""\nlane=update-source\n'
            'install "${e}--target-directory=$tmp/$lane" AGENTS.md\n',
            "e=''\nlane=update-source\n"
            'install "${e}-t$tmp/$lane" AGENTS.md\n',
            'e=\ninstall "${e}--target-directory" "$tmp/update-source" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                )

    def test_an_assembled_word_naming_no_option_keeps_its_reading(self) -> None:
        """Joining resolved parts never removes a destination already read.

        The first word below reaches `t` only after letters this checker does
        not model, and the second names no option at all. Reading either as
        the target-directory option would take the next word as a directory
        and stop the written destination from being read, so both keep the
        reading they already had.
        """

        for form, expected in (
            (
                'own=oroot\ninstall "-$own" AGENTS.md "$tmp/update-source"\n',
                "a write into the update source stands outside the inventory "
                "region",
            ),
            (
                'b=-target-directory=\n'
                'install "-$b" AGENTS.md "$tmp/update-source"\n',
                "a write this checker cannot place",
            ),
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form), RULE_INVENTORY_REGION, expected
                )

    def test_an_empty_assignment_does_not_widen_a_path_reading(self) -> None:
        """Only option classification supplies the empty value.

        A path word carrying an empty name stays a word this checker refuses
        to read, so the operation keeps its fail-closed disposition instead of
        settling to a destination the general path model never proved.
        """

        self.assert_rejected(
            self.outside('e=\ncp "$root/AGENTS.md" "${e}$update_source/AGENTS.md"\n'),
            RULE_INVENTORY_REGION,
            "a write this checker cannot place is written where the update "
            "source is named",
        )

    def test_an_empty_assignment_keeps_an_ordinary_path_accepted(self) -> None:
        self.assert_accepted(
            self.outside('e=\ncat "${e}$root/pyproject.toml" >/dev/null\n')
        )

    def test_an_ambiguous_target_directory_option_stays_unplaceable(self) -> None:
        for form, expected in (
            (
                'topt=-t\n'
                'if [ -n "${NOPE-}" ]; then topt=--target-directory; fi\n'
                'install "$topt" "$tmp/update-source" AGENTS.md\n',
                "a write this checker cannot place",
            ),
            (
                'install_helper() { install "$1" "$tmp/update-source" AGENTS.md; }\n'
                'install_helper -t\n'
                'install_helper --target-directory\n',
                "a write this checker cannot place",
            ),
            # A cluster reaching `t` only after unmodelled letters keeps the
            # reading it already had, so the real destination is still read.
            (
                'own=oroot\ninstall "-$own" AGENTS.md "$tmp/update-source"\n',
                "a write into the update source stands outside the inventory "
                "region",
            ),
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form), RULE_INVENTORY_REGION, expected
                )

    def test_a_repository_written_as_an_option_value_is_read(self) -> None:
        for form in (
            'git --git-dir="$where/.git" add -- NOTICE\n',
            'git --work-tree="$where" add -- NOTICE\n',
            'git -C "$where" add -- NOTICE\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "names a repository or a path this checker cannot place",
                )

    def test_an_expression_and_a_message_stay_unread_as_paths(self) -> None:
        self.assert_accepted(
            self.outside(
                "bump() {\n"
                '  sed -i -r "s/^version: .*/version: $1/" "$update_source/copier.yml"\n'
                '  fixture_git "$update_source" commit -qm "$1" -- copier.yml\n'
                "}\n"
                "bump 9.9.9\n"
            )
        )

    def test_a_copy_source_stays_unread_as_a_destination(self) -> None:
        self.assert_accepted(
            self.outside(self.UNPLACEABLE + 'cp "$where/copier.yml" "$tmp/held.yml"\n')
        )

    def test_a_quoted_option_is_read_as_the_option_it_spells(self) -> None:
        for form in (
            'install "-t" "$where" AGENTS.md\n',
            "install '-t' \"$where\" AGENTS.md\n",
            'install -"t" "$where" AGENTS.md\n',
            'install \\-t "$where" AGENTS.md\n',
            'cp "--target-directory=$where" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_quoted_git_repository_option_is_read(self) -> None:
        self.assert_rejected(
            self.outside(self.UNPLACEABLE + 'git "-C" "$where" add -- AGENTS.md\n'),
            RULE_INVENTORY_REGION,
            "names a repository or a path this checker cannot place",
        )

    def test_a_staging_that_names_no_repository_is_reported(self) -> None:
        for form in (
            'git add -- AGENTS.md\n',
            '( cd "$where" && git add -- AGENTS.md )\n',
            'git commit -qm x -- AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "names no repository outside the directory it stands in",
                )

    def test_a_staging_that_names_a_relative_repository_is_reported(self) -> None:
        for form in (
            '( cd "$where" && git -C . add -- AGENTS.md )\n',
            '( cd "$where" && git -C ./ add -- AGENTS.md )\n',
            '( cd "$where" && git --git-dir=.git add -- AGENTS.md )\n',
            '( cd "$where" && git -C held add -- AGENTS.md )\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "names no repository outside the directory it stands in",
                )

    def test_an_option_this_checker_cannot_name_keeps_every_operand_read(self) -> None:
        for form in (
            'install "-t$empty" "$where" AGENTS.md\n',
            'install "-t${empty}" "$where" AGENTS.md\n',
            'cp "-t$empty" "$where" AGENTS.md\n',
            'mv "-t$empty" "$where" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside("empty=\n" + self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_an_option_an_expansion_opens_keeps_every_operand_read(self) -> None:
        for form in (
            'install "${empty}-t" "$where" AGENTS.md\n',
            'install "$empty-t" "$where" AGENTS.md\n',
            'install "$opt" "$where" AGENTS.md\n',
            'install "$opt=$where" AGENTS.md\n',
            'cp "${empty}-t" "$where" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside("empty=\nopt=-t\n" + self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_written_path_segment_keeps_a_copy_source_out_of_the_reading(
        self,
    ) -> None:
        self.assert_accepted(
            self.outside(
                self.UNPLACEABLE + 'cp "$where/copier.yml" "$tmp/held.yml"\n'
            )
        )

    def test_an_alias_of_the_update_source_is_rejected(self) -> None:
        for form in (
            'ln -s "$update_source" "$tmp/held"\n',
            'ln "$update_source/copier.yml" "$tmp/held.yml"\n',
            'mv "$update_source" "$tmp/held"\n',
            'ln -s -t "$tmp" "$update_source"\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "an alias of the update source stands outside the "
                    "inventory region",
                )

    def test_an_inline_interpreter_program_carrying_update_source_is_rejected(
        self,
    ) -> None:
        for form in (
            "python3 -c \"import os; os.symlink('$update_source', '$tmp/held')\"\n",
            "sh -c \"ln -s '$update_source' '$tmp/held'\"\n",
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "inline interpreter program carries a name",
                )

    def test_interpreter_file_and_standard_input_forms_remain_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'python3 "$root/scripts/tool.py" "$update_source"\n'
                'python3 - "$update_source/copier.yml"\n'
            )
        )


class IndirectDispatchTest(ContractSupportTest):
    """A call this checker cannot read settles no name across it."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    RELAY = (
        "mutate() { held=update-source; }\n"
        "relay() { runner=mutate; $runner; }\n"
        "run() {\n"
        "  held=other\n"
        "  relay\n"
        '  sed -i "s/a/b/" "$tmp/$held/NOTICE"\n'
        "}\n"
        "run\n"
    )

    def test_a_call_dispatched_from_a_name_this_checker_cannot_read_unsettles_it(
        self,
    ) -> None:
        self.assert_rejected(
            self.outside(self.RELAY),
            RULE_INVENTORY_REGION,
            "takes a destination this checker cannot place",
        )

    def test_a_call_written_out_keeps_the_names_it_never_assigns_settled(self) -> None:
        self.assert_accepted(
            self.outside(
                "keep() { spare=held; }\n"
                "run() {\n"
                "  held=other\n"
                "  keep\n"
                '  sed -i "s/a/b/" "$tmp/$held/NOTICE"\n'
                "}\n"
                "run\n"
            )
        )


class DirectInvocationTest(ContractSupportTest):
    def test_direct_snapshot_invocation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'grep -q \'"state": "pending"\' "$attempt_state"',
                'python3 "$project/.project-agent-workflow/scripts/'
                'snapshot-validation-witness-provenance.py" --stage before\n'
                'grep -q \'"state": "pending"\' "$attempt_state"',
            ),
            RULE_DIRECT_INVOCATION,
            "migration snapshot script directly",
        )

    def test_direct_copier_dispatch_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                VERSION_COMMITS,
                VERSION_COMMITS + '\ncopier copy -q -f "$update_source" "$project"\n',
            ),
            RULE_DIRECT_INVOCATION,
            "`copier` binary directly",
        )


class CommandShadowingTest(ContractSupportTest):
    """The commands a bound observation runs may not be rebound.

    Every other rule reads the written text of an operation, so a fixture that
    keeps that text and gives the command name another meaning makes the
    observation vacuous. A shell rebinds a command name through a function
    declaration, an alias, a `hash` entry, or a file a search-path lookup
    reaches first, and each of them is covered here for every protected name.
    """

    # A persistent search-path assignment is what makes a written file the
    # command a bare name resolves to, so the helper cases carry one.
    SEARCHED = (
        '\nmkdir -p "$tmp/bin"\n'
        'PATH="$tmp/bin:$PATH"\n'
        "export PATH\n"
    )

    def observed(self) -> list[str]:
        return sorted(copier_fixture_validator.OBSERVED_COMMANDS)

    def declarable(self) -> list[str]:
        return [name for name in self.observed() if name.isidentifier()]

    def helpers(self) -> list[str]:
        return sorted(copier_fixture_validator.SHADOWED_HELPER_COMMANDS)

    def searched(self, addition: str) -> str:
        return COMPLIANT + self.SEARCHED + addition

    def test_the_release_commands_are_protected(self) -> None:
        self.assertLessEqual(
            copier_fixture_validator.RELEASE_COMMANDS,
            copier_fixture_validator.OBSERVED_COMMANDS,
        )

    def test_only_the_builtin_names_are_exempt_from_the_helper_reading(self) -> None:
        """A name the shell resolves before it searches is not shadowed by a file."""

        self.assertEqual(
            copier_fixture_validator.OBSERVED_COMMANDS
            - copier_fixture_validator.SHADOWED_HELPER_COMMANDS,
            copier_fixture_validator.OBSERVED_BUILTINS,
        )
        self.assertLessEqual(
            copier_fixture_validator.OBSERVED_BUILTINS,
            copier_fixture_validator.OBSERVED_COMMANDS,
        )

    def test_the_reproduced_admission_is_rejected(self) -> None:
        mutated = COMPLIANT + "\ngrep() { :; }\ntest() { :; }\ntouch() { :; }\n"
        rejected = [
            finding.message
            for finding in check(mutated)
            if finding.rule == RULE_COMMAND_SHADOWING
        ]
        self.assertEqual(len(rejected), 3, self.messages(mutated))

    def test_declaring_each_observed_command_is_rejected(self) -> None:
        for name in self.declarable():
            with self.subTest(command=name):
                self.assert_rejected(
                    COMPLIANT + f"\n{name}() {{\n  :\n}}\n",
                    RULE_COMMAND_SHADOWING,
                    f"declares `{name}` as a function",
                )

    def test_the_names_the_bound_control_flow_runs_are_declarable(self) -> None:
        """The poll bound, the release, and the inventory loop are all rebindable.

        A shell resolves these names before it searches a path, so a helper
        file never reaches them and only the declaration case protects them.
        """

        for name in ("read", "exit", "trap", "cd", "wait", "kill"):
            with self.subTest(command=name):
                self.assertIn(name, self.declarable())
                self.assert_rejected(
                    COMPLIANT + f"\n{name}() {{\n  :\n}}\n",
                    RULE_COMMAND_SHADOWING,
                    f"declares `{name}` as a function",
                )

    def test_a_declaration_that_wraps_the_real_command_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\ngrep() {\n  command grep "$@" || true\n}\n',
            RULE_COMMAND_SHADOWING,
            "declares `grep` as a function",
        )

    def test_aliasing_each_observed_command_is_rejected(self) -> None:
        for name in self.observed():
            with self.subTest(command=name):
                self.assert_rejected(
                    COMPLIANT + f"\nalias {name}='true'\n",
                    RULE_STRUCTURE,
                    "`alias`",
                )

    def test_a_helper_named_for_each_observed_command_is_rejected(self) -> None:
        forms = (
            'cat >"$tmp/bin/{name}" <<\'EOF_SHIM\'\n'
            "#!/bin/sh\n"
            "exit 0\n"
            "EOF_SHIM\n",
            'cp "$root/tests/fixtures/helper" "$tmp/bin/{name}"\n',
            'touch "$tmp/bin/{name}"\n',
            'ln -s "$root/tests/fixtures/helper" "$tmp/bin/{name}"\n',
        )
        for name in self.helpers():
            for index, form in enumerate(forms):
                with self.subTest(command=name, form=index):
                    self.assert_rejected(
                        self.searched(form.format(name=name)),
                        RULE_COMMAND_SHADOWING,
                        f"writes a `{name}` helper",
                    )

    def test_a_helper_moved_into_a_searched_directory_is_rejected(self) -> None:
        """A move names its destination directory rather than the written file."""

        self.assert_rejected(
            self.searched('mv "$tmp/staging/grep" "$tmp/bin"\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_helper_named_through_a_variable_is_rejected(self) -> None:
        self.assert_rejected(
            self.searched('shim_dir="$tmp/bin"\ntouch "$shim_dir/sed"\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `sed` helper",
        )

    def test_a_helper_named_under_an_unplaceable_search_path_is_rejected(self) -> None:
        """A search path this checker cannot place reaches whatever it reaches.

        Exporting a value in one command leaves this checker unable to settle
        the directories the shell will search, so a written file that carries
        an observed name is read as reachable from the name it is written with.
        """

        self.assert_rejected(
            COMPLIANT
            + '\nexport PATH="$tmp/shim:$PATH"\n'
            + 'cp "$root/tests/fixtures/helper" "$tmp/shim/sed"\n',
            RULE_COMMAND_SHADOWING,
            "writes a `sed` helper",
        )

    def test_a_search_path_written_in_front_of_an_observation_is_rejected(self) -> None:
        """A prefixed search path decides what the observation itself runs."""

        self.assert_rejected(
            self.mutate(
                'grep -q \'"state": "consumed"\' "$attempt_state"\n',
                'PATH="$tmp/shim:$PATH" grep -q \'"state": "consumed"\''
                ' "$attempt_state"\n',
            ),
            RULE_COMMAND_SHADOWING,
            "writes a search path in front of `grep`",
        )

    def test_binding_a_command_name_through_hash_is_rejected(self) -> None:
        """A hashed entry is read before the search path the fixture writes."""

        self.assert_rejected(
            COMPLIANT + '\nhash -p "$tmp/true" grep\n',
            RULE_COMMAND_SHADOWING,
            "binds a command name through `hash`",
        )

    def test_the_bracket_test_cannot_be_rebound_at_all(self) -> None:
        """The checked projections close the two remaining vectors for `[`.

        The checked function table admits a declaration only for a name it
        reads as an exact literal word, so `[` is rejected as structure before
        this rule reads it, and the shell resolves `[` before it searches a
        path, so a written file of that name shadows nothing.
        """

        self.assertIn("[", copier_fixture_validator.OBSERVED_COMMANDS)
        self.assertNotIn("[", self.declarable())
        self.assertNotIn("[", self.helpers())
        self.assert_rejected(COMPLIANT + "\n[() {\n  :\n}\n", RULE_STRUCTURE, "")

    def test_a_helper_the_inspection_lane_reaches_by_prefix_is_accepted(self) -> None:
        """A directory reached only in front of one command shadows nothing.

        The fixture writes a deliberately failing `git` helper and reaches it
        by writing the search path in front of the single command that must
        see it, so the shell's own search path never holds that directory.
        """

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/failing-git"\n'
                'cat >"$tmp/failing-git/git" <<\'EOF_FAILING_GIT\'\n'
                "#!/bin/sh\n"
                "exit 7\n"
                "EOF_FAILING_GIT\n"
                'PATH="$tmp/failing-git:$PATH" python3 -c "pass"\n'
            )
        )

    def test_a_git_helper_a_searched_directory_holds_is_rejected(self) -> None:
        """The same helper written where the shell searches is a rebinding."""

        self.assert_rejected(
            self.searched(
                'cat >"$tmp/bin/git" <<\'EOF_GIT\'\n'
                "#!/bin/sh\n"
                "exit 0\n"
                "EOF_GIT\n"
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `git` helper",
        )

    def test_a_helper_written_inside_an_expansion_is_rejected(self) -> None:
        """A command written inside an expansion writes the same file.

        Reading operands from the written command runs alone would leave a
        command the shell runs inside a substitution writing nothing at all.
        """

        for index, form in enumerate(
            (
                'written=$(touch "$tmp/bin/grep")\n',
                'written=$(cat "$root/helper" >"$tmp/bin/grep")\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_search_path_written_inside_an_expansion_is_rejected(self) -> None:
        self.assert_rejected(
            self.searched('found=$(PATH="$tmp/shim:$PATH" cat "$tmp/guardian.pid")\n'),
            RULE_COMMAND_SHADOWING,
            "in front of `cat`",
        )

    def test_a_search_path_written_in_front_of_a_launcher_is_rejected(self) -> None:
        """A launcher runs one of its own words, so the first word proves nothing."""

        for index, form in enumerate(
            (
                'PATH="$tmp/shim:$PATH" command grep -q x "$attempt_state"\n',
                'PATH="$tmp/shim:$PATH" env grep -q x "$attempt_state"\n',
                'env PATH="$tmp/shim:$PATH" grep -q x "$attempt_state"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    COMPLIANT + "\n" + form,
                    RULE_COMMAND_SHADOWING,
                    "in front of `grep`",
                )

    def test_a_search_path_written_in_front_of_a_wrapper_is_rejected(self) -> None:
        """A declared wrapper forwards to the command its body writes."""

        self.assert_rejected(
            COMPLIANT
            + '\nPATH="$tmp/shim:$PATH" fixture_git "$update_source" tag v9\n',
            RULE_COMMAND_SHADOWING,
            "in front of the declared `fixture_git` wrapper",
        )

    def test_a_helper_placed_by_a_target_directory_option_is_rejected(self) -> None:
        """The directory is read from the option word, however it is written."""

        for index, form in enumerate(
            (
                'cp -t "$tmp/bin" "$tmp/staging/grep"\n',
                'cp -t"$tmp/bin" "$tmp/staging/grep"\n',
                'cp --target-directory="$tmp/bin" "$tmp/staging/grep"\n',
                'install --target-directory="$tmp/bin" "$tmp/staging/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_helper_written_through_the_working_directory_is_rejected(self) -> None:
        """A relative path names the directory the shell is in, which may be searched."""

        self.assert_rejected(
            self.searched('cd "$tmp/bin"\ncp "$root/tests/fixtures/helper" grep\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_relative_search_path_element_is_read_as_unplaceable(self) -> None:
        self.assert_rejected(
            COMPLIANT
            + '\nPATH="bin:$PATH"\nexport PATH\n'
            + 'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\n',
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_search_path_bound_without_an_assignment_is_read_as_unplaceable(
        self,
    ) -> None:
        """A shell also binds the search path through `read` and through a loop."""

        for index, form in enumerate(
            ('read PATH <"$tmp/new-path"\n', "for PATH in a b; do\n  :\ndone\n")
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(
                        'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\n'
                        + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_binding_a_command_name_behind_a_launcher_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'hash -p "$tmp/true" grep\n',
                'command hash -p "$tmp/true" grep\n',
                'builtin hash -p "$tmp/true" git\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    COMPLIANT + "\n" + form,
                    RULE_COMMAND_SHADOWING,
                    "binds a command name through `hash`",
                )

    def test_a_search_path_written_in_front_of_a_forwarder_is_rejected(self) -> None:
        """A program that runs its own argument forwards the search path too.

        No bounded list of such programs exists, so every word of the run is
        read rather than only the command word and a known launcher list.
        """

        for name in ("nice", "ionice", "timeout 5", "stdbuf -oL"):
            with self.subTest(command=name):
                self.assert_rejected(
                    COMPLIANT
                    + f'\nPATH="$tmp/shim:$PATH" {name} grep -q x "$attempt_state"\n',
                    RULE_COMMAND_SHADOWING,
                    "in front of `grep`",
                )

    def test_a_hash_option_this_checker_cannot_read_is_rejected(self) -> None:
        """A word that carries an expansion may be the option that rebinds."""

        self.assert_rejected(
            COMPLIANT + '\nhash_option=-p\nhash "$hash_option" "$tmp/true" grep\n',
            RULE_COMMAND_SHADOWING,
            "binds a command name through `hash`",
        )

    def test_a_target_directory_option_this_checker_cannot_read_is_rejected(
        self,
    ) -> None:
        """An unreadable word that could be the option leaves the destination unknown."""

        for index, form in enumerate(
            (
                'placement=-t\ncp "$placement" "$tmp/bin" "$tmp/staging/grep"\n',
                'placement=--target-directory\n'
                'install "$placement" "$tmp/bin" "$tmp/staging/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_unsetting_the_search_path_is_read_as_unplaceable(self) -> None:
        self.assert_rejected(
            self.searched(
                'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\nunset PATH\n'
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_destination_this_checker_cannot_place_is_rejected(self) -> None:
        """A path this checker cannot settle is not a path proved to lie outside.

        A parent segment and a command substitution both leave the destination
        unsettled, and the file still lands in the searched directory.
        """

        for index, form in enumerate(
            (
                'printf "x" >"$tmp/bin/../bin/grep"\n',
                'cp "$root/helper" "$tmp/bin/x/../grep"\n',
                'touch "$tmp/bin/x/../grep"\n',
                'printf x | tee "$tmp/bin/x/../grep"\n',
                'ln -s "$root/helper" "$tmp/bin/x/../grep"\n',
                'cp "$root/helper" "$(printf %s "$tmp/bin")/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_redirection_written_on_a_compound_is_rejected(self) -> None:
        """A group and a subshell carry a redirection no single command holds."""

        for index, form in enumerate(
            (
                '{ printf "x"; } >"$tmp/bin/grep"\n',
                '( printf "x" ) >"$tmp/bin/grep"\n',
                'for name in one; do printf "x"; done >"$tmp/bin/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_search_path_written_in_front_of_a_carried_program_is_rejected(
        self,
    ) -> None:
        """An interpreter runs the commands written inside the word it is given."""

        for index, form in enumerate(
            (
                'PATH="$tmp/shim:$PATH" sh -c \'grep -q x "$1"\' _ "$attempt_state"\n',
                'PATH="$tmp/shim:$PATH" bash -c "grep -q x $attempt_state"\n',
                'PATH="$tmp/shim:$PATH" awk \'BEGIN { system("git status") }\'\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a search path in front of",
                )

    def test_a_launcher_that_only_carries_the_search_path_name_is_accepted(
        self,
    ) -> None:
        """A launcher binds no name, so the name it carries stays data."""

        for index, form in enumerate(
            (
                'command grep PATH "$attempt_state" || true\n',
                'env grep PATH "$attempt_state" || true\n',
                'timeout 5 grep PATH "$attempt_state" || true\n',
                'command printf "%s" PATH\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched(form + 'touch "$tmp/archive/git"\n')
                )

    def test_a_compound_redirection_is_read_at_every_binding_it_may_use(
        self,
    ) -> None:
        """The shell expands the word before the body the word is written after.

        A value bound inside the body is therefore not the only value the
        redirection may use, and a word repeated under a different value names
        a different file each time it is written.
        """

        for index, form in enumerate(
            (
                'place="$tmp/bin"\n'
                '{ place="$tmp/archive"; printf x; } >"$place/grep"\n',
                'place="$tmp/archive"\n'
                'printf x >"$place/grep"\n'
                'place="$tmp/bin"\n'
                '{ printf y; } >"$place/grep"\n',
                'place="$tmp/archive"\n'
                'printf x >"$place/grep"\n'
                'place="$tmp/bin"\n'
                '( printf y ) >"$place/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_compound_redirection_outside_the_search_path_is_accepted(self) -> None:
        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n{ printf x; } >"$tmp/archive/git"\n'
            )
        )

    def test_a_carried_program_this_checker_cannot_unquote_is_rejected(self) -> None:
        """A word that could be a program text is refused, not searched.

        The shell removes an escape and expands a name before it reads a
        command name, so a written text that spells no observed name may still
        run one.
        """

        for index, form in enumerate(
            (
                'PATH="$tmp/shim:$PATH" sh -c \'\\grep -q x "$attempt_state"\'\n',
                'PATH="$tmp/shim:$PATH" sh -c \'reader=grep; $reader -q x f\'\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a search path in front of",
                )

    def test_a_name_bound_behind_a_launcher_option_is_read(self) -> None:
        """An option written after a launcher belongs to the launcher."""

        self.assert_rejected(
            self.searched(
                'command -p read PATH <"$tmp/new-path"\n'
                'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\n'
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_compound_redirection_reads_the_value_its_compound_starts_with(
        self,
    ) -> None:
        """A name rebound before the compound names one file, not every file."""

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                '{ printf x; } >"$place/grep"\n'
            )
        )

    def test_a_loop_redirection_reads_the_value_its_body_binds(self) -> None:
        """A loop expands its redirection word once for each pass it makes."""

        self.assert_rejected(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/archive"\n'
                'for step in one two; do place="$tmp/bin"; printf x; done '
                '>"$place/grep"\n'
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_an_escape_written_before_a_carried_name_is_read(self) -> None:
        """A shell removes the escape before it reads the command name."""

        self.assert_rejected(
            self.searched('PATH="$tmp/shim:$PATH" sh -c \'\\grep\'\n'),
            RULE_COMMAND_SHADOWING,
            "writes a search path in front of `grep`",
        )

    def test_an_escape_written_in_data_is_accepted(self) -> None:
        """An escape a format string carries never reaches a command name."""

        self.assert_accepted(
            self.searched(
                'PATH="$tmp/failing-git:$PATH" printf %s\\n checked\n'
            )
        )

    def test_a_reserved_word_written_as_data_leaves_the_compound_read(
        self,
    ) -> None:
        """A compound is opened by a reserved word only where a command starts.

        The same text written as an operand is data, so it must not be read as
        opening a compound that never closes.
        """

        for index, operand in enumerate(("for", "if", "case", "while", "until")):
            with self.subTest(operand=operand):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'place="$tmp/archive"\n'
                        '{ :; } >"$tmp/archive/first"\n'
                        'place="$tmp/bin"\n'
                        f'{{ printf %s {operand}; printf x; }} >"$place/grep"\n'
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_reserved_word_written_as_data_keeps_a_safe_compound_accepted(
        self,
    ) -> None:
        """The same reading must not reject a path written outside the search path."""

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                '{ printf %s for; printf x; } >"$place/grep"\n'
            )
        )

    def test_a_case_pattern_leaves_the_compound_read(self) -> None:
        """A pattern closes no subshell, so it must not unbalance the reading.

        The value is rebound before the compound, so the accepted reading
        holds only while the pattern leaves the enclosing compound readable.
        """

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                'case one in one) : ;; esac\n'
                '{ printf x; } >"$place/grep"\n'
            )
        )

    def test_a_compound_redirection_in_a_body_is_read_at_its_call(self) -> None:
        """A body runs where it is called, not where it is written."""

        for index, form in enumerate(
            (
                'helper() { { printf x; } >"$place/grep"; }\n',
                'helper() { ( printf x ) >"$place/grep"; }\n',
                'helper() { for step in one; do printf x; done >"$place/grep"; }\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'place="$tmp/archive"\n'
                        + form
                        + 'place="$tmp/bin"\n'
                        'helper\n'
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_compound_redirection_in_a_body_reads_only_its_calls(self) -> None:
        """A value no call of the body holds names no file the body creates.

        Every dispatch this fixture cannot read is written with a path, so it
        runs a file rather than a declared body, and the body is read against
        the values its written calls hold.
        """

        for index, form in enumerate(
            (
                'helper() { { printf x; } >"$place/grep"; }\n'
                'place="$tmp/archive"\n'
                'helper\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n',
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/grep"; }\n'
                'helper\n',
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/git"; }\n'
                'helper\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_hash_entry_written_in_a_deferred_body_is_rejected(self) -> None:
        """A `hash` entry a deferred body writes rebinds the whole shell."""

        for index, form in enumerate(
            (
                'helper() { hash -p "$tmp/archive/g" grep; }\n'
                'name=helper\n'
                '$name\n',
                'helper() { hash -p "$tmp/archive/g" grep; }\ntrap helper EXIT\n',
                'inner() { hash -p "$tmp/archive/g" grep; }\n'
                'outer() { inner; }\n'
                'trap outer EXIT\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "binds a command name through `hash`",
                )

    def test_a_body_a_deferred_body_calls_is_read(self) -> None:
        """A call written inside a deferred body reaches another body.

        The deferred names are closed over the calls the collected bodies
        make, so a chain of calls behind one trap action is read, and a
        dispatch such a body cannot resolve reaches every declaration. An
        action such a body registers and a file it includes reach a body the
        same way, so both are followed as well.
        """

        for index, form in enumerate(
            (
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { inner; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'middle() { inner; }\n'
                'outer() { middle; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { chosen=inner; $chosen; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { trap inner USR1; }\n'
                'trap outer TERM\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { . "$tmp/library.sh"; }\n'
                'trap outer TERM\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'inner() { touch "$tmp/bin/keep"; }\n'
                'outer() { inner; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/keep"; }\n'
                'outer() { trap inner USR1; }\n'
                'trap outer TERM\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))

    def test_a_dispatch_written_with_a_path_calls_no_body(self) -> None:
        """A command word holding a slash is never looked up as a function.

        Such a dispatch runs a file, so it arms no reading of a declared body,
        while a dispatch that may still name one does.
        """

        body = (
            'mkdir -p "$tmp/archive"\n'
            'place="$tmp/bin"\n'
            'touch "$place/keep"\n'
            'place="$tmp/archive"\n'
            'capture() { printf x >"$place/git"; }\n'
            'capture\n'
        )
        self.assert_accepted(self.searched(body))
        self.assert_rejected(
            self.searched(body + 'called=capture\n$called\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `git` helper",
        )

    def test_a_body_a_call_the_graph_cannot_resolve_reaches_is_read(
        self,
    ) -> None:
        """A trap action and a dispatch the graph cannot read still run a body.

        The graph folds a body into the calls it resolves, so an unresolved
        call leaves the body holding no command node. The files such a body
        writes are created all the same, so they are read from the records.
        """

        for index, form in enumerate(
            (
                'helper() { touch "$tmp/bin/grep"; }\ntrap helper EXIT\n',
                "helper() { touch \"$tmp/bin/grep\"; }\ntrap 'helper' EXIT\n",
                'place="$tmp/bin"\n'
                'helper() { { printf x; } >"$place/grep"; }\n'
                'trap helper EXIT\n',
                'helper() { touch "$tmp/bin/grep"; }\nname=helper\n$name\n',
                'helper() { touch "$tmp/bin/grep"; }\nset -- helper\n"$1"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_body_a_call_cannot_resolve_writes_no_observed_name(self) -> None:
        """A deferred body naming no observed command writes no shim.

        The destination a deferred body writes is settled and compared with
        the search path, so a file it creates elsewhere, a name it only reads,
        and a file it moves out of the search path all stay accepted.
        """

        for index, form in enumerate(
            (
                'helper() { touch "$tmp/bin/keep"; }\ntrap helper EXIT\n',
                'helper() { printf grep; }\ntrap helper EXIT\n',
                'helper() { touch "$tmp/archive/grep"; }\ntrap helper EXIT\n',
                'helper() { mv "$tmp/bin/sleep" "$tmp/archive"; }\n'
                'trap helper EXIT\n',
                'helper() { cp "$tmp/archive/grep" "$tmp/archive/copy"; }\n'
                'trap helper EXIT\n',
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/git"; }\n'
                'helper\n',
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/grep"; }\n'
                'helper\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_deferred_body_writing_into_the_path_is_rejected(self) -> None:
        """Every way a deferred body puts a file in the search path is read.

        A dead call leaves the body unmodelled just as no call does, a
        substitution encloses a redirection the body still runs, and a copying
        command creates a file named after what it reads when its destination
        names a searched directory. A call the graph resolves does not exhaust
        the calls a body gets, so a deferred call that runs it again with a
        later value is read as well, and the destination of a copying command
        is read through the same option-aware settling the modelled commands
        use.
        """

        for index, form in enumerate(
            (
                'helper() { touch "$tmp/bin/grep"; }\n'
                'trap helper EXIT\n'
                'exit 0\n'
                'helper\n',
                'helper() { out=$(printf x >"$tmp/bin/grep"); }\n'
                'trap helper EXIT\n',
                'helper() { mv "$tmp/archive/grep" "$tmp/bin"; }\n'
                'trap helper EXIT\n',
                'helper() { cp "$tmp/archive/x" "$tmp/bin/grep"; }\n'
                'trap helper EXIT\n',
                'place="$tmp/archive"\n'
                'helper() { touch "$place/grep"; }\n'
                'helper\n'
                'trap helper EXIT\n'
                'place="$tmp/bin"\n',
                'place="$tmp/archive"\n'
                'helper() { touch "$place/grep"; }\n'
                'helper\n'
                'name=helper\n'
                'place="$tmp/bin"\n'
                '$name\n',
                'part=grep\n'
                'helper() { mv "$tmp/archive/$part" "$tmp/bin"; }\n'
                'trap helper EXIT\n',
                'helper() { cp -t "$tmp/bin" "$tmp/archive/grep"; }\n'
                'trap helper EXIT\n',
                'helper() { mv "$tmp/archive/grep" "$elsewhere"; }\n'
                'trap helper EXIT\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_redirection_written_alone_reads_its_own_place(self) -> None:
        """A command that is only a redirection belongs to no compound.

        The word is expanded where it is written, so the value the preceding
        group bound is the value the shell uses, and a value bound after that
        group names the file it really creates.
        """

        for index, form in enumerate(
            (
                '{ place="$tmp/bin"; :; }\n>"$place/grep"\n',
                '{ place="$tmp/bin"; :; }\n2>"$place/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\nplace="$tmp/archive"\n' + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                '>"$place/grep"\n'
            )
        )

    def test_a_working_directory_root_may_name_a_searched_directory(self) -> None:
        """A substitution that reads the working directory names no fixed place.

        `cd` decides what such a substitution reports, so a path written below
        one root is never proved to lie outside a directory written below
        another. The paths written apart by a name both spell as text stay
        apart, and so does a directory written below a searched one, because a
        search-path lookup never descends.
        """

        for index, form in enumerate(
            (
                'cd "$tmp/bin"\nplace=$(pwd)\ntouch "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(pwd -P)\ntouch "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(command pwd)\nprintf x >"$place/grep"\n',
                'place=$(cd "$tmp/bin" && pwd)\ntouch "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(pwd)\ncp "$root/helper" "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(pwd)\ncp -t "$place" "$tmp/staging/grep"\n',
                'helper() { place=$(pwd); touch "$place/grep"; }\ntrap helper EXIT\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'cd "$tmp/bin"\nplace=$(pwd)\ntouch "$place/keep"\n',
                'mkdir -p "$tmp/archive"\n'
                'cd "$tmp"\n'
                "place=$(pwd)\n"
                'touch "$place/archive/grep"\n',
                'mkdir -p "$tmp/bin/sub"\ntouch "$tmp/bin/sub/grep"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))

    def test_a_directory_is_placed_by_the_segments_two_paths_write_alike(
        self,
    ) -> None:
        """A path written from the root a searched directory is written from.

        The segments the two write the same way name the same directories, so
        what they write apart places them: a directory the search path names
        is not reached from the directory above it, from a directory beside
        it, or from a directory of the same name written under another one.
        """

        for index, form in enumerate(
            (
                'touch "$tmp/grep"\n',
                'place="$tmp"\ntouch "$place/grep"\n',
                'printf x >"$tmp/grep"\n',
                'mkdir -p "$tmp/archive"\ncp "$tmp/archive/grep" "$tmp"\n',
                'mkdir -p "$tmp/archive"\ncp -t "$tmp" "$tmp/archive/grep"\n',
                'mkdir -p "$tmp/archive/bin"\ntouch "$tmp/archive/bin/grep"\n',
                'mkdir -p "$tmp/sub/bin"\ncp "$root/helper" "$tmp/sub/bin/grep"\n',
                'mkdir -p "$tmp/sub/archive"\ntouch "$tmp/sub/archive/grep"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))
        for index, form in enumerate(
            (
                'touch "$tmp/bin/grep"\n',
                'mkdir -p "$tmp/bin/../bin"\ntouch "$tmp/bin/grep"\n',
                # The searched directory is written from a substitution that
                # may stand for the root itself, so a path written wholly as
                # text under the same name is not proved to be another one.
                'touch "/bin/grep"\n',
                'touch "/x/bin/grep"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        self.assert_rejected(
            COMPLIANT
            + '\nmkdir -p "/opt/x/bin"\n'
            + 'PATH="/opt/x/bin:$PATH"\n'
            + "export PATH\n"
            + 'touch "/opt/x/bin/grep"\n',
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_word_this_checker_cannot_read_is_read_for_the_helper_it_writes(
        self,
    ) -> None:
        """An interpreter given a program text writes the files that text writes.

        The shell unquoting such a text needs is not performed here, so the
        word is refused rather than settled and the path endings it writes are
        read from its text. A destination refused that way is not placed, so a
        text that writes a helper outside the searched directories is refused
        as well. A word that only mentions a name writes no path with it.
        """

        for index, form in enumerate(
            (
                'sh -c "touch $tmp/bin/grep"\n',
                'sh -c "cp $tmp/archive/x $tmp/bin/grep"\n',
                'awk "BEGIN { system(\\"touch $tmp/bin/grep\\") }" </dev/null\n',
                'dd if=/dev/null of="$tmp/bin/grep" 2>/dev/null\n',
                "python3 -c \"open('$tmp/bin/grep','w').close()\"\n",
                'sh -c "touch $tmp/archive/grep"\n',
                'helper() { sh -c "touch $tmp/bin/grep"; }\ntrap helper EXIT\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'sh -c "touch $tmp/bin/keep"\n',
                'printf "%s\\n" "adoption did not install the helper" >&2\n',
                "grep -q 'a\\|git push\\|b' \"$attempt_state\" || true\n",
                'sh -c "printf %s x" >/dev/null\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))

    def test_a_run_this_checker_models_writes_no_helper_its_words_mention(
        self,
    ) -> None:
        """A message, a pattern and a script are data rather than a program.

        A run written as a command this checker models either reads its
        operands as data or is settled as the write it is written as, so a
        path a word of such a run spells names no file the run creates. The
        refusal is kept for every other run, which may be an interpreter given
        a program text.
        """

        for index, form in enumerate(
            (
                'printf "%s\\n" "see tools/git for details"\n',
                'printf "%s\\n" "restored docs/plan and tools/cat"\n',
                'grep -q "a b/sed" "$tmp/archive/f" || true\n',
                'sed -i "s/old docs\\/git/new/" "$tmp/archive/f"\n',
                'echo "kept tools/rm and tools/install" >/dev/null\n',
                'test -f "$tmp/archive/f" || printf "%s\\n" "no tools/mv"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'touch "$tmp/archive/f"\n' + form
                    )
                )
        for index, form in enumerate(
            (
                'sh -c "touch $tmp/bin/grep"\n',
                'env sh -c "touch $tmp/bin/grep"\n',
                'PATH="$PATH" sh -c "touch $tmp/bin/grep"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_command_written_as_a_path_is_not_read_as_the_utility_it_names(
        self,
    ) -> None:
        """A file the fixture supplies may write whatever it likes.

        The exemption a message-writing command carries belongs to the utility
        a bare name reaches, not to a file the fixture puts at that name, so a
        command written as a path is read for the helper paths its words
        carry.
        """

        for index, form in enumerate(
            (
                './printf "touch $tmp/bin/grep"\n',
                '/bin/echo "touch $tmp/bin/grep"\n',
                '"$tmp/archive/printf" "touch $tmp/bin/grep"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        self.assert_accepted(self.searched('printf "%s\\n" "tools/grep"\n'))

    def test_a_sed_script_that_runs_a_command_is_read_as_a_shell_text(
        self,
    ) -> None:
        """`sed` runs a command with `e`, which writes what no `w` names."""

        for index, form in enumerate(
            (
                'sed "s/.*/touch $tmp\\/bin\\/grep/e" "$attempt_state" >/dev/null\n',
                'sed "s|.*|touch $tmp/bin/grep|e" "$attempt_state" >/dev/null\n',
                'sed "s/.*/touch $tmp\\/bin\\/grep/ge" "$attempt_state" >/dev/null\n',
                'sed "s/.*/touch $tmp\\/bin\\/grep/g e" "$attempt_state" >/dev/null\n',
                'sed "1e touch $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;1e touch $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s|.*|cp $tmp/archive/f $tmp/bin/grep|e" "$attempt_state"'
                ' >/dev/null\n',
                'sed "1e touch $tmp/bin/grep\n2w $tmp/archive/log"'
                ' "$attempt_state" >/dev/null\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'touch "$tmp/archive/f"\n' + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_sed_script_is_data_until_it_writes_the_file_it_names(
        self,
    ) -> None:
        """`sed` names a file to write with `w`, and nothing else it reads does.

        A script that spells no write carries its paths as data, so a fixture
        that rewrites a message mentioning a helper name is accepted. A script
        that spells the write command or the substitution flag names the file
        it creates, so the paths it carries are read as helpers.
        """

        for index, form in enumerate(
            (
                'sed "s/x/y/w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -n "/x/w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "1w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "\\$w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "2,3w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "1W $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "1w$tmp/bin/grep" "$attempt_state"\n',
                'sed "s|a|b|w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s,a,b,w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'x=1 sed "s|a|b|w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -n "p;w $tmp/bin/grep" "$attempt_state"\n',
                'env sed -e "1w $tmp/bin/grep" "$attempt_state"\n',
                'sed -e "s/a/b/gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/x/y/pw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/x/y/Iw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/pgw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'env sed -e "s/a/b/gw $tmp/bin/grep" "$attempt_state"\n',
                'sed -e "s/a/b/2w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/g3w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/gw$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1wbin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/gwbin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1w./bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e1wbin/grep "$attempt_state" >/dev/null\n',
                'sed -e "\\$w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1!w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1 w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\,foo,w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\,foo,wbin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\%foo%w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\%foo%,\\%bar%w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "/foo/,\\%bar%w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\,foo,!w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed --expression=1w"$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed --expression=w"$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed --expression=1w$tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed --expression=\\,foo,wbin/grep "$attempt_state" >/dev/null\n',
                'sed "1a hello\n2w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "1w $tmp/bin/grep\n2a hello" "$attempt_state" >/dev/null\n',
                "sed '1a\\\\\n1wbin/grep' \"$attempt_state\" >/dev/null\n",
                'sed "s;a;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;i;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s{a{b{w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b;gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b;\n1w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "y;a;b;\n1w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s;a;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s{a{b{w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "y/x/y/;s;a;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s/p/q/;s;i;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b\\\\\nc;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;when;tools/x;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b;;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s|a|b| w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b; w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s{a{b{ w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/g w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ 1w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ w$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s;a;b; w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "y;a;x;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ p w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ Iw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ g2w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/g pw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b; gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/x/ pw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed 1w$tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed -es/a/b/gw$tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed -e1w\\ $tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed --expression=1w\\ $tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed -e1e\\ touch\\ $tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed --expression=1e\\ touch\\ $tmp/bin/grep "$attempt_state"\n',
                'sed -es,.*,touch\\ $tmp/bin/grep,e "$attempt_state" >/dev/null\n',
                'sed -nes,.*,touch\\ $tmp/bin/grep,e "$attempt_state" >/dev/null\n',
                'sed -e"1e touch $tmp/bin/grep" "$attempt_state" >/dev/null\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'sed -i "s/old docs\\/git/new/" "$tmp/archive/f"\n',
                'sed -i "s/a/b/" "$tmp/archive/f"\n',
                'sed "s/tools\\/grep/x/" "$attempt_state" >/dev/null\n',
                'printf "%s\\n" "restored new file and tools/git"\n',
                'env sed -e "1w $tmp/archive/log" "$attempt_state"\n',
                'env LC_ALL=C sed -n "/warning/p" "$attempt_state"\n',
                'command sed -e "1w $tmp/archive/log" "$attempt_state"\n',
                'sed -n "/warning/p" "$tmp/bin/git"\n',
                'val=$(sed -n "s/^ *when: *//p" "$tmp/bin/git")\n',
                'sed -n "1w $tmp/archive/log" "$tmp/bin/grep"\n',
                'sed "s|a/grep|b|w $tmp/archive/out" "$attempt_state" >/dev/null\n',
                'sed "s|a|/grep|w $tmp/archive/out" "$attempt_state" >/dev/null\n',
                'sed "s|a/grep|b|" "$attempt_state" >/dev/null\n',
                'sed "s|workflow/git|x|" "$attempt_state" >/dev/null\n',
                'sed -n "/warning\\/grep/p" "$attempt_state"\n',
                'sed "s|old|new-workflow/git|" "$attempt_state" >"$tmp/archive/o"\n',
                'sed -i "s|workflow/git|new|" "$tmp/archive/f"\n',
                'sed "s|bigwig/grep|x|" "$attempt_state" >/dev/null\n',
                'sed "s|show|workflow/git|g" "$attempt_state" >/dev/null\n',
                'sed -n "/wait\\/grep/!p" "$attempt_state"\n',
                'sed "/rework\\/grep/d" "$attempt_state" >/dev/null\n',
                'sed "s/msg/see workflow\\/git docs/" "$attempt_state" >/dev/null\n',
                'sed "s/x/y warning\\/git/" "$attempt_state" >/dev/null\n',
                'sed -n "/a!warning\\/grep/p" "$attempt_state"\n',
                'sed -n "\\,warning/grep,p" "$attempt_state"\n',
                'sed --expression=/warning\\/grep/p "$attempt_state" >/dev/null\n',
                'sed --in-place "s|workflow/git|new|" "$tmp/archive/f"\n',
                'sed -i.bak "s|workflow/git|new|" "$tmp/archive/f"\n',
                'sed -ne "/warning/p" "$attempt_state"\n',
                'sed -n -e "/warning/p" "$attempt_state"\n',
                'sed -es/where/x/ "$attempt_state" >/dev/null\n',
                'sed 1w$tmp/archive/log "$attempt_state" >/dev/null\n',
                'sed "$a\\\\\nwhen done see tools/git" "$attempt_state" >/dev/null\n',
                'sed "1a\\\\\nfirst\\\\\nworkflow/git ref" "$attempt_state" >/dev/null\n',
                'sed "1i\\\\\nwill call tools/grep" "$attempt_state" >/dev/null\n',
                'sed "1c\\\\\nwarning tools/git" "$attempt_state" >/dev/null\n',
                'sed "1a warning tools/git" "$attempt_state" >/dev/null\n',
                'sed "1a hello;2w tools/grep" "$attempt_state" >/dev/null\n',
                "sed '1a\\\nwarning tools/git' \"$attempt_state\" >/dev/null\n",
                'sed "s;a/grep;b;" "$attempt_state" >/dev/null\n',
                'sed "s;q;r;;1a hello workflow/git" "$attempt_state" >/dev/null\n',
                'sed "1a\\\\\nworkflow/git and s;x;y; notes" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;1a hello workflow/git" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s;a/grep;b;" "$attempt_state" >/dev/null\n',
                'sed "s;when;tools/git;" "$attempt_state" >/dev/null\n',
                'sed "s{when{tools/git{" "$attempt_state" >/dev/null\n',
                'sed "s;x;we tools/git;" "$attempt_state" >/dev/null\n',
                'sed "s;warn/old;warn/git;" "$attempt_state" >/dev/null\n',
                'sed "y/a/b/ w tools/git" "$attempt_state" >/dev/null\n',
                'sed "s/w/x/ p" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ meow" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ mow tools/git" "$attempt_state" >/dev/null\n',
                'sed "s;x;e touch tools/git;" "$attempt_state" >/dev/null\n',
                'sed -n -e "/warning/p" "$attempt_state" >/dev/null\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'touch "$tmp/archive/f"\n' + form
                    )
                )

    def test_a_loop_head_names_the_file_a_word_under_it_creates(
        self,
    ) -> None:
        """A `for` head writes its list in full where the head is written.

        This checker settles no name a loop head binds, so a destination
        written as that name carries no name of its own. The file such a write
        creates is one of the paths the list names, so the list is read for the
        helpers it puts in place. A list naming no helper is accepted.
        """

        for index, form in enumerate(
            (
                'for p in "$tmp/bin/grep"; do touch "$p"; done\n',
                'for p in "$tmp/archive/h" "$tmp/bin/grep"; do touch "$p"; done\n',
                'for p in "$tmp/bin/grep"; do printf x >"$p"; done\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'for p in "$tmp/bin/keep"; do touch "$p"; done\n',
                'for p in "$tmp/archive/grep"; do touch "$p"; done\n',
                'for p in "$tmp/archive/h"; do cat "$p" >/dev/null; done\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_write_no_word_names_makes_every_written_helper_reachable(
        self,
    ) -> None:
        """A command that takes its destination from what it reads names no file.

        `xargs` supplies the operands from its input, so nothing written says
        what file the run creates, and every helper name the fixture writes
        anywhere may be the name it takes. The word the launcher chain runs is
        a command name rather than a path, so it is not read as one.
        """

        self.assert_rejected(
            self.searched('printf %s "$tmp/bin/grep" | xargs touch\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )
        for index, form in enumerate(
            (
                'printf %s "$tmp/bin/keep" | xargs touch\n',
                'printf %s "$tmp/bin/keep" | xargs touch\n'
                'command grep PATH "$attempt_state" || true\n',
                'printf %s "$tmp/bin/grep" | cat >/dev/null\n',
                'command -v touch >/dev/null\ntouch "$tmp/archive/grep"\n',
                'printf "%s\\n" touch\ntouch "$tmp/archive/grep"\n',
                'printf x | tee\ntouch "$tmp/archive/grep"\n',
                'printf %s "$attempt_state" | xargs grep -q touch\n'
                'touch "$tmp/archive/grep"\n',
                'grep -q cp "$attempt_state" || true\n'
                'touch "$tmp/archive/grep"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_helper_finding_is_reported_where_the_operation_is_written(
        self,
    ) -> None:
        """The position names the command that writes the file, not the rule."""
        written = 'touch "$tmp/bin/grep"\n'
        source = self.searched(written)
        findings = [
            finding
            for finding in check(source)
            if finding.rule == RULE_COMMAND_SHADOWING
        ]
        self.assertEqual(len(findings), 1, self.messages(source))
        self.assertIsNotNone(findings[0].position)
        self.assertEqual(findings[0].position.offset, source.index(written))

    def test_every_redirection_a_compound_carries_is_read_at_its_compound(
        self,
    ) -> None:
        """The second redirection belongs to the same compound as the first."""

        for index, form in enumerate(
            (
                '{ printf x; } >"$place/grep" 2>"$place/sed"\n',
                '{ printf x; } >"$place/grep" >>"$place/sed"\n',
                '( printf x ) >"$place/grep" 2>"$place/sed"\n',
                'for step in one; do printf x; done >"$place/grep" 2>"$place/sed"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'place="$tmp/bin"\n'
                        'touch "$place/keep"\n'
                        'place="$tmp/archive"\n' + form
                    )
                )
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\nplace="$tmp/bin"\n' + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `sed` helper",
                )

    def test_a_declaration_that_rebinds_nothing_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT + "\nassert_state() {\n  :\n}\n")

    def test_a_helper_named_for_another_command_is_accepted(self) -> None:
        self.assert_accepted(
            self.searched(
                'cat >"$tmp/bin/copier-shim" <<\'EOF_SHIM\'\n'
                "#!/bin/sh\n"
                "exit 0\n"
                "EOF_SHIM\n"
            )
        )

    def test_a_helper_written_outside_every_searched_directory_is_accepted(self) -> None:
        self.assert_accepted(self.searched('touch "$tmp/archive/sed"\n'))

    def test_moving_an_observed_name_out_of_the_search_path_is_accepted(self) -> None:
        """A source operand is read as what is moved, not as what is created."""

        self.assert_accepted(self.searched('mv "$tmp/bin/sleep" "$tmp/archive"\n'))

    def test_moving_an_observed_name_out_with_an_option_is_accepted(self) -> None:
        """A target-directory option outside the search path creates nothing there."""

        self.assert_accepted(
            self.searched('mv -t "$tmp/archive" "$tmp/bin/sleep"\n')
        )

    def test_a_command_that_only_reads_the_search_path_name_is_accepted(self) -> None:
        """A word spelled like the search path is data unless a command binds it."""

        for index, form in enumerate(
            (
                'grep PATH "$attempt_state" || true\n',
                'grep PATH=x "$attempt_state" || true\n',
                "printf '%s\\n' PATH\n",
                'checked=$(read PATH </dev/null; echo done)\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched(form + 'touch "$tmp/archive/git"\n')
                )

    def test_a_written_path_that_only_reads_an_observed_name_is_accepted(self) -> None:
        self.assert_accepted(self.searched('cat "$tmp/bin/grep" >/dev/null\n'))


class SourcedLibraryTest(ContractSupportTest):
    """A file the fixture sources is read under the same shadowing rule.

    A sourced file runs with the authority of the shell that sources it, so a
    declaration written there rebinds a command name for every bound
    observation while the fixture keeps exactly its committed text. The bound
    libraries are supplied here, so nothing in this class reads a file the
    repository ships.
    """

    LIBRARY = "tests/lib-fixture.sh"

    LIBRARY_TEXT = (
        "fixture_available() {\n"
        "  command -v fixture >/dev/null 2>&1\n"
        "}\n"
        "\n"
        "run_fixture() {\n"
        '  fixture "$@"\n'
        "}\n"
    )

    SOURCING = '\n. "$root/tests/lib-fixture.sh"\n'

    # A Copier operation written through the wrapper. Only a name the fixture
    # runs this way carries a bound Copier observation, so this is what makes
    # the wrapper rule ask for a dispatch rather than for a name.
    OPERATION = (
        'run_copier copy -q --trust --defaults --vcs-ref v1.4.5 '
        '"$update_source" "$tmp/wrapper-out" >/dev/null\n'
    )

    sourced: dict[str, str] = {LIBRARY: LIBRARY_TEXT}

    def library(self, addition: str = "") -> dict[str, str]:
        return {self.LIBRARY: self.LIBRARY_TEXT + addition}

    def with_library(self, addition: str = "") -> str:
        return COMPLIANT + self.SOURCING + addition

    def shadowing(self, source: str) -> list[str]:
        """Return the shadowing findings alone.

        A fixture that writes a Copier operation of its own draws findings
        from the rules that read where Copier writes, and those say nothing
        about which names the shell holds.
        """

        return [
            str(finding)
            for finding in check(source, self.declared, self.sourced)
            if finding.rule == RULE_COMMAND_SHADOWING
        ]

    def assert_wrapper_rejected(self, text: str, expected: str) -> None:
        self.sourced = {self.LIBRARY: text}
        try:
            reported = "\n".join(self.shadowing(self.with_library(self.OPERATION)))
            self.assertIn(expected, reported)
            self.assertIn(f"the sourced library `{self.LIBRARY}`", reported)
        finally:
            self.sourced = self.library()

    def assert_wrapper_accepted(self, text: str) -> None:
        self.sourced = {self.LIBRARY: text}
        try:
            self.assertEqual(
                self.shadowing(self.with_library(self.OPERATION)), []
            )
        finally:
            self.sourced = self.library()

    def assert_library_rejected(self, addition: str, expected: str) -> None:
        self.sourced = self.library(addition)
        try:
            self.assert_rejected(
                self.with_library(), RULE_COMMAND_SHADOWING, expected
            )
            self.assertIn(f"the sourced library `{self.LIBRARY}`", self.messages(
                self.with_library()
            ))
        finally:
            self.sourced = self.library()

    def test_a_bound_library_the_fixture_sources_is_accepted(self) -> None:
        self.assert_accepted(self.with_library())

    def test_a_fixture_that_sources_nothing_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT)

    def test_an_observed_command_declared_in_the_library_is_rejected(self) -> None:
        for name in sorted(copier_fixture_validator.OBSERVED_COMMANDS):
            if not name.isidentifier():
                continue
            with self.subTest(command=name):
                self.assert_library_rejected(
                    f"\n{name}() {{\n  :\n}}\n", f"declares `{name}` as a function"
                )

    def test_the_reproduced_library_admission_is_rejected(self) -> None:
        self.assert_library_rejected(
            "\ngrep() { :; }\n", "declares `grep` as a function"
        )

    def test_a_helper_the_library_writes_on_the_search_path_is_rejected(self) -> None:
        self.assert_library_rejected(
            '\nmkdir -p "$tmp/bin"\nPATH="$tmp/bin:$PATH"\nexport PATH\n'
            'cp "$tmp/fake-grep" "$tmp/bin/grep"\n',
            "search path",
        )

    def test_a_hash_entry_written_in_the_library_is_rejected(self) -> None:
        self.assert_library_rejected(
            '\nhash -p "$tmp/fake-grep" grep\n', "binds a command name through `hash`"
        )

    def test_a_search_path_the_library_writes_for_one_command_is_rejected(self) -> None:
        self.assert_library_rejected(
            '\nPATH="$tmp/bin" grep -q x "$attempt_state"\n',
            "writes a search path in front of",
        )

    def test_the_copier_wrapper_declared_in_the_fixture_is_rejected(self) -> None:
        """The reproduced admission: a no-op wrapper keeps every needle intact."""

        self.assert_rejected(
            self.with_library("run_copier() { return 0; }\n"),
            RULE_COMMAND_SHADOWING,
            "declares the Copier wrapper `run_copier`",
        )

    def test_every_copier_named_declaration_in_the_fixture_is_rejected(self) -> None:
        for name in ("run_copier", "copier_available", "COPIER_run"):
            with self.subTest(name=name):
                self.assert_rejected(
                    self.with_library(f"{name}() {{\n  :\n}}\n"),
                    RULE_COMMAND_SHADOWING,
                    f"declares the Copier wrapper `{name}`",
                )

    def test_a_declaration_the_library_already_makes_is_rejected(self) -> None:
        self.assert_rejected(
            self.with_library("run_fixture() {\n  :\n}\n"),
            RULE_COMMAND_SHADOWING,
            "declares `run_fixture`, which the sourced library "
            f"`{self.LIBRARY}` declares as well",
        )

    def test_a_declaration_the_library_does_not_make_is_accepted(self) -> None:
        self.assert_accepted(self.with_library("report_state() {\n  :\n}\n"))

    def test_an_unbound_sourced_path_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\n. "$root/tests/lib-other.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_library_written_behind_another_directory_is_unbound(self) -> None:
        """Only the one anchor the sourcing file is given places the library."""

        self.assert_rejected(
            COMPLIANT + '\n. "$tmp/vendor/tests/lib-fixture.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_library_the_fixture_could_write_itself_is_unbound(self) -> None:
        """Only the anchor the invocation decides places a bound library.

        A scratch directory the fixture fills is decided inside these bytes, so
        a file written there is not the file this checker was given, however
        the tail of the path is spelled.
        """

        self.assert_rejected(
            COMPLIANT
            + '\nmkdir -p "$tmp/tests"\n'
            + 'printf \'grep() { :; }\\n\' > "$tmp/tests/lib-fixture.sh"\n'
            + '. "$tmp/tests/lib-fixture.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_source_written_relative_to_no_anchor_is_rejected(self) -> None:
        for operand in ("tests/lib-fixture.sh", "./tests/lib-fixture.sh"):
            with self.subTest(operand=operand):
                self.assert_rejected(
                    COMPLIANT + f"\n. {operand}\n",
                    RULE_COMMAND_SHADOWING,
                    "sources a path this checker was not given",
                )

    def test_a_second_value_written_for_the_anchor_unbinds_it(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\nroot="$tmp"\n' + self.SOURCING,
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_an_anchor_the_fixture_decides_is_unbound(self) -> None:
        self.assert_rejected(
            self.with_library().replace('root=$1\n', 'root="$tmp/vendor"\n', 1),
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_copier_wrapper_the_library_empties_is_rejected(self) -> None:
        """The library holds the same authority the fixture does."""

        self.assert_wrapper_rejected(
            "run_copier() {\n  return 0\n}\n", "runs no Copier command"
        )

    def test_a_copier_wrapper_that_only_reports_is_rejected(self) -> None:
        self.assert_wrapper_rejected(
            'run_copier() {\n  echo copier "$@"\n}\n', "runs no Copier command"
        )

    def test_a_copier_wrapper_reduced_to_a_query_is_rejected(self) -> None:
        """Asking where Copier is performs no Copier operation."""

        self.assert_wrapper_rejected(
            "run_copier() {\n  command -v copier >/dev/null 2>&1\n}\n",
            "runs no Copier command",
        )

    def test_a_copier_wrapper_that_delegates_to_a_query_is_rejected(self) -> None:
        self.assert_wrapper_rejected(
            "copier_available() {\n  command -v copier >/dev/null 2>&1\n}\n"
            '\nrun_copier() {\n  copier_available "$@"\n}\n',
            "declares the Copier wrapper `run_copier` with a body that runs "
            "no Copier command",
        )

    def test_a_copier_wrapper_that_runs_copier_is_accepted(self) -> None:
        self.assert_wrapper_accepted(
            "copier_available() {\n"
            "  command -v copier >/dev/null 2>&1\n"
            "}\n"
            '\nrun_copier() {\n  copier "$@"\n}\n'
        )

    def test_a_copier_wrapper_that_runs_a_copier_path_is_accepted(self) -> None:
        self.assert_wrapper_accepted(
            "copier_bin=$(command -v copier)\n"
            '\nrun_copier() {\n  "$copier_bin" "$@"\n}\n'
        )

    def test_a_copier_wrapper_that_delegates_to_a_dispatcher_is_accepted(self) -> None:
        self.assert_wrapper_accepted(
            'copier_dispatch() {\n  copier "$@"\n}\n'
            '\nrun_copier() {\n  copier_dispatch "$@"\n}\n'
        )

    def test_a_copier_predicate_that_asks_where_copier_is_is_accepted(self) -> None:
        """A predicate the fixture never runs as an operation may ask."""

        self.sourced = {
            self.LIBRARY: "copier_available() {\n"
            "  command -v copier >/dev/null 2>&1\n"
            "}\n"
        }
        try:
            self.assert_accepted(self.with_library())
        finally:
            self.sourced = self.library()

    def test_a_copier_predicate_that_names_no_copier_is_rejected(self) -> None:
        self.sourced = {self.LIBRARY: "copier_available() {\n  return 0\n}\n"}
        try:
            self.assert_rejected(
                self.with_library(),
                RULE_COMMAND_SHADOWING,
                "declares the Copier wrapper `copier_available` with a body "
                "that names no Copier command",
            )
        finally:
            self.sourced = self.library()

    def test_an_anchor_value_this_checker_was_not_given_is_unbound(self) -> None:
        """A value that mentions the invocation may still expand elsewhere.

        The anchor is read as written, so a value that names a positional
        parameter in a branch it never takes binds no library.
        """

        self.assert_rejected(
            self.with_library().replace(
                "root=$1\n",
                "root=$(CDPATH= cd -- \"$tmp\" && pwd -P || printf '%s' \"$0\")\n",
                1,
            ),
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_source_whose_operand_is_not_written_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\n. "$library"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_the_source_keyword_is_read_as_a_source(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\nsource "$root/tests/lib-other.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_source_written_inside_a_body_is_read(self) -> None:
        """A body the shell runs includes its file into the whole shell."""

        self.sourced = self.library("\ngrep() { :; }\n")
        try:
            self.assert_rejected(
                COMPLIANT
                + '\nload_helpers() {\n  . "$root/tests/lib-fixture.sh"\n}\n'
                + "load_helpers\n",
                RULE_COMMAND_SHADOWING,
                "declares `grep` as a function",
            )
        finally:
            self.sourced = self.library()

    def test_a_body_the_graph_resolves_no_call_for_is_read(self) -> None:
        """A body a trap action reaches includes its file just as a call does."""

        self.sourced = self.library("\ngrep() { :; }\n")
        try:
            self.assert_rejected(
                COMPLIANT
                + '\nload_helpers() {\n  . "$root/tests/lib-fixture.sh"\n}\n'
                + "trap load_helpers USR1\n",
                RULE_COMMAND_SHADOWING,
                "declares `grep` as a function",
            )
        finally:
            self.sourced = self.library()

    def test_a_case_pattern_is_not_read_as_a_source(self) -> None:
        """A `.` written as a `case` pattern is no command word at all."""

        self.assert_accepted(
            COMPLIANT
            + '\ncase "$candidate" in\n  .|..|./*) exit 1 ;;\n  *) : ;;\nesac\n'
        )

    def test_a_library_the_checked_projections_reject_is_reported(self) -> None:
        self.sourced = {self.LIBRARY: "cat <<<here\n"}
        try:
            self.assert_rejected(
                self.with_library(),
                RULE_STRUCTURE,
                "the checked projections rejected the sourced bytes",
            )
        finally:
            self.sourced = self.library()

    def test_a_library_is_read_once_however_often_it_is_sourced(self) -> None:
        self.sourced = self.library("\ngrep() { :; }\n")
        try:
            reported = [
                finding
                for finding in check(
                    COMPLIANT + self.SOURCING + self.SOURCING,
                    self.declared,
                    self.sourced,
                )
                if finding.rule == RULE_COMMAND_SHADOWING
            ]
            self.assertEqual(len(reported), 1, self.messages(COMPLIANT))
        finally:
            self.sourced = self.library()

    def test_the_bound_set_is_the_one_this_checker_ships_beside(self) -> None:
        libraries = copier_fixture_validator.read_libraries()
        self.assertEqual(
            tuple(libraries), copier_fixture_validator.SOURCED_LIBRARY_PATHS
        )
        for text in libraries.values():
            self.assertTrue(text.strip())

    def test_a_root_without_the_bound_library_binds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                copier_fixture_validator.read_libraries(Path(directory)), {}
            )

    def test_supplied_library_bytes_are_decoded(self) -> None:
        self.sourced = {self.LIBRARY: self.LIBRARY_TEXT.encode("utf-8")}
        try:
            self.assert_accepted(self.with_library())
        finally:
            self.sourced = self.library()


class UpdateChildTest(ContractSupportTest):
    def test_removing_the_asynchronous_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'
                ' --defaults --vcs-ref v1.4.5 &\n',
                "",
            ),
            RULE_UPDATE_CHILD,
            "starts no asynchronous update child",
        )

    def test_running_the_update_child_in_the_foreground_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'
                ' --defaults --vcs-ref v1.4.5 &\n',
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'
                ' --defaults --vcs-ref v1.4.5\n',
            ),
            RULE_UPDATE_CHILD,
            "starts no asynchronous update child",
        )

    def test_conditionally_enclosed_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'
                ' --defaults --vcs-ref v1.4.5 &\nupdate_pid=$!\n',
                'if [ -n "$maybe" ]; then\n'
                '  "$project/.project-agent-workflow/scripts/update-from-copier.sh"'
                ' --defaults --vcs-ref v1.4.5 &\n'
                "  update_pid=$!\n"
                "fi\n",
            ),
            RULE_UPDATE_CHILD,
            "can be skipped",
        )

    def test_second_asynchronous_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'update_pid=$!\n',
                'update_pid=$!\n"$project/.project-agent-workflow/scripts/'
                'update-from-copier.sh" --defaults &\n',
            ),
            RULE_UPDATE_CHILD,
            "more than one asynchronous update child",
        )

    def test_child_that_avoids_the_update_wrapper_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'
                ' --defaults --vcs-ref v1.4.5 &',
                'run_copier update -q --defaults --vcs-ref v1.4.5 "$project" &',
            ),
            RULE_UPDATE_CHILD,
            "does not run the update wrapper",
        )

    def test_missing_child_pid_capture_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate("update_pid=$!\n", "update_pid=0\n"),
            RULE_CHILD_PID,
            "not captured by the next assignment",
        )


class BoundedPollTest(ContractSupportTest):
    def test_removing_one_poll_is_rejected(self) -> None:
        mutated = self.mutate(
            """release_waited=0
while [ "$release_waited" -lt 30 ]; do
  if [ ! -e "$release_file" ]; then
    break
  fi
  release_waited=$((release_waited + 1))
  sleep 1
done
""",
            "",
        )
        self.assert_rejected(mutated, RULE_BOUNDED_POLL, "both bounded polling loops")

    def test_poll_without_a_counter_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate("  ready_waited=$((ready_waited + 1))\n", ""),
            RULE_BOUNDED_POLL,
            "maintains no counter",
        )

    def test_a_poll_bounded_only_by_its_condition_is_accepted(self) -> None:
        """A counted loop stops on its own turn count without an early exit."""

        self.assert_accepted(
            self.mutate(
                """  if [ -e "$ready_file" ]; then
    break
  fi
""",
                """  if [ -e "$ready_file" ]; then
    echo waiting
  fi
""",
            )
        )


class UnboundedPollTest(ContractSupportTest):
    """A poll is bounded only when its own counter stops it."""

    def mutate_both_conditions(self, condition: str) -> str:
        mutated = self.mutate('while [ "$ready_waited" -lt 30 ]; do', condition)
        return self.mutate('while [ "$release_waited" -lt 30 ]; do', condition, mutated)

    def test_constant_loop_condition_is_rejected(self) -> None:
        for condition in ("while true; do", "while :; do", "until false; do"):
            with self.subTest(condition=condition):
                self.assert_rejected(
                    self.mutate_both_conditions(condition),
                    RULE_BOUNDED_POLL,
                    "does not test its own counter to stop",
                )

    READY_LOOP = (
        'while [ "$ready_waited" -lt 30 ]; do\n'
        '  if [ -e "$ready_file" ]; then\n'
        "    break\n"
        "  fi\n"
        "  ready_waited=$((ready_waited + 1))\n"
        "  sleep 1\n"
        "done\n"
    )

    def test_a_limit_test_guarding_a_break_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                self.READY_LOOP,
                "while true; do\n"
                '  if [ -e "$ready_file" ]; then\n'
                "    break\n"
                "  fi\n"
                "  ready_waited=$((ready_waited + 1))\n"
                '  if [ "$ready_waited" -ge 30 ]; then\n'
                "    break\n"
                "  fi\n"
                "  sleep 1\n"
                "done\n",
            )
        )

    GUARD = '  if [ -e "$ready_file" ]; then\n    break\n  fi\n'
    INCREMENT = "  ready_waited=$((ready_waited + 1))\n"

    def body_loop(self, body: str) -> str:
        return "while true; do\n" + body + "done\n"

    def test_every_written_guard_form_is_accepted(self) -> None:
        for label, guard in (
            ("or", '  [ "$ready_waited" -lt 30 ] || break\n  sleep 1\n'),
            ("and", '  [ "$ready_waited" -ge 30 ] && break\n  sleep 1\n'),
            ("test", '  test "$ready_waited" -ge 30 && break\n  sleep 1\n'),
            ("case", '  case "$ready_waited" in 30) break;; esac\n  sleep 1\n'),
            (
                "else",
                '  if [ "$ready_waited" -lt 30 ]; then\n'
                "    sleep 1\n"
                "  else\n"
                "    break\n"
                "  fi\n",
            ),
        ):
            with self.subTest(guard=label):
                self.assert_accepted(
                    self.mutate(
                        self.READY_LOOP,
                        self.body_loop(self.GUARD + self.INCREMENT + guard),
                    )
                )

    def test_a_guard_reading_something_else_is_rejected(self) -> None:
        for label, guard in (
            ("or", '  [ -e "$ready_file" ] || break\n  sleep 1\n'),
            ("case", '  case "$ready_file" in *) break;; esac\n  sleep 1\n'),
        ):
            with self.subTest(guard=label):
                self.assert_rejected(
                    self.mutate(
                        self.READY_LOOP,
                        self.body_loop(self.INCREMENT + guard),
                    ),
                    RULE_BOUNDED_POLL,
                    "does not test its own counter to stop",
                )

    def test_every_written_bounded_poll_form_is_accepted(self) -> None:
        for label, replacement in (
            (
                "and condition",
                'while [ ! -e "$ready_file" ] && [ "$ready_waited" -lt 30 ]; do\n'
                "  sleep 1\n" + self.INCREMENT + "done\n",
            ),
            (
                "until condition",
                'until [ -e "$ready_file" ] || [ "$ready_waited" -ge 30 ]; do\n'
                "  sleep 1\n" + self.INCREMENT + "done\n",
            ),
            (
                "word list",
                "for tick in 1 2 3; do\n" + self.GUARD + "  sleep 1\n" "done\n",
            ),
            ("expanded word list", "for ready_step in $(seq 1 30); do\n  sleep 1\ndone\n"),
            (
                "exit inside a nested loop",
                "while true; do\n"
                "  for tick in 1 2; do\n"
                '    if [ "$ready_waited" -ge 30 ]; then\n'
                "      exit 1\n"
                "    fi\n"
                "  done\n" + self.GUARD + self.INCREMENT + "  sleep 1\n"
                "done\n",
            ),
            (
                "nested loop with no command",
                'while [ "$ready_waited" -lt 30 ]; do\n'
                "  for tick in 1 2; do\n"
                "    total=$((total + 1))\n"
                "  done\n" + self.GUARD + "  sleep 1\n" + self.INCREMENT + "done\n",
            ),
        ):
            with self.subTest(poll=label):
                self.assert_accepted(self.mutate(self.READY_LOOP, replacement))

    def test_an_increment_written_inside_a_branch_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                self.READY_LOOP,
                'while [ "$ready_waited" -lt 30 ]; do\n'
                '  if [ -e "$ready_file" ]; then\n'
                "    ready_waited=$((ready_waited + 1))\n"
                "  fi\n"
                "  sleep 1\n"
                "done\n",
            ),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )

    def counted_loop(self, body: str) -> str:
        return 'while [ "$ready_waited" -lt 30 ]; do\n' + body + "done\n"

    def test_a_counter_that_skips_a_turn_is_rejected(self) -> None:
        for label, body in (
            ("and list", '  [ -e "$other" ] && ready_waited=$((ready_waited + 1))\n  sleep 1\n'),
            ("or list", '  [ -e "$other" ] || ready_waited=$((ready_waited + 1))\n  sleep 1\n'),
            ("subshell", "  ( ready_waited=$((ready_waited + 1)) )\n  sleep 1\n"),
            (
                "subshell over lines",
                "  (\n    ready_waited=$((ready_waited + 1))\n  )\n  sleep 1\n",
            ),
            ("pipeline", "  true | ready_waited=$((ready_waited + 1))\n  sleep 1\n"),
            (
                "guarded group",
                '  [ -e "$other" ] && { ready_waited=$((ready_waited + 1)); }\n  sleep 1\n',
            ),
        ):
            with self.subTest(written=label):
                self.assert_rejected(
                    self.mutate(self.READY_LOOP, self.counted_loop(body)),
                    RULE_BOUNDED_POLL,
                    "does not test its own counter to stop",
                )

    def test_a_counter_isolated_by_a_following_operator_is_rejected(self) -> None:
        for label, body in (
            ("pipeline", "  ready_waited=$((ready_waited + 1)) | true\n  sleep 1\n"),
            ("asynchronous", "  ready_waited=$((ready_waited + 1)) &\n  sleep 1\n"),
        ):
            with self.subTest(written=label):
                self.assert_rejected(
                    self.mutate(self.READY_LOOP, self.counted_loop(body)),
                    RULE_BOUNDED_POLL,
                    "does not test its own counter to stop",
                )

    def test_a_counter_kept_by_the_shell_is_accepted(self) -> None:
        for label, body in (
            ("redirected", "  ready_waited=$((ready_waited + 1)) 2>/dev/null\n  sleep 1\n"),
            ("and list", "  ready_waited=$((ready_waited + 1)) && sleep 1\n"),
        ):
            with self.subTest(written=label):
                self.assert_accepted(
                    self.mutate(self.READY_LOOP, self.counted_loop(body))
                )

    def test_a_counter_raised_on_every_turn_is_accepted(self) -> None:
        for label, replacement in (
            (
                "one line",
                'while [ "$ready_waited" -lt 30 ]; do'
                " ready_waited=$((ready_waited + 1)); sleep 1; done\n",
            ),
            (
                "after a semicolon",
                self.counted_loop("  sleep 1; ready_waited=$((ready_waited + 1))\n"),
            ),
            (
                "in a group",
                self.counted_loop(
                    "  { ready_waited=$((ready_waited + 1)); }\n  sleep 1\n"
                ),
            ),
        ):
            with self.subTest(written=label):
                self.assert_accepted(self.mutate(self.READY_LOOP, replacement))

    def test_a_nested_loop_does_not_bound_the_loop_holding_it(self) -> None:
        for label, replacement in (
            (
                "no outer exit",
                "while true; do\n"
                "  inner=0\n"
                "  while true; do\n"
                '    if [ "$inner" -ge 3 ]; then\n'
                "      break\n"
                "    fi\n"
                "    inner=$((inner + 1))\n"
                "  done\n"
                "  sleep 1\n"
                "done\n",
            ),
            (
                "outer never stops",
                "while true; do\n"
                '  if [ -e "$ready_file" ]; then\n'
                "    :\n"
                "  fi\n"
                "  inner=0\n"
                '  while [ "$inner" -lt 3 ]; do\n'
                "    inner=$((inner + 1))\n"
                "  done\n"
                "  sleep 1\n"
                "done\n",
            ),
        ):
            with self.subTest(loop=label):
                self.assert_rejected(
                    self.mutate(self.READY_LOOP, replacement),
                    RULE_BOUNDED_POLL,
                    "maintains no counter",
                )

    def test_a_bounded_loop_holding_a_nested_loop_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                self.READY_LOOP,
                'while [ "$ready_waited" -lt 30 ]; do\n'
                + self.GUARD
                + "  inner=0\n"
                '  while [ "$inner" -lt 3 ]; do\n'
                "    inner=$((inner + 1))\n"
                "  done\n"
                + self.INCREMENT
                + "  sleep 1\n"
                "done\n",
            )
        )

    def test_a_loop_terminator_written_as_an_argument_is_not_an_end(self) -> None:
        for label, replacement in (
            (
                "echo",
                'while [ "$ready_waited" -lt 30 ]; do\n'
                '  if [ -e "$ready_file" ]; then\n'
                "    echo done\n"
                "    break\n"
                "  fi\n" + self.INCREMENT + "  sleep 1\n"
                "done\n",
            ),
            (
                "comparison",
                'while [ "$ready_waited" -lt 30 ]; do\n'
                '  status=$(cat "$ready_file" 2>/dev/null || printf waiting)\n'
                '  [ "$status" = done ] && break\n' + self.INCREMENT + "  sleep 1\n"
                "done\n",
            ),
        ):
            with self.subTest(written=label):
                self.assert_accepted(self.mutate(self.READY_LOOP, replacement))

    def test_a_nested_case_head_does_not_guard_an_outer_arm(self) -> None:
        self.assert_rejected(
            self.mutate(
                self.READY_LOOP,
                "while true; do\n"
                '  state=$(cat "$ready_file" 2>/dev/null || printf waiting)\n'
                '  case "$state" in\n'
                "    waiting)\n"
                '      case "$ready_waited" in\n'
                "        99) sleep 1 ;;\n"
                "      esac\n"
                "      ;;\n"
                "    ready)\n"
                "      break\n"
                "      ;;\n"
                "  esac\n" + self.INCREMENT + "  sleep 1\n"
                "done\n",
            ),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )

    def test_a_counter_written_last_in_the_body_is_counted(self) -> None:
        self.assert_accepted(
            self.mutate(
                self.READY_LOOP,
                'while [ "$ready_waited" -lt 30 ]; do\n'
                + self.GUARD
                + "  sleep 1\n"
                + self.INCREMENT
                + "done\n",
            )
        )

    def test_a_loop_that_only_continues_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate("    break\n", "    continue\n"),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )

    def test_a_limit_test_guarding_only_a_continue_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                self.READY_LOOP,
                "while true; do\n"
                '  if [ -e "$ready_file" ]; then\n'
                "    break\n"
                "  fi\n"
                "  ready_waited=$((ready_waited + 1))\n"
                '  if [ "$ready_waited" -ge 30 ]; then\n'
                "    continue\n"
                "  fi\n"
                "  sleep 1\n"
                "done\n",
            ),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )

    def test_an_exit_nested_under_a_different_test_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                self.READY_LOOP,
                "while true; do\n"
                '  if [ "$ready_waited" -lt 30 ]; then\n'
                '    if [ -e "$ready_file" ]; then\n'
                "      break\n"
                "    fi\n"
                "  fi\n"
                "  ready_waited=$((ready_waited + 1))\n"
                "  sleep 1\n"
                "done\n",
            ),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )

    def test_a_limit_test_guarding_an_exit_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                self.READY_LOOP,
                "while true; do\n"
                '  if [ -e "$ready_file" ]; then\n'
                "    break\n"
                "  fi\n"
                "  ready_waited=$((ready_waited + 1))\n"
                '  if [ "$ready_waited" -ge 30 ]; then\n'
                "    exit 1\n"
                "  fi\n"
                "  sleep 1\n"
                "done\n",
            )
        )

    def test_an_arithmetic_limit_test_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                '[ "$ready_waited" -lt 30 ]', '[ "$((ready_waited))" -lt 30 ]'
            )
        )

    def test_an_exit_guarded_by_something_else_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                self.READY_LOOP,
                "while true; do\n"
                "  ready_waited=$((ready_waited + 1))\n"
                '  if [ -e "$ready_file" ]; then\n'
                "    break\n"
                "  fi\n"
                "  sleep 1\n"
                "done\n",
            ),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )

    def test_counter_the_condition_never_reads_is_rejected(self) -> None:
        mutated = self.mutate('while [ "$ready_waited" -lt 30 ]; do', "while true; do")
        self.assert_rejected(
            self.mutate(
                "ready_waited=$((ready_waited + 1))", "junk=$((1 + 1))", mutated
            ),
            RULE_BOUNDED_POLL,
            "does not test its own counter to stop",
        )


class ReleasePathTest(ContractSupportTest):
    def test_missing_normal_release_path_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('rm -f "$release_file"\n\nrelease_waited=0', "\nrelease_waited=0"),
            RULE_RELEASE_PATH,
            "no unconditional before-stage release path",
        )

    def test_missing_ready_failure_release_path_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                """if [ ! -e "$ready_file" ]; then
  rm -f "$release_file"
""",
                """if [ ! -e "$ready_file" ]; then
""",
            ),
            RULE_RELEASE_PATH,
            "no ready-failure release path",
        )

    def test_missing_cleanup_release_path_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('  result=$?\n  rm -f "$release_file"\n', "  result=$?\n"),
            RULE_RELEASE_PATH,
            "cleanup handler runs no before-stage release path",
        )

    def test_release_before_the_ready_event_is_rejected(self) -> None:
        mutated = self.mutate(
            """ready_waited=0
while [ "$ready_waited" -lt 30 ]; do
  if [ -e "$ready_file" ]; then
    break
  fi
  ready_waited=$((ready_waited + 1))
  sleep 1
done
if [ ! -e "$ready_file" ]; then
  rm -f "$release_file"
  echo "the guardian ready event was not observed" >&2
  exit 1
fi

grep -q '"state": "pending"' "$attempt_state"
guardian_pid=$(cat "$tmp/guardian.pid")
[ "$guardian_pid" -gt 0 ]

rm -f "$release_file"
""",
            """rm -f "$release_file"

ready_waited=0
while [ "$ready_waited" -lt 30 ]; do
  if [ -e "$ready_file" ]; then
    break
  fi
  ready_waited=$((ready_waited + 1))
  sleep 1
done
if [ ! -e "$ready_file" ]; then
  rm -f "$release_file"
  echo "the guardian ready event was not observed" >&2
  exit 1
fi

grep -q '"state": "pending"' "$attempt_state"
guardian_pid=$(cat "$tmp/guardian.pid")
[ "$guardian_pid" -gt 0 ]
""",
        )
        self.assert_rejected(
            mutated, RULE_RELEASE_PATH, "released before the ready event is observed"
        )


class StateOrderTest(ContractSupportTest):
    def test_missing_pending_assertion_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('grep -q \'"state": "pending"\' "$attempt_state"\n', ""),
            RULE_STATE_ORDER,
            "never asserts the pending attempt state",
        )

    def test_pending_assertion_after_the_release_is_rejected(self) -> None:
        mutated = self.mutate(
            """grep -q '"state": "pending"' "$attempt_state"
guardian_pid=$(cat "$tmp/guardian.pid")
[ "$guardian_pid" -gt 0 ]

rm -f "$release_file"
""",
            """guardian_pid=$(cat "$tmp/guardian.pid")
[ "$guardian_pid" -gt 0 ]

rm -f "$release_file"
grep -q '"state": "pending"' "$attempt_state"
""",
        )
        self.assert_rejected(
            mutated, RULE_STATE_ORDER, "asserted after the before-stage release"
        )

    def test_missing_consumed_assertion_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('\ngrep -q \'"state": "consumed"\' "$attempt_state"\n', "\n"),
            RULE_STATE_ORDER,
            "never asserts the consumed attempt state",
        )

    def test_consumed_assertion_before_the_reap_is_rejected(self) -> None:
        moved = COMPLIANT.replace(
            '\ngrep -q \'"state": "consumed"\' "$attempt_state"\n', "\n"
        )
        mutated = self.mutate(
            'wait "$update_pid"\nkill -TERM',
            'grep -q \'"state": "consumed"\' "$attempt_state"\n'
            'wait "$update_pid"\nkill -TERM',
            moved,
        )
        self.assert_rejected(
            mutated, RULE_STATE_ORDER, "asserted before the update child is reaped"
        )

    def test_conditionally_enclosed_consumed_assertion_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'grep -q \'"state": "consumed"\' "$attempt_state"\n',
                'if [ -e "$attempt_state" ]; then\n'
                '  grep -q \'"state": "consumed"\' "$attempt_state"\n'
                'fi\n',
            ),
            RULE_STATE_ORDER,
            "consumed attempt state assertion can be skipped",
        )


class ChildReapTest(ContractSupportTest):
    def test_missing_termination_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('kill -TERM "$update_pid" 2>/dev/null || true\n', ""),
            RULE_CHILD_REAP,
            "never terminates the update child",
        )

    def test_termination_before_the_bounded_wait_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                """wait "$update_pid"
kill -TERM "$update_pid" 2>/dev/null || true
sleep 5
""",
                """kill -TERM "$update_pid" 2>/dev/null || true
sleep 5
""",
            ),
            RULE_CHILD_REAP,
            "terminated before the bounded wait",
        )

    def test_missing_grace_period_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'kill -TERM "$update_pid" 2>/dev/null || true\nsleep 5\n',
                'kill -TERM "$update_pid" 2>/dev/null || true\n',
            ),
            RULE_CHILD_REAP,
            "grace period",
        )

    def test_missing_forced_termination_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('kill -KILL "$update_pid" 2>/dev/null || true\n', ""),
            RULE_CHILD_REAP,
            "never forcibly terminated",
        )

    def test_missing_final_reap_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'kill -KILL "$update_pid" 2>/dev/null || true\n'
                'wait "$update_pid" 2>/dev/null || true\n',
                'kill -KILL "$update_pid" 2>/dev/null || true\n',
            ),
            RULE_CHILD_REAP,
            "never reaped after forced termination",
        )

    def test_conditionally_enclosed_final_reap_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'wait "$update_pid" 2>/dev/null || true\nupdate_pid=\n',
                'if [ -n "$update_pid" ]; then\n'
                '  wait "$update_pid" 2>/dev/null || true\n'
                'fi\n'
                'update_pid=\n',
            ),
            RULE_CHILD_REAP,
            "final update-child reap can be skipped",
        )

    def test_missing_pid_clear_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'wait "$update_pid" 2>/dev/null || true\nupdate_pid=\n',
                'wait "$update_pid" 2>/dev/null || true\n',
            ),
            RULE_CHILD_REAP,
            "is not cleared after the reap",
        )


class GuardianTest(ContractSupportTest):
    def test_missing_positive_guardian_pid_check_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate('[ "$guardian_pid" -gt 0 ]\n', ""),
            RULE_GUARDIAN,
            "never proves the guardian PID is positive",
        )

    def test_conditionally_enclosed_guardian_assertion_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '[ "$guardian_pid" -gt 0 ]\n',
                'if [ -n "$maybe" ]; then\n  [ "$guardian_pid" -gt 0 ]\nfi\n',
            ),
            RULE_GUARDIAN,
            "guardian PID assertion can be skipped",
        )

    def test_missing_guardian_cleanup_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '    kill -TERM "$guardian_pid" 2>/dev/null || true\n',
                '    echo "leaving the guardian running" >&2\n',
            ),
            RULE_GUARDIAN,
            "never stops the detached guardian",
        )

    def test_fixture_without_a_cleanup_handler_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate("trap cleanup EXIT HUP INT TERM\n", ""),
            RULE_GUARDIAN,
            "registers no cleanup handler for the guardian",
        )


class AlternatePathTest(ContractSupportTest):
    def test_second_copier_update_path_during_the_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'rm -f "$release_file"\n\nrelease_waited=0',
                'rm -f "$release_file"\n'
                'run_copier update -q --defaults --vcs-ref v1.4.5 "$project"\n\n'
                'release_waited=0',
            ),
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_second_copier_update_path_through_a_variable_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'wait "$update_pid"\n',
                'alternate="$project/.project-agent-workflow/scripts/update-from-copier.sh"\n'
                '"$alternate" --defaults --vcs-ref v1.4.4\n'
                'wait "$update_pid"\n',
            ),
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_an_indirect_second_update_path_is_rejected(self) -> None:
        wrapper = "$project/.project-agent-workflow/scripts/update-from-copier.sh"
        for inserted in (
            f'timeout 60 "{wrapper}" --defaults\n',
            f'sh -c "{wrapper}"\n',
            f'run_w() {{\n  "$1" --defaults\n}}\nrun_w "{wrapper}"\n',
            f'run_w() {{\n  "$@"\n}}\nrun_w "{wrapper}" --defaults\n',
        ):
            with self.subTest(inserted=inserted.splitlines()[-1]):
                self.assert_rejected(
                    self.mutate(
                        'wait "$update_pid"\n', inserted + 'wait "$update_pid"\n'
                    ),
                    RULE_ALTERNATE_PATH,
                    "second Copier update path",
                )

    def test_a_helper_running_an_unrelated_path_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT + 'run_w() {\n  "$1" --check\n}\nrun_w "$project/report.sh"\n'
        )

    def test_naming_the_update_wrapper_is_not_an_update_path(self) -> None:
        wrapper = "$project/.project-agent-workflow/scripts/update-from-copier.sh"
        for named in (
            f'test -x "{wrapper}"\n',
            f'wrapper="{wrapper}"\ntest -x "$wrapper"\n',
            'grep -q "update-from-copier.sh" "$project/manifest.txt"\n',
            'note="copier update finished"\necho "$note" >&2\n',
        ):
            with self.subTest(named=named.splitlines()[-1]):
                self.assert_accepted(COMPLIANT + named)

    def test_second_copier_update_path_before_the_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"',
                'run_copier update -q --defaults --vcs-ref v1.4.5 "$project"\n'
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"',
            ),
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_second_copier_update_path_after_the_reap_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + 'run_copier update -q --defaults --vcs-ref v1.4.5 "$project"\n',
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )


class NameBindingTest(unittest.TestCase):
    """The surfaces that decide which names a fixture may bind.

    Every case here is a spelling one of the stopped review rounds reported. A
    name a fixture may bind through any surface must be reported unsettled, and
    a surface written in a form the checker does not enumerate must leave the
    name unsettled rather than settled.
    """

    def build(self, body: str):
        """Return the derived fixture for one written body."""

        text = "#!/bin/sh\nset -eu\n" + body
        records = shell_lexical.project(text)
        table = shell_functions.derive(records)
        graph = shell_execution.derive(records, table)
        return copier_fixture_validator._Fixture(text, records, table, graph)

    def unsettled(self, body: str) -> frozenset:
        """Return every name the checker cannot settle in one written body."""

        return self.build(body).unsettled_names()

    def test_a_standalone_assignment_settles_its_name(self):
        self.assertNotIn("dest", self.unsettled('dest=/tmp/one\nprintf %s "$dest"\n'))

    def test_a_second_assignment_written_as_one_command_unsettles_its_name(self):
        self.assertIn("other", self.unsettled('dest=/tmp/one other=/tmp/two\n'))

    def test_a_prefix_assignment_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('dest=/tmp/one printf %s x\n'))

    def test_a_prefix_assignment_written_with_a_redirection_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('dest=>/dev/null printf %s x\n'))

    def test_a_prefix_assignment_written_with_a_substitution_unsettles_its_name(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one other=$(printf x) printf %s y\n'),
        )

    def test_a_prefix_assignment_written_with_a_quoted_value_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('dest="/tmp/one; two" printf %s x\n'))

    def test_a_quoted_name_opens_an_assignment(self):
        self.assertIn("dest", self.unsettled('de"st"=/tmp/one printf %s x\n'))

    def test_a_quoted_equals_opens_no_assignment(self):
        self.assertNotIn("dest", self.unsettled('printf %s "dest=/tmp/one"\n'))

    def test_an_escaped_equals_opens_no_assignment(self):
        self.assertNotIn("dest", self.unsettled('printf %s dest\\=/tmp/one\n'))

    def test_an_assigning_command_unsettles_its_operand(self):
        self.assertIn("dest", self.unsettled('read -r dest\n'))

    def test_an_assigning_command_unsettles_a_quoted_operand(self):
        self.assertIn("dest", self.unsettled("read -r 'dest'\n"))

    def test_an_exported_name_is_unsettled(self):
        self.assertIn("dest", self.unsettled('export dest=/tmp/one\n'))

    def test_a_launcher_that_stays_in_the_shell_reads_what_it_launches(self):
        self.assertNotIn(
            "dest", self.unsettled('dest=/tmp/one\ncommand true dest\n')
        )
        self.assertIn("dest", self.unsettled('command read -r dest\n'))
        self.assertIn("dest", self.unsettled('command "$reader" dest\n'))

    def test_a_launcher_that_forks_settles_a_bare_operand(self):
        self.assertNotIn(
            "dest", self.unsettled('dest=/tmp/one\nenv dest true\n')
        )

    def test_a_command_word_carrying_a_slash_settles_a_bare_operand(self):
        self.assertNotIn(
            "dest", self.unsettled('dest=/tmp/one\n"$helper/run.sh" dest\n')
        )

    def test_a_command_reached_through_a_name_unsettles_its_operand(self):
        self.assertIn("dest", self.unsettled('reader=read\n"$reader" -r dest\n'))

    def test_a_command_reached_through_two_names_unsettles_its_operand(self):
        self.assertIn(
            "dest",
            self.unsettled('first=read\nsecond=$first\n"$second" -r dest\n'),
        )

    def test_a_declared_assigning_command_still_unsettles_its_operand(self):
        self.assertIn(
            "dest",
            self.unsettled('read() { :; }\nread dest\n'),
        )

    def test_a_dynamic_operand_of_an_assigning_command_unsettles_every_name(self):
        unsettled = self.unsettled(
            'dest=/tmp/one\nname=dest=/evil\nexport $name\n'
        )
        self.assertIn("dest", unsettled)
        self.assertIn("name", unsettled)

    def test_a_dynamic_operand_of_an_unresolvable_command_unsettles_every_name(self):
        unsettled = self.unsettled(
            'dest=/tmp/one\nrunner=export\nvalue=dest=/evil\n"$runner" "$value"\n'
        )
        self.assertIn("dest", unsettled)

    def test_a_dynamic_named_option_target_unsettles_every_name(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nptr=dest\nprintf -v "$ptr" %s /evil\n'),
        )

    def test_a_sourced_path_operand_settles_its_names(self):
        self.assertNotIn(
            "dest",
            self.unsettled('dest=/tmp/one\nlib=/tmp/lib.sh\n. "$lib"\n'),
        )

    def test_a_loop_head_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('for dest in a b; do :; done\n'))

    def test_a_continued_loop_head_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('for \\\n  dest in a b; do :; done\n'))

    def test_a_name_a_shell_keeps_itself_is_unsettled(self):
        self.assertIn("PWD", self.unsettled('printf %s "$PWD"\n'))
        self.assertIn("IFS", self.unsettled('printf %s "$IFS"\n'))

    def test_a_first_assignment_written_under_a_condition_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('if false; then\n  dest=/tmp/one\nfi\n'),
        )

    def test_a_first_assignment_written_in_a_function_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('run() {\n  dest=/tmp/one\n}\nrun\n'),
        )

    def test_a_later_assignment_in_a_function_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nrun() {\n  dest=/tmp/two\n}\nrun\n'),
        )

    def test_a_separator_written_inside_a_quoted_span_opens_no_command(self):
        self.assertNotIn(
            "dest",
            self.unsettled('printf %s "; dest=/tmp/one"\ndest=/tmp/two\n'),
        )

    def test_a_command_written_after_a_separator_is_read_as_its_own(self):
        self.assertIn("dest", self.unsettled('printf %s x; dest=/tmp/one printf %s y\n'))

    def test_a_reserved_word_never_hides_a_prefix_assignment(self):
        self.assertIn("dest", self.unsettled('if dest=/tmp/one printf %s x; then :; fi\n'))

    def test_a_heredoc_body_opens_no_command(self):
        self.assertNotIn(
            "dest",
            self.unsettled('cat <<EOF\ndest=/tmp/one printf\nEOF\ndest=/tmp/two\n'),
        )

    def test_a_redirection_target_is_not_a_command_word(self):
        self.assertNotIn(
            "dest",
            self.unsettled('printf %s x >/tmp/out\ndest=/tmp/two\n'),
        )

    def test_an_assignment_written_under_a_condition_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nif false; then dest=/tmp/two; fi\n'),
        )

    def test_an_assignment_written_in_a_loop_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nfor i in a; do dest=/tmp/two; done\n'),
        )

    def test_an_assignment_written_in_a_case_branch_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\ncase x in y) dest=/tmp/two;; esac\n'),
        )

    def test_an_assignment_written_behind_an_or_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('dest=/tmp/one\nfalse || dest=/tmp/two\n')
        )

    def test_an_assignment_written_in_a_subshell_is_unsettled(self):
        self.assertIn("dest", self.unsettled('dest=/tmp/one\n( dest=/tmp/two )\n'))

    def test_an_assignment_written_in_a_pipeline_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nprintf %s x | { dest=/tmp/two; }\n'),
        )

    def test_an_assignment_written_behind_an_ampersand_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('dest=/tmp/one\n{ dest=/tmp/two; } &\n')
        )

    def test_a_parenthesis_written_inside_a_quoted_span_detaches_nothing(self):
        self.assertNotIn(
            "dest",
            self.unsettled('printf %s "("\ndest=/tmp/one\nprintf %s "$dest"\n'),
        )

    def test_an_assigning_parameter_expansion_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nprintf %s "${dest:=/tmp/two}"\n'),
        )

    def test_a_reading_parameter_expansion_settles_its_name(self):
        self.assertNotIn(
            "dest",
            self.unsettled('dest=/tmp/one\nprintf %s "${dest:-/tmp/two}"\n'),
        )

    def test_an_arithmetic_expansion_unsettles_every_name_it_writes(self):
        self.assertIn("dest", self.unsettled('dest=1\n: $((dest + 1))\n'))

    def test_a_trap_string_unsettles_the_name_it_assigns(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\ntrap "dest=/tmp/two" EXIT\n'),
        )

    def test_an_attached_named_option_unsettles_its_name(self):
        self.assertIn(
            "dest", self.unsettled('dest=/safe\nprintf -vdest "%s" /evil\n')
        )

    def test_a_detached_named_option_unsettles_its_name(self):
        self.assertIn(
            "dest", self.unsettled('dest=/safe\nprintf -v dest "%s" /evil\n')
        )

    def test_an_arithmetic_expansion_in_a_heredoc_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=1\ncat <<EOF >/dev/null\n$((dest=5))\nEOF\n'),
        )

    def test_a_parameter_assignment_in_a_heredoc_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('cat <<EOF >/dev/null\n${dest:=/tmp/evil}\nEOF\n'),
        )

    def test_a_continued_assignment_name_is_unsettled(self):
        self.assertIn("dest", self.unsettled('de\\\nst=/evil\n'))

    def test_a_redirected_group_written_behind_an_ampersand_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('{ dest=/tmp/two; } >/dev/null &\n')
        )

    def test_a_redirected_group_written_beside_a_pipe_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('{ dest=/tmp/two; } 2>/dev/null | cat\n')
        )

    def test_a_group_written_with_a_heredoc_behind_an_ampersand_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('{ dest=/tmp/two; } <<EOF &\nbody\nEOF\n'),
        )

    def test_a_redirected_group_that_is_not_detached_settles_its_name(self):
        self.assertNotIn(
            "dest",
            self.unsettled(
                'dest=/tmp/one\n{ dest=/tmp/two; } >/dev/null\nprintf %s "$dest"\n'
            ),
        )

    def test_a_descriptor_variable_redirection_unsettles_its_name(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nexec {dest}>/dev/null\n'),
        )

    def test_an_unaccepted_construct_unsettles_every_written_name(self):
        fixture = self.build('dest=/tmp/one\nexec {fd}>/dev/null\nother=/tmp/two\n')
        self.assertTrue(fixture.unaccepted_constructs())
        unsettled = fixture.unsettled_names()
        self.assertIn("dest", unsettled)
        self.assertIn("other", unsettled)
        self.assertIn("fd", unsettled)

    def test_a_brace_expansion_is_an_unaccepted_construct(self):
        self.assertTrue(self.build('printf %s a{b,c}\n').unaccepted_constructs())

    def test_a_quoted_brace_is_an_accepted_construct(self):
        fixture = self.build('dest=/tmp/one\nprintf %s "{}"\n')
        self.assertEqual(fixture.unaccepted_constructs(), ())
        self.assertNotIn("dest", fixture.unsettled_names())

    def test_a_group_brace_is_an_accepted_construct(self):
        fixture = self.build('dest=/tmp/one\n{ printf %s x; }\n')
        self.assertEqual(fixture.unaccepted_constructs(), ())
        self.assertNotIn("dest", fixture.unsettled_names())

    def test_the_accepted_constructs_cover_the_forms_the_grammar_reads(self):
        fixture = self.build(
            'dest=/tmp/one\n'
            "printf '%s' \"$dest\" >/dev/null 2>&1\n"
            'cat <<EOF | { printf %s x; } || true\nbody\nEOF\n'
            '# a comment\n'
            'run() { printf %s "$(printf y)"; }\n'
            'for item in a b; do run; done\n'
        )
        self.assertEqual(fixture.unaccepted_constructs(), ())

    def test_an_expanded_word_denotes_no_settled_text(self):
        text = shell_lexical.project('"$dest"').tokens[0]
        self.assertIsNone(copier_fixture_validator._token_text(text))

    def test_a_quoted_word_denotes_its_inner_text(self):
        text = shell_lexical.project('"de"st').tokens[0]
        self.assertEqual(copier_fixture_validator._token_text(text), "dest")


class WordGrammarTest(unittest.TestCase):
    """Prove a word settles only when the modelled grammar writes all of it."""

    module = copier_fixture_validator

    def fixture(self, source: str):
        records = self.module.shell_lexical.project(source)
        table = self.module.shell_functions.derive(records)
        graph = self.module.shell_execution.derive(records, table)
        return self.module._Fixture(source, records, table, graph)

    def bind(self, values: dict[str, tuple[str, ...]] | None):
        """Return one binding map holding only values written as plain text.

        A substitution is bound only where an assignment runs it once, which
        this helper cannot express, so it refuses a value that carries one and
        every test that needs one builds a fixture instead.
        """

        bindings: dict[str, object] = {}
        for name, texts in (values or {}).items():
            settled: list[object] = []
            for index, text in enumerate(texts):
                parts = self.module._word_parts(text, f"a{name}{index}", splits=False)
                if parts is None:
                    settled = None
                    break
                self.assertFalse(
                    self.module._carries_substitution((parts,)),
                    "bind() holds only values written as plain text",
                )
                grown = self.module._resolve_parts(parts, bindings, frozenset())
                if grown is None:
                    settled = None
                    break
                settled.extend(grown)
            bindings[name] = None if settled is None else tuple(settled)
        return bindings

    def settle(self, word: str, values: dict[str, tuple[str, ...]] | None = None):
        return self.module._settle_word(word, self.bind(values), origin=word)

    def settled_word(self, source: str, word: str, command: str = "printf"):
        """Return every path one word names where one fixture command runs."""

        fixture = self.fixture(source)
        operation = next(
            item
            for item in fixture.operations
            if item.reachable and item.name == command
        )
        return self.module._settle_written_word(fixture, operation, word)

    def test_a_word_outside_the_grammar_is_unproven(self) -> None:
        for word in (
            '"$1"',
            '"$@"',
            '"$*/x"',
            '"$$/x"',
            '"$!/x"',
            '"$-/x"',
            '"$?/x"',
            '"${x:-ln}"',
            '"${x#/a}"',
            "'$dest'",
            "'a\"b'",
            '"$tmp/*"',
            '"$tmp/a?"',
            '"$tmp/[ab]"',
            '"~/p"',
            '"$tmp/a\\b"',
            '"$tmp/a b"',
            '"$tmp',
            '""',
            "",
            '"$((1 + 1))/x"',
            '"$(printf %s $(echo x))"',
            '"$(printf %s x"',
            '"a;b"',
            '"a|b"',
            '"a>b"',
            '"a&b"',
        ):
            with self.subTest(word=word):
                self.assertEqual(
                    self.settle(word, {"tmp": ("/tmp",), "dest": ("/tmp/a",)}),
                    frozenset(),
                )

    def test_an_unquoted_expansion_in_a_command_word_is_unproven(self) -> None:
        """A shell splits an unquoted expansion into fields it may not model."""

        for word in ("$tmp/x", "${tmp}/x", "$(printf %s /tmp)/x", "a$tmp"):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word, {"tmp": ("/tmp",)}), frozenset())

    def test_an_assignment_reads_its_value_without_splitting_it(self) -> None:
        settled = self.settled_word(
            'base=$(pwd -P)\nprintf %s "$base/x"\n', '"$base/x"'
        )
        self.assertEqual(len(settled), 1)
        self.assertEqual(next(iter(settled))[1][1:], ("x",))

    def test_a_backquote_never_settles(self) -> None:
        self.assertEqual(self.settle('"`printf %s /tmp`/x"'), frozenset())

    def test_a_modelled_word_settles_to_its_segments(self) -> None:
        for word, values, expected in (
            ("/a/b", {}, (True, ("a", "b"))),
            ('"$tmp/p"', {"tmp": ("/tmp",)}, (True, ("tmp", "p"))),
            ('"${tmp}/p"', {"tmp": ("/tmp",)}, (True, ("tmp", "p"))),
            ("/a//b/./c/", {}, (True, ("a", "b", "c"))),
            ('"$t/x"', {}, (False, ("$t", "x"))),
        ):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word, values), frozenset({expected}))

    def test_a_substitution_in_a_command_word_is_unproven(self) -> None:
        """A command word runs its substitution again each time it runs."""

        for word in ('"$(cat anchor)/a"', '"$(pwd -P)/a"'):
            with self.subTest(word=word):
                self.assertEqual(
                    self.settled_word(f"printf %s {word}\n", word), frozenset()
                )

    def test_a_bound_substitution_settles_as_one_opaque_segment(self) -> None:
        source = 'base=$(CDPATH= cd -- /tmp && pwd -P)\nprintf %s "$base/x"\n'
        settled = self.settled_word(source, '"$base/x"')
        self.assertEqual(len(settled), 1)
        anchored, segments = next(iter(settled))
        self.assertTrue(anchored)
        self.assertTrue(self.module._carries_expansion(segments[0]))
        self.assertEqual(segments[1:], ("x",))

    def test_only_the_modelled_command_list_anchors_a_substitution(self) -> None:
        """Any other list may write a path the working directory decides."""

        for value in (
            "$(mktemp -d)",
            "$(printf %s x; pwd)",
            "$(printf .)",
            "$(cd /tmp && printf %s x)",
        ):
            source = f'base={value}\nprintf %s "$base/x"\n'
            with self.subTest(value=value):
                settled = self.settled_word(source, '"$base/x"')
                self.assertEqual({anchored for anchored, _ in settled}, {False})

    def test_a_declared_command_never_anchors_a_substitution(self) -> None:
        source = (
            "pwd() { printf %s relative; }\n"
            "base=$(cd /tmp && pwd)\n"
            'printf %s "$base/x"\n'
        )
        settled = self.settled_word(source, '"$base/x"')
        self.assertEqual({anchored for anchored, _ in settled}, {False})

    def test_a_special_parameter_is_never_settled(self) -> None:
        """A special parameter names text no assignment in the fixture writes."""

        for word in ('"$0"', '"$1/x"', '"$@"', '"$#"', '"$?"', '"$$/x"', '"$!"'):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word), frozenset())

    def test_a_substitution_list_writing_more_than_one_command_is_unanchored(
        self,
    ) -> None:
        """Only the one modelled list anchors a path; every other list does not."""

        for value in (
            "$(cd /tmp && pwd && printf %s /evil)",
            "$(pwd; printf %s /evil)",
            "$(printf %s /evil && pwd)",
            "$(cd /tmp && pwd | tr -d x)",
        ):
            with self.subTest(value=value):
                source = f"base={value}\nprintf %s \"$base/x\"\n"
                settled = self.settled_word(source, '"$base/x"')
                self.assertNotIn(True, {anchored for anchored, _ in settled})

    def test_the_committed_fixture_anchors_only_the_modelled_list(self) -> None:
        """The committed fixture writes both a modelled and an unmodelled list."""

        source = Path("tests/copier-update.sh").read_text(encoding="utf-8")
        fixture = self.fixture(source)
        bindings = fixture.bindings_before(len(source))
        unsettled = fixture.unsettled_names()
        self.assertEqual(
            self.module._settle_word('"$root"', bindings, unsettled),
            frozenset(),
            "a nested substitution is outside the grammar",
        )
        self.assertEqual(
            {anchored for anchored, _ in self.module._settle_word(
                '"$tmp/x"', bindings, unsettled
            )},
            {True},
            "the modelled command list anchors the path it writes",
        )

    def test_a_parent_segment_is_never_modelled(self) -> None:
        """A parent segment names a directory the links above it decide."""

        for word in ('"$t/.."', "../a", "/a/b/../c", "/a/..", '"/tmp/a/../b"'):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word), frozenset())

    def test_every_value_a_name_may_hold_is_settled(self) -> None:
        """A name bound more than once settles to every value it may hold."""

        self.assertEqual(
            self.settle('"$dest/x"', {"dest": ("/tmp/one", "/tmp/two")}),
            frozenset({(True, ("tmp", "one", "x")), (True, ("tmp", "two", "x"))}),
        )

    def test_a_name_the_binding_surfaces_report_unsettled_is_unproven(self) -> None:
        """A name a branch may rebind is reported unsettled, so it proves nothing.

        The binding surfaces report which names this checker settles, and a
        name written under a condition is one of them. The parts each value
        carries are still enumerated, but the word that reads the name is
        unproven, because a value this checker never settles may name any path
        at all.
        """

        source = (
            "dest=/tmp/one\n"
            "if [ -d /tmp ]; then\n  dest=/tmp/two\nfi\n"
            'printf %s "$dest"\n'
        )
        fixture = self.fixture(source)
        self.assertIn("dest", fixture.unsettled_names())
        self.assertEqual(self.settled_word(source, '"$dest"'), frozenset())

    def test_a_value_outside_the_grammar_leaves_the_word_unproven(self) -> None:
        self.assertEqual(self.settle('"$dest/x"', {"dest": ("/tmp/*",)}), frozenset())

    def test_a_value_is_read_where_the_assignment_is_written(self) -> None:
        """A shell settles a value once, not again where the name is read."""

        source = "y=/tmp/old\nx=$y\ny=/tmp/new\nprintf %s \"$x\"\n"
        self.assertEqual(
            self.settled_word(source, '"$x"'), frozenset({(True, ("tmp", "old"))})
        )

    def test_a_self_referential_value_terminates(self) -> None:
        source = 't=$t/x\nprintf %s "$t"\n'
        self.assertEqual(
            self.settled_word(source, '"$t"'), frozenset({(False, ("$t", "x"))})
        )

    def test_a_settlement_past_the_text_bound_is_unproven(self) -> None:
        values = {
            f"n{index}": tuple(f"/v{index}-{choice}" for choice in range(4))
            for index in range(4)
        }
        word = '"' + "".join(f"$n{index}" for index in range(4)) + '"'
        self.assertEqual(self.settle(word, values), frozenset())

    def test_a_long_word_settles_without_growing(self) -> None:
        """Repeated names settle once each rather than once per combination."""

        source = (
            "".join(f"n{index}=/a\n" for index in range(20))
            + 'printf %s "'
            + "/".join(f"$n{index}" for index in range(20))
            + '"\n'
        )
        word = '"' + "/".join(f"$n{index}" for index in range(20)) + '"'
        self.assertEqual(
            self.settled_word(source, word), frozenset({(True, ("a",) * 20)})
        )

    def test_a_call_site_value_reaches_a_function_body(self) -> None:
        source = (
            "dest=/tmp/first\n"
            'inner() { printf %s "$dest"; }\n'
            "outer() { inner; }\n"
            "dest=/tmp/second\n"
            "outer\n"
        )
        self.assertEqual(
            self.settled_word(source, '"$dest"'),
            frozenset({(True, ("tmp", "first")), (True, ("tmp", "second"))}),
        )

    def test_a_name_a_command_may_assign_is_never_settled(self) -> None:
        for assigning in (
            "export dest=/tmp/actual",
            "readonly dest=/tmp/actual",
            "read dest",
            "getopts x dest",
            'assign=export\n"$assign" dest=/tmp/actual',
            "command export dest=/tmp/actual",
            "printf -v dest /tmp/actual",
        ):
            source = f'dest=/tmp/outer\n{assigning}\nprintf %s "$dest"\n'
            with self.subTest(assigning=assigning):
                fixture = self.fixture(source)
                self.assertIn("dest", fixture.unsettled_names())

    def test_a_name_written_with_a_value_anywhere_is_never_settled(self) -> None:
        """Only the first assignment of one command is recorded in position."""

        for written in (
            "other=x dest=/tmp/new",
            'dest=/tmp/new other="a b" printf %s x',
            'export de"st"=/tmp/new',
            "unset dest",
        ):
            source = f'dest=/tmp/old\n{written}\nprintf %s "$dest"\n'
            with self.subTest(written=written):
                fixture = self.fixture(source)
                self.assertIn("dest", fixture.unsettled_names())
                self.assertEqual(self.settled_word(source, '"$dest"'), frozenset())

    def test_a_name_the_shell_keeps_itself_is_never_settled(self) -> None:
        """A shell changes these names where no assignment is written."""

        for name in ("PWD", "OLDPWD", "IFS", "OPTIND", "REPLY"):
            with self.subTest(name=name):
                fixture = self.fixture(f'printf %s "${name}/x"\n')
                self.assertIn(name, fixture.unsettled_names())
                self.assertEqual(
                    self.settled_word(f'printf %s "${name}/x"\n', f'"${name}/x"'),
                    frozenset(),
                )

    def test_a_name_a_function_body_assigns_is_never_settled(self) -> None:
        """A function runs where it is called, so its assignment reaches later."""

        source = (
            "set_dest() { dest=/tmp/new; }\n"
            "dest=/tmp/old\n"
            "set_dest\n"
            'printf %s "$dest"\n'
        )
        fixture = self.fixture(source)
        self.assertIn("dest", fixture.unsettled_names())
        self.assertEqual(self.settled_word(source, '"$dest"'), frozenset())

    def test_a_name_a_loop_head_binds_holds_the_head_words(self) -> None:
        """A loop head binds its name from the words written after `in`.

        The name is unsettled everywhere else, because a word written outside
        the loop reads whatever the assignments around it hold, but a word
        written under the loop reads one of the head words.
        """

        source = (
            "dest=/tmp/old\nfor dest in /tmp/new; do\n"
            '  printf %s "$dest"\ndone\n'
        )
        continued = (
            "dest=/tmp/old\nfor \\\n dest in /tmp/new; do\n"
            '  printf %s "$dest"\ndone\n'
        )
        for written in (source, continued):
            with self.subTest(written=written):
                fixture = self.fixture(written)
                self.assertIn("dest", fixture.unsettled_names())
                self.assertEqual(
                    self.settled_word(written, '"$dest"'),
                    frozenset({(True, ("tmp", "new"))}),
                )

    def test_a_loop_head_this_checker_cannot_read_settles_no_name(self) -> None:
        written = (
            'for dest in $(printf %s /tmp/new); do\n'
            '  printf %s "$dest"\ndone\n'
        )
        self.assertEqual(self.settled_word(written, '"$dest"'), frozenset())

    def test_a_prefix_assigned_name_is_never_settled(self) -> None:
        for prefix in (
            'dest=/tmp/new printf %s "$dest"',
            'dest=/tmp/new other=x printf %s "$dest"',
            'dest=/tmp/new \\\n  printf %s "$dest"',
        ):
            source = f'dest=/tmp/old\n{prefix}\n'
            with self.subTest(prefix=prefix):
                fixture = self.fixture(source)
                self.assertIn("dest", fixture.unsettled_names())

    def test_a_standalone_assignment_is_not_a_prefix_assignment(self) -> None:
        fixture = self.fixture('dest=/tmp/old\nprintf %s "$dest"\n')
        self.assertNotIn("dest", fixture.prefix_assigned_names())

    def test_two_paths_are_separate_only_when_written_text_keeps_them_apart(
        self,
    ) -> None:
        for left, right, expected in (
            ('"$x/a"', '"$x/b"', False),
            ('"/tmp/a"', '"/tmp/b"', True),
            ('"${x}a"', '"${x}/a"', False),
            ('"/tmp/a"', '"/tmp//a"', False),
            ('"/tmp/a/$tail"', '"/tmp/b/$tail"', False),
            ('"/tmp/a"', '"/tmp/a/b"', False),
            ('"/tmp/a"', '"/tmp/a"', False),
            ("project", "/tmp/project", False),
            ("project", "other", False),
            ('"$x/a"', '"/tmp/a"', False),
        ):
            with self.subTest(left=left, right=right):
                self.assertIs(
                    self.module._paths_are_lexically_separate(
                        self.settle(left), self.settle(right)
                    ),
                    expected,
                )

    def test_a_path_this_checker_cannot_anchor_is_never_separate(self) -> None:
        """A fixture may change the directory a relative path starts from."""

        source = (
            "base=$(printf .)\n"
            'printf %s "$base/scripts"\n'
            "cd scripts\n"
            'printf %s "$base/other"\n'
        )
        fixture = self.fixture(source)
        commands = [
            item
            for item in fixture.operations
            if item.reachable and item.name == "printf"
        ]
        left = self.module._settle_written_word(fixture, commands[0], '"$base/scripts"')
        right = self.module._settle_written_word(fixture, commands[1], '"$base/other"')
        self.assertTrue(left)
        self.assertTrue(right)
        self.assertFalse(self.module._paths_are_lexically_separate(left, right))

    def test_one_binding_read_twice_is_one_anchor(self) -> None:
        source = (
            'base=$(pwd -P)\nprintf %s "$base/a"\nprintf %s "$base/b"\n'
        )
        fixture = self.fixture(source)
        commands = [
            item
            for item in fixture.operations
            if item.reachable and item.name == "printf"
        ]
        left = self.module._settle_written_word(fixture, commands[0], '"$base/a"')
        right = self.module._settle_written_word(fixture, commands[1], '"$base/b"')
        self.assertTrue(
            self.module._paths_are_lexically_separate(left, right)
        )
        self.assertFalse(
            self.module._paths_are_lexically_separate(
                left,
                self.module._settle_written_word(
                    fixture, commands[1], '"$base/a/b"'
                ),
            )
        )

    def test_a_repeated_binding_never_anchors_a_comparison(self) -> None:
        """An assignment that may run again may hold another value."""

        source = (
            "if [ -d /tmp ]; then\n  base=$(pwd -P)\nfi\n"
            'printf %s "$base/a"\n'
        )
        self.assertEqual(self.settled_word(source, '"$base/a"'), frozenset())

    def test_an_unproven_side_is_never_separate(self) -> None:
        settled = self.settle("/tmp/a")
        self.assertFalse(
            self.module._paths_are_lexically_separate(settled, frozenset())
        )
        self.assertFalse(
            self.module._paths_are_lexically_separate(frozenset(), settled)
        )

    def test_the_committed_fixture_settles_the_paths_it_writes(self) -> None:
        """The words are read from the fixture rather than written here."""

        source = (ROOT / "tests" / "copier-update.sh").read_text(encoding="utf-8")
        fixture = self.fixture(source)
        self.assertNotIn("tmp", fixture.unsettled_names())
        written: dict[str, tuple[object, frozenset]] = {}
        for operation in fixture.operations:
            if not operation.reachable:
                continue
            for word in operation.text.split():
                if not word.startswith('"$tmp/') or word in written:
                    continue
                settled = self.module._settle_written_word(fixture, operation, word)
                if len(settled) == 1:
                    written[word] = (operation, settled)
        self.assertGreaterEqual(len(written), 2)
        for word, (_, settled) in written.items():
            with self.subTest(word=word):
                anchored, segments = next(iter(settled))
                self.assertTrue(anchored)
                self.assertTrue(self.module._carries_expansion(segments[0]))
                self.assertEqual(
                    len(segments), len(word.strip('"').rstrip("/").split("/"))
                )
        paths = [settled for _, settled in written.values()]
        separate = [
            self.module._paths_are_lexically_separate(left, right)
            for index, left in enumerate(paths)
            for right in paths[index + 1 :]
        ]
        self.assertIn(True, separate)
        first = next(iter(written.values()))[1]
        anchored, segments = next(iter(first))
        inside = (anchored, segments + ("inside",))
        self.assertFalse(
            self.module._paths_are_lexically_separate(first, frozenset({inside}))
        )


class AliasCollectionTest(unittest.TestCase):
    """Prove an alias is collected only from the modelled command grammar."""

    module = copier_fixture_validator

    def fixture(self, source: str):
        records = self.module.shell_lexical.project(source)
        table = self.module.shell_functions.derive(records)
        graph = self.module.shell_execution.derive(records, table)
        return self.module._Fixture(source, records, table, graph)

    def aliases(self, body: str):
        source = "#!/bin/sh\nset -eu\n" + body
        links, unplaced = self.module._symlinked_paths(self.fixture(source))
        return frozenset(self.module._path_text(path) for path in links), unplaced

    def placed(self, body: str) -> frozenset[str]:
        links, unplaced = self.aliases(body)
        self.assertFalse(unplaced, "expected every alias of this fixture to be placed")
        return links

    def test_a_written_symbolic_link_places_both_readings(self) -> None:
        """A second operand may name a directory, so both readings are placed."""

        self.assertEqual(
            self.placed("ln -s /tmp/one /tmp/two\n"),
            frozenset({"/tmp/two", "/tmp/two/one"}),
        )

    def test_a_hard_link_places_no_alias(self) -> None:
        self.assertEqual(self.placed("ln /tmp/one /tmp/two\n"), frozenset())

    def test_a_plain_copy_places_no_alias(self) -> None:
        self.assertEqual(self.placed("cp /tmp/one /tmp/two\n"), frozenset())

    def test_every_symbolic_option_spelling_is_read(self) -> None:
        for option in ("-s", "-sf", "-fs", "--symbolic", "--sym", "--s"):
            with self.subTest(option=option):
                self.assertIn(
                    "/tmp/two", self.placed(f"ln {option} /tmp/one /tmp/two\n")
                )

    def test_a_launched_link_is_read_as_a_link(self) -> None:
        for launcher in ("env", "command", "exec", "nohup"):
            with self.subTest(launcher=launcher):
                self.assertIn(
                    "/tmp/two",
                    self.placed(f"{launcher} ln -s /tmp/one /tmp/two\n"),
                )

    def test_a_command_word_this_checker_cannot_read_is_held_to_the_link_form(
        self,
    ) -> None:
        """An unread command word may name a link, so a link spelling is read."""

        linked, unplaced = self.aliases('runner=/bin/ln\n"$runner" -s /tmp/one /tmp/two\n')
        self.assertEqual(linked, frozenset({"/tmp/two", "/tmp/two/one"}))
        self.assertFalse(unplaced)

    def test_an_unread_command_word_without_a_link_option_places_no_alias(self) -> None:
        self.assertEqual(
            self.placed('runner=/bin/cat\n"$runner" -n /tmp/one\n'), frozenset()
        )

    def test_an_option_this_checker_cannot_read_leaves_the_alias_unplaced(self) -> None:
        """A link option written through an expansion may ask for a link."""

        for body in (
            "opt=-s\nln \"$opt\" /tmp/one /tmp/two\n",
            "opt=-s\nln \"${opt}\" /tmp/one /tmp/two\n",
            'ln "$(printf %s -s)" /tmp/one /tmp/two\n',
            'opt=--symbolic\ncp "$opt" /tmp/one /tmp/two\n',
        ):
            with self.subTest(body=body):
                self.assertTrue(self.aliases(body)[1])

    def test_a_word_written_with_a_slash_is_never_read_as_an_option(self) -> None:
        """A slash is not an option letter, so such a word is an operand."""

        self.assertEqual(
            self.placed('base=/tmp\ncp "$base/one" "$base/two"\n'), frozenset()
        )

    def test_an_operand_settling_to_an_anchored_path_is_never_an_option(self) -> None:
        self.assertEqual(
            self.placed('one=/tmp/one\ntwo=/tmp/two\nln "$one" "$two"\n'), frozenset()
        )

    def test_a_copy_keeps_a_link_whatever_case_the_option_is_written_in(self) -> None:
        """`-R` is a synonym of `-r`, and `-P` asks for no dereference."""

        for option in ("-R", "-P", "-r", "-a", "-d", "-p"):
            with self.subTest(option=option):
                self.assertIn(
                    "/tmp/three",
                    self.placed(
                        "ln -s /tmp/one /tmp/two\n"
                        f"cp {option} /tmp/two /tmp/three\n"
                    ),
                )

    def test_a_long_symbolic_option_is_read_in_every_spelling(self) -> None:
        for option in ("--symbolic", "--symbolic-link", "--sym"):
            with self.subTest(option=option):
                self.assertIn(
                    "/tmp/two",
                    self.placed(f'runner=/bin/cp\n"$runner" {option} /tmp/one /tmp/two\n'),
                )

    def test_a_target_directory_option_leaves_the_alias_unplaced(self) -> None:
        for option in ("-t", "-st", "--target-directory", "--target", "--t"):
            with self.subTest(option=option):
                _, unplaced = self.aliases(f"ln -s {option} /tmp/dir /tmp/one\n")
                self.assertTrue(unplaced)

    def test_an_operand_count_this_checker_does_not_read_leaves_it_unplaced(
        self,
    ) -> None:
        for body in (
            "ln -s /tmp/one\n",
            "ln -s /tmp/one /tmp/two /tmp/dir\n",
        ):
            with self.subTest(body=body):
                self.assertTrue(self.aliases(body)[1])

    def test_an_operand_this_checker_cannot_settle_leaves_it_unplaced(self) -> None:
        self.assertTrue(self.aliases('ln -s /tmp/one "$(printf %s /tmp/two)"\n')[1])

    def test_a_bare_double_dash_ends_the_options(self) -> None:
        self.assertEqual(
            self.placed("ln -s -- /tmp/one /tmp/two\n"),
            frozenset({"/tmp/two", "/tmp/two/one"}),
        )

    def test_a_move_carries_a_tracked_alias(self) -> None:
        self.assertEqual(
            self.placed("ln -s /tmp/one /tmp/two\nmv /tmp/two /tmp/three\n"),
            frozenset(
                {"/tmp/two", "/tmp/two/one", "/tmp/three", "/tmp/three/two"}
            ),
        )

    def test_a_move_option_never_stops_the_alias(self) -> None:
        """A move carries a link whatever options are written with it."""

        self.assertIn(
            "/tmp/three",
            self.placed("ln -s /tmp/one /tmp/two\nmv -f /tmp/two /tmp/three\n"),
        )

    def test_a_copy_keeps_a_link_only_with_a_preserving_option(self) -> None:
        kept = self.placed("ln -s /tmp/one /tmp/two\ncp -a /tmp/two /tmp/three\n")
        self.assertIn("/tmp/three", kept)
        stored = self.placed("ln -s /tmp/one /tmp/two\ncp /tmp/two /tmp/three\n")
        self.assertNotIn("/tmp/three", stored)

    def test_a_copy_option_this_checker_cannot_read_leaves_it_unplaced(self) -> None:
        self.assertTrue(
            self.aliases("ln -s /tmp/one /tmp/two\ncp --reflink /tmp/two /tmp/three\n")[1]
        )

    def test_a_relocation_this_checker_cannot_read_leaves_it_unplaced(self) -> None:
        for body in (
            "ln -s /tmp/one /tmp/two\nmv -t /tmp/dir /tmp/two\n",
            "ln -s /tmp/one /tmp/two\nmv /tmp/two\n",
            'ln -s /tmp/one /tmp/two\nmv /tmp/two "$(printf %s /tmp/three)"\n',
        ):
            with self.subTest(body=body):
                self.assertTrue(self.aliases(body)[1])

    def test_a_relocation_of_an_untracked_path_carries_nothing(self) -> None:
        self.assertEqual(
            self.placed("ln -s /tmp/one /tmp/two\nmv /other/four /other/five\n"),
            frozenset({"/tmp/two", "/tmp/two/one"}),
        )

    def test_a_chain_of_relocations_is_followed(self) -> None:
        carried = self.placed(
            "ln -s /tmp/one /tmp/two\n"
            "mv /tmp/two /tmp/three\n"
            "mv /tmp/three /tmp/four\n"
        )
        self.assertIn("/tmp/four", carried)

    def test_an_alias_this_checker_cannot_anchor_holds_every_path(self) -> None:
        """An unanchored alias names a directory no written text decides."""

        source = '#!/bin/sh\nset -eu\nln -s /tmp/one "$outside/two"\n'
        links, _ = self.module._symlinked_paths(self.fixture(source))
        self.assertTrue(links, "an unanchored alias is still collected")
        self.assertTrue(
            self.module._may_be_linked(links, frozenset({(True, ("other", "place"))})),
            "an unanchored alias may name any destination",
        )

    def test_a_path_a_link_holds_may_be_named_by_it(self) -> None:
        link = (True, ("tmp", "two"))
        self.assertTrue(self.module._may_be_ancestor(link, (True, ("tmp", "two", "x"))))
        self.assertFalse(self.module._may_be_ancestor(link, (True, ("tmp",))))
        self.assertFalse(self.module._may_be_ancestor(link, (True, ("tmp", "three"))))
        self.assertTrue(self.module._may_be_ancestor(link, link))

    def test_a_segment_written_with_an_expansion_never_holds_a_path(self) -> None:
        self.assertFalse(
            self.module._holds_path((True, ("$a",)), (True, ("$a", "x")))
        )

    def test_the_committed_fixture_places_every_alias_it_writes(self) -> None:
        source = Path("tests/copier-update.sh").read_text(encoding="utf-8")
        links, unplaced = self.module._symlinked_paths(self.fixture(source))
        self.assertFalse(unplaced, "the committed fixture writes only modelled aliases")
        self.assertTrue(links, "the committed fixture writes a symbolic link")


class AlternatePathDestinationTest(ContractSupportTest):
    """Cover the destination the alternate-path prohibition is bounded to."""

    OTHER = "$tmp/other-project"
    module = copier_fixture_validator

    def fixture(self, source: str):
        records = self.module.shell_lexical.project(source)
        table = self.module.shell_functions.derive(records)
        graph = self.module.shell_execution.derive(records, table)
        return self.module._Fixture(source, records, table, graph)

    def assert_second_path_rejected(self, inserted: str) -> None:
        self.assert_rejected(
            COMPLIANT + inserted, RULE_ALTERNATE_PATH, "second Copier update path"
        )

    def test_a_renamed_wrapper_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            '"$project/.project-agent-workflow/scripts/run-copier-update.sh" --force\n'
        )

    def test_an_alias_directory_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'alias_dir="$project/.project-agent-workflow/scripts"\n'
            '"$alias_dir/update-from-copier.sh" --defaults\n'
        )

    def test_the_same_destination_written_differently_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$tmp/project"\n'
        )
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$project/"\n'
        )

    def test_an_unproven_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$elsewhere"\n'
        )
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$tmp/$lane"\n'
        )

    def test_an_update_without_a_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected("run_copier update -q --defaults\n")

    def test_a_relative_wrapper_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            '(cd "$project" && .project-agent-workflow/scripts/update-from-copier.sh)\n'
        )

    def test_an_update_inside_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$project/nested"\n'
        )

    def test_an_update_of_the_enclosing_directory_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$tmp"\n'
        )

    def test_an_update_behind_an_unknown_option_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update --unknown-option value "$tmp/other-project"\n'
        )

    def test_an_expanded_subcommand_reaching_the_same_project_is_rejected(
        self,
    ) -> None:
        self.assert_second_path_rejected(
            'verb=update\nrun_copier "$verb" -q --defaults "$project"\n'
        )

    def test_the_same_destination_spelled_with_segments_is_rejected(self) -> None:
        for written in (
            "$tmp/./project",
            "$tmp//project",
            "$tmp/other/../project",
            "$project/.",
        ):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'run_copier update -q --defaults "{written}"\n'
                )

    def test_a_destination_above_an_expansion_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults "$tmp/../elsewhere"\n'
        )

    def test_an_assignment_in_front_of_the_command_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" run_copier update -q --defaults "$dest"\n'
        )

    def test_an_assignment_carried_across_a_continuation_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" \\\n'
            '  run_copier update -q --defaults "$dest"\n'
        )

    def test_an_assignment_in_front_of_another_command_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" /bin/true\n'
            'run_copier update -q --defaults "$dest"\n'
        )

    def test_an_unmodelled_destination_word_is_rejected(self) -> None:
        for written in ("$tmp/pro\\ject", "//$tmp/project", "$tmp/proj*"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f"run_copier update -q --defaults {written}\n"
                )

    def test_a_linked_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'ln -s "$project" "$tmp/project-alias"\n'
            'run_copier update -q --defaults "$tmp/project-alias"\n'
        )

    def test_a_link_that_may_hold_the_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'ln -s "$tmp/elsewhere" "$tmp"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_a_copied_link_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'cp -s "$project" "$tmp/project-copy-alias"\n'
            'run_copier update -q --defaults "$tmp/project-copy-alias"\n'
        )

    def test_a_link_written_inside_a_destination_is_rejected(self) -> None:
        """An update walks into the directory it changes, so a link under it redirects the walk."""

        self.assert_second_path_rejected(
            'ln -s "$tmp/elsewhere" "$tmp/other-project/note"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )
        self.assert_second_path_rejected(
            'ln -s "$tmp/elsewhere" "$project/note"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_a_link_that_redirects_an_installed_workflow_is_rejected(self) -> None:
        """The boundary segment the destination is derived from may itself be an alias."""

        self.assert_second_path_rejected(
            'other="$tmp/other"\n'
            'ln -s "$project/.project-agent-workflow" '
            '"$other/.project-agent-workflow"\n'
            '"$other/.project-agent-workflow/scripts/update-from-copier.sh" '
            "--defaults\n"
        )

    def test_an_escaped_quote_in_an_option_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update --exclude "key=value\\" $tmp/other-project '
            '--vcs-ref " "$project"\n'
        )

    def test_an_assignment_behind_a_redirection_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" 3>&1 run_copier update -q --defaults "$dest"\n'
        )

    def test_a_link_command_written_as_a_path_is_rejected(self) -> None:
        for written in ('/usr/bin/ln -s', 'env ln -s'):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/other-project"\n'
                    'run_copier update -q --defaults "$tmp/other-project"\n'
                )

    def test_an_escaped_separator_is_not_a_separator(self) -> None:
        for written in (">\\&", ">\\;", ">\\|"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    'dest="$project"\n'
                    f'dest="$tmp/other-project" {written} '
                    'run_copier update -q --defaults "$dest"\n'
                )

    def test_a_separator_still_ends_a_prefix_assignment(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'dest="$tmp/other-project" && '
            + 'run_copier update -q --defaults "$dest"\n'
        )

    def test_an_assignment_that_runs_in_its_own_shell_proves_no_destination(
        self,
    ) -> None:
        """A backgrounded assignment gives the writing shell no value."""

        self.assert_second_path_rejected(
            'dest="$tmp/other-project" & '
            'run_copier update -q --defaults "$dest"\n'
        )

    def test_a_quoted_link_command_is_rejected(self) -> None:
        for written in ("l''n -s", 'l""n -s', "nice -n 1 ln -s"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/other-project"\n'
                    'run_copier update -q --defaults "$tmp/other-project"\n'
                )

    def test_a_continued_link_command_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'l\\\nn -s "$project" "$tmp/other-project"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_an_unread_link_command_is_rejected(self) -> None:
        for written in (
            "${link_command:-ln} -s",
            "$(printf %s ln) -s",
            '"$linker" --symbolic',
        ):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/other-project"\n'
                    'run_copier update -q --defaults "$tmp/other-project"\n'
                )

    def test_an_unread_command_is_not_read_as_a_link(self) -> None:
        """The run carries no alias, and its bare operands settle no name."""

        source = (
            COMPLIANT
            + '"$reporter" --defaults "$project" "$tmp/other-project"\n'
            + 'run_copier update -q --defaults "$tmp/other-project"\n'
        )
        links, unplaced = self.module._symlinked_paths(self.fixture(source))
        self.assertEqual(links, frozenset())
        self.assertFalse(unplaced)
        self.assert_second_path_rejected(
            '"$reporter" --defaults "$project" "$tmp/other-project"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_a_launched_link_command_is_rejected(self) -> None:
        for written in (
            "command ${link_command:-ln} -s",
            "env $(printf %s ln) -s",
            "command ln -s",
        ):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/project-alias"\n'
                    '"$tmp/project-alias/.project-agent-workflow/scripts'
                    '/update-from-copier.sh" --defaults\n'
                )

    def test_a_launched_ordinary_command_is_not_a_link(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'git -C "$project" commit -s -m note\n'
            + 'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_an_update_of_another_project_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'run_copier update -q --defaults --vcs-ref v1.4.5 "{self.OTHER}"\n'
        )

    def test_a_relative_wrapper_is_placed_by_its_subshell_directory(self) -> None:
        """The subshell writes the directory, so the wrapper reaches it."""

        self.assert_accepted(
            COMPLIANT
            + f'(cd "{self.OTHER}" && '
            ".project-agent-workflow/scripts/update-from-copier.sh)\n"
        )

    def test_a_relative_wrapper_reaching_the_child_is_rejected(self) -> None:
        """A settled subshell directory places the wrapper on the child."""

        self.assert_second_path_rejected(
            '(cd "$project" && '
            ".project-agent-workflow/scripts/update-from-copier.sh)\n"
        )

    def test_a_wrapper_held_in_a_name_is_rejected(self) -> None:
        """The command word writes no marker, so the settled path is read."""

        self.assert_second_path_rejected(
            'wrapper="$project/.project-agent-workflow/scripts'
            '/update-from-copier.sh"\n'
            '"$wrapper" --defaults\n'
        )

    def test_a_helper_that_updates_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            "run_copier() {\n  copier update -q \"$project\"\n}\n"
            'run_copier update -q "$tmp/other-project"\n'
        )

    def test_an_attached_option_value_keeps_the_destination_read(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update --vcs-ref=v1.4.5 "$project"\n'
        )
        self.assert_accepted(
            COMPLIANT
            + f'run_copier update --vcs-ref=v1.4.5 "{self.OTHER}"\n'
        )

    def test_an_option_terminator_keeps_the_destination_read(self) -> None:
        self.assert_second_path_rejected('run_copier update -q -- "$project"\n')
        self.assert_accepted(
            COMPLIANT + f'run_copier update -q -- "{self.OTHER}"\n'
        )

    def test_an_option_cluster_this_checker_does_not_read_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'run_copier update -qf "{self.OTHER}"\n'
        )

    def test_an_option_held_in_a_name_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'flag=-q\nrun_copier update "$flag" "{self.OTHER}"\n'
        )

    def test_a_destination_a_branch_may_change_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            f'if [ -d /tmp ]; then dest="{self.OTHER}"; fi\n'
            'run_copier update -q "$dest"\n'
        )

    def test_a_destination_a_loop_binds_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'for dest in "$project" "{self.OTHER}"; do\n'
            '  run_copier update -q "$dest"\n'
            "done\n"
        )

    def test_an_alias_above_another_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'ln -s "$project" "$tmp"\nrun_copier update -q "{self.OTHER}"\n'
        )

    def test_an_alias_naming_another_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'ln -s "$project" "{self.OTHER}"\n'
            f'run_copier update -q "{self.OTHER}"\n'
        )

    def test_an_alias_moved_onto_another_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'ln -s "$project" "$tmp/a"\nmv "$tmp/a" "{self.OTHER}"\n'
            f'run_copier update -q "{self.OTHER}"\n'
        )

    def test_a_wrapper_run_through_a_launcher_is_rejected(self) -> None:
        for written in ("sh", "env"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project/.project-agent-workflow/scripts'
                    '/update-from-copier.sh" --defaults\n'
                )

    def test_the_committed_runtime_keeps_passing_the_check(self) -> None:
        """Plan 227 completed the transition this rule is reached through."""

        source = (ROOT / "tests" / "copier-update.sh").read_text(encoding="utf-8")
        self.assertEqual(check(source), ())
        self.assertTrue(self.module._is_transition(self.fixture(source)))

    def test_a_copy_naming_an_update_source_is_not_an_update(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'update_source="$tmp/source"\n'
            f'run_copier copy -q --vcs-ref v1.4.5 "$update_source" "{self.OTHER}"\n'
        )


class CopierWriteTest(ContractSupportTest):
    """Cover the Copier writes that replace the destination the child updates.

    A copy and a recopy are not updates, so the alternate-path prohibition never
    reads them. They still write a whole project, so a write proven to reach the
    sanctioned destination is rejected everywhere except the one creation the
    fixture must perform before it starts the update child.
    """

    OTHER = "$tmp/other-project"
    MESSAGE = "unmodelled Copier copy path"
    CHILD = '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'

    def assert_write_rejected(self, source: str) -> None:
        self.assert_rejected(source, RULE_ALTERNATE_PATH, self.MESSAGE)

    def before_the_child(self, inserted: str) -> str:
        return self.mutate(self.CHILD, inserted + self.CHILD)

    def test_a_copy_into_the_sanctioned_destination_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT
            + 'run_copier copy -q -f --vcs-ref v1.4.5 "$update_source" "$project"\n'
        )

    def test_a_recopy_of_the_sanctioned_destination_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'run_copier recopy -q -f --vcs-ref v1.4.5 "$project"\n'
        )

    def test_a_copy_written_differently_is_rejected(self) -> None:
        for written in ("$tmp/project", "$project/", "$tmp/./project", "$project/."):
            with self.subTest(written=written):
                self.assert_write_rejected(
                    COMPLIANT
                    + f'run_copier copy -q -f "$update_source" "{written}"\n'
                )

    def test_a_copy_inside_the_sanctioned_destination_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$project/nested"\n'
        )

    def test_a_copy_of_the_enclosing_directory_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$tmp"\n'
        )

    def test_a_copy_behind_a_launcher_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'env run_copier copy -q -f "$update_source" "$project"\n'
        )

    def test_a_copy_into_a_separate_project_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'run_copier copy -q -f "$update_source" "{self.OTHER}"\n'
            + f'run_copier recopy -q -f "{self.OTHER}"\n'
        )

    def test_a_destination_that_does_not_settle_is_accepted(self) -> None:
        """The committed fixture copies into a lane path no written text settles."""

        self.assert_accepted(
            COMPLIANT
            + 'for out in "$tmp/a" "$project"; do\n'
            '  run_copier copy -q -f "$update_source" "$out"\n'
            "done\n"
        )

    def test_a_destination_one_call_site_settles_is_read(self) -> None:
        """A parameter carries the destination its call site writes.

        The copy is reported because the call site names the sanctioned
        destination, which the body reaches through its first parameter.
        """

        self.assert_rejected(
            COMPLIANT
            + "write_lane() {\n"
            '  run_copier copy -q -f "$update_source" "$1"\n'
            "}\n"
            'write_lane "$project"\n',
            RULE_ALTERNATE_PATH,
            "an unmodelled Copier copy path writes the sanctioned destination",
        )

    def test_an_expansion_where_the_paths_differ_is_rejected(self) -> None:
        """An expansion written there may still name the sanctioned project."""

        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$tmp/$lane"\n'
        )

    def test_an_unsettled_segment_under_the_destination_is_rejected(self) -> None:
        """The written prefix already places the copy inside the sanctioned project."""

        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$project/$lane"\n'
        )

    def test_a_destination_no_written_text_anchors_is_rejected(self) -> None:
        """An unanchored path is placed by the working directory, not by the text."""

        for written in ('"$elsewhere"', '"$lane/project"', "project"):
            with self.subTest(written=written):
                self.assert_write_rejected(
                    COMPLIANT + f'run_copier copy -q -f "$update_source" {written}\n'
                )

    def test_a_child_destination_the_checker_cannot_read_reserves_every_copy(
        self,
    ) -> None:
        """An unread child destination must not switch the whole rule off."""

        unread = self.mutate(
            "$project/.project-agent-workflow",
            "$candidate_path/.project-agent-workflow",
        )
        self.assert_write_rejected(
            unread + f'run_copier copy -q -f "$update_source" "{self.OTHER}"\n'
        )

    def test_an_unread_option_leaves_the_destination_unread(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'run_copier copy --unknown-option value "$update_source" "$project"\n'
        )

    def test_an_unread_operand_count_leaves_the_destination_unread(self) -> None:
        self.assert_accepted(COMPLIANT + 'run_copier copy -q -f "$project"\n')
        self.assert_accepted(
            COMPLIANT + 'run_copier recopy -q -f "$update_source" "$project"\n'
        )

    def test_an_unread_subcommand_is_not_a_copy(self) -> None:
        self.assert_accepted(
            COMPLIANT + 'run_copier clone -q -f "$update_source" "$project"\n'
        )

    def test_the_modelled_creation_before_the_child_is_accepted(self) -> None:
        self.assert_accepted(
            self.before_the_child(
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
            )
        )

    def test_a_second_creation_before_the_child_is_rejected(self) -> None:
        self.assert_write_rejected(
            self.before_the_child(
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
            )
        )

    def test_a_creation_before_the_child_keeps_a_later_copy_rejected(self) -> None:
        self.assert_write_rejected(
            self.before_the_child(
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
            )
            + 'run_copier recopy -q -f "$project"\n'
        )

    def test_a_fixture_without_a_transition_reads_no_copy(self) -> None:
        self.assert_accepted(
            WITHOUT_TRANSITION
            + 'run_copier copy -q -f "$update_source" "$project"\n'
        )

    def test_a_copy_in_a_body_written_before_the_child_is_rejected(self) -> None:
        self.assert_write_rejected(
            self.before_the_child(
                "recreate() {\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "}\n"
            )
            + "recreate\n"
        )

    def test_an_uncalled_body_written_before_the_child_is_accepted(self) -> None:
        self.assert_accepted(
            self.before_the_child(
                "recreate() {\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "}\n"
            )
        )

    def test_a_copy_in_a_loop_that_reaches_the_child_is_rejected(self) -> None:
        self.assert_write_rejected(
            self.mutate(
                self.CHILD,
                "for attempt in one two; do\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "  " + self.CHILD,
            )
            + "done\n"
        )

    def test_a_copy_in_a_region_that_ends_before_the_child_is_accepted(self) -> None:
        self.assert_accepted(
            self.before_the_child(
                "if [ -d /tmp ]; then\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "fi\n"
            )
        )


class ResolutionAuthorityTest(ContractSupportTest):
    """Cover the resolution model as the single authority on what runs an update."""

    WRAPPER = "$other/.project-agent-workflow/scripts/update-from-copier.sh"

    def assert_second_path_rejected(self, inserted: str) -> None:
        self.assert_rejected(
            COMPLIANT + 'other="$tmp/other"\n' + inserted,
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_a_wrapper_inside_an_interpreter_string_is_rejected(self) -> None:
        """The words of the run say nothing about what the string runs."""

        self.assert_second_path_rejected(
            "sh -c '\"$1/.project-agent-workflow/scripts/update-from-copier.sh\" "
            '--defaults\' _ "$other"\n'
        )

    def test_a_wrapper_behind_a_command_prefix_is_rejected(self) -> None:
        """A prefix that is no launcher still runs the word written after it."""

        self.assert_second_path_rejected('nice "%s" --defaults\n' % self.WRAPPER)

    def test_a_wrapper_a_helper_forwards_is_rejected(self) -> None:
        """A helper that runs one of its own arguments runs what the call site writes."""

        self.assert_second_path_rejected(
            "runit() {\n"
            '  "$1" --defaults\n'
            "}\n"
            'runit "%s"\n' % self.WRAPPER
        )

    def test_a_wrapper_a_helper_interprets_is_rejected(self) -> None:
        """A helper that runs an interpreter on its arguments runs the written script."""

        self.assert_second_path_rejected(
            "runsh() {\n  sh \"$1\"\n}\n" 'runsh "%s"\n' % self.WRAPPER
        )

    def test_an_update_carried_by_an_expansion_is_rejected(self) -> None:
        """A command word this checker never reads still carries the subcommand."""

        self.assert_second_path_rejected(
            "tool=copier\n" '"$tool" update -q --defaults "$other"\n'
        )

    def test_a_copy_whose_operands_write_the_update_word_is_accepted(self) -> None:
        """A copy is proved to be no update, so the words its operands write are read only as paths."""

        self.assert_accepted(
            COMPLIANT
            + 'src="$tmp/update-source"\n'
            'out="$tmp/other-update"\n'
            'run_copier copy -q -f --vcs-ref v1.2.1 "$src" "$out"\n'
        )

    def test_an_update_of_a_separate_project_stays_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'out="$tmp/other"\n'
            'run_copier update -q --defaults "$out"\n'
        )

    def test_a_non_update_script_of_an_installed_workflow_is_accepted(self) -> None:
        """A script of an installed workflow runs an update only when its name says so."""

        self.assert_accepted(
            COMPLIANT
            + 'other="$tmp/other"\n'
            '"$other/.project-agent-workflow/scripts/context-compress.sh" doc tag\n'
        )
        self.assert_accepted(
            COMPLIANT + ".project-agent-workflow/scripts/context-compress.sh doc tag\n"
        )

    def test_an_update_script_of_an_installed_workflow_is_still_read(self) -> None:
        """A name that writes both marks keeps its unanchored destination unproven."""

        self.assert_second_path_rejected(
            ".project-agent-workflow/scripts/run-copier-update.sh --force\n"
        )

    def test_a_script_name_written_by_an_expansion_is_unproven(self) -> None:
        """A name this checker cannot read may be the update wrapper itself."""

        self.assert_second_path_rejected(
            ".project-agent-workflow/scripts/$script --defaults\n"
        )

    def test_a_read_script_name_keeps_its_destination_read(self) -> None:
        """Reading the name settles what runs, not which project it runs against."""

        self.assert_accepted(
            COMPLIANT
            + 'other="$tmp/other"\n'
            "script=update-from-copier.sh\n"
            '"$other/.project-agent-workflow/scripts/$script" --defaults\n'
        )
        self.assert_rejected(
            COMPLIANT
            + "script=update-from-copier.sh\n"
            '"$project/.project-agent-workflow/scripts/$script" --defaults\n',
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )


class SubshellDirectoryTest(ContractSupportTest):
    """Cover the directory a subshell settles for a relative command word."""

    OTHER = "$tmp/other-project"
    WRAPPER = ".project-agent-workflow/scripts/update-from-copier.sh"

    def assert_second_path_rejected(self, inserted: str) -> None:
        self.assert_rejected(
            COMPLIANT + inserted, RULE_ALTERNATE_PATH, "second Copier update path"
        )

    def test_a_settled_subshell_directory_places_the_wrapper(self) -> None:
        """One directory change written before the word settles the project."""

        self.assert_accepted(
            COMPLIANT + f'(cd "{self.OTHER}" && {self.WRAPPER} --defaults)\n'
        )

    def test_a_settled_subshell_directory_reaching_the_child_is_rejected(
        self,
    ) -> None:
        """The settled directory is the sanctioned child, so the word reaches it."""

        self.assert_second_path_rejected(
            f'(cd "$project" && {self.WRAPPER} --defaults)\n'
        )

    def test_a_wrapper_with_no_subshell_stays_unplaced(self) -> None:
        """Nothing written says which directory the word runs in."""

        self.assert_second_path_rejected(f"{self.WRAPPER} --defaults\n")

    def test_two_directory_changes_leave_the_wrapper_unplaced(self) -> None:
        """A second change leaves no single directory the word runs in."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && cd "$tmp" && {self.WRAPPER} --defaults)\n'
        )

    def test_an_unsettled_directory_leaves_the_wrapper_unplaced(self) -> None:
        """A directory this checker cannot place proves no destination."""

        self.assert_second_path_rejected(
            f'(cd "$tmp/$lane" && {self.WRAPPER} --defaults)\n'
        )

    def test_a_relative_directory_leaves_the_wrapper_unplaced(self) -> None:
        """A directory that is not anchored is placed by nothing written."""

        self.assert_second_path_rejected(
            f'(cd other-project && {self.WRAPPER} --defaults)\n'
        )

    def test_a_directory_change_outside_the_subshell_is_unread(self) -> None:
        """A change written outside the subshell settles no directory inside it."""

        self.assert_second_path_rejected(
            f'cd "{self.OTHER}"\n(: && {self.WRAPPER} --defaults)\n'
        )

    def test_a_directory_change_written_after_the_word_is_unread(self) -> None:
        """A change the word never runs under settles no directory for it."""

        self.assert_second_path_rejected(
            f'({self.WRAPPER} --defaults && cd "{self.OTHER}")\n'
        )

    def test_a_directory_change_in_another_branch_is_unread(self) -> None:
        """A change on a separate enclosure path never runs before the word."""

        self.assert_second_path_rejected(
            f'(if [ -d "{self.OTHER}" ]; then cd "{self.OTHER}"; fi\n'
            f"{self.WRAPPER} --defaults)\n"
        )

    def test_a_change_carried_by_a_called_function_leaves_it_unplaced(
        self,
    ) -> None:
        """A called function moves the same directory the word runs in."""

        self.assert_second_path_rejected(
            "goto() {\n  cd \"$1\"\n}\n"
            f'(cd "{self.OTHER}" && goto "$project" && {self.WRAPPER} --force)\n'
        )

    def test_any_other_operation_before_the_word_leaves_it_unplaced(
        self,
    ) -> None:
        """Only a subshell that runs the change alone writes its directory."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && : && {self.WRAPPER} --defaults)\n'
        )

    def test_a_sourced_file_before_the_word_leaves_it_unplaced(self) -> None:
        """A sourced file runs in the same shell and may move the directory."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && . "$tmp/lib.sh" && {self.WRAPPER})\n'
        )

    def test_a_change_written_after_the_word_leaves_it_unplaced(self) -> None:
        """A later change still runs before the word on a second turn."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && {self.WRAPPER} && cd "$project")\n'
        )

    def test_a_change_carried_by_a_loop_leaves_the_word_unplaced(self) -> None:
        """The second turn of the loop runs the word in the changed directory."""

        self.assert_second_path_rejected(
            f'o="{self.OTHER}"\n(cd "$o"\n'
            f'for i in 1 2; do {self.WRAPPER} --force; cd "$project"; done)\n'
        )

    def test_a_repeated_word_leaves_it_unplaced(self) -> None:
        """A word one loop may run again is placed by no single directory."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}"\nfor i in 1 2; do {self.WRAPPER} --force; done)\n'
        )

    def test_a_word_repeated_by_a_loop_condition_is_unplaced(self) -> None:
        """A loop condition runs again under the directory the body left."""

        self.assert_second_path_rejected(
            f'o="{self.OTHER}"\n'
            f'while (cd "$o" && {self.WRAPPER} --force); do o="$project"; done\n'
        )

    def test_a_branch_condition_still_places_the_word(self) -> None:
        """A branch condition runs once, so its subshell settles a directory."""

        self.assert_accepted(
            COMPLIANT
            + f'if (cd "{self.OTHER}" && {self.WRAPPER} --force); then :; fi\n'
        )


class SnapshotIndirectionTest(ContractSupportTest):
    SNAPSHOT = "$project/scripts/snapshot-validation-witness-provenance.py"

    def test_naming_the_snapshot_script_is_not_invoking_it(self) -> None:
        for named in (
            f'test -f "{self.SNAPSHOT}"\n',
            'expected="snapshot-validation-witness-provenance"\n'
            'grep -q "$expected" "$project/manifest.txt"\n',
            'note="snapshot-validation-witness-provenance is managed"\necho "$note" >&2\n',
        ):
            with self.subTest(named=named.splitlines()[-1]):
                self.assert_accepted(COMPLIANT + named)

    def test_running_the_snapshot_script_as_the_command_word_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + f'"{self.SNAPSHOT}" --stage before\n',
            RULE_DIRECT_INVOCATION,
            "invokes the migration snapshot script directly",
        )

    def test_direct_snapshot_invocation_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + f'python3 "{self.SNAPSHOT}" --stage before\n',
            RULE_DIRECT_INVOCATION,
            "invokes the migration snapshot script directly",
        )

    def test_snapshot_invocation_through_a_variable_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + f'snapshot="{self.SNAPSHOT}"\npython3 "$snapshot" --stage before\n',
            RULE_DIRECT_INVOCATION,
            "invokes the migration snapshot script directly",
        )

    def test_interpreter_reached_through_a_helper_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT
            + "run_stage() {\n  python3 \"$1\" --stage \"$2\"\n}\n"
            + f'run_stage "{self.SNAPSHOT}" before\n',
            RULE_DIRECT_INVOCATION,
            "invokes the migration snapshot script directly",
        )

    def test_every_interpreter_spelling_is_rejected(self) -> None:
        for dispatch in (
            "timeout 30 python3",
            "/usr/bin/python3",
            "python3.11",
            "uv run",
        ):
            with self.subTest(dispatch=dispatch):
                self.assert_rejected(
                    COMPLIANT + f'{dispatch} "{self.SNAPSHOT}" --stage before\n',
                    RULE_DIRECT_INVOCATION,
                    "invokes the migration snapshot script directly",
                )

    def test_helper_running_an_unrelated_script_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + "run_stage() {\n  python3 \"$1\" --stage \"$2\"\n}\n"
            + 'run_stage "$project/report.py" before\n'
        )

    def test_a_reserved_word_written_as_an_argument_assigns_nothing(self) -> None:
        for carrier in (":", "echo"):
            for keyword in ("do", "then", "else", "{"):
                with self.subTest(carrier=carrier, keyword=keyword):
                    self.assert_rejected(
                        COMPLIANT
                        + f'snap="{self.SNAPSHOT}"\n'
                        + f"{carrier} {keyword} snap=/tmp/harmless\n"
                        + 'python3 "$snap" --stage before\n',
                        RULE_DIRECT_INVOCATION,
                        "invokes the migration snapshot script directly",
                    )

    def test_unrelated_variable_dispatch_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT + 'report="$project/scripts/report.py"\npython3 "$report" --quiet\n'
        )


class UnresolvedDispatchTest(ContractSupportTest):
    """An unresolved command word must not carry a Copier update."""

    def test_unresolved_copier_subcommand_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + 'copier_command=copier\n"$copier_command" update -q "$project"\n',
            RULE_UNRESOLVED_DISPATCH,
            "unresolved dispatch can run a Copier update",
        )

    def test_unresolved_dispatch_naming_copier_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '"$tmp/run-copier" --defaults "$project"\n',
            RULE_UNRESOLVED_DISPATCH,
            "unresolved dispatch can run a Copier update",
        )

    def test_unresolved_dispatch_of_the_update_wrapper_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT)
        self.assertIn(
            '"$project/.project-agent-workflow/scripts/update-from-copier.sh"', COMPLIANT
        )

    def test_unrelated_unresolved_dispatch_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT + '"$tmp/report-status" --quiet\n')

    def test_padding_past_the_expansion_bound_does_not_admit_a_dispatch(self) -> None:
        wrapper = "$out/.project-agent-workflow/scripts/update-from-copier.sh"
        for padding in (0, 2, 6, 12):
            with self.subTest(padding=padding):
                body = (
                    "cmd=copier\n"
                    f'if [ -n "$x" ]; then\n  cmd="{wrapper}"\nfi\n'
                )
                arguments = ""
                for turn in range(padding):
                    body += (
                        f"pad{turn}=one\n"
                        f'if [ -n "$y{turn}" ]; then pad{turn}=/tmp/v{turn}; fi\n'
                    )
                    arguments += f' "$pad{turn}"'
                body += f'"$cmd" update --defaults "$project"{arguments}\n'
                self.assert_rejected(
                    WITHOUT_TRANSITION + body,
                    RULE_UNRESOLVED_DISPATCH,
                    "unresolved dispatch can run a Copier update",
                )


class ShadowedAssignmentTest(ContractSupportTest):
    """A written override must not hide an operation that still runs."""

    SNAPSHOT = "$project/scripts/snapshot-validation-witness-provenance.py"
    WRAPPER = "$out/.project-agent-workflow/scripts/update-from-copier.sh"
    SHADOWS = (
        "if false; then {name}=/bin/true; fi\n",
        "false && {name}=/bin/true\n",
        "( {name}=/bin/true )\n",
        "true | {name}=/bin/true\n",
        "shadow_it() {{\n  {name}=/bin/true\n}}\n",
        'if [ -n "$override" ]; then\n  {name}="$override"\nfi\n',
        'if [ -n "$override" ]; then {name}="${name}"; fi\n',
        "for turn in 1 2; do\n  {name}=/bin/true\ndone\n",
    )

    def test_a_shadowed_snapshot_dispatch_is_rejected(self) -> None:
        for shadow in self.SHADOWS:
            with self.subTest(shadow=shadow.splitlines()[0]):
                self.assert_rejected(
                    COMPLIANT
                    + f'snap="{self.SNAPSHOT}"\n'
                    + shadow.format(name="snap")
                    + 'python3 "$snap" --stage before\n',
                    RULE_DIRECT_INVOCATION,
                    "invokes the migration snapshot script directly",
                )

    def test_a_shadowed_update_path_is_rejected(self) -> None:
        for shadow in self.SHADOWS:
            with self.subTest(shadow=shadow.splitlines()[0]):
                self.assert_rejected(
                    COMPLIANT
                    + f'alt="{self.WRAPPER}"\n'
                    + shadow.format(name="alt")
                    + '"$alt" --defaults --vcs-ref v1.4.4\n',
                    RULE_ALTERNATE_PATH,
                    "second Copier update path",
                )

    def test_an_override_written_where_it_certainly_runs_replaces_the_value(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'snap="{self.SNAPSHOT}"\nsnap=/bin/true\npython3 "$snap" --stage before\n'
        )

    def test_a_shadowed_name_that_is_only_named_stays_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'snap="{self.SNAPSHOT}"\n'
            + 'if false; then snap=/bin/true; fi\n'
            + 'test -f "$snap"\n'
        )

    def test_the_expansion_count_stays_bounded(self) -> None:
        names = {
            name: tuple(f"value-{name}{turn}" for turn in range(4))
            for name in ("a", "b", "c", "d")
        }
        bounded = copier_fixture_validator._expand_all("run $a $b $c $d", names)
        self.assertEqual(len(bounded.texts), 1)
        self.assertFalse(bounded.exact)
        for name, values in names.items():
            for value in values:
                self.assertIn(value, bounded.texts[0])
        product = copier_fixture_validator._expand_all(
            "run $a $b", {name: names[name] for name in ("a", "b")}
        )
        self.assertEqual(len(product.texts), 16)
        self.assertTrue(product.exact)


class OperationEvidenceTest(ContractSupportTest):
    """A required operation must be performed, not merely named."""

    def test_comment_naming_a_release_does_not_satisfy_the_release_path(self) -> None:
        self.assert_rejected(
            self.mutate(
                '\nrm -f "$release_file"\n\nrelease_waited=0',
                '\n: # release the before stage\n\nrelease_waited=0',
            ),
            RULE_RELEASE_PATH,
            "no unconditional before-stage release path",
        )

    def test_printing_the_release_path_does_not_release_it(self) -> None:
        self.assert_rejected(
            self.mutate(
                '\nrm -f "$release_file"\n\nrelease_waited=0',
                '\necho "$release_file"\n\nrelease_waited=0',
            ),
            RULE_RELEASE_PATH,
            "no unconditional before-stage release path",
        )

    def test_reading_the_release_path_does_not_release_it(self) -> None:
        self.assert_rejected(
            self.mutate(
                '\nrm -f "$release_file"\n\nrelease_waited=0',
                '\ncat "$release_file" >/dev/null\n\nrelease_waited=0',
            ),
            RULE_RELEASE_PATH,
            "no unconditional before-stage release path",
        )

    def test_release_written_through_a_redirection_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                '\nrm -f "$release_file"\n\nrelease_waited=0',
                '\n: >"$release_file"\n\nrelease_waited=0',
            )
        )


class WrittenFormTest(ContractSupportTest):
    """One operation stays recognized in every written form that performs it."""

    def test_single_line_guardian_cleanup_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                '  if [ "$guardian_pid" -gt 0 ]; then\n'
                '    kill -TERM "$guardian_pid" 2>/dev/null || true\n'
                "  fi\n",
                '  if [ "$guardian_pid" -gt 0 ]; then '
                'kill -TERM "$guardian_pid" 2>/dev/null || true; fi\n',
            )
        )

    def test_single_line_release_cleanup_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(
                '  rm -f "$release_file"\n  if [ "$guardian_pid"',
                '  if [ -e "$release_file" ]; then rm -f "$release_file"; fi\n'
                '  if [ "$guardian_pid"',
            )
        )

    def test_pid_cleared_with_an_empty_quoted_value_is_accepted(self) -> None:
        for cleared in ('update_pid=""', "update_pid=''"):
            with self.subTest(cleared=cleared):
                self.assert_accepted(
                    self.mutate("update_pid=\n\ngrep", f"{cleared}\n\ngrep")
                )

    def test_pid_left_set_after_the_reap_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate("update_pid=\n\ngrep", 'update_pid="0"\n\ngrep'),
            RULE_CHILD_REAP,
            "is not cleared after the reap",
        )


class OperationTargetTest(ContractSupportTest):
    """A termination, reap, or guardian check must name its own subject."""

    def test_termination_of_another_process_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'kill -TERM "$update_pid" 2>/dev/null || true\n',
                'kill -TERM "$guardian_pid" 2>/dev/null || true\n',
            ),
            RULE_CHILD_REAP,
            "never terminates the update child",
        )

    def test_forced_termination_of_another_process_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'kill -KILL "$update_pid" 2>/dev/null || true\n',
                'kill -KILL "$guardian_pid" 2>/dev/null || true\n',
            ),
            RULE_CHILD_REAP,
            "never forcibly terminated",
        )

    def test_waiting_for_another_process_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT.replace('wait "$update_pid"', 'wait "$guardian_pid"'),
            RULE_CHILD_REAP,
            "never waits for the update child",
        )

    def test_guardian_positivity_bound_to_another_pid_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT.replace('"$guardian_pid" -gt 0', '"$update_pid" -gt 0'),
            RULE_GUARDIAN,
            "never proves the guardian PID is positive",
        )

    def test_cleanup_that_stops_another_process_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '    kill -TERM "$guardian_pid" 2>/dev/null || true\n',
                '    kill -TERM "$update_pid" 2>/dev/null || true\n'
                '    echo "the guardian is detached" >&2\n',
            ),
            RULE_GUARDIAN,
            "never stops the detached guardian",
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
        self.assertNotIn(str(runtime), Path(__file__).read_text(encoding="utf-8"))
        for fixture in (COMPLIANT, WITHOUT_TRANSITION):
            self.assertTrue(fixture.startswith("#!/bin/sh"))
            self.assertNotIn("copier-update", fixture)


if __name__ == "__main__":
    unittest.main()
