"""Interpret the bounded command forms a pre-tool gate is allowed to recognize.

A gate that searches a whole command string for a lifecycle file name cannot
tell `python3 scripts/restructure-plan.py` from `wc -l
scripts/restructure-plan.py`. The first is a repository write; the second only
reads the file. This module answers two narrow questions instead:

* which recognized invocations inside one command string begin with a
  repository write, and
* which directory such an invocation actually runs in.

It is deliberately not a shell. It recognizes ordinary Git commands and a
single interpreter launching a named lifecycle script, and nothing else. An
unrecognized command is reported as unrecognized; it is never certified
read-only, and the authoritative fail-closed surfaces stay the lifecycle
commands and the pre-commit hook.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path


class ContextError(RuntimeError):
    """The payload described an execution directory that cannot be trusted.

    The directories the payload named are carried along, so a caller that must
    reject the context can still ask whether any of them is governed instead of
    falling back to a directory the command does not run in.
    """

    def __init__(self, message: str, candidates: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.candidates = candidates


class Unparsed(RuntimeError):
    """The command string is outside the recognized forms and needs the fallback."""


# Command text that builds a program name at run time cannot be read
# statically. Such a string is handed back to the caller's conservative
# pattern fallback rather than interpreted here.
DYNAMIC_MARKERS = ("$(", "`", "${", "$((")

OPERATORS = frozenset({"&&", "||", ";", "|", "&", "(", ")", "<", ">", ">>", "<<", ";;", "|&"})

# A redirection operator is followed by a file name, not by a program, so the
# word after it must not be read as the start of a new invocation.
REDIRECTIONS = frozenset({"<", ">", ">>", "<<", "<<<", "<&", ">&", "&>", "&>>", "2>", "2>>"})

# Wrappers that run another program without changing what that program does.
# `env python3 scripts/restructure-plan.py` is still that script running.
WRAPPERS = frozenset({"env", "command", "nohup", "time", "timeout", "stdbuf", "setsid", "exec"})

# Programs whose arguments name another program to run. This module cannot
# tell which of their arguments is that program, so it declines to interpret
# them instead of reading the arguments as data.
COMMAND_RUNNERS = frozenset({
    "xargs", "parallel", "watch", "find", "make", "ssh", "sudo", "doas", "su",
    "chroot", "unshare", "strace", "ltrace", "script", "npx", "uv",
})

# Programs that change the directory the rest of the command runs in, or that
# re-enter the shell. This module models neither, so it declines to interpret
# a command that contains one.
CONTEXT_COMMANDS = frozenset({"cd", "pushd", "popd", "chdir", "eval", "source", "."})

# Programs that only read the files named in their arguments, together with the
# bounded option grammar that keeps each of them read-only. An option outside
# this grammar may redirect output, run a helper program or rewrite a file, so
# the invocation is reported as unread instead of certified read-only.
READER_FLAGS = {
    "cat": frozenset({"-n", "-b", "-s", "-E", "-T", "-v", "-A", "-e", "-t"}),
    "wc": frozenset({"-l", "-c", "-w", "-m", "-L"}),
    "head": frozenset(),
    "tail": frozenset(),
    "nl": frozenset(),
    "file": frozenset({"-b", "-i"}),
    "stat": frozenset(),
    "basename": frozenset(),
    "dirname": frozenset(),
    "realpath": frozenset({"-e", "-m"}),
    "readlink": frozenset({"-f"}),
    "cksum": frozenset(),
    "md5sum": frozenset(),
    "sha1sum": frozenset(),
    "sha256sum": frozenset(),
    "grep": frozenset({
        "-n", "-i", "-r", "-R", "-l", "-L", "-c", "-v", "-w", "-x", "-H", "-h",
        "-F", "-E", "--files-with-matches", "--count", "--line-number",
    }),
    "rg": frozenset({
        "-n", "-i", "-l", "-L", "-c", "-w", "-x", "-F", "--files-with-matches",
        "--count", "--no-heading", "--line-number",
    }),
}

# Reader options that consume the next word as their own value.
READER_VALUE_OPTIONS = {
    "head": frozenset({"-n", "-c"}),
    "tail": frozenset({"-n", "-c"}),
    "stat": frozenset({"-c"}),
    "grep": frozenset({"-e", "-m"}),
    "rg": frozenset({"-e", "-m", "-g", "-t"}),
}

# Redirection operators that can create or overwrite their operand.
OUTPUT_REDIRECTIONS = frozenset({">", ">>", ">&", "&>", "&>>", "2>", "2>>"})

# A leading environment assignment names a variable and then its value. An
# option that merely contains `=` is not an assignment and must not be dropped.
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")

INTERPRETERS = frozenset({"python", "python2", "python3", "py"})
SHELLS = frozenset({"sh", "bash", "dash", "zsh", "ksh"})

# Interpreter options that consume the next word as their own value, so that
# word is not the script being launched.
INTERPRETER_VALUE_OPTIONS = frozenset({"-X", "-W", "-Q", "--check-hash-based-pycs"})

# Shell options that consume the next word, so that word is not the script.
SHELL_VALUE_OPTIONS = frozenset({"-O", "+O", "-o", "+o"})

# Lifecycle subcommands that only report. Any other subcommand, or none that
# this module recognizes, keeps the conservative write answer.
LIFECYCLE_READ_ONLY_SUBCOMMANDS = {"plan_authoring.py": frozenset({"check", "legacy-input"})}
LIFECYCLE_SUBCOMMANDS = {"plan_authoring.py": frozenset({"check", "write", "legacy-input"})}

# Lifecycle scripts whose ordinary invocation writes to the repository. The set
# matches the names the previous pattern list already recognized, so this module
# changes how a command is recognized, not which commands are governed.
LIFECYCLE_SCRIPTS = frozenset(
    {
        "create-plan.sh",
        "create-plan.py",
        "complete-plan.sh",
        "complete-plan.py",
        "finalize-plan.sh",
        "finalize-plan.py",
        "shelve-plan.sh",
        "shelve-plan.py",
        "promote-plan.sh",
        "promote-plan.py",
        "restructure-plan.py",
        "plan_authoring.py",
    }
)

GIT_WRITE_SUBCOMMANDS = frozenset(
    {
        "commit",
        "merge",
        "rebase",
        "cherry-pick",
        "revert",
        "am",
        "apply",
        "stash",
        "update-ref",
        "mv",
        "rm",
        "restore",
        "switch",
        "checkout",
        "add",
    }
)

# `git branch` and `git tag` write only when they are given a name to create,
# so their listing and query forms stay outside the write set.
GIT_NAMING_SUBCOMMANDS = frozenset({"branch", "tag"})
GIT_LISTING_WORDS = frozenset({"l", "list", "show-current", "contains"})

# Git global options that carry a separate value token before the subcommand.
GIT_VALUE_OPTIONS = frozenset({"-c", "-C"})

# Git subcommands that only report. Recognizing them positively is what lets a
# lifecycle path appear in `git log -- <path>` without becoming a write.
GIT_READ_SUBCOMMANDS = frozenset(
    {
        "log",
        "status",
        "show",
        "diff",
        "blame",
        "ls-files",
        "ls-tree",
        "cat-file",
        "rev-parse",
        "rev-list",
        "describe",
        "shortlog",
        "reflog",
        "grep",
        "for-each-ref",
        "merge-base",
        "name-rev",
        "whatchanged",
        "check-ignore",
    }
)

# Argument-object keys that an execution tool uses for the command text and for
# the directory the command runs in.
COMMAND_KEYS = ("command", "cmd", "shell_command")
WORKDIR_KEYS = ("workdir", "cwd")
ARGUMENT_CONTAINERS = ("arguments", "tool_input")


@dataclass(frozen=True)
class RepositoryWrite:
    """One recognized invocation whose first repository effect is a write."""

    program: str
    directories: tuple[str, ...]


class ReadOnly:
    """A positively recognized invocation that writes nothing.

    This is distinct from "nothing was recognized". Only a form this module
    validated may certify a lifecycle file name as data; an unrecognized form
    keeps the caller's conservative fallback.
    """

    __slots__ = ()


READ_ONLY = ReadOnly()

Answer = RepositoryWrite | ReadOnly | None


def mentions_lifecycle(word: str) -> bool:
    """Report whether this word names a lifecycle script anywhere inside it."""

    return any(name in word for name in LIFECYCLE_SCRIPTS)


def has_dynamic_construction(command: str) -> bool:
    """Report whether the command builds part of itself at run time."""

    return any(marker in command for marker in DYNAMIC_MARKERS)


def tokenize(line: str) -> list[str]:
    """Split one command line into words and shell operators.

    Quoting is honored, so a file name inside a quoted argument stays one word
    and never looks like a separate command.
    """

    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError as error:
        raise Unparsed(f"command could not be tokenized: {error}") from error


def segments(command: str) -> list[list[str]]:
    """Return the separate invocations in one command string.

    A newline separates commands exactly as `;` does, so the lines are split
    before tokenizing rather than being folded into ordinary whitespace.
    """

    if has_dynamic_construction(command):
        raise Unparsed("command constructs part of itself at run time")
    found: list[list[str]] = []
    for line in command.splitlines():
        current: list[str] = []
        skip_operand = False
        output_target = False
        for token in tokenize(line):
            if token in OPERATORS or (
                token and all(character in "&|;()<>" for character in token)
            ):
                if token in REDIRECTIONS:
                    # The redirection target belongs to the invocation that is
                    # already open; it never starts a new one.
                    skip_operand = True
                    output_target = token in OUTPUT_REDIRECTIONS
                    continue
                if current:
                    found.append(current)
                current = []
                skip_operand = False
                output_target = False
                continue
            if skip_operand:
                skip_operand = False
                if output_target and mentions_lifecycle(token):
                    # The command writes this file directly, so it must never
                    # be dropped as a mere redirection operand.
                    raise Unparsed("output redirection targets a lifecycle script")
                output_target = False
                continue
            current.append(token)
        if current:
            found.append(current)
    return found


def strip_dashes(word: str) -> str:
    name = word.split("=", 1)[0]
    return name[2:] if name.startswith("--") else name[1:] if name.startswith("-") else name


def bundles(option: str, letters: str) -> bool:
    """Report whether one short-option token carries any of these letters.

    Short options combine, so `bash -lc` carries the same `-c` that `bash -l -c`
    does. Reading only the exact token `-c` would let the combined form hide the
    program text that follows it.
    """

    if not option.startswith("-") or option.startswith("--"):
        return False
    return any(letter in option[1:] for letter in letters)


def git_write(tokens: list[str]) -> Answer:
    """Interpret one `git ...` invocation, including its `-C` directories."""

    directories: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in GIT_VALUE_OPTIONS:
            if index + 1 >= len(tokens):
                return None
            if token == "-C":
                directories.append(tokens[index + 1])
            index += 2
            continue
        if token.startswith("-"):
            # Any other global option changes context this module does not
            # model, so the invocation stays unrecognized instead of being
            # judged on an assumed repository.
            return None
        break
    else:
        return None
    subcommand = tokens[index]
    arguments = tokens[index + 1 :]
    if subcommand in GIT_WRITE_SUBCOMMANDS:
        return RepositoryWrite(f"git {subcommand}", tuple(directories))
    if subcommand in GIT_NAMING_SUBCOMMANDS:
        if not arguments or strip_dashes(arguments[0]) in GIT_LISTING_WORDS:
            return READ_ONLY
        return RepositoryWrite(f"git {subcommand}", tuple(directories))
    if subcommand in GIT_READ_SUBCOMMANDS:
        return READ_ONLY
    return None


def lifecycle_write(name: str, arguments: list[str]) -> bool:
    """Report whether this lifecycle script invocation writes in this mode.

    Only an option that argparse still reads as an option can select a
    reporting mode. Everything after a `--` terminator is a positional value,
    so a file named `--verify` never certifies a write as verification.
    """

    options = arguments[: arguments.index("--")] if "--" in arguments else list(arguments)
    if name == "restructure-plan.py":
        return not any(option.split("=", 1)[0] == "--verify" for option in options)
    known = LIFECYCLE_SUBCOMMANDS.get(name)
    if known is not None:
        for word in options:
            if word in known:
                return word not in LIFECYCLE_READ_ONLY_SUBCOMMANDS[name]
        # A grammar this module cannot read is not evidence of a reporting
        # mode, so the write answer stands.
        return True
    return True


def launched_script(arguments: list[str], *, interpreter: bool) -> tuple[str, list[str]] | None:
    """Return the script an interpreter launches and the arguments after it."""

    index = 0
    while index < len(arguments) and arguments[index].startswith("-"):
        option = arguments[index]
        if option == "--":
            index += 1
            break
        if interpreter and bundles(option, "cm"):
            # A program body or module name is data for the interpreter. A
            # lifecycle file name inside it is not an invocation of that file.
            return None
        if not interpreter and bundles(option, "c"):
            # Shell program text is another command string that this module
            # does not interpret. The caller keeps its conservative fallback
            # for it instead of certifying it.
            raise Unparsed("shell program text is not a recognized invocation")
        value_options = INTERPRETER_VALUE_OPTIONS if interpreter else SHELL_VALUE_OPTIONS
        if option.split("=", 1)[0] in value_options and "=" not in option:
            index += 2
            continue
        index += 1
    if index >= len(arguments):
        return None
    return Path(arguments[index]).name, arguments[index + 1 :]


def reader_is_read_only(program: str, arguments: list[str]) -> bool:
    """Report whether this reader invocation stays inside its read-only grammar.

    An option outside the recorded grammar may redirect output, run a helper
    program or rewrite a file, so it is not read-only evidence.
    """

    flags = READER_FLAGS[program]
    value_options = READER_VALUE_OPTIONS.get(program, frozenset())
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--":
            return True
        if not word.startswith("-") or word == "-":
            index += 1
            continue
        if "=" in word:
            # An option that carries its own value can name a program or an
            # output file, which this grammar does not model.
            return False
        if word in value_options:
            index += 2
            continue
        if word not in flags:
            return False
        index += 1
    return True


def script_write(tokens: list[str]) -> Answer:
    """Interpret a lifecycle script launched directly or through an interpreter."""

    while tokens:
        head = Path(tokens[0]).name
        if head in WRAPPERS:
            # A wrapper runs the rest of the line, so the invocation it hides is
            # the one that matters. `env` also carries `VAR=value` assignments.
            tokens = [
                token
                for token in tokens[1:]
                if not ASSIGNMENT.match(token.split("/", 1)[0])
            ]
            continue
        if ASSIGNMENT.match(tokens[0].split("/", 1)[0]):
            # A leading assignment sets the environment of the invocation that
            # follows it; the invocation is still the thing being run.
            tokens = tokens[1:]
            continue
        break
    if not tokens:
        return None
    program = Path(tokens[0]).name
    if tokens[0].startswith("-") or program.startswith("-") or program.isdigit():
        # An option or an IO number in program position means a wrapper or a
        # redirection was not modelled here, so the invocation is unread.
        raise Unparsed("invocation does not begin with a program name")
    if "$" in tokens[0]:
        # The program name is only known once the shell expands it.
        raise Unparsed("program name is expanded at run time")
    if program in CONTEXT_COMMANDS:
        raise Unparsed(f"{program} changes the context the rest of the command runs in")
    if program in COMMAND_RUNNERS:
        raise Unparsed(f"{program} runs a program named in its arguments")
    arguments = tokens[1:]
    if program == "git":
        return git_write(tokens)
    if program in INTERPRETERS or program in SHELLS:
        launched = launched_script(arguments, interpreter=program in INTERPRETERS)
        if launched is None:
            # The interpreter was given a program body rather than a script, so
            # a lifecycle name inside it is data the interpreter reads.
            return READ_ONLY
        target, remainder = launched
        if target not in LIFECYCLE_SCRIPTS:
            if any(Path(word).name in LIFECYCLE_SCRIPTS for word in arguments):
                # An option this module does not model consumed the script
                # position, so the invocation is unread rather than harmless.
                raise Unparsed("interpreter options hide the launched script")
            return None
        return (
            RepositoryWrite(target, ())
            if lifecycle_write(target, remainder)
            else READ_ONLY
        )
    if program in LIFECYCLE_SCRIPTS:
        return (
            RepositoryWrite(program, ())
            if lifecycle_write(program, arguments)
            else READ_ONLY
        )
    if program in READER_FLAGS:
        if not reader_is_read_only(program, arguments):
            raise Unparsed(f"{program} was given an option outside its read-only grammar")
        return READ_ONLY
    return None


def repository_writes(command: str) -> list[RepositoryWrite]:
    """Return the recognized invocations in this command that begin with a write.

    Raises :class:`Unparsed` when the command is outside the recognized forms,
    which leaves the decision with the caller's conservative fallback.
    """

    writes: list[RepositoryWrite] = []
    for tokens in segments(command):
        if not tokens:
            continue
        found = script_write(tokens)
        if isinstance(found, RepositoryWrite):
            writes.append(found)
            continue
        if found is READ_ONLY:
            continue
        if any(mentions_lifecycle(token) for token in tokens):
            # Nothing here explains why a lifecycle script is named, so the
            # previous conservative classification decides this command.
            raise Unparsed("no recognized invocation explains this lifecycle reference")
    return writes


def payload_workdir(payload: dict) -> str | None:
    """Return the one execution directory this payload supplies, if any.

    Only an execution-tool argument object is read. An absent directory is a
    real limitation of the payload, reported as ``None`` so the caller keeps
    its own process directory rather than guessing a repository.
    """

    values: list[str] = []
    malformed = False
    for container_key in ARGUMENT_CONTAINERS:
        container = payload.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in WORKDIR_KEYS:
            if key not in container:
                continue
            value = container[key]
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip() or "\0" in value:
                # Keep scanning, so a malformed value never hides a governed
                # directory that the payload also named.
                malformed = True
                continue
            values.append(value)
    distinct = sorted(set(values))
    if malformed:
        raise ContextError("execution directory is malformed", tuple(distinct))
    if len(distinct) > 1:
        raise ContextError(
            "payload names conflicting execution directories",
            tuple(distinct),
        )
    return values[0] if values else None


def effective_directory(base: Path, workdir: str | None, directories: tuple[str, ...]) -> Path:
    """Resolve the directory one recognized invocation actually runs in.

    A relative directory resolves against the invocation base, which is the
    payload directory when the tool supplies one and the hook's own process
    directory when it does not.
    """

    current = base
    for value in (workdir, *directories):
        if value is None:
            continue
        candidate = Path(value)
        current = candidate if candidate.is_absolute() else current / candidate
    try:
        resolved = current.resolve()
    except OSError as error:
        raise ContextError(f"execution directory cannot be resolved: {error}") from error
    if not resolved.is_dir():
        raise ContextError(f"execution directory does not exist: {resolved}")
    return resolved
