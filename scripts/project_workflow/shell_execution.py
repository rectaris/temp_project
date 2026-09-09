"""Bounded reachable command graph over checked shell records.

The graph consumes only the lexical records emitted by the checked bounded
shell lexical projection and the checked bounded top-level function table. It
never re-tokenizes supplied bytes and never executes, sources, or imports the
supplied script.

Every control transfer is an explicit edge. A command executes only when an
edge reaches its node, so a region that a shell can never run has no incoming
edge instead of being assumed reachable. The permitted success path is the
exact set of command nodes that lie on every path from the entry node to the
successful termination node, so a region that a conditional, loop, case arm,
and-or operand, conditional expansion, background job, or early termination
can skip is never reported as guaranteed.

The graph answers a control-flow question, not a status question. A command
status is never evaluated, so:

- `success_path` means "the shell reaches this command on every execution that
  terminates successfully". It does not claim that a successful execution
  exists, and it does not claim that the command itself completed. An
  expansion error, a redirection error, or a missing utility can still skip
  the command word alone; `Node.may_fail_before_running` reports the
  redirection case, which is the only one that is visible in the records.
- A failing command reaches the failing termination node under `set -e`, which
  is not a successful execution, so the reading above holds with and without
  errexit. `ExecutionGraph.shell_options` reports the option words the script
  sets, because they change which executions can succeed.
- A child process ends early without ending the script, so every command in a
  subshell, command substitution, pipeline member, or background list carries
  an explicit early-end transfer. This over-approximates the skip: a child
  that enables no option and runs no special built-in always completes. The
  approximation only ever removes a guarantee, never adds one.
- The reference shells disagree about redirection target expansion: one
  expands every target word before applying any redirection, and another
  applies each redirection as it reads it. Every redirection therefore carries
  a skip path over the words that follow it, which is the reading both shells
  allow. A here-document body is expanded when its redirection is applied in
  both, so the same ordered walk is exact for it.
- The reference shells also disagree about whether an assignment prefix is
  expanded before or after the redirections of the same command. Both expand
  the command words first, so the prefix is ordered last, where a failing
  redirection can still skip it. `precedes` therefore reports no dependable
  order between one command's assignment prefix and its own redirections.
- Reachability is also an over-approximation. A loop with a condition that can
  never fail still reports its exit as reachable, so a required region must be
  proven with `guaranteed`, not with `reachable`.

A construct outside the accepted subset is rejected with an exact source
position instead of being modelled partially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from .shell_functions import FunctionDeclaration, FunctionTable
# The assignment split is security relevant: a word whose `=` is quoted is a
# command word, not an assignment. Reuse the checked helper instead of
# restating the rule, so the two modules can never disagree about which word
# holds the command name.
from .shell_functions import _assignment_prefix
from .shell_lexical import (
    COMMAND_SUBSTITUTION,
    COMMENT,
    HEREDOC_BODY,
    IO_NUMBER,
    LINE_CONTINUATION,
    LexicalProjection,
    NEWLINE,
    OPERATOR,
    PARAMETER_EXPANSION,
    Position,
    Segment,
    Token,
    WORD,
)


__all__ = [
    "ABORT",
    "ASYNC",
    "ASYNC_LIST",
    "BRACE_GROUP",
    "BREAK",
    "CALL",
    "CASE",
    "CASE_ARM",
    "CASE_MATCH",
    "CASE_SKIP",
    "COMMAND",
    "CONDITION",
    "CONDITIONAL_ENCLOSURES",
    "CONDITIONAL_OPERAND",
    "CONDITION_FALSE",
    "CONDITION_TRUE",
    "CONTINUE",
    "DISPUTED_PREFIXES",
    "EFFECT_BREAK",
    "EFFECT_CONTINUE",
    "EFFECT_EXEC",
    "EFFECT_EXIT",
    "EFFECT_MUTATE_TABLE",
    "EFFECT_RETURN",
    "EFFECT_SOURCE",
    "EFFECT_TRAP",
    "ELIF_CONDITION",
    "ELSE_BRANCH",
    "END",
    "ENTRY",
    "EXPANSION_REGION",
    "EXPANSION_SKIP",
    "Edge",
    "Enclosure",
    "ExecutionGraph",
    "FUNCTION_BODY",
    "LOOP",
    "LOOP_BODY",
    "LOOP_ENTER",
    "LOOP_EXIT",
    "LOOP_REPEAT",
    "MAX_CALL_DEPTH",
    "MAX_DEPTH",
    "MAX_NODES",
    "Node",
    "PIPELINE",
    "PIPELINE_MEMBER",
    "PROCESS_ABORT",
    "REDIRECTION_SKIP",
    "RETURNED",
    "SEPARATOR",
    "SEQUENTIAL",
    "SUBSHELL",
    "SUBSTITUTION",
    "SUBSTITUTION_REGION",
    "ShellExecutionError",
    "TERMINAL_EFFECTS",
    "TERMINATE",
    "TERMINATION_FAILURE",
    "TERMINATION_SUCCESS",
    "TERMINATION_UNKNOWN",
    "THEN_BRANCH",
    "TRANSPARENT_PREFIXES",
    "derive",
]


ENTRY = "entry"
END = "end"
ABORT = "abort"
COMMAND = "command"
LOOP = "loop"
CASE = "case"

SEQUENTIAL = "sequential"
PIPELINE = "pipeline"
ON_SUCCESS = "on_success"
ON_FAILURE = "on_failure"
CONDITION_TRUE = "condition_true"
CONDITION_FALSE = "condition_false"
LOOP_ENTER = "loop_enter"
LOOP_REPEAT = "loop_repeat"
LOOP_EXIT = "loop_exit"
CASE_MATCH = "case_match"
CASE_SKIP = "case_skip"
CALL = "call"
RETURNED = "returned"
ASYNC = "async"
SUBSTITUTION = "substitution"
EXPANSION_SKIP = "expansion_skip"
REDIRECTION_SKIP = "redirection_skip"
PROCESS_ABORT = "process_abort"
TERMINATE = "terminate"
BREAK = "break"
CONTINUE = "continue"

EFFECT_EXIT = "exit"
EFFECT_EXEC = "exec"
EFFECT_RETURN = "return"
EFFECT_BREAK = "break"
EFFECT_CONTINUE = "continue"
EFFECT_SOURCE = "source"
EFFECT_TRAP = "trap"
EFFECT_MUTATE_TABLE = "mutate_table"

TERMINAL_EFFECTS = frozenset({EFFECT_EXIT, EFFECT_EXEC})

TERMINATION_SUCCESS = "success"
TERMINATION_FAILURE = "failure"
TERMINATION_UNKNOWN = "unknown"
TRANSFER_EFFECTS = frozenset({EFFECT_RETURN, EFFECT_BREAK, EFFECT_CONTINUE})

CONDITION = "condition"
ELIF_CONDITION = "elif_condition"
THEN_BRANCH = "then_branch"
ELSE_BRANCH = "else_branch"
LOOP_BODY = "loop_body"
CASE_ARM = "case_arm"
SUBSHELL = "subshell"
BRACE_GROUP = "brace_group"
PIPELINE_MEMBER = "pipeline_member"
SUBSTITUTION_REGION = "command_substitution"
ASYNC_LIST = "async_list"
FUNCTION_BODY = "function_body"
CONDITIONAL_OPERAND = "conditional_operand"
EXPANSION_REGION = "conditional_expansion"

CONDITIONAL_ENCLOSURES = frozenset(
    {
        THEN_BRANCH,
        ELSE_BRANCH,
        LOOP_BODY,
        CASE_ARM,
        CONDITIONAL_OPERAND,
        ELIF_CONDITION,
        ASYNC_LIST,
        EXPANSION_REGION,
    }
)

SEPARATOR = ";"

MAX_NODES = 20000
# `str.isdigit` accepts characters `int` rejects, and an unbounded digit run
# exceeds the interpreter conversion limit, so a modelled status or level is
# read as an exact bounded decimal literal.
MAX_LITERAL_DIGITS = 6
# A recursive descent over deeply nested compound commands must fail with an
# exact rejection instead of a raw interpreter recursion error.
MAX_DEPTH = 64
MAX_CALL_DEPTH = 32

IGNORED_KINDS = frozenset({COMMENT, LINE_CONTINUATION, HEREDOC_BODY})
REDIRECTION_OPERATORS = frozenset({"<", ">", ">>", "<<", "<<-", "<&", ">&", "<>", ">|"})
HERE_DOCUMENT_OPERATORS = frozenset({"<<", "<<-"})
STOP_WORDS = frozenset({"then", "else", "elif", "fi", "do", "done", "esac", "}"})
COMPOUND_WORDS = frozenset({"{", "if", "while", "until", "for", "case"})
# Mirrors the transparent prefix set of the checked function table.
TRANSPARENT_PREFIXES = frozenset(
    {"command", "builtin", "time", "exec", "env", "nohup"}
)
# `builtin` is not defined by POSIX. A shell that lacks it runs no operand at
# all, and a shell that defines it runs a built-in, so the dispatch target of
# an undeclared `builtin` word is reported as unresolved instead of guessed.
AMBIGUOUS_PREFIXES = frozenset({"builtin"})
# A prefix that runs its operand outside the shell cannot reach a shell
# function or a shell built-in, so no effect word behind it is terminal.
EXTERNAL_PREFIXES = frozenset({"env", "nohup"})
# `time` is a reserved word in one reference shell, which runs its operand in
# the current shell, and an external utility in another, which cannot. The two
# readings disagree about every operand, so an operand of one is rejected.
DISPUTED_PREFIXES = frozenset({"time"})
# Exact option letters each prefix accepts without a separate operand word.
PREFIX_OPTION_LETTERS = {
    "command": frozenset("pvV"),
    "builtin": frozenset(),
    "env": frozenset("i"),
    "nohup": frozenset(),
    "time": frozenset("p"),
    "exec": frozenset(),
}
# `command -v` and `command -V` report how a word would run and execute
# nothing.
COMMAND_QUERY_LETTERS = frozenset("vV")
# Options that consume the next word as their operand.
PREFIX_OPTION_OPERANDS = {"env": frozenset({"-u", "--unset"})}
EFFECT_WORDS = {
    "exit": EFFECT_EXIT,
    "return": EFFECT_RETURN,
    "break": EFFECT_BREAK,
    "continue": EFFECT_CONTINUE,
    ".": EFFECT_SOURCE,
    "source": EFFECT_SOURCE,
    "trap": EFFECT_TRAP,
    "alias": EFFECT_MUTATE_TABLE,
    "unalias": EFFECT_MUTATE_TABLE,
}
CONDITIONAL_WORD_OPERATORS = frozenset("-+=?")
NAME_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
NAME_CHARACTERS = NAME_START | frozenset("0123456789")


class ShellExecutionError(ValueError):
    """Raised when checked records leave the accepted execution subset."""

    def __init__(self, message: str, position: Position | None = None) -> None:
        self.position = position
        if position is None:
            super().__init__(message)
        else:
            super().__init__(f"line {position.line} column {position.column}: {message}")


@dataclass(frozen=True)
class Enclosure:
    """One structural region that encloses a command node."""

    kind: str
    token: Token | None = None

    @property
    def position(self) -> Position | None:
        return None if self.token is None else self.token.start


@dataclass(frozen=True)
class Node:
    """One node of the reachable command graph."""

    index: int
    kind: str
    token: Token | None = None
    name: str | None = None
    words: tuple[Token, ...] = ()
    arguments: tuple[Token, ...] = ()
    effect: str | None = None
    termination: str | None = None
    enclosures: tuple[Enclosure, ...] = ()
    in_subshell: bool = False
    asynchronous: bool = False
    dynamic: bool = False
    call_path: tuple[str, ...] = ()
    declaration: FunctionDeclaration | None = None
    redirected: bool = False
    reachable: bool = False
    guaranteed: bool = False

    @property
    def position(self) -> Position | None:
        """Return the exact source position of the command word."""

        return None if self.token is None else self.token.start

    @property
    def enclosure_kinds(self) -> tuple[str, ...]:
        """Return every enclosing region kind from outermost to innermost."""

        return tuple(enclosure.kind for enclosure in self.enclosures)

    @property
    def is_conditional(self) -> bool:
        """Report whether a control transfer can skip this node."""

        return any(kind in CONDITIONAL_ENCLOSURES for kind in self.enclosure_kinds)

    @property
    def is_terminal(self) -> bool:
        """Report whether the node ends its own shell process."""

        return self.effect in TERMINAL_EFFECTS

    @property
    def is_call(self) -> bool:
        """Report whether the node dispatches to a declared function."""

        return self.declaration is not None

    @property
    def may_fail_before_running(self) -> bool:
        """Report whether the shell can skip the command itself.

        A redirection is performed before the utility runs, so a redirection
        error skips this command without skipping the commands that follow it.
        Reaching this node therefore does not prove that its utility ran.
        """

        return self.redirected

    @property
    def argument_values(self) -> tuple[str | None, ...]:
        """Return the expansion-free argument text, or None per unresolved word."""

        return tuple(token.literal_value for token in self.arguments)


@dataclass(frozen=True)
class Edge:
    """One explicit control transfer between two nodes."""

    source: int
    target: int
    transfer: str


@dataclass(frozen=True)
class ExecutionGraph:
    """The reachable command graph of one supplied script."""

    source: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    entry_index: int
    end_index: int
    abort_index: int
    dominator_bits: tuple[int, ...] = ()
    postdominator_bits: tuple[int, ...] = ()
    table: FunctionTable | None = None

    @property
    def entry(self) -> Node:
        return self.nodes[self.entry_index]

    @property
    def end(self) -> Node:
        """Return the node that represents successful script termination."""

        return self.nodes[self.end_index]

    @property
    def abort(self) -> Node:
        """Return the node that represents failing script termination."""

        return self.nodes[self.abort_index]

    @property
    def commands(self) -> tuple[Node, ...]:
        """Return every command node in execution-construction order."""

        return tuple(node for node in self.nodes if node.kind == COMMAND)

    @property
    def success_path(self) -> tuple[Node, ...]:
        """Return the one permitted success path of guaranteed command nodes.

        A node is on the path when every path from the entry node to the
        successful termination node passes through it, so the path holds
        exactly the commands the shell reaches on every execution that
        terminates successfully. The path is empty when no execution can
        terminate successfully.
        """

        return tuple(node for node in self.commands if node.guaranteed)

    @property
    def reachable(self) -> tuple[Node, ...]:
        """Return every command node that at least one execution path reaches."""

        return tuple(node for node in self.commands if node.reachable)

    @property
    def unreachable(self) -> tuple[Node, ...]:
        """Return every command node that no execution path can reach."""

        return tuple(node for node in self.commands if not node.reachable)

    @property
    def terminal_nodes(self) -> tuple[Node, ...]:
        """Return every node that ends its own shell process."""

        return tuple(node for node in self.commands if node.is_terminal)

    @property
    def transfer_nodes(self) -> tuple[Node, ...]:
        """Return every alternate control transfer node."""

        return tuple(
            node for node in self.commands if node.effect in TRANSFER_EFFECTS
        )

    @property
    def asynchronous_nodes(self) -> tuple[Node, ...]:
        """Return every command node started as a background job."""

        return tuple(node for node in self.commands if node.asynchronous)

    @property
    def calls(self) -> tuple[Node, ...]:
        """Return every node that dispatches to a declared function."""

        return tuple(node for node in self.commands if node.is_call)

    @property
    def dynamic_commands(self) -> tuple[Node, ...]:
        """Return every node whose dispatch target is not a literal name."""

        return tuple(node for node in self.commands if node.dynamic)

    @property
    def included_sources(self) -> tuple[Node, ...]:
        """Return every node that includes another file into this shell."""

        return tuple(
            node for node in self.commands if node.effect == EFFECT_SOURCE
        )

    @property
    def shell_options(self) -> tuple[Node, ...]:
        """Return every node that changes shell option state with `set`."""

        return tuple(
            node
            for node in self.commands
            if node.name == "set"
            and any(
                (value or "").startswith(("-", "+")) and value not in ("-", "--")
                for value in node.argument_values
            )
        )

    @property
    def trap_registrations(self) -> tuple[Node, ...]:
        """Return every node that registers a deferred trap action."""

        return tuple(node for node in self.commands if node.effect == EFFECT_TRAP)

    @property
    def is_fully_resolved(self) -> bool:
        """Report whether the graph describes every command of the script.

        A dynamic dispatch, an included file, or a registered trap action adds
        commands that cannot be resolved without executing the script. A
        consumer that requires the graph to describe the whole script must
        assert this property; a false result means at least one executable
        region is outside the graph.
        """

        if self.dynamic_commands or self.included_sources or self.trap_registrations:
            return False
        return self.table is None or self.table.is_fully_resolved

    def outgoing(self, node: Node | int) -> tuple[Edge, ...]:
        """Return every control transfer that leaves the node."""

        index = node if isinstance(node, int) else node.index
        return tuple(edge for edge in self.edges if edge.source == index)

    def incoming(self, node: Node | int) -> tuple[Edge, ...]:
        """Return every control transfer that reaches the node."""

        index = node if isinstance(node, int) else node.index
        return tuple(edge for edge in self.edges if edge.target == index)

    def find(self, name: str) -> tuple[Node, ...]:
        """Return every command node dispatching to the exact literal name."""

        return tuple(node for node in self.commands if node.name == name)

    def find_reachable(self, name: str) -> tuple[Node, ...]:
        """Return every reachable command node with the exact literal name."""

        return tuple(node for node in self.find(name) if node.reachable)

    def find_guaranteed(self, name: str) -> tuple[Node, ...]:
        """Return every success-path command node with the exact literal name."""

        return tuple(node for node in self.find(name) if node.guaranteed)

    def dominates(self, first: Node | int, second: Node | int) -> bool:
        """Report whether every path to the second node passes the first node."""

        source = first if isinstance(first, int) else first.index
        target = second if isinstance(second, int) else second.index
        if not self.nodes[target].reachable:
            return False
        return bool(self.dominator_bits[target] >> source & 1)

    def postdominates(self, first: Node | int, second: Node | int) -> bool:
        """Report whether every successful path from the second reaches the first.

        The relation is false when the second node cannot reach successful
        termination at all, so an unreachable or always-aborting region never
        proves that a later command runs.
        """

        source = first if isinstance(first, int) else first.index
        target = second if isinstance(second, int) else second.index
        if not self.postdominator_bits[target]:
            return False
        return bool(self.postdominator_bits[target] >> source & 1)

    def precedes(self, first: Node, second: Node) -> bool:
        """Report whether the first node always runs before the second node."""

        return (
            first.index != second.index
            and self.dominates(first, second)
            and self.postdominates(second, first)
        )

    def __iter__(self) -> Iterator[Node]:
        return iter(self.commands)

    def __len__(self) -> int:
        return len(self.commands)


@dataclass(frozen=True)
class _Redirect:
    io_number: Token | None
    operator: Token
    target: Token
    heredoc: Token | None = None


@dataclass(frozen=True)
class _Simple:
    assignments: tuple[Token, ...]
    words: tuple[Token, ...]
    redirects: tuple[_Redirect, ...]


@dataclass(frozen=True)
class _Declaration:
    declaration: FunctionDeclaration


@dataclass(frozen=True)
class _Pipeline:
    members: tuple[object, ...]
    negation: Token | None = None


@dataclass(frozen=True)
class _AndOr:
    first: _Pipeline
    rest: tuple[tuple[Token, _Pipeline], ...] = ()


@dataclass(frozen=True)
class _List:
    items: tuple[tuple[_AndOr, str], ...] = ()


@dataclass(frozen=True)
class _BraceGroup:
    token: Token
    body: _List
    redirects: tuple[_Redirect, ...] = ()


@dataclass(frozen=True)
class _Subshell:
    token: Token
    body: _List
    redirects: tuple[_Redirect, ...] = ()


@dataclass(frozen=True)
class _If:
    token: Token
    branches: tuple[tuple[_List, _List], ...]
    else_body: _List | None = None
    redirects: tuple[_Redirect, ...] = ()


@dataclass(frozen=True)
class _Loop:
    token: Token
    kind: str
    condition: _List
    body: _List
    redirects: tuple[_Redirect, ...] = ()


@dataclass(frozen=True)
class _For:
    token: Token
    name: Token
    words: tuple[Token, ...]
    body: _List
    # `for name in` with no word runs the body zero times, while `for name`
    # iterates over the positional parameters and may run it.
    explicit_list: bool = False
    redirects: tuple[_Redirect, ...] = ()


@dataclass(frozen=True)
class _CaseArm:
    patterns: tuple[Token, ...]
    body: _List


@dataclass(frozen=True)
class _Case:
    token: Token
    word: Token
    arms: tuple[_CaseArm, ...]
    redirects: tuple[_Redirect, ...] = ()


def derive(records: LexicalProjection, table: FunctionTable) -> ExecutionGraph:
    """Derive the reachable command graph from checked records and table."""

    if not isinstance(records, LexicalProjection):
        raise ShellExecutionError("checked lexical records are required")
    if not isinstance(table, FunctionTable):
        raise ShellExecutionError("a checked function table is required")
    _require_matching_table(records, table)
    builder = _Builder(records, table)
    return builder.run()


def _require_matching_table(records: LexicalProjection, table: FunctionTable) -> None:
    """Reject a function table that does not describe the supplied records."""

    positions = {token.start.offset: token for token in records.tokens}
    for declaration in table.declarations:
        for token in (declaration.name_token, declaration.open_brace, declaration.close_brace):
            if positions.get(token.start.offset) != token:
                raise ShellExecutionError(
                    "function table does not describe the supplied lexical records",
                    token.start,
                )


def _here_document_bodies(tokens: tuple[Token, ...]) -> dict[int, Token]:
    """Bind each here-document operator to the body record the shell reads."""

    bodies: dict[int, Token] = {}
    pending: list[Token] = []
    for token in tokens:
        if token.kind == OPERATOR and token.text in HERE_DOCUMENT_OPERATORS:
            pending.append(token)
        elif token.kind == HEREDOC_BODY and pending:
            bodies[pending.pop(0).start.offset] = token
    return bodies


def _substitution_segments(
    token: Token | None,
) -> Iterator[tuple[Segment, bool]]:
    """Yield every command substitution the shell expands inside one record.

    Each substitution is reported with the flag that states whether the shell
    expands it conditionally, so a substitution the shell may skip is never
    modelled as an unconditional command.
    """

    if token is None:
        return
    yield from _segment_substitutions(token.segments, False)


def _segment_substitutions(
    segments: tuple[Segment, ...], conditional: bool
) -> Iterator[tuple[Segment, bool]]:
    for segment in segments:
        if segment.kind == COMMAND_SUBSTITUTION:
            # Nested substitutions live in the region's own records and are
            # reached when that region's commands are built.
            yield segment, conditional
            continue
        threshold = _conditional_word_offset(segment)
        for part in segment.segments:
            nested = conditional or (
                threshold is not None and part.start.offset >= threshold
            )
            yield from _segment_substitutions((part,), nested)


def _conditional_word_offset(segment: Segment) -> int | None:
    """Return the offset after which a braced expansion word is conditional.

    `${name:-word}`, `${name-word}`, `${name:+word}`, `${name+word}`,
    `${name:=word}`, `${name=word}`, `${name:?word}`, and `${name?word}`
    expand `word` only for a particular parameter state, so a command
    substitution inside `word` may never run. Every other braced form,
    including `${#name}`, `${name%pattern}`, and `${name#pattern}`, expands its
    word whenever the expansion itself is reached.
    """

    if segment.kind != PARAMETER_EXPANSION:
        return None
    text = segment.text
    if not text.startswith("${"):
        return None
    cursor = 2
    if (
        cursor + 1 < len(text)
        and text[cursor] == "#"
        and text[cursor + 1] in NAME_CHARACTERS
    ):
        # `${#name}` is a length expansion, while `${#}` and `${#-word}` name
        # the special parameter `#`.
        cursor += 1
    start = cursor
    while cursor < len(text) and text[cursor] in NAME_CHARACTERS:
        cursor += 1
    if cursor == start and cursor < len(text):
        cursor += 1
    if cursor >= len(text):
        return None
    if (
        text[cursor] == ":"
        and cursor + 1 < len(text)
        and text[cursor + 1] in CONDITIONAL_WORD_OPERATORS
    ):
        return segment.start.offset + cursor + 2
    if text[cursor] in CONDITIONAL_WORD_OPERATORS:
        return segment.start.offset + cursor + 1
    return None


def _is_name(value: str | None) -> bool:
    if not value or value[0] not in NAME_START:
        return False
    return all(character in NAME_CHARACTERS for character in value)


class _Parser:
    """Recursive-descent parser over one checked record sequence."""

    def __init__(
        self,
        tokens: tuple[Token, ...],
        declarations: dict[int, FunctionDeclaration] | None = None,
    ) -> None:
        self.bodies = _here_document_bodies(tokens)
        self.tokens = tuple(
            token for token in tokens if token.kind not in IGNORED_KINDS
        )
        self.declarations = declarations or {}
        self.closers = {
            declaration.close_brace.start.offset: declaration
            for declaration in self.declarations.values()
        }
        self.index = 0
        self.depth = 0

    def fail(self, message: str, token: Token | None = None) -> ShellExecutionError:
        if token is None:
            token = self.peek() or (self.tokens[-1] if self.tokens else None)
        return ShellExecutionError(message, None if token is None else token.start)

    def peek(self) -> Token | None:
        if self.index < len(self.tokens):
            return self.tokens[self.index]
        return None

    def advance(self) -> Token:
        token = self.peek()
        if token is None:
            raise self.fail("supplied records end inside an unterminated command")
        self.index += 1
        return token

    def at_end(self) -> bool:
        return self.index >= len(self.tokens)

    def at_word(self, *values: str) -> bool:
        token = self.peek()
        return (
            token is not None
            and token.kind == WORD
            and token.literal_value in values
        )

    def at_operator(self, *texts: str) -> bool:
        token = self.peek()
        return token is not None and token.kind == OPERATOR and token.text in texts

    def at_newline(self) -> bool:
        token = self.peek()
        return token is not None and token.kind == NEWLINE

    def skip_newlines(self) -> None:
        while self.at_newline():
            self.index += 1

    def expect_word(self, value: str) -> Token:
        if not self.at_word(value):
            raise self.fail(f"expected `{value}`")
        return self.advance()

    def expect_operator(self, text: str) -> Token:
        if not self.at_operator(text):
            raise self.fail(f"expected `{text}`")
        return self.advance()

    def parse_program(self) -> _List:
        body = self.parse_list(frozenset(), frozenset())
        if not self.at_end():
            raise self.fail("unexpected record outside any command")
        return body

    def at_stop(self, words: frozenset[str], operators: frozenset[str]) -> bool:
        if self.at_end():
            return True
        token = self.peek()
        assert token is not None
        if token.kind == WORD and token.literal_value in words:
            return True
        return token.kind == OPERATOR and token.text in operators

    def parse_list(
        self, words: frozenset[str], operators: frozenset[str]
    ) -> _List:
        items: list[tuple[_AndOr, str]] = []
        while True:
            self.skip_newlines()
            if self.at_stop(words, operators):
                break
            and_or = self.parse_and_or()
            separator = SEPARATOR
            if self.at_operator("&"):
                separator = "&"
                self.advance()
            elif self.at_operator(";"):
                self.advance()
            elif self.at_newline():
                self.advance()
            elif not self.at_stop(words, operators):
                raise self.fail("unsupported record after a complete command")
            items.append((and_or, separator))
        return _List(items=tuple(items))

    def parse_and_or(self) -> _AndOr:
        first = self.parse_pipeline()
        rest: list[tuple[Token, _Pipeline]] = []
        while self.at_operator("&&", "||"):
            operator = self.advance()
            self.skip_newlines()
            rest.append((operator, self.parse_pipeline()))
        return _AndOr(first=first, rest=tuple(rest))

    def parse_pipeline(self) -> _Pipeline:
        negation = self.advance() if self.at_word("!") else None
        members = [self.parse_command()]
        while self.at_operator("|"):
            self.advance()
            self.skip_newlines()
            members.append(self.parse_command())
        return _Pipeline(members=tuple(members), negation=negation)

    def parse_command(self) -> object:
        token = self.peek()
        if token is None:
            raise self.fail("supplied records end where a command is required")
        if self.depth >= MAX_DEPTH:
            raise self.fail(
                f"command nesting exceeds the bounded depth of {MAX_DEPTH}", token
            )
        self.depth += 1
        try:
            return self.parse_command_at(token)
        finally:
            self.depth -= 1

    def parse_command_at(self, token: Token) -> object:
        if token.kind == OPERATOR and token.text == "(":
            return self.parse_subshell()
        if token.kind == WORD:
            declaration = self.declarations.get(token.start.offset)
            if declaration is not None:
                return self.parse_declaration(declaration)
            value = token.literal_value
            if value == "{":
                return self.parse_brace_group()
            if value == "if":
                return self.parse_if()
            if value in ("while", "until"):
                return self.parse_loop()
            if value == "for":
                return self.parse_for()
            if value == "case":
                return self.parse_case()
        return self.parse_simple()

    def parse_declaration(self, declaration: FunctionDeclaration) -> _Declaration:
        closing = declaration.close_brace.start.offset
        while not self.at_end():
            token = self.advance()
            if token.start.offset == closing:
                return _Declaration(declaration=declaration)
        raise self.fail(
            "function declaration body is not terminated", declaration.name_token
        )

    def parse_redirect(self) -> _Redirect:
        io_number = self.advance() if self.peek().kind == IO_NUMBER else None
        operator = self.advance()
        if operator.kind != OPERATOR or operator.text not in REDIRECTION_OPERATORS:
            raise self.fail("expected a redirection operator", operator)
        target = self.peek()
        if target is None or target.kind != WORD:
            raise self.fail("redirection lacks a target word", operator)
        self.advance()
        heredoc = None
        if operator.text in HERE_DOCUMENT_OPERATORS:
            heredoc = self.bodies.get(operator.start.offset)
        return _Redirect(
            io_number=io_number, operator=operator, target=target, heredoc=heredoc
        )

    def at_redirect(self) -> bool:
        token = self.peek()
        if token is None:
            return False
        if token.kind == IO_NUMBER:
            return True
        return token.kind == OPERATOR and token.text in REDIRECTION_OPERATORS

    def parse_redirects(self) -> tuple[_Redirect, ...]:
        redirects: list[_Redirect] = []
        while self.at_redirect():
            redirects.append(self.parse_redirect())
        return tuple(redirects)

    def parse_simple(self) -> _Simple:
        assignments: list[Token] = []
        words: list[Token] = []
        redirects: list[_Redirect] = []
        while True:
            token = self.peek()
            if token is None or token.kind == NEWLINE:
                break
            if self.at_redirect():
                redirects.append(self.parse_redirect())
                continue
            if token.kind == OPERATOR:
                break
            if token.kind != WORD:
                raise self.fail("unsupported record in a command", token)
            if not words and _is_assignment(token):
                assignments.append(self.advance())
                continue
            words.append(self.advance())
        if not words and not assignments and not redirects:
            raise self.fail("expected a command")
        return _Simple(
            assignments=tuple(assignments),
            words=tuple(words),
            redirects=tuple(redirects),
        )

    def parse_brace_group(self) -> _BraceGroup:
        token = self.expect_word("{")
        body = self.parse_list(frozenset({"}"}), frozenset())
        if not self.at_word("}"):
            raise self.fail("brace group is not terminated", token)
        self.advance()
        return _BraceGroup(token=token, body=body, redirects=self.parse_redirects())

    def parse_subshell(self) -> _Subshell:
        token = self.expect_operator("(")
        body = self.parse_list(frozenset(), frozenset({")"}))
        if not self.at_operator(")"):
            raise self.fail("subshell is not terminated", token)
        self.advance()
        return _Subshell(token=token, body=body, redirects=self.parse_redirects())

    def parse_if(self) -> _If:
        token = self.expect_word("if")
        branches: list[tuple[_List, _List]] = []
        while True:
            condition = self.parse_list(frozenset({"then"}), frozenset())
            self.expect_word("then")
            body = self.parse_list(frozenset({"elif", "else", "fi"}), frozenset())
            branches.append((condition, body))
            if self.at_word("elif"):
                self.advance()
                continue
            break
        else_body = None
        if self.at_word("else"):
            self.advance()
            else_body = self.parse_list(frozenset({"fi"}), frozenset())
        if not self.at_word("fi"):
            raise self.fail("`if` command is not terminated", token)
        self.advance()
        return _If(
            token=token,
            branches=tuple(branches),
            else_body=else_body,
            redirects=self.parse_redirects(),
        )

    def parse_loop(self) -> _Loop:
        token = self.advance()
        kind = token.literal_value or ""
        condition = self.parse_list(frozenset({"do"}), frozenset())
        self.expect_word("do")
        body = self.parse_list(frozenset({"done"}), frozenset())
        if not self.at_word("done"):
            raise self.fail(f"`{kind}` command is not terminated", token)
        self.advance()
        return _Loop(
            token=token,
            kind=kind,
            condition=condition,
            body=body,
            redirects=self.parse_redirects(),
        )

    def parse_for(self) -> _For:
        token = self.expect_word("for")
        name = self.peek()
        if name is None or name.kind != WORD or not _is_name(name.literal_value):
            raise self.fail("`for` command requires an exact literal name", token)
        self.advance()
        words: list[Token] = []
        explicit_list = False
        if self.at_word("in"):
            explicit_list = True
            self.advance()
            while not self.at_end():
                if self.at_newline() or self.at_operator(";"):
                    break
                candidate = self.peek()
                assert candidate is not None
                if candidate.kind != WORD:
                    raise self.fail("unsupported record in a `for` word list", candidate)
                words.append(self.advance())
        while self.at_operator(";") or self.at_newline():
            self.advance()
        self.expect_word("do")
        body = self.parse_list(frozenset({"done"}), frozenset())
        if not self.at_word("done"):
            raise self.fail("`for` command is not terminated", token)
        self.advance()
        return _For(
            token=token,
            name=name,
            words=tuple(words),
            body=body,
            explicit_list=explicit_list,
            redirects=self.parse_redirects(),
        )

    def parse_case(self) -> _Case:
        token = self.expect_word("case")
        word = self.peek()
        if word is None or word.kind != WORD:
            raise self.fail("`case` command requires a word", token)
        self.advance()
        self.skip_newlines()
        self.expect_word("in")
        arms: list[_CaseArm] = []
        while True:
            self.skip_newlines()
            if self.at_word("esac") or self.at_end():
                break
            if self.at_operator("("):
                self.advance()
            patterns: list[Token] = []
            while True:
                pattern = self.peek()
                if pattern is None or pattern.kind != WORD:
                    raise self.fail("`case` arm requires a pattern word", token)
                patterns.append(self.advance())
                if self.at_operator("|"):
                    self.advance()
                    continue
                break
            self.expect_operator(")")
            body = self.parse_list(frozenset({"esac"}), frozenset({";;"}))
            arms.append(_CaseArm(patterns=tuple(patterns), body=body))
            if self.at_operator(";;"):
                self.advance()
                continue
            break
        if not self.at_word("esac"):
            raise self.fail("`case` command is not terminated", token)
        self.advance()
        return _Case(
            token=token,
            word=word,
            arms=tuple(arms),
            redirects=self.parse_redirects(),
        )


def _is_assignment(token: Token) -> bool:
    """Report whether one word carries an unquoted assignment name and `=`."""

    prefix = _assignment_prefix(token)
    marker = prefix.find("=")
    if marker <= 0:
        return False
    return _is_name(prefix[:marker])


@dataclass
class _ProcessFrame:
    """One shell process whose termination stays inside its own boundary."""

    is_child: bool = False
    terminations: list[tuple[int, str]] = field(default_factory=list)
    aborts: list[tuple[int, str]] = field(default_factory=list)

    @property
    def pending(self) -> list[tuple[int, str]]:
        """Return the transfers a parent shell continues from.

        A child process ends early when one of its commands fails under
        errexit, when a special built-in reports an error, or when an expansion
        fails. The parent shell then continues with the next command, so every
        such early end is an explicit transfer instead of an assumed
        continuation.
        """

        return [(index, TERMINATE) for index, _ in self.terminations] + list(
            self.aborts
        )


@dataclass
class _FunctionFrame:
    """One inlined function call whose `return` rejoins after the call."""

    return_pending: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class _LoopFrame:
    """One loop whose `break` and `continue` transfers stay explicit."""

    head: int
    break_pending: list[tuple[int, str]] = field(default_factory=list)


@dataclass(frozen=True)
class _Context:
    process: _ProcessFrame
    enclosures: tuple[Enclosure, ...] = ()
    in_subshell: bool = False
    asynchronous: bool = False
    call_path: tuple[str, ...] = ()
    loops: tuple[_LoopFrame, ...] = ()
    function: _FunctionFrame | None = None
    # Offset of the outermost call site whose body is being built, which is
    # when the shell runs this region.
    activation_offset: int = 0

    def enclosed(self, kind: str, token: Token | None = None) -> "_Context":
        return _Context(
            process=self.process,
            enclosures=self.enclosures + (Enclosure(kind=kind, token=token),),
            in_subshell=self.in_subshell,
            asynchronous=self.asynchronous,
            call_path=self.call_path,
            loops=self.loops,
            function=self.function,
            activation_offset=self.activation_offset,
        )

    def child_process(
        self, kind: str, token: Token | None = None, *, asynchronous: bool = False
    ) -> "_Context":
        """Enter a new shell process, so no transfer crosses the boundary."""

        return _Context(
            process=_ProcessFrame(is_child=True),
            enclosures=self.enclosures + (Enclosure(kind=kind, token=token),),
            in_subshell=True,
            asynchronous=self.asynchronous or asynchronous,
            call_path=self.call_path,
            loops=(),
            function=None,
            activation_offset=self.activation_offset,
        )

    def called(
        self,
        name: str,
        frame: _FunctionFrame,
        token: Token,
        activation_offset: int,
    ) -> "_Context":
        return _Context(
            process=self.process,
            enclosures=self.enclosures + (Enclosure(kind=FUNCTION_BODY, token=token),),
            in_subshell=self.in_subshell,
            asynchronous=self.asynchronous,
            call_path=self.call_path + (name,),
            # `break` and `continue` in a called body act on a loop declared
            # in that body, never on a loop around the call site.
            loops=(),
            function=frame,
            activation_offset=activation_offset,
        )

    def looped(
        self, frame: _LoopFrame, token: Token, kind: str = LOOP_BODY
    ) -> "_Context":
        return _Context(
            process=self.process,
            enclosures=self.enclosures + (Enclosure(kind=kind, token=token),),
            in_subshell=self.in_subshell,
            asynchronous=self.asynchronous,
            call_path=self.call_path,
            loops=self.loops + (frame,),
            function=self.function,
            activation_offset=self.activation_offset,
        )


@dataclass(frozen=True)
class _Dispatch:
    """One resolved command word with its arguments and terminal effect."""

    name: str | None
    token: Token | None
    arguments: tuple[Token, ...]
    effect: str | None
    dynamic: bool
    prefixed: bool


class _Draft:
    """Mutable node record used before reachability is known."""

    __slots__ = (
        "index",
        "kind",
        "token",
        "name",
        "words",
        "arguments",
        "effect",
        "termination",
        "enclosures",
        "in_subshell",
        "asynchronous",
        "dynamic",
        "call_path",
        "declaration",
        "redirected",
    )

    def __init__(
        self,
        index: int,
        kind: str,
        *,
        token: Token | None = None,
        name: str | None = None,
        words: tuple[Token, ...] = (),
        arguments: tuple[Token, ...] = (),
        effect: str | None = None,
        termination: str | None = None,
        enclosures: tuple[Enclosure, ...] = (),
        in_subshell: bool = False,
        asynchronous: bool = False,
        dynamic: bool = False,
        call_path: tuple[str, ...] = (),
        declaration: FunctionDeclaration | None = None,
        redirected: bool = False,
    ) -> None:
        self.index = index
        self.kind = kind
        self.token = token
        self.name = name
        self.words = words
        self.arguments = arguments
        self.effect = effect
        self.termination = termination
        self.enclosures = enclosures
        self.in_subshell = in_subshell
        self.asynchronous = asynchronous
        self.dynamic = dynamic
        self.call_path = call_path
        self.redirected = redirected
        self.declaration = declaration


class _Builder:
    """Build one reachable command graph from checked records and table."""

    def __init__(self, records: LexicalProjection, table: FunctionTable) -> None:
        self.records = records
        self.table = table
        self.drafts: list[_Draft] = []
        self.edges: list[Edge] = []
        self.recorded: set[Edge] = set()
        self.bodies: dict[str, _List] = {}
        self.declarations = {
            declaration.name_token.start.offset: declaration
            for declaration in table.declarations
        }

    def run(self) -> ExecutionGraph:
        entry = self.add(ENTRY)
        end = self.add(END)
        abort = self.add(ABORT)
        parser = _Parser(self.records.tokens, self.declarations)
        program = parser.parse_program()
        process = _ProcessFrame()
        context = _Context(process=process)
        pending = self.build_list(program, [(entry, SEQUENTIAL)], context)
        self.connect(list(pending), end)
        for index, status in process.terminations:
            if status in (TERMINATION_SUCCESS, TERMINATION_UNKNOWN):
                self.link(index, end, TERMINATE)
            if status in (TERMINATION_FAILURE, TERMINATION_UNKNOWN):
                self.link(index, abort, TERMINATE)
        return self.freeze(entry, end, abort)

    def add(self, kind: str, **fields: object) -> int:
        if len(self.drafts) >= MAX_NODES:
            token = fields.get("token")
            raise ShellExecutionError(
                f"supplied script exceeds the bounded graph size of {MAX_NODES} nodes",
                token.start if isinstance(token, Token) else None,
            )
        draft = _Draft(len(self.drafts), kind, **fields)
        self.drafts.append(draft)
        return draft.index

    def connect(self, pending: list[tuple[int, str]], target: int) -> None:
        for source, transfer in pending:
            self.link(source, target, transfer)

    def link(self, source: int, target: int, transfer: str) -> None:
        """Record one control transfer exactly once."""

        edge = Edge(source=source, target=target, transfer=transfer)
        if edge in self.recorded:
            return
        self.recorded.add(edge)
        self.edges.append(edge)

    def relabel(
        self, pending: list[tuple[int, str]], transfer: str
    ) -> list[tuple[int, str]]:
        return [(source, transfer) for source, _ in pending]

    def build_list(
        self, node: _List, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        if len(context.enclosures) >= MAX_DEPTH:
            token = self.first_token(node.items[0][0]) if node.items else None
            raise ShellExecutionError(
                f"region nesting exceeds the bounded depth of {MAX_DEPTH}",
                None if token is None else token.start,
            )
        for and_or, separator in node.items:
            if separator == "&":
                background = context.child_process(
                    ASYNC_LIST, self.first_token(and_or), asynchronous=True
                )
                self.build_and_or(and_or, self.relabel(pending, ASYNC), background)
                continue
            pending = self.build_and_or(and_or, pending, context)
        return pending

    def first_token(self, node: _AndOr) -> Token | None:
        member = node.first.members[0] if node.first.members else None
        return self.command_token(member)

    def command_token(self, member: object) -> Token | None:
        if isinstance(member, _Simple):
            for token in member.words or member.assignments:
                return token
            for redirect in member.redirects:
                return redirect.operator
            return None
        for attribute in ("token",):
            token = getattr(member, attribute, None)
            if isinstance(token, Token):
                return token
        return None

    def build_and_or(
        self, node: _AndOr, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        """Model one left-associative and-or list without assuming a status.

        An and-or list is evaluated left to right, so the status carried out of
        a short-circuited operand still selects the next operand. Successful
        and failing exit points are therefore tracked separately instead of
        letting a skipped operand bypass the rest of the list.
        """

        exits = self.build_pipeline(node.first, pending, context)
        succeeded = list(exits)
        failed = list(exits)
        for operator, pipeline in node.rest:
            operand = context.enclosed(CONDITIONAL_OPERAND, operator)
            if operator.text == "&&":
                entered = self.relabel(succeeded, ON_SUCCESS)
                exits = self.build_pipeline(pipeline, entered, operand)
                failed = _merge(self.relabel(failed, ON_FAILURE), exits)
                succeeded = list(exits)
            else:
                entered = self.relabel(failed, ON_FAILURE)
                exits = self.build_pipeline(pipeline, entered, operand)
                succeeded = _merge(self.relabel(succeeded, ON_SUCCESS), exits)
                failed = list(exits)
        return _merge(succeeded, failed)

    def build_pipeline(
        self, node: _Pipeline, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        if len(node.members) == 1:
            return self.build_command(node.members[0], pending, context)
        first = True
        for member in node.members:
            member_context = context.child_process(
                PIPELINE_MEMBER, self.command_token(member)
            )
            entering = pending if first else self.relabel(pending, PIPELINE)
            exits = self.build_command(member, entering, member_context)
            pending = exits + member_context.process.pending
            first = False
        return pending

    def build_command(
        self, node: object, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        if isinstance(node, _Simple):
            return self.build_simple(node, pending, context)
        if isinstance(node, _Declaration):
            return pending
        if isinstance(node, _BraceGroup):
            pending, skipped = self.build_redirects(node.redirects, pending, context)
            return self.build_list(
                node.body, pending, context.enclosed(BRACE_GROUP, node.token)
            ) + skipped
        if isinstance(node, _Subshell):
            pending, skipped = self.build_redirects(node.redirects, pending, context)
            inner = context.child_process(SUBSHELL, node.token)
            exits = self.build_list(node.body, pending, inner)
            return exits + inner.process.pending + skipped
        if isinstance(node, _If):
            return self.build_if(node, pending, context)
        if isinstance(node, _Loop):
            return self.build_loop(node, pending, context)
        if isinstance(node, _For):
            return self.build_for(node, pending, context)
        if isinstance(node, _Case):
            return self.build_case(node, pending, context)
        raise ShellExecutionError("unsupported command structure")

    def build_redirects(
        self,
        redirects: tuple[_Redirect, ...],
        pending: list[tuple[int, str]],
        context: _Context,
    ) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        """Model the expansions of a compound redirection and its skip path.

        A redirection is performed before the command it belongs to runs, so a
        redirection error skips the whole enclosed region. The second result is
        that explicit skip path, which is empty when the region carries no
        redirection.
        """

        skipped: list[tuple[int, str]] = []
        for redirect in redirects:
            tokens = [redirect.target]
            if redirect.heredoc is not None:
                tokens.append(redirect.heredoc)
            pending = self.build_expansions(tokens, pending, context)
            # The shell performs one redirection before it expands the next
            # one, so a failure here skips every later expansion as well as
            # the region itself.
            skipped.extend(self.relabel(pending, REDIRECTION_SKIP))
        return pending, skipped

    def build_expansions(
        self,
        tokens: list[Token],
        pending: list[tuple[int, str]],
        context: _Context,
        *,
        conditional: bool = False,
    ) -> list[tuple[int, str]]:
        """Model every command substitution the shell runs before a command."""

        segments: list[tuple[Segment, bool]] = []
        for token in sorted(tokens, key=lambda item: item.start.offset):
            segments.extend(
                (segment, conditional or nested)
                for segment, nested in _substitution_segments(token)
            )
        for segment, skippable in segments:
            parser = _Parser(segment.tokens)
            body = parser.parse_program()
            region = context
            if skippable:
                region = context.enclosed(EXPANSION_REGION, None)
            inner = region.child_process(SUBSTITUTION_REGION, None)
            exits = self.build_list(
                body, self.relabel(pending, SUBSTITUTION), inner
            )
            skipped = self.relabel(pending, EXPANSION_SKIP) if skippable else []
            pending = exits + inner.process.pending + skipped
        return pending

    def build_simple(
        self, node: _Simple, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        # The command words are expanded before the assignment prefix in every
        # reference shell. The shells then disagree about whether the prefix or
        # the redirections come next, so the prefix is placed last, where a
        # failing redirection can still skip it.
        pending = self.build_expansions(node.words, pending, context)
        pending, skipped = self.build_redirects(node.redirects, pending, context)
        pending = self.build_expansions(node.assignments, pending, context)
        dispatch = self.classify(node)
        name = dispatch.name
        name_token = dispatch.token
        arguments = dispatch.arguments
        effect = dispatch.effect
        dynamic = dispatch.dynamic
        termination = (
            _termination_status(effect, arguments)
            if effect in TERMINAL_EFFECTS
            else None
        )
        declaration = None
        if effect is None and name is not None and not dynamic and not dispatch.prefixed:
            declaration = self.resolve_call(name, name_token, context)
        index = self.add(
            COMMAND,
            token=name_token,
            name=name,
            words=node.words,
            arguments=arguments,
            effect=effect,
            termination=termination,
            enclosures=context.enclosures,
            in_subshell=context.in_subshell,
            asynchronous=context.asynchronous,
            dynamic=dynamic,
            call_path=context.call_path,
            declaration=declaration,
            redirected=bool(node.redirects),
        )
        self.connect(pending, index)
        if context.process.is_child:
            context.process.aborts.append((index, PROCESS_ABORT))
        if effect in TERMINAL_EFFECTS:
            assert termination is not None
            context.process.terminations.append((index, termination))
            return skipped
        if effect == EFFECT_MUTATE_TABLE:
            raise ShellExecutionError(
                f"`{name}` changes how a later command word resolves and has no"
                " bounded graph",
                None if name_token is None else name_token.start,
            )
        if effect == EFFECT_RETURN:
            if context.function is None:
                raise ShellExecutionError(
                    "`return` is not inside a function body in the current shell",
                    None if name_token is None else name_token.start,
                )
            context.function.return_pending.append((index, RETURNED))
            return skipped
        if effect in (EFFECT_BREAK, EFFECT_CONTINUE):
            return (
                self.build_transfer(node, index, effect, arguments, context) + skipped
            )
        if declaration is not None:
            exits = self.build_call(declaration, index, name_token, context)
            if node.redirects:
                # A redirection error skips the whole body of the call.
                exits = exits + [(index, REDIRECTION_SKIP)]
            return exits + skipped
        return [(index, SEQUENTIAL)] + skipped

    def resolve_call(
        self, name: str, token: Token | None, context: _Context
    ) -> FunctionDeclaration | None:
        """Return the function a command word runs at its activation time.

        A shell defines a function when its declaration executes, so a call
        that the shell reaches before that point runs an external utility, not
        the later body. The activation offset of an inlined body is the offset
        of the outermost call site, because that is when the body runs.
        """

        declaration = self.table.get(name)
        if declaration is None:
            return None
        if declaration.close_brace.end.offset > self.activation_offset(token, context):
            return None
        return declaration

    @staticmethod
    def activation_offset(token: Token | None, context: _Context) -> int:
        if context.call_path:
            return context.activation_offset
        return 0 if token is None else token.start.offset

    def build_transfer(
        self,
        node: _Simple,
        index: int,
        effect: str,
        arguments: tuple[Token, ...],
        context: _Context,
    ) -> list[tuple[int, str]]:
        position = None if not node.words else node.words[0].start
        level = 1
        if arguments:
            value = arguments[0].literal_value
            level = _literal_number(value) or 0
            if level < 1:
                raise ShellExecutionError(
                    f"`{effect}` requires an exact bounded positive literal level",
                    position,
                )
        if len(context.loops) < level:
            scope = "function" if context.function is not None else "shell"
            raise ShellExecutionError(
                f"`{effect}` is not inside {level} enclosing loops"
                f" in the current {scope}",
                position,
            )
        frame = context.loops[len(context.loops) - level]
        if effect == EFFECT_BREAK:
            frame.break_pending.append((index, BREAK))
        else:
            self.link(index, frame.head, CONTINUE)
        return []

    def build_call(
        self,
        declaration: FunctionDeclaration,
        index: int,
        token: Token | None,
        context: _Context,
    ) -> list[tuple[int, str]]:
        if declaration.name in context.call_path:
            raise ShellExecutionError(
                f"recursive call to `{declaration.name}` has no bounded graph",
                None if token is None else token.start,
            )
        if len(context.call_path) >= MAX_CALL_DEPTH:
            raise ShellExecutionError(
                f"call nesting exceeds the bounded depth of {MAX_CALL_DEPTH}",
                None if token is None else token.start,
            )
        body = self.bodies.get(declaration.name)
        if body is None:
            body = _Parser(declaration.body).parse_program()
            self.bodies[declaration.name] = body
        frame = _FunctionFrame()
        inner = context.called(
            declaration.name,
            frame,
            declaration.name_token,
            self.activation_offset(token, context),
        )
        exits = self.build_list(body, [(index, CALL)], inner)
        return self.relabel(exits, RETURNED) + frame.return_pending

    def build_if(
        self, node: _If, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        pending, skipped = self.build_redirects(node.redirects, pending, context)
        exits: list[tuple[int, str]] = list(skipped)
        for order, (condition, body) in enumerate(node.branches):
            # Only the first condition always runs once the `if` is reached;
            # an earlier branch succeeding skips every later condition.
            kind = CONDITION if order == 0 else ELIF_CONDITION
            condition_exits = self.build_list(
                condition, pending, context.enclosed(kind, node.token)
            )
            branch = self.build_list(
                body,
                self.relabel(condition_exits, CONDITION_TRUE),
                context.enclosed(THEN_BRANCH, node.token),
            )
            exits.extend(branch)
            pending = self.relabel(condition_exits, CONDITION_FALSE)
        if node.else_body is not None:
            exits.extend(
                self.build_list(
                    node.else_body, pending, context.enclosed(ELSE_BRANCH, node.token)
                )
            )
            return exits
        return exits + pending

    def build_loop(
        self, node: _Loop, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        pending, skipped = self.build_redirects(node.redirects, pending, context)
        head = self.add(
            LOOP,
            token=node.token,
            name=node.kind,
            enclosures=context.enclosures,
            in_subshell=context.in_subshell,
            asynchronous=context.asynchronous,
            call_path=context.call_path,
        )
        self.connect(pending, head)
        frame = _LoopFrame(head=head)
        # `while break; do ...; done` leaves its own loop, so the condition
        # runs inside this loop's frame rather than an enclosing one.
        condition_exits = self.build_list(
            node.condition,
            [(head, SEQUENTIAL)],
            context.looped(frame, node.token, CONDITION),
        )
        body_exits = self.build_list(
            node.body,
            self.relabel(condition_exits, LOOP_ENTER),
            context.looped(frame, node.token),
        )
        self.connect(self.relabel(body_exits, LOOP_REPEAT), head)
        return self.relabel(condition_exits, LOOP_EXIT) + frame.break_pending + skipped

    def build_for(
        self, node: _For, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        pending, skipped = self.build_redirects(node.redirects, pending, context)
        pending = self.build_expansions(list(node.words), pending, context)
        head = self.add(
            LOOP,
            token=node.token,
            name="for",
            words=node.words,
            enclosures=context.enclosures,
            in_subshell=context.in_subshell,
            asynchronous=context.asynchronous,
            call_path=context.call_path,
        )
        self.connect(pending, head)
        frame = _LoopFrame(head=head)
        # `for name in` with no word never enters the body, so the body has no
        # incoming edge and every command in it stays unreachable.
        entered = [] if node.explicit_list and not node.words else [(head, LOOP_ENTER)]
        body_exits = self.build_list(
            node.body, entered, context.looped(frame, node.token)
        )
        self.connect(self.relabel(body_exits, LOOP_REPEAT), head)
        return [(head, LOOP_EXIT)] + frame.break_pending + skipped

    def build_case(
        self, node: _Case, pending: list[tuple[int, str]], context: _Context
    ) -> list[tuple[int, str]]:
        pending, skipped = self.build_redirects(node.redirects, pending, context)
        pending = self.build_expansions([node.word], pending, context)
        head = self.add(
            CASE,
            token=node.token,
            name="case",
            words=(node.word,),
            enclosures=context.enclosures,
            in_subshell=context.in_subshell,
            asynchronous=context.asynchronous,
            call_path=context.call_path,
        )
        self.connect(pending, head)
        exits: list[tuple[int, str]] = [(head, CASE_SKIP)]
        for arm in node.arms:
            arm_context = context.enclosed(
                CASE_ARM, arm.patterns[0] if arm.patterns else None
            )
            # A pattern is expanded while the shell tests the arm, so a command
            # substitution in a pattern runs before the arm body.
            entered: list[tuple[int, str]] = [(head, CASE_MATCH)]
            for position, pattern in enumerate(arm.patterns):
                # Only the first alternative of an arm is always expanded; a
                # later alternative is expanded only when the earlier ones do
                # not match.
                entered = self.build_expansions(
                    [pattern], entered, arm_context, conditional=position > 0
                )
            exits.extend(self.build_list(arm.body, entered, arm_context))
        return exits + skipped

    def classify(self, node: _Simple) -> _Dispatch:
        """Resolve the dispatch target, arguments, and effect of one command.

        A transparent prefix suppresses shell-function lookup, so a word behind
        one names a utility or built-in and never runs a declared body. A
        `command -v` or `command -V` query runs nothing at all.
        """

        words = node.words
        position = 0
        replaced = False
        prefixed = False
        external = False
        disputed = False
        while position < len(words):
            token = words[position]
            value = token.literal_value
            if value is None:
                return _Dispatch(None, token, words[position + 1:], None, True, prefixed)
            if not prefixed and value in self.table:
                return _Dispatch(value, token, words[position + 1:], None, False, False)
            if value in AMBIGUOUS_PREFIXES:
                return _Dispatch(
                    value, token, words[position + 1:], None, True, prefixed
                )
            if not external and value in TRANSPARENT_PREFIXES:
                position, query, resolved = self.skip_prefix_options(
                    value, words, position + 1
                )
                if not resolved:
                    # An option this prefix does not define leaves the dispatch
                    # target unresolved instead of being guessed.
                    return _Dispatch(None, words[position], (), None, True, True)
                if query:
                    return _Dispatch(
                        value, token, tuple(words[position:]), None, False, True
                    )
                prefixed = True
                if value == "exec":
                    replaced = True
                if value in EXTERNAL_PREFIXES:
                    external = True
                if value in DISPUTED_PREFIXES:
                    disputed = True
                if position >= len(words):
                    # A transparent prefix with no command word runs the prefix
                    # itself; `exec` with redirections only does not replace
                    # the shell.
                    return _Dispatch(value, token, (), None, False, True)
                continue
            arguments = words[position + 1:]
            if disputed:
                # Deciding which operands the two readings agree about needs a
                # complete built-in inventory for every reference shell, so
                # every operand of a disputed prefix is rejected instead.
                raise ShellExecutionError(
                    f"`time {value}` runs in the current shell in one reference"
                    " shell and outside it in another",
                    token.start,
                )
            if replaced:
                effect: str | None = EFFECT_EXEC
            elif external:
                # The operand of an external prefix names a utility, so a
                # shell built-in name behind it has no shell effect.
                effect = None
            elif value == "unset" and self.removes_a_declaration(arguments):
                effect = EFFECT_MUTATE_TABLE
            else:
                effect = EFFECT_WORDS.get(value)
            return _Dispatch(value, token, arguments, effect, False, prefixed)
        return _Dispatch(None, None, (), None, False, prefixed)

    def removes_a_declaration(self, arguments: tuple[Token, ...]) -> bool:
        """Report whether one `unset` can remove a declared function.

        `unset -v name` removes a variable of that name even when a function
        shares it, while `unset -f name` and a mode-less `unset name` can
        remove the declaration the graph resolved calls against.
        """

        names: list[str | None] = []
        variables_only = False
        for argument in arguments:
            value = argument.literal_value
            if value is not None and value.startswith("-") and len(value) > 1:
                letters = set(value[1:])
                if "f" in letters:
                    return True
                if "v" in letters:
                    variables_only = True
                continue
            names.append(value)
        if variables_only:
            return False
        return any(name is None or name in self.table for name in names)

    def skip_prefix_options(
        self, prefix: str, words: tuple[Token, ...], position: int
    ) -> tuple[int, bool, bool]:
        """Consume the exact options one transparent prefix defines.

        The third result is false when an option is not part of the prefix
        grammar, because the command word cannot be resolved from the records
        alone in that case.
        """

        letters = PREFIX_OPTION_LETTERS.get(prefix, frozenset())
        operands = PREFIX_OPTION_OPERANDS.get(prefix, frozenset())
        query = False
        while position < len(words):
            argument = words[position].literal_value
            if argument is None:
                return position, False, False
            if prefix == "env" and _is_assignment(words[position]):
                position += 1
                continue
            if argument == "--":
                return position + 1, query, True
            if not argument.startswith("-") or argument == "-":
                break
            if argument in operands:
                if position + 1 >= len(words):
                    return position, False, False
                position += 2
                continue
            if argument.startswith("--"):
                name = argument.split("=", 1)[0]
                if name not in operands:
                    return position, False, False
                position += 1
                continue
            cluster = set(argument[1:])
            if not cluster <= letters:
                return position, False, False
            if prefix == "command" and cluster & COMMAND_QUERY_LETTERS:
                query = True
            position += 1
        return position, query, True

    def freeze(self, entry: int, end: int, abort: int) -> ExecutionGraph:
        count = len(self.drafts)
        successors: list[list[int]] = [[] for _ in range(count)]
        predecessors: list[list[int]] = [[] for _ in range(count)]
        for edge in self.edges:
            successors[edge.source].append(edge.target)
            predecessors[edge.target].append(edge.source)
        reachable = _reachable(entry, successors)
        dominators = _dominators(count, predecessors, entry, reachable)
        coreachable = _reachable(end, predecessors) if end in reachable else set()
        postdominators = _dominators(count, successors, end, coreachable)
        guaranteed = dominators[end] if end in reachable else 0
        nodes = tuple(
            Node(
                index=draft.index,
                kind=draft.kind,
                token=draft.token,
                name=draft.name,
                words=draft.words,
                arguments=draft.arguments,
                effect=draft.effect,
                termination=draft.termination,
                enclosures=draft.enclosures,
                in_subshell=draft.in_subshell,
                asynchronous=draft.asynchronous,
                dynamic=draft.dynamic,
                call_path=draft.call_path,
                declaration=draft.declaration,
                redirected=draft.redirected,
                reachable=draft.index in reachable,
                guaranteed=bool(guaranteed >> draft.index & 1),
            )
            for draft in self.drafts
        )
        return ExecutionGraph(
            source=self.records.source,
            nodes=nodes,
            edges=tuple(self.edges),
            entry_index=entry,
            end_index=end,
            abort_index=abort,
            dominator_bits=tuple(dominators),
            postdominator_bits=tuple(postdominators),
            table=self.table,
        )


def _merge(
    first: list[tuple[int, str]], second: list[tuple[int, str]]
) -> list[tuple[int, str]]:
    """Return one pending transfer per source node, in first-seen order."""

    merged: dict[int, str] = {}
    for source, transfer in list(first) + list(second):
        merged.setdefault(source, transfer)
    return [(source, transfer) for source, transfer in merged.items()]


def _termination_status(effect: str | None, arguments: tuple[Token, ...]) -> str:
    """Classify how a terminal command ends the script.

    A literal status ends the script successfully when the status the shell
    reports is zero. The reported status is the requested status reduced to
    eight bits, so `exit 256` is a successful termination. A missing or
    unresolved status, and every `exec` replacement, can end the script either
    way, so both terminations stay explicit instead of being assumed.
    """

    if effect != EFFECT_EXIT or not arguments:
        return TERMINATION_UNKNOWN
    reported = _literal_number(arguments[0].literal_value)
    if reported is None:
        return TERMINATION_UNKNOWN
    reported %= 256
    return TERMINATION_SUCCESS if reported == 0 else TERMINATION_FAILURE


def _literal_number(value: str | None) -> int | None:
    """Read one exact bounded decimal literal, or report that there is none."""

    if value is None or not value.isascii() or not value.isdecimal():
        return None
    digits = value.lstrip("0") or "0"
    if len(digits) > MAX_LITERAL_DIGITS:
        return None
    return int(digits)


def _reachable(entry: int, successors: list[list[int]]) -> set[int]:
    seen = {entry}
    stack = [entry]
    while stack:
        current = stack.pop()
        for target in successors[current]:
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return seen


def _dominators(
    count: int, predecessors: list[list[int]], entry: int, reachable: set[int]
) -> list[int]:
    """Return one dominator bit set per node over the reachable subgraph."""

    full = (1 << count) - 1
    dominators = [full if index in reachable else 0 for index in range(count)]
    dominators[entry] = 1 << entry
    order = sorted(index for index in reachable if index != entry)
    changed = True
    while changed:
        changed = False
        for index in order:
            current = full
            for source in predecessors[index]:
                if source in reachable:
                    current &= dominators[source]
            current |= 1 << index
            if current != dominators[index]:
                dominators[index] = current
                changed = True
    return dominators
