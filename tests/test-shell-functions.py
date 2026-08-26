#!/usr/bin/env python3
"""Behavior tests for the bounded shell function table."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from project_workflow import shell_functions  # noqa: E402
from project_workflow.shell_functions import (  # noqa: E402
    FunctionTable,
    ShellFunctionError,
    derive,
)
from project_workflow.shell_lexical import project  # noqa: E402


class FunctionTableSupportTest(unittest.TestCase):
    def table(self, source: str) -> FunctionTable:
        return derive(project(source))

    def names(self, source: str) -> tuple[str, ...]:
        return self.table(source).names

    def assert_rejected(self, source: str, expected: str) -> None:
        with self.assertRaises(ShellFunctionError) as raised:
            self.table(source)
        self.assertIn(expected, str(raised.exception))


class AcceptedDeclarationTest(FunctionTableSupportTest):
    def test_unique_top_level_declarations_form_the_table(self) -> None:
        source = "a() {\n  echo x\n}\nb() { echo y; }\na\n"
        table = self.table(source)
        self.assertEqual(table.names, ("a", "b"))
        self.assertEqual(len(table), 2)
        self.assertIn("a", table)
        self.assertNotIn("missing", table)
        self.assertIs(table.get("missing"), None)
        self.assertEqual([declaration.name for declaration in table], ["a", "b"])

    def test_declaration_records_its_exact_name_and_brace_span(self) -> None:
        source = "outer() {\n  inner_call arg\n}\ntrailing\n"
        declaration = self.table(source)["outer"]
        self.assertEqual(declaration.name_token.text, "outer")
        self.assertEqual(declaration.open_brace.text, "{")
        self.assertEqual(declaration.close_brace.text, "}")
        self.assertEqual(declaration.start.line, 1)
        self.assertEqual(declaration.end.line, 3)
        self.assertEqual(
            [token.text for token in declaration.body],
            ["\n", "inner_call", "arg", "\n"],
        )

    def test_brace_in_argument_position_does_not_close_the_body(self) -> None:
        declaration = self.table("f() { echo } ; }\n")["f"]
        self.assertEqual(
            [token.text for token in declaration.body], ["echo", "}", ";"]
        )
        self.assertEqual(declaration.close_brace.start.column, 16)

    def test_missing_name_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.table("a() { :; }\n")["b"]

    def test_derivation_requires_checked_lexical_records(self) -> None:
        with self.assertRaises(ShellFunctionError):
            derive("a() { :; }\n")  # type: ignore[arg-type]

    def test_body_compound_commands_do_not_leave_the_declaration(self) -> None:
        source = (
            "f() {\n"
            "  for value in 1 2; do echo $value; done\n"
            "  while read line; do echo $line; done\n"
            "  if test -n x; then echo y; else echo z; fi\n"
            "  case $1 in (a) echo a;; b) echo b;; esac\n"
            "  { echo grouped; }\n"
            "  ( echo subshell )\n"
            "}\n"
            "g() { :; }\n"
        )
        self.assertEqual(self.names(source), ("f", "g"))

    def test_top_level_case_and_loops_do_not_declare_functions(self) -> None:
        self.assertEqual(self.names("case x in (a) b;; c) d;; esac\n"), ())
        self.assertEqual(self.names("for i in 1 2; do echo $i; done\n"), ())
        self.assertEqual(self.names("{ a; }\nf() { :; }\n"), ("f",))

    def test_top_level_records_exclude_function_bodies_and_blocks(self) -> None:
        table = self.table("f() {\n  hidden\n}\nvisible\nif x; then blocked; fi\n")
        self.assertEqual([token.text for token in table.top_level], ["visible"])

    def test_prefixes_and_redirections_do_not_break_derivation(self) -> None:
        source = "A=1 B=2 >out 2>&1 command arg\nf() { :; }\n"
        self.assertEqual(self.names(source), ("f",))

    def test_declaration_after_a_line_continuation_is_accepted(self) -> None:
        source = "f() \\\n{\n  :\n}\n"
        self.assertEqual(self.names(source), ("f",))

    def test_declaration_separated_by_a_comment_is_accepted(self) -> None:
        self.assertEqual(self.names("f() # note\n{\n  :\n}\n"), ("f",))
        self.assertEqual(self.names("f()\n{\n  :\n}\n"), ("f",))

    def test_case_arms_are_tracked_without_declaring_functions(self) -> None:
        self.assertEqual(self.names("case x in (p) a;; q) b;; esac\n"), ())
        self.assertEqual(self.names("case x in a|b) c;; *) d;; esac\n"), ())
        self.assertEqual(self.names("case x in esac\n"), ())
        source = (
            "f() {\n"
            "  case $1 in\n"
            "    a|b) case $2 in (c) x ;; esac ;;\n"
            "    *) y ;;\n"
            "  esac\n"
            "}\n"
            "g() { :; }\n"
        )
        self.assertEqual(self.names(source), ("f", "g"))

    def test_command_preceding_a_subshell_is_not_a_declaration(self) -> None:
        self.assertEqual(self.names("if ( x ); then y; fi\nf() { :; }\n"), ("f",))


class RejectedDeclarationTest(FunctionTableSupportTest):
    def test_duplicate_declaration_is_rejected(self) -> None:
        self.assert_rejected("a() { :; }\na() { :; }\n", "duplicate function declaration")

    def test_nested_declaration_is_rejected(self) -> None:
        self.assert_rejected("a() {\n  b() { :; }\n}\n", "not at the top level")
        self.assert_rejected("{ a() { :; }; }\n", "not at the top level")
        self.assert_rejected("( a() { :; } )\n", "not at the top level")

    def test_conditional_and_loop_enclosed_declarations_are_rejected(self) -> None:
        self.assert_rejected("if x; then a() { :; }; fi\n", "not at the top level")
        self.assert_rejected("while x; do a() { :; }; done\n", "not at the top level")
        self.assert_rejected("for i in 1; do a() { :; }; done\n", "not at the top level")
        self.assert_rejected("case x in (p) a() { :; };; esac\n", "not at the top level")

    def test_piped_and_listed_declarations_are_rejected(self) -> None:
        self.assert_rejected("x | a() { :; }\n", "not a complete top-level command")
        self.assert_rejected("x && a() { :; }\n", "not a complete top-level command")
        self.assert_rejected("x || a() { :; }\n", "not a complete top-level command")
        self.assert_rejected("! a() { :; }\n", "not a complete top-level command")

    def test_declaration_inside_a_command_substitution_is_rejected(self) -> None:
        self.assert_rejected("x=$(a() { :; })\n", "not at the top level")
        self.assert_rejected(
            "cat <<EOF\n$(a() { :; })\nEOF\n", "not at the top level"
        )

    def test_command_prefixes_leave_no_eval_unchecked(self) -> None:
        # `command`, `builtin`, and `time` run `eval` in the current shell.
        # `exec`, `env`, and `nohup` cannot, and are conservative over-rejection.
        for source in (
            "command eval 'g() { :; }'\n",
            "builtin eval 'g() { :; }'\n",
            "time eval 'g() { :; }'\n",
            "time command eval 'g() { :; }'\n",
            "command command eval 'g() { :; }'\n",
            "command -p eval 'g() { :; }'\n",
            "env FOO=1 eval 'g() { :; }'\n",
            "exec eval 'g() { :; }'\n",
            "nohup eval 'g() { :; }'\n",
            "f() {\n  command eval 'g() { :; }'\n}\n",
            "x=$(command eval 'g() { :; }')\n",
        ):
            with self.subTest(source=source):
                self.assert_rejected(source, "dynamic `eval` command")

    def test_a_function_may_be_named_after_a_command_prefix(self) -> None:
        self.assertEqual(self.names("env() { echo hi; }\nf() { :; }\n"), ("env", "f"))
        self.assertEqual(self.names("command() { :; }\ntime() { :; }\n"), ("command", "time"))

    def test_declaration_after_a_line_operator_newline_is_rejected(self) -> None:
        for source in (
            "cat |\nf() { :; }\n",
            "cat |\n\n\nf() { :; }\n",
            "cat | \\\nf() { :; }\n",
            "false &&\nf() { :; }\n",
            "true ||\nf() { :; }\n",
            "a | b |\nf() { :; }\n",
        ):
            with self.subTest(source=source):
                self.assert_rejected(source, "not a complete top-level command")

    def test_a_completed_list_still_permits_a_later_declaration(self) -> None:
        for source in (
            "a | b\nf() { :; }\n",
            "cat;\nf() { :; }\n",
            "case x in (a) b;; esac\nf() { :; }\n",
            "if x; then y; fi\nf() { :; }\n",
            "a &\nf() { :; }\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(self.names(source), ("f",))

    def test_transparent_prefix_still_accepts_an_ordinary_command(self) -> None:
        self.assertEqual(self.names("command ls -l\nf() { :; }\n"), ("f",))
        self.assertEqual(self.names("env FOO=1 printf x\nf() { :; }\n"), ("f",))

    def test_subshell_terminated_declaration_is_rejected(self) -> None:
        self.assert_rejected(
            "f() { :; } | cat\n", "not a complete top-level command"
        )
        self.assert_rejected("f() { :; } &\n", "not a complete top-level command")
        self.assert_rejected(
            "cat | f() { :; }\n", "not a complete top-level command"
        )

    def test_asynchronous_and_or_list_declaration_is_rejected(self) -> None:
        # `&` makes the whole and-or list run in a subshell, so the declaration
        # never reaches the current shell even though `&&` follows the body.
        for source in (
            "f() { :; } && ls &\n",
            "f() { :; } || ls &\n",
            "f() { :; } && a && b &\n",
            "f() { :; } && a | b &\n",
            "f() { :; } &&\nls &\n",
            "f() { :; } >o && ls &\n",
            "f() { :; } && ls &\ng() { :; }\n",
            "f() { :; } && { a; b; } &\n",
            "f() { :; } && (a) &\n",
            "f() { :; } && case x in a) b;; esac &\n",
            "f() { :; } && if x; then y; fi &\n",
        ):
            with self.subTest(source=source):
                self.assert_rejected(source, "not a complete top-level command")

    def test_current_shell_terminated_declaration_is_accepted(self) -> None:
        self.assertEqual(self.names("f() { :; } >log 2>&1\ng() { :; }\n"), ("f", "g"))
        self.assertEqual(self.names("f() { :; } && g\n"), ("f",))
        self.assertEqual(self.names("f() { :; }"), ("f",))
        self.assertEqual(self.names("f() { :; } && h"), ("f",))
        self.assertEqual(self.names("f() { :; } && true ;\n"), ("f",))
        self.assertEqual(self.names("f() { :; } && ls | cat\n"), ("f",))
        self.assertEqual(self.names("f() { :; } ; true &\n"), ("f",))
        self.assertEqual(self.names("f() { :; } ; { a; b; } &\n"), ("f",))
        self.assertEqual(self.names("true &\nf() { :; }\n"), ("f",))
        self.assertEqual(self.names("f() { :; }\ng() { :; } && h\n"), ("f", "g"))
        # An `&` nested inside a compound command does not make the list async.
        self.assertEqual(self.names("f() { :; } && { a & }\n"), ("f",))
        self.assertEqual(self.names("f() { :; } && if x; then y & fi\n"), ("f",))
        self.assertEqual(self.names("f() { :; } && ( a & )\n"), ("f",))

    def test_hidden_regions_inside_expansions_are_walked(self) -> None:
        for source in (
            'x="$(eval z)"\n',
            "x=${y:-$(eval z)}\n",
            "x=$(( $(eval z) ))\n",
            'x="prefix $(outer $(eval z))"\n',
            "cat <<EOF\n${y:-$(eval z)}\nEOF\n",
        ):
            with self.subTest(source=source):
                self.assert_rejected(source, "dynamic `eval` command")

    def test_hidden_declarations_inside_expansions_are_rejected(self) -> None:
        for source in (
            'x="$(g() { :; })"\n',
            "x=${y:-$(g() { :; })}\n",
            "x=$(outer $(g() { :; }))\n",
        ):
            with self.subTest(source=source):
                self.assert_rejected(source, "not at the top level")

    def test_dynamic_command_words_are_reported_not_silently_trusted(self) -> None:
        table = self.table(
            '"$root/run.sh" arg\n$cmd other\nf() { $inner; }\nx=$(command $nested arg)\n'
        )
        self.assertEqual(
            [token.text for token in table.dynamic_commands],
            ['"$root/run.sh"', "$cmd", "$inner", "$nested"],
        )
        self.assertFalse(table.is_fully_resolved)
        resolved = self.table("literal arg\nf() { :; }\n")
        self.assertEqual(resolved.dynamic_commands, ())
        self.assertTrue(resolved.is_fully_resolved)

    def test_a_quoted_equals_sign_makes_a_command_word_not_an_assignment(self) -> None:
        # bash, bash --posix, dash, and busybox ash all agree on this split:
        # the `=` must be unquoted for the word to be an assignment.
        for source in (
            '"a"=1 arg\n',
            "'a'=1 arg\n",
            'a"="1 arg\n',
            "a'='1 arg\n",
            'a"x"=1 arg\n',
            "a\\=1 arg\n",
            "a$e=1 arg\n",
        ):
            with self.subTest(source=source):
                table = self.table(source)
                self.assertEqual(len(table.top_level), 1)
                self.assertEqual(table.top_level[0].start.column, 1)
        unquoted = self.table("a=1 arg\n").top_level
        self.assertEqual(len(unquoted), 1)
        self.assertEqual(unquoted[0].start.column, 5)
        continued = self.table("a\\\n=1 arg\nf() { :; }\n")
        self.assertEqual(continued.names, ("f",))
        self.assertEqual([token.text for token in continued.top_level], ["arg"])

    def test_assignment_prefixes_are_not_command_words(self) -> None:
        table = self.table('src=$1\nrel=${path#./}\na=b=c\nf() { :; }\n')
        self.assertEqual(table.names, ("f",))
        self.assertEqual(table.dynamic_commands, ())
        self.assertEqual(table.top_level, ())

    def test_dynamic_declaration_paths_are_rejected(self) -> None:
        self.assert_rejected('eval "a() { :; }"\n', "dynamic `eval` command")
        self.assert_rejected("x=$(eval y)\n", "dynamic `eval` command")
        self.assert_rejected("cat <<EOF\n$(eval y)\nEOF\n", "dynamic `eval` command")
        self.assert_rejected("f() {\n  eval y\n}\n", "dynamic `eval` command")
        self.assert_rejected("function a { :; }\n", "`function` keyword declaration")

    def test_split_declaration_is_rejected(self) -> None:
        self.assert_rejected("a(\n)\n{ :; }\n", "is not a function declaration")
        self.assert_rejected("a (\n) { :; }\n", "is not a function declaration")

    def test_non_brace_body_is_rejected(self) -> None:
        self.assert_rejected("a() ( echo x )\n", "function body must be a brace group")
        self.assert_rejected("a()\n", "function body must be a brace group")
        self.assert_rejected("a() if x; then y; fi\n", "function body must be a brace group")

    def test_non_literal_or_invalid_name_is_rejected(self) -> None:
        self.assert_rejected('"$name"() { :; }\n', "exact literal name")
        self.assert_rejected("a-b() { :; }\n", "exact literal name")
        self.assert_rejected("if() { :; }\n", "unexpected `}`")

    def test_unterminated_structures_are_rejected(self) -> None:
        self.assert_rejected("a() {\n  echo x\n", "function body is not terminated")
        self.assert_rejected("if x; then y\n", "unterminated `fi` block")
        self.assert_rejected("a() { :; }\n)\n", "unbalanced closing parenthesis")

    def test_rejection_reports_an_exact_source_position(self) -> None:
        with self.assertRaises(ShellFunctionError) as raised:
            self.table("a() { :; }\nb() {\n  c() { :; }\n}\n")
        self.assertEqual(raised.exception.position.line, 3)
        self.assertEqual(raised.exception.position.column, 3)


class SuppliedScriptTest(FunctionTableSupportTest):
    def test_repository_scripts_derive_a_unique_table(self) -> None:
        expected = {
            "tests/smoke.sh": "run_root_python",
            "scripts/context-compress.sh": "usage",
            "tests/lib-copier.sh": "run_copier",
        }
        for relative, name in expected.items():
            with self.subTest(relative=relative):
                table = derive(project((ROOT / relative).read_bytes()))
                self.assertIn(name, table)
                self.assertEqual(len(set(table.names)), len(table.names))

    def test_scripts_without_declarations_derive_an_empty_table(self) -> None:
        for relative in ("scripts/lint-project-workflow.sh", "tests/copier-minimum.sh"):
            with self.subTest(relative=relative):
                self.assertEqual(derive(project((ROOT / relative).read_bytes())).names, ())

    def test_nested_declaration_in_the_copier_fixture_is_rejected(self) -> None:
        fixture = (ROOT / "tests/copier-update.sh").read_bytes()
        with self.assertRaises(ShellFunctionError) as raised:
            derive(project(fixture))
        self.assertIn("not at the top level", str(raised.exception))

    def test_module_never_executes_or_imports_the_supplied_script(self) -> None:
        text = (ROOT / "scripts/project_workflow/shell_functions.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("subprocess", "os.system", "importlib", "exec(", "eval("):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("shell_lexical.project", text)
        self.assertNotIn("def project", text)

    def test_derivation_is_deterministic(self) -> None:
        source = "a() {\n  echo $(inner)\n}\nb() { :; }\n"
        first = self.table(source)
        second = self.table(source)
        self.assertEqual(first.names, second.names)
        self.assertEqual(first.declarations, second.declarations)


if __name__ == "__main__":
    unittest.main()
