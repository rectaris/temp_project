#!/usr/bin/env python3
"""Bounded Copier fixture operation contract over checked shell projections.

The validator answers one question about supplied shell bytes: does the
Copier transition fixture still perform every bounded operation the accepted
runtime contract requires, in the required order, on a path the shell can
reach?

It consumes the checked bounded lexical projection, the checked bounded
top-level function table, and the checked bounded reachable command graph. It
never re-tokenizes supplied bytes, never restates the structural rules those
projections own, and never executes, sources, or imports the supplied script.
A construct the checked projections reject is reported as a `structure`
finding instead of being validated partially, because a partially projected
script cannot prove any operation contract.

The contract has two layers:

- Copier operation rules apply to every supplied fixture. They require unique
  version commits, exactly one inventory-driven copy and staging region, and
  no direct invocation of the migration snapshot script or the `copier`
  binary. These rules describe operations the fixture already owns, so they
  hold for a fixture that carries no migration transition region.
- Transition rules apply only when the supplied fixture writes a bounded
  migration transition, which is anchored on the transition event vocabulary
  (ready, release, pending, consumed, guardian) or on an asynchronous child.
  The anchor is deliberately not any single operation the transition rules
  require, so deleting a required operation reports that operation as missing
  instead of silently disabling the rules that require it. They require the
  ready and release ordering, both bounded polls, three release paths, child
  termination and reap, PID clearing, the pending and consumed order, a
  positive guardian PID, and guardian cleanup. A fixture without that anchor
  runs no transition, so the transition rules report nothing rather than
  inventing a requirement.

Both layers reject a missing, reordered, duplicated, unreachable, or
alternate-path operation. Reachability comes from the checked graph, so an
operation that a shell can never run never satisfies a requirement.

Two boundaries are explicit. A command whose command word the checked graph
cannot resolve proves nothing about what it runs, so a Copier update reached
through such a dispatch is rejected instead of being read as absent. A file
the fixture sources is outside the supplied bytes, so an operation moved into
a sourced file is reported as missing by the rule that requires it: the
contract states what the supplied bytes prove, and it never treats an unread
region as evidence that a required operation exists.
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


if __package__:
    from . import shell_execution, shell_functions, shell_lexical
    from .shell_functions import ShellFunctionError
    # The assignment split is contract relevant: a word whose `=` is quoted is
    # a command word, not an assignment. Reuse the checked helper instead of
    # restating the rule, exactly as the checked execution graph does, so the
    # modules can never disagree about which word carries an assignment.
    from .shell_functions import _assignment_prefix
    from .shell_functions import RESERVED_WORDS
    from .shell_lexical import NEWLINE, OPERATOR, Position, ShellLexicalError, Token, WORD
    from .shell_execution import (
        ASYNC_LIST,
        CASE_ARM,
        CONDITION,
        CONDITIONAL_ENCLOSURES,
        CONDITIONAL_OPERAND,
        EFFECT_BREAK,
        EFFECT_CONTINUE,
        EFFECT_EXIT,
        EFFECT_RETURN,
        EFFECT_TRAP,
        ExecutionGraph,
        LOOP_BODY,
        Node,
        ShellExecutionError,
    )
else:  # pragma: no cover - exercised by the documented direct CLI contract
    _SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
    if str(_SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_ROOT))
    from project_workflow import shell_execution, shell_functions, shell_lexical
    from project_workflow.shell_functions import ShellFunctionError
    from project_workflow.shell_functions import _assignment_prefix
    from project_workflow.shell_functions import RESERVED_WORDS
    from project_workflow.shell_lexical import (
        NEWLINE,
        OPERATOR,
        Position,
        ShellLexicalError,
        Token,
        WORD,
    )
    from project_workflow.shell_execution import (
        ASYNC_LIST,
        CASE_ARM,
        CONDITION,
        CONDITIONAL_ENCLOSURES,
        CONDITIONAL_OPERAND,
        EFFECT_BREAK,
        EFFECT_CONTINUE,
        EFFECT_EXIT,
        EFFECT_RETURN,
        EFFECT_TRAP,
        ExecutionGraph,
        LOOP_BODY,
        Node,
        ShellExecutionError,
    )


__all__ = [
    "CopierFixtureError",
    "Finding",
    "RULES",
    "RULE_ALTERNATE_PATH",
    "RULE_UNRESOLVED_DISPATCH",
    "RULE_BOUNDED_POLL",
    "RULE_CHILD_PID",
    "RULE_CHILD_REAP",
    "RULE_DIRECT_INVOCATION",
    "RULE_GUARDIAN",
    "RULE_INVENTORY_REGION",
    "RULE_RELEASE_PATH",
    "RULE_STATE_ORDER",
    "RULE_STRUCTURE",
    "RULE_UPDATE_CHILD",
    "RULE_VERSION_COMMIT",
    "check",
    "main",
    "validate",
]


RULE_STRUCTURE = "structure"
RULE_VERSION_COMMIT = "version_commit"
RULE_INVENTORY_REGION = "inventory_region"
RULE_DIRECT_INVOCATION = "direct_invocation"
RULE_UPDATE_CHILD = "update_child"
RULE_CHILD_PID = "child_pid"
RULE_BOUNDED_POLL = "bounded_poll"
RULE_RELEASE_PATH = "release_path"
RULE_STATE_ORDER = "state_order"
RULE_CHILD_REAP = "child_reap"
RULE_GUARDIAN = "guardian"
RULE_ALTERNATE_PATH = "alternate_path"
RULE_UNRESOLVED_DISPATCH = "unresolved_dispatch"

RULES = (
    RULE_STRUCTURE,
    RULE_VERSION_COMMIT,
    RULE_INVENTORY_REGION,
    RULE_DIRECT_INVOCATION,
    RULE_UPDATE_CHILD,
    RULE_CHILD_PID,
    RULE_BOUNDED_POLL,
    RULE_RELEASE_PATH,
    RULE_STATE_ORDER,
    RULE_CHILD_REAP,
    RULE_GUARDIAN,
    RULE_ALTERNATE_PATH,
    RULE_UNRESOLVED_DISPATCH,
)

SNAPSHOT_MARKER = "snapshot-validation-witness-provenance"
UPDATE_WRAPPER_MARKER = "update-from-copier.sh"
COPIER_MARKER = "copier"
UPDATE_MARKER = "update"
READY_MARKER = "ready"
RELEASE_MARKER = "release"
PENDING_MARKER = "pending"
CONSUMED_MARKER = "consumed"
GUARDIAN_MARKER = "guardian"
PID_MARKER = "pid"

VERSION_TAG_PATTERN = re.compile(r"^v\d+(?:\.\d+)*$")
ASSIGNMENT_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")
EXPANSION_PATTERN = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
)
# One command references few names, and each name holds few written values,
# so the combination count is small in practice. The bound keeps supplied
# bytes from making the expansion work grow without limit.
MAX_EXPANSIONS = 64


# The grammar this checker settles a written word from. A word is settled
# only when every character of it is written in one of these forms, so a
# spelling this checker does not enumerate is unproven by construction
# rather than read as the literal text it happens to be written with.
WORD_LITERAL_PATTERN = re.compile(r"[A-Za-z0-9._+,:@%/-]")


BRACED_NAME_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


PLAIN_NAME_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


SUBSTITUTION_START = "$("


SUBSTITUTION_END = ")"


ARITHMETIC_START = "$(("


BACKQUOTE_MARK = "`"


QUOTE_MARKS = ('"', "'")


# A quoted span may carry the separators that end a command, so it is removed
# before the text between an assignment and a command word is read.
QUOTED_SPAN_PATTERN = re.compile(r"\"[^\"]*\"|\'[^\']*\'")


# The one command list this checker reads as naming an absolute directory. A
# shell writes an absolute path for ``pwd`` and for a directory change that
# succeeds before it, and no other list is modelled, so every other
# substitution names a directory this checker cannot anchor.
ABSOLUTE_SUBSTITUTION_PATTERN = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*[ \t]+)*"
    r"(?:cd[ \t][^&|;]*&&[ \t]*)?"
    r"(?:command[ \t]+)?pwd(?:[ \t]+-P)?[ \t]*$"
)


ABSOLUTE_SHELL_COMMAND = "pwd"


OPAQUE_MARK = "$"


ABSOLUTE_OPAQUE_MARK = "$!"


# A fixture may assign a name from its own value, so each name is settled at
# the offset its own assignment is written and the settled texts are bounded.
SETTLED_TEXTS = 32


SETTLED_SEGMENTS = 64
# --- the modelled binding surfaces ------------------------------------------
#
# A word is settled from what a fixture writes above it, so every place a
# fixture may give a name a value has to be read before any word is. The
# surfaces below are read from the lexical tokens the fixture is parsed into,
# never from its raw text, because a quoted span, a command substitution, or a
# continued line hides a separator from any pattern matched over raw text. A
# surface written in a form this checker does not enumerate leaves the names it
# is written with unsettled rather than leaving them settled.
NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
QUOTED_SEGMENTS = ("single_quoted", "double_quoted")
LITERAL_SEGMENT = "literal"
# A command list ends at one of these, so the words of one command are the
# words written between two of them.
COMMAND_BREAKS = frozenset({";", "&", "&&", "|", "||", ";;", "(", ")"})
CONTINUATION_KIND = "line_continuation"
LINE_CONTINUATION = "\\\n"
HEREDOC_KIND = "heredoc_body"
# The words a shell reads as syntax rather than as a command name.
LOOP_KEYWORD = "for"
RESERVED_WORDS = frozenset(
    {
        "if",
        "then",
        "elif",
        "else",
        "fi",
        "for",
        "while",
        "until",
        "do",
        "done",
        "case",
        "esac",
        "in",
        "{",
        "}",
        "!",
    }
)
# The operators that detach what is written from the shell that writes it.
SUBSHELL_OPEN = "("
SUBSHELL_CLOSE = ")"
GROUP_OPEN = "{"
GROUP_CLOSE = "}"
DETACHING_BREAKS = frozenset({"&", "|", "||"})
# --- the accepted fixture constructs ----------------------------------------
#
# Every stopped attempt at this model failed the same way: a construct the
# reader did not enumerate was read as if it did nothing, so the names written
# around it stayed settled. A reader cannot list what it failed to look at, so
# the constructs themselves are enumerated here instead. A fixture that writes
# anything outside this enumeration is not read at all, and every name written
# in it is reported unsettled, because a checker that does not know what a
# construct does cannot know which names it leaves alone either.
ACCEPTED_TOKEN_KINDS = frozenset(
    {
        "word",
        "operator",
        "newline",
        "comment",
        "io_number",
        "heredoc_body",
        "line_continuation",
    }
)
ACCEPTED_OPERATORS = frozenset(
    {
        ";",
        ";;",
        "&",
        "&&",
        "|",
        "||",
        "(",
        ")",
        "<",
        ">",
        ">>",
        "<<",
        "<<-",
        ">&",
        "<&",
        "<>",
        ">|",
    }
)
ACCEPTED_SEGMENT_KINDS = frozenset(
    {
        "literal",
        "escape",
        "single_quoted",
        "double_quoted",
        "parameter_expansion",
        "command_substitution",
        "arithmetic_expansion",
    }
)
# A brace written unquoted outside a group opens a construct this checker does
# not read, including the descriptor-variable redirection that binds the name
# written inside it and the brace expansion that writes several words.
BRACE_CHARACTERS = ("{", "}")
GROUP_WORDS = frozenset({"{", "}"})
# A command that gives a name a value this checker records no assignment for.
ASSIGNING_COMMANDS = frozenset(
    {
        "export",
        "readonly",
        "local",
        "declare",
        "typeset",
        "set",
        "read",
        "readarray",
        "mapfile",
        "getopts",
        "unset",
        "let",
        "select",
        "eval",
        "trap",
        "wait",
        "coproc",
        "source",
        ".",
    }
)
# A command whose operands are paths rather than names. A fixture that sources
# a path gives the sourced bytes the same authority as its own, which is the
# one boundary this checker accepts rather than reads, so an operand it cannot
# read here names a file rather than a variable.
PATH_OPERAND_COMMANDS = frozenset({"source", "."})
# A command whose bare operands name a running process rather than a variable.
# Such a command gives the writing shell a value only through the option that
# is written with the name, so a bare operand this checker cannot read is a
# process identifier rather than a name it never sees.
JOB_OPERAND_COMMANDS = frozenset({"wait"})
JOB_NAME_OPTION = "-p"
# A command that runs another command, so the command a fixture writes may be
# written behind one of these rather than first.
LAUNCHER_COMMANDS = frozenset(
    {
        "command",
        "builtin",
        "env",
        "exec",
        "nohup",
        "setsid",
        "stdbuf",
        "sudo",
        "time",
        "timeout",
        "xargs",
        "busybox",
    }
)
# A launcher that runs what it is given in its own process. Nothing it runs can
# give the shell that writes it a value, so a name written with one of these is
# read no further.
FORKING_LAUNCHERS = frozenset(
    {
        "env",
        "nohup",
        "setsid",
        "stdbuf",
        "sudo",
        "timeout",
        "xargs",
        "busybox",
    }
)
# A shell resolves a command word carrying a slash as a pathname, so such a word
# never names a builtin and never gives the shell that writes it a value.
PATH_SEPARATOR = "/"
NAMED_OPTION = "-v"
# An expansion a shell gives a value through rather than only reads through.
ASSIGNING_EXPANSION = "="
ARITHMETIC_SEGMENT = "arithmetic_expansion"
PARAMETER_SEGMENT = "parameter_expansion"
# A shell keeps these names itself and changes them where no assignment is
# written, so what one of them holds is never settled from written text.
MUTABLE_SHELL_NAMES = frozenset(
    {
        "PWD",
        "OLDPWD",
        "CDPATH",
        "IFS",
        "OPTIND",
        "OPTARG",
        "REPLY",
        "RANDOM",
        "SECONDS",
        "LINENO",
        "PPID",
        "SHLVL",
        "_",
        "DIRSTACK",
        "COPROC",
        "COPROC_PID",
    }
)
# No written path contains a null byte, so joining unresolved values with it
# keeps every value readable in one word without inventing a new one.
UNRESOLVED_JOINER = "\0"
ARITHMETIC_MARKER = "$(("
BOUND_EXIT_EFFECTS = frozenset(
    {EFFECT_EXIT, EFFECT_RETURN, EFFECT_BREAK, EFFECT_CONTINUE}
)
# `continue` restarts a loop instead of leaving it, so a poll that only
# continues still runs forever. The bound the contract asks for is the set of
# effects that leave the loop.
LOOP_EXIT_EFFECTS = BOUND_EXIT_EFFECTS - {EFFECT_CONTINUE}
LOOP_TERMINATOR = "done"
# Every compound command the contract needs an extent for, paired with the
# word written to close it.
COMPOUND_TERMINATORS = {
    "while": LOOP_TERMINATOR,
    "until": LOOP_TERMINATOR,
    "for": LOOP_TERMINATOR,
    "if": "fi",
    "case": "esac",
}
COMPOUND_CLOSERS = frozenset(COMPOUND_TERMINATORS.values())
BRANCH_KEYWORDS = frozenset({"if", "case"})
# A command runs on every turn of the list that holds it only when it is
# written after one of these records. Any other separator makes the command
# depend on what ran before it.
SEQUENCE_OPERATORS = frozenset({";", ";;"})
# A word written after one of these opens the command that follows it rather
# than being a command itself, so the command inherits the position it stands in.
COMMAND_PREFIX_WORDS = frozenset({"do", "then", "else", "{"})
SUBSHELL_OPEN = "("
SUBSHELL_CLOSE = ")"
# These operators put the element written before them in a subshell, so
# whatever it assigns never reaches the shell that reads the counter.
ISOLATING_OPERATORS = frozenset({"|", "&"})
CASE_KEYWORD = "case"
CASE_TERMINATOR = "esac"
CASE_SUBJECT_END = "in"
# An exit written under one of these enclosures is guarded by the command
# written immediately before it rather than by a named condition record.
PRECEDED_ENCLOSURES = frozenset({CONDITIONAL_OPERAND, CASE_ARM})

GIT_VALUE_OPTIONS = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
)
COPY_COMMANDS = frozenset({"cp", "install"})
REDIRECTIONS = frozenset(shell_lexical.REDIRECTION_OPERATORS)
WRITE_REDIRECTIONS = frozenset({">", ">>", ">|", ">&", "<>"})
COPIER_SUBCOMMANDS = frozenset({"copy", "recopy", "update"})
# An asynchronous list does not make the command it starts skippable.
STARTED_ANYWAY = frozenset({ASYNC_LIST})
INTERPRETER_PATTERN = re.compile(r"^(?:ba|da|k|z)?sh[0-9.]*$|^python[0-9.]*$")
COMMAND_PREFIXES = frozenset({"nice", "stdbuf", "timeout", "uv"})
POSITIONAL_PATTERN = re.compile(r"\$\{?[0-9@*]")
TAG_VALUE_OPTIONS = frozenset({"-F", "-m", "-u", "--file", "--local-user", "--message"})
TAG_VALUE_LETTERS = "Fmu"
LOOP_WORD_LIST = "for"
LOOP_KEYWORDS = frozenset({"while", "until", LOOP_WORD_LIST})
# A release path changes the release event itself. A command that only reads
# the event, such as a poll guard or a counter test, never releases the before
# stage, so only a mutating command can satisfy a release requirement.
# Only a command that changes the release path can satisfy a release
# requirement. A command that merely names or prints the path leaves the
# release event unperformed, so it satisfies a release rule only when it
# writes the release path through a redirection.
RELEASE_COMMANDS = frozenset({"cp", "install", "ln", "mv", "rm", "touch"})
# The transition rules describe the bounded migration transition, so they are
# anchored on the transition's own event vocabulary rather than on any single
# operation the rules require. Anchoring them on the asynchronous update child
# alone would let a fixture delete that child and lose every transition rule
# with it.
TRANSITION_MARKERS = (
    GUARDIAN_MARKER,
    READY_MARKER,
    RELEASE_MARKER,
    PENDING_MARKER,
    CONSUMED_MARKER,
)
TERMINATION_SIGNALS = ("term", "sigterm", "15")
FORCED_SIGNALS = ("kill", "sigkill", "9")


class CopierFixtureError(ValueError):
    """Raised when supplied bytes cannot be validated or break the contract."""


@dataclass(frozen=True)
class Finding:
    """One rejected Copier fixture operation with its exact source position."""

    rule: str
    message: str
    position: Position | None = None

    @property
    def sort_key(self) -> tuple[int, int, str]:
        offset = -1 if self.position is None else self.position.offset
        return (offset, RULES.index(self.rule), self.message)

    def __str__(self) -> str:
        if self.position is None:
            return f"{self.rule}: {self.message}"
        return (
            f"line {self.position.line} column {self.position.column}: "
            f"{self.rule}: {self.message}"
        )


@dataclass(frozen=True)
class _Operation:
    """One written command, with every projected occurrence folded together.

    A command inside a function body is projected once per reachable call
    site. The contract asks about the written operation, so the occurrences of
    one source position are folded: the operation is reachable when any
    occurrence is reachable, and it is conditional only when every occurrence
    can be skipped.
    """

    node: Node
    offset: int
    reachable: bool
    conditional: bool
    text: str
    redirect_targets: tuple[str, ...] = ()
    conditional_kinds: tuple[frozenset[str], ...] = ()

    def skippable(self, ignore: frozenset[str] = frozenset()) -> bool:
        """Report whether control can skip this operation.

        `ignore` drops enclosure kinds that do not make the operation itself
        skippable. An asynchronous command is enclosed in an asynchronous list
        because the commands after it do not wait for it, which says nothing
        about whether the command is started.
        """

        if not self.conditional_kinds:
            return self.conditional
        return all(bool(kinds - ignore) for kinds in self.conditional_kinds)

    @property
    def name(self) -> str | None:
        return self.node.name

    @property
    def position(self) -> Position | None:
        return self.node.position

    @property
    def asynchronous(self) -> bool:
        return self.node.asynchronous

    @property
    def effect(self) -> str | None:
        return self.node.effect

    @property
    def argument_values(self) -> tuple[str | None, ...]:
        return self.node.argument_values

    @property
    def loop_conditions(self) -> tuple[int, ...]:
        """Return the start offset of every loop whose condition holds this."""

        regions: list[int] = []
        for enclosure in self.node.enclosures:
            token = enclosure.token
            if token is None or enclosure.kind != CONDITION:
                continue
            if token.literal_value in LOOP_KEYWORDS:
                regions.append(token.start.offset)
        return tuple(regions)

    @property
    def loop_keywords(self) -> dict[int, str | None]:
        """Return the written keyword of every loop that encloses this."""

        keywords: dict[int, str | None] = {}
        for enclosure in self.node.enclosures:
            token = enclosure.token
            if token is None or enclosure.kind not in (LOOP_BODY, CONDITION):
                continue
            if token.literal_value in LOOP_KEYWORDS:
                keywords[token.start.offset] = token.literal_value
        return keywords

    @property
    def loop_regions(self) -> tuple[int, ...]:
        """Return the start offset of every loop that encloses this operation.

        A `while` loop encloses its condition and its body with the same loop
        record, so a `read` written in the condition belongs to the same
        region as the commands written in the body.
        """

        regions: list[int] = []
        for enclosure in self.node.enclosures:
            token = enclosure.token
            if token is None or enclosure.kind not in (LOOP_BODY, CONDITION):
                continue
            if token.literal_value in LOOP_KEYWORDS:
                regions.append(token.start.offset)
        return tuple(regions)


@dataclass(frozen=True)
class _Assignment:
    """One variable assignment written in command position."""

    name: str
    value: str
    token: Token

    @property
    def offset(self) -> int:
        return self.token.start.offset

    @property
    def is_empty(self) -> bool:
        """Report whether the assignment sets the empty value.

        `name=`, `name=""`, and `name=\'\'` are the same POSIX operation, so
        emptiness is read from the checked expansion-free word value instead
        of from the raw token text.
        """

        literal = self.token.literal_value
        return literal is not None and literal == f"{self.name}="


def _decode(source: str | bytes) -> str:
    if isinstance(source, (bytes, bytearray)):
        try:
            return bytes(source).decode("utf-8")
        except UnicodeDecodeError as error:
            raise CopierFixtureError(
                f"supplied bytes are not valid UTF-8 at offset {error.start}"
            ) from error
    if isinstance(source, str):
        return source
    raise CopierFixtureError("supplied source must be str or bytes")


def _node_text(
    index: dict[int, tuple[tuple[Token, ...], int]], node: Node
) -> tuple[str, tuple[str, ...]]:
    """Return one command's written text and its redirection targets.

    The text is built from the checked lexical records of the command itself:
    the command prefix, the command word, every argument, and every
    redirection operator and target. A comment, a here-document body, and any
    neighbouring command are excluded, so a marker written in a comment can
    never satisfy an operation requirement.
    """

    located = _locate(index, node)
    if located is None:
        parts = [] if node.token is None else [node.token.text]
        parts.extend(word.text for word in node.words)
        return " ".join(parts), ()
    span = _command_span(*located)
    targets: list[str] = []
    pending_target = False
    for token in span:
        if token.kind == shell_lexical.OPERATOR:
            pending_target = token.text in WRITE_REDIRECTIONS
            continue
        if pending_target and token.kind == shell_lexical.WORD:
            targets.append(token.text)
        pending_target = False
    return " ".join(token.text for token in span), tuple(targets)


def _token_index(records: shell_lexical.LexicalProjection) -> dict[int, tuple[tuple[Token, ...], int]]:
    """Index every projected record, including command-substitution records."""

    index: dict[int, tuple[tuple[Token, ...], int]] = {}
    regions = [records.tokens, *shell_lexical.executable_regions(records)]
    for region in regions:
        for position, token in enumerate(region):
            index.setdefault(token.start.offset, (region, position))
    return index


def _locate(
    index: dict[int, tuple[tuple[Token, ...], int]], node: Node
) -> tuple[tuple[Token, ...], int] | None:
    position = node.position
    if position is None:
        return None
    return index.get(position.offset)


def _command_span(region: tuple[Token, ...], start: int) -> tuple[Token, ...]:
    """Return the record span of the one command that starts at `start`."""

    first = start
    cursor = start - 1
    while cursor >= 0 and _is_command_record(region[cursor]):
        if region[cursor].kind != shell_lexical.LINE_CONTINUATION:
            first = cursor
        cursor -= 1
    last = start
    cursor = start + 1
    while cursor < len(region) and _is_command_record(region[cursor]):
        if region[cursor].kind != shell_lexical.LINE_CONTINUATION:
            last = cursor
        cursor += 1
    return tuple(
        token
        for token in region[first : last + 1]
        if token.kind != shell_lexical.LINE_CONTINUATION
    )


def _is_command_record(token: Token) -> bool:
    if token.kind in (shell_lexical.WORD, shell_lexical.IO_NUMBER):
        return True
    if token.kind == shell_lexical.LINE_CONTINUATION:
        return True
    return token.kind == shell_lexical.OPERATOR and token.text in REDIRECTIONS


def _fold_operations(
    records: shell_lexical.LexicalProjection, graph: ExecutionGraph
) -> tuple[_Operation, ...]:
    """Fold every projected occurrence of one written command into one record."""

    index = _token_index(records)
    grouped: dict[int, list[Node]] = {}
    for node in graph.commands:
        position = node.position
        if position is None:
            continue
        grouped.setdefault(position.offset, []).append(node)
    operations: list[_Operation] = []
    for offset in sorted(grouped):
        nodes = grouped[offset]
        text, targets = _node_text(index, nodes[0])
        operations.append(
            _Operation(
                node=nodes[0],
                offset=offset,
                reachable=any(node.reachable for node in nodes),
                conditional=all(node.is_conditional for node in nodes),
                text=text,
                redirect_targets=targets,
                conditional_kinds=tuple(
                    frozenset(
                        kind
                        for kind in node.enclosure_kinds
                        if kind in CONDITIONAL_ENCLOSURES
                    )
                    for node in nodes
                ),
            )
        )
    return tuple(operations)


def _command_positions(records: shell_lexical.LexicalProjection) -> frozenset[int]:
    """Return the offset of every word written where a command may start.

    Command position is decided from the checked record stream only: a word
    starts a command when the previous projected record is a newline or an
    operator. A reserved word written anywhere else is an ordinary argument.
    """

    offsets: list[int] = []
    opens = True
    for token in records.tokens:
        if token.kind != WORD:
            if token.kind in (NEWLINE, OPERATOR):
                opens = True
            continue
        if opens:
            offsets.append(token.start.offset)
        # Only a reserved word standing in command position opens the command
        # written after it. The same text written as an argument is a word.
        opens = opens and token.text in COMMAND_PREFIX_WORDS
    return frozenset(offsets)


def _unconditional_positions(
    records: shell_lexical.LexicalProjection,
) -> frozenset[int]:
    """Return the offset of every word written to run on every turn.

    Command position alone is not enough: the right operand of an and-or list
    runs only when the left operand decided so, a pipeline stage runs on the
    other side of a pipe, and a subshell keeps whatever it assigns to itself.
    Only a word written after a newline, a `;`, or the reserved word that
    opens a body runs unconditionally where it is written.
    """

    offsets: list[int] = []
    pending: int | None = None
    starts = True
    depth = 0
    for token in records.tokens:
        if token.kind == OPERATOR:
            if token.text in ISOLATING_OPERATORS:
                pending = None
            elif token.text == SUBSHELL_OPEN:
                depth += 1
            elif token.text == SUBSHELL_CLOSE and depth:
                depth -= 1
            if token.text in SEQUENCE_OPERATORS or token.text not in ISOLATING_OPERATORS:
                if pending is not None:
                    offsets.append(pending)
                    pending = None
            starts = token.text in SEQUENCE_OPERATORS
            continue
        if token.kind == NEWLINE:
            if pending is not None:
                offsets.append(pending)
                pending = None
            starts = True
            continue
        if token.kind != WORD:
            continue
        # A body opener keeps the position it stands in, so a command written
        # after `&& {` is still the right operand of the and-or list.
        if token.text in COMMAND_PREFIX_WORDS and starts:
            continue
        if starts and not depth:
            pending = token.start.offset
        starts = False
    if pending is not None:
        offsets.append(pending)
    return frozenset(offsets)


def _command_assignments(records: shell_lexical.LexicalProjection) -> tuple[_Assignment, ...]:
    """Return every assignment written where a command word may start.

    Command position is decided from the checked record stream only, by the
    same scan the extent derivation uses. The name split reuses the checked
    function-table helper, so a quoted or expanded `=` is never read as an
    assignment.
    """

    commands = _command_positions(records)
    assignments: list[_Assignment] = []
    for token in records.tokens:
        if token.kind != WORD or token.start.offset not in commands:
            continue
        prefix = _assignment_prefix(token)
        match = ASSIGNMENT_PATTERN.match(prefix)
        if match is None:
            continue
        name = match.group(1)
        assignments.append(
            _Assignment(name=name, value=token.text[len(name) + 1:], token=token)
        )
    return tuple(assignments)


def _word_letters(token: Token) -> tuple[tuple[str, bool], ...] | None:
    """Return every letter one word denotes, paired with whether it is quoted.

    A word is read letter by letter so that a quoted separator is never read as
    the separator itself. A word carrying an expansion denotes text this
    checker cannot read, so no letters are returned for it.
    """

    letters: list[tuple[str, bool]] = []
    for segment in token.segments:
        if segment.kind == LITERAL_SEGMENT:
            letters.extend((letter, False) for letter in segment.text)
        elif segment.kind == "escape":
            if segment.value is None:
                return None
            letters.extend((letter, True) for letter in segment.value)
        elif segment.kind == "single_quoted":
            if segment.value is None:
                return None
            letters.extend((letter, True) for letter in segment.value)
        elif segment.kind == "double_quoted":
            for inner in segment.segments:
                if inner.kind not in (LITERAL_SEGMENT, "escape"):
                    return None
                text = inner.text if inner.kind == LITERAL_SEGMENT else inner.value
                if text is None:
                    return None
                letters.extend((letter, True) for letter in text)
        else:
            return None
    return tuple(letters)


def _expansion_segments(
    segments: Sequence[shell_lexical.Segment],
) -> tuple[shell_lexical.Segment, ...]:
    """Return every expansion written in one word, including quoted ones.

    A double-quoted span still expands, so the segments written inside it are
    read as well. A command substitution runs in its own shell and gives no
    value to the shell that writes it, so what is written inside one is not
    read here.
    """

    found: list[shell_lexical.Segment] = []
    for segment in segments:
        if segment.kind in (ARITHMETIC_SEGMENT, PARAMETER_SEGMENT):
            found.append(segment)
        elif segment.kind == "double_quoted":
            found.extend(_expansion_segments(segment.segments))
    return tuple(found)


def _writes_a_path(token: Token) -> bool:
    """Report whether one command word certainly carries a slash.

    A shell resolves a command word containing a slash as a pathname and runs
    it in its own process, so such a word never names a builtin that could give
    the writing shell a value. Only the slashes written literally are read; a
    slash an expansion may produce is not one this checker knows about.
    """

    for segment in token.segments:
        if segment.kind == LITERAL_SEGMENT:
            if PATH_SEPARATOR in segment.text:
                return True
        elif segment.kind in ("escape", "single_quoted"):
            if segment.value is not None and PATH_SEPARATOR in segment.value:
                return True
        elif segment.kind == "double_quoted":
            for inner in segment.segments:
                if inner.kind == LITERAL_SEGMENT and PATH_SEPARATOR in inner.text:
                    return True
    return False


def _token_text(token: Token) -> str | None:
    """Return the one text a word denotes, or nothing when it denotes more."""

    letters = _word_letters(token)
    if letters is None:
        return None
    return "".join(letter for letter, _ in letters)


def _assignment_name(token: Token) -> str | None:
    """Return the name one word assigns, or nothing when it assigns none.

    A shell reads a word as an assignment when an unquoted `=` follows a name,
    so a quoted or expanded `=` never opens one. A word whose name part carries
    an expansion cannot open an assignment at all, because the text before the
    `=` would then not be a written name.
    """

    name: list[str] = []
    for segment in token.segments:
        if segment.kind == LITERAL_SEGMENT:
            head, marked, _ = segment.text.partition("=")
            name.append(head)
            if marked:
                written = "".join(name)
                return written if NAME_PATTERN.fullmatch(written) else None
            continue
        letters = _word_letters(
            Token(kind=WORD, text=segment.text, start=token.start, end=token.end, segments=(segment,))
        )
        if letters is None:
            return None
        name.extend(letter for letter, _ in letters)
    return None


@dataclass(frozen=True)
class _CommandRun:
    """Every word one command is written with, read from the token stream."""

    tokens: tuple[Token, ...]

    @property
    def named(self) -> tuple[Token, ...]:
        """Return the words left once the leading reserved words are dropped."""

        index = 0
        while index < len(self.tokens):
            if _token_text(self.tokens[index]) not in RESERVED_WORDS:
                break
            index += 1
        return self.tokens[index:]

    @property
    def assignments(self) -> tuple[Token, ...]:
        """Return the assignment words written in front of this command."""

        assignments: list[Token] = []
        for token in self.named:
            if _assignment_name(token) is None:
                break
            assignments.append(token)
        return tuple(assignments)

    @property
    def words(self) -> tuple[Token, ...]:
        """Return the command word and its operands, if a command word is written."""

        return self.named[len(self.assignments):]

    def assignment_names(self) -> tuple[tuple[Token, str], ...]:
        """Return every assignment word written in front of this command."""

        pairs = []
        for token in self.assignments:
            name = _assignment_name(token)
            if name is not None:
                pairs.append((token, name))
        return tuple(pairs)

    def command_name(self, fixture: "_Fixture") -> str | None:
        """Return the one command this run names, or nothing when it names more.

        A command written behind a launcher, or written with an expansion, is
        not read as one command, because the command that would run is decided
        from text this checker does not settle here. A command a fixture
        declares itself is read as its own name, because what a declared
        function binds is read from its body rather than from its call.
        """

        if not self.words:
            return None
        written = _token_text(self.words[0])
        if written is None or written in LAUNCHER_COMMANDS:
            return None
        return written


def _segment_kinds(segments: Sequence[shell_lexical.Segment]) -> set[str]:
    """Return every segment kind written in one word, however deeply nested."""

    kinds: set[str] = set()
    for segment in segments:
        kinds.add(segment.kind)
        kinds.update(_segment_kinds(segment.segments))
        for token in segment.tokens:
            kinds.update(_segment_kinds(token.segments))
    return kinds


def _unaccepted_constructs(
    records: shell_lexical.LexicalProjection,
) -> tuple[str, ...]:
    """Return one description of every construct this checker does not read.

    The enumeration is deliberately narrow. Widening it is a reviewed change,
    because each construct added here is one more thing the settled answer
    depends on.
    """

    reasons: list[str] = []
    for token in records.tokens:
        if token.kind not in ACCEPTED_TOKEN_KINDS:
            reasons.append(f"a {token.kind} record at offset {token.start.offset}")
            continue
        if token.kind == "operator" and token.text not in ACCEPTED_OPERATORS:
            reasons.append(
                f"the operator {token.text!r} at offset {token.start.offset}"
            )
            continue
        unread = _segment_kinds(token.segments) - ACCEPTED_SEGMENT_KINDS
        if unread:
            reasons.append(
                f"a {sorted(unread)[0]} span at offset {token.start.offset}"
            )
            continue
        if token.kind == "word" and token.text not in GROUP_WORDS:
            for segment in token.segments:
                if segment.kind != "literal":
                    continue
                if any(brace in segment.text for brace in BRACE_CHARACTERS):
                    reasons.append(
                        f"an unquoted brace at offset {segment.start.offset}"
                    )
                    break
    return tuple(reasons)


def _written_names(records: shell_lexical.LexicalProjection) -> frozenset[str]:
    """Return every name written anywhere in one fixture.

    A shell joins a continued line before it reads a name, so the names it can
    see are the ones written in the joined text as well as the ones written in
    the text as it stands.
    """

    joined = records.source.replace(LINE_CONTINUATION, "")
    return frozenset(
        NAME_PATTERN.findall(records.source) + NAME_PATTERN.findall(joined)
    )


def _detaching_follows(words: Sequence[Token], index: int) -> bool:
    """Report whether a detaching operator is written after one token.

    A command carries its redirections between its last word and the operator
    that follows it, so the redirections written there are read past rather
    than read as the following operator. A redirection is written as an
    optional file number, the redirection operator, and the one word it
    redirects to, and a here-document also carries its body.
    """

    position = index + 1
    while position < len(words):
        token = words[position]
        if token.kind == "io_number" or token.kind == HEREDOC_KIND:
            position += 1
            continue
        if token.kind == "operator" and token.text not in COMMAND_BREAKS:
            position += 1
            while position < len(words) and words[position].kind == HEREDOC_KIND:
                position += 1
            if position < len(words) and words[position].kind == WORD:
                position += 1
            continue
        return token.kind == "operator" and token.text in DETACHING_BREAKS
    return False


def _detached_spans(
    records: shell_lexical.LexicalProjection,
) -> tuple[tuple[int, int], ...]:
    """Return every extent whose assignments the surrounding shell never sees.

    A shell runs a subshell, one side of a pipeline, and a command written
    behind `&` in its own copy of itself, so an assignment written in one of
    them leaves the surrounding shell holding whatever it held before. Every
    such extent is read from the tokens, because a parenthesis or a `&` written
    inside a quoted span or a here-document is not one at all. A group carries
    its redirections after its closing brace, so the operator that detaches the
    group is the one written past those redirections.
    """

    spans: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    words = [token for token in records.tokens if token.kind != CONTINUATION_KIND]
    for index, token in enumerate(words):
        detaches = _detaching_follows(words, index)
        if token.kind == "operator" and token.text == SUBSHELL_OPEN:
            stack.append((SUBSHELL_OPEN, token.start.offset))
            continue
        if token.kind == "operator" and token.text == SUBSHELL_CLOSE:
            while stack:
                kind, start = stack.pop()
                spans.append((start, token.end.offset))
                if kind == SUBSHELL_OPEN:
                    break
            continue
        if token.kind == WORD and _token_text(token) == GROUP_OPEN:
            stack.append((GROUP_OPEN, token.start.offset))
            continue
        if token.kind == WORD and _token_text(token) == GROUP_CLOSE:
            if stack and stack[-1][0] == GROUP_OPEN:
                _, start = stack.pop()
                if detaches:
                    spans.append((start, token.end.offset))
            continue
        if token.kind == "operator" and token.text in DETACHING_BREAKS:
            spans.append((token.start.offset, token.end.offset))
    for _, start in stack:
        spans.append((start, len(records.source)))
    return tuple(spans)


def _pipeline_extents(
    records: shell_lexical.LexicalProjection,
) -> tuple[tuple[int, int], ...]:
    """Return the extent of every command list written beside `&` or `|`.

    A command list ends at a newline or a `;`, so the extent between two of
    those that carries a detaching operator is the extent a shell detaches.
    """

    extents: list[tuple[int, int]] = []
    start: int | None = None
    detached = False
    for token in records.tokens:
        if token.kind == CONTINUATION_KIND:
            continue
        if token.kind == "newline" or (
            token.kind == "operator" and token.text in (";", ";;")
        ):
            if start is not None and detached:
                extents.append((start, token.start.offset))
            start = None
            detached = False
            continue
        if start is None:
            start = token.start.offset
        if token.kind == "operator" and token.text in DETACHING_BREAKS:
            detached = True
    if start is not None and detached:
        extents.append((start, len(records.source)))
    return tuple(extents)


def _command_runs(records: shell_lexical.LexicalProjection) -> tuple[_CommandRun, ...]:
    """Return every command written in one fixture, read from its tokens.

    A command ends where a shell ends a command list, and a redirection is
    written with a word that is not one of the command's own, so both the
    redirection operator and the word that follows it are dropped.
    """

    runs: list[_CommandRun] = []
    words: list[Token] = []
    redirected = False
    for token in records.tokens:
        if token.kind == CONTINUATION_KIND:
            continue
        if token.kind == WORD:
            if redirected:
                redirected = False
                continue
            words.append(token)
            continue
        redirected = False
        if token.kind == "io_number" or token.kind == "heredoc_body":
            continue
        if token.kind == "newline" or (
            token.kind == "operator" and token.text in COMMAND_BREAKS
        ):
            if words:
                runs.append(_CommandRun(tokens=tuple(words)))
                words = []
            continue
        if token.kind == "operator":
            redirected = True
    if words:
        runs.append(_CommandRun(tuple(words)))
    return tuple(runs)


_Parts = tuple[tuple[str, str], ...]


_Bindings = dict[str, tuple[_Parts, ...] | None]


def _unquoted(word: str) -> str:
    """Return one written word with its quote marks removed."""

    written: list[str] = []
    quote: str | None = None
    for character in word:
        if quote is None and character in QUOTE_MARKS:
            quote = character
            continue
        if quote is not None and character == quote:
            quote = None
            continue
        written.append(character)
    return "".join(written)


def _word_parts(
    word: str, origin: str, splits: bool = True, anchored: bool = True
) -> _Parts | None:
    """Return the modelled parts of one written word, or ``None`` for any other.

    A part is written text, a name the shell expands, or a command
    substitution this checker reads as one opaque unit. A quote decides what
    the shell does with an expansion: a dollar sign inside single quotes is
    text the shell keeps, and an unquoted expansion in a command word is split
    into fields and matched against path names, so neither is modelled.

    A substitution is read only where it is bound to a name, which ``splits``
    reports: an assignment runs it once and every later reader of that name
    reads the one value it produced, while a substitution written in a command
    word runs again each time that command runs. The bound value is named by
    ``origin`` and its place in the value, so two readers of one binding carry
    one name and two bindings never do.
    """

    parts: list[tuple[str, str]] = []
    literal: list[str] = []
    quote: str | None = None
    index = 0

    def flush() -> None:
        if literal:
            parts.append(("literal", "".join(literal)))
            literal.clear()

    while index < len(word):
        character = word[index]
        if quote is None and character in QUOTE_MARKS:
            quote = character
            index += 1
            continue
        if quote is not None and character == quote:
            quote = None
            index += 1
            continue
        if character == "$" and quote != "'":
            if splits and quote is None:
                return None
            match = BRACED_NAME_PATTERN.match(word, index) or PLAIN_NAME_PATTERN.match(
                word, index
            )
            if match is not None:
                flush()
                parts.append(("name", match.group(1)))
                index = match.end()
                continue
            if splits:
                return None
            end = _substitution_end(word, index)
            if end < 0:
                return None
            inside = word[index + len(SUBSTITUTION_START) : end - 1]
            absolute = anchored and (
                ABSOLUTE_SUBSTITUTION_PATTERN.fullmatch(inside.strip()) is not None
            )
            flush()
            mark = ABSOLUTE_OPAQUE_MARK if absolute else OPAQUE_MARK
            parts.append(("opaque", f"{mark}{origin}:{index}"))
            index = end
            continue
        if WORD_LITERAL_PATTERN.fullmatch(character) is None:
            return None
        literal.append(character)
        index += 1
    if quote is not None:
        return None
    flush()
    return tuple(parts) or None


def _substitution_end(word: str, index: int) -> int:
    """Return where one modelled command substitution ends, or ``-1``.

    A command substitution names a path this checker cannot compute, so it is
    read as one opaque unit and never as the text inside it. Only the plain
    form is modelled: an arithmetic expansion, a nested substitution, a
    backquote, or an unterminated span is not.
    """

    if not word.startswith(SUBSTITUTION_START, index):
        return -1
    if word.startswith(ARITHMETIC_START, index):
        return -1
    end = word.find(SUBSTITUTION_END, index)
    if end < 0:
        return -1
    inside = word[index + len(SUBSTITUTION_START) : end]
    if SUBSTITUTION_START in inside or BACKQUOTE_MARK in inside or "(" in inside:
        return -1
    return end + 1


def _settled_path(parts: _Parts) -> tuple[bool, tuple[str, ...]] | None:
    """Return one written word as an anchored sequence of path segments.

    Segments are built from the modelled parts rather than from the written
    text, so a substitution that carries separators never divides into
    segments this checker compares. An empty or current segment names the same
    directory and is dropped. A parent segment is not modelled at all: the
    directory it names depends on whether the segment above it is a link,
    which no written text decides.
    """

    absolute = _anchors_a_path(parts[0])
    segments: list[str] = []
    current = ""

    def close(segment: str) -> bool:
        if segment in ("", "."):
            return True
        if segment == "..":
            return False
        segments.append(segment)
        return len(segments) <= SETTLED_SEGMENTS

    for kind, text in parts:
        if kind == "literal":
            written = text.split("/")
            current += written[0]
            for piece in written[1:]:
                if not close(current):
                    return None
                current = piece
            continue
        current += "$" + text if kind == "name" else text
    if not close(current):
        return None
    if not segments and not absolute:
        return None
    return absolute, tuple(segments)


def _anchors_a_path(part: tuple[str, str]) -> bool:
    """Report whether one leading part names a directory from the root.

    Written text names it when it starts at the root. A substitution names it
    only in the one command list this checker reads as writing an absolute
    path, because every other value may name a directory the working directory
    decides, and a fixture may change that directory between two readers.
    """

    kind, text = part
    if kind == "literal":
        return text.startswith("/")
    return kind == "opaque" and text.startswith(ABSOLUTE_OPAQUE_MARK)


def _carries_expansion(segment: str) -> bool:
    """Report whether one settled segment still depends on an expansion.

    The modelled literal characters exclude the dollar sign, so a segment that
    writes one carries a name or a substitution whose value this checker never
    reads.
    """

    return "$" in segment


def _carries_substitution(values: tuple[_Parts, ...]) -> bool:
    """Report whether any settled value depends on a command substitution."""

    return any(kind == "opaque" for parts in values for kind, _ in parts)


def _merge_binding(
    bindings: _Bindings, name: str, settled: tuple[_Parts, ...] | None
) -> None:
    """Add one more value a name may hold, keeping an unread value unproven."""

    if name in bindings and bindings[name] is None:
        return
    if settled is None:
        bindings[name] = None
        return
    held = bindings.get(name) or ()
    bindings[name] = held + tuple(value for value in settled if value not in held)


def _resolve_parts(
    parts: _Parts, bindings: _Bindings, unsettled: frozenset[str]
) -> tuple[_Parts, ...] | None:
    """Return every part sequence one word may carry once its names are read.

    A bound value carries no name of its own, because it was read where it was
    written, so replacing a name always removes one and the walk terminates. A
    name this checker cannot settle, or a walk that grows past the text bound,
    proves nothing and yields ``None``. A name no assignment binds keeps the
    value the surrounding shell holds, which is one value at every reader, so
    it stays in the sequence as an unread unit.
    """

    done: set[_Parts] = set()
    pending: list[_Parts] = [parts]
    seen: set[_Parts] = {parts}
    while pending:
        if len(done) + len(pending) > SETTLED_TEXTS:
            return None
        current = pending.pop()
        index = next(
            (place for place, (kind, _) in enumerate(current) if kind == "name"),
            None,
        )
        if index is None:
            done.add(current)
            continue
        name = current[index][1]
        if name in unsettled:
            return None
        if name in bindings:
            held = bindings[name]
            if held is None:
                return None
            grown = tuple(
                current[:index] + value + current[index + 1 :] for value in held
            )
        else:
            grown = (current[:index] + (("opaque", "$" + name),) + current[index + 1 :],)
        for candidate in grown:
            if candidate not in seen:
                seen.add(candidate)
                pending.append(candidate)
    return tuple(sorted(done))


def _settle_word(
    word: str,
    bindings: _Bindings,
    unsettled: frozenset[str] = frozenset(),
    origin: str = "w",
    splits: bool = True,
) -> frozenset[tuple[bool, tuple[str, ...]]]:
    """Return every path one written word may name, or nothing when unproven."""

    parts = _word_parts(word, origin, splits)
    if parts is None:
        return frozenset()
    resolved = _resolve_parts(parts, bindings, unsettled)
    if resolved is None:
        return frozenset()
    settled: set[tuple[bool, tuple[str, ...]]] = set()
    for candidate in resolved:
        path = _settled_path(candidate)
        if path is None:
            return frozenset()
        settled.add(path)
    return frozenset(settled)


def _settle_written_word(
    fixture: _Fixture, operation: _Operation, word: str
) -> frozenset[tuple[bool, tuple[str, ...]]]:
    """Return every path one word of one operation may name."""

    return _settle_word(
        word, fixture.bindings_for(operation), fixture.unsettled_names()
    )


def _paths_are_lexically_separate(
    reserved: frozenset[tuple[bool, tuple[str, ...]]],
    candidate: frozenset[tuple[bool, tuple[str, ...]]],
) -> bool:
    """Report whether no written candidate path spells a reserved path.

    This answers what the written text decides. A link written by the fixture
    can still make two separately written paths name one directory, so a caller
    that needs directory separation must also prove that no alias it tracks
    lies on either path.
    """

    if not reserved or not candidate:
        return False
    return all(
        _lexically_separate(left, right) for left in reserved for right in candidate
    )


def _lexically_separate(
    left: tuple[bool, tuple[str, ...]], right: tuple[bool, tuple[str, ...]]
) -> bool:
    """Report whether two settled paths are written as separate directories.

    Two paths are written apart only when they start from the same anchor,
    differ in a segment both write entirely as text, and write no expansion at
    or after that segment. An expansion written there may name the same
    directory the other path names, which removes the difference the written
    text carries. A path written inside the other is never apart, because an
    update there changes the same files.
    """

    if left == right:
        return False
    if not left[0] or not right[0]:
        # A path this checker cannot anchor at the root names a directory the
        # working directory decides, and a fixture may change that directory
        # between two readers, so no written text keeps such paths apart.
        return False
    first, second = left[1], right[1]
    if first and second and first[0] != second[0] and (
        _carries_expansion(first[0]) or _carries_expansion(second[0])
    ):
        # Two anchors this checker reads as separate expansions may still name
        # one directory, because their values are written nowhere.
        return False
    length = min(len(first), len(second))
    index = next(
        (position for position in range(length) if first[position] != second[position]),
        length,
    )
    if index == length:
        return False
    return not any(
        _carries_expansion(segment)
        for segments in (first, second)
        for segment in segments[index:]
    )


def _path_text(path: tuple[bool, tuple[str, ...]]) -> str:
    """Return one settled path as the text a message reads."""

    return ("/" if path[0] else "") + "/".join(path[1])


# The commands this checker reads as writing an alias. A command written in
# any other spelling leaves the alias set unplaced rather than carrying no
# alias, because a link this checker never sees makes one written path name a
# directory another written path names.
LINK_COMMANDS = frozenset({"ln", "cp"})


RELOCATION_COMMANDS = frozenset({"mv", "cp"})


SYMLINK_OPTION_MARK = "s"


# Every short option that keeps a symbolic link a link. `-R` is an exact
# synonym of `-r` and `-P` asks for no dereference, so the marks are read
# without regard to case.
LINK_PRESERVING_MARKS = ("d", "a", "r", "p", "s", "P")


LINK_PRESERVING_OPTIONS = ("no-dereference", "archive", "recursive", "symbolic")


SYMBOLIC_OPTIONS = ("symbolic", "symbolic-link")


TARGET_DIRECTORY_MARK = "t"


TARGET_DIRECTORY_OPTION = "target-directory"


OPTION_MARK = "-"


OPTION_END = "--"


# A relocation may carry an alias to a path a later relocation moves again, so
# the chain is followed under a fixed budget rather than to a fixed point.
MOVE_ROUNDS = 8


_Path = tuple[bool, tuple[str, ...]]


# The directory a generated project holds its installed workflow in. A command
# word written inside it runs against the project above it whatever the script
# is named, so the destination of such a dispatch is read from the path rather
# than from the name.
WORKFLOW_DIRECTORY = ".project-agent-workflow"
# The Copier subcommand that changes a project in place. Every other
# subcommand writes a project this checker reads from its own operands, so
# only this one names a destination the sanctioned child may share.
UPDATE_SUBCOMMAND = "update"
# The Copier subcommands that write a whole project from the template. They
# are not updates, so they are never read as an alternate update path, but a
# write they aim at the sanctioned destination replaces the project the
# transition proves, so their destination is read as well.
COPY_SUBCOMMAND = "copy"
RECOPY_SUBCOMMAND = "recopy"
COPY_SUBCOMMANDS = frozenset({COPY_SUBCOMMAND, RECOPY_SUBCOMMAND})
# The operand count each read Copier subcommand writes. A copy writes the
# template it reads and then the project it writes; an update and a recopy
# write only the project. The destination is the last of them, so an operand
# count this checker does not read settles no destination at all.
COPIER_WRITE_OPERANDS = {
    UPDATE_SUBCOMMAND: 1,
    COPY_SUBCOMMAND: 2,
    RECOPY_SUBCOMMAND: 1,
}
# The enclosure a subshell opens and the command that changes a directory
# inside it. A relative command word runs against the directory its own
# subshell settles, so only these two names are read to place such a word.
SUBSHELL_ENCLOSURE = "subshell"
DIRECTORY_CHANGE = "cd"
# The options this checker reads a Copier update as writing. An option written
# in any other spelling may take an operand this checker would read as the
# destination, so a dispatch that writes one names no destination at all.
COPIER_FLAG_OPTIONS = frozenset(
    {
        "-f",
        "-q",
        "--force",
        "--quiet",
        "--defaults",
        "--overwrite",
        "--pretend",
        "--trust",
        "--unsafe",
        "--skip-answered",
        "--skip-tasks",
    }
)
COPIER_VALUE_OPTIONS = frozenset(
    {
        "-r",
        "-x",
        "-d",
        "-a",
        "--vcs-ref",
        "--exclude",
        "--data",
        "--data-file",
        "--answers-file",
        "--conflict",
        "--context-lines",
        "--skip",
    }
)
# A launcher runs the command written after it, so the command word of a
# dispatch may be written behind one of these rather than first.
LAUNCHER_WORDS = LAUNCHER_COMMANDS | FORKING_LAUNCHERS
# One dispatch writes few launcher prefixes, and the bound keeps supplied
# bytes from making the walk long.
LAUNCHER_ROUNDS = 4


def _launched_command(literals: tuple[str | None, ...]) -> str | None:
    """Return the command one bounded chain of launchers runs, when it is written.

    A launcher runs the command written after its own options, so a run whose
    own command word is a launcher names the command this checker reads behind
    it rather than no command at all.
    """

    places = _command_word_places(literals)
    if len(places) < 2:
        return None
    written = literals[places[-1]]
    return None if written is None else _basename(written)


def _run_literals(run: _CommandRun) -> tuple[str | None, ...]:
    """Return the text each word of one command reads as, or ``None`` for any other."""

    return tuple(_token_text(word) for word in run.words)


def _basename(literal: str) -> str:
    """Return the name a written command word runs, without its directory."""

    return literal.rsplit(PATH_SEPARATOR, 1)[-1]


def _command_index(literals: tuple[str | None, ...], names: frozenset[str]) -> int:
    """Return where one command run writes one of the named commands.

    Every word is read, not only the command word, because a launcher may
    carry its own options and this checker reads a launcher argument as the
    command it runs. Reading one word too many keeps an alias this checker
    cannot place from proving separation, which is the safe direction.
    """

    return next(
        (
            index
            for index, literal in enumerate(literals)
            if literal is not None and _basename(literal) in names
        ),
        -1,
    )


def _unread_command_index(literals: tuple[str | None, ...]) -> int:
    """Return where one command run writes a command word this checker cannot read.

    Only the command word is read, because a run whose command word names an
    ordinary command runs that command whatever its operands expand to. An
    operand this checker cannot read never turns a written command into a link
    command, so reading one as a command word would call an ordinary run a
    link and leave every destination unproven.
    """

    places = _command_word_places(literals)
    if not places:
        return -1
    place = places[-1]
    return place if literals[place] is None else -1


def _written_options(literals: tuple[str | None, ...], index: int) -> list[str]:
    """Return every option written after one command word, up to a bare double dash."""

    options: list[str] = []
    for literal in literals[index + 1 :]:
        if literal == OPTION_END:
            break
        if literal is not None and literal.startswith(OPTION_MARK) and literal != OPTION_MARK:
            options.append(literal)
    return options


def _written_operands(run: _CommandRun, literals: tuple[str | None, ...], index: int):
    """Return every operand written after one command word.

    An option this checker cannot read may take its own operand, so a run that
    writes one is never read as writing a known operand count.
    """

    operands: list[Token] = []
    ended = False
    for place in range(index + 1, len(literals)):
        literal = literals[place]
        if not ended and literal == OPTION_END:
            ended = True
            continue
        if not ended and literal is not None and literal.startswith(OPTION_MARK) and literal != OPTION_MARK:
            continue
        operands.append(run.words[place])
    return operands


def _cannot_be_an_option(
    fixture: _Fixture, run: _CommandRun, word: Token
) -> bool:
    """Report whether one written word can never be read as an option.

    A command reads a word as an option only when the word starts with a dash,
    and it reads the characters after that dash as option letters. A slash is
    not an option letter and no long option this checker reads carries one, so
    a word written with a slash is refused as an option whatever its
    expansions produce, and the command that writes it fails rather than
    writing a link. A word that settles to a path anchored at the root writes
    a slash for the same reason.
    """

    parts = _word_parts(word.text, f"p{word.start.offset}", splits=True)
    if parts is not None and any(
        kind == LITERAL_SEGMENT and PATH_SEPARATOR in text for kind, text in parts
    ):
        return True
    settled = _settle_operand(fixture, run, word)
    return bool(settled) and all(anchored for anchored, _ in settled)


def _is_symlink_option(literal: str) -> bool:
    """Report whether one option asks a link command for a symbolic link."""

    if literal.startswith(OPTION_END):
        written = literal[2:].split("=", 1)[0]
        return bool(written) and any(
            name.startswith(written) or written.startswith(name)
            for name in SYMBOLIC_OPTIONS
        )
    cluster = literal[1:]
    return bool(cluster) and cluster.isalpha() and SYMLINK_OPTION_MARK in cluster


def _names_target_directory(options: list[str]) -> bool:
    """Report whether one option list places its operands inside a directory."""

    return any(
        _abbreviates_target_directory(option)
        if option.startswith(OPTION_END)
        else TARGET_DIRECTORY_MARK in option[1:]
        for option in options
    )


def _abbreviates_target_directory(option: str) -> bool:
    """Report whether one long option may be written for a target directory."""

    written = option[2:].split("=", 1)[0]
    return bool(written) and TARGET_DIRECTORY_OPTION.startswith(written)


def _preserves_link(option: str) -> bool:
    """Report whether one copy option keeps a symbolic link a link."""

    if option.startswith(OPTION_END):
        written = option[2:].split("=", 1)[0]
        return bool(written) and any(
            name.startswith(written) or written.startswith(name)
            for name in LINK_PRESERVING_OPTIONS
        )
    cluster = option[1:]
    return any(
        mark in cluster or mark.lower() in cluster.lower()
        for mark in LINK_PRESERVING_MARKS
    )


def _holds_path(outer: _Path, inner: _Path) -> bool:
    """Report whether one settled path is written above another.

    A path is written above another only when both are anchored at the same
    root, the outer path writes fewer segments, and every segment it writes is
    the segment the inner path writes there. A segment written with an
    expansion decides nothing, so it never places one path above another.
    """

    if outer[0] != inner[0] or len(outer[1]) >= len(inner[1]):
        return False
    if any(_carries_expansion(segment) for segment in outer[1]):
        return False
    return inner[1][: len(outer[1])] == outer[1]


def _may_be_ancestor(link: _Path, destination: _Path) -> bool:
    """Report whether one alias may name one destination or hold it."""

    if link == destination or _holds_path(link, destination):
        return True
    if _holds_path(destination, link):
        return False
    return not _lexically_separate(link, destination)


def _may_be_linked(links: frozenset[_Path], destinations: frozenset[_Path]) -> bool:
    """Report whether any tracked alias may name one destination or hold it."""

    return any(
        _may_be_ancestor(link, destination)
        for link in links
        for destination in destinations
    )


def _inside_directory(directory: frozenset[_Path], named: frozenset[_Path]) -> frozenset[_Path]:
    """Return each named path read as written inside one written directory.

    A second operand may name a directory rather than the alias itself, and no
    written text decides which, so both readings are recorded.
    """

    return frozenset(
        (place[0], place[1] + (path[1][-1],))
        for place in directory
        for path in named
        if path[1]
    )


def _settle_operand(fixture: _Fixture, run: _CommandRun, word: Token) -> frozenset[_Path]:
    """Return every path one operand of a link or a relocation may name."""

    bindings = fixture.bindings_at(run)
    if bindings is None:
        return frozenset()
    return _settle_word(
        word.text, bindings, fixture.unsettled_names(), f"o{word.start.offset}"
    )


def _symlinked_paths(fixture: _Fixture) -> tuple[frozenset[_Path], bool]:
    """Return every path a fixture may link, and whether one cannot be placed.

    A symbolic link makes one written path name another directory, so a
    destination a link may name is not the destination it is written as. A
    link this checker cannot place leaves every destination unproven, and a
    command word this checker cannot read is held to the spellings a symbolic
    link is written with, because a broader reading would call every unread
    command a link.
    """

    links: set[_Path] = set()
    unplaced = False
    for run in fixture.command_runs():
        if not run.words:
            continue
        literals = _run_literals(run)
        index = _command_index(literals, LINK_COMMANDS)
        named = index >= 0
        if not named:
            index = _unread_command_index(literals)
            if index < 0:
                continue
        options = _written_options(literals, index)
        if not any(
            SYMLINK_OPTION_MARK in option[1:] or _is_symlink_option(option)
            if named
            else _is_symlink_option(option)
            for option in options
        ):
            # An option this checker cannot read may be the one that asks for
            # a symbolic link, so a run that writes one is never read as a run
            # that writes no link.
            if named and any(
                literal is None
                and not _cannot_be_an_option(fixture, run, run.words[place])
                for place, literal in enumerate(literals)
                if place > index
            ):
                unplaced = True
            continue
        operands = _written_operands(run, literals, index)
        if len(operands) != 2 or _names_target_directory(options):
            unplaced = True
            continue
        targets = _settle_operand(fixture, run, operands[0])
        aliases = _settle_operand(fixture, run, operands[1])
        if not targets or not aliases:
            unplaced = True
            continue
        links |= aliases
        links |= _inside_directory(aliases, targets)
    return _moved_aliases(fixture, frozenset(links), unplaced)


def _moves(fixture: _Fixture) -> list[tuple[frozenset[_Path], frozenset[_Path]]]:
    """Return every relocation of one written path to another."""

    relocations: list[tuple[frozenset[_Path], frozenset[_Path]]] = []
    for run in fixture.command_runs():
        if not run.words:
            continue
        literals = _run_literals(run)
        index = _command_index(literals, RELOCATION_COMMANDS)
        if index < 0:
            continue
        options = _written_options(literals, index)
        written = literals[index]
        moves = written is not None and _basename(written) == "mv"
        if not moves and not any(_preserves_link(option) for option in options):
            # A copy option this checker does not read may keep a link a link,
            # so only a copy written without one is read as storing the file
            # the link names.
            if any(option.startswith(OPTION_END) for option in options):
                relocations.append((frozenset(), frozenset()))
            continue
        operands = _written_operands(run, literals, index)
        if len(operands) != 2 or _names_target_directory(options):
            relocations.append((frozenset(), frozenset()))
            continue
        sources = _settle_operand(fixture, run, operands[0])
        targets = _settle_operand(fixture, run, operands[1])
        if sources and targets:
            targets |= _inside_directory(targets, sources)
        else:
            targets = frozenset()
        relocations.append((sources, targets))
    return relocations


def _moved_aliases(
    fixture: _Fixture, links: frozenset[_Path], unplaced: bool
) -> tuple[frozenset[_Path], bool]:
    """Return every path a fixture may move one of its links to.

    Moving a symbolic link carries the alias to the path it is moved to, so a
    destination the moved path names is no more proven than the path it was
    written at. A relocation this checker cannot place may move any tracked
    alias, and a chain of relocations is followed under a fixed round budget.
    """

    carried = set(links)
    relocations = _moves(fixture)
    for _ in range(MOVE_ROUNDS):
        added = False
        for source, target in relocations:
            if not carried:
                break
            if source and not _may_be_linked(frozenset(carried), source):
                continue
            if not target:
                unplaced = True
                continue
            if not target <= carried:
                carried |= target
                added = True
        if not added:
            break
    return frozenset(carried), unplaced


class _Fixture:
    """Every derived view the Copier operation contract reads."""

    def __init__(
        self,
        text: str,
        records: shell_lexical.LexicalProjection,
        table: shell_functions.FunctionTable,
        graph: ExecutionGraph,
    ) -> None:
        self.text = text
        self.records = records
        self.table = table
        self.graph = graph
        self.operations = _fold_operations(records, graph)
        self.assignments = _command_assignments(records)
        self.git_wrappers = frozenset(
            node.call_path[0]
            for node in graph.commands
            if node.name == "git" and node.call_path
        )
        self.cleanup = self._cleanup_declaration()
        self._loop_extents, self._branch_extents = self._derive_compound_extents()
        self._unconditional = _unconditional_positions(records)
        self._conditional_spans = self._derive_conditional_spans()
        self._expanded = self._expand_operations()
        self._git_operations = self._derive_git_operations()
        self._git_subcommands = {
            operation.offset: _git_subcommand(operation)[0]
            for operation in self._git_operations
        }
        self._runs: tuple[_CommandRun, ...] | None = None
        self._unsettled: frozenset[str] | None = None
        self._detached: tuple[tuple[int, int], ...] | None = None
        self._unaccepted: tuple[str, ...] | None = None
        self._unknown_binding = False
        self._resolved: dict[int, _Bindings] = {}
        self._settled: dict[int, _Bindings] = {}
        self._operations_by_offset: dict[int, _Operation] | None = None

    def command_runs(self) -> tuple["_CommandRun", ...]:
        """Return every command this fixture writes, read from its tokens.

        A command is the run of words written between two of the operators a
        shell ends a command list with. The words a shell reads as an
        assignment come first, and the first word that is not one of them is
        the command word, so a fixture that writes only assignments writes no
        command word at all.
        """

        if self._runs is None:
            self._runs = _command_runs(self.records)
        return self._runs

    def declares(self, name: str) -> bool:
        """Report whether this fixture declares a function of one name."""

        return any(
            declaration.name == name for declaration in self.table.declarations
        )

    def written_assigned_names(self) -> frozenset[str]:
        """Return every name written with a value this checker records no assignment for.

        A fixture may write several assignments as one command, and only the
        first of them is recorded in command position, so a name written with a
        value where this checker holds no assignment is never settled. A
        recorded assignment the token walk does not read as the same name is
        never settled either, because the two readings then disagree about
        which name carries the written value.
        """

        derived = {
            token.start.offset: name
            for run in self.command_runs()
            for token, name in run.assignment_names()
        }
        names = {
            name
            for offset, name in derived.items()
            if offset not in {item.offset for item in self.assignments}
        }
        names.update(
            assignment.name
            for assignment in self.assignments
            if derived.get(assignment.offset) != assignment.name
        )
        return frozenset(names)

    def prefix_assigned_names(self) -> frozenset[str]:
        """Return every name a fixture assigns in front of a command.

        A shell expands a command's words before it applies the assignments
        written in front of that command, and such an assignment leaves the
        shell's own value unchanged, so neither that command nor any later one
        carries it. This checker settles with every assignment written earlier,
        so a word that reads such a name is not settled by what is written
        above it.
        """

        return frozenset(
            name
            for run in self.command_runs()
            if run.words
            for _, name in run.assignment_names()
        )

    def command_assigned_names(self) -> frozenset[str]:
        """Return every name a command may give a value this checker misses.

        A shell also assigns through commands such as ``export`` and ``read``,
        and this checker reads only the assignments written in command
        position. A name written with a value in any operand, or named by a
        command this checker models as assigning, may therefore hold a value no
        assignment carries. A command word this checker cannot read as one name
        may name any command at all, so every bare operand written with it is
        treated as a name that command may bind, unless the word carries a
        slash or runs in its own process, because neither can name a builtin
        that gives the writing shell a value. An operand this checker cannot
        read as one text names a variable this checker cannot name, so such an
        operand records that the fixture binds a name it never sees.
        """

        names: set[str] = set()
        self._unknown_binding = False
        for run in self.command_runs():
            if not run.words:
                continue
            command = run.command_name(self)
            if command is None:
                command = _launched_command(_run_literals(run))
            if _token_text(run.words[0]) in FORKING_LAUNCHERS or _writes_a_path(
                run.words[0]
            ):
                continue
            binds = command is None or command in ASSIGNING_COMMANDS
            names_jobs = command in JOB_OPERAND_COMMANDS
            binds = binds and not names_jobs
            mark = JOB_NAME_OPTION if names_jobs else NAMED_OPTION
            named = False
            reads_paths = command in PATH_OPERAND_COMMANDS
            for token in run.words[1:]:
                written = _token_text(token)
                if written is None:
                    if (binds or named) and not reads_paths:
                        self._unknown_binding = True
                    named = False
                    continue
                if named:
                    names.add(written.split("=", 1)[0])
                    named = False
                    continue
                if written.startswith(mark):
                    attached = written[len(mark):]
                    if attached:
                        names.add(attached.split("=", 1)[0])
                    else:
                        named = True
                    continue
                if written.startswith("-"):
                    continue
                if binds:
                    names.add(written.split("=", 1)[0])
        return frozenset(name for name in names if NAME_PATTERN.fullmatch(name))

    def loop_assigned_names(self) -> frozenset[str]:
        """Return every name a loop head binds.

        A loop head binds its name once per round from a list this checker does
        not read, so a word written under it reads a value no assignment above
        it carries.
        """

        names: set[str] = set()
        for run in self.command_runs():
            for index, token in enumerate(run.tokens[:-1]):
                if _token_text(token) != LOOP_KEYWORD:
                    continue
                written = _token_text(run.tokens[index + 1])
                if written is None or not NAME_PATTERN.fullmatch(written):
                    continue
                names.add(written)
        return frozenset(names)

    def function_assigned_names(self) -> frozenset[str]:
        """Return every name a function body assigns.

        A function runs where it is called, so an assignment written in its
        body gives a value to every later reader, not only to the words written
        under it. This checker settles a name from the assignments written
        above the reader, so such a name is never settled.
        """

        return frozenset(
            assignment.name
            for assignment in self.assignments
            if self.inside_declaration(assignment.offset)
        )

    def inherited_names(self) -> frozenset[str]:
        """Return every name whose first written value may not be written at all.

        A shell runs a fixture with the values its caller holds. An assignment
        the fixture may not reach leaves that inherited value in place, and no
        written text carries it, so a name whose first assignment does not
        certainly run is never settled.
        """

        first: dict[str, _Assignment] = {}
        for assignment in sorted(self.assignments, key=lambda item: item.offset):
            first.setdefault(assignment.name, assignment)
        return frozenset(
            name
            for name, assignment in first.items()
            if not self._certainly_runs(assignment)
        )

    def uncertainly_assigned_names(self) -> frozenset[str]:
        """Return every name whose written value may not be the value it holds.

        A shell applies an assignment only where it reaches it, and an
        assignment written under a condition, inside a loop, in a subshell, in
        one side of a pipeline, or behind `&` either does not run at all or
        runs where the surrounding shell never sees it. This checker settles a
        name from the last assignment written above the reader, so a name any
        of whose assignments does not certainly run where it is written is
        never settled.
        """

        detached = self.detached_spans()
        return frozenset(
            assignment.name
            for assignment in self.assignments
            if not self._certainly_runs(assignment)
            or any(start <= assignment.offset <= end for start, end in detached)
        )

    def detached_spans(self) -> tuple[tuple[int, int], ...]:
        """Return every extent whose assignments the surrounding shell never sees."""

        if self._detached is None:
            self._detached = _detached_spans(self.records) + _pipeline_extents(
                self.records
            )
        return self._detached

    def expansion_assigned_names(self) -> frozenset[str]:
        """Return every name an expansion may give a value to.

        A shell assigns through `${name=value}` and `${name:=value}` as well as
        through arithmetic, where `$((name=1))` and `$((name++))` both write.
        The written form inside an expansion is not enumerated here, so every
        name written inside an arithmetic expansion, and every name written
        inside a parameter expansion carrying `=`, is reported unsettled. A
        here-document body expands in the shell that writes it, so the
        expansions written inside one are read as well.
        """

        names: set[str] = set()
        for token in self.records.tokens:
            if token.kind not in (WORD, HEREDOC_KIND):
                continue
            for segment in _expansion_segments(token.segments):
                if segment.kind == ARITHMETIC_SEGMENT or (
                    ASSIGNING_EXPANSION in segment.text
                ):
                    names.update(NAME_PATTERN.findall(segment.text))
        return frozenset(names)

    def unaccepted_constructs(self) -> tuple[str, ...]:
        """Return one description of every construct this checker does not read."""

        if self._unaccepted is None:
            self._unaccepted = _unaccepted_constructs(self.records)
        return self._unaccepted

    def inside_declaration(self, offset: int) -> bool:
        """Report whether one offset is written inside a function body."""

        return any(
            declaration.start.offset <= offset <= declaration.end.offset
            for declaration in self.table.declarations
        )

    def unsettled_names(self) -> frozenset[str]:
        """Return every name whose value this checker cannot settle.

        A fixture that writes any construct this checker does not accept is not
        read at all, and every name written in it is reported. Otherwise the
        answer is a union of the enumerated binding surfaces, so a name is
        settled only where every surface proves it is not bound. The one
        boundary this checker accepts rather than reads is a sourced file: a
        fixture that sources a path gives the sourced bytes the same authority
        as its own, so those bytes stay part of what this checker trusts rather
        than part of what it proves.
        """

        if self._unsettled is None:
            if self.unaccepted_constructs():
                self._unsettled = _written_names(self.records)
                return self._unsettled
            settled = (
                MUTABLE_SHELL_NAMES
                | self.written_assigned_names()
                | self.prefix_assigned_names()
                | self.command_assigned_names()
                | self.loop_assigned_names()
                | self.function_assigned_names()
                | self.inherited_names()
                | self.uncertainly_assigned_names()
                | self.expansion_assigned_names()
            )
            if self._unknown_binding:
                settled = settled | _written_names(self.records)
            self._unsettled = settled
        return self._unsettled

    def loop_extents(self) -> dict[int, int]:
        """Return the end offset of every loop the graph reports."""

        return dict(self._loop_extents)

    def unconditional_positions(self) -> frozenset[int]:
        """Return the offset of every word written to run on every turn."""

        return self._unconditional

    def branch_extents(self) -> tuple[tuple[int, int], ...]:
        """Return the extent of every branch written in the supplied bytes."""

        return self._branch_extents

    def _derive_compound_extents(self) -> tuple[dict[int, int], tuple[tuple[int, int], ...]]:
        """Pair every compound command written here with its terminator.

        A body ends at its written terminator, not at its last command. An
        assignment written as the last statement carries no command word, so a
        window derived from commands alone would leave it outside the body it
        belongs to, and a loop whose body holds only assignments is reported
        by no command at all. Both are read from the checked record stream
        instead, where a reserved word opens or closes a body only when it is
        written where a command may start.
        """

        commands = _command_positions(self.records)
        loops: dict[int, int] = {}
        branches: list[tuple[int, int]] = []
        stack: list[tuple[str, int]] = []
        for token in self.records.tokens:
            if token.kind != WORD or token.start.offset not in commands:
                continue
            offset = token.start.offset
            opener = COMPOUND_TERMINATORS.get(token.text)
            if opener is not None:
                stack.append((token.text, offset))
                continue
            if token.text not in COMPOUND_CLOSERS:
                continue
            while stack:
                keyword, start = stack.pop()
                if COMPOUND_TERMINATORS[keyword] != token.text:
                    continue
                if keyword in BRANCH_KEYWORDS:
                    branches.append((start, offset))
                else:
                    loops[start] = offset
                break
        return loops, tuple(branches)

    def _derive_conditional_spans(self) -> tuple[tuple[int, int], ...]:
        """Return every written extent whose commands may not run where written.

        A branch arm, a loop body, and a function body are all written in the
        supplied bytes, but none of them is guaranteed to run at the point it
        is written: a branch may be untaken, a loop may turn zero times, and a
        function body runs only where it is called. An assignment written
        inside one of these extents therefore may not have replaced the value
        the name held before it.
        """

        spans = list(self._branch_extents)
        spans.extend(self._loop_extents.items())
        for declaration in self.table.declarations:
            spans.append((declaration.start.offset, declaration.end.offset))
        return tuple(spans)

    def _certainly_runs(self, assignment: _Assignment) -> bool:
        """Report whether one assignment certainly runs where it is written."""

        if assignment.offset not in self._unconditional:
            return False
        return not any(
            start <= assignment.offset <= end for start, end in self._conditional_spans
        )

    def _expand_operations(self) -> dict[int, _Expansion]:
        """Expand one bounded level of variable references per operation.

        A fixture that assigns a path to a variable and then runs the variable
        performs the same operation as one that writes the path directly, so a
        prohibition must read the assigned value rather than the written word.
        The assignments that precede one operation are accumulated in a single
        offset-ordered pass, and exactly one level is expanded, so the
        expansion always terminates.

        Only an assignment that certainly runs where it is written replaces
        the value a name already holds. Any other assignment adds a value the
        name may hold, because the value written before it survives when the
        branch is not taken, the loop turns zero times, or the function is
        never called. Every value a name may hold is expanded, so a written
        override never hides an operation that still runs.
        """

        expanded: dict[int, _Expansion] = {}
        values: dict[str, tuple[str, ...]] = {}
        assignments = sorted(self.assignments, key=lambda item: item.offset)
        index = 0
        for operation in self.operations:
            while index < len(assignments) and assignments[index].offset < operation.offset:
                assignment = assignments[index]
                if self._certainly_runs(assignment):
                    values[assignment.name] = (assignment.value,)
                else:
                    held = values.get(assignment.name, ())
                    if assignment.value not in held:
                        values[assignment.name] = held + (assignment.value,)
                index += 1
            expanded[operation.offset] = _expand_all(operation.text, values)
            if operation.node.token is not None:
                expanded[-operation.offset - 1] = _expand_all(
                    " ".join(
                        [operation.node.token.text]
                        + [argument.text for argument in operation.node.arguments]
                    ),
                    values,
                )
        return expanded

    def expansions(self, operation: _Operation) -> tuple[str, ...]:
        """Return every text one operation may carry after one expansion level."""

        return self._expansion(operation.offset, operation.text).texts

    def dispatches(self, operation: _Operation) -> tuple[str, ...]:
        """Return every command word and argument list one operation may run."""

        return self._expansion(-operation.offset - 1, operation.text).texts

    def expansions_are_exact(self, operation: _Operation) -> bool:
        """Report whether each expansion is one text the operation may carry.

        Past the expansion bound the values are joined into one text, which
        proves that a value is present but not that every text carries it. A
        check that admits an operation because all of its texts agree must
        require an exact list.
        """

        return self._expansion(operation.offset, operation.text).exact

    def _expansion(self, key: int, text: str) -> _Expansion:
        return self._expanded.get(key, _Expansion((text,)))

    def _derive_git_operations(self) -> tuple[_Operation, ...]:
        selected: list[_Operation] = []
        for operation in self.operations:
            if operation.node.call_path:
                # The inlined body of a Git wrapper carries `"$@"`, so the
                # call site is the only place the operation words are visible.
                continue
            if operation.name == "git" or operation.name in self.git_wrappers:
                selected.append(operation)
        return tuple(selected)

    def _cleanup_declaration(self) -> shell_functions.FunctionDeclaration | None:
        for operation in self.operations:
            if operation.effect != EFFECT_TRAP:
                continue
            for value in operation.argument_values:
                if value and value in self.table:
                    return self.table[value]
        return None

    @property
    def cleanup_span(self) -> tuple[int, int] | None:
        if self.cleanup is None:
            return None
        return (self.cleanup.start.offset, self.cleanup.end.offset)

    def in_cleanup(self, offset: int) -> bool:
        span = self.cleanup_span
        return span is not None and span[0] <= offset <= span[1]

    def git_operations(self) -> tuple[_Operation, ...]:
        """Return every operation that reaches Git, directly or through a wrapper."""

        return self._git_operations

    def git_subcommand(self, operation: _Operation) -> str | None:
        """Return the Git subcommand of one operation, or None when it runs no Git."""

        return self._git_subcommands.get(operation.offset)

    def matching(self, marker: str) -> tuple[_Operation, ...]:
        lowered = marker.lower()
        return tuple(
            operation
            for operation in self.operations
            if lowered in operation.text.lower()
        )

    def loop_keywords(self) -> dict[int, str | None]:
        keywords: dict[int, str | None] = {}
        for operation in self.operations:
            keywords.update(operation.loop_keywords)
        return keywords

    def loop_condition_operations(self) -> dict[int, list[_Operation]]:
        regions: dict[int, list[_Operation]] = {}
        for operation in self.operations:
            for region in operation.loop_conditions:
                regions.setdefault(region, []).append(operation)
        return regions

    def assignments_after(self, offset: int) -> tuple[_Assignment, ...]:
        return tuple(
            assignment
            for assignment in self.assignments
            if assignment.offset > offset
        )

    def loop_regions(self) -> dict[int, list[_Operation]]:
        regions: dict[int, list[_Operation]] = {}
        for operation in self.operations:
            for region in operation.loop_regions:
                regions.setdefault(region, []).append(operation)
        return regions

    def bindings_before(self, offset: int) -> "_Bindings":
        """Return the settled parts each name may hold before one written offset.

        A shell evaluates an assignment where it is written, so each written
        value is settled against the names bound above it rather than against
        the names bound where the value is later read. A name whose value this
        checker cannot read is bound to ``None``, which proves nothing.
        """

        cached = self._resolved.get(offset)
        if cached is not None:
            return cached
        unsettled = self.unsettled_names()
        bindings: _Bindings = {}
        for assignment in sorted(self.assignments, key=lambda item: item.offset):
            if assignment.offset >= offset:
                break
            self._bind_value(bindings, assignment, unsettled)
        self._resolved[offset] = bindings
        return bindings
    def _bind_value(
        self, bindings: "_Bindings", assignment: _Assignment, unsettled: frozenset[str]
    ) -> None:
        """Bind one written assignment to the parts its value settles to.

        A command substitution is one evaluation, so the parts it produces are
        comparable across two readers only when the assignment that ran it runs
        exactly once. An assignment written under a condition or inside a
        function body may run again with another value, so a value that carries
        a substitution is bound to ``None`` there.
        """

        parts = _word_parts(
            assignment.value,
            f"a{assignment.offset}",
            splits=False,
            anchored=self._anchors_a_substitution(),
        )
        settled = None if parts is None else _resolve_parts(parts, bindings, unsettled)
        single = self._certainly_runs(assignment) and not self._inside_declaration(
            assignment.offset
        )
        if settled is not None and not single and _carries_substitution(settled):
            settled = None
        if self._certainly_runs(assignment):
            bindings[assignment.name] = settled
            return
        _merge_binding(bindings, assignment.name, settled)
    def _anchors_a_substitution(self) -> bool:
        """Report whether the modelled absolute command is the shell's own.

        A fixture may declare a function whose name is the command this
        checker reads as writing an absolute path, and that function writes
        whatever it likes, so no substitution is anchored where one is
        declared.
        """

        return not any(
            declaration.name == ABSOLUTE_SHELL_COMMAND
            for declaration in self.table.declarations
        )
    def _inside_declaration(self, offset: int) -> bool:
        """Report whether one offset is written inside a function body."""

        return any(
            declaration.start.offset <= offset <= declaration.end.offset
            for declaration in self.table.declarations
        )
    def bindings_for(self, operation: _Operation) -> "_Bindings":
        """Return the settled parts each name may hold where one operation runs.

        A function body runs where it is called, not where it is written, so a
        name the body reads carries the value its call site holds. Every
        reachable call environment is added to the environment written above
        the body, and a function called from another function runs where that
        caller runs, so the call sites are followed outward. Each call site is
        visited once and a fixture writes finitely many, so the walk always
        terminates.
        """

        cached = self._settled.get(operation.offset)
        if cached is not None:
            return cached
        bindings: _Bindings = dict(self.bindings_before(operation.offset))
        pending = list(self._call_offsets(operation.offset))
        visited = set(pending)
        while pending:
            offset = pending.pop()
            for name, held in self.bindings_before(offset).items():
                _merge_binding(bindings, name, held)
            for further in self._call_offsets(offset):
                if further not in visited:
                    visited.add(further)
                    pending.append(further)
        self._settled[operation.offset] = bindings
        return bindings
    def _call_offsets(self, offset: int) -> tuple[int, ...]:
        """Return where every reachable call of an enclosing function runs."""

        names = {
            declaration.name
            for declaration in self.table.declarations
            if declaration.start.offset <= offset <= declaration.end.offset
        }
        if not names:
            return ()
        return tuple(
            candidate.offset
            for candidate in self.operations
            if candidate.reachable and candidate.name in names
        )

    def bindings_at(self, run: "_CommandRun") -> "_Bindings | None":
        """Return the settled parts each name may hold where one command run is written.

        A command written inside a function body runs where that body is
        called, so the environment it reads is the one the operation carries
        rather than the one written above it. A run this checker cannot place
        against a written operation reads no environment at all, because a
        smaller environment settles an operand to fewer paths than it may
        name, which would prove a separation the fixture never keeps.
        """

        if not run.words:
            return None
        if self._operations_by_offset is None:
            self._operations_by_offset = {
                operation.offset: operation for operation in self.operations
            }
        operation = self._operations_by_offset.get(run.words[0].start.offset)
        if operation is None:
            # A launched command is recorded at the offset of the word the
            # launcher runs, so the run is placed against the one operation
            # written inside it.
            start = run.tokens[0].start.offset
            end = run.tokens[-1].end.offset
            inside = [
                candidate
                for offset, candidate in self._operations_by_offset.items()
                if start <= offset <= end
            ]
            if len(inside) != 1:
                return None
            operation = inside[0]
        return self.bindings_for(operation)


def _git_subcommand(operation: _Operation) -> tuple[str | None, tuple[str | None, ...]]:
    """Return the Git subcommand of one operation and its remaining words."""

    values = list(operation.argument_values)
    index = 0
    while index < len(values):
        value = values[index]
        if value is None:
            # An unresolved word such as the fixture repository path never
            # names a subcommand, so it is skipped rather than guessed.
            index += 1
            continue
        if value in GIT_VALUE_OPTIONS:
            index += 2
            continue
        if value.startswith("-"):
            index += 1
            continue
        return value, tuple(values[index + 1:])
    return None, ()


_UNRESOLVED = "\0unresolved"


def _takes_value(value: str) -> bool:
    """Report whether one `git tag` option consumes the following word.

    A combined short cluster such as `-am` ends in the option that takes the
    value, exactly as the commit message split already reads `-qm`.
    """

    if value in TAG_VALUE_OPTIONS:
        return True
    if not value.startswith("-") or value.startswith("--") or len(value) < 2:
        return False
    return value[-1] in TAG_VALUE_LETTERS


def _tag_name(values: Sequence[str | None]) -> str | None:
    """Return the version tag one `git tag` operation creates.

    `None` means the operation creates no version tag. `_UNRESOLVED` means it
    creates a tag whose name an expansion decides, which proves that a tag
    exists without proving which version it names. An option that takes a
    value consumes the following word, so an annotated tag message is never
    read as the tag name.
    """

    skip = False
    for value in values:
        if skip:
            skip = False
            continue
        if value is not None and _takes_value(value):
            skip = True
            continue
        if value is not None and value.startswith("-"):
            continue
        if value is None:
            return _UNRESOLVED
        return value if VERSION_TAG_PATTERN.match(value) else None
    return None


def _commit_message(values: Sequence[str | None]) -> str | None:
    for position, value in enumerate(values):
        if value is None:
            continue
        if value == "--message" or (
            value.startswith("-")
            and not value.startswith("--")
            and value.endswith("m")
        ):
            if position + 1 < len(values):
                return values[position + 1]
            return None
        if value.startswith("--message="):
            return value[len("--message="):]
    return None


def _check_version_commits(fixture: _Fixture) -> list[Finding]:
    """Require one distinct preceding commit for every version tag."""

    findings: list[Finding] = []
    commits: list[tuple[_Operation, str | None]] = []
    tags: list[tuple[_Operation, str]] = []
    unresolved: list[_Operation] = []
    for operation in fixture.git_operations():
        subcommand, rest = _git_subcommand(operation)
        if subcommand == "commit":
            commits.append((operation, _commit_message(rest)))
        elif subcommand == "tag":
            name = _tag_name(rest)
            if name is None:
                continue
            if name is _UNRESOLVED:
                unresolved.append(operation)
            else:
                tags.append((operation, name))
    if not any(tag.reachable for tag, _ in tags) and not any(
        tag.reachable for tag in unresolved
    ):
        findings.append(
            Finding(
                RULE_VERSION_COMMIT,
                "no reachable operation creates a version tag",
                tags[0][0].position if tags else None,
            )
        )
    claimed: dict[int, str] = {}
    messages: dict[str, str] = {}
    for tag, name in tags:
        if not tag.reachable:
            findings.append(
                Finding(
                    RULE_VERSION_COMMIT,
                    f"version tag `{name}` is on no reachable execution path",
                    tag.position,
                )
            )
            continue
        preceding = [
            (commit, message)
            for commit, message in commits
            if commit.offset < tag.offset and commit.reachable
        ]
        if not preceding:
            findings.append(
                Finding(
                    RULE_VERSION_COMMIT,
                    f"version tag `{name}` has no reachable preceding commit",
                    tag.position,
                )
            )
            continue
        commit, message = preceding[-1]
        owner = claimed.get(commit.offset)
        if owner is not None:
            findings.append(
                Finding(
                    RULE_VERSION_COMMIT,
                    f"version tags `{owner}` and `{name}` share one commit",
                    tag.position,
                )
            )
            continue
        claimed[commit.offset] = name
        if message is not None:
            duplicate = messages.get(message)
            if duplicate is not None:
                findings.append(
                    Finding(
                        RULE_VERSION_COMMIT,
                        f"version tags `{duplicate}` and `{name}` reuse the "
                        f"commit message `{message}`",
                        tag.position,
                    )
                )
                continue
            messages[message] = name
    return findings


def _references(text: str, name: str) -> bool:
    return f"${name}" in text or f"${{{name}" in text


def _check_inventory_region(fixture: _Fixture) -> list[Finding]:
    """Require one inventory-driven copy and staging region."""

    findings: list[Finding] = []
    regions = fixture.loop_regions()
    inventory_regions: list[int] = []
    for region, operations in regions.items():
        reads = [operation for operation in operations if operation.name == "read"]
        copies = [operation for operation in operations if operation.name in COPY_COMMANDS]
        stages = [
            operation
            for operation in operations
            if fixture.git_subcommand(operation) == "add"
        ]
        if reads and copies and stages:
            inventory_regions.append(region)
    if not inventory_regions:
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                "no loop reads one inventory and both copies and stages its paths",
            )
        )
        return findings
    if len(inventory_regions) > 1:
        for region in sorted(inventory_regions)[1:]:
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "more than one inventory copy and staging region is present",
                    regions[region][0].position,
                )
            )
        return findings
    region = inventory_regions[0]
    operations = regions[region]
    read = next(operation for operation in operations if operation.name == "read")
    variables = [
        value
        for value in read.argument_values
        if value and not value.startswith("-")
    ]
    copies = [operation for operation in operations if operation.name in COPY_COMMANDS]
    stages = [
        operation
        for operation in operations
        if fixture.git_subcommand(operation) == "add"
    ]
    if len(copies) > 1:
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                "the inventory region copies more than once",
                copies[1].position,
            )
        )
    if len(stages) > 1:
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                "the inventory region stages more than once",
                stages[1].position,
            )
        )
    copy = copies[0]
    stage = stages[0]
    if not variables:
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                "the inventory loop reads no exact variable name",
                read.position,
            )
        )
        return findings
    variable = variables[0]
    if not _references(copy.text, variable):
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                f"the inventory copy is not derived from `{variable}`",
                copy.position,
            )
        )
    if not _references(stage.text, variable):
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                f"the inventory staging is not derived from `{variable}`",
                stage.position,
            )
        )
    if stage.offset < copy.offset:
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                "the inventory region stages the path before copying it",
                stage.position,
            )
        )
    if not copy.reachable or not stage.reachable:
        findings.append(
            Finding(
                RULE_INVENTORY_REGION,
                "the inventory copy and staging region is unreachable",
                copy.position,
            )
        )
    for operation in fixture.operations:
        if operation.offset == copy.offset or operation.offset == stage.offset:
            continue
        if region in operation.loop_regions:
            continue
        if not _references(operation.text, variable):
            continue
        if operation.name in COPY_COMMANDS:
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    f"a copy outside the inventory region uses `{variable}`",
                    operation.position,
                )
            )
        elif fixture.git_subcommand(operation) == "add":
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    f"staging outside the inventory region uses `{variable}`",
                    operation.position,
                )
            )
    return findings


def _check_direct_invocation(fixture: _Fixture) -> list[Finding]:
    """Reject a direct snapshot or `copier` dispatch inside the fixture."""

    findings: list[Finding] = []
    for operation in fixture.operations:
        if _invokes_snapshot(fixture, operation):
            findings.append(
                Finding(
                    RULE_DIRECT_INVOCATION,
                    "the fixture invokes the migration snapshot script directly",
                    operation.position,
                )
            )
        if operation.name == COPIER_MARKER:
            findings.append(
                Finding(
                    RULE_DIRECT_INVOCATION,
                    "the fixture dispatches the `copier` binary directly",
                    operation.position,
                )
            )
    return findings


def _invokes_snapshot(fixture: _Fixture, operation: _Operation) -> bool:
    """Report whether one command dispatches the migration snapshot script.

    Naming the script is not running it: a fixture legitimately asserts that
    the managed script exists or is listed in the inventory. Only the command
    word, or the script argument of an interpreter, is a dispatch. Every value
    an expansion may carry is read, because one of them is what runs.
    """

    if operation.node.token is None:
        return False
    return any(
        _dispatch_invokes_snapshot(fixture, operation, dispatch)
        for dispatch in fixture.dispatches(operation)
    )


def _dispatch_invokes_snapshot(
    fixture: _Fixture, operation: _Operation, dispatch: str
) -> bool:
    word = dispatch.split(" ", 1)[0]
    if SNAPSHOT_MARKER in word:
        return True
    if SNAPSHOT_MARKER not in dispatch:
        return False
    if _is_interpreter(word) or _strip(word) in COMMAND_PREFIXES:
        return True
    return _forwards_to_interpreter(fixture, operation.name)


def _strip(word: str) -> str:
    """Return one written word without its surrounding quote characters."""

    return word.strip("\"'")


def _is_interpreter(word: str) -> bool:
    """Report whether one written command word runs a script it is given."""

    return INTERPRETER_PATTERN.match(_strip(word).rsplit("/", 1)[-1]) is not None


def _forwards_to_interpreter(fixture: _Fixture, name: str | None) -> bool:
    """Report whether a declared function runs an interpreter on its arguments.

    A fixture that wraps an interpreter in a helper passes the script path at
    the call site, which is the only place the path is written. One bounded
    level is inspected, so the check always terminates.
    """

    if name is None or name not in fixture.table:
        return False
    for command in _declaration_commands(fixture.table[name]):
        if _is_interpreter(command.name or "") and POSITIONAL_PATTERN.search(command.text):
            return True
    return False


def _expand(text: str, values: dict[str, str]) -> str:
    """Expand one bounded level of variable references in one command.

    A fixture that assigns a path to a variable and then runs the variable
    performs the same operation as one that writes the path directly, so the
    prohibition must read the assigned value rather than the written word.
    Exactly one level is expanded, so the expansion always terminates.
    """

    if "$" not in text:
        return text
    return EXPANSION_PATTERN.sub(
        lambda match: values.get(match.group(1) or match.group(2), match.group(0)), text
    )


def _referenced(text: str) -> tuple[str, ...]:
    """Return every variable name one command references, in written order."""

    names: list[str] = []
    for match in EXPANSION_PATTERN.finditer(text):
        name = match.group(1) or match.group(2)
        if name not in names:
            names.append(name)
    return tuple(names)


@dataclass(frozen=True)
class _Expansion:
    """Every text one operation may carry, and whether that list is exact."""

    texts: tuple[str, ...]
    exact: bool = True
    """Whether each text is one combination the operation may actually carry.

    A joined fallback text carries several values of one name at once, so it
    proves that a value is present but never that every text carries it. A
    check that admits an operation because all of its texts agree must refuse
    to read an inexact list, or the agreement it reads is manufactured.
    """


def _expand_all(text: str, values: dict[str, tuple[str, ...]]) -> _Expansion:
    """Return one expansion for every combination of values the names may hold.

    A name whose value a branch, a loop, or a call decides holds one of
    several written values, and reading only one of them would let a written
    override hide an operation that still runs. Every combination is read
    instead. The combination count is bounded: past the bound one text is
    returned in which each unresolved name carries all of its values at once,
    so a prohibition still reads every value while the work stays finite. That
    text is reported as inexact, because collapsing the combinations into one
    text would otherwise turn agreement across texts into a single match.
    """

    if "$" not in text:
        return _Expansion((text,))
    names = tuple(name for name in _referenced(text) if name in values)
    if not names:
        return _Expansion((text,))
    combinations = 1
    for name in names:
        combinations *= len(values[name])
    if combinations > MAX_EXPANSIONS:
        joined = _expand(
            text, {name: UNRESOLVED_JOINER.join(values[name]) for name in names}
        )
        return _Expansion((joined,), exact=False)
    expansions: list[str] = []
    for combination in itertools.product(*(values[name] for name in names)):
        expanded = _expand(text, dict(zip(names, combination)))
        if expanded not in expansions:
            expansions.append(expanded)
    return _Expansion(tuple(expansions))


def _mentions(text: str, marker: str) -> bool:
    return marker in text.lower()


def _check_update_child(
    fixture: _Fixture,
) -> tuple[list[Finding], _Operation | None]:
    findings: list[Finding] = []
    children = [operation for operation in fixture.operations if operation.asynchronous]
    if not children:
        findings.append(
            Finding(
                RULE_UPDATE_CHILD,
                "the transition starts no asynchronous update child",
                _transition_anchor(fixture),
            )
        )
        return findings, None
    for extra in children[1:]:
        findings.append(
            Finding(
                RULE_UPDATE_CHILD,
                "more than one asynchronous update child is started",
                extra.position,
            )
        )
    child = children[0]
    if UPDATE_WRAPPER_MARKER not in child.text:
        findings.append(
            Finding(
                RULE_UPDATE_CHILD,
                "the asynchronous update child does not run the update wrapper",
                child.position,
            )
        )
    if not child.reachable:
        findings.append(
            Finding(
                RULE_UPDATE_CHILD,
                "the asynchronous update child is on no reachable execution path",
                child.position,
            )
        )
    if child.skippable(STARTED_ANYWAY):
        findings.append(
            Finding(
                RULE_UPDATE_CHILD,
                "the asynchronous update child can be skipped",
                child.position,
            )
        )
    return findings, child


def _check_child_pid(fixture: _Fixture, child: _Operation) -> tuple[list[Finding], str | None]:
    findings: list[Finding] = []
    following = fixture.assignments_after(child.offset)
    if not following or "$!" not in following[0].value:
        findings.append(
            Finding(
                RULE_CHILD_PID,
                "the update child PID is not captured by the next assignment",
                child.position,
            )
        )
        return findings, None
    return findings, following[0].name


def _check_bounded_polls(fixture: _Fixture) -> list[Finding]:
    findings: list[Finding] = []
    regions = fixture.loop_regions()
    keywords = fixture.loop_keywords()
    polls: list[int] = []
    for region, operations in regions.items():
        if any(operation.name == "sleep" for operation in operations):
            polls.append(region)
    if len(polls) < 2:
        findings.append(
            Finding(
                RULE_BOUNDED_POLL,
                "the transition does not run both bounded polling loops",
                None if not polls else regions[polls[0]][0].position,
            )
        )
    extents = fixture.loop_extents()
    for region in sorted(polls):
        operations = regions[region]
        end = extents.get(region, max(operation.offset for operation in operations))
        # A nested loop proves nothing about the loop that holds it: its
        # counter and its `break` bound the inner loop only. Boundedness is
        # therefore proved from the operations this loop owns directly.
        owned = tuple(
            operation
            for operation in operations
            if operation.loop_regions and operation.loop_regions[-1] == region
        )
        nested = tuple(
            (start, extents.get(start, end))
            for start in extents
            if region < start <= end
        )
        counted = {
            assignment.name
            for assignment in fixture.assignments
            if region <= assignment.offset <= end
            and ARITHMETIC_MARKER in assignment.value
            and not any(start <= assignment.offset <= stop for start, stop in nested)
        }
        keyword = keywords.get(region)
        if keyword == LOOP_WORD_LIST:
            pass
        elif not counted:
            findings.append(
                Finding(
                    RULE_BOUNDED_POLL,
                    "a polling loop maintains no counter",
                    operations[0].position,
                )
            )
        elif not _counts_down(fixture, region, counted, owned, operations):
            findings.append(
                Finding(
                    RULE_BOUNDED_POLL,
                    "a polling loop does not test its own counter to stop",
                    operations[0].position,
                )
            )
        if not any(operation.reachable for operation in operations):
            findings.append(
                Finding(
                    RULE_BOUNDED_POLL,
                    "a polling loop is on no reachable execution path",
                    operations[0].position,
                )
            )
    return findings


def _counts_down(
    fixture: _Fixture,
    region: int,
    counted: set[str],
    owned: tuple[_Operation, ...],
    operations: tuple[_Operation, ...],
) -> bool:
    """Report whether a loop stops because of the counter it maintains.

    A counter that nothing tests bounds nothing: `while true` with a counter
    in its body still runs forever. The test is written in one of two places,
    and both stop the loop after a fixed number of turns: the loop's own
    continuation condition, or a test inside the body that guards an exit.

    A continuation condition proves a bound only when every turn reaches the
    counter. A `continue` written in the body can skip the increment, and an
    increment written inside a branch runs only on some turns, so neither
    loop is bounded by its condition.
    """

    conditions = fixture.loop_condition_operations().get(region, ())
    tested = {
        name
        for name in counted
        for operation in conditions
        if _reads(operation.text, name)
    }
    if tested and not any(
        operation.effect == EFFECT_CONTINUE for operation in owned
    ):
        if any(_increments_every_turn(fixture, region, name) for name in tested):
            return True
    return _guards_exit(fixture, counted, owned, operations)


def _increments_every_turn(fixture: _Fixture, region: int, name: str) -> bool:
    """Report whether one counter is raised outside every branch of a loop."""

    end = fixture.loop_extents().get(region)
    if end is None:
        return False
    branches = fixture.branch_extents()
    sequenced = fixture.unconditional_positions()
    for assignment in fixture.assignments:
        if assignment.name != name or not region <= assignment.offset <= end:
            continue
        if ARITHMETIC_MARKER not in assignment.value:
            continue
        if assignment.offset not in sequenced:
            continue
        if any(start <= assignment.offset <= stop for start, stop in branches):
            continue
        return True
    return False


def _reads(text: str, name: str) -> bool:
    """Report whether one written command reads the named variable.

    A name is read through an expansion (`$name`, `${name}`) or bare inside an
    arithmetic expansion, so both written forms count.
    """

    if re.search(rf"\$[({{]*\s*{re.escape(name)}\b", text) is not None:
        return True
    if ARITHMETIC_MARKER not in text:
        return False
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text) is not None


def _guards_exit(
    fixture: _Fixture,
    counted: set[str],
    owned: tuple[_Operation, ...],
    operations: tuple[_Operation, ...],
) -> bool:
    """Report whether a counter test guards a bounded exit inside the loop.

    An exit is guarded in one of two written ways. A branch records the
    condition and the guarded commands under one shared enclosure record, so
    the counter test and the exit it protects are recognised by that shared
    record. An and-or list and a `case` arm carry no such condition record,
    and there the guard is the command written immediately before the exit.

    Only the innermost enclosure of the exit counts, because an exit merely
    nested beneath the counter test is decided by whatever test is written
    closest to it. A `break` bounds only the loop that owns it, while `exit`
    ends the script and so bounds every loop written around it.
    """

    guarding: set[int] = set()
    for operation in operations:
        if not any(_reads(operation.text, name) for name in counted):
            continue
        for enclosure in operation.node.enclosures:
            if enclosure.kind == CONDITION and enclosure.token is not None:
                guarding.add(enclosure.token.start.offset)
    exits = [
        operation
        for operation in owned
        if operation.effect in LOOP_EXIT_EFFECTS or operation.name == "exit"
    ]
    exits.extend(
        operation
        for operation in operations
        if operation not in exits
        and (operation.effect == EFFECT_EXIT or operation.name == "exit")
    )
    for operation in exits:
        if not operation.node.enclosures:
            continue
        innermost = operation.node.enclosures[-1]
        if innermost.token is not None and innermost.token.start.offset in guarding:
            return True
        if innermost.kind not in PRECEDED_ENCLOSURES or innermost.token is None:
            continue
        offset = innermost.token.start.offset
        if innermost.kind == CASE_ARM:
            subject = _case_subject(fixture, offset)
            if any(_reads(subject, name) for name in counted):
                return True
            continue
        if _preceding_test(counted, operations, offset):
            return True
    return False


def _case_subject(fixture: _Fixture, offset: int) -> str:
    """Return the word a `case` written before one arm selects on.

    A `case` head carries its subject in the command word itself, which the
    graph reports without a position, so the subject is read back from the
    checked record stream instead.
    """

    index = _token_index(fixture.records)
    located = index.get(offset)
    if located is None:
        return ""
    region, position = located
    commands = _command_positions(fixture.records)
    start = None
    depth = 0
    for candidate in range(position - 1, -1, -1):
        token = region[candidate]
        if token.kind != WORD:
            continue
        if token.text == CASE_TERMINATOR and token.start.offset in commands:
            depth += 1
            continue
        if token.text != CASE_KEYWORD or token.start.offset not in commands:
            continue
        if depth:
            depth -= 1
            continue
        start = candidate
        break
    if start is None:
        return ""
    words: list[str] = []
    for candidate in range(start + 1, position):
        if region[candidate].text == CASE_SUBJECT_END:
            break
        words.append(region[candidate].text)
    return " ".join(words)


def _preceding_test(
    counted: set[str], operations: tuple[_Operation, ...], offset: int
) -> bool:
    """Report whether the command written before one position reads a counter."""

    preceding = [
        operation for operation in operations if operation.offset < offset
    ]
    if not preceding:
        return False
    nearest = max(preceding, key=lambda operation: operation.offset)
    return any(_reads(nearest.text, name) for name in counted)


@dataclass(frozen=True)
class _CleanupCommand:
    """One command written in the registered cleanup handler."""

    name: str | None
    word: str | None
    text: str
    redirect_targets: tuple[str, ...]


def _cleanup_commands(fixture: _Fixture) -> tuple[_CleanupCommand, ...]:
    """Split the cleanup handler body into its written commands.

    A cleanup requirement names one command and one subject, so the two must
    be read from the same command. Matching two markers anywhere in the body
    would accept a handler that stops an unrelated process and merely mentions
    the required subject somewhere else.
    """

    if fixture.cleanup is None:
        return ()
    return _declaration_commands(fixture.cleanup)


def _declaration_commands(
    declaration: shell_functions.FunctionDeclaration,
) -> tuple[_CleanupCommand, ...]:
    """Split one declared function body into its written commands."""

    commands: list[_CleanupCommand] = []
    for span in _split_commands(declaration.body):
        name: str | None = None
        word: str | None = None
        targets: list[str] = []
        pending_target = False
        for token in span:
            if token.kind == shell_lexical.OPERATOR:
                pending_target = token.text in WRITE_REDIRECTIONS
                continue
            if token.kind != shell_lexical.WORD:
                pending_target = False
                continue
            if pending_target:
                targets.append(token.text)
                pending_target = False
                continue
            if word is not None:
                continue
            if ASSIGNMENT_PATTERN.match(_assignment_prefix(token)) is not None:
                continue
            value = token.literal_value
            # A reserved word written before a command on the same line is an
            # ordinary word record, so it must be skipped instead of being
            # read as the command the body runs.
            if value in RESERVED_WORDS:
                continue
            # The written word is kept even when the projection cannot resolve
            # it, because a command word the fixture builds from an expansion
            # still says which position the command runs from.
            word = token.text
            name = value
        commands.append(
            _CleanupCommand(
                name=name,
                word=word,
                text=" ".join(token.text for token in span),
                redirect_targets=tuple(targets),
            )
        )
    return tuple(commands)


def _split_commands(tokens: tuple[Token, ...]) -> tuple[tuple[Token, ...], ...]:
    """Split a projected record sequence on every command separator."""

    spans: list[tuple[Token, ...]] = []
    current: list[Token] = []
    for token in tokens:
        if token.kind == shell_lexical.LINE_CONTINUATION:
            continue
        separates = token.kind == NEWLINE or (
            token.kind == OPERATOR and token.text not in REDIRECTIONS
        )
        if separates or token.kind in (shell_lexical.COMMENT, shell_lexical.HEREDOC_BODY):
            if current:
                spans.append(tuple(current))
                current = []
            continue
        current.append(token)
    if current:
        spans.append(tuple(current))
    return tuple(spans)


def _performs_release(operation: _Operation | _CleanupCommand) -> bool:
    """Report whether one command performs the release of the named path."""

    if not _mentions(operation.text, RELEASE_MARKER):
        return False
    if operation.name in RELEASE_COMMANDS:
        return True
    return any(
        _mentions(target, RELEASE_MARKER) for target in operation.redirect_targets
    )


def _transition_anchor(fixture: _Fixture) -> Position | None:
    """Return the position of the first written transition event."""

    for operation in fixture.operations:
        if not operation.reachable:
            continue
        if any(_mentions(operation.text, marker) for marker in TRANSITION_MARKERS):
            return operation.position
    return None


def _is_transition(fixture: _Fixture) -> bool:
    """Report whether the supplied fixture writes a bounded migration transition."""

    if any(operation.asynchronous for operation in fixture.operations):
        return True
    return _transition_anchor(fixture) is not None


def _check_release_paths(fixture: _Fixture) -> tuple[list[Finding], _Operation | None]:
    findings: list[Finding] = []
    if fixture.cleanup is None:
        findings.append(
            Finding(
                RULE_RELEASE_PATH,
                "the transition registers no cleanup handler for the release path",
            )
        )
    releases = [
        operation
        for operation in fixture.matching(RELEASE_MARKER)
        if not fixture.in_cleanup(operation.offset)
        and operation.reachable
        and _performs_release(operation)
    ]
    normal = [operation for operation in releases if not operation.conditional]
    conditional = [operation for operation in releases if operation.conditional]
    if not normal:
        findings.append(
            Finding(
                RULE_RELEASE_PATH,
                "the transition has no unconditional before-stage release path",
                releases[0].position if releases else None,
            )
        )
    if not conditional:
        findings.append(
            Finding(
                RULE_RELEASE_PATH,
                "the transition has no ready-failure release path",
                releases[0].position if releases else None,
            )
        )
    if fixture.cleanup is not None and not any(
        _performs_release(command) for command in _cleanup_commands(fixture)
    ):
        findings.append(
            Finding(
                RULE_RELEASE_PATH,
                "the cleanup handler runs no before-stage release path",
                fixture.cleanup.start,
            )
        )
    ordered = normal or releases
    first = min(ordered, key=lambda operation: operation.offset) if ordered else None
    if first is not None:
        ready = [
            operation
            for operation in fixture.matching(READY_MARKER)
            if operation.reachable and operation.offset < first.offset
        ]
        if not ready:
            findings.append(
                Finding(
                    RULE_RELEASE_PATH,
                    "the before stage is released before the ready event is observed",
                    first.position,
                )
            )
    return findings, first


def _check_state_order(
    fixture: _Fixture, release: _Operation | None, final_wait: _Operation | None
) -> list[Finding]:
    findings: list[Finding] = []
    pending = [
        operation
        for operation in fixture.matching(PENDING_MARKER)
        if operation.reachable and not fixture.in_cleanup(operation.offset)
    ]
    consumed = [
        operation
        for operation in fixture.matching(CONSUMED_MARKER)
        if operation.reachable and not fixture.in_cleanup(operation.offset)
    ]
    if not pending:
        findings.append(
            Finding(
                RULE_STATE_ORDER,
                "the transition never asserts the pending attempt state",
            )
        )
    else:
        first_pending = min(pending, key=lambda operation: operation.offset)
        if release is not None and first_pending.offset > release.offset:
            findings.append(
                Finding(
                    RULE_STATE_ORDER,
                    "the pending attempt state is asserted after the before-stage release",
                    release.position,
                )
            )
        if first_pending.conditional:
            findings.append(
                Finding(
                    RULE_STATE_ORDER,
                    "the pending attempt state assertion can be skipped",
                    first_pending.position,
                )
            )
    if not consumed:
        findings.append(
            Finding(
                RULE_STATE_ORDER,
                "the transition never asserts the consumed attempt state",
            )
        )
        return findings
    last_consumed = max(consumed, key=lambda operation: operation.offset)
    if final_wait is not None and last_consumed.offset < final_wait.offset:
        findings.append(
            Finding(
                RULE_STATE_ORDER,
                "the consumed attempt state is asserted before the update child is reaped",
                last_consumed.position,
            )
        )
    if pending and last_consumed.offset < min(
        operation.offset for operation in pending
    ):
        findings.append(
            Finding(
                RULE_STATE_ORDER,
                "the consumed attempt state is asserted before the pending state",
                last_consumed.position,
            )
        )
    if last_consumed.conditional:
        findings.append(
            Finding(
                RULE_STATE_ORDER,
                "the consumed attempt state assertion can be skipped",
                last_consumed.position,
            )
        )
    return findings


def _targets(operation: _Operation, pid_name: str | None) -> bool:
    """Report whether one command names the captured update-child PID.

    A termination or reap that names another process does not terminate or
    reap the update child, so the operation must expand the exact variable the
    fixture captured `$!` into.
    """

    if pid_name is None:
        return True
    return f"${pid_name}" in operation.text or f"${{{pid_name}}}" in operation.text


def _signalled(operation: _Operation, signals: Iterable[str]) -> bool:
    lowered = operation.text.lower()
    return any(f"-{signal}" in lowered or f"-s {signal}" in lowered for signal in signals)


def _check_child_reap(
    fixture: _Fixture, child: _Operation, pid_name: str | None
) -> tuple[list[Finding], _Operation | None]:
    findings: list[Finding] = []
    waits = [
        operation
        for operation in fixture.operations
        if operation.name == "wait"
        and operation.reachable
        and operation.offset > child.offset
        and not fixture.in_cleanup(operation.offset)
        and (not operation.argument_values or _targets(operation, pid_name))
    ]
    kills = [
        operation
        for operation in fixture.operations
        if operation.name == "kill"
        and operation.reachable
        and operation.offset > child.offset
        and not fixture.in_cleanup(operation.offset)
        and _targets(operation, pid_name)
    ]
    terminations = [operation for operation in kills if _signalled(operation, TERMINATION_SIGNALS)]
    forced = [operation for operation in kills if _signalled(operation, FORCED_SIGNALS)]
    if not waits:
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the transition never waits for the update child",
                child.position,
            )
        )
        return findings, None
    if not terminations:
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the transition never terminates the update child",
                child.position,
            )
        )
        return findings, None
    termination = terminations[0]
    if not any(wait.offset < termination.offset for wait in waits):
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the update child is terminated before the bounded wait",
                termination.position,
            )
        )
    grace = [
        operation
        for operation in fixture.operations
        if operation.name == "sleep"
        and operation.reachable
        and operation.offset > termination.offset
    ]
    if not grace:
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the update child gets no grace period after termination",
                termination.position,
            )
        )
    forced_after = [
        operation for operation in forced if operation.offset > termination.offset
    ]
    if not forced_after:
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the update child is never forcibly terminated after the grace period",
                termination.position,
            )
        )
        return findings, None
    force = forced_after[0]
    if grace and not any(
        termination.offset < operation.offset < force.offset for operation in grace
    ):
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the grace period does not separate termination from forced termination",
                force.position,
            )
        )
    final = [wait for wait in waits if wait.offset > force.offset]
    if not final:
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the update child is never reaped after forced termination",
                force.position,
            )
        )
        return findings, None
    final_wait = final[0]
    if final_wait.conditional:
        findings.append(
            Finding(
                RULE_CHILD_REAP,
                "the final update-child reap can be skipped",
                final_wait.position,
            )
        )
    if pid_name is not None:
        cleared = [
            assignment
            for assignment in fixture.assignments
            if assignment.name == pid_name
            and assignment.offset > final_wait.offset
            and assignment.is_empty
        ]
        if not cleared:
            findings.append(
                Finding(
                    RULE_CHILD_REAP,
                    f"the update child PID `{pid_name}` is not cleared after the reap",
                    final_wait.position,
                )
            )
    return findings, final_wait


def _check_guardian(fixture: _Fixture) -> list[Finding]:
    findings: list[Finding] = []
    checks = [
        operation
        for operation in fixture.operations
        if operation.reachable
        and _mentions(operation.text, GUARDIAN_MARKER)
        and _mentions(operation.text, PID_MARKER)
        and "-gt" in operation.argument_values
        and "0" in operation.argument_values
    ]
    if not checks:
        findings.append(
            Finding(
                RULE_GUARDIAN,
                "the transition never proves the guardian PID is positive",
            )
        )
    elif all(check.conditional for check in checks):
        findings.append(
            Finding(
                RULE_GUARDIAN,
                "the guardian PID assertion can be skipped",
                checks[0].position,
            )
        )
    if fixture.cleanup is None:
        findings.append(
            Finding(
                RULE_GUARDIAN,
                "the transition registers no cleanup handler for the guardian",
            )
        )
    elif not any(
        command.name == "kill" and _mentions(command.text, GUARDIAN_MARKER)
        for command in _cleanup_commands(fixture)
    ):
        findings.append(
            Finding(
                RULE_GUARDIAN,
                "the cleanup handler never stops the detached guardian",
                fixture.cleanup.start,
            )
        )
    return findings


def _check_alternate_paths(fixture: _Fixture, child: _Operation) -> list[Finding]:
    """Reject every Copier update path that may reach the sanctioned destination.

    An alternate path is read wherever it is written, not only while the update
    child is live, because a second update before or after the child changes
    the same project through an unbounded path. A dispatch is accepted only
    when this checker proves that the directory it updates is written apart
    from the directory the update child updates, so a destination it cannot
    read is rejected exactly as the blanket prohibition rejected it.
    """

    reserved = _update_destinations(fixture, child)
    links, unplaced = _symlinked_paths(fixture)
    findings: list[Finding] = []
    for operation in fixture.operations:
        if operation.offset == child.offset or not operation.reachable:
            continue
        if not _runs_an_update(fixture, operation):
            continue
        if _updates_a_separate_project(
            fixture, operation, reserved, links, unplaced
        ):
            continue
        findings.append(
            Finding(
                RULE_ALTERNATE_PATH,
                "a second Copier update path runs outside the update child",
                operation.position,
            )
        )
    return findings


def _check_copier_writes(fixture: _Fixture, child: _Operation) -> list[Finding]:
    """Reject every unmodelled Copier copy or recopy of the sanctioned destination.

    A copy is not an update, so it is never read as an alternate update path.
    It still writes a whole project, so a copy this checker proves to reach the
    destination the update child updates removes the project the transition is
    proving. The fixture must create that project once before it starts the
    child, so the one write proven to run before the child is the modelled
    creation and every other proven write is rejected.

    Only a proven reach is rejected. A destination that settles nothing proves
    nothing about which project it writes, so it stays accepted, which is what
    keeps the fixture's unsettleable lane copy passing. A destination the
    checker does read is kept apart only when the written text says so, exactly
    as the alternate-path prohibition keeps two update destinations apart.
    """

    reserved = _update_destinations(fixture, child)
    findings: list[Finding] = []
    created = False
    for operation in sorted(fixture.operations, key=lambda found: found.offset):
        if not operation.reachable:
            continue
        if not _writes_a_reserved_path(
            reserved, _copy_destinations(fixture, operation)
        ):
            continue
        if not created and _precedes_the_child(fixture, operation, child):
            created = True
            continue
        findings.append(
            Finding(
                RULE_ALTERNATE_PATH,
                "an unmodelled Copier copy path writes the sanctioned destination",
                operation.position,
            )
        )
    return findings


def _precedes_the_child(
    fixture: _Fixture, operation: _Operation, child: _Operation
) -> bool:
    """Report whether one written write is proven to run before the update child.

    Only a write whose written place is its running place is read as the
    creation. A write inside a function body runs wherever the body is called,
    and a write inside a region that reaches past the child runs again on a
    later turn, so neither is proven to run first and neither takes the one
    exemption this rule grants.
    """

    if operation.offset >= child.offset:
        return False
    if fixture.inside_declaration(operation.offset):
        return False
    regions = list(fixture.loop_extents().items()) + list(fixture.branch_extents())
    return not any(
        start <= operation.offset and end >= child.offset for start, end in regions
    )


def _writes_a_reserved_path(
    reserved: frozenset[_Path], candidate: frozenset[_Path]
) -> bool:
    """Report whether one written destination is proven to reach a reserved one.

    A destination this checker settles nothing for is not read at all and never
    reaches anything, which is the one exemption the committed fixture's lane
    copy needs. Every destination it does read is answered by the same written
    separation the alternate-path prohibition reads, so an unread child
    destination reserves everything and this rule is never weaker than the
    prohibition it is modelled on.
    """

    if not candidate:
        return False
    return not _paths_are_lexically_separate(reserved, candidate)


def _updates_a_separate_project(
    fixture: _Fixture,
    operation: _Operation,
    reserved: frozenset[_Path],
    links: frozenset[_Path],
    unplaced: bool,
) -> bool:
    """Report whether one dispatch updates a directory written apart from the child's.

    Both destinations must be read, they must be written apart, and no alias
    the fixture may write may name a directory that holds either of them. A
    link this checker cannot place leaves every destination unproven, because
    an unseen link is what makes two separately written paths name one
    directory.
    """

    if unplaced or not reserved:
        return False
    candidate = _update_destinations(fixture, operation)
    if not _paths_are_lexically_separate(reserved, candidate):
        return False
    return not any(
        _holds_a_path(link, path)
        for link in links
        for path in reserved | candidate
    )


def _holds_a_path(link: _Path, path: _Path) -> bool:
    """Report whether one alias may name a directory that holds one path.

    Only an alias written apart from the path never reaches it. An alias
    written inside the path is not exempt: an update walks into the directory
    it changes, so a link written anywhere under that directory redirects the
    walk to whatever it names, which is how two separately written paths come
    to name one project.
    """

    return not _lexically_separate(link, path)


def _run_for(fixture: _Fixture, operation: _Operation) -> _CommandRun | None:
    """Return the written command run one operation is read from.

    An operation is recorded at the offset of the word the shell runs, so a
    launched command is placed against the one run that writes it. A run this
    checker cannot place against exactly one operation reads nothing, because
    a smaller reading settles a destination this fixture never keeps.
    """

    runs = fixture.command_runs()
    named = [
        run
        for run in runs
        if run.words and run.words[0].start.offset == operation.offset
    ]
    if len(named) == 1:
        return named[0]
    inside = [
        run
        for run in runs
        if run.words
        and run.tokens[0].start.offset <= operation.offset <= run.tokens[-1].end.offset
    ]
    if len(inside) == 1:
        return inside[0]
    return None


def _command_word_places(literals: tuple[str | None, ...]) -> tuple[int, ...]:
    """Return every place one command run may write its command word at.

    A launcher runs the command written after its own options, so the command
    word of a dispatch is either the first word or the word one bounded chain
    of launchers reaches. A word this checker cannot read ends the chain,
    because no written text says what it launches.
    """

    places: list[int] = []
    place = 0
    for _ in range(LAUNCHER_ROUNDS):
        if place >= len(literals):
            break
        places.append(place)
        literal = literals[place]
        if literal is None or _basename(literal) not in LAUNCHER_WORDS:
            break
        place += 1
        while place < len(literals):
            written = literals[place]
            if written is None:
                break
            if written.startswith(OPTION_MARK) and written != OPTION_END:
                place += 1
                continue
            if "=" in written and not written.startswith(OPTION_MARK):
                place += 1
                continue
            if written == OPTION_END:
                place += 1
            break
    return tuple(places)


def _workflow_destinations(
    paths: frozenset[_Path], directory: frozenset[_Path]
) -> frozenset[_Path] | None:
    """Return the project each installed-workflow path updates.

    A command word written inside the installed workflow directory runs
    against the project that holds it, so the destination is the path above
    that directory. A word that may name such a script proves no destination
    unless every path it may name is one, because the path this checker cannot
    place is the one that runs.

    A word that writes nothing above the installed workflow directory names
    the project its working directory decides, so it is placed only when the
    subshell that runs it settles one directory of its own.
    """

    if not paths or not any(
        WORKFLOW_DIRECTORY in segments for _, segments in paths
    ):
        return None
    destinations: set[_Path] = set()
    for anchored, segments in paths:
        if WORKFLOW_DIRECTORY not in segments:
            return frozenset()
        index = segments.index(WORKFLOW_DIRECTORY)
        if index + 1 >= len(segments):
            # The directory itself is not a script the shell runs.
            return frozenset()
        if not index and not anchored:
            # Nothing is written above the workflow directory, so the project
            # it belongs to is the one the working directory decides.
            if not directory:
                return frozenset()
            destinations.update(directory)
            continue
        destinations.add((anchored, segments[:index]))
    return frozenset(destinations)


def _subshell_marks(operation: _Operation) -> tuple[int, ...] | None:
    """Return where every enclosure around one operation opens.

    An enclosure this checker cannot place has no offset to compare, so the
    whole path is unread rather than compared against a missing one.
    """

    marks: list[int] = []
    for enclosure in operation.node.enclosures:
        if enclosure.token is None:
            return None
        marks.append(enclosure.token.start.offset)
    return tuple(marks)


def _inside_subshell(operation: _Operation, mark: int) -> bool:
    """Report whether one operation runs inside the subshell opened at a mark."""

    return any(
        enclosure.kind == SUBSHELL_ENCLOSURE
        and enclosure.token is not None
        and enclosure.token.start.offset == mark
        for enclosure in operation.node.enclosures
    )


def _subshell_directory(
    fixture: _Fixture, operation: _Operation
) -> frozenset[_Path]:
    """Return the one directory one subshell settles for the operation it runs.

    A relative command word is placed only when its own subshell writes the
    directory it runs in and nothing else it runs can write another one. The
    subshell must therefore hold exactly two operations, the word and one
    directory change written before it on the same enclosure path, and that
    change must settle to one anchored path.

    Reading the whole subshell rather than the operations written before the
    word is what keeps the reading sound. A directory change carried by a
    called function runs in the same shell, and a change written after the word
    still runs before it on the second turn of a loop, so a subshell that runs
    anything besides the change and the word leaves the directory unwritten.
    """

    marks = _subshell_marks(operation)
    if marks is None or operation.node.call_path:
        return frozenset()
    if operation.loop_regions:
        # A repeated word runs under whatever the previous turn left behind.
        # The loop a word sits in is read rather than the enclosure it carries,
        # because a loop condition and a branch condition share one enclosure.
        return frozenset()
    opens = [
        enclosure.token.start.offset
        for enclosure in operation.node.enclosures
        if enclosure.kind == SUBSHELL_ENCLOSURE
    ]
    if len(opens) != 1:
        return frozenset()
    inside = [
        other
        for other in fixture.operations
        if _inside_subshell(other, opens[0])
    ]
    before = [other for other in inside if other.offset < operation.offset]
    if len(inside) != 2 or len(before) != 1:
        return frozenset()
    change = before[0]
    if change.node.name != DIRECTORY_CHANGE or change.node.call_path:
        return frozenset()
    carried = _subshell_marks(change)
    if carried is None or carried != marks[: len(carried)]:
        # The change runs on a separate path, so the word never follows it.
        return frozenset()
    run = _run_for(fixture, change)
    if run is None or len(run.words) != 2:
        return frozenset()
    places = _settle_operand(fixture, run, run.words[1])
    if len(places) != 1 or not next(iter(places))[0]:
        return frozenset()
    return places


def _copier_destinations(
    fixture: _Fixture,
    run: _CommandRun,
    literals: tuple[str | None, ...],
    place: int,
    subcommand: str = UPDATE_SUBCOMMAND,
) -> frozenset[_Path]:
    """Return every project one written Copier subcommand may write.

    Only the enumerated options are read, so an option written in any other
    spelling may take the word this checker would otherwise read as the
    destination and the dispatch names no destination at all. Each read
    subcommand writes a fixed operand count and writes the project last, so
    any other operand count is unread as well.
    """

    if place + 1 >= len(literals) or literals[place + 1] != subcommand:
        return frozenset()
    operands: list[Token] = []
    index = place + 2
    ended = False
    while index < len(literals):
        written = literals[index]
        if written is None or ended:
            operands.append(run.words[index])
            index += 1
            continue
        if written == OPTION_END:
            ended = True
            index += 1
            continue
        if written.startswith(OPTION_MARK) and written != OPTION_MARK:
            if written.startswith(OPTION_END) and "=" in written:
                index += 1
                continue
            if written in COPIER_FLAG_OPTIONS:
                index += 1
                continue
            if written in COPIER_VALUE_OPTIONS:
                index += 2
                continue
            return frozenset()
        operands.append(run.words[index])
        index += 1
    if len(operands) != COPIER_WRITE_OPERANDS[subcommand]:
        return frozenset()
    return _settle_operand(fixture, run, operands[-1])


def _update_reading(
    fixture: _Fixture, operation: _Operation
) -> frozenset[_Path] | None:
    """Return every project one operation may update, or ``None`` when it updates none."""

    run = _run_for(fixture, operation)
    if run is None or not run.words:
        return frozenset() if _writes_an_update(operation.text) else None
    literals = _run_literals(run)
    places = _command_word_places(literals)
    for place in places:
        paths = _settle_operand(fixture, run, run.words[place])
        if _names_no_update_script(paths):
            continue
        settled = _workflow_destinations(
            paths, _subshell_directory(fixture, operation)
        )
        if settled is not None:
            return settled
        if _names_an_installed_workflow(run.words[place].text):
            return frozenset()
    for place in places:
        written = literals[place]
        if written is None or not _mentions(written, COPIER_MARKER):
            continue
        if place + 1 < len(literals) and literals[place + 1] == UPDATE_SUBCOMMAND:
            return _copier_destinations(fixture, run, literals, place)
    if _forwards_an_update(fixture, operation):
        return frozenset()
    return None


def _names_an_update_script(name: str) -> bool:
    """Report whether one written script name may run a Copier update.

    An installed workflow holds scripts that never update anything, and the
    name of a script is written text this checker reads. Only a name that
    says it carries a Copier update is read as one.

    This reading holds one invariant on the installed workflow it reads: an
    installed script that can carry a Copier update says both words in its
    own name. A future update entry point that drops either word would be
    read as no update, so a new update entry point must keep that name.
    """

    return _mentions(name, COPIER_MARKER) and _mentions(name, UPDATE_MARKER)


def _names_no_update_script(paths: frozenset[_Path]) -> bool:
    """Report whether every path one command word may name runs no Copier update.

    A command word inside an installed workflow runs an update only when its
    own written name says so. A name that carries an expansion, a path that
    names no installed workflow, and a reading that settled nothing all prove
    nothing, so they leave the operation unproven instead.
    """

    if not paths:
        return False
    for _, segments in paths:
        if WORKFLOW_DIRECTORY not in segments:
            return False
        if segments.index(WORKFLOW_DIRECTORY) + 1 >= len(segments):
            return False
        name = segments[-1]
        if _carries_expansion(name) or _names_an_update_script(name):
            return False
    return True


def _forwards_an_update(fixture: _Fixture, operation: _Operation) -> bool:
    """Report whether one operation carries an update its own words never write.

    A dispatch may run the update wrapper from inside an interpreter string,
    from behind a command prefix, or through a helper that runs one of its own
    arguments. The words of the run say nothing about any of these, so every
    value the expansion may carry is read instead, and a match leaves the
    destination unproven rather than accepted.
    """

    return any(
        _forwarded_dispatch_updates(fixture, operation, dispatch.lower())
        for dispatch in fixture.dispatches(operation)
    )


def _forwarded_dispatch_updates(
    fixture: _Fixture, operation: _Operation, dispatch: str
) -> bool:
    """Report whether one expansion of one operation may carry a Copier update."""

    words = dispatch.split()
    word = words[0] if words else ""
    if _mentions(word, UPDATE_WRAPPER_MARKER):
        return True
    if _mentions(dispatch, UPDATE_WRAPPER_MARKER) and (
        _is_interpreter(word)
        or _strip(word) in COMMAND_PREFIXES
        or _forwards_to_interpreter(fixture, operation.name)
        or _forwards_positional(fixture, operation.name)
    ):
        return True
    if not _mentions(word, COPIER_MARKER):
        return False
    return any(
        _strip(text) == UPDATE_SUBCOMMAND
        for text in words[1:]
        if not _strip(text).startswith(OPTION_MARK)
    )


def _names_an_installed_workflow(written: str) -> bool:
    """Report whether one written command word runs a script of an installed workflow.

    The written text is read as well as the settled path, because a word this
    checker cannot settle still runs the update wrapper it writes, and a
    dispatch this checker skips is a dispatch it never rejects. A command word
    whose own name says it carries a Copier update is read the same way,
    because the name is what the fixture writes about what runs.
    """

    return (
        _mentions(written, WORKFLOW_DIRECTORY)
        or _mentions(written, UPDATE_WRAPPER_MARKER)
        or _names_an_update_script(written)
    )


def _writes_an_update(text: str) -> bool:
    """Report whether one written operation may carry a Copier update.

    A run this checker cannot place against exactly one operation reads no
    words at all, so the operation text is read instead. Reading one operation
    too many leaves its destination unproven, which is the safe direction.
    """

    return _names_an_installed_workflow(text) or (
        _mentions(text, COPIER_MARKER) and _mentions(text, UPDATE_MARKER)
    )


def _runs_an_update(fixture: _Fixture, operation: _Operation) -> bool:
    """Report whether the written words of one operation run a Copier update."""

    return _update_reading(fixture, operation) is not None


def _update_destinations(
    fixture: _Fixture, operation: _Operation
) -> frozenset[_Path]:
    """Return every project one operation may update, or nothing when unproven."""

    return _update_reading(fixture, operation) or frozenset()


def _copy_destinations(
    fixture: _Fixture, operation: _Operation
) -> frozenset[_Path]:
    """Return every project one operation may write through a Copier copy or recopy.

    Only a written Copier command word followed by a read copy subcommand is
    read. Every other spelling of a copy hides which project it writes, and an
    operation this checker cannot settle a destination for proves no reach, so
    reading it further would reject a fixture on text rather than on proof.
    """

    run = _run_for(fixture, operation)
    if run is None or not run.words:
        return frozenset()
    literals = _run_literals(run)
    for place in _command_word_places(literals):
        written = literals[place]
        if written is None or not _mentions(written, COPIER_MARKER):
            continue
        if place + 1 >= len(literals):
            continue
        subcommand = literals[place + 1]
        if subcommand not in COPY_SUBCOMMANDS:
            continue
        return _copier_destinations(fixture, run, literals, place, subcommand)
    return frozenset()


def _forwards_positional(fixture: _Fixture, name: str | None) -> bool:
    """Report whether a declared function runs one of its own arguments.

    A helper whose command word is a positional parameter runs whatever the
    call site passes, so the path written at the call site is the path that
    runs. One bounded level is inspected, so the check always terminates.
    """

    if name is None or name not in fixture.table:
        return False
    for command in _declaration_commands(fixture.table[name]):
        if POSITIONAL_PATTERN.match(_strip(command.word or "")) is not None:
            return True
    return False


def _check_unresolved_dispatch(fixture: _Fixture) -> list[Finding]:
    """Reject a Copier update reached through an unresolved dispatch.

    The checked graph reports a command whose command word it cannot resolve.
    Such a command proves nothing about what it runs, so it must not be able
    to carry a Copier update past the direct-invocation and alternate-path
    rules. A dispatch that names the sanctioned update wrapper stays admitted,
    because the wrapper path is exactly the operation the contract requires.
    The admission requires every value the expansion may carry to name the
    wrapper: one value that names it does not prove the others do. An
    expansion the bound collapsed into one text proves no such agreement, so
    it is never admitted.
    """

    findings: list[Finding] = []
    for operation in fixture.operations:
        if not operation.node.dynamic or not operation.reachable:
            continue
        expansions = fixture.expansions(operation)
        if fixture.expansions_are_exact(operation) and all(
            _mentions(text, UPDATE_WRAPPER_MARKER) for text in expansions
        ):
            continue
        subcommand = any(
            value in COPIER_SUBCOMMANDS
            for value in operation.argument_values
            if value is not None
        )
        if subcommand or any(_mentions(text, COPIER_MARKER) for text in expansions):
            findings.append(
                Finding(
                    RULE_UNRESOLVED_DISPATCH,
                    "an unresolved dispatch can run a Copier update",
                    operation.position,
                )
            )
    return findings


def _check_transition(fixture: _Fixture) -> list[Finding]:
    findings, child = _check_update_child(fixture)
    if child is None:
        return findings
    pid_findings, pid_name = _check_child_pid(fixture, child)
    findings.extend(pid_findings)
    findings.extend(_check_bounded_polls(fixture))
    release_findings, release = _check_release_paths(fixture)
    findings.extend(release_findings)
    reap_findings, final_wait = _check_child_reap(fixture, child, pid_name)
    findings.extend(reap_findings)
    findings.extend(_check_state_order(fixture, release, final_wait))
    findings.extend(_check_guardian(fixture))
    findings.extend(_check_alternate_paths(fixture, child))
    findings.extend(_check_copier_writes(fixture, child))
    return findings


def check(source: str | bytes) -> tuple[Finding, ...]:
    """Return every Copier fixture operation the supplied bytes fail to prove."""

    text = _decode(source)
    try:
        records = shell_lexical.project(text)
    except ShellLexicalError as error:
        return (
            Finding(
                RULE_STRUCTURE,
                f"the checked lexical projection rejected the supplied bytes: {error}",
                error.position,
            ),
        )
    try:
        table = shell_functions.derive(records)
    except ShellFunctionError as error:
        return (
            Finding(
                RULE_STRUCTURE,
                f"the checked function table rejected the supplied bytes: {error}",
                error.position,
            ),
        )
    try:
        graph = shell_execution.derive(records, table)
    except ShellExecutionError as error:
        return (
            Finding(
                RULE_STRUCTURE,
                f"the checked execution graph rejected the supplied bytes: {error}",
                error.position,
            ),
        )
    fixture = _Fixture(text, records, table, graph)
    findings = list(_check_version_commits(fixture))
    findings.extend(_check_inventory_region(fixture))
    findings.extend(_check_direct_invocation(fixture))
    findings.extend(_check_unresolved_dispatch(fixture))
    if _is_transition(fixture):
        findings.extend(_check_transition(fixture))
    return tuple(sorted(findings, key=lambda finding: finding.sort_key))


def validate(source: str | bytes) -> None:
    """Raise when supplied bytes break the bounded Copier fixture contract."""

    findings = check(source)
    if findings:
        report = "\n".join(str(finding) for finding in findings)
        raise CopierFixtureError(
            f"the supplied Copier fixture broke {len(findings)} bounded "
            f"operation rule(s):\n{report}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        metavar="PATH",
        required=True,
        type=Path,
        help="validate the bounded Copier fixture operations of one shell file",
    )
    arguments = parser.parse_args(argv)
    try:
        supplied = arguments.check.read_bytes()
    except OSError as error:
        print(f"copier fixture check failed: {error}", file=sys.stderr)
        return 1
    try:
        findings = check(supplied)
    except CopierFixtureError as error:
        print(f"copier fixture check failed: {error}", file=sys.stderr)
        return 1
    if findings:
        print(
            f"copier fixture check failed: {arguments.check}: "
            f"{len(findings)} bounded operation rule(s) rejected",
            file=sys.stderr,
        )
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print(f"copier fixture check passed: {arguments.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
