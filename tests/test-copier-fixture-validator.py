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
    RULE_ALTERNATE_PATH,
    RULE_BOUNDED_POLL,
    RULE_CHILD_PID,
    RULE_CHILD_REAP,
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
    main,
    validate,
)


VALIDATOR = ROOT / "scripts/project_workflow/copier_fixture_validator.py"

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
    def rules(self, source: str) -> list[str]:
        return [finding.rule for finding in check(source)]

    def messages(self, source: str) -> str:
        return "\n".join(str(finding) for finding in check(source))

    def assert_accepted(self, source: str) -> None:
        findings = check(source)
        self.assertEqual(findings, (), self.messages(source))

    def assert_rejected(self, source: str, rule: str, expected: str) -> None:
        findings = check(source)
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
        self.assertEqual(check(COMPLIANT.encode("utf-8")), ())

    def test_contract_is_deterministic(self) -> None:
        mutated = self.remove('fixture_git "$update_source" tag v1.4.5\n')
        self.assertEqual(check(mutated), check(mutated))

    def test_validate_raises_only_for_a_broken_contract(self) -> None:
        self.assertIsNone(validate(COMPLIANT))
        with self.assertRaises(CopierFixtureError) as raised:
            validate(self.remove('rm -f "$release_file"\n\nrelease_waited=0'))
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

    def test_a_name_a_loop_head_binds_is_never_settled(self) -> None:
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

    def test_a_relative_wrapper_is_rejected_wherever_it_is_written(self) -> None:
        """No written text says which directory a relative wrapper runs in."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && '
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
        """Plan 227 completes the transition this rule is reached through."""

        source = (ROOT / "tests" / "copier-update.sh").read_text(encoding="utf-8")
        self.assertEqual(check(source), ())
        self.assertFalse(self.module._is_transition(self.fixture(source)))

    def test_a_copy_naming_an_update_source_is_not_an_update(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'update_source="$tmp/source"\n'
            f'run_copier copy -q --vcs-ref v1.4.5 "$update_source" "{self.OTHER}"\n'
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
