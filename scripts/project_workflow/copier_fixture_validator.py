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
  version commits, exactly one inventory-driven copy and staging region, no
  direct invocation of the migration snapshot script or the `copier` binary,
  and no redefinition or shadowing of a command a bound observation runs,
  written in the fixture or in a library the fixture sources.
  These rules describe operations the fixture already owns, so they
  hold for a fixture that carries no migration transition region. The one
  region rule that needs a fact the supplied bytes do not carry is the staging
  rule: the update source may hold only the paths the Copier update inventory
  declares, and the fixture names that inventory through a positional
  parameter, so the declared paths are supplied to the checker instead.
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
the fixture sources runs with the fixture's own authority, so every library a
caller binds is read through the shadowing rule, and a source that names any
other path is rejected rather than read as declaring nothing. An operation
moved into a sourced file is still reported as missing by the rule that
requires it: the contract states what the supplied bytes prove, and it never
treats a sourced region as evidence that a required operation exists.
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


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
        EFFECT_SOURCE,
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
        EFFECT_SOURCE,
        EFFECT_TRAP,
        ExecutionGraph,
        LOOP_BODY,
        Node,
        ShellExecutionError,
    )


__all__ = [
    "CopierFixtureError",
    "Finding",
    "INVENTORY_PATH",
    "RULES",
    "RULE_ALTERNATE_PATH",
    "RULE_UNRESOLVED_DISPATCH",
    "RULE_BOUNDED_POLL",
    "RULE_CHILD_PID",
    "RULE_CHILD_REAP",
    "RULE_COMMAND_SHADOWING",
    "RULE_DIRECT_INVOCATION",
    "RULE_GUARDIAN",
    "RULE_INVENTORY_REGION",
    "RULE_RELEASE_PATH",
    "RULE_STATE_ORDER",
    "RULE_STRUCTURE",
    "RULE_UPDATE_CHILD",
    "RULE_VERSION_COMMIT",
    "SOURCED_LIBRARY_PATHS",
    "check",
    "declared_paths",
    "library_sources",
    "main",
    "read_inventory",
    "read_libraries",
    "validate",
]


# The Copier update source inventory this repository ships. A fixture builds
# its own inventory path from a positional parameter, so no supplied byte
# places that file and the declared paths cannot be recovered from the fixture
# text. They are read from the inventory this checker is installed beside
# instead, and a caller that knows the inventory supplies it directly.
INVENTORY_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests/fixtures/orchestration/copier-update-source-inventory.txt"
)


def declared_paths(values: Iterable[str]) -> frozenset[tuple[str, ...]]:
    """Return the update source paths written inventory lines declare.

    Each line declares one path relative to the update source. A blank line
    declares nothing, and a repeated separator is dropped so one written path
    settles to one segment tuple.
    """

    declared: set[tuple[str, ...]] = set()
    for value in values:
        written = value.strip()
        if not written:
            continue
        declared.add(tuple(segment for segment in written.split("/") if segment))
    return frozenset(declared)


def read_inventory(path: Path | None = None) -> frozenset[tuple[str, ...]]:
    """Return the paths one inventory file declares.

    An inventory this checker cannot read declares no path, so every staging
    outside the inventory region is then rejected rather than accepted.
    """

    try:
        text = (INVENTORY_PATH if path is None else path).read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    return declared_paths(text.splitlines())


# The library files a transition fixture sources into its own shell, written
# as the repository-relative paths a sourcing file names them by. A sourced
# file is run by the shell that sources it, so a declaration written there
# rebinds a name for every bound observation of the sourcing file while that
# file keeps exactly the text it was committed with. The bound set is decided
# here rather than followed from whatever a source operand expands to, so this
# checker keeps its text-only boundary and its refusal stays decidable: a
# source that names a path outside the bound set is rejected as unread instead
# of being read as a line that declares nothing.
SOURCED_LIBRARY_PATHS = ("tests/lib-copier.sh",)
# The directory the bound libraries are read from when a caller supplies none.
LIBRARY_ROOT = Path(__file__).resolve().parents[2]
# The one name a bound library may be sourced under, and the spelling that
# writes it. Reading any anchor would let a fixture write a library of its own
# under a directory it controls, source it under a bound-looking path, and be
# checked against the committed bytes rather than the bytes the shell runs, so
# the anchor is bound here exactly as the path behind it is. The value written
# for the anchor is bound the same way, because a value that merely mentions
# the invocation can still expand to a directory the fixture fills itself, and
# no text-only reading settles where an arbitrary expansion lands. A fixture
# that writes the anchor another way is therefore rejected rather than read,
# so changing that line means binding the new spelling here.
LIBRARY_ANCHOR_NAME = "root"
LIBRARY_ANCHOR_PATTERN = re.compile(
    r"\A\$(?:\{" + LIBRARY_ANCHOR_NAME + r"\}|" + LIBRARY_ANCHOR_NAME + r")/(.+)\Z"
)
LIBRARY_ANCHOR_VALUES = (
    "$1",
    '$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)',
)


def library_sources(values: Mapping[str, str | bytes]) -> dict[str, str]:
    """Return the text of every sourced library one caller binds.

    Each key is the repository-relative path a sourcing file writes the
    library as, and each value carries the bytes this checker reads it from.
    Only a library bound here is read, so a source that names any other path
    is rejected rather than passed over.
    """

    return {str(path): _decode(text) for path, text in values.items()}


def read_libraries(root: Path | None = None) -> dict[str, str]:
    """Return the bound sourced libraries this checker is installed beside.

    A library this checker cannot read stays unbound, so the source that names
    it is rejected rather than accepted on bytes nothing supplied.
    """

    base = LIBRARY_ROOT if root is None else root
    libraries: dict[str, str] = {}
    for relative in SOURCED_LIBRARY_PATHS:
        try:
            libraries[relative] = (base / relative).read_text(encoding="utf-8")
        except OSError:
            continue
    return libraries


RULE_STRUCTURE = "structure"
RULE_VERSION_COMMIT = "version_commit"
RULE_INVENTORY_REGION = "inventory_region"
RULE_DIRECT_INVOCATION = "direct_invocation"
RULE_COMMAND_SHADOWING = "command_shadowing"
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
    RULE_COMMAND_SHADOWING,
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


# A positional parameter is a name too, and the value it holds is whatever the
# call site writes in that position. It is spelled with digits, which no other
# name may start with, so the two never collide in one binding table. Only the
# braced form reads more than one digit, exactly as the shell does.
SHIFT_DISTANCE_LIMIT = 16
"""How many distances one body may shift its parameters before it is unread."""

BRACED_POSITION_PATTERN = re.compile(r"\$\{([0-9]+)\}")


PLAIN_POSITION_PATTERN = re.compile(r"\$([0-9])")


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
LOOP_LIST_KEYWORD = "in"
LOOP_BODY_KEYWORDS = frozenset({"do", ";", "\n"})
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
# The commands one bound observation of the fixture runs. Every rule above
# reads the written text of an operation, so a fixture that gives one of these
# names another meaning keeps that committed text while the observation it
# performs stops happening: `grep` no longer reads the attempt state, `[` no
# longer compares the poll counter, `kill` no longer signals the child, `read`
# no longer turns the inventory loop, and `touch` no longer performs the
# release. The name itself is therefore protected, rather than any single
# spelling of one redefinition.
OBSERVED_COMMANDS = (
    frozenset(
        {
            # the bounded poll limit tests and the positive guardian test
            "[",
            "test",
            # the published transition identifier the cleanup handler reads
            "cat",
            # the pending and consumed attempt-state assertions
            "grep",
            # the guardian identifier recovered from the attempt state
            "sed",
            # the child termination, the forced termination, and the
            # guardian stop
            "kill",
            # the poll turn and the termination grace period
            "sleep",
            # the bounded child reap
            "wait",
            # the guarded exit one bounded poll is proved by
            "exit",
            # the cleanup handler every release path is read through
            "trap",
            # the inventory loop that drives the copy and staging region
            "read",
            # the working directory a Copier write destination is placed from
            "cd",
            # the version commits and the inventory staging
            "git",
        }
    )
    | RELEASE_COMMANDS
)
# The observed names a shell resolves as a builtin or a function before it
# searches `PATH`. A written helper file of one of these names is never the
# command that runs, so only a declaration can rebind them.
OBSERVED_BUILTINS = frozenset({"[", "cd", "exit", "kill", "read", "test", "trap", "wait"})
# A shell finds a command written as a bare name through `PATH`, so a helper
# file the fixture writes under a searched directory rebinds the command a
# bound observation runs just as a declaration does.
SHADOWED_HELPER_COMMANDS = OBSERVED_COMMANDS - OBSERVED_BUILTINS
# The commands that put a written helper file in place. A redirection writes
# one as well, and it is read from every operation rather than from this set.
HELPER_WRITING_COMMANDS = frozenset({"cp", "install", "ln", "mv", "tee", "touch"})
# The helper-writing commands whose every operand is a path they create. The
# remaining ones write their last operand, and write inside it when that
# operand names a directory.
HELPER_OPERAND_COMMANDS = frozenset({"touch", "tee"})
# The name of the command search path, its element separator, and the commands
# that give a name a value without writing it in command position.
SEARCH_PATH_NAME = "PATH"
SEARCH_PATH_SEPARATOR = ":"
EXPORTING_COMMANDS = frozenset({"export", "readonly", "declare", "typeset"})
# The command that runs another command with an environment it is given, and
# the commands that bind the name written as their operand rather than reading
# it as data.
ENVIRONMENT_COMMANDS = frozenset({"env"})
NAME_BINDING_COMMANDS = frozenset({"read", "unset", "getopts"})
# The pieces of one written word that a shell given that word as a program
# would read as separate words.
CARRIED_WORD_PATTERN = re.compile(r"[^\s;|&()<>'\"$`]+")
ESCAPE_MARK = "\\"
# The written words that open a compound command and the words that close it.
# A compound the shell may run again is kept apart, because it expands a
# redirection word once per pass.
ENCLOSURE_CLOSERS = {
    "}": frozenset({"{"}),
    SUBSHELL_CLOSE: frozenset({SUBSHELL_OPEN}),
    "fi": frozenset({"if"}),
    "done": frozenset({"for", "while", "until"}),
    "esac": frozenset({"case"}),
}
ENCLOSURE_OPENERS = frozenset({"{", "if", "for", "while", "until", "case"})
SUBSHELL_OPEN = "("
SUBSHELL_CLOSE = ")"
REPEATING_ENCLOSURES = frozenset({"for", "while", "until"})
# `hash -p` binds one command name to one path ahead of every `PATH` lookup,
# which is a third way to rebind a name that no checked projection rejects.
COMMAND_HASH = "hash"
HASH_PATH_OPTION = "p"


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
    deferred: bool = False
    """Whether the graph resolves no call site that gives this command values.

    A body reached only through a trap action or a dispatch whose command word
    is an expansion holds no call environment, so its words are settled
    against every value the fixture ever binds instead.
    """

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
            if match is None:
                match = BRACED_POSITION_PATTERN.match(
                    word, index
                ) or PLAIN_POSITION_PATTERN.match(word, index)
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
            if name.isdigit():
                # A positional parameter holds what a call site writes. Where
                # no call site binds it, the supplied bytes fix no value for
                # it, so it names no path rather than naming one of its own.
                return None
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

    if operation.deferred:
        return _settle_deferred_word(fixture, word)
    return _settle_word(
        word, fixture.bindings_for(operation), fixture.unsettled_for(operation)
    )


def _settle_deferred_word(
    fixture: _Fixture, word: str
) -> frozenset[tuple[bool, tuple[str, ...]]]:
    """Return every path one word of an unmodelled body may name.

    No call site the graph resolves says which values such a body holds, and a
    trap action or a dispatch the graph cannot read runs it at a point no
    written text fixes, so every value the fixture binds anywhere is read.
    That names more files than the shell creates and never fewer.
    """

    unsettled = fixture.unsettled_names()
    read = _read_names(word)
    settled: set[tuple[bool, tuple[str, ...]]] = set()
    for place in _binding_places(fixture, len(fixture.text)):
        bindings = fixture.bindings_before(place)
        if not read <= frozenset(bindings):
            continue
        settled |= _settle_word(word, bindings, unsettled)
    return frozenset(settled)


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
# The launcher option letters that ask where a command is found instead of
# running it. A body reduced to such a query names Copier while performing no
# Copier operation, so the wrapper the fixture runs as an operation is read
# through this distinction rather than through the name alone.
COPIER_QUERY_OPTIONS = frozenset({"v", "V"})
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

    return _word_literals(run.words)


def _word_literals(words: Sequence[Token]) -> tuple[str | None, ...]:
    """Return the text each of one command's words reads as, or ``None`` for any other.

    The words are read as a sequence rather than from a written run, because a
    command written inside an expansion is placed against no written run and
    still writes the words the checked graph records for it.
    """

    return tuple(_token_text(word) for word in words)


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


def _written_operands(words: Sequence[Token], literals: tuple[str | None, ...], index: int):
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
        operands.append(words[place])
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
        operands = _written_operands(run.words, literals, index)
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
        operands = _written_operands(run.words, literals, index)
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
        self._positional: dict[tuple[int, int | None], _Bindings] = {}
        self._positional_names: _Bindings | None = None
        self._resolving: set[int] = set()
        self._declaration_assigned: dict[str, frozenset[str]] = {}
        self._loop_heads: tuple[tuple[str, tuple[Token, ...], tuple[int, int]], ...] | None = None
        self._loop_values: dict[int, _Bindings] = {}
        self._assigning: set[str] = set()
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

    def loop_heads(
        self,
    ) -> tuple[tuple[str, tuple[Token, ...], tuple[int, int]], ...]:
        """Return the name each loop head binds and the words it binds it from."""

        if self._loop_heads is not None:
            return self._loop_heads
        extents = sorted(self.loop_extents().items())
        heads: list[tuple[str, tuple[Token, ...], tuple[int, int]]] = []
        for run in self.command_runs():
            for index, token in enumerate(run.tokens[:-1]):
                if _token_text(token) != LOOP_KEYWORD:
                    continue
                written = _token_text(run.tokens[index + 1])
                if written is None or not NAME_PATTERN.fullmatch(written):
                    continue
                rest = run.tokens[index + 2 :]
                if not rest or _token_text(rest[0]) != LOOP_LIST_KEYWORD:
                    continue
                words: list[Token] = []
                for item in rest[1:]:
                    if _token_text(item) in LOOP_BODY_KEYWORDS:
                        break
                    words.append(item)
                extent = next(
                    (
                        (start, end)
                        for start, end in extents
                        if start <= token.start.offset <= end
                    ),
                    None,
                )
                if extent is None or not words:
                    continue
                heads.append((written, tuple(words), extent))
        self._loop_heads = tuple(heads)
        return self._loop_heads

    def loop_values(self, offset: int) -> "_Bindings":
        """Return the values each loop head binds its name to at one offset.

        A loop head binds its name once per round from the words written after
        `in`, so a word written under the loop reads one of those words. Every
        word is read together, which names more values than one round holds and
        never fewer. A head word this checker cannot read, and one that runs a
        substitution of its own once per round, both leave the name unproven
        rather than settled, so a word written from it is reported instead of
        accepted.
        """

        cached = self._loop_values.get(offset)
        if cached is not None:
            return dict(cached)
        values: _Bindings = {}
        unsettled = self.unsettled_names()
        for name, words, extent in self.loop_heads():
            if not extent[0] <= offset <= extent[1]:
                continue
            environment = self.bindings_before(extent[0])
            held: tuple[_Parts, ...] | None = ()
            for token in words:
                parts = _word_parts(
                    token.text,
                    f"l{token.start.offset}",
                    splits=False,
                    anchored=self._anchors_a_substitution(),
                )
                settled = (
                    None
                    if parts is None
                    else _resolve_parts(parts, environment, unsettled)
                )
                if parts is not None and _carries_substitution((parts,)):
                    # A loop head runs its substitution once per round, so the
                    # value it produces is not one two readers may compare.
                    settled = None
                if settled is None:
                    held = None
                    break
                held = held + tuple(value for value in settled if value not in held)
            values[name] = held or None
        self._loop_values[offset] = dict(values)
        return values

    def declaration_assigned_names(self, name: str) -> frozenset[str]:
        """Return every name that running one declared function may assign.

        A call replaces a value a reader above it settled only when the body it
        reaches assigns that name, whether the body writes the assignment
        itself or reaches a further body that writes it. A call this walk
        re-enters proves nothing, so every name the fixture assigns is returned
        there and the reader settles nothing through it. A dispatch whose
        command word is an expansion may reach any declared body, so it is read
        the same way: leaving it out let one indirection replace a name the
        reader believed it had settled.
        """

        cached = self._declaration_assigned.get(name)
        if cached is not None:
            return cached
        if name not in self.table or name in self._assigning:
            return frozenset(assignment.name for assignment in self.assignments)
        declaration = self.table[name]
        span = (declaration.start.offset, declaration.end.offset)
        names = {
            assignment.name
            for assignment in self.assignments
            if span[0] <= assignment.offset <= span[1]
        }
        self._assigning.add(name)
        try:
            for operation in self.operations:
                if not span[0] <= operation.offset <= span[1]:
                    continue
                if operation.name == name:
                    continue
                if operation.name is None and operation.node.dynamic:
                    names |= self.dispatch_assigned_names(operation)
                    continue
                if operation.name in self.table:
                    names |= self.declaration_assigned_names(operation.name)
        finally:
            self._assigning.discard(name)
        settled = frozenset(names)
        if not self._assigning:
            self._declaration_assigned[name] = settled
        return settled

    def dispatch_assigned_names(self, operation: _Operation) -> frozenset[str]:
        """Return every name a dispatch this checker cannot read may assign.

        A command word written as an expansion runs whatever that expansion
        carries. When every value it may carry is written out and none of them
        spells a declared function, the dispatch runs a separate program, which
        assigns no name in this shell. Otherwise it may run any declared body,
        so every name the fixture assigns is returned and the reader settles
        nothing across it.
        """

        every = frozenset(assignment.name for assignment in self.assignments)
        if not self.expansions_are_exact(operation):
            return every
        texts = self.expansions(operation)
        if not texts:
            return every
        names: set[str] = set()
        for text in texts:
            for word in text.split():
                candidate = _strip(word)
                if candidate in self.table:
                    names |= self.declaration_assigned_names(candidate)
                elif "/" in candidate:
                    # A word carrying a path separator names a file to run,
                    # never a function this fixture declares.
                    continue
                elif "$" in candidate:
                    return every
        return frozenset(names)

    def locally_settled_names(self, offset: int) -> frozenset[str]:
        """Return every body name one reader inside that body may settle.

        A name a function body assigns is unsettled everywhere, because the
        body runs where it is called and a reader written below the call would
        otherwise read a value written above it. A reader written inside the
        declaring body, below the assignment, is not such a reader: every
        assignment of the name is written in that body above it, so the value
        it reads is the one written there. The assignment must also be written
        on the body's own path, because one written under a condition, in a
        loop, or in a detached span leaves the earlier value in place.
        """

        declarations = [
            declaration
            for declaration in self.table.declarations
            if declaration.start.offset <= offset <= declaration.end.offset
        ]
        if not declarations:
            return frozenset()
        declaration = max(declarations, key=lambda item: item.start.offset)
        detached = self.detached_spans()
        span = (declaration.start.offset, declaration.end.offset)
        conditional = [
            extent
            for extent in self._conditional_spans
            if extent != span and span[0] <= extent[0] and extent[1] <= span[1]
        ]
        settled: set[str] = set()
        latest: dict[str, int] = {}
        outside: set[str] = set()
        for assignment in self.assignments:
            if not declaration.start.offset <= assignment.offset <= offset:
                outside.add(assignment.name)
                continue
            if any(
                start <= assignment.offset <= end for start, end in conditional
            ) or any(start <= assignment.offset <= end for start, end in detached):
                outside.add(assignment.name)
                continue
            latest[assignment.name] = max(
                latest.get(assignment.name, assignment.offset), assignment.offset
            )
            settled.add(assignment.name)
        declared = {item.name for item in self.table.declarations}
        for name in sorted(settled):
            if name not in outside:
                continue
            # Another body assigns this name, so a call that reaches such a
            # body between the value read here and the assignment above it may
            # replace it. A call that reaches no body assigning the name
            # cannot, so the value written above stays the value read here.
            if any(
                latest[name] < operation.offset <= offset
                and operation.name in declared
                and name in self.declaration_assigned_names(operation.name)
                for operation in self.operations
            ):
                settled.discard(name)
        return frozenset(settled)

    def unsettled_for(self, operation: _Operation) -> frozenset[str]:
        """Return every name one operation cannot settle where it is written."""

        unsettled = self.unsettled_names()
        if self._unknown_binding or self.unaccepted_constructs():
            return unsettled
        looped = frozenset(
            name
            for name, held in self.loop_values(operation.offset).items()
            if held is not None
        )
        unsettled = unsettled - looped
        local = self.locally_settled_names(operation.offset)
        if not local:
            return unsettled
        elsewhere = (
            MUTABLE_SHELL_NAMES
            | self.written_assigned_names()
            | self.prefix_assigned_names()
            | self.command_assigned_names()
            | self.loop_assigned_names()
            | self.expansion_assigned_names()
        )
        return frozenset(unsettled - (local - elsewhere))

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
        bindings: _Bindings = dict(self.positional_names())
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
        function body may run again with another value, so a value that writes
        a substitution of its own is bound to ``None`` there. A substitution a
        name carries into the value is not one of those: it was evaluated where
        that name was bound, and this same rule already proved that binding
        runs once, so every reader of it reads one value.
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
        written = parts is not None and _carries_substitution((parts,))
        if settled is not None and not single and written:
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
    def positional_names(self) -> "_Bindings":
        """Return every positional parameter this fixture reads, held unproven.

        The parameters a script is called with come from outside the supplied
        bytes, so nothing here places them. Seeding them as unproven keeps a
        word written with one from settling to a path of its own, which is what
        the value a call site writes later replaces inside a function body.
        """

        if self._positional_names is None:
            self._positional_names = {
                match.group(1): None
                for match in PARAMETER_POSITION_PATTERN.finditer(self.text)
            }
        return dict(self._positional_names)

    def _shifted_by(
        self, declaration, offset: int
    ) -> tuple[tuple[int, ...], bool] | None:
        """Return every distance one body may shift its parameters.

        The answer is the set of distances the body may hold where one word is
        read, together with whether a loop may carry the shift past every
        distance the set names. A shift the shell always reaches moves every
        held distance alike. A shift written under a condition, on the right of
        a list operator, in a detached span, or on a path this checker cannot
        prove is reached runs on some turns and not on others, so the distance
        that skips it and the distance that takes it both stay possible and
        both are kept: reading a body at every distance it may hold names more
        values than one run holds and never fewer. A shift a loop wraps runs
        once per turn and the loop carries control back above the word that
        reads it, so it is admitted whether it stands above or below that word
        and it fixes no bounded distance at all. A shift written with a word
        this checker cannot read fixes no distance and leaves the whole body
        holding no parameter this checker can place.
        """

        span = (declaration.start.offset, declaration.end.offset)
        loops = tuple(
            (start, end)
            for start, end in self.loop_extents().items()
            if span[0] <= start and end <= span[1]
        )
        uncertain = [
            extent
            for extent in self._conditional_spans
            if extent != span and span[0] <= extent[0] and extent[1] <= span[1]
        ]
        uncertain.extend(self.detached_spans())
        carrying = tuple(
            extent for extent in loops if extent[0] <= offset <= extent[1]
        )
        distances = {0}
        carried = False
        for operation in self.operations:
            if operation.name != "shift":
                continue
            if not (span[0] <= operation.offset <= span[1]):
                continue
            looped = any(
                start <= operation.offset <= end for start, end in loops
            )
            if operation.offset > offset and not any(
                start <= operation.offset <= end for start, end in carrying
            ):
                continue
            words = _operation_words(operation)
            if len(words) == 1:
                moved = 1
            else:
                written = _strip(words[1].text)
                if not written.isdigit():
                    return None
                moved = int(written)
            if looped:
                if moved:
                    carried = True
                continue
            certain = operation.offset in self.unconditional_positions() and not any(
                start <= operation.offset <= end for start, end in uncertain
            )
            moved_set = {held + moved for held in distances}
            distances = moved_set if certain else distances | moved_set
            if len(distances) > SHIFT_DISTANCE_LIMIT:
                return None
        return tuple(sorted(distances)), carried

    def positional_bindings(self, offset: int) -> "_Bindings":
        """Return the values each positional parameter holds inside one body.

        A function body runs with the words its call sites write, so a
        parameter holds whatever any reachable call writes in that position.
        Every call site is read together rather than one at a time, which names
        more values than one run holds and never fewer, and a call word this
        checker cannot read drops only itself: keeping the words its siblings
        write is what stops one unreadable call from hiding a readable one. A
        call site is read in the environment it runs in, so a word it writes
        from its own parameter carries the value the call above it writes, and
        a call this walk re-enters proves nothing. A position no call site
        writes and a body whose parameters are shifted by an unread amount both
        stay unproven.
        """

        declarations = [
            declaration
            for declaration in self.table.declarations
            if declaration.start.offset <= offset <= declaration.end.offset
        ]
        if not declarations:
            return {}
        declaration = max(declarations, key=lambda item: item.start.offset)
        positions = sorted(self.positional_names())
        reach = self._shifted_by(declaration, offset)
        key = (declaration.start.offset, reach)
        cached = self._positional.get(key)
        if cached is not None:
            return dict(cached)
        bindings: _Bindings = {position: None for position in positions}
        if declaration.start.offset in self._resolving:
            return bindings
        calls = [
            operation
            for operation in self.operations
            if operation.name == declaration.name and operation.reachable
        ]
        if reach is not None and calls:
            distances, carried = reach
            self._resolving.add(declaration.start.offset)
            try:
                environments = [
                    (call, self.bindings_for(call), self.unsettled_for(call))
                    for call in calls
                ]
            finally:
                self._resolving.discard(declaration.start.offset)
            for position in positions:
                place = int(position)
                if place == 0:
                    continue
                held: tuple[_Parts, ...] = ()
                for call, environment, unsettled in environments:
                    words = _operation_words(call)
                    indexes = (
                        range(place + min(distances), len(words))
                        if carried
                        else tuple(place + shifted for shifted in distances)
                    )
                    for index in indexes:
                        if not 0 <= index < len(words):
                            continue
                        parts = _word_parts(
                            words[index].text,
                            f"p{call.offset}:{index}",
                            splits=False,
                            anchored=self._anchors_a_substitution(),
                        )
                        settled = (
                            None
                            if parts is None
                            else _resolve_parts(parts, environment, unsettled)
                        )
                        if settled is None:
                            continue
                        held = held + tuple(
                            value for value in settled if value not in held
                        )
                bindings[position] = held or None
        if not self._resolving:
            self._positional[key] = dict(bindings)
        return bindings

    def bindings_for(self, operation: _Operation) -> "_Bindings":
        """Return the settled parts each name may hold where one operation runs.

        A function body runs where it is called, not where it is written, so a
        name the body reads carries the value its call site holds. Every
        reachable call environment is added to the environment written above
        the body, and a function called from another function runs where that
        caller runs, so the call sites are followed outward. Each call site is
        visited once and a fixture writes finitely many, so the walk always
        terminates.

        A parameter the call site writes is installed last, and every
        assignment the enclosing body makes above the operation is then read
        again against it, because a name bound from a parameter settles only
        once the value that parameter carries is known.
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
        positional = self.positional_bindings(operation.offset)
        if positional:
            bindings.update(positional)
            unsettled = self.unsettled_for(operation)
            for assignment in sorted(self.assignments, key=lambda item: item.offset):
                if assignment.offset >= operation.offset:
                    break
                if not self._inside_declaration(assignment.offset):
                    continue
                bindings.pop(assignment.name, None)
                self._bind_value(bindings, assignment, unsettled)
        bindings.update(self.loop_values(operation.offset))
        if self._resolving:
            # A value read while one call walk is open may hold the unproven
            # fallback that walk installs, so it is never kept for later.
            return bindings
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


def _check_inventory_region(
    fixture: _Fixture, declared: frozenset[tuple[str, ...]]
) -> list[Finding]:
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
    findings.extend(
        _check_update_source_inputs(fixture, region, copy, variable, declared)
    )
    return findings


UPDATE_SOURCE_PLACING_COMMANDS = frozenset(
    {"tar", "rsync", "unzip", "cpio", "patch", "scp", "curl", "wget", "bsdtar"}
)
UPDATE_SOURCE_PLACING_SUBCOMMANDS = frozenset(
    {
        "am",
        "apply",
        "checkout",
        "cherry-pick",
        "clean",
        "clone",
        "hash-object",
        "merge",
        "mv",
        "pull",
        "reset",
        "restore",
        "revert",
        "rm",
        "stash",
        "worktree",
    }
)
UPDATE_SOURCE_EDITING_COMMANDS = frozenset(
    {
        "awk",
        "cp",
        "dd",
        "ed",
        "gawk",
        "install",
        "ln",
        "mawk",
        "mv",
        "nawk",
        "node",
        "perl",
        "python",
        "python2",
        "python3",
        "ruby",
        "sed",
        "sponge",
        "tar",
        "tee",
        "touch",
        "truncate",
        "rsync",
    }
)
STAGING_SUBCOMMANDS = frozenset({"add", "stage", "update-index"})
# An editing command that reads a program takes its first operand as that
# program rather than as a path, and a few options take a value that names no
# path either. Reading those words as paths would report an expression or a
# message as a destination the fixture writes at.
EXPRESSION_COMMANDS = frozenset(
    {"awk", "gawk", "mawk", "nawk", "node", "perl", "python", "python2", "python3", "ruby", "sed"}
)
EXPRESSION_SKIP_OPTIONS = frozenset({"-e", "--expression", "-f", "--file", "-c", "-m"})
# An option takes a value only for the commands that read one. `-r` and `-s`
# are flags for an expression command and values for a sizing command, so one
# command-independent table would consume the operand written after them and
# drop the destination this rule exists to read.
EXPRESSION_VALUE_OPTIONS = frozenset({"-e", "--expression", "-f", "--file", "-c", "-m"})
SIZE_COMMANDS = frozenset({"truncate"})
SIZE_VALUE_OPTIONS = frozenset({"-s", "--size", "-r", "--reference"})
# A copying command writes at its last operand and reads the operands before
# it, so only the last one names a destination this rule reads.
DESTINATION_LAST_COMMANDS = frozenset({"cp", "install", "rsync"})
# These commands hand the identity of their source to their destination, so a
# write through the destination is a write through the source. Both operands
# name the tree that gets written and both are read.
ALIAS_COMMANDS = frozenset({"ln", "mv"})
# These commands take the destination directory as an option value instead,
# which leaves a source written last. `rsync` spells `-t` as a timestamp flag,
# so it keeps the last-operand reading.
TARGET_OPTION_COMMANDS = frozenset({"cp", "install", "ln", "mv"})
TARGET_VALUE_OPTIONS = frozenset({"-t", "--target-directory"})
# Only these Git options name the tree a staging writes into.
GIT_REPOSITORY_OPTIONS = frozenset({"-C", "--git-dir", "--work-tree"})
# `git commit` writes the tree the update source is read from, so the forms
# that stage on their own are read here exactly as a staging is.
COMMIT_STAGING_OPTIONS = frozenset({"--all", "--include", "--only"})
COMMIT_STAGING_LETTERS = "aio"
COMMIT_VALUE_OPTIONS = frozenset(
    {
        "--author",
        "--cleanup",
        "--date",
        "--file",
        "--fixup",
        "--gpg-sign",
        "--message",
        "--pathspec-from-file",
        "--reedit-message",
        "--reuse-message",
        "--squash",
        "--template",
        "--trailer",
        "--untracked-files",
    }
)
COMMIT_VALUE_LETTERS = "CFcmt"
COMMIT_PLAIN_OPTIONS = frozenset(
    {
        "--allow-empty",
        "--allow-empty-message",
        "--amend",
        "--branch",
        "--dry-run",
        "--edit",
        "--long",
        "--no-edit",
        "--no-gpg-sign",
        "--no-post-rewrite",
        "--no-signoff",
        "--no-status",
        "--no-verify",
        "--porcelain",
        "--quiet",
        "--reset-author",
        "--short",
        "--signoff",
        "--status",
        "--verbose",
    }
)
COMMIT_PLAIN_LETTERS = "envqs"
UPDATE_SOURCE_SHELLS = frozenset({"sh", "bash", "dash", "ksh", "zsh", "eval"})
FOR_LIST_PATTERN = re.compile(r"(?m)^[ \t]*for[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+in[ \t]+([^\n;]*)")
PARAMETER_POSITION_PATTERN = re.compile(r"(?<![A-Za-z0-9_])\$\{?([1-9][0-9]*)\}?")


def _mentions_name(text: str, names: frozenset[str]) -> bool:
    """Report whether one written word reads one of the named variables.

    The read is taken from the written bytes rather than from the expansions
    this checker resolves, because a name written inside a command
    substitution or inside a quoted script still carries the value the
    surrounding fixture gives it.
    """

    return any(
        re.search(
            r"(?<![A-Za-z0-9_])\$\{?" + re.escape(name) + r"(?![A-Za-z0-9_])", text
        )
        for name in names
    )


def _update_source_roots(
    fixture: _Fixture, copy: _Operation, variable: str
) -> frozenset[_Path]:
    """Return every directory the inventory copy writes the declared files under.

    The update source is read from the destination the inventory copy writes
    rather than from a name this checker fixes, because the fixture decides
    what it calls that directory. The loop variable is left out, because it
    holds the path one inventory line declares rather than the directory that
    holds them all.
    """

    destination = _operation_words(copy)[-1].text
    roots: set[_Path] = set()
    for name in sorted(_read_names(destination)):
        if name == variable:
            continue
        roots |= _settle_written_word(fixture, copy, f'"${name}"')
    return frozenset(roots)


def _is_one_path(left: _Path, right: _Path) -> bool:
    """Report whether two settled paths may name one file or directory."""

    return len(left[1]) == len(right[1]) and _may_be_one_directory(left, right)


def _lies_under(path: _Path, roots: frozenset[_Path]) -> bool:
    """Report whether one settled path may lie under one of the roots."""

    return any(
        len(path[1]) > len(root[1])
        and _may_be_one_directory((path[0], path[1][: len(root[1])]), root)
        for root in roots
    )


def _names_one_root(path: _Path, roots: frozenset[_Path]) -> bool:
    """Report whether one settled path names one of the roots itself.

    A path no written text anchors at the root names a directory the shell
    decides, so it is not read as naming the update source: an operand written
    as a relative path is the path one repository holds rather than the
    repository itself.
    """

    return path[0] and any(_is_one_path(path, root) for root in roots)


def _operation_paths(fixture: _Fixture, operation: _Operation) -> frozenset[_Path]:
    """Return every path the words of one operation settle to."""

    settled: set[_Path] = set()
    for token in _operation_words(operation):
        settled |= _settle_written_word(fixture, operation, token.text)
    return frozenset(settled)


def _edited_operands(
    command: str, words: Sequence[Token]
) -> tuple[Token, ...]:
    """Return the words one editing command takes as the paths it writes.

    An editing command that reads a program takes that program as its first
    operand, and several options take a value that names no path, so neither is
    read as a destination. A copying command writes at its last operand alone,
    and an interpreter hands every operand to the script it runs, whose options
    this checker does not know, so neither is read here: an interpreter run is
    read by the interpreter rules instead. Everything else the command is
    written with is read as a path it may write at.

    A word this reading cannot resolve to one option may spell the option that
    carries the destination, so the last operand is no longer proven to be the
    destination and every operand is returned instead.
    """

    if _is_interpreter(command):
        return ()
    expression = command in EXPRESSION_COMMANDS
    values = set()
    if expression:
        values |= EXPRESSION_VALUE_OPTIONS
    if command in SIZE_COMMANDS:
        values |= SIZE_VALUE_OPTIONS
    targeted = command in TARGET_OPTION_COMMANDS
    operands: list[Token] = []
    targets: list[Token] = []
    skipped = expression
    ended = False
    unreadable = False
    index = 1
    while index < len(words):
        text = _written_option(words[index].text)
        if text is None and not ended and _spells_a_dash_word(words[index].text):
            unreadable = True
        if text is not None and not ended and text == "--":
            ended = True
            index += 1
            continue
        if text is not None and not ended and text != "-":
            option, separator, _ = text.partition("=")
            if targeted and option in TARGET_VALUE_OPTIONS:
                if separator:
                    targets.append(words[index])
                    index += 1
                elif index + 1 < len(words):
                    targets.append(words[index + 1])
                    index += 2
                else:
                    index += 1
                continue
            if option in EXPRESSION_SKIP_OPTIONS:
                skipped = False
            if option in values and not separator:
                index += 2
                continue
            index += 1
            continue
        if skipped:
            skipped = False
            index += 1
            continue
        operands.append(words[index])
        index += 1
    if targets and not unreadable:
        return tuple(targets)
    if command in DESTINATION_LAST_COMMANDS and not unreadable:
        return tuple(operands[-1:])
    return tuple(targets) + tuple(operands)


def _written_option(word: str) -> str | None:
    """Return the option one written word spells, or None when it spells none.

    Quoting a character changes nothing about the option a command receives, so
    the quote and escape characters are removed before the word is read: `-t`,
    `"-t"`, `'-t'`, `-"t"`, and `\\-t` all hand the same option over. Reading the
    written bytes instead let a quoted option fall through to the operand list,
    which dropped the destination every operand rule exists to read. Only the
    name half is read, because the value half may carry an expansion this
    reading does not resolve; a word whose name half carries one spells
    whatever it expands to, so it is left for the operand reading, where a word
    this checker cannot place is reported.
    """

    name, separator, value = word.partition("=")
    if "$" in name or "`" in name:
        return None
    bare = name.replace('"', "").replace("'", "").replace("\\", "")
    if not bare.startswith("-"):
        return None
    return bare + separator + value


def _spells_a_dash_word(word: str) -> bool:
    """Report whether one written word may reach its command as an option.

    A word this reading cannot name may still spell an option, because an
    expansion anywhere in it carries whatever it holds: `"-t$e"`, `"${e}-t"`
    and `"$opt"` all reach the command as the same option. Reading only a
    literal leading dash missed the last two, so an expansion also leaves the
    word unproven, and the reading that follows it must not treat the operands
    around it as proven.

    A word that carries a written path separator is read as a path even when it
    carries an expansion, because `"$root/pyproject.toml"` is how this fixture
    writes the sources of an ordinary copy. Without that reading every such
    copy would be reported for a source this checker cannot place.
    """

    bare = word.replace('"', "").replace("'", "").replace("\\", "")
    if bare.startswith("-"):
        return True
    return "$" in word and "/" not in bare


def _repository_operands(words: Sequence[Token]) -> tuple[str, ...]:
    """Return the words one Git run names its repository with.

    A staging written against a repository this checker cannot place stages
    into a tree it cannot follow, so the repository words are read as paths
    exactly as the staged operands are. Only the words written before the
    subcommand name a repository; the words after it are read elsewhere. An
    option that carries the repository is read at its value, because dropping
    every word written with a leading dash lets one option name the tree
    without any word this rule reads.
    """

    operands: list[str] = []
    index = 1
    while index < len(words):
        token = words[index]
        option = _written_option(token.text)
        if option is None:
            if _strip(token.text) in STAGING_SUBCOMMANDS or _strip(token.text) == "commit":
                break
            operands.append(token.text)
            index += 1
            continue
        name, separator, value = option.partition("=")
        if name in GIT_REPOSITORY_OPTIONS:
            if separator:
                operands.append(value)
                index += 1
            elif index + 1 < len(words):
                operands.append(words[index + 1].text)
                index += 2
            else:
                index += 1
            continue
        if name in GIT_VALUE_OPTIONS and not separator:
            index += 2
            continue
        index += 1
    return tuple(operands)


def _reads_an_unplaceable_path(
    fixture: _Fixture, operation: _Operation, words: Sequence[Token]
) -> bool:
    """Report whether one operation takes a destination this checker cannot place.

    A word written with an expansion names a path at run time whether or not
    this checker can compute it. Reading such a word as naming nothing is what
    every evasion of this rule was built from: a positional parameter, a loop
    variable, a name a `read` writes, and a parameter expansion with an
    operator all settle to nothing, and each would otherwise carry an edit or a
    staging past every rule below. A word this checker cannot place is
    therefore reported as an unproven destination rather than accepted as a
    harmless one. Only the words the command takes as the paths it writes are
    read here, so an expression, a message, a copy source, and an operand an
    interpreter hands to its script are not reported as destinations. The
    callers pick those words, so a word written with a leading dash is read
    here exactly as any other: an option that carries a path names one.
    """

    return _reads_an_unplaceable_text(
        fixture, operation, tuple(token.text for token in words)
    )


def _reads_an_unplaceable_text(
    fixture: _Fixture, operation: _Operation, texts: Sequence[str]
) -> bool:
    """Report whether one operation is written with a path it cannot place."""

    for text in texts:
        if "$" not in text:
            continue
        if not _settle_written_word(fixture, operation, text):
            return True
    return False


def _names_the_update_source(
    fixture: _Fixture,
    operation: _Operation,
    words: Sequence[Token],
    roots: frozenset[_Path],
) -> bool:
    """Report whether one operation names the update source at any operand.

    A command that renames or links hands the identity of its source to its
    destination, so a write through the destination writes the source tree.
    Reading only the destination let one link give the update source a second
    name that no later rule recognises, which took every rule below out of
    play at once.
    """

    for token in words:
        for path in _settle_written_word(fixture, operation, token.text):
            if path in roots or _lies_under(path, roots):
                return True
    return False


def _names_a_relative_repository(
    fixture: _Fixture, operation: _Operation, texts: Sequence[str]
) -> bool:
    """Report whether a staging names its tree from the directory it stands in.

    A relative repository is the directory the run happens to stand in, which
    this checker does not follow, so it proves no more about the tree it writes
    into than a staging that names no repository at all. Reading only the
    absent form let the same relay be written as `-C .`. A word that settles to
    nothing names the directory it stands in as well, because a current or a
    parent segment is exactly what settles to no path.
    """

    for text in texts:
        settled = _settle_written_word(fixture, operation, text)
        if not settled or any(not absolute for absolute, _ in settled):
            return True
    return False


def _staged_operands(
    fixture: _Fixture, operation: _Operation
) -> tuple[tuple[Token, ...], bool]:
    """Return the paths one staging names and whether it stages what it finds.

    A staging written with no path of its own, or written to add everything a
    tree holds, names no file this checker can compare against the inventory,
    so it is reported instead of read.
    """

    operands: list[Token] = []
    everything = False
    started = False
    for token in _operation_words(operation):
        if not started:
            started = token.text in STAGING_SUBCOMMANDS
            continue
        if token.text == "--":
            continue
        if token.text.startswith("-"):
            if token.text in {"-A", "--all", "--no-ignore-removal", "-u", "--update"}:
                everything = True
            continue
        if _strip(token.text) in {".", ":/", "*", ":/*"}:
            everything = True
            continue
        operands.append(token)
    return tuple(operands), everything or not operands


def _committed_operands(words: Sequence[Token]) -> tuple[tuple[Token, ...], bool]:
    """Return the paths one commit stages and whether it stages what it finds.

    A commit written with no path and no staging option stages nothing of its
    own, so it names no operand here and the caller reads it as no staging at
    all. An option this reader does not know may carry a path or consume the
    word after it, so such a commit is read as staging what it finds rather
    than as staging a path this reader can compare against the inventory.
    """

    operands: list[Token] = []
    everything = False
    started = False
    separated = False
    skip = False
    for token in words:
        if not started:
            started = token.text == "commit"
            continue
        if skip:
            skip = False
            continue
        if separated:
            operands.append(token)
            continue
        text = token.text
        if text == "--":
            separated = True
            continue
        if not text.startswith("-") or text == "-":
            operands.append(token)
            continue
        name, _, attached = text.partition("=")
        if text.startswith("--"):
            if name in COMMIT_STAGING_OPTIONS:
                everything = True
            elif name in COMMIT_VALUE_OPTIONS:
                skip = not attached
            elif name not in COMMIT_PLAIN_OPTIONS:
                everything = True
            continue
        letters = text[1:]
        if any(letter in COMMIT_STAGING_LETTERS for letter in letters):
            everything = True
        if any(
            letter not in COMMIT_STAGING_LETTERS
            and letter not in COMMIT_VALUE_LETTERS
            and letter not in COMMIT_PLAIN_LETTERS
            for letter in letters
        ):
            everything = True
            continue
        skip = letters[-1] in COMMIT_VALUE_LETTERS
    return tuple(operands), everything


def _update_source_names(
    fixture: _Fixture, copy: _Operation, variable: str
) -> frozenset[str]:
    """Return every name a word may write the update source with.

    A destination this checker cannot place still says which names it is
    written from, so the names the inventory copy writes its destination with
    are followed through every assignment that reads one of them. A name bound
    from such a word may hold the update source whatever the value settles to,
    so an operation written with it is read as naming the update source.
    """

    destination = _operation_words(copy)[-1].text
    names = {name for name in _read_names(destination) if name != variable}
    lists = FOR_LIST_PATTERN.findall(fixture.text)
    while True:
        grown = set(names)
        held = frozenset(names)
        for assignment in fixture.assignments:
            if _mentions_name(assignment.value, held):
                grown.add(assignment.name)
            grown |= _passed_names(fixture, assignment, held)
        for name, words in lists:
            if _mentions_name(words, held):
                grown.add(name)
        if grown == names:
            return frozenset(names)
        names = grown


def _inside_substitution(fixture: _Fixture, operation: _Operation) -> bool:
    """Report whether one operation stands inside a substituted assignment value.

    A directory change written inside a command substitution ends with the
    substitution, so the operations written after it are read from the
    directory the fixture already stood in.
    """

    return any(
        assignment.token.start.offset
        <= operation.offset
        <= assignment.token.end.offset
        for assignment in fixture.assignments
    )


def _passed_names(
    fixture: _Fixture, assignment: _Assignment, names: frozenset[str]
) -> set[str]:
    """Return the assignment name when a call passes the update source to it.

    A function that binds a positional parameter carries whatever its call
    sites write there, so a name bound from `$1` holds the update source when
    one call writes the update source in that position. The word position is
    read exactly rather than tolerantly, so a helper called with the update
    source in another position binds no name here.
    """

    positions = {
        int(match.group(1))
        for match in PARAMETER_POSITION_PATTERN.finditer(assignment.value)
    }
    if not positions:
        return set()
    declared = [
        declaration
        for declaration in fixture.table.declarations
        if declaration.start.offset <= assignment.offset <= declaration.end.offset
    ]
    passed: set[str] = set()
    for declaration in declared:
        for operation in fixture.operations:
            if operation.name != declaration.name:
                continue
            words = _operation_words(operation)
            for position in positions:
                if position < len(words) and _mentions_name(
                    words[position].text, names
                ):
                    passed.add(assignment.name)
    return passed


def _may_name_update_source(
    fixture: _Fixture,
    operation: _Operation,
    roots: frozenset[_Path],
    names: frozenset[str],
) -> bool:
    """Report whether one operation may be written against the update source."""

    texts = [token.text for token in _operation_words(operation)]
    texts.extend(operation.redirect_targets)
    for text in texts:
        if _mentions_name(text, names):
            return True
        for path in _settle_written_word(fixture, operation, text):
            if not path[0]:
                continue
            if _names_one_root(path, roots) or _lies_under(path, roots):
                return True
    return False


def _is_declared(
    path: _Path, roots: frozenset[_Path], declared: frozenset[tuple[str, ...]]
) -> bool:
    """Report whether one inventory line declares one staged update source path.

    The comparison is exact. A segment written with an expansion names a file
    the written text does not fix, so no inventory line proves it, and a path
    the checker cannot read against a root proves nothing either. Both are read
    as undeclared, because the inventory is what says which paths the update
    source may carry.
    """

    for root in roots:
        if len(path[1]) <= len(root[1]):
            continue
        if not _may_be_one_directory((path[0], path[1][: len(root[1])]), root):
            continue
        relative = path[1][len(root[1]) :]
        if any(_carries_expansion(segment) for segment in relative):
            continue
        if relative in declared:
            return True
    return False


def _writes_undeclared(
    paths: Iterable[_Path],
    roots: frozenset[_Path],
    declared: frozenset[tuple[str, ...]],
) -> bool:
    """Report whether one operation edits an update source path nothing declares.

    Only a path this checker places inside the update source is read here. A
    word that settles outside the roots names a file the inventory says nothing
    about, and a word this checker cannot place is reported by the rule that
    reads an unplaceable write instead.
    """

    return any(
        path[0] and _lies_under(path, roots) and not _is_declared(path, roots, declared)
        for path in paths
    )


def _reached_git_subcommand(fixture: _Fixture, operation: _Operation) -> str | None:
    """Return the Git subcommand one operation runs, including inside a body.

    The fixture reads a Git wrapper at its call site, because the inlined body
    of such a wrapper carries `"$@"` rather than the words the run is made of.
    A body that writes the subcommand itself does carry those words, so it is
    read here as well: otherwise one helper function that names the staging
    keeps every staging rule from ever seeing it.
    """

    subcommand = fixture.git_subcommand(operation)
    if subcommand is not None or not operation.node.call_path:
        return subcommand
    if operation.name != "git" and operation.name not in fixture.git_wrappers:
        return None
    return _git_subcommand(operation)[0]


def _check_update_source_inputs(
    fixture: _Fixture,
    region: int,
    copy: _Operation,
    variable: str,
    declared: frozenset[tuple[str, ...]],
) -> list[Finding]:
    """Reject every update source input the inventory loop does not perform.

    A fixture takes an input the inventory does not declare either by writing a
    file into the update source outside the inventory region or by staging a
    path in the update source that nothing there writes. Both are read from the
    destination the operation settles to rather than from the name it is
    written with, because a hard-coded path and a further variable name one
    directory as readily as the name the loop copies with. A destination this
    checker cannot place is reported rather than read as writing nothing,
    whenever the operation is written with a name the update source is written
    with, and a command that puts a file in place without naming it, a Git
    subcommand that writes a tree, and a directory change into the update
    source are reported the same way, because each carries a file this checker
    cannot follow to the destination it takes. A staging is read against every
    path the rest of the fixture edits inside the update source and against the
    inventory, because the fixture edits a file the loop copied before staging
    it. An editing command alone never licenses a staging: the inventory says
    which paths the update source may carry, so a path no inventory line
    declares is rejected however the fixture writes it, whether the fixture
    writes the edit, the staging, or both. A staging this checker cannot read
    as a direct Git run is reported rather than skipped, and a staging written
    inside the body of a called function is read there, because a helper that
    names the staging itself would otherwise carry it past every rule below.
    """

    findings: list[Finding] = []
    roots = _update_source_roots(fixture, copy, variable)
    if not roots:
        return [
            Finding(
                RULE_INVENTORY_REGION,
                "the inventory copy names no update source this checker can place",
                copy.position,
            )
        ]
    names = _update_source_names(fixture, copy, variable)
    edited: dict[int, frozenset[_Path]] = {}
    for operation in fixture.operations:
        if not operation.reachable:
            continue
        if _resolved_command(_operation_words(operation)) in UPDATE_SOURCE_EDITING_COMMANDS:
            edited[operation.offset] = _operation_paths(fixture, operation)
    for operation in fixture.operations:
        if not operation.reachable or region in operation.loop_regions:
            continue
        named = _may_name_update_source(fixture, operation, roots, names)
        created, inside, _words, unknown = _helper_paths(fixture, operation)
        written = set(created) | {
            (directory[0], directory[1] + (name,)) for directory, name in inside
        }
        command = _resolved_command(_operation_words(operation))
        subcommand = fixture.git_subcommand(operation)
        if any(_lies_under(path, roots) for path in written):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                    operation.position,
                )
            )
        elif named and unknown:
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "a write this checker cannot place is written where the "
                    "update source is named",
                    operation.position,
                )
            )
        if named and (
            command in UPDATE_SOURCE_PLACING_COMMANDS
            or subcommand in UPDATE_SOURCE_PLACING_SUBCOMMANDS
        ):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "a command that puts files in place is written where the "
                    "update source is named",
                    operation.position,
                )
            )
        if command in UPDATE_SOURCE_EDITING_COMMANDS and _writes_undeclared(
            edited.get(operation.offset, frozenset()), roots, declared
        ):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "an edit outside the inventory region writes a path no "
                    "inventory line declares",
                    operation.position,
                )
            )
        if command in ALIAS_COMMANDS and _names_the_update_source(
            fixture,
            operation,
            _edited_operands(command, _operation_words(operation)),
            roots,
        ):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "an alias of the update source stands outside the "
                    "inventory region",
                    operation.position,
                )
            )
        if command in UPDATE_SOURCE_EDITING_COMMANDS and _reads_an_unplaceable_path(
            fixture, operation, _edited_operands(command, _operation_words(operation))
        ):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "an edit outside the inventory region takes a destination "
                    "this checker cannot place",
                    operation.position,
                )
            )
        if named and command == "cd" and not _inside_substitution(fixture, operation):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "a directory change into the update source stands outside "
                    "the inventory region",
                    operation.position,
                )
            )
        if (
            named
            and subcommand is None
            and not operation.node.call_path
            and operation.name != "git"
            and operation.name not in fixture.git_wrappers
            and (
                command in UPDATE_SOURCE_SHELLS
                or any(
                    _strip(token.text) == "git"
                    or _strip(token.text) in fixture.git_wrappers
                    for token in _operation_words(operation)
                )
            )
        ):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "a Git run this checker cannot read is written where the "
                    "update source is named",
                    operation.position,
                )
            )
        staging = _reached_git_subcommand(fixture, operation)
        if staging == "commit":
            operands, everything = _committed_operands(_operation_words(operation))
            if not operands and not everything:
                # A commit that stages nothing of its own records only what a
                # staging this rule already read put in the index.
                continue
        elif staging in STAGING_SUBCOMMANDS:
            operands, everything = _staged_operands(fixture, operation)
        else:
            continue
        repository = _repository_operands(_operation_words(operation))
        if _reads_an_unplaceable_text(
            fixture, operation, repository
        ) or _reads_an_unplaceable_path(fixture, operation, operands):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region names a repository or "
                    "a path this checker cannot place",
                    operation.position,
                )
            )
        if not repository or _names_a_relative_repository(
            fixture, operation, repository
        ):
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region names no repository "
                    "outside the directory it stands in",
                    operation.position,
                )
            )
        if not named:
            continue
        if everything:
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region adds the update "
                    "source without naming one path",
                    operation.position,
                )
            )
        for token in operands:
            settled = _settle_written_word(fixture, operation, token.text)
            staged: set[_Path] = set()
            for anchored, segments in settled:
                if anchored and _lies_under((anchored, segments), roots):
                    staged.add((anchored, segments))
                    continue
                staged |= {(root[0], root[1] + segments) for root in roots}
            if not staged:
                findings.append(
                    Finding(
                        RULE_INVENTORY_REGION,
                        "staging outside the inventory region adds a path this "
                        "checker cannot place in the update source",
                        operation.position,
                    )
                )
                continue
            if any(
                offset != operation.offset
                and path[0]
                and _lies_under(path, roots)
                and any(_is_one_path(path, entry) for entry in staged)
                for offset, paths in edited.items()
                for path in paths
            ):
                if all(_is_declared(entry, roots, declared) for entry in staged):
                    continue
                findings.append(
                    Finding(
                        RULE_INVENTORY_REGION,
                        "staging outside the inventory region adds a path no "
                        "inventory line declares",
                        operation.position,
                    )
                )
                continue
            findings.append(
                Finding(
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region adds a path nothing "
                    "writes into the update source",
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


def _check_command_shadowing(fixture: _Fixture) -> list[Finding]:
    """Reject a fixture that gives an observed command name another meaning.

    Every other rule reads what one operation is written as. A rebinding of the
    command name leaves that written text exactly as committed while the
    command it names stops being the command the observation depends on, so the
    assertion still reads as present and proves nothing. The defect class is
    the rebinding itself, not one spelling of it, so every name a bound
    observation runs is rejected rather than only the names one known mutation
    happens to take.

    Five ways to rebind a name are reachable in the shells this fixture may
    run under: a function declaration, an alias, a helper file a `PATH` lookup
    finds first, a search path written for one command rather than for the
    shell, and a `hash -p` entry that wins over any lookup. The alias is
    already rejected by the checked execution graph, whose parse-time
    expansion has no bounded graph, and a duplicate or nested declaration is
    already rejected by the checked function table; this rule never restates
    them. The remaining four are rejected here.

    One boundary is explicit. A directory the fixture puts on the search path
    without writing its contents, and the search path its caller already holds,
    are outside the supplied bytes, so a command installed there is not
    something this checker proves anything about.
    """

    findings: list[Finding] = []
    for declaration in fixture.table.declarations:
        if declaration.name not in OBSERVED_COMMANDS:
            continue
        findings.append(
            Finding(
                RULE_COMMAND_SHADOWING,
                f"the fixture declares `{declaration.name}` as a function, "
                "which makes every bound observation that runs it vacuous",
                declaration.start,
            )
        )
    findings.extend(_hashed_lookups(fixture))
    findings.extend(_prefixed_lookups(fixture))
    findings.extend(_shadowing_helpers(fixture))
    return findings


def _sourced_operands(fixture: _Fixture) -> tuple[tuple[Position | None, Token | None], ...]:
    """Return the position and the operand of every source one file writes.

    The sources are read from the checked graph rather than from the written
    runs, because a word a `case` arm writes as a pattern is not a command
    word at all, and reading one as a source would call a pattern a file the
    shell includes. A body the graph resolves no call for is read as well,
    because the file such a body includes is included into the whole shell.
    A source that writes no operand is reported with none, because the file it
    includes is then decided by text this checker never sees.
    """

    nodes: list[tuple[Node, Position | None]] = [
        (node, node.position) for node in fixture.graph.included_sources
    ]
    for declaration in _deferred_bodies(fixture):
        nodes.extend(
            (operation.node, operation.position)
            for operation in _deferred_operations(fixture, declaration) or ()
            if operation.effect == EFFECT_SOURCE
        )
    written: list[tuple[Position | None, Token | None]] = []
    reported: set[int | None] = set()
    for node, position in nodes:
        offset = None if position is None else position.offset
        if offset in reported:
            # The same statement is read once as a modelled command and once
            # as a deferred one, and it includes the one file either way.
            continue
        reported.add(offset)
        literals = _word_literals(node.words)
        place = next(
            (
                index
                for index in _command_word_places(literals)
                if literals[index] is not None
                and _basename(literals[index]) in PATH_OPERAND_COMMANDS
            ),
            0,
        )
        operand = node.words[place + 1] if place + 1 < len(node.words) else None
        written.append((position, operand))
    return tuple(written)


def _anchored_on_the_invocation(fixture: _Fixture, name: str) -> bool:
    """Report whether one name holds the root the sourcing script was invoked from.

    A library is read only when the directory it is written under is decided
    outside the sourcing bytes. The name must therefore carry exactly one
    written value, that value must be one of the bound anchor spellings, and
    no binding this checker cannot read may reach the name.

    The value is bound rather than described. A value that only mentions a
    positional parameter still expands wherever the rest of its text says, so
    a fixture could write `$(cd -- "$tmp" ... || printf '%s' "$0")`, fill that
    directory itself, and be checked against the committed bytes instead of
    the bytes the shell runs. Reading the value as written closes that, at the
    cost that a new anchor spelling has to be bound above before it is read.
    """

    if name in fixture.unsettled_names():
        return False
    values = [
        assignment.value
        for assignment in fixture.assignments
        if assignment.name == name
    ]
    if len(values) != 1:
        return False
    return _strip(values[0]) in LIBRARY_ANCHOR_VALUES


def _bound_library(
    fixture: _Fixture, operand: Token | None, libraries: Mapping[str, str]
) -> str | None:
    """Return the bound library one source operand names, or nothing for any other.

    The operand is read as written rather than as it expands, because the
    value an expansion carries is decided outside these bytes. Only one
    spelling names a bound library: the bound anchor, then the bound path.
    Every other operand names a file nothing supplied, including a path
    written relative to a working directory this checker does not settle and a
    path written under an anchor the fixture could fill itself.
    """

    if operand is None:
        return None
    matched = LIBRARY_ANCHOR_PATTERN.fullmatch(_strip(operand.text))
    if matched is None:
        return None
    path = matched.group(1)
    if path not in libraries:
        return None
    if not _anchored_on_the_invocation(fixture, LIBRARY_ANCHOR_NAME):
        return None
    return path


def _project_library(text: str) -> tuple[_Fixture | None, Finding | None]:
    """Return one sourced library read through the checked projections.

    A library those projections reject says nothing about which of its words
    are written, so it is reported as a structure finding instead of being
    read partially, exactly as a rejected fixture is.
    """

    try:
        records = shell_lexical.project(text)
        table = shell_functions.derive(records)
        graph = shell_execution.derive(records, table)
    except (ShellLexicalError, ShellFunctionError, ShellExecutionError) as error:
        return None, Finding(
            RULE_STRUCTURE,
            f"the checked projections rejected the sourced bytes: {error}",
            error.position,
        )
    return _Fixture(text, records, table, graph), None


def _library_finding(path: str, finding: Finding) -> Finding:
    """Return one finding of a sourced library, placed in that library.

    The position of such a finding counts in the library rather than in the
    file that sources it, so it is written into the message instead of being
    reported as a position of the supplied bytes. The subject of the message
    is rewritten for the same reason: the rule that produced it reads one file
    at a time, and the file it read here is the library.
    """

    place = (
        ""
        if finding.position is None
        else f" line {finding.position.line} column {finding.position.column}"
    )
    subject = "the fixture "
    message = finding.message
    if message.startswith(subject):
        message = "it " + message[len(subject) :]
    return Finding(
        finding.rule,
        f"the sourced library `{path}`{place}: {message}",
        None,
    )


def _queries_rather_than_runs(literals: tuple[str | None, ...], place: int) -> bool:
    """Report whether one command word is only asked about rather than run.

    A launcher asked for a name reports where that name would be found and
    runs nothing, so `command -v copier` names Copier without performing any
    Copier operation. The option letters written before the command word are
    the text that says so, and a word this checker cannot read is passed over.
    """

    for written in literals[:place]:
        if written is None or written == OPTION_END:
            continue
        if not written.startswith(OPTION_MARK):
            continue
        if set(written[1:]) & COPIER_QUERY_OPTIONS:
            return True
    return False


def _declaration_named(
    library: _Fixture, name: str
) -> shell_functions.FunctionDeclaration | None:
    """Return the declaration one library makes under a written name."""

    for declaration in library.table.declarations:
        if declaration.name == name:
            return declaration
    return None


def _copier_words(
    library: _Fixture,
    declaration: shell_functions.FunctionDeclaration,
    seen: frozenset[str] = frozenset(),
) -> tuple[bool, bool] | None:
    """Return whether one declared body names Copier, and whether it runs it.

    Every command word the body writes is read, including the word a launcher
    reaches, because a wrapper written as `command -v copier` names Copier at
    the word its launcher runs. The written text is read rather than the text
    this checker settles, so a Copier binary held in a name still counts. A
    body the checked projections do not accept on its own says nothing about
    the words it writes, so nothing is returned for it and it proves neither
    reading.

    A word that names another declaration the same library makes is read
    through that declaration instead of counted for itself, because the shell
    runs its body rather than any Copier command. A wrapper written as a call
    to the availability predicate would otherwise pass on the name alone while
    asking where Copier is and running nothing. Each name is entered once, so
    a body that reaches itself again runs no further Copier command.
    """

    if declaration.name in seen:
        return False, False
    entered = seen | {declaration.name}
    operations = _deferred_operations(library, declaration)
    if operations is None:
        return None
    named = False
    dispatched = False
    for operation in operations:
        words = _operation_words(operation)
        if not words:
            continue
        literals = _word_literals(words)
        for place in _command_word_places(literals):
            if place >= len(words):
                continue
            written = words[place].text
            if not _mentions(written, COPIER_MARKER):
                continue
            queried = _queries_rather_than_runs(literals, place)
            inner = _declaration_named(library, _strip(written))
            if inner is not None:
                reached = _copier_words(library, inner, entered)
                if reached is None:
                    continue
                named = named or reached[0]
                dispatched = dispatched or (reached[1] and not queried)
                continue
            named = True
            if not queried:
                dispatched = True
    return named, dispatched


def _carries_a_copier_operation(fixture: _Fixture, name: str) -> bool:
    """Report whether the sourcing file runs one name as a Copier operation.

    This checker reads a command word that mentions Copier, followed by a
    Copier subcommand, as the Copier operation it performs. A name the fixture
    writes that way carries a bound observation, so the body behind it has to
    run Copier rather than only ask where Copier is. A name written any other
    way, such as the predicate the fixture tests before it starts, carries no
    such observation.
    """

    for run in fixture.command_runs():
        literals = _word_literals(run.words)
        for place in _command_word_places(literals):
            if place >= len(run.words):
                continue
            if _strip(run.words[place].text) != name:
                continue
            for written in literals[place + 1 :]:
                if written == UPDATE_SUBCOMMAND or written in COPY_SUBCOMMANDS:
                    return True
    return False


def _check_library_wrapper(
    fixture: _Fixture, path: str, library: _Fixture
) -> list[Finding]:
    """Reject a Copier wrapper a sourced library declares without running Copier.

    This checker reads a command word that mentions Copier as the Copier
    operation it performs, so a wrapper of such a name carries every bound
    Copier observation the file that sources it writes. A body that runs no
    Copier command leaves each of those observations written exactly as
    committed while no Copier run happens at all, which is the same vacuity a
    redefinition creates and is rejected the same way.

    A wrapper the fixture runs as a Copier operation must dispatch Copier, not
    merely name it: a body reduced to `command -v copier` reports where Copier
    is and performs nothing, so every operation written through it is vacuous.
    A Copier name the fixture never runs as an operation is the predicate it
    tests before starting, for which asking is the whole point, so naming
    Copier is enough there.
    """

    findings: list[Finding] = []
    for declaration in library.table.declarations:
        if not _mentions(declaration.name, COPIER_MARKER):
            continue
        reached = _copier_words(library, declaration)
        named, dispatched = reached if reached is not None else (False, False)
        if _carries_a_copier_operation(fixture, declaration.name):
            if dispatched:
                continue
            lack = "a body that runs no Copier command"
        else:
            if named:
                continue
            lack = "a body that names no Copier command"
        findings.append(
            _library_finding(
                path,
                Finding(
                    RULE_COMMAND_SHADOWING,
                    f"it declares the Copier wrapper `{declaration.name}` with "
                    f"{lack}, which makes every bound Copier observation "
                    "vacuous",
                    declaration.start,
                ),
            )
        )
    return findings


def _check_sourced_libraries(
    fixture: _Fixture, libraries: Mapping[str, str]
) -> list[Finding]:
    """Reject a rebinding written in, or hidden behind, a sourced file.

    A sourced file is run by the shell that sources it, so every rule that
    reads the sourcing text alone stays satisfied while a declaration written
    in the sourced file decides what each bound observation runs. The bound
    libraries are therefore read through the same shadowing rule as the file
    that sources them.

    Two further rebindings cross the source boundary. A declaration the
    sourcing file repeats is a redefinition: the later declaration is the one
    the shell holds, so the observation the sourced one carried is vacuous.
    And the Copier wrapper is an observed name, because this checker reads a
    command word that mentions Copier as the Copier operation it performs, so
    a fixture that declares such a name gives every bound Copier observation
    another meaning while keeping its own text. The wrapper belongs in a bound
    library, and the one declared there must run a Copier command rather than
    carry the observations on its name alone.

    One boundary is explicit. Only a bound library is read, and a source that
    names any other path is rejected, because bytes nothing supplied prove
    nothing about the names the shell holds after that line.
    """

    findings: list[Finding] = []
    read: dict[str, _Fixture] = {}
    pending: list[tuple[str | None, _Fixture]] = [(None, fixture)]
    while pending:
        origin, current = pending.pop(0)
        for position, operand in _sourced_operands(current):
            path = _bound_library(current, operand, libraries)
            if path is None:
                unread = Finding(
                    RULE_COMMAND_SHADOWING,
                    "the fixture sources a path this checker was not given, "
                    "so a redefinition written there is never read",
                    position,
                )
                findings.append(
                    unread if origin is None else _library_finding(origin, unread)
                )
                continue
            if path in read:
                continue
            library, rejected = _project_library(libraries[path])
            if library is None:
                findings.append(_library_finding(path, rejected))
                continue
            read[path] = library
            findings.extend(
                _library_finding(path, finding)
                for finding in _check_command_shadowing(library)
            )
            findings.extend(_check_library_wrapper(fixture, path, library))
            pending.append((path, library))
    declared: dict[str, str] = {}
    for path, library in read.items():
        for declaration in library.table.declarations:
            earlier = declared.setdefault(declaration.name, path)
            if earlier == path:
                continue
            findings.append(
                _library_finding(
                    path,
                    Finding(
                        RULE_COMMAND_SHADOWING,
                        f"it declares `{declaration.name}`, which the sourced "
                        f"library `{earlier}` declares as well, so the "
                        "declaration every bound observation runs is replaced",
                        declaration.start,
                    ),
                )
            )
    for declaration in fixture.table.declarations:
        name = declaration.name
        if _mentions(name, COPIER_MARKER):
            findings.append(
                Finding(
                    RULE_COMMAND_SHADOWING,
                    f"the fixture declares the Copier wrapper `{name}`, "
                    "which makes every bound Copier observation vacuous",
                    declaration.start,
                )
            )
            continue
        earlier = declared.get(name)
        if earlier is None:
            continue
        findings.append(
            Finding(
                RULE_COMMAND_SHADOWING,
                f"the fixture declares `{name}`, which the sourced library "
                f"`{earlier}` declares as well, so the declaration every "
                "bound observation runs is replaced",
                declaration.start,
            )
        )
    return findings


def _operation_words(operation: _Operation) -> tuple[Token, ...]:
    """Return the words the checked graph records for one operation.

    A command written inside an expansion is placed against no written run,
    so reading its operands from a run would read a command that writes files
    and a command that writes nothing exactly alike. The checked graph records
    the words of both, so every operand reading is taken from there.
    """

    return operation.node.words


def _hashed_lookups(fixture: _Fixture) -> list[Finding]:
    """Reject a `hash` entry that binds a command name to a written path.

    `hash -p path name` is consulted before `PATH`, so it rebinds a name
    without declaring anything and without writing a file the search path
    reaches. Every word is read rather than the resolved command name alone,
    because a launcher such as `command` or `builtin` carries the same entry,
    and the words that follow are read as written rather than as the options
    this checker can settle, because a word it cannot read may be that option.
    A body reached only by a call the graph cannot resolve is read as well,
    because the entry it writes rebinds the name for the whole shell.
    """

    findings: list[Finding] = []
    deferred: list[tuple[_Operation, Position | None]] = []
    for declaration in _deferred_bodies(fixture):
        deferred.extend(
            (operation, declaration.name_token.start)
            for operation in _deferred_operations(fixture, declaration) or ()
        )
    reachable = [
        (operation, operation.position)
        for operation in fixture.operations
        if operation.reachable
    ]
    reported: set[int | None] = set()
    for operation, position in reachable + deferred:
        written = None if operation.position is None else operation.position.offset
        if written in reported:
            # The same statement is read once as a modelled command and once
            # as a deferred one, and it binds the one name either way.
            continue
        literals = _word_literals(_operation_words(operation))
        index = _command_index(literals, frozenset({COMMAND_HASH}))
        if index < 0:
            continue
        if not any(
            option is None
            or (
                option.startswith(OPTION_MARK)
                and option != OPTION_MARK
                and HASH_PATH_OPTION in option[1:]
            )
            for option in literals[index + 1 :]
        ):
            continue
        reported.add(written)
        findings.append(
            Finding(
                RULE_COMMAND_SHADOWING,
                "the fixture binds a command name through `hash`, which is "
                "read before the command a bound observation runs",
                position,
            )
        )
    return findings


def _prefixed_lookups(fixture: _Fixture) -> list[Finding]:
    """Reject a search path written for one command rather than for the shell.

    A value written in front of one command, and a value `env` carries, decide
    what that command resolves to, so a search path written there settles what
    the observation runs from text this checker never sees. Every word of the
    run is read, because a launcher and a declared wrapper both forward to the
    command the observation depends on while the word written first is neither.
    The admission therefore requires proof that the run reaches no observed
    command: a word this checker cannot read, and a call into a function whose
    body this checker would have to follow, are both refused.
    """

    findings: list[Finding] = []
    for run in fixture.command_runs() + _nested_runs(fixture):
        if not run.words:
            continue
        if not _writes_a_search_path(fixture, run):
            continue
        named = _reached_by_lookup(
            fixture,
            _run_literals(run),
            tuple(word.text for word in run.words),
        )
        if named is None:
            continue
        findings.append(
            Finding(
                RULE_COMMAND_SHADOWING,
                f"the fixture writes a search path in front of {named}, "
                "which decides what a bound observation runs",
                run.words[0].start,
            )
        )
    return findings


def _reached_by_lookup(
    fixture: _Fixture,
    literals: tuple[str | None, ...],
    words: tuple[str, ...] = (),
) -> str | None:
    """Return how one run reaches an observed command, or nothing when it cannot.

    Every word is read, not only the command word, because a program that
    execs its own argument reaches an observed command while being written
    first itself, and no list of such programs is bounded. A word is read for
    the command names it carries as well as for the name it is, because an
    interpreter given a program text runs the commands written inside that one
    word, and a word this checker cannot resolve is read for the names its
    written text carries, because that text is still written here. A word that
    could be a program text at all is refused rather than searched, because
    the shell unquoting this checker does not perform would decide which names
    that text holds. A launcher
    may also reach a command written as an expansion, and a
    function this fixture declares runs the commands its body writes, so
    neither proves the observation is untouched. A run this checker reads
    completely, whose words carry no observed command name, reaches none.
    """

    if not literals:
        return None
    first = literals[0]
    if first is None:
        return "a command this checker cannot read"
    name = _basename(first)
    if fixture.declares(name):
        return f"the declared `{name}` wrapper"
    index = _command_index(literals, OBSERVED_COMMANDS)
    if index >= 0:
        return f"`{_basename(literals[index] or '')}`"
    for place, literal in enumerate(literals):
        source = literal
        if source is None and place < len(words):
            source = words[place]
        carried = _carried_command(source)
        if carried is not None:
            return f"`{carried}`"
        if place and source is not None and _may_carry_a_program(source):
            return "a command this checker cannot read"
    if name not in LAUNCHER_COMMANDS:
        return None
    if any(literal is None for literal in literals[1:]):
        return "a command this checker cannot read"
    if any(fixture.declares(_basename(literal)) for literal in literals[1:] if literal):
        return "a command this checker cannot read"
    return None


def _may_carry_a_program(written: str) -> bool:
    """Report whether one written word could hold a program rather than data.

    A program text is written as several words separated by blanks, and a
    shell splits such a word into commands and arguments this checker would
    have to unquote to read. That unquoting is not performed here, so a word
    written with a blank is refused instead of searched. A word written
    without a blank spells one name, which the caller reads directly.
    """

    return any(character.isspace() for character in written)


def _carried_command(literal: str | None) -> str | None:
    """Return the observed command name one written word carries, if any.

    A word given to an interpreter carries a whole program, so the observed
    names written inside it are found by reading the word as the shell would
    read a command line. This is deliberately read for every word rather than
    for the words of a listed set of interpreters, because the set of programs
    that run a program text they are given is not bounded. The escape a shell
    removes before it reads a command name is removed here as well, so a name
    written with one is read as the name it resolves to.
    """

    if literal is None:
        return None
    for piece in CARRIED_WORD_PATTERN.findall(literal):
        for name in (_basename(piece), _basename(piece.replace(ESCAPE_MARK, ""))):
            if name in OBSERVED_COMMANDS:
                return name
    return None


def _nested_runs(fixture: _Fixture) -> tuple[_CommandRun, ...]:
    """Return every command written inside an expansion the shell runs.

    The checked lexical projection reports the record sequence of each such
    region, so a command written there is read exactly as a command written at
    the top level. Without it a search path written inside an expansion would
    decide what an observation runs while this checker read the expansion as
    one opaque word.
    """

    runs: list[_CommandRun] = []
    for region in shell_lexical.executable_regions(fixture.records):
        runs.extend(
            _command_runs(shell_lexical.LexicalProjection(fixture.text, region))
        )
    return tuple(runs)


def _writes_a_search_path(fixture: _Fixture, run: _CommandRun) -> bool:
    """Report whether one run gives the search path a value for its command alone.

    A value written in front of the command is one such form. A value carried
    as an argument of the command that builds an environment is the other,
    because that command searches with the value it was given. Every other
    command reads such a word as data, so only these two forms are read here,
    and a value an exporting command carries changes the shell's own search
    path and is read where the searched directories are.
    """

    if any(name == SEARCH_PATH_NAME for _, name in run.assignment_names()):
        return True
    place = _command_index(_run_literals(run), ENVIRONMENT_COMMANDS)
    if place < 0:
        return False
    return any(
        _assignment_name(token) == SEARCH_PATH_NAME
        for token in run.words[place + 1 :]
    )


def _search_path_values(fixture: _Fixture, run: _CommandRun) -> tuple[Token, ...]:
    """Return every word that gives the search path a value the shell keeps.

    A value written in front of a command applies to that command alone and
    leaves the shell's own search path unchanged, so it is read by the
    prefix rule instead of here.
    """

    if not run.words:
        return tuple(
            token for token, name in run.assignment_names() if name == SEARCH_PATH_NAME
        )
    command = run.command_name(fixture)
    if command is None or _basename(command) not in EXPORTING_COMMANDS:
        return ()
    return tuple(
        token
        for token in run.words[1:]
        if _assignment_name(token) == SEARCH_PATH_NAME
    )


def _binds_the_search_path_unreadably(fixture: _Fixture) -> bool:
    """Report whether the fixture gives the search path a value no word carries.

    A shell also binds a name through `read`, through `unset`, through a loop
    head, and through any command this checker cannot read as one name, and
    none of them writes the value this checker settles the searched
    directories from. A fixture that binds the search path that way searches
    wherever that value points. Only a command that binds the name it is given
    is read this way, because every other command reads such a word as data,
    and only the fixture's own shell is read, because a binding written inside
    an expansion is left behind with the subshell that made it.
    """

    for run in fixture.command_runs():
        for index, token in enumerate(run.tokens[:-1]):
            if _token_text(token) != LOOP_KEYWORD:
                continue
            if _token_text(run.tokens[index + 1]) == SEARCH_PATH_NAME:
                return True
        if not run.words:
            continue
        if not _binds_a_written_name(fixture, run):
            continue
        for token in run.words[1:]:
            if _token_text(token) == SEARCH_PATH_NAME:
                return True
    return False


def _binds_a_written_name(fixture: _Fixture, run: _CommandRun) -> bool:
    """Report whether one run binds the name written as its operand.

    The command is read past every launcher, because a launcher runs the
    command written after it and binds nothing itself, and reading an
    unresolved command word as unreadable would make every launcher bind the
    name it merely carries. An option written after a launcher belongs to that
    launcher rather than to the command it runs, so it is read past as well. A
    command word this checker cannot read may be any command, so it is read as
    binding.
    """

    launched = False
    for literal in _run_literals(run):
        if literal is None:
            return True
        name = _basename(literal)
        if name in LAUNCHER_COMMANDS:
            launched = True
            continue
        if launched and literal.startswith(OPTION_MARK) and literal != OPTION_MARK:
            # The option belongs to the launcher, so the command it runs is
            # written further on and is the command that binds.
            continue
        return name in NAME_BINDING_COMMANDS or fixture.declares(name)
    return False


def _path_elements(parts: _Parts) -> tuple[_Parts, ...]:
    """Split the modelled parts of one search-path value into its elements.

    The separator is read from the modelled literal parts only, so a separator
    an expansion may carry never divides one written element into two.
    """

    elements: list[list[tuple[str, str]]] = [[]]
    for kind, text in parts:
        if kind != LITERAL_SEGMENT or SEARCH_PATH_SEPARATOR not in text:
            elements[-1].append((kind, text))
            continue
        pieces = text.split(SEARCH_PATH_SEPARATOR)
        elements[-1].append((kind, pieces[0]))
        for piece in pieces[1:]:
            elements.append([(kind, piece)])
    # An empty literal piece is the separator itself rather than written text.
    # An element left with no part at all is the working directory, which no
    # written text names, so it stays empty and is reported by the caller.
    return tuple(
        tuple(part for part in element if part != (LITERAL_SEGMENT, ""))
        for element in elements
    )


def _searched_directories(fixture: _Fixture) -> tuple[frozenset[_Path], bool]:
    """Return every directory the fixture puts on the command search path.

    A helper file rebinds a command only where the shell looks for it, so the
    prohibition is anchored on the search path the fixture writes rather than
    on the name a written file happens to take. The element that names the
    search path the caller already holds is skipped: no written text says what
    it holds, and every fixture keeps it. An element this checker cannot
    settle, an element no written text anchors at the root, and a search path
    bound by something other than a written assignment all name a directory
    this checker cannot compare, so they are reported and every written helper
    is then read as reachable through the search path.
    """

    inherited: _Parts = (("name", SEARCH_PATH_NAME),)
    searched: set[_Path] = set()
    unplaced = _binds_the_search_path_unreadably(fixture)
    unsettled = fixture.unsettled_names()
    for run in fixture.command_runs():
        for token in _search_path_values(fixture, run):
            name = _assignment_name(token)
            if name is None:
                continue
            value = token.text[len(name) + 1 :]
            bindings = fixture.bindings_before(token.start.offset)
            parts = _word_parts(value, f"p{token.start.offset}")
            if parts is None:
                unplaced = True
                continue
            for element in _path_elements(parts):
                if element == inherited:
                    continue
                resolved = None if not element else _resolve_parts(
                    element, bindings, unsettled
                )
                if resolved is None:
                    unplaced = True
                    continue
                for candidate in resolved:
                    path = _settled_path(candidate)
                    if path is None or not path[0]:
                        # A relative element names the directory the shell is
                        # in, which the fixture may change between two readers.
                        unplaced = True
                    else:
                        searched.add(path)
    return frozenset(searched), unplaced


def _may_be_one_directory(left: _Path, right: _Path) -> bool:
    """Report whether two settled paths may name one directory.

    A path this checker cannot anchor at the root names a directory the
    working directory decides, so it may name any directory. Two anchored
    paths are read from what they write in common: a segment both write the
    same way names the same directory, because a name no assignment binds and
    a substitution one assignment ran hold one value at every reader, so the
    segments written alike at the start and at the end are removed from both.
    What is left is written apart, and a segment that carries an expansion may
    stand for any number of directories and for none, so the two are proved
    apart only where a segment both write entirely as text places one of them
    at a depth or under a name the other cannot take.
    """

    if not left[0] or not right[0]:
        return True
    first, second = left[1], right[1]
    while first and second and first[0] == second[0]:
        first, second = first[1:], second[1:]
    while first and second and first[-1] == second[-1]:
        first, second = first[:-1], second[:-1]
    if not first and not second:
        return True
    if not first or not second:
        # One path ends where the other still writes directories, so the two
        # name one directory only when what is written between them may stand
        # for no directory at all.
        return any(_carries_expansion(segment) for segment in first + second)
    if not _carries_expansion(first[0]) and not _carries_expansion(second[0]):
        # The two write different names at one depth below what they share.
        return False
    if not _carries_expansion(first[-1]) and not _carries_expansion(second[-1]):
        # The two write different names for the directory itself.
        return False
    return True


def _reaches_a_searched_directory(
    directory: _Path, searched: frozenset[_Path]
) -> bool:
    """Report whether one directory may be one the command search path names."""

    return any(_may_be_one_directory(directory, entry) for entry in searched)


def _written_name(word: str) -> str | None:
    """Return the name one written word ends with, read from its literal text.

    A word this checker cannot settle still says what the file it writes is
    called whenever the word ends in written text. A word that ends in an
    expansion names a file this checker cannot name at all.
    """

    parts = _word_parts(word, "n", splits=False)
    if not parts:
        return None
    kind, text = parts[-1]
    if kind != LITERAL_SEGMENT:
        return None
    return text.rsplit(PATH_SEPARATOR, 1)[-1] or None


TAKES_THE_NEXT_WORD = object()


# The name that ends one path written inside a word this checker cannot read.
# A helper takes the name its path ends with, so the text is read for those
# names rather than for every name it happens to spell.
CARRIED_PATH_PATTERN = re.compile(r"/([A-Za-z0-9_.+-]+)")


# The commands this checker reads as taking their operands as data rather than
# as a name of a file to create. A message, a pattern and a condition name no
# file the run creates, so a path written inside one of their words is not read
# as a helper. The set is written closed rather than as every observed command,
# because `sed` writes the file its script names with `w`, `git` writes the
# files a subcommand names, and `trap` takes a program text.
DATA_OPERAND_COMMANDS = frozenset(
    {
        "printf",
        "echo",
        "true",
        "false",
        ":",
        "test",
        "[",
        "cd",
        "exit",
        "kill",
        "sleep",
        "wait",
        "read",
        "grep",
        "cat",
        "rm",
        "sed",
    }
)


def _sed_regex_address(name: str) -> str:
    """Return the way `sed` writes a match to select the lines it acts on.

    `sed` reads a match written between two slashes, and reads one written
    between two of any other character when a backslash opens it. The name
    holds the character such a match closes with while the way is read.
    """
    return (
        "/(?:\\\\+\n|\\\\(?s:.)|[^\\\\/\n])*/[IM]*"
        "|\\\\(?P<" + name + ">[^\\\\\n])"
        "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=" + name + "))[^\\\\\n])*(?P=" + name + ")[IM]*"
    )


# The place an address stands in before the command it selects for, written
# as `sed` writes one: a line number, a step, the last line, or a match, one
# of them or two of them, and a negation after them. The last line is read
# with a backslash before it as well, because a fixture that writes the
# address inside a quoted word writes the backslash the quote asks for.
SED_ADDRESS = (
    "(?:[0-9]+(?:~[0-9]+)?|\\\\?\\$|" + _sed_regex_address("first") + ")"
    "(?:,(?:[0-9]+|\\\\?\\$|[+~][0-9]+|" + _sed_regex_address("second") + "))?"
    "[ \t]*!?"
)


# The place a `w` stands in as a command of its own: where a script starts,
# where the option letters before it end, where the name of an option that
# carries its script ends, after a separator, or after a quote, with an
# address before it or none and blanks around it. A blank of its own is not
# read as a place a command starts at, because `sed` separates commands with
# a separator or a newline rather than a blank, and a blank stands inside a
# match and inside a replacement as readily as between them.
SED_COMMAND_WRITE = (
    "(?:^-[A-Za-z]+|^--[A-Za-z-]+=|^|[;{}\n\"'])"
    "[ \t]*(?:" + SED_ADDRESS + ")?[ \t]*[wW]"
)


# The place a `w` stands in as the flag of a substitution: after the whole of
# a substitution written with any delimiter, and after the other flags.
SED_FLAG_WRITE = (
    "(?<![A-Za-z_])s(?P<delimiter>[^\\\\\n])"
    "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=delimiter))[^\\\\\n])*(?P=delimiter)"
    "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=delimiter))[^\\\\\n])*(?P=delimiter)"
    "[0-9gpeiImM]*[wW]"
)


# The way a command names a file to write inside its script. `sed` writes with
# `w`, as a command of its own or as the flag of a substitution, and the name
# to write follows it with or without a blank between. A script is read as
# writing exactly when it spells a `w` in one of those two places, because a
# `w` anywhere else in a script stands inside a match, a replacement, or a
# word the script only reads. Reading the place rather than the letter keeps a
# name a script writes glued to the `w`, which `sed` writes as readily as a
# name a blank follows, from being read as a word.
SED_WRITE_PATTERN = re.compile(
    "(?:" + SED_COMMAND_WRITE + ")|(?:" + SED_FLAG_WRITE + ")"
)
SCRIPT_WRITE_PATTERNS = {"sed": SED_WRITE_PATTERN}


# The place a text a script carries starts at. `sed` reads everything after an
# `a`, an `i`, or a `c` as the text that command adds to its output rather
# than as further commands, so the letter is read where a command stands, the
# same places a `w` is read from.
SED_TEXT_COMMAND = re.compile(
    "(?:^-[A-Za-z]+|^--[A-Za-z-]+=|^|[;{}\n\"'])"
    "[ \t]*(?:" + SED_ADDRESS + ")?[ \t]*[aic]"
)
SCRIPT_TEXT_COMMANDS = {"sed": SED_TEXT_COMMAND}


# The whole of a substitution or a transliteration, written with any
# delimiter. A delimiter is written with the same characters a script
# separates commands with, so the inside of such a command is read past
# rather than read as the commands it is written between.
SED_SUBSTITUTION = re.compile(
    "(?<![A-Za-z_])[sy](?P<mark>[^\\\\\n])"
    "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=mark))[^\\\\\n])*(?P=mark)"
    "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=mark))[^\\\\\n])*(?P=mark)"
    "[0-9gpeiImM]*"
)
SCRIPT_ENCLOSED_COMMANDS = {"sed": SED_SUBSTITUTION}


# The place a `w` stands in as the flag of a substitution a blank divides it
# from. `sed` reads the flags of a substitution across blanks, so a flag is
# written after the delimiter that ends the substitution with blanks before
# it, between the flags, and before the `w` that names a file to write. A
# transliteration carries no flags at all, so a `w` after one is read as
# extra characters and `sed` runs no such script.
SED_TRAILING_WRITE = re.compile(
    "[ \t]+(?:[0-9]+|[gpeiImM]|[ \t])*[wW]"
)
SCRIPT_TRAILING_WRITES = {"sed": SED_TRAILING_WRITE}


# The way a script runs a command of its own. `sed` runs one with `e`, as a
# command of its own, which runs the text after it or the line it is reading,
# and as the flag of a substitution, which runs what the substitution puts in
# its place. A run given such a script writes whatever the command it runs
# writes, which is not written in the script as a file to write, so the whole
# of every word is read for the helper names it carries, the way a word given
# to a shell is read. The letters an option is written with are read as no
# place a command stands at here, because the `e` of `-e` is the option
# rather than the command and a script glued to that option carries the text
# to run in a word of its own.
SED_COMMAND_EXECUTE = "(?:^|[;{}\n\"'])[ \t]*(?:" + SED_ADDRESS + ")?[ \t]*e"
SED_FLAG_EXECUTE = (
    "(?<![A-Za-z_])s(?P<mark_e>[^\\\\\n])"
    "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=mark_e))[^\\\\\n])*(?P=mark_e)"
    "(?:\\\\+\n|\\\\(?s:.)|(?!(?P=mark_e))[^\\\\\n])*(?P=mark_e)"
    "[0-9gpiImM]*e"
)
SED_EXECUTE_PATTERN = re.compile(
    "(?:" + SED_COMMAND_EXECUTE + ")|(?:" + SED_FLAG_EXECUTE + ")"
)
SCRIPT_EXECUTE_PATTERNS = {"sed": SED_EXECUTE_PATTERN}
SED_TRAILING_EXECUTE = re.compile(
    "[ \t]+(?:[0-9]+|[gpeiImM]|[ \t])*e"
)
SCRIPT_TRAILING_EXECUTES = {"sed": SED_TRAILING_EXECUTE}


def _script_text_end(written: str, start: int) -> int:
    """Return where the text a script carries from one place ends.

    A text runs to the end of the line it starts on, and runs on to the line
    after it when a backslash ends that line, which is how a script carries a
    text of more than one line and how it carries one written after the
    backslash the command is spelled with.

    A word written between double quotes carries every backslash the script
    reads written twice, because that is what those quotes ask for, so the
    backslashes such a word ends a line with are counted as half of what is
    written. A backslash a backslash escapes ends the text rather than
    carrying it on, so the count is read for whether it is odd.
    """

    doubled = written.startswith('"')
    place = start
    while True:
        stop = written.find("\n", place)
        if stop < 0:
            return len(written)
        slashes = 0
        while stop - 1 - slashes >= start and written[stop - 1 - slashes] == "\\":
            slashes += 1
        if doubled:
            slashes //= 2
        if slashes % 2 == 0:
            return stop
        place = stop + 1


# The option letters a word carries before the script glued to them. A script
# is written in the same word as the option that carries it, with the option
# letters written before it and with no blank between, so the letters are
# blanked out to leave the script where a script starts. The letters are
# blanked rather than cut away, so every place the script spells is read at
# the offset the word writes it at. A word of option letters that carries no
# script is left as nothing at all this way, so the `e` of `-e` is never read
# as the command `e`. The letters are read to the first one that carries a
# value and no further, because what follows that letter is the value rather
# than more options, so the `s` of a substitution glued to `-e` is left where
# it stands.
SCRIPT_OPTION_PREFIX = re.compile("^(?:--[A-Za-z-]+=|-[A-Za-z]*?[efil])")


def _script_start(written: str) -> str:
    """Return one word with the option letters before its script blanked out."""

    match = SCRIPT_OPTION_PREFIX.match(written)
    if match is None:
        return written
    return " " * match.end() + written[match.end() :]


def _script_commands(name: str | None, written: str) -> str:
    """Return one script with the text its commands carry blanked out.

    A text a script carries is written where commands are written but is read
    as none of them, so a `w` inside such a text names no file the run
    creates. Blanking the text keeps every other place in the script where it
    is, so a write written after a text is still found where it stands. The
    option letters a script is glued to are blanked the same way, so a script
    written in the word of the option that carries it is read from where the
    script starts.
    """

    pattern = SCRIPT_TEXT_COMMANDS.get(name)
    if pattern is None:
        return written
    written = _script_start(written)
    enclosed = SCRIPT_ENCLOSED_COMMANDS[name]
    letters = list(written)
    place = 0
    while True:
        match = pattern.search(written, place)
        if match is None:
            return "".join(letters)
        run = enclosed.search(written, place)
        while run is not None and run.end() <= match.start():
            # A substitution the letter stands after encloses nothing of it,
            # so the one that stands over it is looked for past that one.
            run = enclosed.search(written, run.end())
        if run is not None and run.start() < match.start() < run.end():
            # The letter stands inside a substitution rather than where a
            # command does, because a delimiter is written with the same
            # characters a script separates commands with.
            place = max(run.end(), place + 1)
            continue
        stop = _script_text_end(written, match.end())
        for index in range(match.end(), stop):
            letters[index] = " "
        place = max(stop, match.end() + 1)


# A command that supplies the operands of the command it runs from what it
# reads. The file such a run creates is named by nothing written.
WORD_SUPPLYING_COMMANDS = frozenset({"xargs"})


def _resolved_command(words: tuple[Token, ...]) -> str | None:
    """Return the name one run runs, read past what is written before it.

    A run may be written with assignments and with launchers before the
    command it runs, and neither of them is the command. Nothing is returned
    for a run whose command word this checker cannot read, because such a run
    may run anything.
    """

    for token in words:
        if _assignment_name(token) is not None:
            continue
        literal = _word_literals((token,))[0]
        if literal is None:
            return None
        name = _basename(literal)
        if name in LAUNCHER_COMMANDS:
            continue
        return name
    return None


def _script_runs(name: str | None, written: str) -> tuple[re.Match[str], ...]:
    """Return the whole of every substitution one script is written with.

    The runs are read from the start of the script and none of them stands
    inside another, because a delimiter that opens one is read to the end of
    the command it opens before the next one is looked for.
    """

    enclosed = SCRIPT_ENCLOSED_COMMANDS.get(name)
    if enclosed is None:
        return ()
    found = []
    place = 0
    while True:
        run = enclosed.search(written, place)
        if run is None:
            return tuple(found)
        found.append(run)
        place = max(run.end(), run.start() + 1)


def _script_encloses(
    name: str | None, written: str, start: int, offset: int
) -> bool:
    """Report whether one place in a script stands inside a substitution.

    A substitution is written between delimiters a script also separates
    commands with, so a place inside one is not a place a command stands at,
    however many substitutions are written before it. The place is read as
    inside only when a substitution opens before the place is read from and
    ends after the letter the command is spelled with, so a command written
    straight after a substitution, whose own delimiter stands before it, and
    the flag of the substitution the place is read from, are both left where
    they stand rather than read as inside a run.
    """

    return any(
        run.start() < start and offset < run.end()
        for run in _script_runs(name, written)
    )


def _script_trailing_writes(
    name: str | None, written: str
) -> tuple[re.Match[str], ...]:
    """Return every place a script spells a write at after a substitution.

    `sed` reads the flags of a substitution across the blanks written between
    them, and the delimiter that ends a substitution is read as no separator
    at all, so a write written that way is found from the end of the run
    rather than from a character before it.
    """

    return _script_trailing_places(name, written, SCRIPT_TRAILING_WRITES)


def _script_trailing_places(
    name: str | None,
    written: str,
    patterns: dict[str, "re.Pattern[str]"],
) -> tuple[re.Match[str], ...]:
    """Return every place a script spells one of these after a substitution."""

    pattern = patterns.get(name)
    if pattern is None:
        return ()
    found = []
    for run in _script_runs(name, written):
        if written[run.start() : run.start() + 1] != "s":
            continue
        match = pattern.match(written, run.end())
        if match is not None:
            found.append(match)
    return tuple(found)


def _script_writes(name: str | None, written: str) -> tuple[re.Match[str], ...]:
    """Return every place one script spells a write at.

    The text the script carries is read as no command at all, and a place
    inside a substitution is read as none either, so what is left is every
    place the script names a file to write from. The place is read at the
    letter the write is spelled with rather than at the character that stands
    before it, because that character is the end of the substitution the write
    follows as readily as a separator of its own.
    """

    return _script_places(
        name, written, SCRIPT_WRITE_PATTERNS, SCRIPT_TRAILING_WRITES
    )


def _script_executes(name: str | None, written: str) -> tuple[re.Match[str], ...]:
    """Return every place one script spells a command of its own at.

    A script that runs a command writes whatever that command writes, which
    the script names nowhere, so a run given such a script is read the way a
    run given a shell text is read rather than as a run whose operands are
    data.
    """

    return _script_places(
        name, written, SCRIPT_EXECUTE_PATTERNS, SCRIPT_TRAILING_EXECUTES
    )


def _script_places(
    name: str | None,
    written: str,
    patterns: dict[str, "re.Pattern[str]"],
    trailing: dict[str, "re.Pattern[str]"],
) -> tuple[re.Match[str], ...]:
    """Return every place one script spells one of these commands at."""

    pattern = patterns.get(name)
    if pattern is None:
        return ()
    commands = _script_commands(name, written)
    found: dict[int, re.Match[str]] = {}
    place = 0
    while True:
        match = pattern.search(commands, place)
        if match is None:
            break
        if _script_encloses(name, commands, match.start(), match.end() - 1):
            place = match.start() + 1
            continue
        found.setdefault(match.end(), match)
        place = max(match.end(), match.start() + 1)
    for match in _script_trailing_places(name, commands, trailing):
        found.setdefault(match.end(), match)
    return tuple(match for _, match in sorted(found.items()))


def _reads_operands_as_data(words: tuple[Token, ...]) -> bool:
    """Report whether one run is written as a command this checker models.

    A run written as one of these commands reads its operands as data, so a
    path written inside a word of such a run names no file the run creates.
    Every other run may be an interpreter given a program text, which creates
    the files that text writes.

    Only a bare name is read this way. A command written as a path is a file
    the fixture supplies rather than the utility that name usually reaches, so
    `./printf` is not read as a command that only writes a message.
    """

    name = _resolved_command(words)
    if name is None or name not in DATA_OPERAND_COMMANDS:
        return False
    if _runs_a_script_command(words):
        return False
    if any(
        _assignment_name(token) is None and "/" in token.text for token in words[:1]
    ):
        return False
    return not _writes_through_a_script(words)


def _script_write_words(words: tuple[Token, ...]) -> tuple[Token, ...]:
    """Return every word of one run that names a file to write in its script.

    A script names the file to write inside the word the script is written
    with, so no other operand of the run is the name it writes. The command
    word a launcher is written before, and every file the run only reads, are
    left out that way.
    """

    name = _resolved_command(words)
    pattern = SCRIPT_WRITE_PATTERNS.get(name)
    if pattern is None:
        return ()
    return tuple(token for token in words[1:] if _script_writes(name, token.text))


def _writes_through_a_script(words: tuple[Token, ...]) -> bool:
    """Report whether one run names a file to write inside its own script."""

    return bool(_script_write_words(words))


def _runs_a_script_command(words: tuple[Token, ...]) -> bool:
    """Report whether one run is given a script that runs a command of its own.

    Such a script writes what the command it runs writes rather than what the
    script names, so the run is not read as one whose operands are data and
    not read as one whose script names the file it writes either.
    """

    name = _resolved_command(words)
    if name not in SCRIPT_EXECUTE_PATTERNS:
        return False
    return any(_script_executes(name, token.text) for token in words[1:])


def _carried_names(written: str) -> frozenset[str]:
    """Return every helper name one word this checker cannot read writes.

    An interpreter given a program text creates the files that text writes,
    and the shell unquoting needed to read such a text is not performed here,
    so a word this checker cannot read is refused rather than settled: it
    names a destination this checker cannot place. The name a written helper
    takes is the name its path ends with, so every path ending the text writes
    is read and the ones that name an observed command are reported. A word
    this checker can read is not read this way, because the operation it
    belongs to is already settled as the write it is written as.
    """

    if _word_parts(written, "c", splits=False) is not None:
        return frozenset()
    return _path_endings(written)


def _path_endings(written: str) -> frozenset[str]:
    """Return every helper name a path written inside one text ends with."""

    return frozenset(
        name
        for name in CARRIED_PATH_PATTERN.findall(written)
        if name in SHADOWED_HELPER_COMMANDS
    )


def _carried_helpers(words: tuple[Token, ...]) -> frozenset[str]:
    """Return every helper name the operands of one operation write unreadably.

    The command word is not read this way, because a word run as a command
    writes nothing by being written, and a run this checker models is not read
    this way at all, because its operands are data or a destination this
    checker already settles.
    """

    if _reads_operands_as_data(words):
        return frozenset()
    written = () if _runs_a_script_command(words) else _script_write_words(words)
    if written:
        # A script names the file to write after the write itself, so only the
        # text following each write is read. A path the script matches or
        # writes into its output names no file the run creates.
        name = _resolved_command(words)
        names = set()
        for token in written:
            if _word_parts(token.text, "c", splits=False) is not None:
                continue
            for match in _script_writes(name, token.text):
                names |= _path_endings(token.text[match.end():])
        return frozenset(names)
    names = set()
    for place, token in enumerate(words):
        if place:
            names |= _carried_names(token.text)
    return frozenset(names)


def _cannot_name_an_option(
    fixture: _Fixture, operation: _Operation, word: Token
) -> bool:
    """Report whether one written word can never be read as an option.

    This is the operand reading of `_cannot_be_an_option` for a command placed
    against no written run. A word written with a slash, and a word that
    settles to a path anchored at the root, both write a character no option
    letter carries, so no command reads them as an option.
    """

    parts = _word_parts(word.text, f"o{word.start.offset}", splits=True)
    if parts is not None and any(
        kind == LITERAL_SEGMENT and PATH_SEPARATOR in text for kind, text in parts
    ):
        return True
    settled = _settle_written_word(fixture, operation, word.text)
    return bool(settled) and all(anchored for anchored, _ in settled)


def _target_directory_value(written: str) -> object | None:
    """Return the directory one written option carries, read from the word itself.

    The option writes its value attached to the option letter, after an equals
    sign, or as the next word. The word is read as written rather than as the
    text it settles to, because a value that carries an expansion leaves the
    settled reading empty while the option it is attached to is still written.
    """

    if written.startswith(OPTION_END):
        name, separator, value = written[2:].partition("=")
        if not _abbreviates_target_directory(f"{OPTION_END}{name}"):
            return None
        if not separator:
            return TAKES_THE_NEXT_WORD
        return value
    letters = written[1:]
    place = letters.find(TARGET_DIRECTORY_MARK)
    if place < 0:
        return None
    return letters[place + 1 :] or TAKES_THE_NEXT_WORD


def _target_directories(
    fixture: _Fixture, operation: _Operation, words: Sequence[Token], index: int
) -> tuple[bool, frozenset[_Path], bool, list[Token]]:
    """Return the directory one operation places its operands inside.

    A command written with this option creates every operand it is given
    inside the directory the option names, so the operands are sources and
    none of them is the destination. A target directory this checker cannot
    settle leaves the destination unknown, which is reported so the caller
    never reads the operation as writing in place. A word this checker cannot
    read at all may be the option itself, so it is read that way unless it can
    never be an option.
    """

    present = False
    directories: set[_Path] = set()
    unknown = False
    named = False
    sources: list[Token] = []
    ended = False
    for place in range(index + 1, len(words)):
        token = words[place]
        written = token.text
        if not ended and written == OPTION_END:
            ended = True
            continue
        if named:
            settled = _settle_written_word(fixture, operation, written)
            directories |= settled
            unknown = unknown or not settled
            named = False
            continue
        if not ended and written.startswith(OPTION_MARK) and written != OPTION_MARK:
            value = _target_directory_value(written)
            if value is None:
                continue
            present = True
            if value is TAKES_THE_NEXT_WORD:
                named = True
                continue
            settled = _settle_written_word(fixture, operation, str(value))
            directories |= settled
            unknown = unknown or not settled
            continue
        if (
            not ended
            and _word_literals((token,))[0] is None
            and not _cannot_name_an_option(fixture, operation, token)
        ):
            # The word may expand to the target-directory option, and then the
            # destination is a directory no written text names here. The word
            # is kept as a source as well, because when it is not that option
            # it is the operand it was written as, and the name it ends with
            # still says what file the command creates.
            present = True
            unknown = True
            sources.append(token)
            continue
        sources.append(token)
    if named:
        unknown = True
    return present, frozenset(directories), unknown, sources


def _helper_paths(
    fixture: _Fixture, operation: _Operation
) -> tuple[frozenset[_Path], frozenset[tuple[_Path, str]], tuple[str, ...], bool]:
    """Return what one operation creates, read from the words the graph records.

    A redirection creates the path it writes. A helper-writing command creates
    its last operand, and when that operand names a directory it creates the
    source basename inside it, which no written text decides between. A command
    written with a target-directory option creates every remaining operand
    inside the directory that option names. The written words are returned as
    well, because a word this checker cannot settle still says what the file it
    creates is called, and a destination this checker cannot read at all is
    reported so the caller never reads the operation as writing nothing. Every
    branch reports an unsettled destination that way, because a path this
    checker cannot place is not a path it has proved lies outside the searched
    directories.
    """

    created: set[_Path] = set()
    inside: set[tuple[_Path, str]] = set()
    words: list[str] = list(operation.redirect_targets)
    unsettled = False
    for target in operation.redirect_targets:
        settled_target = _settle_written_word(fixture, operation, target)
        created |= settled_target
        unsettled = unsettled or not settled_target
    recorded = _operation_words(operation)
    ran = _resolved_command(recorded)
    for token in _script_write_words(recorded):
        # The script names the file to write inside its own word, after the
        # write it spells, so the path each write is followed by is settled as
        # well as the word itself. A script written in the word of the option
        # that carries it writes the option letters before the path, which
        # name no directory the path lies in.
        created |= _settle_written_word(fixture, operation, token.text)
        for match in _script_writes(ran, token.text):
            tail = token.text[match.end() :].lstrip(" \t")
            settled_tail = _settle_written_word(fixture, operation, tail)
            created |= settled_tail
            if settled_tail:
                continue
            # A path written with a value this checker cannot place is not a
            # path it has proved lies outside a searched directory, so the
            # name that path ends with is read as reachable.
            created |= {(False, (ending,)) for ending in _path_endings(tail)}
    literals = _word_literals(recorded)
    index = _command_index(literals, HELPER_WRITING_COMMANDS)
    if index < 0:
        return frozenset(created), frozenset(inside), tuple(words), unsettled
    written = literals[index]
    command = None if written is None else _basename(written)
    present, directories, unknown, sources = _target_directories(
        fixture, operation, recorded, index
    )
    if present:
        words.extend(source.text for source in sources)
        for source in sources:
            settled = _settle_written_word(fixture, operation, source.text)
            names = {
                segments[-1] for _, segments in settled if segments
            } or {_written_name(source.text)}
            for name in names:
                if not name:
                    continue
                inside.update((directory, name) for directory in directories)
        return frozenset(created), frozenset(inside), tuple(words), unknown or unsettled
    operands = _written_operands(recorded, literals, index)
    words.extend(operand.text for operand in operands)
    settled = [
        _settle_written_word(fixture, operation, operand.text) for operand in operands
    ]
    if command in HELPER_OPERAND_COMMANDS:
        for paths in settled:
            created |= paths
            unsettled = unsettled or not paths
        return frozenset(created), frozenset(inside), tuple(words), unsettled
    if len(operands) < 2:
        # The destination is not written as a second operand, so the one
        # written word is read as both the created path and a directory a
        # source name may be created inside.
        places = [path for paths in settled for path in paths]
        created.update(places)
        return (
            frozenset(created),
            frozenset(inside),
            tuple(words),
            unsettled or any(not paths for paths in settled),
        )
    destinations = settled[-1]
    created |= destinations
    unsettled = unsettled or not destinations
    for paths in settled[:-1]:
        for _, segments in paths:
            if not segments:
                continue
            inside.update((destination, segments[-1]) for destination in destinations)
    return frozenset(created), frozenset(inside), tuple(words), unsettled


def _body_operations(
    fixture: _Fixture, token: Token
) -> tuple[_Operation, ...] | None:
    """Return the commands of the declared body one record lies inside.

    A function body runs where it is called, not where it is written, so a
    redirection written there is expanded against the values its call sites
    hold. The checked graph already folds every reachable call environment
    into the values each body command holds, so the body commands are what the
    redirection word is settled against. Nothing is returned for a record
    written outside every declared body.
    """

    offset = token.start.offset
    for declaration in fixture.table.declarations:
        start = declaration.open_brace.start.offset
        end = declaration.close_brace.end.offset
        if not start <= offset <= end:
            continue
        return tuple(
            operation
            for operation in fixture.operations
            if start <= operation.offset <= end
        )
    return None


def _opens_an_enclosure(token: Token, starts: frozenset[int]) -> bool:
    """Report whether one written record opens a compound command.

    A reserved word opens a compound only where a command may start, so the
    same text written as an operand is data and is read as data. A subshell is
    opened by an operator record, which is never an operand.
    """

    if token.kind == shell_lexical.OPERATOR:
        return token.text == SUBSHELL_OPEN
    return (
        token.kind == shell_lexical.WORD
        and token.text in ENCLOSURE_OPENERS
        and token.start.offset in starts
    )


def _closes_an_enclosure(token: Token, starts: frozenset[int]) -> bool:
    """Report whether one written record closes a compound command."""

    if token.kind == shell_lexical.OPERATOR:
        return token.text == SUBSHELL_CLOSE
    return (
        token.kind == shell_lexical.WORD
        and token.text in ENCLOSURE_CLOSERS
        and token.start.offset in starts
    )


def _expansion_places(
    fixture: _Fixture, limit: int, enclosure: tuple[int, bool] | None, alone: bool
) -> tuple[int, ...]:
    """Return the offsets one detached redirection word may be expanded at.

    A shell expands the redirection word of a compound before it runs the
    body, so the values live where the compound starts are the ones it uses.
    A compound the shell may run again expands the word once per pass, so the
    values its body binds are read as well. A word the walk has already read
    as carrying no compound is expanded where it is written, exactly as a
    command word is. A word this checker cannot place against any compound is
    read against every place written before it, which names more files than
    the shell creates and never fewer.
    """

    if enclosure is None:
        return (limit,) if alone else _binding_places(fixture, limit)
    start, repeats = enclosure
    if not repeats:
        return (start,)
    return (start,) + tuple(
        place for place in _binding_places(fixture, limit) if place >= start
    )


def _binding_places(fixture: _Fixture, limit: int) -> tuple[int, ...]:
    """Return every written offset before one point where the values may differ.

    A value changes where an assignment is written and where a command runs,
    so those offsets are the points a redirection word may be expanded
    against. The point the word itself is written at is included, because the
    last command before it may leave the values it reads unchanged.
    """

    places = {limit}
    for operation in fixture.operations:
        if operation.offset <= limit:
            places.add(operation.offset)
    for run in fixture.command_runs():
        if run.tokens and run.tokens[0].start.offset <= limit:
            places.add(run.tokens[0].start.offset)
    return tuple(sorted(places))


def _read_names(written: str) -> frozenset[str]:
    """Return every name one written word reads."""

    parts = _word_parts(written, "r", splits=False)
    if parts is None:
        return frozenset()
    return frozenset(text for kind, text in parts if kind == "name")


def _detached_redirections(
    fixture: _Fixture,
) -> tuple[tuple[_Operation, str, frozenset[_Path]], ...]:
    """Return every write redirection no single command carries.

    A redirection written on a group, a subshell, or a loop creates a file
    just as one written on a command does, but it belongs to no command node,
    so the graph never reports it. The written records are read directly here,
    and each occurrence is kept apart by the position it is written at, because
    two commands may redirect to the same written word while the values they
    hold name different files.

    The shell expands such a word before it runs the enclosed body, while the
    word itself is written after that body, so no single command holds the
    values the shell uses. The word is therefore settled against every command
    written before it and the results are joined, which names every file the
    redirection may create and never reads a value bound inside the body as
    the only one. A command that binds nothing the word reads settles it to
    nothing, so a joined result is empty only when no written command names
    the file at all. Only a place that holds every name the word reads is
    joined, because a place written before those names exist reads the word as
    text the shell never produces.

    The value the shell expands is the one live where the enclosing compound
    starts, so that place is read rather than every place in the fixture. A
    compound the shell may run more than once expands the word again on each
    pass, so a value its body binds is joined as well.
    """

    if not fixture.operations:
        return ()
    index = _token_index(fixture.records)
    carried: set[int] = set()
    for operation in fixture.operations:
        located = _locate(index, operation.node)
        if located is None:
            continue
        pending = False
        for token in _command_span(*located):
            if token.kind == shell_lexical.OPERATOR:
                pending = token.text in WRITE_REDIRECTIONS
                continue
            if pending and token.kind == shell_lexical.WORD:
                carried.add(token.start.offset)
            pending = False
    ordered = sorted(fixture.operations, key=lambda operation: operation.offset)
    detached: list[tuple[_Operation, str, frozenset[_Path]]] = []
    regions = [
        fixture.records.tokens,
        *shell_lexical.executable_regions(fixture.records),
    ]
    for region in regions:
        pending = False
        open_enclosures: list[tuple[str, int]] = []
        closed: tuple[int, bool] | None = None
        # Nothing has been read yet, so a redirection written here carries no
        # compound and is expanded where it is written.
        alone = True
        starts = _command_positions(
            shell_lexical.LexicalProjection(fixture.text, region)
        )
        for token in region:
            if _opens_an_enclosure(token, starts):
                open_enclosures.append((token.text, token.start.offset))
                closed = None
                alone = True
                pending = False
                continue
            if _closes_an_enclosure(token, starts):
                opener, offset = (
                    open_enclosures[-1] if open_enclosures else ("", -1)
                )
                if opener in ENCLOSURE_CLOSERS[token.text]:
                    open_enclosures.pop()
                    closed = (offset, opener in REPEATING_ENCLOSURES)
                else:
                    # The written enclosures do not balance here, so no
                    # compound is known and the conservative reading is used.
                    closed = None
                    alone = False
                pending = False
                continue
            if token.kind == shell_lexical.OPERATOR:
                if token.text not in REDIRECTIONS:
                    # The redirections a compound carries end here, so the
                    # compound is no longer the one a later word belongs to.
                    closed = None
                    alone = True
                pending = token.text in WRITE_REDIRECTIONS
                continue
            if token.kind == shell_lexical.NEWLINE:
                # A compound carries its redirections on its own line, so the
                # list ends here and a later word belongs to no compound.
                closed = None
                alone = True
                pending = False
                continue
            if token.kind != shell_lexical.WORD:
                pending = False
                continue
            if not pending:
                closed = None
                alone = False
                continue
            pending = False
            if token.start.offset in carried:
                continue
            preceding = [
                operation
                for operation in ordered
                if operation.offset <= token.start.offset
            ] or [ordered[0]]
            read = _read_names(token.text)
            settled: set[_Path] = set()
            if not read:
                # A word written without an expansion names one file whatever
                # any command binds, so one reading settles it.
                settled |= _settle_written_word(fixture, preceding[-1], token.text)
            else:
                body = _body_operations(fixture, token)
                if body is not None:
                    if not any(operation.reachable for operation in body):
                        # No call the graph resolves reaches the body. A call
                        # it cannot resolve is read from the records instead,
                        # so nothing is settled here.
                        continue
                    for operation in body:
                        settled |= _settle_written_word(
                            fixture, operation, token.text
                        )
                else:
                    for place in _expansion_places(
                        fixture, token.start.offset, closed, alone
                    ):
                        bindings = fixture.bindings_before(place)
                        if not read <= frozenset(bindings):
                            continue
                        settled |= _settle_word(
                            token.text, bindings, fixture.unsettled_names()
                        )
            detached.append((preceding[-1], token.text, frozenset(settled)))
    return tuple(detached)


def _may_name_a_function(fixture: _Fixture, node: object) -> bool:
    """Report whether one dispatch this checker cannot read may call a body.

    A shell looks a command word up as a function only when the word holds no
    slash, so a dispatch written with a path, and one that settles only to
    paths, runs a file and never a declared body. A dispatch whose values this
    checker cannot settle may name anything, so it is read as naming a body.
    """

    if not node.words:
        return True
    written = node.words[0]
    parts = _word_parts(written.text, f"d{written.start.offset}", splits=False)
    if parts is not None and any(
        kind == LITERAL_SEGMENT and PATH_SEPARATOR in text for kind, text in parts
    ):
        return False
    settled = _settle_deferred_word(fixture, written.text)
    if not settled:
        return True
    return any(len(segments) < 2 and not anchored for anchored, segments in settled)


def _deferred_bodies(fixture: _Fixture) -> tuple[object, ...]:
    """Return every declared body a call outside the checked graph may reach.

    The graph folds a body into the calls it can resolve, so a body it
    resolves no call for holds no command node at all. A body is still run by
    a registered trap action, by a dispatch whose command word is an
    expansion, and by an included file, and each of those really creates the
    files the body writes. Such a body is returned here so that the helpers it
    writes are read from the written records rather than passed over. A body
    the graph does resolve a call for is returned as well, because a resolved
    call does not exhaust the calls a body gets: a deferred call may run it
    again with values the resolved call never held. A body such a body calls
    is reached as well, so the deferred names are closed over the calls the
    collected bodies make, over the actions they register, and over the files
    they include.
    """

    graph = fixture.graph
    if graph.is_fully_resolved:
        return ()
    every = bool(graph.included_sources) or any(
        _may_name_a_function(fixture, node) for node in graph.dynamic_commands
    )
    named: set[str] = set()
    for node in graph.trap_registrations:
        for value in node.argument_values:
            if value is None:
                # The action is an expansion, so it may name any body.
                every = True
                continue
            named.update(NAME_PATTERN.findall(value))
    declared = {
        declaration.name: declaration for declaration in fixture.table.declarations
    }
    pending = [name for name in named if name in declared]
    while pending and not every:
        declaration = declared[pending.pop()]
        operations = _deferred_operations(fixture, declaration)
        if operations is None:
            # The body is not readable on its own, so it may call any other.
            every = True
            break
        for operation in operations:
            if operation.effect == EFFECT_SOURCE:
                # The included file may call any body.
                every = True
                break
            if operation.effect == EFFECT_TRAP:
                registered: set[str] = set()
                for value in operation.node.argument_values:
                    if value is None:
                        every = True
                        break
                    registered.update(NAME_PATTERN.findall(value))
                if every:
                    break
                for called in registered & set(declared) - named:
                    named.add(called)
                    pending.append(called)
                continue
            if operation.node.dynamic:
                every = _may_name_a_function(fixture, operation.node)
                if every:
                    break
                continue
            called = operation.name
            if called in declared and called not in named:
                named.add(called)
                pending.append(called)
    return tuple(
        declaration
        for declaration in fixture.table.declarations
        if every or declaration.name in named
    )


def _deferred_operations(
    fixture: _Fixture, declaration: object
) -> tuple[_Operation, ...] | None:
    """Return one deferred operation per command of an unmodelled body.

    The body records are read through the same checked projections the rest of
    this module consumes, so no text is read a second time here, and every
    command the derivation records is returned as an operation whose values
    are settled against the whole fixture. Nothing is returned for a body
    those projections do not accept on its own, because it says nothing about
    which of its words are written.
    """

    body = declaration.body
    records = shell_lexical.LexicalProjection(fixture.text, body)
    try:
        table = shell_functions.derive(records)
        graph = shell_execution.derive(records, table)
    except (ShellFunctionError, ShellExecutionError):
        return None
    start = declaration.open_brace.start.offset
    return tuple(
        _Operation(
            node=node,
            offset=node.words[0].start.offset if node.words else start,
            reachable=True,
            conditional=True,
            text=fixture.text,
            deferred=True,
        )
        for node in graph.commands
    )


def _deferred_redirections(declaration: object) -> tuple[str, ...]:
    """Return every word an unmodelled body redirects a write to.

    A redirection belongs to no command node whenever a compound carries it,
    so the written records are read here as well, and the regions a
    substitution encloses are read with them.
    """

    body = declaration.body
    targets: list[str] = []
    for region in (body, *shell_lexical.executable_regions(body)):
        pending = False
        for token in region:
            if token.kind == shell_lexical.OPERATOR:
                pending = token.text in WRITE_REDIRECTIONS
                continue
            if pending and token.kind == shell_lexical.WORD:
                targets.append(token.text)
            pending = False
    return tuple(targets)


def _writes_where_no_word_names(fixture: _Fixture) -> bool:
    """Report whether the fixture puts a file in place without writing where.

    A command that puts a file in place takes its destination from the words
    it is written with, and `xargs` supplies those words from what it reads
    instead. Such a command creates a file no written text names at all, so
    nothing about it says the file is not a helper, and the fixture is read
    the way one whose search path this checker cannot place is read.
    """

    for operation in _every_operation(fixture):
        recorded = _operation_words(operation)
        if _resolved_command(recorded) not in HELPER_WRITING_COMMANDS:
            continue
        literals = _word_literals(recorded)
        if not any(
            literal is not None and _basename(literal) in WORD_SUPPLYING_COMMANDS
            for literal in literals
        ):
            # A command written with no destination of its own and nothing to
            # supply one creates no file.
            continue
        created, inside, words, _ = _helper_paths(fixture, operation)
        if not created and not inside and not words:
            return True
    return False


def _every_operation(fixture: _Fixture) -> tuple[_Operation, ...]:
    """Return every command this checker reads, including unmodelled bodies."""

    operations = [
        operation for operation in fixture.operations if operation.reachable
    ]
    for declaration in _deferred_bodies(fixture):
        operations.extend(_deferred_operations(fixture, declaration) or ())
    return tuple(operations)


def _loop_lists(fixture: _Fixture) -> dict[int, tuple[Token, ...]]:
    """Return the words each `for` head iterates, keyed by where the head starts."""

    lists: dict[int, tuple[Token, ...]] = {}
    for node in fixture.graph.nodes:
        if node.name != LOOP_KEYWORD or node.token is None:
            continue
        lists[node.token.start.offset] = node.words
    return lists


def _loop_list_paths(fixture: _Fixture, operation: _Operation) -> frozenset[_Path]:
    """Return every path the list of a `for` head enclosing one operation names.

    A `for` head binds its name once per round, and this checker settles no
    name a loop head binds, so a word written under it that reads that name is
    reported as unsettled with no name of its own. The list is written in full
    where the head is, though, so the file such a word creates is one of the
    paths the list names.
    """

    lists = _loop_lists(fixture)
    settled: set[_Path] = set()
    for enclosure in operation.node.enclosures:
        if enclosure.kind != LOOP_BODY or enclosure.token is None:
            continue
        for word in lists.get(enclosure.token.start.offset, ()):
            settled |= _settle_written_word(fixture, operation, word.text)
    return frozenset(settled)


def _shadowing_helpers(fixture: _Fixture) -> list[Finding]:
    """Reject every helper file the fixture writes into a searched directory.

    A helper is written either through a redirection or as the operand of a
    command that puts a file in place. Both readings settle the written word
    against the values the operation holds, so a helper named through a
    variable is read as the name it carries. A created path no written text
    anchors at the root names a directory the shell decides, and the shell may
    be in a searched directory, so such a path is read as reachable. A created
    path is compared against a searched directory by what both are written
    with rather than by their text, because a substitution that reads the
    working directory names a directory `cd` decides, so two paths written
    apart may still name one directory. A fixture
    whose search path this checker cannot place, and an operation whose
    destination it cannot read, prove nothing about where a written file is
    found, so every helper they name is rejected on the name the word is
    written with. A word this checker cannot read at all is refused rather
    than settled, because an interpreter given a program text creates the
    files that text writes, and a command that takes its destination from what
    it reads names no file at all, so the fixture is then read for every
    helper name it writes anywhere. A redirection written on a group or a loop
    carries no command of its own, so it is read from the written records as
    well.
    """

    searched, unplaced = _searched_directories(fixture)
    if not searched and not unplaced:
        return []
    unnamed = _writes_where_no_word_names(fixture)
    unplaced = unplaced or unnamed
    findings: dict[tuple[str, int | None], Finding] = {}

    def record(name: str, position: Position | None) -> None:
        findings.setdefault(
            (name, None if position is None else position.offset),
            Finding(
                RULE_COMMAND_SHADOWING,
                f"the fixture writes a `{name}` helper the command search path "
                "it puts in place can reach before the command a bound "
                "observation runs",
                position,
            ),
        )

    if unnamed:
        # The file that command creates is named by nothing written, so every
        # helper name the fixture writes anywhere may be the name it takes.
        for operation in _every_operation(fixture):
            recorded = _operation_words(operation)
            literals = _word_literals(recorded)
            # The word a launcher chain runs is a command name rather than a
            # path, so the reading starts after the command this run resolves.
            start = max(
                _command_index(literals, OBSERVED_COMMANDS),
                _command_index(literals, HELPER_WRITING_COMMANDS),
                0,
            )
            for place, token in enumerate(recorded):
                if place <= start:
                    continue
                name = _written_name(token.text)
                if name in SHADOWED_HELPER_COMMANDS:
                    record(name, operation.position)
    for operation in fixture.operations:
        if not operation.reachable:
            continue
        created, inside, words, unknown = _helper_paths(fixture, operation)
        for anchored, segments in created:
            if not segments or segments[-1] not in SHADOWED_HELPER_COMMANDS:
                continue
            reached = _reaches_a_searched_directory(
                (anchored, segments[:-1]), searched
            )
            if unplaced or not anchored or reached:
                record(segments[-1], operation.position)
        for directory, name in inside:
            if name not in SHADOWED_HELPER_COMMANDS:
                continue
            reached = _reaches_a_searched_directory(directory, searched)
            if unplaced or not directory[0] or reached:
                record(name, operation.position)
        for name in _carried_helpers(_operation_words(operation)):
            record(name, operation.position)
        if unknown:
            for anchored, segments in _loop_list_paths(fixture, operation):
                if not segments or segments[-1] not in SHADOWED_HELPER_COMMANDS:
                    continue
                reached = _reaches_a_searched_directory(
                    (anchored, segments[:-1]), searched
                )
                if unplaced or not anchored or reached:
                    record(segments[-1], operation.position)
        if not unplaced and not unknown:
            continue
        for word in words:
            name = _written_name(word)
            if name in SHADOWED_HELPER_COMMANDS:
                record(name, operation.position)
    for operation, target, settled in _detached_redirections(fixture):
        for anchored, segments in settled:
            if not segments or segments[-1] not in SHADOWED_HELPER_COMMANDS:
                continue
            reached = _reaches_a_searched_directory(
                (anchored, segments[:-1]), searched
            )
            if unplaced or not anchored or reached:
                record(segments[-1], operation.position)
        if not settled or unplaced:
            name = _written_name(target)
            if name in SHADOWED_HELPER_COMMANDS:
                record(name, operation.position)
    for declaration in _deferred_bodies(fixture):
        position = declaration.name_token.start
        operations = _deferred_operations(fixture, declaration)
        if operations is None:
            for token in declaration.body:
                if token.kind != shell_lexical.WORD:
                    continue
                name = _written_name(token.text)
                if name in SHADOWED_HELPER_COMMANDS:
                    record(name, position)
                for carried in _carried_names(token.text):
                    record(carried, position)
            continue
        for operation in operations:
            created, inside, words, unknown = _helper_paths(fixture, operation)
            for anchored, segments in created:
                if not segments or segments[-1] not in SHADOWED_HELPER_COMMANDS:
                    continue
                reached = _reaches_a_searched_directory(
                    (anchored, segments[:-1]), searched
                )
                if unplaced or not anchored or reached:
                    record(segments[-1], position)
            for directory, name in inside:
                if name not in SHADOWED_HELPER_COMMANDS:
                    continue
                reached = _reaches_a_searched_directory(directory, searched)
                if unplaced or not directory[0] or reached:
                    record(name, position)
            for name in _carried_helpers(_operation_words(operation)):
                record(name, position)
            if not unplaced and not unknown:
                continue
            for word in words:
                name = _written_name(word)
                if name in SHADOWED_HELPER_COMMANDS:
                    record(name, position)
        for target in _deferred_redirections(declaration):
            settled = _settle_deferred_word(fixture, target)
            for anchored, segments in settled:
                if not segments or segments[-1] not in SHADOWED_HELPER_COMMANDS:
                    continue
                reached = _reaches_a_searched_directory(
                    (anchored, segments[:-1]), searched
                )
                if unplaced or not anchored or reached:
                    record(segments[-1], position)
            if not settled or unplaced:
                name = _written_name(target)
                if name in SHADOWED_HELPER_COMMANDS:
                    record(name, position)
    return list(findings.values())


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


def check(
    source: str | bytes,
    declared: Iterable[str] | None = None,
    sourced: Mapping[str, str | bytes] | None = None,
) -> tuple[Finding, ...]:
    """Return every Copier fixture operation the supplied bytes fail to prove.

    `declared` carries the update source paths the Copier update inventory
    declares, written one path per entry. A caller that omits it gets the
    inventory this checker ships beside, because the fixture builds its own
    inventory path from a positional parameter that no supplied byte places.

    `sourced` binds the libraries the fixture may source, each written as the
    repository-relative path the fixture names it by. A caller that omits it
    gets the libraries this checker ships beside. A source that names any
    other path is rejected, because a file nothing bound could rebind a
    command name for every bound observation while the fixture kept exactly
    the text it was committed with.
    """

    inventory = read_inventory() if declared is None else declared_paths(declared)
    libraries = read_libraries() if sourced is None else library_sources(sourced)
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
    findings.extend(_check_inventory_region(fixture, inventory))
    findings.extend(_check_direct_invocation(fixture))
    findings.extend(_check_command_shadowing(fixture))
    findings.extend(_check_sourced_libraries(fixture, libraries))
    findings.extend(_check_unresolved_dispatch(fixture))
    if _is_transition(fixture):
        findings.extend(_check_transition(fixture))
    return tuple(sorted(findings, key=lambda finding: finding.sort_key))


def validate(
    source: str | bytes,
    declared: Iterable[str] | None = None,
    sourced: Mapping[str, str | bytes] | None = None,
) -> None:
    """Raise when supplied bytes break the bounded Copier fixture contract."""

    findings = check(source, declared, sourced)
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
    parser.add_argument(
        "--inventory",
        metavar="PATH",
        default=INVENTORY_PATH,
        type=Path,
        help="read the declared Copier update source paths from this inventory",
    )
    parser.add_argument(
        "--library-root",
        metavar="PATH",
        default=LIBRARY_ROOT,
        type=Path,
        help="read the bound sourced libraries from this directory",
    )
    arguments = parser.parse_args(argv)
    try:
        supplied = arguments.check.read_bytes()
    except OSError as error:
        print(f"copier fixture check failed: {error}", file=sys.stderr)
        return 1
    try:
        declared = arguments.inventory.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        print(f"copier fixture check failed: {error}", file=sys.stderr)
        return 1
    try:
        findings = check(
            supplied, declared, read_libraries(arguments.library_root)
        )
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
