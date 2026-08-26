"""Bounded unique top-level function table over checked lexical records.

The table consumes only the lexical records emitted by the checked bounded
shell lexical projection. It never re-tokenizes supplied bytes and never
executes, sources, or imports the supplied script. Every alternate, hidden, or
dynamic declaration path is rejected instead of producing a partial table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from .shell_lexical import (
    COMMAND_SUBSTITUTION,
    COMMENT,
    CONTINUATION,
    LITERAL,
    HEREDOC_BODY,
    IO_NUMBER,
    LINE_CONTINUATION,
    NEWLINE,
    OPERATOR,
    WORD,
    LexicalProjection,
    Position,
    Segment,
    Token,
)


__all__ = [
    "FunctionDeclaration",
    "FunctionTable",
    "ShellFunctionError",
    "derive",
]


NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASSIGNMENT_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")

REDIRECTION_OPERATORS = frozenset({"<", ">", ">>", "<<", "<<-", "<&", ">&", "<>", ">|"})
SEPARATOR_OPERATORS = frozenset({";", ";;", "&", "&&", "||", "|", "\n"})
IGNORED_KINDS = frozenset({COMMENT, LINE_CONTINUATION, HEREDOC_BODY})

BLOCK_OPENERS = {
    "{": "}",
    "if": "fi",
    "while": "done",
    "until": "done",
    "for": "done",
    "case": "esac",
}
BLOCK_CLOSERS = frozenset({"}", "fi", "done", "esac"})
COMMAND_PREFIX_WORDS = frozenset({"then", "else", "elif", "do", "!"})
RESERVED_WORDS = (
    frozenset(BLOCK_OPENERS)
    | BLOCK_CLOSERS
    | COMMAND_PREFIX_WORDS
    | frozenset({"in", "esac"})
)
REJECTED_COMMAND_WORDS = {
    "eval": "dynamic `eval` command",
    "function": "`function` keyword declaration",
}
TRANSPARENT_COMMAND_PREFIXES = frozenset(
    {"command", "builtin", "time", "exec", "env", "nohup"}
)
LIST_CONTINUATION_OPERATORS = frozenset({"|", "&&", "||"})
DECLARATION_TERMINATORS = frozenset({";", "&&", "||", "\n"})


def _assignment_prefix(token: Token) -> str:
    """Return the leading text that can carry an assignment `=` in one word.

    bash, `bash --posix`, dash, and busybox ash agree that any quoting or
    escaping in the name portion makes the word a command word rather than an
    assignment, while a line continuation is removed before tokenization and
    leaves the assignment intact.
    """

    parts: list[str] = []
    for segment in token.segments:
        if segment.kind == CONTINUATION:
            continue
        if segment.kind != LITERAL:
            break
        parts.append(segment.value)
    return "".join(parts)


class ShellFunctionError(ValueError):
    """Raised when checked lexical records leave the accepted function subset."""

    def __init__(self, message: str, position: Position | None = None) -> None:
        self.position = position
        if position is None:
            super().__init__(message)
        else:
            super().__init__(f"line {position.line} column {position.column}: {message}")


@dataclass(frozen=True)
class FunctionDeclaration:
    """One accepted unique top-level function declaration."""

    name: str
    name_token: Token
    open_brace: Token
    close_brace: Token
    body: tuple[Token, ...]

    @property
    def start(self) -> Position:
        return self.name_token.start

    @property
    def end(self) -> Position:
        return self.close_brace.end


@dataclass(frozen=True)
class FunctionTable:
    """The unique top-level function declaration table of one supplied script."""

    declarations: tuple[FunctionDeclaration, ...]
    top_level: tuple[Token, ...]
    dynamic_commands: tuple[Token, ...] = ()
    """Command-position words whose dispatch target is not a literal name.

    A dynamic command word cannot be resolved without executing the script, so
    it is reported rather than silently trusted. A consumer that requires a
    fully resolved dispatch must treat a non-empty tuple as unresolved.
    """

    @property
    def names(self) -> tuple[str, ...]:
        """Return every declared function name in declaration order."""

        return tuple(declaration.name for declaration in self.declarations)

    @property
    def is_fully_resolved(self) -> bool:
        """Return whether every command dispatch in the script is a literal name.

        A consumer that requires the table to describe the whole script must
        assert this property; a false result means at least one command word is
        only resolvable by executing the script.
        """

        return not self.dynamic_commands

    def get(self, name: str) -> FunctionDeclaration | None:
        """Return the declaration for a name, or None when it is undeclared."""

        for declaration in self.declarations:
            if declaration.name == name:
                return declaration
        return None

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.get(name) is not None

    def __getitem__(self, name: str) -> FunctionDeclaration:
        declaration = self.get(name)
        if declaration is None:
            raise KeyError(name)
        return declaration

    def __iter__(self) -> Iterator[FunctionDeclaration]:
        return iter(self.declarations)

    def __len__(self) -> int:
        return len(self.declarations)


def derive(records: LexicalProjection) -> FunctionTable:
    """Derive the unique top-level function table from checked lexical records."""

    if not isinstance(records, LexicalProjection):
        raise ShellFunctionError("checked lexical records are required")
    walker = _Walker(records.tokens, top_level=True)
    walker.run()
    dynamic: list[Token] = list(walker.dynamic_commands)
    for region in _nested_regions(records.tokens):
        nested = _Walker(region, top_level=False)
        nested.run()
        dynamic.extend(nested.dynamic_commands)
    return FunctionTable(
        declarations=tuple(walker.declarations),
        top_level=tuple(walker.top_level_tokens),
        dynamic_commands=tuple(dynamic),
    )


def _nested_regions(tokens: tuple[Token, ...]) -> Iterator[tuple[Token, ...]]:
    for token in tokens:
        yield from _segment_regions(token.segments)


def _segment_regions(segments: tuple[Segment, ...]) -> Iterator[tuple[Token, ...]]:
    for segment in segments:
        if segment.kind == COMMAND_SUBSTITUTION:
            yield segment.tokens
            yield from _nested_regions(segment.tokens)
        yield from _segment_regions(segment.segments)


class _Walker:
    """Single pass over one record sequence at a fixed nesting level."""

    def __init__(self, tokens: tuple[Token, ...], *, top_level: bool) -> None:
        self.tokens = tokens
        self.top_level = top_level
        self.index = 0
        self.blocks: list[str] = []
        self.expect_command = True
        self.declaration_allowed = True
        self.skip_redirection_target = False
        self.declarations: list[FunctionDeclaration] = []
        self.declared: dict[str, FunctionDeclaration] = {}
        self.top_level_tokens: list[Token] = []
        self.dynamic_commands: list[Token] = []
        self.list_continuation = False
        self.pending_declaration: Token | None = None
        self.pending_depth = 0
        self.case_arm: list[bool] = []
        self.function_depth = 0

    def fail(self, message: str, token: Token | None) -> ShellFunctionError:
        return ShellFunctionError(message, token.start if token is not None else None)

    def significant(self, start: int, *, skip_newlines: bool = False) -> int | None:
        cursor = start
        while cursor < len(self.tokens):
            kind = self.tokens[cursor].kind
            if kind in IGNORED_KINDS or (skip_newlines and kind == NEWLINE):
                cursor += 1
                continue
            return cursor
        return None

    def in_case_pattern(self) -> bool:
        return bool(self.case_arm) and self.case_arm[-1] and self.blocks[-1] == "esac"

    def run(self) -> None:
        while self.index < len(self.tokens):
            token = self.tokens[self.index]
            if token.kind in IGNORED_KINDS:
                self.index += 1
                continue
            if token.kind == NEWLINE:
                if not self.in_case_pattern():
                    self.expect_command = True
                    self.declaration_allowed = not self.list_continuation
                    if not self.list_continuation:
                        self.clear_pending_declaration()
                self.skip_redirection_target = False
                self.index += 1
                continue
            if token.kind == IO_NUMBER:
                self.index += 1
                continue
            if token.kind == OPERATOR:
                self.handle_operator(token)
                continue
            self.handle_word(token)
        if self.blocks:
            raise self.fail(
                f"unterminated `{self.blocks[-1]}` block",
                self.tokens[-1] if self.tokens else None,
            )

    def handle_operator(self, token: Token) -> None:
        text = token.text
        self.list_continuation = text in LIST_CONTINUATION_OPERATORS
        if text == "&" and self.pending_declaration is not None:
            if len(self.blocks) == self.pending_depth:
                raise self.fail(
                    "function declaration is not a complete top-level command",
                    self.pending_declaration,
                )
        if text in (";", ";;"):
            self.clear_pending_declaration()
        if self.in_case_pattern():
            if text in ("(", "|"):
                self.index += 1
                return
            if text == ")":
                self.case_arm[-1] = False
                self.expect_command = True
                self.declaration_allowed = False
                self.index += 1
                return
            raise self.fail(f"unsupported case pattern operator `{text}`", token)
        if text in SEPARATOR_OPERATORS and text.startswith(";;") and self.blocks and self.blocks[-1] == "esac":
            self.case_arm[-1] = True
            self.expect_command = False
            self.skip_redirection_target = False
            self.index += 1
            return
        if text in REDIRECTION_OPERATORS:
            self.skip_redirection_target = True
            self.index += 1
            return
        if text in SEPARATOR_OPERATORS:
            self.expect_command = True
            self.declaration_allowed = text not in LIST_CONTINUATION_OPERATORS
            self.skip_redirection_target = False
            self.index += 1
            return
        if text == "(":
            self.blocks.append(")")
            self.expect_command = True
            self.declaration_allowed = False
            self.index += 1
            return
        if text == ")":
            if self.blocks and self.blocks[-1] == ")":
                self.blocks.pop()
            elif "esac" not in self.blocks:
                raise self.fail("unbalanced closing parenthesis", token)
            self.expect_command = False
            self.index += 1
            return
        raise self.fail(f"unsupported operator `{text}`", token)

    def handle_word(self, token: Token) -> None:
        self.list_continuation = False
        if self.skip_redirection_target:
            self.skip_redirection_target = False
            self.index += 1
            return
        value = token.literal_value
        if self.in_case_pattern():
            if value == "esac":
                self.close_block(token, "esac")
                self.case_arm.pop()
                self.expect_command = False
            self.index += 1
            return
        if not self.expect_command:
            if (
                value == "in"
                and self.case_arm
                and not self.case_arm[-1]
                and self.blocks
                and self.blocks[-1] == "esac"
            ):
                self.case_arm[-1] = True
            self.index += 1
            return
        if value is not None and value in REJECTED_COMMAND_WORDS:
            raise self.fail(f"unsupported {REJECTED_COMMAND_WORDS[value]}", token)
        if (
            value is not None
            and value in TRANSPARENT_COMMAND_PREFIXES
            and not self.is_declaration_start()
        ):
            self.index += 1
            self.skip_prefix_arguments()
            return
        if value in BLOCK_CLOSERS:
            self.close_block(token, value)
            if value == "esac":
                self.case_arm.pop()
            self.index += 1
            self.expect_command = False
            return
        if value in BLOCK_OPENERS:
            self.blocks.append(BLOCK_OPENERS[value])
            if value == "case":
                self.case_arm.append(False)
                self.expect_command = False
            else:
                self.expect_command = True
            self.declaration_allowed = False
            self.index += 1
            return
        if value in COMMAND_PREFIX_WORDS:
            self.index += 1
            self.expect_command = True
            self.declaration_allowed = False
            return
        if self.is_declaration_start():
            self.accept_declaration(token, value)
            return
        if ASSIGNMENT_PATTERN.match(_assignment_prefix(token)):
            self.index += 1
            return
        if value is None:
            self.dynamic_commands.append(token)
        if self.top_level and not self.blocks and not self.function_depth:
            self.top_level_tokens.append(token)
        self.index += 1
        self.expect_command = False

    def skip_prefix_arguments(self) -> None:
        """Keep command position across a transparent prefix such as `command`.

        Only `command`, `builtin`, and `time` can actually run the `eval`
        builtin in the current shell. `exec`, `env`, and `nohup` are included
        as conservative over-rejection because they cost nothing and remove a
        whole class of reader doubt.
        """

        while True:
            cursor = self.significant(self.index)
            if cursor is None:
                return
            candidate = self.tokens[cursor]
            if candidate.kind != WORD:
                return
            value = candidate.literal_value
            if value is None:
                return
            if not value.startswith("-") and ASSIGNMENT_PATTERN.match(value) is None:
                return
            self.index = cursor + 1

    def close_block(self, token: Token, value: str | None) -> None:
        if not self.blocks or self.blocks[-1] != value:
            raise self.fail(f"unexpected `{value}`", token)
        self.blocks.pop()

    def is_declaration_start(self) -> bool:
        opener = self.significant(self.index + 1)
        if opener is None:
            return False
        candidate = self.tokens[opener]
        return candidate.kind == OPERATOR and candidate.text == "("

    def accept_declaration(self, token: Token, value: str | None) -> None:
        opener = self.significant(self.index + 1)
        assert opener is not None
        closer = self.significant(opener + 1)
        if closer is None or self.tokens[closer].text != ")":
            raise self.fail(
                "word followed by an open parenthesis is not a function declaration",
                token,
            )
        if value is None or NAME_PATTERN.fullmatch(value) is None:
            raise self.fail("function name must be an exact literal name", token)
        if value in RESERVED_WORDS:
            raise self.fail("function name must not be a reserved word", token)
        if not self.top_level or self.blocks or self.function_depth:
            raise self.fail("function declaration is not at the top level", token)
        if not self.declaration_allowed:
            raise self.fail(
                "function declaration is not a complete top-level command", token
            )
        body_start = self.significant(closer + 1, skip_newlines=True)
        if body_start is None or self.tokens[body_start].literal_value != "{":
            raise self.fail("function body must be a brace group", token)
        if value in self.declared:
            raise self.fail(f"duplicate function declaration `{value}`", token)
        open_brace = self.tokens[body_start]
        close_index = self.consume_function_body(body_start)
        close_brace = self.tokens[close_index]
        self.reject_subshell_termination(close_index)
        declaration = FunctionDeclaration(
            name=value,
            name_token=token,
            open_brace=open_brace,
            close_brace=close_brace,
            body=tuple(self.tokens[body_start + 1:close_index]),
        )
        self.declarations.append(declaration)
        self.declared[value] = declaration
        self.pending_declaration = token
        self.pending_depth = len(self.blocks)
        self.index = close_index + 1
        self.expect_command = False

    def clear_pending_declaration(self) -> None:
        """Release a declaration once its and-or list ends in the current shell."""

        if self.pending_declaration is not None and len(self.blocks) == self.pending_depth:
            self.pending_declaration = None

    def reject_subshell_termination(self, close_index: int) -> None:
        """Reject a declaration a real shell would evaluate in a subshell."""

        cursor = self.significant(close_index + 1)
        while cursor is not None:
            follower = self.tokens[cursor]
            if follower.kind == IO_NUMBER:
                cursor = self.significant(cursor + 1)
                continue
            if follower.kind == OPERATOR and follower.text in REDIRECTION_OPERATORS:
                target = self.significant(cursor + 1)
                cursor = None if target is None else self.significant(target + 1)
                continue
            if follower.kind == NEWLINE or (
                follower.kind == OPERATOR and follower.text in DECLARATION_TERMINATORS
            ):
                return
            raise self.fail(
                "function declaration is not a complete top-level command", follower
            )

    def consume_function_body(self, body_start: int) -> int:
        saved_blocks = self.blocks
        saved_expect = self.expect_command
        self.blocks = []
        self.expect_command = True
        self.function_depth += 1
        self.index = body_start + 1
        try:
            while self.index < len(self.tokens):
                token = self.tokens[self.index]
                if (
                    not self.blocks
                    and self.expect_command
                    and token.kind == WORD
                    and token.literal_value == "}"
                ):
                    return self.index
                if token.kind in IGNORED_KINDS:
                    self.index += 1
                    continue
                if token.kind == NEWLINE:
                    self.expect_command = True
                    self.skip_redirection_target = False
                    self.index += 1
                    continue
                if token.kind == IO_NUMBER:
                    self.index += 1
                    continue
                if token.kind == OPERATOR:
                    self.handle_operator(token)
                    continue
                self.handle_word(token)
            raise self.fail(
                "function body is not terminated",
                self.tokens[body_start],
            )
        finally:
            self.function_depth -= 1
            self.blocks = saved_blocks
            self.expect_command = saved_expect
