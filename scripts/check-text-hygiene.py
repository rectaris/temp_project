#!/usr/bin/env python3
"""Refuse tracked text that the release boundary would reject.

The release boundary reads a commit range, so the same repository state can
pass or fail depending on which range is taken. This command reads the whole
tracked file set instead, so the answer belongs to the repository rather than
to a range, and a defect is visible before a push rather than after one.

The verdict itself is Git's. Comparing the empty tree against the index and
against the working tree presents every tracked line as added, so `git diff
--check` answers for the whole repository with exactly the rule the release
boundary applies, including its binary detection, its line-ending conversion
and its path attributes. Reimplementing any of that here would only create a
second opinion that could disagree, so Git's exit status decides, and this
command only explains the answer. One rule is added on top: a file that ends
without a newline, which Git reports in the patch but does not refuse.

Both the index and the working tree are read, because a commit records the
index while `git add` records the working tree, and a defect in either one
reaches the release boundary.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MAX_REPORTED = 50
NO_NEWLINE_MARKER = "\\ No newline at end of file"
GIT_FOUND_PROBLEMS = 2
STAGED_PREFIX = "(staged) "
REPORT_PATTERN = re.compile(r"^.+:\d+: [^:]+\.$")
# A symlink blob holds a path and a gitlink holds a commit. Neither is text
# this repository writes, and neither ends with a newline.
REGULAR_BLOB_MODES = frozenset({"100644", "100755"})
# The release boundary runs Git with its default whitespace rule, so that rule
# is pinned here rather than left to whatever configuration a checkout carries.
# A local setting that relaxed it would let a defect through here and still
# fail the boundary. Everything else Git decides is left to Git.
PINNED_WHITESPACE = "core.whitespace=blank-at-eol,space-before-tab,blank-at-eof"
# A configured or exported diff program would answer in Git's place, and a
# text conversion would hide the bytes that are actually stored.
NATIVE_DIFF = ("--no-ext-diff", "--no-textconv")


class HygieneError(RuntimeError):
    """Raised when the tracked content cannot be read as stated."""


def run_git(root: Path, arguments: list[str], accept: tuple[int, ...] = (0,)) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-c", PINNED_WHITESPACE, *arguments],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode not in accept:
        message = result.stderr.decode(errors="replace").strip()
        raise HygieneError(message or f"git {' '.join(arguments)} failed")
    return result.returncode, result.stdout.decode(errors="replace")


def require_repository_root(root: Path) -> None:
    """Refuse a root that is not itself the top of a working tree.

    Git searches upwards, so a directory that holds no repository can still
    answer for an enclosing one, and a subdirectory would answer for part of
    the tracked set while reporting success for all of it.
    """

    _, toplevel = run_git(root, ["rev-parse", "--show-toplevel"])
    if not toplevel.strip() or Path(toplevel.strip()).resolve() != root:
        raise HygieneError(f"{root} is not the root of a Git working tree")


def empty_tree(root: Path) -> str:
    return run_git(root, ["hash-object", "-t", "tree", "/dev/null"])[1].strip()


def whitespace_reports(root: Path, scope: list[str], tree: str) -> list[str]:
    """What `git diff --check` says about every tracked line.

    Git's exit status is the verdict. Its messages are only read to say where
    the defect is, so an unrecognised or translated message still refuses.
    """

    status, output = run_git(
        root,
        ["diff", *NATIVE_DIFF, "--check", *scope, tree],
        accept=(0, GIT_FOUND_PROBLEMS),
    )
    if status != GIT_FOUND_PROBLEMS:
        return []
    reports = [line for line in output.splitlines() if REPORT_PATTERN.match(line)]
    return reports or [
        "git diff --check refused this repository without a report this command"
        f" could read: {' '.join(output.split()) or '<no output>'}"
    ]


def changed_entries(root: Path, scope: list[str], tree: str) -> list[tuple[str, str]]:
    """The mode and path of each patch section, as Git records them.

    Patch headers are display text and quote awkward paths, so the identity of
    each section is taken from the machine-readable listing instead. Both come
    from the same comparison in the same order.
    """

    fields = run_git(root, ["diff", *NATIVE_DIFF, "--raw", "-z", *scope, tree])[1].split("\0")
    entries: list[tuple[str, str]] = []
    position = 0
    while position < len(fields) - 1:
        record = fields[position]
        position += 1
        if not record.startswith(":"):
            continue
        parts = record.split()
        mode = parts[1] if len(parts) > 1 else ""
        entries.append((mode, fields[position]))
        position += 1
    return entries


def missing_newline_reports(root: Path, scope: list[str], tree: str) -> list[str]:
    """The one rule Git reports in the patch without refusing it."""

    entries = changed_entries(root, scope, tree)
    patch = run_git(root, ["diff", *NATIVE_DIFF, "--no-color", *scope, tree])[1]
    reports: list[str] = []
    section = -1
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            section += 1
        elif line == NO_NEWLINE_MARKER and 0 <= section < len(entries):
            mode, path = entries[section]
            if mode in REGULAR_BLOB_MODES:
                reports.append(f"{path}: missing final newline.")
    return reports


def inspect(root: Path) -> list[str]:
    require_repository_root(root)
    tree = empty_tree(root)
    collected: dict[str, bool] = {}
    for scope, staged in ((["--cached"], True), ([], False)):
        for report in whitespace_reports(root, scope, tree) + missing_newline_reports(
            root, scope, tree
        ):
            # The same defect in both places is one defect, and the working
            # tree is where it is repaired.
            collected[report] = collected.get(report, True) and staged
    return sorted(
        f"{STAGED_PREFIX}{report}" if staged else report
        for report, staged in collected.items()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check tracked text hygiene.")
    parser.add_argument("--root", default=".", help="repository root whose tracked text is read")
    arguments = parser.parse_args(argv)
    root = Path(arguments.root).resolve()
    try:
        reports = inspect(root)
    except HygieneError as exc:
        sys.stderr.write(f"text hygiene check failed: {exc}\n")
        return 2
    if reports:
        for report in reports[:MAX_REPORTED]:
            sys.stderr.write(f"{report}\n")
        if len(reports) > MAX_REPORTED:
            sys.stderr.write(f"... and {len(reports) - MAX_REPORTED} more\n")
        sys.stderr.write(
            "Next: remove the reported characters and run this command again."
            f" A {STAGED_PREFIX.strip()} report names content the index already holds,"
            " so stage the repair as well.\n"
        )
        return 1
    sys.stdout.write("tracked text hygiene check passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
