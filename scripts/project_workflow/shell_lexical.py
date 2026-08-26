"""Bounded lexical projection of supplied shell bytes.

The projection turns supplied shell text into deterministic lexical records
without executing, sourcing, or importing the supplied script. Every region
that a shell would execute is exposed as an explicit record, and every
construct outside the accepted subset is rejected instead of being projected
partially.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Iterator


__all__ = [
    "ARITHMETIC_EXPANSION",
    "COMMAND_SUBSTITUTION",
    "COMMENT",
    "CONTINUATION",
    "DOUBLE_QUOTED",
    "ESCAPE",
    "HEREDOC_BODY",
    "IO_NUMBER",
    "LINE_CONTINUATION",
    "LITERAL",
    "NEWLINE",
    "OPERATOR",
    "PARAMETER_EXPANSION",
    "Position",
    "Segment",
    "ShellLexicalError",
    "SINGLE_QUOTED",
    "Token",
    "WORD",
    "LexicalProjection",
    "executable_regions",
    "project",
]


WORD = "word"
OPERATOR = "operator"
IO_NUMBER = "io_number"
NEWLINE = "newline"
COMMENT = "comment"
HEREDOC_BODY = "heredoc_body"
LINE_CONTINUATION = "line_continuation"

LITERAL = "literal"
ESCAPE = "escape"
CONTINUATION = "continuation"
SINGLE_QUOTED = "single_quoted"
DOUBLE_QUOTED = "double_quoted"
PARAMETER_EXPANSION = "parameter_expansion"
COMMAND_SUBSTITUTION = "command_substitution"
ARITHMETIC_EXPANSION = "arithmetic_expansion"

DETERMINATE_SEGMENTS = frozenset({LITERAL, ESCAPE, CONTINUATION, SINGLE_QUOTED})

BLANKS = " \t"
OPERATOR_START = "&|;<>()"
NAME_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
NAME_CHARACTERS = NAME_START + "0123456789"
SPECIAL_PARAMETERS = "@*#?-$!0123456789"

REDIRECTION_OPERATORS = ("<<-", "<<", ">>", "<&", ">&", "<>", ">|", "<", ">")
CONTROL_OPERATORS = ("&&", "||", ";;", "|", "&", ";", "(", ")")
OPERATORS = tuple(
    sorted(REDIRECTION_OPERATORS + CONTROL_OPERATORS, key=len, reverse=True)
)

REJECTED_SEQUENCES = (
    (";;&", "case fall-through operator"),
    ("&>>", "appending redirection of both streams"),
    ("<<<", "here-string"),
    ("&>", "redirection of both streams"),
    ("|&", "pipeline of both streams"),
    (";&", "case fall-through operator"),
    ("((", "arithmetic command"),
    ("<(", "process substitution"),
    (">(", "process substitution"),
)


def _ends_with_continuation(line: str) -> bool:
    """Report whether a physical line ends with an unescaped backslash."""

    return (len(line) - len(line.rstrip("\\"))) % 2 == 1


def _contains_literal_brace(segment: Segment) -> bool:
    """Report whether a quoted or escaped part hides a literal closing brace."""

    if segment.kind in (SINGLE_QUOTED, ESCAPE) and "}" in (segment.value or ""):
        return True
    return any(_contains_literal_brace(part) for part in segment.segments)


class ShellLexicalError(ValueError):
    """Raised when supplied shell bytes leave the accepted lexical subset."""

    def __init__(self, message: str, position: "Position | None" = None) -> None:
        self.position = position
        if position is None:
            super().__init__(message)
        else:
            super().__init__(f"line {position.line} column {position.column}: {message}")


@dataclass(frozen=True)
class Position:
    """Exact source location of a projected record boundary."""

    offset: int
    line: int
    column: int


@dataclass(frozen=True)
class Segment:
    """One lexical part of a word, here-document body, or quoted region."""

    kind: str
    text: str
    start: Position
    end: Position
    value: str | None = None
    segments: tuple["Segment", ...] = ()
    tokens: tuple["Token", ...] = ()

    @property
    def is_determinate(self) -> bool:
        """Report whether the segment resolves without expansion."""

        if self.kind in DETERMINATE_SEGMENTS:
            return True
        if self.kind == DOUBLE_QUOTED:
            return all(part.is_determinate for part in self.segments)
        return False

    @property
    def literal_value(self) -> str | None:
        """Return the expansion-free text of the segment when it exists."""

        if not self.is_determinate:
            return None
        if self.kind == DOUBLE_QUOTED:
            return "".join(part.literal_value or "" for part in self.segments)
        return self.value or ""


@dataclass(frozen=True)
class Token:
    """One deterministic lexical record of the supplied shell text."""

    kind: str
    text: str
    start: Position
    end: Position
    segments: tuple[Segment, ...] = ()
    delimiter: str | None = None
    quoted_delimiter: bool = False
    strip_tabs: bool = False

    @property
    def is_word(self) -> bool:
        """Report whether the record is a word record."""

        return self.kind == WORD

    @property
    def literal_value(self) -> str | None:
        """Return the expansion-free word text when the word has one."""

        if not self.segments:
            return None
        if not all(segment.is_determinate for segment in self.segments):
            return None
        return "".join(segment.literal_value or "" for segment in self.segments)

    @property
    def content(self) -> str:
        """Return here-document body text with `<<-` tab stripping applied."""

        if self.kind != HEREDOC_BODY or not self.strip_tabs:
            return self.text
        return "".join(line.lstrip("\t") for line in self.text.splitlines(keepends=True))


@dataclass(frozen=True)
class LexicalProjection:
    """The complete lexical record projection of supplied shell text."""

    source: str
    tokens: tuple[Token, ...] = field(default_factory=tuple)

    def __iter__(self) -> Iterator[Token]:
        return iter(self.tokens)

    def __len__(self) -> int:
        return len(self.tokens)


def executable_regions(
    records: LexicalProjection | tuple[Token, ...],
) -> Iterator[tuple[Token, ...]]:
    """Yield every nested record sequence that the shell would execute."""

    tokens = records.tokens if isinstance(records, LexicalProjection) else records
    for token in tokens:
        yield from _segment_regions(token.segments)


def _segment_regions(segments: tuple[Segment, ...]) -> Iterator[tuple[Token, ...]]:
    for segment in segments:
        if segment.kind == COMMAND_SUBSTITUTION:
            yield segment.tokens
            yield from executable_regions(segment.tokens)
        yield from _segment_regions(segment.segments)


def project(source: str | bytes) -> LexicalProjection:
    """Project supplied shell bytes into deterministic lexical records."""

    if isinstance(source, (bytes, bytearray)):
        try:
            text = bytes(source).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ShellLexicalError(
                f"supplied bytes are not valid UTF-8 at offset {error.start}"
            ) from error
    elif isinstance(source, str):
        text = source
    else:
        raise ShellLexicalError("supplied source must be str or bytes")
    nul = text.find("\0")
    if nul != -1:
        raise ShellLexicalError(f"supplied bytes contain NUL at offset {nul}")
    scanner = _Scanner(text)
    tokens = scanner.run(nested=False)
    return LexicalProjection(source=text, tokens=tuple(tokens))


class _PendingHereDocument:
    __slots__ = ("delimiter", "quoted", "strip_tabs")

    def __init__(self, delimiter: str, quoted: bool, strip_tabs: bool) -> None:
        self.delimiter = delimiter
        self.quoted = quoted
        self.strip_tabs = strip_tabs


class _Scanner:
    """Single-pass scanner over supplied shell text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.limit = len(text)
        self.line_starts = [0]
        for index, character in enumerate(text):
            if character == "\n":
                self.line_starts.append(index + 1)

    def position(self, offset: int) -> Position:
        line = bisect.bisect_right(self.line_starts, offset)
        return Position(
            offset=offset,
            line=line,
            column=offset - self.line_starts[line - 1] + 1,
        )

    def fail(self, message: str, offset: int | None = None) -> ShellLexicalError:
        return ShellLexicalError(
            message, self.position(self.pos if offset is None else offset)
        )

    def token(
        self,
        kind: str,
        start: int,
        end: int,
        segments: tuple[Segment, ...] = (),
        **extra: object,
    ) -> Token:
        return Token(
            kind=kind,
            text=self.text[start:end],
            start=self.position(start),
            end=self.position(end),
            segments=segments,
            **extra,  # type: ignore[arg-type]
        )

    def run(self, *, nested: bool) -> list[Token]:
        tokens: list[Token] = []
        pending: list[_PendingHereDocument] = []
        expect_delimiter: tuple[bool, int] | None = None
        paren_depth = 0
        while self.pos < self.limit:
            character = self.text[self.pos]
            if character == "\n":
                if expect_delimiter is not None:
                    raise self.fail("here-document operator lacks a delimiter word")
                start = self.pos
                self.pos += 1
                tokens.append(self.token(NEWLINE, start, self.pos))
                if pending:
                    tokens.extend(self.consume_here_documents(pending))
                    pending = []
                continue
            if character in BLANKS:
                self.pos += 1
                continue
            if character == "\\" and self.peek(1) == "\n":
                start = self.pos
                self.pos += 2
                tokens.append(self.token(LINE_CONTINUATION, start, self.pos))
                continue
            if character == "#":
                if expect_delimiter is not None:
                    raise self.fail("here-document operator lacks a delimiter word")
                start = self.pos
                end = self.text.find("\n", self.pos, self.limit)
                self.pos = self.limit if end == -1 else end
                tokens.append(self.token(COMMENT, start, self.pos))
                continue
            self.reject_unsupported_sequence()
            if nested and character == ")" and paren_depth == 0:
                if expect_delimiter is not None:
                    raise self.fail("here-document operator lacks a delimiter word")
                if pending:
                    raise self.fail("here-document body is not terminated")
                return tokens
            operator = self.match_operator()
            if operator is not None:
                if expect_delimiter is not None:
                    raise self.fail("here-document operator lacks a delimiter word")
                start = self.pos
                self.pos += len(operator)
                tokens.append(self.token(OPERATOR, start, self.pos))
                if operator == "(":
                    paren_depth += 1
                elif operator == ")":
                    paren_depth -= 1
                if operator in ("<<", "<<-"):
                    expect_delimiter = (operator == "<<-", start)
                continue
            io_number = self.match_io_number()
            if io_number is not None:
                if expect_delimiter is not None:
                    raise self.fail("here-document operator lacks a delimiter word")
                tokens.append(io_number)
                continue
            word = self.scan_word()
            tokens.append(word)
            if expect_delimiter is not None:
                strip_tabs, operator_offset = expect_delimiter
                pending.append(self.here_document_delimiter(word, strip_tabs, operator_offset))
                expect_delimiter = None
        if expect_delimiter is not None:
            raise self.fail("here-document operator lacks a delimiter word")
        if nested:
            raise self.fail("command substitution is not terminated")
        if pending:
            raise self.fail("here-document body is not terminated")
        return tokens

    def peek(self, ahead: int = 0) -> str:
        index = self.pos + ahead
        return self.text[index] if index < self.limit else ""

    def reject_unsupported_sequence(self) -> None:
        for sequence, description in REJECTED_SEQUENCES:
            if self.text.startswith(sequence, self.pos) and self.pos + len(sequence) <= self.limit:
                raise self.fail(f"unsupported {description} `{sequence}`")

    def reject_process_substitution(self) -> None:
        for sequence in ("<(", ">("):
            if self.text.startswith(sequence, self.pos) and self.pos + 2 <= self.limit:
                raise self.fail(f"unsupported process substitution `{sequence}`")

    def match_operator(self) -> str | None:
        for operator in OPERATORS:
            if self.text.startswith(operator, self.pos) and self.pos + len(operator) <= self.limit:
                return operator
        return None

    def match_io_number(self) -> Token | None:
        cursor = self.pos
        while cursor < self.limit and self.text[cursor].isdigit():
            cursor += 1
        if cursor == self.pos or cursor >= self.limit:
            return None
        if self.text[cursor] not in "<>":
            return None
        start = self.pos
        self.pos = cursor
        return self.token(IO_NUMBER, start, cursor)

    def here_document_delimiter(
        self, word: Token, strip_tabs: bool, operator_offset: int
    ) -> _PendingHereDocument:
        delimiter = word.literal_value
        if delimiter is None:
            raise self.fail(
                "here-document delimiter must not use expansion", word.start.offset
            )
        if not delimiter:
            raise self.fail("here-document delimiter must not be empty", word.start.offset)
        if any(segment.kind == CONTINUATION for segment in word.segments):
            raise self.fail(
                "here-document delimiter must not use a line continuation",
                word.start.offset,
            )
        quoted = any(segment.kind != LITERAL for segment in word.segments)
        del operator_offset
        return _PendingHereDocument(delimiter, quoted, strip_tabs)

    def consume_here_documents(
        self, pending: list[_PendingHereDocument]
    ) -> list[Token]:
        tokens: list[Token] = []
        for entry in pending:
            body_start = self.pos
            body_end = None
            cursor = self.pos
            accumulated = ""
            while cursor < self.limit:
                line_end = self.text.find("\n", cursor, self.limit)
                stop = self.limit if line_end == -1 else line_end
                line = self.text[cursor:stop]
                candidate = line.lstrip("\t") if entry.strip_tabs else line
                continued = not entry.quoted and _ends_with_continuation(line)
                if accumulated:
                    if candidate == entry.delimiter:
                        raise self.fail(
                            "here-document delimiter absorbed by a line continuation "
                            "is ambiguous",
                            cursor,
                        )
                    joined = accumulated + (line[:-1] if continued else line)
                    if not continued:
                        stripped = joined.lstrip("\t") if entry.strip_tabs else joined
                        if stripped == entry.delimiter:
                            raise self.fail(
                                "here-document delimiter formed by a line continuation "
                                "is ambiguous",
                                cursor,
                            )
                    accumulated = joined if continued else ""
                elif candidate == entry.delimiter:
                    body_end = cursor
                    self.pos = self.limit if line_end == -1 else line_end + 1
                    break
                elif continued:
                    accumulated = line[:-1]
                if line_end == -1:
                    cursor = self.limit
                    break
                cursor = line_end + 1
            if body_end is None:
                raise self.fail(
                    f"here-document body for `{entry.delimiter}` is not terminated",
                    body_start,
                )
            if entry.quoted:
                segments = (
                    Segment(
                        kind=SINGLE_QUOTED,
                        text=self.text[body_start:body_end],
                        start=self.position(body_start),
                        end=self.position(body_end),
                        value=self.text[body_start:body_end],
                    ),
                )
            else:
                segments = self.scan_bounded_segments(body_start, body_end)
            tokens.append(
                self.token(
                    HEREDOC_BODY,
                    body_start,
                    body_end,
                    segments,
                    delimiter=entry.delimiter,
                    quoted_delimiter=entry.quoted,
                    strip_tabs=entry.strip_tabs,
                )
            )
        return tokens

    def scan_bounded_segments(self, start: int, end: int) -> tuple[Segment, ...]:
        saved_pos, saved_limit = self.pos, self.limit
        self.pos, self.limit = start, end
        try:
            segments = self.scan_expandable_segments(
                stop_at_quote=False, escapable="$`\\"
            )
        finally:
            self.pos, self.limit = saved_pos, saved_limit
        return segments

    def scan_expandable_segments(
        self, *, stop_at_quote: bool, escapable: str = '$`"\\'
    ) -> tuple[Segment, ...]:
        segments: list[Segment] = []
        literal_start = self.pos
        while self.pos < self.limit:
            character = self.text[self.pos]
            if stop_at_quote and character == '"':
                break
            if character == "`":
                raise self.fail("unsupported backquote command substitution")
            if character not in "\\$":
                self.pos += 1
                continue
            if self.pos > literal_start:
                segments.append(self.literal_segment(literal_start, self.pos))
            if character == "\\":
                segments.append(self.scan_escape(escapable=escapable))
            else:
                segments.append(self.scan_dollar(quoted=True))
            literal_start = self.pos
        if self.pos > literal_start:
            segments.append(self.literal_segment(literal_start, self.pos))
        return tuple(segments)

    def literal_segment(self, start: int, end: int) -> Segment:
        return Segment(
            kind=LITERAL,
            text=self.text[start:end],
            start=self.position(start),
            end=self.position(end),
            value=self.text[start:end],
        )

    def scan_escape(self, *, escapable: str | None) -> Segment:
        start = self.pos
        following = self.peek(1)
        if not following:
            raise self.fail("supplied text ends with a dangling backslash")
        self.pos += 2
        if following == "\n":
            return Segment(
                kind=CONTINUATION,
                text=self.text[start:self.pos],
                start=self.position(start),
                end=self.position(self.pos),
                value="",
            )
        if escapable is not None and following not in escapable:
            self.pos = start + 1
            return self.literal_segment(start, self.pos)
        return Segment(
            kind=ESCAPE,
            text=self.text[start:self.pos],
            start=self.position(start),
            end=self.position(self.pos),
            value=following,
        )

    def scan_single_quoted(self) -> Segment:
        start = self.pos
        close = self.text.find("'", self.pos + 1, self.limit)
        if close == -1:
            raise self.fail("single-quoted text is not terminated", start)
        self.pos = close + 1
        return Segment(
            kind=SINGLE_QUOTED,
            text=self.text[start:self.pos],
            start=self.position(start),
            end=self.position(self.pos),
            value=self.text[start + 1:close],
        )

    def scan_double_quoted(self) -> Segment:
        start = self.pos
        self.pos += 1
        segments = self.scan_expandable_segments(stop_at_quote=True)
        if self.pos >= self.limit or self.text[self.pos] != '"':
            raise self.fail("double-quoted text is not terminated", start)
        self.pos += 1
        return Segment(
            kind=DOUBLE_QUOTED,
            text=self.text[start:self.pos],
            start=self.position(start),
            end=self.position(self.pos),
            segments=segments,
        )

    def scan_dollar(self, *, quoted: bool = False) -> Segment:
        start = self.pos
        following = self.peek(1)
        if not quoted and following == "'":
            raise self.fail("unsupported dollar-single-quoted text `$'`")
        if not quoted and following == '"':
            raise self.fail('unsupported dollar-double-quoted text `$"`')
        if following == "(" and self.peek(2) == "(":
            return self.scan_arithmetic_expansion()
        if following == "(":
            return self.scan_command_substitution()
        if following == "{":
            return self.scan_braced_parameter()
        if following and following in NAME_START:
            cursor = self.pos + 1
            while cursor < self.limit and self.text[cursor] in NAME_CHARACTERS:
                cursor += 1
            self.pos = cursor
            return self.expansion_segment(PARAMETER_EXPANSION, start)
        if following and following in SPECIAL_PARAMETERS:
            self.pos += 2
            return self.expansion_segment(PARAMETER_EXPANSION, start)
        self.pos += 1
        return self.literal_segment(start, self.pos)

    def expansion_segment(self, kind: str, start: int) -> Segment:
        return Segment(
            kind=kind,
            text=self.text[start:self.pos],
            start=self.position(start),
            end=self.position(self.pos),
        )

    def scan_braced_parameter(self) -> Segment:
        start = self.pos
        self.pos += 2
        segments: list[Segment] = []
        literal_start = self.pos
        while self.pos < self.limit:
            character = self.text[self.pos]
            if character == "}":
                self.pos += 1
                if self.pos - 1 > literal_start:
                    segments.append(self.literal_segment(literal_start, self.pos - 1))
                return Segment(
                    kind=PARAMETER_EXPANSION,
                    text=self.text[start:self.pos],
                    start=self.position(start),
                    end=self.position(self.pos),
                    segments=tuple(segments),
                )
            if character not in "'\"$\\`":
                self.reject_process_substitution()
                self.pos += 1
                continue
            if self.pos > literal_start:
                segments.append(self.literal_segment(literal_start, self.pos))
            if character == "`":
                raise self.fail("unsupported backquote command substitution")
            if character == "'":
                segment = self.scan_single_quoted()
            elif character == '"':
                segment = self.scan_double_quoted()
            elif character == "\\":
                segment = self.scan_escape(escapable=None)
            else:
                segment = self.scan_dollar()
            if _contains_literal_brace(segment):
                raise self.fail(
                    "quoted brace inside a parameter expansion is ambiguous",
                    segment.start.offset,
                )
            segments.append(segment)
            literal_start = self.pos
        raise self.fail("braced parameter expansion is not terminated", start)

    def scan_arithmetic_expansion(self) -> Segment:
        start = self.pos
        self.pos += 3
        depth = 2
        segments: list[Segment] = []
        while self.pos < self.limit:
            character = self.text[self.pos]
            if character == "(":
                depth += 1
                self.pos += 1
                continue
            if character == ")":
                depth -= 1
                self.pos += 1
                if depth == 0:
                    if not self.text.endswith("))", 0, self.pos):
                        raise self.fail(
                            "arithmetic expansion must close with adjacent parentheses",
                            start,
                        )
                    return Segment(
                        kind=ARITHMETIC_EXPANSION,
                        text=self.text[start:self.pos],
                        start=self.position(start),
                        end=self.position(self.pos),
                        segments=tuple(segments),
                    )
                continue
            if character == "`":
                raise self.fail("unsupported backquote command substitution")
            if character in "'\"":
                raise self.fail("quoting inside an arithmetic expansion is ambiguous")
            if character == "\\":
                if self.peek(1) != "\n":
                    raise self.fail("unsupported backslash in an arithmetic expansion")
                segments.append(self.scan_escape(escapable=None))
                continue
            if character == "$":
                segments.append(self.scan_dollar())
                continue
            self.reject_process_substitution()
            self.pos += 1
        raise self.fail("arithmetic expansion is not terminated", start)

    def scan_command_substitution(self) -> Segment:
        start = self.pos
        self.pos += 2
        tokens = self.run(nested=True)
        if self.pos >= self.limit or self.text[self.pos] != ")":
            raise self.fail("command substitution is not terminated", start)
        self.pos += 1
        return Segment(
            kind=COMMAND_SUBSTITUTION,
            text=self.text[start:self.pos],
            start=self.position(start),
            end=self.position(self.pos),
            tokens=tuple(tokens),
        )

    def scan_word(self) -> Token:
        start = self.pos
        segments: list[Segment] = []
        literal_start = self.pos
        while self.pos < self.limit:
            character = self.text[self.pos]
            if character in BLANKS or character == "\n":
                break
            if character in OPERATOR_START:
                self.reject_unsupported_sequence()
                break
            if character == "`":
                raise self.fail("unsupported backquote command substitution")
            if character not in "\\$'\"":
                self.pos += 1
                continue
            if self.pos > literal_start:
                segments.append(self.literal_segment(literal_start, self.pos))
            if character == "\\":
                segments.append(self.scan_escape(escapable=None))
            elif character == "'":
                segments.append(self.scan_single_quoted())
            elif character == '"':
                segments.append(self.scan_double_quoted())
            else:
                segments.append(self.scan_dollar())
            literal_start = self.pos
        if self.pos > literal_start:
            segments.append(self.literal_segment(literal_start, self.pos))
        if self.pos == start:
            raise self.fail(f"unsupported character `{self.text[start]}`", start)
        return self.token(WORD, start, self.pos, tuple(segments))
