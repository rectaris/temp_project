#!/usr/bin/env python3
"""Parse the bounded shell structure used by the Copier fixture validator."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
from types import MappingProxyType
from typing import Iterable, Mapping, Pattern, Sequence


MAX_SOURCE_BYTES = 1_048_576
_FUNCTION_OPEN = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)\s*\{\s*$"
)
_FUNCTION_SIGNATURE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)\s*$"
)
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.DOTALL)
_TRANSFER_WORDS = frozenset({"break", "continue", "exec", "exit", "return"})
_SKIPPING_ENCLOSURES = frozenset(
    {"and_or", "case", "if", "loop", "subshell"}
)


class ShellStructureError(ValueError):
    """Raised when supplied shell text is outside the accepted subset."""


@dataclass(frozen=True)
class ShellCommand:
    text: str
    start_line: int
    end_line: int
    enclosures: tuple[str, ...]

    @property
    def is_unconditionally_reachable(self) -> bool:
        return not _SKIPPING_ENCLOSURES.intersection(self.enclosures)


@dataclass(frozen=True)
class ShellRegion:
    commands: tuple[ShellCommand, ...]

    @property
    def reachable_commands(self) -> tuple[ShellCommand, ...]:
        return tuple(
            command
            for command in self.commands
            if command.is_unconditionally_reachable
        )

    def require_reachable_sequence(
        self,
        patterns: Sequence[str | Pattern[str]],
    ) -> tuple[ShellCommand, ...]:
        """Return unique reachable matches in order, or fail closed."""

        compiled = tuple(
            re.compile(pattern) if isinstance(pattern, str) else pattern
            for pattern in patterns
        )
        matches: list[ShellCommand] = []
        previous_index = -1
        reachable = self.reachable_commands
        for pattern in compiled:
            candidates = [
                (index, command)
                for index, command in enumerate(reachable)
                if pattern.search(command.text)
            ]
            all_candidates = [
                command for command in self.commands if pattern.search(command.text)
            ]
            if not candidates:
                if all_candidates:
                    raise ShellStructureError(
                        f"required command is enclosed by skippable control flow: "
                        f"{pattern.pattern}"
                    )
                raise ShellStructureError(
                    f"required command is missing: {pattern.pattern}"
                )
            if len(candidates) != 1 or len(all_candidates) != 1:
                raise ShellStructureError(
                    f"required command is not unique: {pattern.pattern}"
                )
            index, command = candidates[0]
            if index <= previous_index:
                raise ShellStructureError(
                    f"required command is out of order: {pattern.pattern}"
                )
            previous_index = index
            matches.append(command)
        return tuple(matches)


@dataclass(frozen=True)
class ShellFunction:
    name: str
    start_line: int
    end_line: int
    body: ShellRegion


@dataclass(frozen=True)
class ShellStructure:
    functions: Mapping[str, ShellFunction]
    top_level: ShellRegion


@dataclass
class _Frame:
    kind: str
    start_line: int
    name: str | None = None
    commands: list[ShellCommand] | None = None
    phase: str | None = None


@dataclass(frozen=True)
class _LogicalLine:
    text: str
    start_line: int
    end_line: int


def _decode_source(source: str | bytes) -> str:
    if isinstance(source, bytes):
        if len(source) > MAX_SOURCE_BYTES:
            raise ShellStructureError("shell source exceeds the bounded size")
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ShellStructureError("shell source is not valid UTF-8") from exc
    else:
        text = source
        if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ShellStructureError("shell source exceeds the bounded size")
    if "\0" in text:
        raise ShellStructureError("shell source contains a NUL byte")
    return text


def _starts_comment(text: str, index: int) -> bool:
    return index == 0 or text[index - 1].isspace() or text[index - 1] in ";&|()<>"


def _continues_line(line: str) -> bool:
    if not line.endswith("\\"):
        return False
    quote: str | None = None
    escaped = False
    backtick = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif backtick:
            if char == "`":
                backtick = False
        elif char in {"'", '"'}:
            quote = char
        elif char == "`":
            backtick = True
        elif char == "#" and _starts_comment(line, index):
            return False
    return escaped


def _heredoc_markers(text: str) -> tuple[tuple[str, bool], ...]:
    markers: list[tuple[str, bool]] = []
    quote: str | None = None
    escaped = False
    backtick = False
    index = 0
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif backtick:
            if char == "`":
                backtick = False
        elif char in {"'", '"'}:
            quote = char
        elif char == "`":
            backtick = True
        elif char == "#" and _starts_comment(text, index):
            break
        elif text.startswith("<<", index) and not text.startswith("<<<", index):
            cursor = index + 2
            strip_tabs = cursor < len(text) and text[cursor] == "-"
            if strip_tabs:
                cursor += 1
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text):
                raise ShellStructureError("here-document operator has no delimiter")
            delimiter_quote = text[cursor] if text[cursor] in {"'", '"'} else None
            if delimiter_quote:
                cursor += 1
                end = text.find(delimiter_quote, cursor)
                if end < 0:
                    raise ShellStructureError(
                        "here-document delimiter has an unterminated quote"
                    )
                marker = text[cursor:end]
                cursor = end + 1
            else:
                start = cursor
                while (
                    cursor < len(text)
                    and not text[cursor].isspace()
                    and text[cursor] not in ";&|<>()"
                ):
                    cursor += 1
                word = text[start:cursor]
                if any(char in word for char in {"'", '"', "`"}):
                    raise ShellStructureError(
                        "unsupported quoted here-document delimiter"
                    )
                try:
                    parsed_word = shlex.split(word, comments=False, posix=True)
                except ValueError as exc:
                    raise ShellStructureError(
                        "here-document delimiter is invalid"
                    ) from exc
                marker = parsed_word[0] if len(parsed_word) == 1 else ""
            if not marker:
                raise ShellStructureError("here-document delimiter is invalid")
            markers.append((marker, strip_tabs))
            index = cursor - 1
        index += 1
    return tuple(markers)


def _split_and_or(text: str) -> tuple[tuple[str, bool], ...]:
    parts: list[tuple[str, bool]] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    backtick = False
    substitution_depth = 0
    parameter_depth = 0
    conditional = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\" and quote != "'":
            current.append(char)
            escaped = True
        elif quote:
            current.append(char)
            if char == quote:
                quote = None
        elif backtick:
            current.append(char)
            if char == "`":
                backtick = False
        elif char in {"'", '"'}:
            current.append(char)
            quote = char
        elif char == "`":
            current.append(char)
            backtick = True
        elif char == "$" and next_char == "(":
            current.extend((char, next_char))
            substitution_depth += 1
            index += 1
        elif char == "$" and next_char == "{":
            current.extend((char, next_char))
            parameter_depth += 1
            index += 1
        elif char == ")" and substitution_depth:
            current.append(char)
            substitution_depth -= 1
        elif char == "}" and parameter_depth:
            current.append(char)
            parameter_depth -= 1
        elif (
            char + next_char in {"&&", "||"}
            and not substitution_depth
            and not parameter_depth
        ):
            part = "".join(current).strip()
            if not part:
                raise ShellStructureError("AND/OR list has an empty command")
            parts.append((part, conditional))
            current = []
            conditional = True
            index += 1
        else:
            current.append(char)
        index += 1
    part = "".join(current).strip()
    if not part:
        raise ShellStructureError("AND/OR list has an empty command")
    parts.append((part, conditional))
    return tuple(parts)


def _is_control_transfer(text: str) -> bool:
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars="<>")
        lexer.commenters = ""
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError as exc:
        raise ShellStructureError(f"invalid shell command: {text}") from exc
    index = 0
    while index < len(words):
        if (
            words[index].isdigit()
            and index + 2 < len(words)
            and set(words[index + 1]) <= {"<", ">", "&", "|"}
        ):
            index += 3
        elif set(words[index]) <= {"<", ">", "&", "|"} and set(words[index]):
            if index + 1 >= len(words):
                raise ShellStructureError(f"redirection has no target: {text}")
            index += 2
        else:
            break
    while index < len(words) and _ASSIGNMENT.fullmatch(words[index]):
        index += 1
    while index < len(words) and words[index] in {"!", "command"}:
        index += 1
    return index < len(words) and words[index] in _TRANSFER_WORDS


def _logical_lines(text: str) -> Iterable[_LogicalLine]:
    physical = text.splitlines()
    index = 0
    while index < len(physical):
        start = index + 1
        parts = [physical[index]]
        while _continues_line(parts[-1]):
            index += 1
            if index >= len(physical):
                raise ShellStructureError(
                    f"unterminated line continuation at line {start}"
                )
            parts[-1] = parts[-1][:-1]
            parts.append(physical[index])
        logical = "".join(parts)
        end = index + 1
        yield _LogicalLine(logical, start, end)
        for marker, strip_tabs in _heredoc_markers(logical):
            found = False
            while index + 1 < len(physical):
                index += 1
                candidate = physical[index].lstrip("\t") if strip_tabs else physical[index]
                if candidate == marker:
                    found = True
                    break
            if not found:
                raise ShellStructureError(
                    f"unterminated here-document declared at line {start}"
                )
        index += 1


def _split_clauses(line: _LogicalLine) -> tuple[str, ...]:
    clauses: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    backtick = False
    substitution_depth = 0
    parameter_depth = 0
    index = 0
    text = line.text
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\" and quote != "'":
            current.append(char)
            escaped = True
        elif quote:
            current.append(char)
            if char == quote:
                quote = None
        elif backtick:
            current.append(char)
            if char == "`":
                backtick = False
        elif char in {"'", '"'}:
            current.append(char)
            quote = char
        elif char == "`":
            current.append(char)
            backtick = True
        elif char == "$" and next_char == "(":
            current.extend((char, next_char))
            substitution_depth += 1
            index += 1
        elif char == "$" and next_char == "{":
            current.extend((char, next_char))
            parameter_depth += 1
            index += 1
        elif char == ")" and substitution_depth:
            current.append(char)
            substitution_depth -= 1
        elif char == "}" and parameter_depth:
            current.append(char)
            parameter_depth -= 1
        elif (
            char == "#"
            and not substitution_depth
            and not parameter_depth
            and (not current or current[-1].isspace())
        ):
            break
        elif char == ";" and not substitution_depth and not parameter_depth:
            if next_char == ";":
                if "".join(current).strip():
                    clauses.append("".join(current).strip())
                clauses.append(";;")
                current = []
                index += 1
            else:
                if "".join(current).strip():
                    clauses.append("".join(current).strip())
                current = []
        else:
            current.append(char)
        index += 1
    if quote or backtick or substitution_depth or parameter_depth:
        raise ShellStructureError(f"unterminated shell token at line {line.start_line}")
    if "".join(current).strip():
        clauses.append("".join(current).strip())
    return tuple(clauses)


def _current_function(frames: Sequence[_Frame]) -> _Frame | None:
    for frame in reversed(frames):
        if frame.kind == "function":
            return frame
    return None


def _enclosures(frames: Sequence[_Frame]) -> tuple[str, ...]:
    return tuple(frame.kind for frame in frames if frame.kind != "function")


def _close_frame(
    frames: list[_Frame],
    expected: str,
    line: _LogicalLine,
) -> _Frame:
    if not frames or frames[-1].kind != expected:
        raise ShellStructureError(
            f"unmatched {expected} terminator at line {line.start_line}"
        )
    return frames.pop()


def parse_shell_structure(source: str | bytes) -> ShellStructure:
    """Parse supplied shell bytes without executing or importing them."""

    text = _decode_source(source)
    functions: dict[str, ShellFunction] = {}
    top_level_commands: list[ShellCommand] = []
    frames: list[_Frame] = []
    terminated_regions: dict[str, int] = {}
    pending_function: tuple[str, int] | None = None

    def add_command(clause: str, logical: _LogicalLine) -> None:
        function = _current_function(frames)
        region_name = function.name if function is not None else "<top-level>"
        base_enclosures = _enclosures(frames)
        base_reachable = not _SKIPPING_ENCLOSURES.intersection(base_enclosures)
        for text_part, conditional in _split_and_or(clause):
            enclosures = base_enclosures + (("and_or",) if conditional else ())
            command = ShellCommand(
                text=text_part,
                start_line=logical.start_line,
                end_line=logical.end_line,
                enclosures=enclosures,
            )
            if base_reachable and region_name in terminated_regions:
                raise ShellStructureError(
                    f"command at line {logical.start_line} follows control "
                    f"transfer at line {terminated_regions[region_name]}"
                )
            if function is None:
                top_level_commands.append(command)
            else:
                assert function.commands is not None
                function.commands.append(command)
            if base_reachable and _is_control_transfer(text_part):
                terminated_regions[region_name] = logical.start_line

    for logical in _logical_lines(text):
        for clause in _split_clauses(logical):
            if not clause:
                continue

            if pending_function is not None:
                name, start_line = pending_function
                if clause != "{":
                    raise ShellStructureError(
                        f"function signature {name!r} at line {start_line} is "
                        f"not followed by an opening brace"
                    )
                if frames:
                    raise ShellStructureError(
                        f"nested function definition {name!r} at line {start_line}"
                    )
                if name in functions:
                    raise ShellStructureError(
                        f"duplicate function definition {name!r} at line {start_line}"
                    )
                frames.append(
                    _Frame("function", start_line, name=name, commands=[])
                )
                pending_function = None
                continue

            function_match = _FUNCTION_OPEN.fullmatch(clause)
            if function_match:
                name = function_match.group("name")
                if frames:
                    raise ShellStructureError(
                        f"nested function definition {name!r} at line "
                        f"{logical.start_line}"
                    )
                if name in functions:
                    raise ShellStructureError(
                        f"duplicate function definition {name!r} at line "
                        f"{logical.start_line}"
                    )
                frames.append(
                    _Frame("function", logical.start_line, name=name, commands=[])
                )
                continue

            signature_match = _FUNCTION_SIGNATURE.fullmatch(clause)
            if signature_match:
                pending_function = (
                    signature_match.group("name"),
                    logical.start_line,
                )
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)", clause):
                raise ShellStructureError(
                    f"unsupported function definition at line {logical.start_line}"
                )

            first = clause.split(None, 1)[0]
            if first == "if":
                condition = clause[len(first) :].strip()
                if not condition:
                    raise ShellStructureError(
                        f"if has no condition at line {logical.start_line}"
                    )
                add_command(condition, logical)
                frames.append(_Frame("if", logical.start_line, phase="await_then"))
                continue
            if first in {"while", "until"}:
                condition = clause[len(first) :].strip()
                if not condition:
                    raise ShellStructureError(
                        f"{first} has no condition at line {logical.start_line}"
                    )
                add_command(condition, logical)
                frames.append(_Frame("loop", logical.start_line, phase="await_do"))
                continue
            if first in {"for", "select"}:
                frames.append(_Frame("loop", logical.start_line, phase="await_do"))
                continue
            if first == "case":
                frames.append(_Frame("case", logical.start_line))
                continue
            if clause == "(":
                frames.append(_Frame("subshell", logical.start_line))
                continue
            if clause == "{":
                frames.append(_Frame("group", logical.start_line))
                continue
            if clause == "then":
                if (
                    not frames
                    or frames[-1].kind != "if"
                    or frames[-1].phase != "await_then"
                ):
                    raise ShellStructureError(
                        f"unmatched then at line {logical.start_line}"
                    )
                frames[-1].phase = "body"
                continue
            if clause == "do":
                if (
                    not frames
                    or frames[-1].kind != "loop"
                    or frames[-1].phase != "await_do"
                ):
                    raise ShellStructureError(
                        f"unmatched do at line {logical.start_line}"
                    )
                frames[-1].phase = "body"
                continue
            if first == "elif":
                if not frames or frames[-1].kind != "if":
                    raise ShellStructureError(
                        f"unmatched {first} at line {logical.start_line}"
                    )
                if frames[-1].phase != "body":
                    raise ShellStructureError(
                        f"invalid elif at line {logical.start_line}"
                    )
                condition = clause[len(first) :].strip()
                if not condition:
                    raise ShellStructureError(
                        f"elif has no condition at line {logical.start_line}"
                    )
                frames[-1].phase = "await_then"
                add_command(condition, logical)
                continue
            if clause == "else":
                if not frames or frames[-1].kind != "if":
                    raise ShellStructureError(
                        f"unmatched {first} at line {logical.start_line}"
                    )
                if frames[-1].phase != "body":
                    raise ShellStructureError(
                        f"invalid else at line {logical.start_line}"
                    )
                frames[-1].phase = "else"
                continue
            if clause == ";;":
                if not frames or frames[-1].kind != "case":
                    raise ShellStructureError(
                        f"unmatched case terminator at line {logical.start_line}"
                    )
                continue
            if clause == "fi":
                if not frames or frames[-1].kind != "if":
                    raise ShellStructureError(
                        f"unmatched if terminator at line {logical.start_line}"
                    )
                if frames[-1].phase not in {"body", "else"}:
                    raise ShellStructureError(
                        f"incomplete if block at line {logical.start_line}"
                    )
                _close_frame(frames, "if", logical)
                continue
            if clause == "done":
                if not frames or frames[-1].kind != "loop":
                    raise ShellStructureError(
                        f"unmatched loop terminator at line {logical.start_line}"
                    )
                if frames[-1].phase != "body":
                    raise ShellStructureError(
                        f"incomplete loop block at line {logical.start_line}"
                    )
                _close_frame(frames, "loop", logical)
                continue
            if clause == "esac":
                _close_frame(frames, "case", logical)
                continue
            if first in {"do", "done", "else", "esac", "fi", "then"}:
                raise ShellStructureError(
                    f"unsupported reserved-word clause at line {logical.start_line}"
                )
            if clause == ")":
                _close_frame(frames, "subshell", logical)
                continue
            closing_brace = re.fullmatch(r"}(?P<pipeline>\s*\|(?!=).*)?", clause)
            if closing_brace:
                if not frames:
                    raise ShellStructureError(
                        f"unmatched closing brace at line {logical.start_line}"
                    )
                frame = frames[-1]
                if frame.kind == "group":
                    frames.pop()
                    pipeline = closing_brace.group("pipeline")
                    if pipeline:
                        add_command(pipeline.lstrip()[1:].strip(), logical)
                    continue
                if frame.kind != "function":
                    raise ShellStructureError(
                        f"closing brace crosses {frame.kind} block at line "
                        f"{logical.start_line}"
                    )
                if closing_brace.group("pipeline"):
                    raise ShellStructureError(
                        f"function definition is piped at line {logical.start_line}"
                    )
                frames.pop()
                assert frame.name is not None
                assert frame.commands is not None
                functions[frame.name] = ShellFunction(
                    name=frame.name,
                    start_line=frame.start_line,
                    end_line=logical.end_line,
                    body=ShellRegion(tuple(frame.commands)),
                )
                continue

            add_command(clause, logical)

    if frames:
        frame = frames[-1]
        description = frame.name if frame.kind == "function" else frame.kind
        raise ShellStructureError(
            f"unterminated {description!r} block opened at line {frame.start_line}"
        )
    if pending_function is not None:
        name, start_line = pending_function
        raise ShellStructureError(
            f"function signature {name!r} at line {start_line} has no body"
        )
    if not top_level_commands:
        raise ShellStructureError("shell source has no top-level execution sequence")

    return ShellStructure(
        functions=MappingProxyType(functions),
        top_level=ShellRegion(tuple(top_level_commands)),
    )


__all__ = [
    "ShellCommand",
    "ShellFunction",
    "ShellRegion",
    "ShellStructure",
    "ShellStructureError",
    "parse_shell_structure",
]
