#!/usr/bin/env python3
"""Behavior tests for the bounded shell execution graph."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from project_workflow import shell_execution  # noqa: E402
from project_workflow.shell_execution import (  # noqa: E402
    ASYNC,
    ASYNC_LIST,
    BREAK,
    CALL,
    CASE,
    CASE_ARM,
    CASE_MATCH,
    CASE_SKIP,
    COMMAND,
    CONDITION,
    CONDITION_TRUE,
    CONTINUE,
    EFFECT_EXEC,
    EFFECT_EXIT,
    EFFECT_RETURN,
    EFFECT_SOURCE,
    EFFECT_TRAP,
    ELSE_BRANCH,
    EXPANSION_REGION,
    ExecutionGraph,
    LOOP,
    LOOP_BODY,
    LOOP_ENTER,
    LOOP_EXIT,
    LOOP_REPEAT,
    MAX_CALL_DEPTH,
    MAX_DEPTH,
    ON_FAILURE,
    ON_SUCCESS,
    PIPELINE,
    REDIRECTION_SKIP,
    SUBSHELL,
    SUBSTITUTION_REGION,
    ShellExecutionError,
    TERMINATION_FAILURE,
    TERMINATION_SUCCESS,
    TERMINATION_UNKNOWN,
    THEN_BRANCH,
    derive,
)
from project_workflow.shell_functions import (  # noqa: E402
    ShellFunctionError,
    derive as derive_table,
)
from project_workflow.shell_lexical import project  # noqa: E402


class ExecutionGraphSupportTest(unittest.TestCase):
    def graph(self, source: str) -> ExecutionGraph:
        records = project(source)
        return derive(records, derive_table(records))

    def success(self, source: str) -> list[str | None]:
        return [node.name for node in self.graph(source).success_path]

    def reachable(self, source: str) -> list[str | None]:
        return [node.name for node in self.graph(source).reachable]

    def unreachable(self, source: str) -> list[str | None]:
        return [node.name for node in self.graph(source).unreachable]

    def node(self, graph: ExecutionGraph, name: str):
        matches = graph.find(name)
        self.assertEqual(len(matches), 1, f"expected one `{name}` node")
        return matches[0]

    def assert_rejected(self, source: str, expected: str) -> None:
        with self.assertRaises(ShellExecutionError) as raised:
            self.graph(source)
        self.assertIn(expected, str(raised.exception))


class ReachableGraphTest(ExecutionGraphSupportTest):
    def test_sequential_commands_form_the_permitted_success_path(self) -> None:
        graph = self.graph("first\nsecond\nthird\n")
        self.assertEqual([node.name for node in graph.success_path], ["first", "second", "third"])
        self.assertEqual(len(graph), 3)
        self.assertEqual([node.name for node in graph], ["first", "second", "third"])
        self.assertEqual(graph.unreachable, ())
        self.assertTrue(graph.is_fully_resolved)

    def test_every_control_transfer_is_an_explicit_edge(self) -> None:
        graph = self.graph("a && b\n")
        first = self.node(graph, "a")
        second = self.node(graph, "b")
        self.assertEqual(
            [edge.transfer for edge in graph.incoming(second)], [ON_SUCCESS]
        )
        self.assertIn(ON_FAILURE, [edge.transfer for edge in graph.outgoing(first)])
        self.assertEqual(graph.entry.kind, "entry")
        self.assertEqual(graph.end.kind, "end")
        self.assertEqual(graph.abort.kind, "abort")

    def test_reachable_nodes_other_than_the_entry_have_an_incoming_edge(self) -> None:
        source = (
            "helper() { helped; }\n"
            "start\n"
            "helper\n"
            "if guard; then taken; else other; fi\n"
            "while spin; do body; done\n"
            "case $x in (a) arm;; esac\n"
            "last\n"
        )
        graph = self.graph(source)
        for node in graph.nodes:
            if node.index == graph.entry_index:
                self.assertEqual(graph.incoming(node), ())
                continue
            if node.reachable:
                self.assertTrue(graph.incoming(node), f"{node.name} has no transfer")
            else:
                self.assertEqual(graph.incoming(node), ())

    def test_and_or_operands_are_conditionally_enclosed(self) -> None:
        graph = self.graph("a && b\nc || d\ne\n")
        self.assertEqual(
            [node.name for node in graph.success_path], ["a", "c", "e"]
        )
        for name in ("b", "d"):
            node = self.node(graph, name)
            self.assertTrue(node.reachable)
            self.assertFalse(node.guaranteed)
            self.assertTrue(node.is_conditional)

    def test_a_guard_that_terminates_with_failure_keeps_the_success_path(self) -> None:
        source = "check || { echo bad; exit 1; }\nrequired\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path], ["check", "required"]
        )
        self.assertEqual(self.node(graph, "exit").termination, TERMINATION_FAILURE)

    def test_a_conditional_success_exit_removes_the_later_guarantee(self) -> None:
        source = "if skip; then echo note; exit 0; fi\nrequired\n"
        graph = self.graph(source)
        self.assertEqual([node.name for node in graph.success_path], ["skip"])
        required = self.node(graph, "required")
        self.assertTrue(required.reachable)
        self.assertFalse(required.guaranteed)
        self.assertEqual(self.node(graph, "exit").termination, TERMINATION_SUCCESS)

    def test_pipeline_members_run_in_subshells_on_the_success_path(self) -> None:
        graph = self.graph("producer | filter | consumer\n")
        self.assertEqual(
            [node.name for node in graph.success_path],
            ["producer", "filter", "consumer"],
        )
        for name in ("producer", "filter", "consumer"):
            self.assertTrue(self.node(graph, name).in_subshell)
        self.assertEqual(
            [edge.transfer for edge in graph.incoming(self.node(graph, "filter"))],
            [PIPELINE],
        )

    def test_a_single_command_pipeline_stays_in_the_current_shell(self) -> None:
        graph = self.graph("! probe\nplain\n")
        self.assertFalse(self.node(graph, "probe").in_subshell)
        self.assertEqual([node.name for node in graph.success_path], ["probe", "plain"])

    def test_brace_group_stays_in_the_current_shell_and_subshell_does_not(self) -> None:
        graph = self.graph("{ grouped; }\n( isolated )\n")
        grouped = self.node(graph, "grouped")
        isolated = self.node(graph, "isolated")
        self.assertFalse(grouped.in_subshell)
        self.assertTrue(isolated.in_subshell)
        self.assertIn(SUBSHELL, isolated.enclosure_kinds)
        self.assertTrue(grouped.guaranteed)
        self.assertTrue(isolated.guaranteed)

    def test_assignments_and_redirections_do_not_hide_the_command_word(self) -> None:
        graph = self.graph('A=1 B=2 >out 2>&1 runner arg\n')
        node = self.node(graph, "runner")
        self.assertEqual(node.argument_values, ("arg",))
        self.assertTrue(node.reachable)
        self.assertTrue(node.may_fail_before_running)
        self.assertEqual([n.name for n in graph.commands], ["runner"])
        graph = self.graph("A=1 runner arg\n")
        self.assertTrue(self.node(graph, "runner").guaranteed)

    def test_an_assignment_only_command_has_no_dispatch(self) -> None:
        graph = self.graph("plain=1\nnext\n")
        self.assertEqual([node.name for node in graph.commands], [None, "next"])
        self.assertFalse(graph.commands[0].dynamic)

    def test_transparent_prefixes_resolve_the_dispatch_target(self) -> None:
        graph = self.graph(
            "command ls -l\nenv FOO=1 python3 script.py\nnohup runner\n"
        )
        self.assertEqual(
            [node.name for node in graph.success_path], ["ls", "python3", "runner"]
        )

    def test_a_declared_function_shadows_a_transparent_prefix(self) -> None:
        graph = self.graph("env() { inner; }\nenv FOO=1 python3\n")
        node = self.node(graph, "env")
        self.assertTrue(node.is_call)
        self.assertEqual(node.declaration.name, "env")
        self.assertEqual([n.name for n in graph.success_path], ["env", "inner"])

    def test_ordering_relations_follow_explicit_transfers(self) -> None:
        graph = self.graph("ready\nif x; then middle; fi\nrelease\n")
        ready = self.node(graph, "ready")
        middle = self.node(graph, "middle")
        release = self.node(graph, "release")
        self.assertTrue(graph.dominates(ready, release))
        self.assertTrue(graph.dominates(ready, middle))
        self.assertFalse(graph.dominates(release, ready))
        self.assertTrue(graph.postdominates(release, ready))
        self.assertFalse(graph.postdominates(middle, ready))
        self.assertTrue(graph.precedes(ready, release))
        self.assertFalse(graph.precedes(release, ready))
        self.assertFalse(graph.precedes(ready, ready))


class ControlTransferTest(ExecutionGraphSupportTest):
    def test_multi_command_conditions_run_on_the_success_path(self) -> None:
        source = "if setup; probe; then taken; else other; fi\nafter\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path], ["setup", "probe", "after"]
        )
        for name in ("setup", "probe"):
            self.assertIn(CONDITION, self.node(graph, name).enclosure_kinds)
        self.assertIn(THEN_BRANCH, self.node(graph, "taken").enclosure_kinds)
        self.assertIn(ELSE_BRANCH, self.node(graph, "other").enclosure_kinds)

    def test_branch_bodies_are_reached_only_through_their_condition(self) -> None:
        graph = self.graph("if guard; then taken; else other; fi\n")
        guard = self.node(graph, "guard")
        taken = self.node(graph, "taken")
        self.assertEqual(
            [edge.source for edge in graph.incoming(taken)], [guard.index]
        )
        self.assertEqual(
            [edge.transfer for edge in graph.incoming(taken)], [CONDITION_TRUE]
        )
        self.assertTrue(graph.dominates(guard, taken))
        self.assertFalse(taken.guaranteed)
        self.assertFalse(self.node(graph, "other").guaranteed)

    def test_elif_chains_keep_every_branch_conditional(self) -> None:
        source = "if a; then x; elif b; then y; else z; fi\nafter\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path], ["a", "after"]
        )
        self.assertTrue(graph.dominates(self.node(graph, "a"), self.node(graph, "b")))
        for name in ("x", "y", "z"):
            self.assertFalse(self.node(graph, name).guaranteed)
            self.assertTrue(self.node(graph, name).reachable)

    def test_loop_bodies_are_reachable_but_never_guaranteed(self) -> None:
        source = "while probe; do body; done\nfor item in a b; do repeated; done\nafter\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path], ["probe", "after"]
        )
        for name in ("body", "repeated"):
            node = self.node(graph, name)
            self.assertTrue(node.reachable)
            self.assertFalse(node.guaranteed)
            self.assertIn(LOOP_BODY, node.enclosure_kinds)

    def test_loop_transfers_model_entry_repetition_and_exit(self) -> None:
        graph = self.graph("while probe; do body; done\nafter\n")
        heads = [node for node in graph.nodes if node.kind == LOOP]
        self.assertEqual(len(heads), 1)
        head = heads[0]
        body = self.node(graph, "body")
        after = self.node(graph, "after")
        transfers = {edge.transfer for edge in graph.outgoing(self.node(graph, "probe"))}
        self.assertIn(LOOP_ENTER, transfers)
        self.assertIn(LOOP_EXIT, transfers)
        self.assertIn(
            LOOP_REPEAT, {edge.transfer for edge in graph.outgoing(body)}
        )
        self.assertIn(head.index, [edge.target for edge in graph.outgoing(body)])
        self.assertTrue(graph.dominates(head, after))
        self.assertTrue(after.guaranteed)
        self.assertFalse(graph.dominates(body, after))

    def test_a_short_circuit_still_selects_a_later_operand(self) -> None:
        # `first && second || third` is left associative, so a failure of
        # `first` must reach `third` instead of bypassing the whole list.
        graph = self.graph("first && second || third\nafter\n")
        third = self.node(graph, "third")
        sources = {
            graph.nodes[edge.source].name: edge.transfer
            for edge in graph.incoming(third)
        }
        self.assertEqual(sources, {"first": ON_FAILURE, "second": ON_FAILURE})
        after = self.node(graph, "after")
        self.assertEqual(
            {graph.nodes[edge.source].name for edge in graph.incoming(after)},
            {"second", "third"},
        )
        self.assertEqual([node.name for node in graph.success_path], ["first", "after"])

    def test_until_loops_use_the_same_bounded_transfers(self) -> None:
        graph = self.graph("until probe; do body; done\nafter\n")
        self.assertEqual([node.name for node in graph.success_path], ["probe", "after"])

    def test_case_arms_are_reached_only_by_a_match(self) -> None:
        source = 'case "$value" in (a) first;; b|c) second;; *) third;; esac\nafter\n'
        graph = self.graph(source)
        heads = [node for node in graph.nodes if node.kind == CASE]
        self.assertEqual(len(heads), 1)
        for name in ("first", "second", "third"):
            node = self.node(graph, name)
            self.assertTrue(node.reachable)
            self.assertFalse(node.guaranteed)
            self.assertIn(CASE_ARM, node.enclosure_kinds)
            self.assertEqual(
                [edge.transfer for edge in graph.incoming(node)], [CASE_MATCH]
            )
        self.assertIn(
            CASE_SKIP, {edge.transfer for edge in graph.outgoing(heads[0])}
        )
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_an_empty_case_arm_carries_the_path_forward(self) -> None:
        graph = self.graph('case "$#" in 0) ;; *) fail; exit 2 ;; esac\nafter\n')
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_break_removes_the_rest_of_the_loop_body(self) -> None:
        source = "while probe; do first; break; skipped; done\nafter\n"
        graph = self.graph(source)
        self.assertIn("skipped", self.unreachable(source))
        self.assertTrue(self.node(graph, "first").reachable)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_continue_removes_the_rest_of_the_loop_body(self) -> None:
        source = "while probe; do first; continue; skipped; done\nafter\n"
        graph = self.graph(source)
        self.assertIn("skipped", self.unreachable(source))
        head = [node for node in graph.nodes if node.kind == LOOP][0]
        self.assertIn(
            head.index,
            [edge.target for edge in graph.outgoing(self.node(graph, "continue"))],
        )

    def test_a_numbered_break_leaves_the_named_loop(self) -> None:
        source = (
            "while outer; do\n"
            "  while inner; do break 2; unreachable_inner; done\n"
            "  after_inner\n"
            "done\n"
            "after\n"
        )
        graph = self.graph(source)
        self.assertIn("unreachable_inner", self.unreachable(source))
        self.assertTrue(self.node(graph, "after_inner").reachable)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_return_ends_only_the_called_function_body(self) -> None:
        source = "f() {\n  if guard; then return; fi\n  tail\n}\nf\nafter\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path], ["f", "guard", "after"]
        )
        tail = self.node(graph, "tail")
        self.assertTrue(tail.reachable)
        self.assertFalse(tail.guaranteed)
        self.assertEqual(self.node(graph, "return").effect, EFFECT_RETURN)

    def test_an_unconditional_return_removes_the_rest_of_the_body(self) -> None:
        source = "f() { return; skipped; }\nf\nafter\n"
        graph = self.graph(source)
        self.assertIn("skipped", self.unreachable(source))
        self.assertTrue(self.node(graph, "after").guaranteed)


    def test_a_transfer_in_a_loop_condition_leaves_its_own_loop(self) -> None:
        # `break` in the condition of the inner loop exits that loop, so the
        # command after it still runs on every outer iteration.
        graph = self.graph(
            "while outer; do\n"
            "  while break; do body; done\n"
            "  after_inner\n"
            "done\n"
            "tail\n"
        )
        self.assertFalse(self.node(graph, "body").reachable)
        self.assertTrue(self.node(graph, "after_inner").reachable)
        self.assertTrue(self.node(graph, "tail").reachable)
        self.assertEqual(
            [
                (graph.nodes[edge.target].name, edge.transfer)
                for edge in graph.outgoing(self.node(graph, "break"))
            ],
            [("after_inner", BREAK)],
        )

    def test_a_continue_in_a_loop_condition_repeats_its_own_loop(self) -> None:
        # The condition is re-evaluated, so this loop never exits and nothing
        # after it can run. Both reference shells hang on this script.
        graph = self.graph("while continue; do body; done\ntail\n")
        self.assertFalse(self.node(graph, "body").reachable)
        self.assertFalse(self.node(graph, "tail").reachable)
        self.assertEqual(
            [
                (graph.nodes[edge.target].kind, edge.transfer)
                for edge in graph.outgoing(self.node(graph, "continue"))
            ],
            [(LOOP, CONTINUE)],
        )

    def test_a_called_body_does_not_transfer_into_a_caller_loop(self) -> None:
        # Both reference shells ignore a `break` that no loop in the called
        # body encloses, so the caller's loop must not absorb it.
        self.assert_rejected(
            "breaker() { break; }\nwhile breaker; do body; break; done\nafter\n",
            "not inside 1 enclosing loops in the current function",
        )
        self.assert_rejected(
            "jumper() { continue; }\nfor name in a; do jumper; done\n",
            "not inside 1 enclosing loops in the current function",
        )

    def test_a_loop_inside_a_called_body_still_bounds_its_transfer(self) -> None:
        graph = self.graph(
            "runner() { while probe; do inner; break; done; tail; }\n"
            "while outer; do runner; done\n"
            "after\n"
        )
        self.assertTrue(self.node(graph, "inner").reachable)
        self.assertTrue(self.node(graph, "tail").reachable)
        self.assertTrue(self.node(graph, "after").reachable)
        self.assert_rejected(
            "runner() { while probe; do break 2; done; }\n"
            "while outer; do runner; done\n",
            "not inside 2 enclosing loops in the current function",
        )

    def test_an_outermost_loop_condition_still_bounds_its_transfer(self) -> None:
        self.assert_rejected("while first; do body; done\nbreak\n", "not inside 1")


class TerminalEffectTest(ExecutionGraphSupportTest):
    def test_an_unbounded_or_non_ascii_status_is_not_a_modelled_literal(self) -> None:
        # `str.isdigit` accepts a superscript digit that `int` rejects, and a
        # very long digit run exceeds the interpreter conversion limit.
        for status in ("\u00b2", "1" * 5000):
            with self.subTest(status=status):
                graph = self.graph("exit %s\nafter\n" % status)
                self.assertEqual(
                    self.node(graph, "exit").termination, TERMINATION_UNKNOWN
                )
                self.assertFalse(self.node(graph, "after").reachable)
        # A padded literal still names an exact status once the padding is
        # removed, so it stays a modelled termination on both sides.
        padded = self.graph("exit %s\n" % ("0" * 5000))
        self.assertEqual(self.node(padded, "exit").termination, TERMINATION_SUCCESS)
        padded = self.graph("exit %s\n" % ("0" * 5000 + "1"))
        self.assertEqual(self.node(padded, "exit").termination, TERMINATION_FAILURE)
        for level in ("\u00b2", "1" * 5000):
            with self.subTest(level=level):
                self.assert_rejected(
                    "while first; do break %s; done\n" % level,
                    "exact bounded positive literal level",
                )

    def test_early_termination_makes_later_regions_unreachable(self) -> None:
        source = "before\nexit 0\nrequired\n"
        graph = self.graph(source)
        self.assertEqual([node.name for node in graph.success_path], ["before", "exit"])
        required = self.node(graph, "required")
        self.assertFalse(required.reachable)
        self.assertEqual(graph.incoming(required), ())
        self.assertEqual([node.name for node in graph.unreachable], ["required"])

    def test_terminal_function_calls_terminate_the_calling_script(self) -> None:
        source = "die() { echo fatal; exit 1; }\nbefore\ndie\nrequired\n"
        graph = self.graph(source)
        self.assertIn("required", self.unreachable(source))
        call = self.node(graph, "die")
        self.assertTrue(call.is_call)
        self.assertEqual([edge.transfer for edge in graph.outgoing(call)], [CALL])
        # The inlined body always terminates with failure, so the script has no
        # successful termination and therefore no permitted success path.
        self.assertFalse(graph.end.reachable)
        self.assertEqual(graph.success_path, ())

    def test_a_successful_terminal_call_ends_the_success_path(self) -> None:
        source = "finish() { echo done; exit 0; }\nbefore\nfinish\nrequired\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path],
            ["before", "finish", "echo", "exit"],
        )
        self.assertIn("required", self.unreachable(source))

    def test_a_conditional_terminal_call_keeps_the_later_region_reachable(self) -> None:
        source = "die() { exit 1; }\nprobe || die\nrequired\n"
        graph = self.graph(source)
        self.assertEqual(
            [node.name for node in graph.success_path], ["probe", "required"]
        )
        self.assertTrue(self.node(graph, "die").reachable)

    def test_exit_status_classification_is_explicit(self) -> None:
        graph = self.graph(
            "if a; then exit 0; fi\nif b; then exit 3; fi\nif c; then exit; fi\ntail\n"
        )
        statuses = [node.termination for node in graph.terminal_nodes]
        self.assertEqual(
            statuses,
            [TERMINATION_SUCCESS, TERMINATION_FAILURE, TERMINATION_UNKNOWN],
        )
        self.assertFalse(self.node(graph, "tail").guaranteed)

    def test_an_unresolved_exit_status_can_end_the_script_either_way(self) -> None:
        graph = self.graph('if a; then exit "$code"; fi\ntail\n')
        exit_node = self.node(graph, "exit")
        self.assertEqual(exit_node.termination, TERMINATION_UNKNOWN)
        targets = {edge.target for edge in graph.outgoing(exit_node)}
        self.assertEqual(targets, {graph.end_index, graph.abort_index})
        self.assertFalse(self.node(graph, "tail").guaranteed)

    def test_exec_replaces_the_shell_and_ends_the_graph(self) -> None:
        source = "before\nexec replacement arg\nrequired\n"
        graph = self.graph(source)
        node = self.node(graph, "replacement")
        self.assertEqual(node.effect, EFFECT_EXEC)
        self.assertEqual(node.termination, TERMINATION_UNKNOWN)
        self.assertIn("required", self.unreachable(source))

    def test_exec_with_redirections_only_does_not_terminate(self) -> None:
        graph = self.graph("exec >log 2>&1\nrequired\n")
        node = self.node(graph, "exec")
        self.assertIsNone(node.effect)
        self.assertTrue(self.node(graph, "required").guaranteed)

    def test_exit_inside_a_subshell_ends_only_that_subshell(self) -> None:
        source = "( inner; exit 1 )\nrequired\n"
        graph = self.graph(source)
        self.assertTrue(self.node(graph, "required").guaranteed)
        self.assertEqual(graph.unreachable, ())

    def test_exit_inside_a_pipeline_member_ends_only_that_member(self) -> None:
        graph = self.graph("first | exit 1\nrequired\n")
        self.assertTrue(self.node(graph, "required").guaranteed)

    def test_exit_inside_a_background_job_never_ends_the_script(self) -> None:
        graph = self.graph("worker && exit 1 &\nrequired\n")
        self.assertTrue(self.node(graph, "required").guaranteed)
        self.assertTrue(self.node(graph, "exit").asynchronous)


    def test_a_later_branch_condition_is_reported_as_conditional(self) -> None:
        graph = self.graph("if first; then x; elif second; then y; fi\n")
        self.assertFalse(self.node(graph, "first").is_conditional)
        self.assertTrue(self.node(graph, "first").guaranteed)
        self.assertTrue(self.node(graph, "second").is_conditional)
        self.assertFalse(self.node(graph, "second").guaranteed)


class HiddenRegionTest(ExecutionGraphSupportTest):
    def test_command_substitutions_are_modelled_as_executable_regions(self) -> None:
        graph = self.graph('value=$(hidden arg)\nafter\n')
        hidden = self.node(graph, "hidden")
        self.assertTrue(hidden.in_subshell)
        self.assertIn(SUBSTITUTION_REGION, hidden.enclosure_kinds)
        self.assertTrue(hidden.guaranteed)
        self.assertTrue(graph.precedes(hidden, self.node(graph, "after")))

    def test_nested_and_quoted_substitutions_are_reached(self) -> None:
        for source in (
            'value="$(outer $(inner))"\n',
            "value=${other:-$(inner)}\n",
            "value=$(( $(inner) ))\n",
            'runner "$(inner)"\n',
            "runner >\"$(inner)\"\n",
        ):
            with self.subTest(source=source):
                self.assertIn("inner", self.reachable(source))

    def test_here_document_substitutions_are_reached_when_unquoted(self) -> None:
        self.assertIn("inner", self.reachable("cat <<EOF\n$(inner)\nEOF\n"))
        self.assertIn("inner", self.reachable("cat <<-EOF\n\t$(inner)\nEOF\n"))
        self.assertNotIn("inner", self.reachable("cat <<'EOF'\n$(inner)\nEOF\n"))

    def test_a_substitution_terminating_does_not_terminate_the_script(self) -> None:
        graph = self.graph("value=$(inner; exit 1)\nrequired\n")
        self.assertTrue(self.node(graph, "required").guaranteed)

    def test_asynchronous_lists_leave_the_success_path(self) -> None:
        source = "guardian &\nrequired\n"
        graph = self.graph(source)
        guardian = self.node(graph, "guardian")
        self.assertTrue(guardian.reachable)
        self.assertFalse(guardian.guaranteed)
        self.assertTrue(guardian.asynchronous)
        self.assertTrue(guardian.in_subshell)
        self.assertIn(ASYNC_LIST, guardian.enclosure_kinds)
        self.assertEqual(
            [edge.transfer for edge in graph.incoming(guardian)], [ASYNC]
        )
        self.assertEqual([node.name for node in graph.success_path], ["required"])
        self.assertEqual(graph.asynchronous_nodes, (guardian,))

    def test_an_asynchronous_list_does_not_carry_the_sequential_path(self) -> None:
        graph = self.graph("first\nguardian &\nrequired\n")
        first = self.node(graph, "first")
        required = self.node(graph, "required")
        self.assertEqual([edge.source for edge in graph.incoming(required)], [first.index])
        self.assertEqual(
            [node.name for node in graph.success_path], ["first", "required"]
        )

    def test_dynamic_dispatch_is_reported_not_silently_trusted(self) -> None:
        graph = self.graph('"$root/run.sh" arg\n$command other\nliteral\n')
        self.assertEqual(len(graph.dynamic_commands), 2)
        self.assertEqual([node.name for node in graph.dynamic_commands], [None, None])
        self.assertFalse(self.node(graph, "literal").dynamic)
        self.assertFalse(graph.is_fully_resolved)
        self.assertTrue(self.graph("literal\n").is_fully_resolved)

    def test_included_files_and_traps_leave_the_graph_incomplete(self) -> None:
        graph = self.graph('. "$root/lib.sh"\ntrap cleanup EXIT\nrest\n')
        self.assertEqual(len(graph.included_sources), 1)
        self.assertEqual(graph.included_sources[0].effect, EFFECT_SOURCE)
        self.assertEqual(len(graph.trap_registrations), 1)
        self.assertEqual(graph.trap_registrations[0].effect, EFFECT_TRAP)
        self.assertFalse(graph.is_fully_resolved)
        self.assertTrue(self.node(graph, "rest").guaranteed)
        self.assertEqual(
            self.graph("source lib.sh\n").included_sources[0].effect, EFFECT_SOURCE
        )

    def test_an_uncalled_function_body_contributes_no_reachable_region(self) -> None:
        graph = self.graph("never() { orphan; }\nmain\n")
        self.assertEqual(graph.find("orphan"), ())
        self.assertEqual([node.name for node in graph.commands], ["main"])

    def test_one_function_called_twice_yields_two_bounded_regions(self) -> None:
        graph = self.graph("f() { inner; }\nf\nif guard; then f; fi\n")
        inner = graph.find("inner")
        self.assertEqual(len(inner), 2)
        self.assertTrue(inner[0].guaranteed)
        self.assertFalse(inner[1].guaranteed)
        self.assertEqual(inner[0].call_path, ("f",))

    def test_nested_calls_record_the_exact_call_path(self) -> None:
        graph = self.graph("a() { b; }\nb() { deep; }\na\n")
        deep = self.node(graph, "deep")
        self.assertEqual(deep.call_path, ("a", "b"))
        self.assertTrue(deep.guaranteed)


class ExpansionRegionTest(ExecutionGraphSupportTest):
    def test_a_conditional_expansion_word_is_not_guaranteed(self) -> None:
        graph = self.graph("value=${name:-$(fallback)}\nafter\n")
        fallback = self.node(graph, "fallback")
        self.assertTrue(fallback.reachable)
        self.assertFalse(fallback.guaranteed)
        self.assertIn(EXPANSION_REGION, fallback.enclosure_kinds)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_every_conditional_expansion_form_is_modelled(self) -> None:
        for word in (":-", "-", ":+", "+", ":=", "=", ":?", "?"):
            with self.subTest(word=word):
                graph = self.graph("value=${name%s$(fallback)}\n" % word)
                self.assertFalse(self.node(graph, "fallback").guaranteed)

    def test_an_unconditional_expansion_word_stays_guaranteed(self) -> None:
        for word in ("%", "#", "%%", "##"):
            with self.subTest(word=word):
                graph = self.graph("value=${name%s$(pattern)}\n" % word)
                self.assertTrue(self.node(graph, "pattern").guaranteed)
        graph = self.graph('value="prefix$(plain)suffix"\n')
        self.assertTrue(self.node(graph, "plain").guaranteed)

    def test_a_nested_conditional_expansion_stays_conditional(self) -> None:
        graph = self.graph("value=${outer:-${inner:-$(deep)}}\n")
        self.assertFalse(self.node(graph, "deep").guaranteed)

    def test_a_length_expansion_of_a_special_parameter_is_conditional(self) -> None:
        graph = self.graph("value=${#-$(fallback)}\nafter\n")
        self.assertFalse(self.node(graph, "fallback").guaranteed)
        graph = self.graph("value=${#name}$(plain)\n")
        self.assertTrue(self.node(graph, "plain").guaranteed)

    def test_a_later_case_alternative_is_expanded_conditionally(self) -> None:
        graph = self.graph(
            'case "$value" in "$(first)"|"$(second)") matched;; esac\n'
        )
        matched = self.node(graph, "matched")
        self.assertTrue(graph.dominates(self.node(graph, "first"), matched))
        self.assertFalse(graph.dominates(self.node(graph, "second"), matched))

    def test_a_case_pattern_expansion_runs_before_the_arm_body(self) -> None:
        graph = self.graph('case "$value" in "$(pattern)") matched;; esac\nafter\n')
        pattern = self.node(graph, "pattern")
        matched = self.node(graph, "matched")
        self.assertTrue(pattern.reachable)
        self.assertFalse(pattern.guaranteed)
        self.assertTrue(graph.precedes(pattern, matched))
        self.assertTrue(graph.dominates(pattern, matched))


class DispatchResolutionTest(ExecutionGraphSupportTest):
    def test_a_call_before_the_declaration_is_not_the_declared_body(self) -> None:
        source = "early\nearly() { echo body; exit 0; }\nafter\n"
        graph = self.graph(source)
        call = self.node(graph, "early")
        self.assertFalse(call.is_call)
        self.assertEqual(graph.find("echo"), ())
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_a_call_after_the_declaration_runs_the_declared_body(self) -> None:
        graph = self.graph("late() { echo body; }\nlate\nafter\n")
        self.assertTrue(self.node(graph, "late").is_call)
        self.assertTrue(self.node(graph, "echo").guaranteed)

    def test_a_body_sees_a_declaration_that_precedes_its_call_site(self) -> None:
        graph = self.graph("outer() { inner; }\ninner() { echo body; }\nouter\n")
        self.assertTrue(self.node(graph, "inner").is_call)
        self.assertTrue(self.node(graph, "echo").guaranteed)

    def test_a_body_cannot_see_a_declaration_after_its_call_site(self) -> None:
        graph = self.graph("outer() { inner; }\nouter\ninner() { echo body; }\n")
        self.assertFalse(self.node(graph, "inner").is_call)
        self.assertEqual(graph.find("echo"), ())

    def test_an_ambiguous_prefix_leaves_the_target_unresolved(self) -> None:
        # `builtin` is not defined by POSIX: dash runs nothing while another
        # shell runs a built-in, so the word is reported, not guessed.
        graph = self.graph("builtin exit 0\nafter\n")
        node = self.node(graph, "builtin")
        self.assertTrue(node.dynamic)
        self.assertIsNone(node.effect)
        self.assertTrue(self.node(graph, "after").guaranteed)
        self.assertFalse(graph.is_fully_resolved)

    def test_a_transparent_prefix_never_runs_a_declared_body(self) -> None:
        prefixes = shell_execution.TRANSPARENT_PREFIXES - {"exec"}
        prefixes -= shell_execution.AMBIGUOUS_PREFIXES | shell_execution.DISPUTED_PREFIXES
        for prefix in sorted(prefixes):
            with self.subTest(prefix=prefix):
                graph = self.graph("target() { echo body; }\n%s target\n" % prefix)
                self.assertEqual(graph.find("echo"), ())
                self.assertFalse(self.node(graph, "target").is_call)

    def test_exec_of_a_declared_name_replaces_the_shell(self) -> None:
        graph = self.graph("target() { echo body; }\nexec target\nafter\n")
        target = self.node(graph, "target")
        self.assertEqual(target.effect, EFFECT_EXEC)
        self.assertFalse(target.is_call)
        self.assertFalse(self.node(graph, "after").guaranteed)

    def test_a_command_query_runs_nothing(self) -> None:
        for option in ("-v", "-V"):
            with self.subTest(option=option):
                graph = self.graph(
                    "target() { echo body; }\ncommand %s target\nafter\n" % option
                )
                self.assertEqual(graph.find("echo"), ())
                self.assertEqual(graph.find("target"), ())
                self.assertTrue(self.node(graph, "after").guaranteed)

    def test_a_declared_name_shadowing_a_prefix_is_still_called(self) -> None:
        graph = self.graph("env() { echo body; }\nenv target\n")
        self.assertTrue(self.node(graph, "env").is_call)
        self.assertTrue(self.node(graph, "echo").guaranteed)

    def test_an_effect_word_behind_a_prefix_keeps_its_effect(self) -> None:
        graph = self.graph("command exit 1\nafter\n")
        self.assertEqual(self.node(graph, "exit").termination, TERMINATION_FAILURE)
        self.assertFalse(self.node(graph, "after").guaranteed)

    def test_an_effect_word_behind_an_external_prefix_has_no_effect(self) -> None:
        for prefix in ("env", "nohup"):
            with self.subTest(prefix=prefix):
                graph = self.graph("%s exit 0\nafter\n" % prefix)
                self.assertIsNone(self.node(graph, "exit").effect)
                self.assertTrue(self.node(graph, "after").guaranteed)

    def test_a_disputed_prefix_over_a_shell_operand_is_rejected(self) -> None:
        # `time` is a reserved word in one reference shell, which runs `exit`
        # and a declared body in the current shell, and an external utility in
        # another, which cannot. Neither reading may be assumed.
        self.assert_rejected("time exit 0\nafter\n", "runs in the current shell")
        self.assert_rejected(
            "target() { body; }\ntime target\nafter\n", "runs in the current shell"
        )
        self.assert_rejected("time command exit 0\n", "runs in the current shell")
        self.assert_rejected("time cd /\nafter\n", "runs in the current shell")
        self.assert_rejected("time kill %1\n", "runs in the current shell")
        self.assert_rejected("time worker arg\n", "runs in the current shell")
        # Deciding which operands the two readings agree about would need a
        # complete built-in inventory for every reference shell, so no operand
        # of a disputed prefix is accepted. The prefix alone still resolves.
        graph = self.graph("time\nafter\n")
        self.assertEqual(self.node(graph, "time").name, "time")
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_an_external_prefix_ends_prefix_resolution(self) -> None:
        graph = self.graph("target() { body; }\nnohup command target\nafter\n")
        self.assertEqual(self.node(graph, "command").name, "command")
        self.assertEqual(graph.find("target"), ())
        self.assertEqual(graph.find("body"), ())

    def test_a_clustered_query_option_still_runs_nothing(self) -> None:
        graph = self.graph("target() { body; }\ncommand -pv target\nafter\n")
        self.assertEqual(graph.find("body"), ())
        self.assertEqual(graph.find("target"), ())

    def test_an_option_operand_is_not_the_command_word(self) -> None:
        graph = self.graph("env -u NAME real\nafter\n")
        self.assertEqual(self.node(graph, "real").name, "real")
        self.assertEqual(graph.find("NAME"), ())

    def test_an_assignment_before_the_command_word_is_skipped(self) -> None:
        graph = self.graph('env NAME=value real\nafter\n')
        self.assertEqual(self.node(graph, "real").name, "real")

    def test_an_unknown_prefix_option_leaves_the_target_unresolved(self) -> None:
        graph = self.graph("env -Z real\nafter\n")
        self.assertEqual(len(graph.dynamic_commands), 1)
        self.assertFalse(graph.is_fully_resolved)

    def test_a_terminating_exit_status_uses_the_reported_status(self) -> None:
        graph = self.graph("exit 256\nafter\n")
        self.assertEqual(self.node(graph, "exit").termination, TERMINATION_SUCCESS)
        graph = self.graph("exit 257\nafter\n")
        self.assertEqual(self.node(graph, "exit").termination, TERMINATION_FAILURE)


class ReportedLimitTest(ExecutionGraphSupportTest):
    def test_a_redirection_that_can_fail_is_reported(self) -> None:
        graph = self.graph("plain\nwrite > out\n")
        self.assertFalse(self.node(graph, "plain").may_fail_before_running)
        self.assertTrue(self.node(graph, "write").may_fail_before_running)

    def test_shell_option_changes_are_reported(self) -> None:
        graph = self.graph("set -eu\nset --\nset\nafter\n")
        options = graph.shell_options
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].argument_values, ("-eu",))

    def test_an_empty_word_list_never_enters_the_loop_body(self) -> None:
        graph = self.graph("for name in; do body; done\nafter\n")
        self.assertFalse(self.node(graph, "body").reachable)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_positional_parameters_may_enter_the_loop_body(self) -> None:
        graph = self.graph("for name; do body; done\nafter\n")
        body = self.node(graph, "body")
        self.assertTrue(body.reachable)
        self.assertFalse(body.guaranteed)


class RedirectionOrderTest(ExecutionGraphSupportTest):
    def test_a_here_document_expansion_follows_the_earlier_redirection(self) -> None:
        # The shell performs `< missing` before it expands the here-document,
        # so a failure there skips the substitution completely.
        graph = self.graph("cat < missing <<EOF\n$(probe)\nEOF\nafter\n")
        probe = self.node(graph, "probe")
        self.assertTrue(probe.reachable)
        self.assertFalse(probe.guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_command_words_expand_before_the_assignment_prefix(self) -> None:
        # Every reference shell expands the command words first, then disagrees
        # about the prefix and the redirections, so the prefix is ordered last.
        graph = self.graph("A=$(assign) runner $(word) >$(target)\n")
        assign = self.node(graph, "assign")
        word = self.node(graph, "word")
        target = self.node(graph, "target")
        self.assertTrue(graph.dominates(word, assign))
        self.assertTrue(graph.dominates(word, target))
        self.assertFalse(graph.dominates(assign, word))
        self.assertTrue(word.guaranteed)
        # A failing redirection can skip the prefix in one reference shell, so
        # the prefix keeps no guarantee and no order against the redirection.
        self.assertFalse(assign.guaranteed)
        self.assertFalse(graph.precedes(word, assign))

    def test_the_first_redirection_expansion_is_still_guaranteed(self) -> None:
        # One reference shell expands every redirection target before applying
        # any redirection, and another applies each redirection as it reads it,
        # so a later target keeps the skip path both readings allow.
        graph = self.graph("cat < $(first) < $(second)\nafter\n")
        self.assertTrue(self.node(graph, "first").guaranteed)
        self.assertFalse(self.node(graph, "second").guaranteed)

    def test_a_redirected_command_reports_its_own_skip_path(self) -> None:
        graph = self.graph("write > out\nafter\n")
        write = self.node(graph, "write")
        self.assertTrue(write.may_fail_before_running)
        self.assertFalse(write.guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)
        self.assertIn(
            REDIRECTION_SKIP,
            {edge.transfer for edge in graph.incoming(self.node(graph, "after"))},
        )


class ChildProcessTest(ExecutionGraphSupportTest):
    def test_an_early_end_inside_a_subshell_leaves_the_success_path(self) -> None:
        # A failing command inside a subshell ends only that subshell, so the
        # outer script can still terminate successfully without the commands
        # that follow it inside the subshell.
        graph = self.graph("( set -e; probe; skipped )\nafter\n")
        self.assertTrue(self.node(graph, "set").guaranteed)
        self.assertFalse(self.node(graph, "probe").guaranteed)
        self.assertFalse(self.node(graph, "skipped").guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_an_early_end_inside_a_substitution_leaves_the_success_path(self) -> None:
        graph = self.graph("value=$(first; second)\nafter\n")
        self.assertTrue(self.node(graph, "first").guaranteed)
        self.assertFalse(self.node(graph, "second").guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_a_single_command_child_process_keeps_its_guarantee(self) -> None:
        graph = self.graph("( only )\nafter\n")
        self.assertTrue(self.node(graph, "only").guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_an_early_end_at_the_top_level_is_a_failing_termination(self) -> None:
        graph = self.graph("set -e\nprobe\nrequired\n")
        self.assertTrue(self.node(graph, "probe").guaranteed)
        self.assertTrue(self.node(graph, "required").guaranteed)


class CompoundRedirectionTest(ExecutionGraphSupportTest):
    def test_a_redirected_group_can_be_skipped_whole(self) -> None:
        graph = self.graph("{ first; second; } > out\nafter\n")
        for name in ("first", "second"):
            node = self.node(graph, name)
            self.assertTrue(node.reachable)
            self.assertFalse(node.guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)
        self.assertIn(
            REDIRECTION_SKIP,
            {edge.transfer for edge in graph.incoming(self.node(graph, "after"))},
        )

    def test_a_redirected_call_can_be_skipped_whole(self) -> None:
        graph = self.graph("target() { body; }\ntarget > out\nafter\n")
        self.assertTrue(self.node(graph, "target").may_fail_before_running)
        self.assertFalse(self.node(graph, "body").guaranteed)
        self.assertTrue(self.node(graph, "after").guaranteed)

    def test_every_redirected_compound_carries_a_skip_path(self) -> None:
        sources = {
            "if probe; then body; fi > out\nafter\n": "body",
            "while probe; do body; done < in\nafter\n": "body",
            "for name in a; do body; done > out\nafter\n": "body",
            "case value in a) body;; esac > out\nafter\n": "body",
            "( body ) > out\nafter\n": "body",
        }
        for source, name in sources.items():
            with self.subTest(source=source):
                graph = self.graph(source)
                self.assertFalse(self.node(graph, name).guaranteed)
                after = self.node(graph, "after")
                self.assertTrue(after.guaranteed)
                self.assertIn(
                    REDIRECTION_SKIP,
                    {edge.transfer for edge in graph.incoming(after)},
                )
                # A word that runs on every unredirected execution of the
                # compound loses that guarantee to the redirection alone.
                head = graph.find("probe") or graph.find("value")
                if head:
                    self.assertFalse(head[0].guaranteed)
                    self.assertTrue(head[0].reachable)

    def test_an_unredirected_group_keeps_its_guarantee(self) -> None:
        graph = self.graph("{ first; second; }\nafter\n")
        self.assertTrue(self.node(graph, "first").guaranteed)
        self.assertTrue(self.node(graph, "second").guaranteed)


class RejectedGraphTest(ExecutionGraphSupportTest):
    def test_command_table_mutation_is_rejected(self) -> None:
        self.assert_rejected(
            "alias finish='exit 0'\nfinish\n", "how a later command word resolves"
        )
        self.assert_rejected("unalias finish\n", "how a later command word resolves")
        self.assert_rejected(
            "target() { body; }\nunset -f target\ntarget\n",
            "how a later command word resolves",
        )
        self.assert_rejected(
            "target() { body; }\nunset target\n",
            "how a later command word resolves",
        )

    def test_unset_of_a_plain_variable_is_accepted(self) -> None:
        graph = self.graph("unset -v name\nunset other\nafter\n")
        self.assertTrue(self.node(graph, "after").guaranteed)
        self.assertTrue(graph.is_fully_resolved)

    def test_an_explicit_variable_unset_keeps_a_shared_name(self) -> None:
        graph = self.graph("target() { body; }\nunset -v target\ntarget\n")
        self.assertTrue(self.node(graph, "target").is_call)
        self.assertTrue(self.node(graph, "body").guaranteed)

    def test_recursive_calls_have_no_bounded_graph(self) -> None:
        self.assert_rejected("f() { f; }\nf\n", "recursive call to `f`")
        self.assert_rejected(
            "a() { b; }\nb() { a; }\na\n", "recursive call to `a`"
        )

    def test_alternate_transfers_outside_their_region_are_rejected(self) -> None:
        self.assert_rejected("break\n", "not inside 1 enclosing loops")
        self.assert_rejected("continue\n", "not inside 1 enclosing loops")
        self.assert_rejected(
            "while x; do break 2; done\n", "not inside 2 enclosing loops"
        )
        self.assert_rejected(
            "while x; do ( break ); done\n", "not inside 1 enclosing loops"
        )
        self.assert_rejected(
            "while x; do body && break & done\n", "not inside 1 enclosing loops"
        )
        self.assert_rejected(
            'while x; do break "$n"; done\n', "exact bounded positive literal level"
        )
        self.assert_rejected("while x; do break 0; done\n", "exact bounded positive literal level")

    def test_return_outside_a_function_body_is_rejected(self) -> None:
        self.assert_rejected("return\n", "not inside a function body")
        self.assert_rejected(
            "f() { ( return ); }\nf\n", "not inside a function body"
        )
        self.assert_rejected(
            "f() { inner | return; }\nf\n", "not inside a function body"
        )

    def test_unbalanced_structures_are_rejected_before_the_graph(self) -> None:
        # The checked function table already rejects an unbalanced block, so no
        # partially connected graph is ever built from one.
        for source in (
            "if x; then y\n",
            "while x; do y\n",
            "for i in 1; do y\n",
            "case x in (a) y;;\n",
            "{ y\n",
            "( y\n",
            ")\n",
        ):
            with self.subTest(source=source):
                with self.assertRaises(ShellFunctionError):
                    self.graph(source)

    def test_malformed_structures_are_rejected(self) -> None:
        self.assert_rejected("if x; y; fi\n", "expected `then`")
        self.assert_rejected("while x; y; done\n", "expected `do`")
        self.assert_rejected("until x; y; done\n", "expected `do`")
        self.assert_rejected("for i in a; y; done\n", "expected `do`")
        self.assert_rejected("for 1x in a; do y; done\n", "exact literal name")
        self.assert_rejected("a >\n", "redirection lacks a target word")
        self.assert_rejected("a |\n", "records end where a command is required")

    def test_derivation_requires_checked_records_and_a_checked_table(self) -> None:
        records = project("a\n")
        with self.assertRaises(ShellExecutionError):
            derive("a\n", derive_table(records))  # type: ignore[arg-type]
        with self.assertRaises(ShellExecutionError):
            derive(records, None)  # type: ignore[arg-type]

    def test_a_table_from_other_records_is_rejected(self) -> None:
        records = project("f() { :; }\nf\n")
        other = derive_table(project("padding\nf() { :; }\nf\n"))
        with self.assertRaises(ShellExecutionError) as raised:
            derive(records, other)
        self.assertIn("does not describe the supplied lexical records", str(raised.exception))

    def test_rejection_reports_an_exact_source_position(self) -> None:
        with self.assertRaises(ShellExecutionError) as raised:
            self.graph("first\nsecond\nbreak\n")
        self.assertEqual(raised.exception.position.line, 3)
        self.assertEqual(raised.exception.position.column, 1)

    def test_the_graph_depth_stays_bounded(self) -> None:
        source = "( " * (MAX_DEPTH + 2) + "deep" + " )" * (MAX_DEPTH + 2) + "\n"
        self.assert_rejected(source, "bounded depth")

    def test_the_expansion_region_depth_stays_bounded(self) -> None:
        source = "x=$(" * (MAX_DEPTH + 2) + "deep" + ")" * (MAX_DEPTH + 2) + "\n"
        self.assert_rejected(source, "bounded depth")

    def test_the_call_depth_stays_bounded(self) -> None:
        names = [f"f{step}" for step in range(MAX_CALL_DEPTH + 2)]
        lines = [
            f"{name}() {{ {names[step + 1]}; }}"
            for step, name in enumerate(names[:-1])
        ]
        lines.append(f"{names[-1]}() {{ :; }}")
        lines.append(names[0])
        self.assert_rejected("\n".join(lines) + "\n", "bounded depth")

    def test_the_graph_size_stays_bounded(self) -> None:
        original = shell_execution.MAX_NODES
        try:
            shell_execution.MAX_NODES = 5
            self.assert_rejected("a\nb\nc\nd\ne\nf\n", "bounded graph size")
        finally:
            shell_execution.MAX_NODES = original


class SuppliedScriptTest(ExecutionGraphSupportTest):
    def repository_graph(self, relative: str) -> ExecutionGraph:
        records = project((ROOT / relative).read_bytes())
        return derive(records, derive_table(records))

    def test_repository_scripts_derive_a_reachable_graph(self) -> None:
        expected = {
            "tests/smoke.sh": "run_root_python",
            "scripts/lint-project-workflow.sh": "python3",
            "scripts/complete-plan.sh": "awk",
            "tests/root-plan-lifecycle.sh": "grep",
        }
        for relative, name in expected.items():
            with self.subTest(relative=relative):
                graph = self.repository_graph(relative)
                self.assertTrue(graph.find(name))
                self.assertTrue(graph.success_path)
                self.assertEqual(graph.unreachable, ())

    def test_a_script_without_commands_derives_an_empty_graph(self) -> None:
        graph = self.repository_graph("tests/lib-copier.sh")
        self.assertEqual(graph.commands, ())
        self.assertEqual(graph.success_path, ())

    def test_a_documented_skip_path_removes_later_guarantees(self) -> None:
        graph = self.repository_graph("tests/smoke.sh")
        # `tests/smoke.sh` exits 0 when the copier CLI is absent, so no command
        # after that skip runs on every successful execution.
        self.assertTrue(graph.find_reachable("run_copier"))
        self.assertEqual(graph.find_guaranteed("run_copier"), ())

    def test_module_never_executes_or_re_tokenizes_the_supplied_script(self) -> None:
        text = (ROOT / "scripts/project_workflow/shell_execution.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "subprocess",
            "os.system",
            "importlib",
            "exec(",
            "eval(",
            "shell_lexical.project",
            "shell_functions.derive",
            "def project",
        ):
            self.assertNotIn(forbidden, text)

    def test_derivation_is_deterministic(self) -> None:
        source = "f() {\n  echo $(inner)\n}\nf\nif x; then f; fi\n"
        first = self.graph(source)
        second = self.graph(source)
        self.assertEqual(first.nodes, second.nodes)
        self.assertEqual(first.edges, second.edges)
        self.assertEqual(
            [node.name for node in first.success_path],
            [node.name for node in second.success_path],
        )


if __name__ == "__main__":
    unittest.main()
