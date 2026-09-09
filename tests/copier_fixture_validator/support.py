"""Shared fixtures, repository paths, and the inherited contract test base.

Every fixture used by the Copier fixture validator tests is written here. The
runtime candidate `tests/copier-update.sh` is never read as expected output and
is never executed, so the contract is proven against supplied bytes only.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

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
