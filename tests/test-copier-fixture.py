#!/usr/bin/env python3
"""Tests for the bounded Copier fixture shell structure parser."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/project_workflow/copier_fixture.py"
SPEC = importlib.util.spec_from_file_location("copier_fixture", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Copier fixture parser")
copier_fixture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = copier_fixture
SPEC.loader.exec_module(copier_fixture)


POSITIVE_FIXTURE = b"""#!/bin/sh
set -eu

prepare() {
  printf '%s\\n' prepare
}

release() {
  while poll; do
    inspect
  done
  printf '%s\\n' release
}

prepare
release
printf '%s\\n' complete
"""


class ShellStructureParserTests(unittest.TestCase):
    def parse(self, source: str | bytes):
        return copier_fixture.parse_shell_structure(source)

    def assert_rejected(self, source: str | bytes, message: str) -> None:
        with self.assertRaisesRegex(copier_fixture.ShellStructureError, message):
            self.parse(source)

    def test_extracts_unique_functions_and_reachable_top_level_sequence(self) -> None:
        structure = self.parse(POSITIVE_FIXTURE)

        self.assertEqual(tuple(structure.functions), ("prepare", "release"))
        self.assertEqual(
            [command.text for command in structure.top_level.reachable_commands],
            ["set -eu", "prepare", "release", "printf '%s\\n' complete"],
        )
        self.assertEqual(
            [command.text for command in structure.functions["release"].body.commands],
            ["poll", "inspect", "printf '%s\\n' release"],
        )
        self.assertFalse(
            structure.functions["release"].body.commands[1]
            .is_unconditionally_reachable
        )
        structure.top_level.require_reachable_sequence(
            (r"^prepare$", r"^release$", r"complete$")
        )

    def test_ignores_structure_like_text_in_heredocs_quotes_and_comments(self) -> None:
        structure = self.parse(
            """cat <<'PAYLOAD'
fake() {
fi
PAYLOAD
printf '%s' 'other() {'
# exit 0
finish
"""
        )

        self.assertEqual(tuple(structure.functions), ())
        self.assertEqual(
            [command.text for command in structure.top_level.reachable_commands],
            ["cat <<'PAYLOAD'", "printf '%s' 'other() {'", "finish"],
        )

    def test_does_not_treat_quoted_heredoc_text_as_an_operator(self) -> None:
        self.assert_rejected(
            """work() {
  printf first
}
printf '%s\\n' '<<true'
work() {
  printf second
}
true
work
""",
            "duplicate function definition",
        )

    def test_does_not_treat_commented_or_truncated_heredocs_as_structure(self) -> None:
        self.assert_rejected(
            """work() {
  printf first
}
printf PREPARE;# <<END
work() {
  printf second
}
END
work
""",
            "duplicate function definition",
        )
        self.assert_rejected(
            """work() {
  printf first
}
cat <<END-X
payload
END
work() {
  printf hidden
}
END-X
work() {
  printf second
}
work
""",
            "duplicate function definition",
        )

    def test_rejects_duplicate_function_definitions(self) -> None:
        self.assert_rejected(
            "work() {\n  :\n}\nwork() {\n  :\n}\nwork\n",
            "duplicate function definition",
        )

    def test_rejects_nested_function_definitions(self) -> None:
        self.assert_rejected(
            "outer() {\n  inner() {\n    :\n  }\n}\nouter\n",
            "nested function definition",
        )

    def test_rejects_duplicate_split_function_definitions(self) -> None:
        self.assert_rejected(
            """work() {
  printf first
}
work()
{
  printf second
}
work
""",
            "duplicate function definition",
        )

    def test_rejects_unmatched_and_unterminated_blocks(self) -> None:
        cases = (
            ("fi\nfinish\n", "unmatched if terminator"),
            ("work() {\n  if ready; then\n    finish\n}\nwork\n", "crosses if block"),
            ("if ready; then\n  finish\n", "unterminated 'if' block"),
        )
        for source, message in cases:
            with self.subTest(message=message):
                self.assert_rejected(source, message)

    def test_rejects_early_top_level_termination(self) -> None:
        self.assert_rejected(
            "prepare\nexit 0\nrelease\n",
            "follows control transfer",
        )

    def test_rejects_alternate_top_level_control_transfer(self) -> None:
        self.assert_rejected(
            "prepare\nverify || exec fallback\nrelease\n",
            "follows control transfer",
        )

    def test_rejects_assignment_prefixed_and_continued_control_transfers(self) -> None:
        cases = (
            ("prepare\nX=1 exit 17\nrelease\n", "assignment"),
            ("prepare\nex\\\nit 17\nrelease\n", "continuation"),
        )
        for source, label in cases:
            with self.subTest(label=label):
                self.assert_rejected(source, "follows control transfer")

    def test_rejects_redirection_prefixed_control_transfer(self) -> None:
        self.assert_rejected(
            "prepare\n>/dev/null exit 17\nrelease\n",
            "follows control transfer",
        )

    def test_comment_backslash_does_not_hide_a_later_control_transfer(self) -> None:
        self.assert_rejected(
            "prepare\n# comment \\\nexit 17\nrelease\n",
            "follows control transfer",
        )

    def test_rejects_early_function_termination(self) -> None:
        self.assert_rejected(
            "work() {\n  prepare\n  return 0\n  release\n}\nwork\n",
            "follows control transfer",
        )

    def test_reachable_sequence_rejects_conditional_enclosure(self) -> None:
        structure = self.parse(
            "prepare\nif enabled; then\n  release\nfi\nfinish\n"
        )

        with self.assertRaisesRegex(
            copier_fixture.ShellStructureError,
            "enclosed by skippable control flow",
        ):
            structure.top_level.require_reachable_sequence(
                (r"^prepare$", r"^release$", r"^finish$")
            )

    def test_rejects_control_transfer_in_an_if_condition(self) -> None:
        self.assert_rejected(
            "prepare\nif exit 17; then\n  :\nfi\nrelease\n",
            "follows control transfer",
        )

    def test_reachable_sequence_rejects_loop_enclosure(self) -> None:
        structure = self.parse(
            "prepare\nwhile pending; do\n  release\ndone\nfinish\n"
        )

        with self.assertRaisesRegex(
            copier_fixture.ShellStructureError,
            "enclosed by skippable control flow",
        ):
            structure.top_level.require_reachable_sequence(
                (r"^prepare$", r"^release$", r"^finish$")
            )

    def test_reachable_sequence_rejects_and_or_enclosure(self) -> None:
        structure = self.parse("prepare\nfalse && release\nfinish\n")

        with self.assertRaisesRegex(
            copier_fixture.ShellStructureError,
            "enclosed by skippable control flow",
        ):
            structure.top_level.require_reachable_sequence(
                (r"^prepare$", r"^release$", r"^finish$")
            )

    def test_reachable_sequence_rejects_disconnected_branch_bodies(self) -> None:
        structure = self.parse(
            "prepare\nif enabled; then\n  release-a\nelse\n  release-b\nfi\nfinish\n"
        )

        with self.assertRaisesRegex(
            copier_fixture.ShellStructureError,
            "enclosed by skippable control flow",
        ):
            structure.top_level.require_reachable_sequence(
                (r"^prepare$", r"^release-a$", r"^finish$")
            )

    def test_reachable_sequence_rejects_missing_duplicate_and_reordered_commands(
        self,
    ) -> None:
        structure = self.parse("prepare\nrelease\nrelease\nfinish\n")
        cases = (
            ((r"^missing$",), "required command is missing"),
            ((r"^release$",), "required command is not unique"),
            ((r"^finish$", r"^prepare$"), "required command is out of order"),
        )
        for patterns, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    copier_fixture.ShellStructureError,
                    message,
                ):
                    structure.top_level.require_reachable_sequence(patterns)

    def test_rejects_invalid_source_bytes_and_unterminated_heredoc(self) -> None:
        cases = (
            (b"\xff", "not valid UTF-8"),
            (b"finish\0\n", "NUL byte"),
            ("cat <<EOF\npayload\n", "unterminated here-document"),
        )
        for source, message in cases:
            with self.subTest(message=message):
                self.assert_rejected(source, message)

    def test_rejects_invalid_branch_tokens_and_duplicate_else(self) -> None:
        cases = (
            ("then\nfinish\n", "unmatched then"),
            ("then printf BAD\nfinish\n", "unsupported reserved-word clause"),
            ("do\nfinish\n", "unmatched do"),
            (";;\nfinish\n", "unmatched case terminator"),
            (
                "if ready; then\n  first\nelse\n  second\nelse\n  third\nfi\nfinish\n",
                "invalid else",
            ),
        )
        for source, message in cases:
            with self.subTest(message=message):
                self.assert_rejected(source, message)

    def test_rejects_piped_function_definition(self) -> None:
        self.assert_rejected(
            "work() {\n  printf safe\n} | cat\nwork\n",
            "function definition is piped",
        )

    def test_keeps_group_pipeline_tail_in_the_top_level_sequence(self) -> None:
        structure = self.parse("{\n  printf payload\n} | consume\nfinish\n")

        self.assertEqual(
            [command.text for command in structure.top_level.reachable_commands],
            ["printf payload", "consume", "finish"],
        )


if __name__ == "__main__":
    unittest.main()
