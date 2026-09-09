#!/usr/bin/env python3
"""Behavior tests for the bounded shell lexical projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from project_workflow import shell_lexical  # noqa: E402
from project_workflow.shell_lexical import (  # noqa: E402
    ARITHMETIC_EXPANSION,
    COMMAND_SUBSTITUTION,
    COMMENT,
    CONTINUATION,
    DOUBLE_QUOTED,
    ESCAPE,
    HEREDOC_BODY,
    IO_NUMBER,
    LINE_CONTINUATION,
    LITERAL,
    NEWLINE,
    OPERATOR,
    PARAMETER_EXPANSION,
    SINGLE_QUOTED,
    ShellLexicalError,
    WORD,
    executable_regions,
    project,
)


class ProjectionSupportTest(unittest.TestCase):
    def kinds(self, source: str) -> list[str]:
        return [token.kind for token in project(source)]

    def words(self, source: str) -> list[str]:
        return [token.text for token in project(source) if token.kind == WORD]

    def here_documents(self, source: str) -> list[shell_lexical.Token]:
        return [token for token in project(source) if token.kind == HEREDOC_BODY]

    def is_delimiter_line(self, gap: str, body: shell_lexical.Token) -> bool:
        """Report whether an unprojected gap is exactly a here-document delimiter line."""

        head, separator, tail = gap.partition("\n")
        if tail.strip(" \t"):
            return False
        candidate = head.lstrip("\t") if body.strip_tabs else head
        return candidate == body.delimiter and (separator == "\n" or not tail)

    def assert_complete_cover(self, source: str) -> None:
        """Assert the records cover every byte outside blanks and delimiter lines."""

        records = shell_lexical.project(source)
        cursor = 0
        previous = None
        for token in records:
            gap = source[cursor:token.start.offset]
            if gap:
                allowed = gap.strip(" \t") == ""
                if not allowed and previous is not None and previous.kind == HEREDOC_BODY:
                    allowed = self.is_delimiter_line(gap, previous)
                self.assertTrue(allowed, f"unprojected source {gap!r}")
            self.assertEqual(token.text, source[token.start.offset:token.end.offset])
            cursor = token.end.offset
            previous = token
        trailing = source[cursor:]
        if trailing:
            allowed = trailing.strip(" \t") == ""
            if not allowed and previous is not None and previous.kind == HEREDOC_BODY:
                allowed = self.is_delimiter_line(trailing, previous)
            self.assertTrue(allowed, f"unprojected trailing source {trailing!r}")

    def assert_rejected(self, source: str, expected: str) -> None:
        with self.assertRaises(ShellLexicalError) as raised:
            project(source)
        self.assertIn(expected, str(raised.exception))


class LexicalProjectionTest(ProjectionSupportTest):
    def test_projection_covers_the_supplied_bytes_without_gaps_or_overlap(self) -> None:
        source = 'a=1 echo "x $y" | wc -l\n# note\ncat <<EOF\nbody\nEOF\n'
        self.assert_complete_cover(source)
        self.assert_complete_cover("cat <<-END\n\tbody\n\tEND\n")
        self.assert_complete_cover("cat <<A <<B\nfirst\nA\nsecond\nB\n")
        self.assertEqual(project(source).source, source)

    def test_coverage_check_detects_a_dropped_record(self) -> None:
        source = "cat <<EOF\nbody\nEOF\necho tail\n"
        original = shell_lexical.project

        def truncated(text: str | bytes) -> shell_lexical.LexicalProjection:
            records = original(text)
            return shell_lexical.LexicalProjection(
                source=records.source,
                tokens=tuple(
                    token for token in records.tokens if token.kind != HEREDOC_BODY
                ),
            )

        shell_lexical.project = truncated  # type: ignore[assignment]
        try:
            with self.assertRaises(AssertionError):
                self.assert_complete_cover(source)
        finally:
            shell_lexical.project = original  # type: ignore[assignment]

    def test_projection_is_deterministic_for_identical_input(self) -> None:
        source = 'f() {\n  echo "$(date) $((1 + 2))"\n}\n'
        first = project(source)
        second = project(source.encode("utf-8"))
        self.assertEqual(first.tokens, second.tokens)

    def test_word_segments_expose_quotes_escapes_and_expansions(self) -> None:
        (word,) = [token for token in project("a'b'\"c$d\"\\e$(f)$((1))") if token.kind == WORD]
        self.assertEqual(
            [segment.kind for segment in word.segments],
            [
                LITERAL,
                SINGLE_QUOTED,
                DOUBLE_QUOTED,
                ESCAPE,
                COMMAND_SUBSTITUTION,
                ARITHMETIC_EXPANSION,
            ],
        )
        self.assertIsNone(word.literal_value)
        self.assertEqual(project("'plain text'").tokens[0].literal_value, "plain text")
        self.assertEqual(project('"a\\"b"').tokens[0].literal_value, 'a"b')

    def test_command_substitutions_expose_every_nested_executable_region(self) -> None:
        records = project('echo "$(inner $(deepest) )"\n')
        regions = list(executable_regions(records))
        self.assertEqual(
            [[token.text for token in region if token.kind == WORD] for region in regions],
            [["inner", "$(deepest)"], ["deepest"]],
        )

    def test_command_substitution_keeps_a_nested_subshell_intact(self) -> None:
        (region,) = list(executable_regions(project("echo $( (a; b) )\n")))
        self.assertEqual(
            [token.text for token in region],
            ["(", "a", ";", "b", ")"],
        )

    def test_expansion_only_arithmetic_has_no_executable_region(self) -> None:
        records = project("echo $((1 + (2 * 3)))\n")
        self.assertEqual(list(executable_regions(records)), [])
        (word,) = [token for token in records if token.text.startswith("$((")]
        self.assertEqual(word.segments[0].kind, ARITHMETIC_EXPANSION)
        self.assertEqual(word.segments[0].text, "$((1 + (2 * 3)))")

    def test_arithmetic_expansion_exposes_a_nested_executable_region(self) -> None:
        (region,) = list(executable_regions(project("echo $(( $(id -u) + 1 ))\n")))
        self.assertEqual([token.text for token in region], ["id", "-u"])

    def test_parameter_expansion_exposes_a_nested_executable_region(self) -> None:
        (region,) = list(executable_regions(project("echo ${name:-$(id -u)}\n")))
        self.assertEqual([token.text for token in region], ["id", "-u"])
        (nested,) = list(
            executable_regions(project("run_id=${2:-${R:-$(date -u)}}\n"))
        )
        self.assertEqual([token.text for token in nested], ["date", "-u"])

    def test_quoted_parts_of_a_parameter_expansion_stay_projected(self) -> None:
        (word,) = [
            token
            for token in project('x=${input#"$root"/}\n')
            if token.kind == WORD
        ]
        (expansion,) = word.segments[1:]
        self.assertEqual(expansion.kind, PARAMETER_EXPANSION)
        self.assertEqual(
            [segment.kind for segment in expansion.segments],
            [LITERAL, DOUBLE_QUOTED, LITERAL],
        )

    def test_parameter_expansions_project_as_explicit_records(self) -> None:
        (word,) = [token for token in project("${name:-$other}$?") if token.kind == WORD]
        self.assertEqual(
            [segment.text for segment in word.segments],
            ["${name:-$other}", "$?"],
        )
        self.assertEqual(
            {segment.kind for segment in word.segments}, {PARAMETER_EXPANSION}
        )
        self.assertEqual(
            [part.text for part in word.segments[0].segments], ["name:-", "$other"]
        )


class HereDocumentTest(ProjectionSupportTest):
    def test_quoted_here_document_body_stays_unexpanded(self) -> None:
        (body,) = self.here_documents("cat <<'EOF'\n$(danger) $name\nEOF\n")
        self.assertTrue(body.quoted_delimiter)
        self.assertEqual(body.delimiter, "EOF")
        self.assertEqual(body.text, "$(danger) $name\n")
        self.assertEqual([segment.kind for segment in body.segments], [SINGLE_QUOTED])
        self.assertEqual(list(executable_regions(project("cat <<'EOF'\n$(danger)\nEOF\n"))), [])

    def test_unquoted_here_document_body_exposes_its_executable_region(self) -> None:
        records = project("cat <<EOF\nvalue $(danger arg)\nEOF\n")
        (body,) = [token for token in records if token.kind == HEREDOC_BODY]
        self.assertFalse(body.quoted_delimiter)
        (region,) = list(executable_regions(records))
        self.assertEqual([token.text for token in region], ["danger", "arg"])

    def test_partially_quoted_delimiter_still_suppresses_expansion(self) -> None:
        (body,) = self.here_documents('cat <<E"O"F\n$(danger)\nEOF\n')
        self.assertTrue(body.quoted_delimiter)
        self.assertEqual(body.delimiter, "EOF")
        self.assertEqual([segment.kind for segment in body.segments], [SINGLE_QUOTED])

    def test_indented_here_document_strips_tabs_from_body_and_delimiter(self) -> None:
        (body,) = self.here_documents("cat <<-EOF\n\t\tline\n\tEOF\n")
        self.assertTrue(body.strip_tabs)
        self.assertEqual(body.text, "\t\tline\n")
        self.assertEqual(body.content, "line\n")

    def test_plain_here_document_does_not_accept_an_indented_delimiter(self) -> None:
        self.assert_rejected("cat <<EOF\nline\n\tEOF\n", "is not terminated")

    def test_multiple_here_documents_on_one_line_project_in_order(self) -> None:
        bodies = self.here_documents("cat <<A <<B\nfirst\nA\nsecond\nB\n")
        self.assertEqual([body.delimiter for body in bodies], ["A", "B"])
        self.assertEqual([body.text for body in bodies], ["first\n", "second\n"])

    def test_here_document_inside_a_comment_does_not_start_a_body(self) -> None:
        records = project("# cat <<EOF\necho done\n")
        self.assertEqual([token.kind for token in records if token.kind == HEREDOC_BODY], [])
        self.assertEqual(records.tokens[0].kind, COMMENT)
        self.assertEqual(records.tokens[0].text, "# cat <<EOF")
        self.assertEqual(self.words("# cat <<EOF\necho done\n"), ["echo", "done"])

    def test_here_document_body_keeps_comment_and_operator_text_inert(self) -> None:
        (body,) = self.here_documents("cat <<'EOF'\n# not a comment\na | b > c\nEOF\n")
        self.assertEqual(body.text, "# not a comment\na | b > c\n")

    def test_truncated_here_document_is_rejected(self) -> None:
        self.assert_rejected("cat <<EOF\nbody without end\n", "is not terminated")
        self.assert_rejected("cat <<EOF\n", "is not terminated")
        self.assert_rejected("cat <<EOF\nEO", "is not terminated")

    def test_here_document_delimiter_must_be_an_explicit_word(self) -> None:
        self.assert_rejected("cat <<$name\nbody\n", "must not use expansion")
        self.assert_rejected("cat <<''\nbody\n", "must not be empty")
        self.assert_rejected("cat <<\ncat\n", "lacks a delimiter word")
        self.assert_rejected("cat << | wc\n", "lacks a delimiter word")
        self.assert_rejected("cat << # note\n", "lacks a delimiter word")

    def test_here_document_inside_a_command_substitution_stays_projected(self) -> None:
        records = project("x=$(cat <<EOF\n$(danger)\nEOF\n)\n")
        (outer,) = [token for token in records if token.kind == WORD]
        self.assertEqual(outer.segments[1].kind, COMMAND_SUBSTITUTION)
        nested = outer.segments[1].tokens
        (body,) = [token for token in nested if token.kind == HEREDOC_BODY]
        self.assertEqual(body.delimiter, "EOF")
        self.assertIn(
            ["danger"],
            [[token.text for token in region] for region in executable_regions(records)],
        )
        self.assert_rejected("x=$(cat <<EOF\nbody\n)\n", "is not terminated")

    def test_empty_here_document_body_is_projected(self) -> None:
        (body,) = self.here_documents("cat <<EOF\nEOF\n")
        self.assertEqual(body.text, "")
        self.assertEqual(body.segments, ())


class CommentAndContinuationTest(ProjectionSupportTest):
    def test_comment_does_not_continue_across_a_trailing_backslash(self) -> None:
        records = project("# note \\\necho exposed\n")
        self.assertEqual(records.tokens[0].kind, COMMENT)
        self.assertEqual(records.tokens[0].text, "# note \\")
        self.assertEqual(self.words("# note \\\necho exposed\n"), ["echo", "exposed"])

    def test_hash_inside_a_word_stays_literal(self) -> None:
        self.assertEqual(self.words("echo a#b\n"), ["echo", "a#b"])

    def test_comment_requires_an_unquoted_token_start(self) -> None:
        self.assertEqual(self.words("echo '# quoted'\n"), ["echo", "'# quoted'"])
        self.assertEqual([token.kind for token in project("echo # tail\n")][1], COMMENT)

    def test_line_continuation_between_tokens_is_an_explicit_record(self) -> None:
        self.assertEqual(
            self.kinds("echo \\\n  value\n"),
            [WORD, LINE_CONTINUATION, WORD, NEWLINE],
        )

    def test_line_continuation_inside_a_word_joins_the_word(self) -> None:
        (word,) = [token for token in project("val\\\nue\n") if token.kind == WORD]
        self.assertEqual(word.text, "val\\\nue")
        self.assertEqual([segment.kind for segment in word.segments], [LITERAL, CONTINUATION, LITERAL])
        self.assertEqual(word.literal_value, "value")

    def test_line_continuation_does_not_release_a_pending_here_document(self) -> None:
        (body,) = self.here_documents("cat <<EOF \\\n  extra\nbody\nEOF\n")
        self.assertEqual(body.text, "body\n")

    def test_dangling_backslash_at_end_of_input_is_rejected(self) -> None:
        self.assert_rejected("echo \\", "dangling backslash")


class RedirectionTest(ProjectionSupportTest):
    def test_redirection_prefix_projects_an_io_number_and_operator(self) -> None:
        self.assertEqual(
            self.kinds("2>err.log printf hi\n"),
            [IO_NUMBER, OPERATOR, WORD, WORD, WORD, NEWLINE],
        )
        self.assertEqual(project("2>&1\n").tokens[1].text, ">&")

    def test_digits_not_touching_a_redirection_stay_a_word(self) -> None:
        self.assertEqual(self.kinds("2 > out\n"), [WORD, OPERATOR, WORD, NEWLINE])
        self.assertEqual(self.kinds("echo 2\n"), [WORD, WORD, NEWLINE])

    def test_interleaved_assignment_and_redirection_prefixes_project_in_order(self) -> None:
        self.assertEqual(
            [token.text for token in project("A=1 >out B=2 2>&1 cmd arg\n")],
            ["A=1", ">", "out", "B=2", "2", ">&", "1", "cmd", "arg", "\n"],
        )

    def test_every_accepted_redirection_operator_projects(self) -> None:
        source = "a <in >out >>app <&3 >&4 <>rw >|force\n"
        self.assertEqual(
            [token.text for token in project(source) if token.kind == OPERATOR],
            ["<", ">", ">>", "<&", ">&", "<>", ">|"],
        )

    def test_control_operators_project_as_explicit_records(self) -> None:
        source = "a && b || c | d ; e & (f) ;;\n"
        self.assertEqual(
            [token.text for token in project(source) if token.kind == OPERATOR],
            ["&&", "||", "|", ";", "&", "(", ")", ";;"],
        )


class RejectionTest(ProjectionSupportTest):
    def test_undecodable_bytes_and_nul_are_rejected_before_projection(self) -> None:
        with self.assertRaises(ShellLexicalError) as raised:
            project(b"echo \xff\n")
        self.assertIn("not valid UTF-8", str(raised.exception))
        self.assert_rejected("echo a\0b\n", "contain NUL")
        with self.assertRaises(ShellLexicalError):
            project(3)  # type: ignore[arg-type]

    def test_unterminated_quoting_and_expansion_are_rejected(self) -> None:
        self.assert_rejected("echo 'open\n", "single-quoted text is not terminated")
        self.assert_rejected('echo "open\n', "double-quoted text is not terminated")
        self.assert_rejected("echo ${name\n", "braced parameter expansion is not terminated")
        self.assert_rejected("echo $((1 + 2)\n", "arithmetic expansion is not terminated")
        self.assert_rejected("echo $(inner\n", "command substitution is not terminated")

    def test_ambiguous_or_unsupported_constructs_are_rejected(self) -> None:
        cases = {
            "echo `date`\n": "backquote command substitution",
            "echo $'x'\n": "dollar-single-quoted",
            'echo $"x"\n': "dollar-double-quoted",
            "cat <<<word\n": "here-string",
            "a &> out\n": "redirection of both streams",
            "a &>> out\n": "appending redirection of both streams",
            "a |& b\n": "pipeline of both streams",
            "case x in y) a ;& esac\n": "case fall-through operator",
            "case x in y) a ;;& esac\n": "case fall-through operator",
            "((count += 1))\n": "arithmetic command",
            "diff <(a) <(b)\n": "process substitution",
            "tee >(a)\n": "process substitution",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assert_rejected(source, expected)

    def test_ambiguous_expansion_interiors_are_rejected(self) -> None:
        cases = {
            "echo ${x:-`danger`}\n": "backquote command substitution",
            "echo $((`danger`))\n": "backquote command substitution",
            "echo ${x:-$'a'}\n": "dollar-single-quoted",
            "echo ${x:-<(a)}\n": "process substitution",
            "echo $(( <(a) ))\n": "process substitution",
            "echo \"${x-'}$(danger)'}\"\n": "quoted brace inside a parameter expansion",
            "echo $((a) )\n": "adjacent parentheses",
            "echo $(( 'a' ))\n": "quoting inside an arithmetic expansion",
            "echo $(( a \\b ))\n": "backslash in an arithmetic expansion",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assert_rejected(source, expected)

    def test_parameter_expansion_closes_at_the_first_unquoted_brace(self) -> None:
        (word,) = [token for token in project("echo ${x:-{a}}\n") if token.text.startswith("${")]
        self.assertEqual(
            [(segment.kind, segment.text) for segment in word.segments],
            [(PARAMETER_EXPANSION, "${x:-{a}"), (LITERAL, "}")],
        )
        source = "f() {\n  echo ${x:-{a}\n  danger\n}\nf\n"
        self.assertEqual(
            self.words(source),
            ["f", "{", "echo", "${x:-{a}", "danger", "}", "f"],
        )
        self.assert_complete_cover(source)

    def test_nested_arithmetic_parentheses_stay_accepted(self) -> None:
        (word,) = [token for token in project("echo $(( ((1 + 2)) * 3 ))\n") if token.text.startswith("$((")]
        self.assertEqual(word.segments[0].kind, ARITHMETIC_EXPANSION)

    def test_here_document_line_continuations_are_rejected_as_ambiguous(self) -> None:
        self.assert_rejected(
            "cat <<EO\\\nF\n$(danger)\nEOF\n",
            "delimiter must not use a line continuation",
        )
        self.assert_rejected(
            "cat <<EOF\nhello\nEO\\\nF\ndanger\nEOF\n",
            "delimiter formed by a line continuation",
        )
        self.assert_rejected(
            "cat <<EOF\na\\\nEOF\nafter $(danger)\n",
            "delimiter absorbed by a line continuation",
        )

    def test_unambiguous_here_document_continuations_stay_accepted(self) -> None:
        source = (
            "cat <<_M\n"
            "xdg-email --attach /tmp/logo.png \\\n"
            "          --subject 'Logo contest' \\\n"
            "          value\n"
            "_M\n"
            "echo after\n"
        )
        (body,) = self.here_documents(source)
        self.assertEqual(body.delimiter, "_M")
        self.assertIn("--subject 'Logo contest' \\\n", body.text)
        self.assertEqual(self.words(source)[-2:], ["echo", "after"])
        self.assert_complete_cover(source)

    def test_quoted_here_document_keeps_backslash_lines_literal(self) -> None:
        (body,) = self.here_documents("cat <<'EOF'\na\\\nEOF\n")
        self.assertEqual(body.text, "a\\\n")

    def test_dollar_before_a_quote_stays_literal_inside_quoting(self) -> None:
        self.assertEqual(project('"trailing$"').tokens[0].literal_value, "trailing$")
        (body,) = self.here_documents("cat <<EOF\ntrailing$\nEOF\n")
        self.assertEqual(body.text, "trailing$\n")

    def test_rejection_reports_an_exact_source_position(self) -> None:
        with self.assertRaises(ShellLexicalError) as raised:
            project("echo ok\necho `date`\n")
        self.assertEqual(raised.exception.position.line, 2)
        self.assertEqual(raised.exception.position.column, 6)


class SuppliedScriptTest(ProjectionSupportTest):
    def test_repository_shell_sources_project_without_execution(self) -> None:
        seen: set[str] = set()
        for relative in (
            "tests/copier-update.sh",
            "tests/copier-minimum.sh",
            "tests/lib-copier.sh",
            "tests/smoke.sh",
            "scripts/lint-project-workflow.sh",
        ):
            with self.subTest(relative=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                records = project(source.encode("utf-8"))
                self.assertGreater(len(records), 0)
                self.assert_complete_cover(source)
                seen.update(token.kind for token in records)
        self.assertLessEqual(
            {WORD, OPERATOR, NEWLINE, COMMENT, HEREDOC_BODY, IO_NUMBER}, seen
        )

    def test_every_tracked_shell_source_projects(self) -> None:
        tracked = sorted(ROOT.glob("**/*.sh"))
        checked = 0
        for path in tracked:
            if ".git" in path.parts or ".agent-artifacts" in path.parts:
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertGreater(len(project(path.read_bytes())), 0)
                checked += 1
        self.assertGreater(checked, 10)

    def test_module_never_executes_or_imports_the_supplied_script(self) -> None:
        text = (ROOT / "scripts/project_workflow/shell_lexical.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "importlib", "exec(", "eval("):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
