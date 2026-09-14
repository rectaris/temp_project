#!/usr/bin/env python3
"""Lightweight static security checks for generated repositories."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import security_rules


ROOT = Path.cwd()
SKIP_DIRS = {
    ".git",
    ".project-agent-workflow-migration",
    "node_modules",
    "dist",
    "coverage",
    ".venv",
    ".uv-cache",
    ".uv-tools",
    ".uv-home",
}
SKIP_FILES = {
    Path("scripts/security-static-check.py"),
    Path("scripts/security_rules.py"),
    Path(".project-agent-workflow/scripts/security-static-check.py"),
    Path(".project-agent-workflow/scripts/security_rules.py"),
}
TEXT_SUFFIXES = {".bash", ".sh", ".py", ".js", ".mjs", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".md", ".json"}
MANAGED_FILES = {
    Path(".agents/skills/decision-audit/SKILL.md"),
    Path(".agents/skills/define-referents-first/SKILL.md"),
    Path(".agents/skills/graph-memory/SKILL.md"),
    Path(".agents/skills/implementation-guidelines/SKILL.md"),
    Path(".agents/skills/linear-ops/SKILL.md"),
    Path(".agents/skills/mcp-ops/SKILL.md"),
    Path(".agents/skills/plan-archive/SKILL.md"),
    Path(".agents/skills/sequential-plan-orchestrator/SKILL.md"),
    Path(".agents/skills/write-for-reader/SKILL.md"),
    Path(".codex/hooks/agent_log_event.py"),
    Path(".codex/hooks/pre_tool_hardening_gate.py"),
    Path(".codex/hooks/semantic_guard_advisory.py"),
    Path(".codex/hooks/stop_review_gate.py"),
    Path(".github/codex/prompts/ci-autofix.md"),
    Path(".github/workflows/project-agent-workflow.yml"),
    Path(".github/workflows/codex-ci-autofix.yml"),
}
RULES = [
    (security_rules.PRIVATE_KEY_MATERIAL, "private key material"),
    (security_rules.REMOTE_SCRIPT_PIPE, "remote script piped to shell"),
    (security_rules.SUDO_COMMAND, "sudo command in repository script"),
    (re.compile(r"\bpull_request_target\b"), "pull_request_target workflow requires careful review"),
]

# Credential display in committed shell files.
#
# This rule reads whole files, so it does not reuse the pre-tool gate's
# command-string scanner: that scanner decides one command the agent is about
# to run, while this one reads text that may never be executed at all. It is
# also scoped to shell files, because a Python file that reads a credential
# from the environment is doing legitimate work and nothing at the byte level
# separates that from disclosure.
SHELL_SUFFIXES = {".bash", ".sh"}
# An enumerated set, like the gate's. A category such as "a command that shows
# something" is not decidable, so the list is closed and the forms outside it
# stay the gate's responsibility.
DISPLAY_HEADS = frozenset(
    {"cat", "echo", "head", "less", "logger", "more", "printf", "tail", "tee"}
)
# A line that must quote an unsafe form declares it. The exemption is a
# security decision, so it is a visible line in the file rather than a path
# list a reader of the file cannot see, and it clears the line it sits on and
# the line after it rather than the whole file. A file-wide marker would leave
# every later line in that file unscanned.
CREDENTIAL_DISPLAY_EXEMPTION = "security-static-check: credential-display-example"
# Braces and parentheses are left alone, because splitting on them would
# cut `${NAME}` in half. A group or subshell is reached through the control
# words below instead.
COMMAND_SEPARATOR = re.compile(r"\|\||&&|;;|[;|&]")
WORD = re.compile(r"\S+")
# This module reads whole files rather than one command, so it carries its
# own opener pattern. A backslash quotes the delimiter exactly as a quote
# character does, and a quoted delimiter means the body is literal.
HERE_DOCUMENT_OPENER = re.compile(
    r"<<-?\s*(?P<quote>['\"\\]?)(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)['\"]?"
)
ESCAPED_EXPANSION_CHARACTER = re.compile(r"\\[$`]")
EXPANSION = re.compile(r"\$\{([^{}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def displayed_credential(body: str, declared: object) -> str | None:
    """Name the credential this expansion body can substitute, if it can.

    The length and indirection forms substitute something derived from the
    value rather than the value, and the alternate operator with a fixed
    literal substitutes only that literal, which is the presence test the
    security specification names. Every other form can place the value itself
    into the command's arguments.
    """
    if body[:1] in {"#", "!"}:
        return None
    match = security_rules.VARIABLE_NAME.match(body)
    if match is None:
        return None
    name = match.group(0)
    if not security_rules.is_credential_name(name, declared):
        return None
    operator = body[match.end() :]
    if operator.startswith((":+", "+")):
        alternate = operator[2:] if operator.startswith(":+") else operator[1:]
        if security_rules.is_fixed_literal(alternate):
            return None
    return name


def command_head(segment: str) -> tuple[str, str]:
    """Split a segment into its command head and the rest of its words.

    Assignment words, shell control words and heads that only introduce
    another command stand in front of the head, so they are stepped over
    rather than mistaken for the command.
    """
    remainder = segment.lstrip()
    while True:
        match = WORD.match(remainder)
        if match is None:
            return "", ""
        word = match.group(0)
        remainder = remainder[match.end() :]
        if (
            security_rules.ASSIGNMENT.fullmatch(word)
            or word in security_rules.CONTROL_WORDS
            or word in security_rules.TRANSPARENT_PREFIXES
        ):
            remainder = remainder.lstrip()
            continue
        return word.strip("\"'"), remainder


def strip_quotes_and_comment(line: str, *, keep_quoted: bool = False) -> str:
    """Remove what the shell will not expand on this line.

    Quoting state is tracked while walking the line rather than applied as two
    independent substitutions, because a single quote inside double quotes is
    an ordinary character and a `#` inside quotes starts no comment. Deciding
    them separately deletes text the shell would have expanded.

    With `keep_quoted` the single-quoted text is kept verbatim. The comment is
    still removed, so the result is what the reader sees on the line, which is
    where a here-document delimiter has to keep its own quoting.
    """
    out: list[str] = []
    index = 0
    in_double = False
    while index < len(line):
        character = line[index]
        if character == "\\" and index + 1 < len(line):
            # A backslash escape cannot reintroduce an expansion, so an escaped
            # dollar or backtick is dropped rather than left to be matched.
            if line[index + 1] in "$`" and not keep_quoted:
                index += 2
                continue
            out.append(line[index : index + 2])
            index += 2
            continue
        if character == '"':
            in_double = not in_double
        elif character == "'" and not in_double:
            end = line.find("'", index + 1)
            if end == -1:
                break
            out.append(line[index : end + 1] if keep_quoted else "''")
            index = end + 1
            continue
        elif (
            character == "#"
            and not in_double
            and (index == 0 or line[index - 1].isspace())
        ):
            break
        out.append(character)
        index += 1
    return "".join(out)


def exempt_lines(lines: list[str]) -> set[int]:
    """Number every line one declared exemption clears."""
    cleared: set[int] = set()
    for number, line in enumerate(lines, start=1):
        if CREDENTIAL_DISPLAY_EXEMPTION in line:
            cleared.update({number, number + 1})
    return cleared


def credential_display_findings(text: str, declared: object = frozenset()) -> list[str]:
    """Report each line where a display command can print a credential."""
    findings: list[str] = []
    lines = text.splitlines()
    cleared = exempt_lines(lines)
    index = 0
    while index < len(lines):
        number = index + 1
        line = lines[index]
        index += 1
        body = strip_quotes_and_comment(line)
        # The opener is read from the line with its quoting intact, because a
        # quoted delimiter is what says the body is literal. Reading it from
        # the stripped body would lose the quotes and rescan an inert body as
        # if it were a run of live commands.
        opener = HERE_DOCUMENT_OPENER.search(strip_quotes_and_comment(line, keep_quoted=True))
        if opener is not None:
            # A here-document whose delimiter is unquoted is expanded, so its
            # body is what the command displays. It is folded onto the opening
            # line, which is the line a reader has to change.
            collected: list[str] = []
            while index < len(lines) and lines[index].strip() != opener.group("delimiter"):
                collected.append(lines[index])
                index += 1
            index += 1
            if not opener.group("quote"):
                body = body + " " + ESCAPED_EXPANSION_CHARACTER.sub("", " ".join(collected))
        if number in cleared:
            continue
        for segment in COMMAND_SEPARATOR.split(body):
            head, operands = command_head(segment)
            if head not in DISPLAY_HEADS:
                continue
            for braced, bare in EXPANSION.findall(operands):
                name = displayed_credential(braced or bare, declared)
                if name is not None:
                    findings.append(
                        f"line {number}: {head} can print the credential variable {name}"
                    )
                    break
    return findings


class GitQueryError(RuntimeError):
    """A Git command needed to determine changed files failed."""


def git_paths(args: list[str]) -> list[Path]:
    result = subprocess.run(
        ["git", *args, "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        command = " ".join(["git", *args, "-z"])
        raise GitQueryError(f"Git query failed ({result.returncode}): {command}")
    return [Path(os.fsdecode(value)) for value in result.stdout.split(b"\0") if value]


def changed_paths(base: str | None = None) -> set[Path]:
    if base is not None:
        # Continuous integration checks out a commit with no working-tree edits,
        # so the local diffs below would report nothing. The range names what
        # the branch changed since it left the base.
        return set(git_paths(["diff", "--name-only", f"{base}...HEAD"]))
    paths = set(git_paths(["diff", "--cached", "--name-only"]))
    paths.update(git_paths(["diff", "--name-only"]))
    paths.update(git_paths(["ls-files", "--others", "--exclude-standard"]))
    return paths


def is_managed(relative: Path) -> bool:
    return relative in MANAGED_FILES or relative.parts[:1] == (".project-agent-workflow",)


def iter_files(scope: str = "repository", base: str | None = None) -> list[Path]:
    out: list[Path] = []
    candidates = (
        (ROOT / path for path in changed_paths(base)) if scope == "changed" else ROOT.rglob("*")
    )
    for path in candidates:
        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            continue
        if relative.is_absolute() or ".." in relative.parts:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if path.resolve() == Path(__file__).resolve() or relative in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if scope == "managed" and not is_managed(relative):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"}:
            out.append(path)
    return sorted(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--managed", action="store_true", help="scan Copier-managed workflow files")
    scope.add_argument("--changed", action="store_true", help="scan Git-visible changed files")
    scope.add_argument("--base", help="scan files changed since this ref, for a clean checkout")
    args = parser.parse_args(argv)
    selected_scope = (
        "managed" if args.managed else "changed" if args.changed or args.base else "repository"
    )
    declared = security_rules.DeclaredCredentialNames(ROOT)
    findings: list[str] = []
    try:
        files = iter_files(selected_scope, args.base)
    except GitQueryError as error:
        print(f"static security check failed: {error}", file=sys.stderr)
        return 1
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, message in RULES:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {message}")
        if path.suffix in SHELL_SUFFIXES:
            for finding in credential_display_findings(text, declared):
                findings.append(f"{path.relative_to(ROOT)}: {finding}")
    if findings:
        print("static security check failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("static security check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
