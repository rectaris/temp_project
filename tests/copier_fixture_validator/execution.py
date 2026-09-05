"""Update child, poll, state, guardian, and dispatch behavior tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


if __spec__ is None or not __spec__.parent:  # allow direct execution of this module
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copier_fixture_validator.support import (
    COMPLIANT,
    ContractSupportTest,
    RULE_BOUNDED_POLL,
    RULE_CHILD_PID,
    RULE_CHILD_REAP,
    RULE_DIRECT_INVOCATION,
    RULE_GUARDIAN,
    RULE_RELEASE_PATH,
    RULE_STATE_ORDER,
    RULE_UNRESOLVED_DISPATCH,
    RULE_UPDATE_CHILD,
    VERSION_COMMITS,
    WITHOUT_TRANSITION,
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


if __name__ == "__main__":
    unittest.main()
