"""Shared security detection patterns for generated workflow checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple


PRIVATE_KEY_MATERIAL = re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")
REMOTE_SCRIPT_PIPE = re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sh|bash|zsh)\b")
SUDO_COMMAND = re.compile(r"^\s*sudo\b", re.MULTILINE)

# Credential-name classification.
#
# Names are compared by underscore-separated segment rather than by word
# boundary, because the underscore is a word character and `\btoken\b` misses
# API_TOKEN. A bare `key` segment is deliberately absent from the unambiguous
# list, because SORT_KEY and PRIMARY_KEY are ordinary names; `key` only counts
# inside one of the enumerated two-segment phrases.
UNAMBIGUOUS_CREDENTIAL_SEGMENTS = frozenset(
    {
        "apikey",
        "auth",
        "authorization",
        "bearer",
        "credential",
        "credentials",
        "passphrase",
        "passwd",
        "password",
        "pat",
        "pwd",
        "secret",
        "secrets",
        "token",
        "tokens",
    }
)
CREDENTIAL_SEGMENT_PHRASES = frozenset(
    {
        ("access", "key"),
        ("account", "key"),
        ("api", "key"),
        ("encryption", "key"),
        ("license", "key"),
        ("private", "key"),
        ("secret", "key"),
        ("session", "key"),
        ("signing", "key"),
        ("subscription", "key"),
    }
)

VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Bash accepts `NAME=value`, `NAME+=value` and the indexed forms as assignment
# words before the command head, so all of them must be stepped over rather
# than mistaken for the command itself.
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?\+?=.*", re.DOTALL)
ESCAPED_CHARACTER = re.compile(r"\\.", re.DOTALL)
LINE_CONTINUATION = re.compile(r"\\\n")
# A token the shell reads as a redirection rather than as an operand. It is
# dropped before the command head is found and before deciding whether a dump
# command was given an operand, so `set 2>/dev/null` is still a bare `set`.
REDIRECTION = re.compile(r"[0-9]*(?:<<<|<<-?|<&|>&|&>>|&>|>>|>\||<>|<|>)")
HERE_DOCUMENT = re.compile(
    r"<<-?\s*(?P<quote>['\"]?)(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)"
)

# Every refused command head is enumerated. A category such as "a command that
# displays text" is not decidable, so the list is closed on purpose and the
# forms outside it stay recorded as residual exposure in the plan.
DISPLAY_COMMANDS = frozenset(
    {"cat", "echo", "head", "less", "logger", "more", "printf", "tail", "tee"}
)
# Heads that only introduce another command; the refusal continues at the
# command they run, so `env NAME=value program` stays an ordinary child-process
# environment assignment.
TRANSPARENT_PREFIXES = frozenset(
    {"builtin", "command", "exec", "nohup", "stdbuf", "sudo", "time"}
)
# Options of those heads that consume the following token, which would
# otherwise be mistaken for the command they introduce.
PREFIX_OPTIONS_WITH_ARGUMENT = {
    "command": frozenset(),
    "builtin": frozenset(),
    "exec": frozenset({"-a"}),
    "nohup": frozenset(),
    "stdbuf": frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}),
    "sudo": frozenset(
        {"-C", "-D", "-g", "-h", "-p", "-R", "-r", "-t", "-T", "-U", "-u", "--user", "--group"}
    ),
    "time": frozenset({"-f", "--format", "-o", "--output"}),
}
# Options that make a head report something and exit instead of running a
# command, so nothing is displayed and nothing is dumped.
INSPECTION_OPTIONS = frozenset({"-v", "-V", "--help", "--version", "--usage"})
DEFINITION_PRINT_COMMANDS = frozenset({"declare", "export", "readonly", "typeset"})
# Shell reserved words and grouping punctuation that stand in front of a simple
# command, so `if true; then env; fi` still reaches `env`.
CONTROL_WORDS = frozenset(
    {
        "!",
        "(",
        ")",
        "{",
        "}",
        "case",
        "coproc",
        "do",
        "done",
        "elif",
        "else",
        "esac",
        "fi",
        "for",
        "function",
        "if",
        "in",
        "select",
        "then",
        "until",
        "while",
    }
)
# `env` options that carry the child command inside the option itself, so the
# invocation runs a command even though no separate command token follows.
ENV_COMMAND_OPTIONS = ("-S", "--split-string")
# `env` options that consume the following token. The signal options are absent
# on purpose: they take an optional value only in the `--option=VALUE` form, so
# consuming the next token would hide the command that follows them.
ENV_OPTIONS_WITH_ARGUMENT = frozenset({"-u", "--unset", "-C", "--chdir"})

# Bounds on the work one command may cause. The gate runs on every tool call,
# so a pathological string must reach a decision instead of exhausting the
# interpreter; reaching a bound refuses the command rather than allowing it.
SCAN_CHARACTER_LIMIT = 200_000
SCAN_ITEM_LIMIT = 4_096
SEGMENT_DEPTH_LIMIT = 8

POLICY_RELATIVE = Path("docs/agent/external-services.yaml")
_DECLARED_CACHE: dict[Path, frozenset[str]] = {}


class ScanLimitReached(Exception):
    """A command exceeded the bounded work this scanner will do for it."""


class Token(NamedTuple):
    """One shell word, kept in the two forms the rules need.

    `word` is what the shell would use as a name, with quoting removed, so a
    quoted command head or operand is compared like an unquoted one.
    `expandable` keeps only the parts the shell would expand, so text inside
    single quotes cannot be mistaken for a live expansion.
    """

    word: str
    expandable: str


def credential_segments(name: str) -> tuple[str, ...]:
    """Split a variable name into the segments the classifier compares."""
    return tuple(segment for segment in name.lower().split("_") if segment)


def is_credential_name(name: str, declared: object = frozenset()) -> bool:
    """Report whether this variable name holds a credential.

    The name counts when one segment is an unambiguous credential word, when
    two adjacent segments form an enumerated credential phrase, or when the
    external-services policy declares it. The segment rules are checked first
    so that a name they already settle never pays for the policy read. The
    result cannot be overridden, because an exemption here would certify a
    disclosure.
    """
    segments = credential_segments(name)
    if any(segment in UNAMBIGUOUS_CREDENTIAL_SEGMENTS for segment in segments):
        return True
    if any(pair in CREDENTIAL_SEGMENT_PHRASES for pair in zip(segments, segments[1:])):
        return True
    return name in declared


def is_fixed_literal(text: str) -> bool:
    """Report whether the shell can substitute nothing into this text.

    A backslash escape cannot reintroduce an expansion, so escaped characters
    are removed before looking for the two characters that can.
    """
    stripped = ESCAPED_CHARACTER.sub("", text)
    return "$" not in stripped and "`" not in stripped


def inline_here_documents(command: str) -> str:
    """Fold an unquoted here-document body back onto its own command line.

    The shell expands the body of a here-document whose delimiter is unquoted,
    so the body is input to the command that opened it. Folding it back keeps
    it in the same segment as that command; a quoted delimiter expands nothing
    and its body is dropped.
    """
    if "<<" not in command:
        return command
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        bodies: list[str] = []
        for match in HERE_DOCUMENT.finditer(line):
            delimiter = match.group("delimiter")
            body: list[str] = []
            while index < len(lines) and lines[index].strip() != delimiter:
                body.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            if not match.group("quote"):
                bodies.append(" ".join(body))
        kept.append(" ".join([line, *bodies]) if bodies else line)
    return "\n".join(kept)


def _brace_expansion(body: str) -> tuple[tuple[str, bool] | None, str]:
    """Classify one `${...}` expansion and return its operand for rescanning."""
    head = body
    if head[:1] == "!":
        # Indirect expansion names a second variable; the plan records it as
        # outside this rule, so the named variable is not treated as printed.
        return (None, "")
    if head[:1] == "#":
        head = head[1:]
    match = VARIABLE_NAME.match(head)
    if match is None:
        return (None, body)
    name = match.group(0)
    rest = head[match.end() :]
    if not rest:
        return ((name, True), "")
    operator = rest[:2] if rest[:2] in {":-", ":=", ":?", ":+"} else rest[:1]
    operand = rest[len(operator) :]
    if operator in {"+", ":+"}:
        return ((name, not is_fixed_literal(operand)), operand)
    return ((name, True), operand)


def variable_expansions(text: str) -> list[tuple[str, bool]]:
    """Report every parameter expansion in `text` and whether it discloses.

    A nested expansion is substituted in its own right, so operands are
    rescanned rather than skipped: `${OTHER:-${API_TOKEN}}` discloses. The
    traversal is iterative and bounded, because the gate must reach a decision
    for every command it is handed.
    """
    found: list[tuple[str, bool]] = []
    pending = [text]
    scanned = 0
    while pending:
        if len(pending) > SCAN_ITEM_LIMIT:
            raise ScanLimitReached("too many nested parameter expansions")
        current = pending.pop()
        scanned += len(current)
        if scanned > SCAN_CHARACTER_LIMIT:
            raise ScanLimitReached("parameter expansion text is too long to decide")
        index = 0
        length = len(current)
        while index < length:
            character = current[index]
            if character == "\\":
                index += 2
                continue
            if character != "$":
                index += 1
                continue
            if current[index + 1 : index + 2] == "{":
                depth = 1
                cursor = index + 2
                while cursor < length and depth:
                    if current[cursor] == "{":
                        depth += 1
                    elif current[cursor] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    cursor += 1
                expansion, operand = _brace_expansion(current[index + 2 : cursor])
                if expansion is not None:
                    found.append(expansion)
                if operand:
                    pending.append(operand)
                index = cursor + 1
                continue
            match = VARIABLE_NAME.match(current, index + 1)
            if match is None:
                index += 1
                continue
            found.append((match.group(0), True))
            index = match.end()
    return found


def command_segments(command: str) -> list[str]:
    """Split a command string on its unquoted separators.

    The split is approximate on purpose: it exists so that a display command
    later in a list is judged by its own arguments, which is what keeps the
    enumerated bracket presence test runnable. A `&` that belongs to a
    redirection such as `2>&1` is not a separator.
    """
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    length = len(command)
    while index < length:
        character = command[index]
        if character == "\\" and quote != "'":
            current.append(command[index : index + 2])
            index += 2
            continue
        if quote is not None:
            current.append(character)
            if character == quote:
                quote = None
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
            current.append(character)
            index += 1
            continue
        if character == "&" and (
            (current and current[-1] in {">", "<"}) or command[index + 1 : index + 2] == ">"
        ):
            current.append(character)
            index += 1
            continue
        if character in {";", "|", "&", "\n"}:
            segments.append("".join(current))
            current = []
            index += 1
            continue
        current.append(character)
        index += 1
    segments.append("".join(current))
    return [segment for segment in segments if segment.strip()]


def tokenize(segment: str) -> list[Token]:
    """Split one command segment into words, tracking what stays expandable.

    An unquoted word that starts with `#` begins a comment, and the shell
    expands nothing after it, so tokenizing stops there.
    """
    tokens: list[Token] = []
    word: list[str] = []
    expandable: list[str] = []
    started = False
    quote: str | None = None
    index = 0
    length = len(segment)

    def flush() -> None:
        nonlocal word, expandable, started
        if started:
            tokens.append(Token("".join(word), "".join(expandable)))
        word, expandable, started = [], [], False

    while index < length:
        character = segment[index]
        if quote != "'" and character == "\\" and index + 1 < length:
            started = True
            word.append(segment[index + 1])
            expandable.append(segment[index : index + 2])
            index += 2
            continue
        if quote is None and character in {" ", "\t"}:
            flush()
            index += 1
            continue
        if quote is None and character == "#" and not started:
            break
        if quote is None and character in {"'", '"'}:
            started = True
            quote = character
            index += 1
            continue
        if quote is not None and character == quote:
            quote = None
            index += 1
            continue
        started = True
        word.append(character)
        if quote != "'":
            expandable.append(character)
        index += 1
    flush()
    return tokens


def drop_redirections(tokens: list[Token]) -> list[Token]:
    """Remove redirection tokens and the targets they consume."""
    kept: list[Token] = []
    index = 0
    while index < len(tokens):
        text = tokens[index].word
        match = REDIRECTION.match(text)
        if match:
            index += 2 if match.end() == len(text) else 1
            continue
        kept.append(tokens[index])
        index += 1
    return kept


def _display_refusal(head: str, arguments: str, declared: object) -> str | None:
    for name, discloses in variable_expansions(arguments):
        if discloses and is_credential_name(name, declared):
            return f"{head} would print the value of {name}"
    return None


def _definition_print_refusal(head: str, operands: list[Token], declared: object) -> str | None:
    options = [token.word for token in operands if token.word.startswith("-")]
    names = [token.word.split("=", 1)[0] for token in operands if not token.word.startswith("-")]
    prints_variables = any(
        option.startswith("-")
        and not option.startswith("--")
        and "p" in option[1:]
        # `-f` restricts the listing to functions, which hold no variable value.
        and "f" not in option[1:]
        for option in options
    )
    if not prints_variables:
        return None
    if not names:
        return f"{head} -p with no name prints every variable definition"
    for name in names:
        if is_credential_name(name, declared):
            return f"{head} -p would print the definition of {name}"
    return None


def _head_refusal(head: str, tokens: list[Token], declared: object) -> str | None:
    if head in DISPLAY_COMMANDS:
        # Redirection words are scanned too: a here-string or a folded
        # here-document body carries the value into the command.
        return _display_refusal(head, " ".join(token.expandable for token in tokens), declared)
    remaining = drop_redirections(tokens)
    operands = [token for token in remaining if not token.word.startswith("-")]
    if head == "printenv":
        if not operands:
            return "printenv with no variable operand dumps every environment variable"
        for operand in operands:
            if is_credential_name(operand.word, declared):
                return f"printenv would print the value of {operand.word}"
        return None
    if head == "set" and not operands:
        return "set with no operand prints every variable definition"
    if head in DEFINITION_PRINT_COMMANDS:
        return _definition_print_refusal(head, remaining, declared)
    return None


def _carried_command(tokens: list[Token], index: int) -> str:
    """Return the whole command an `env` split-string option carries."""
    option = tokens[index].word
    carried = ""
    following = index + 1
    if "=" in option:
        carried = option.split("=", 1)[1]
    else:
        for prefix in ENV_COMMAND_OPTIONS:
            if option.startswith(prefix) and len(option) > len(prefix):
                carried = option[len(prefix) :]
                break
        else:
            if following < len(tokens):
                carried = tokens[following].word
                following += 1
    # Arguments after the carried string are appended to it by env, so they
    # belong to the same command and must be judged with it.
    return " ".join([carried, *(token.word for token in tokens[following:])]).strip()


def _segment_refusal(segment: str, declared: object, depth: int = 0) -> str | None:
    if depth > SEGMENT_DEPTH_LIMIT:
        raise ScanLimitReached("command wrappers nest too deeply to decide")
    tokens = tokenize(segment)
    index = 0
    while index < len(tokens):
        text = tokens[index].word
        if text in CONTROL_WORDS or ASSIGNMENT.fullmatch(text):
            index += 1
            continue
        redirection = REDIRECTION.match(text)
        if redirection:
            index += 2 if redirection.end() == len(text) else 1
            continue
        head = text.rsplit("/", 1)[-1]
        if head in TRANSPARENT_PREFIXES:
            consuming = PREFIX_OPTIONS_WITH_ARGUMENT.get(head, frozenset())
            index += 1
            while index < len(tokens) and tokens[index].word.startswith("-"):
                option = tokens[index].word
                if option in INSPECTION_OPTIONS:
                    return None
                if option == "--":
                    index += 1
                    break
                index += 2 if option in consuming else 1
            continue
        if head == "env":
            index += 1
            while index < len(tokens):
                option = tokens[index].word
                if ASSIGNMENT.fullmatch(option):
                    index += 1
                    continue
                if not option.startswith("-"):
                    break
                if option in INSPECTION_OPTIONS:
                    return None
                if option.startswith(ENV_COMMAND_OPTIONS):
                    # The option carries the command, and env substitutes
                    # variables inside it, so judge the carried text itself.
                    return _segment_refusal(_carried_command(tokens, index), declared, depth + 1)
                if option == "--":
                    index += 1
                    break
                index += 2 if option in ENV_OPTIONS_WITH_ARGUMENT else 1
            if index >= len(tokens):
                return "env with no command dumps every environment variable"
            continue
        # The whole segment is scanned for expansions, not only what follows
        # the head, because a leading redirection also feeds the command.
        return _head_refusal(head, tokens[:index] + tokens[index + 1 :], declared)
    return None


def credential_display_refusal(command: str, declared: object = frozenset()) -> str | None:
    """Report why this command would disclose a credential, if it would.

    Only the enumerated command heads and expansion shapes are decided here.
    This is not a sandbox: command substitution, indirect expansion, eval,
    language-runtime reads, shell tracing and encoded disclosure stay outside
    the list.
    """
    if len(command) > SCAN_CHARACTER_LIMIT:
        return "this command is too long for the credential rule to decide"
    # The shell removes a line continuation before it recognizes a command
    # name or a variable name, so the scanner must see the joined text.
    joined = LINE_CONTINUATION.sub("", inline_here_documents(command))
    try:
        for segment in command_segments(joined):
            reason = _segment_refusal(segment, declared)
            if reason is not None:
                return reason
    except ScanLimitReached as limit:
        return f"{limit}"
    return None


class DeclaredCredentialNames:
    """Policy-declared names, read the first time one is actually consulted.

    The gate runs on every tool call, and loading the shipped policy reader
    costs several milliseconds, so the read is deferred until a name the
    segment rules did not already settle reaches the membership test.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._names: frozenset[str] | None = None

    def resolved(self) -> frozenset[str]:
        if self._names is None:
            self._names = declared_credential_names(self._root)
        return self._names

    def __contains__(self, name: object) -> bool:
        return name in self.resolved()

    def __iter__(self):
        return iter(self.resolved())


def _policy_reader():
    """Load the shipped PyYAML-free external-service policy reader."""
    import importlib.util

    path = Path(__file__).resolve().parent / "check-external-service-policy.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("external_service_policy_reader", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declared_credential_names(root: Path) -> frozenset[str]:
    """Credential variable names the repository's service policy declares.

    Schema version 1 names a credential variable per service. Version 2 names
    none, so it contributes nothing until a later schema adds the field. A
    missing, unreadable or unsupported policy contributes no names, because
    failing closed here would refuse unrelated commands in every project that
    carries no policy.
    """
    root = Path(root)
    if root in _DECLARED_CACHE:
        return _DECLARED_CACHE[root]
    names: set[str] = set()
    path = root / POLICY_RELATIVE
    try:
        reader = _policy_reader()
        if reader is not None and path.is_file() and reader.policy_version(path) == 1:
            services = reader.load_v1_services(path)
            # A structurally readable but semantically invalid policy is
            # malformed, so it must contribute nothing rather than let an
            # unvalidated field change a gate decision.
            for name, service in services.items():
                reader.validate_v1_service(name, service)
            for service in services.values():
                if service.get("authentication") != "environment":
                    continue
                reference = service.get("credential_reference")
                if isinstance(reference, str) and reader.ENVIRONMENT_REFERENCE.fullmatch(reference):
                    names.add(reference)
    except Exception:
        names = set()
    result = frozenset(names)
    _DECLARED_CACHE[root] = result
    return result
