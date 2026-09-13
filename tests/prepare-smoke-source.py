#!/usr/bin/env python3
"""Prepare one isolated Copier source that carries the current input files.

The generated-project smoke test renders from a disposable clone so that a run
never mutates the checkout it reads. Selecting that clone's contents by hand
let an edited input keep its old committed bytes, so this helper derives the
selection from Git instead: every tracked input plus every nonignored new file
under the declared input boundary, with tracked deletions and file modes
carried over. The source repository is only read.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


INPUT_PREFIXES = ("copier.yml", "scripts", "template")
SYMLINK_MODE = "120000"
GITLINK_MODE = "160000"
UNMERGED_STAGES = {"1", "2", "3"}


class PreparationError(Exception):
    """One refusal raised before Copier starts."""


def git(repository: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise PreparationError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def nul_fields(raw: bytes) -> list[bytes]:
    return [field for field in raw.split(b"\0") if field]


def display(path: bytes) -> str:
    return os.fsdecode(path)


def tracked_inputs(source: Path) -> dict[bytes, str]:
    """Map each tracked input path to the file mode recorded in the index."""

    entries: dict[bytes, str] = {}
    for field in nul_fields(git(source, "ls-files", "-z", "-s", "--", *INPUT_PREFIXES)):
        metadata, separator, path = field.partition(b"\t")
        if not separator:
            raise PreparationError(f"unreadable index entry: {display(field)}")
        parts = metadata.decode("utf-8", "replace").split(" ")
        if len(parts) != 3:
            raise PreparationError(f"unreadable index entry: {display(field)}")
        mode, _, stage = parts
        if stage in UNMERGED_STAGES:
            raise PreparationError(f"unmerged index entry: {display(path)}")
        if mode in (SYMLINK_MODE, GITLINK_MODE):
            raise PreparationError(
                f"unsupported tracked input type {mode}: {display(path)}"
            )
        entries[path] = mode
    return entries


def new_inputs(source: Path) -> list[bytes]:
    raw = git(source, "ls-files", "-z", "--others", "--exclude-standard", "--", *INPUT_PREFIXES)
    return nul_fields(raw)


def committed_inputs(source: Path) -> list[bytes]:
    raw = git(source, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", *INPUT_PREFIXES)
    return nul_fields(raw)


def ignored_paths(source: Path, relative: list[bytes]) -> set[bytes]:
    result = subprocess.run(
        ["git", "-C", str(source), "check-ignore", "-z", "--stdin"],
        input=b"\0".join(relative),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode not in (0, 1):
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise PreparationError(f"checking ignore rules failed: {detail}")
    return set(nul_fields(result.stdout))


def refuse_special_inputs(source: Path) -> None:
    """Refuse a file type Git cannot carry into the prepared source.

    Git omits a FIFO, socket, or device node from every listing, so such an
    entry would silently leave the prepared source different from the checkout.
    That is the same class of divergence this helper exists to remove.
    """

    found: list[bytes] = []
    for prefix in INPUT_PREFIXES:
        origin = source / prefix
        if not origin.is_dir() or origin.is_symlink():
            continue
        for current, directories, files in os.walk(origin):
            directories[:] = [name for name in directories if name != ".git"]
            for name in files:
                candidate = Path(current) / name
                mode = candidate.lstat().st_mode
                if not stat.S_ISREG(mode) and not stat.S_ISLNK(mode):
                    found.append(os.fsencode(str(candidate.relative_to(source))))
    if not found:
        return
    ignored = ignored_paths(source, found)
    unsupported = sorted(path for path in found if path not in ignored)
    if unsupported:
        raise PreparationError(
            f"unsupported input file type: {display(unsupported[0])}"
        )


def require_readable_regular_file(absolute: Path, relative: bytes) -> bool:
    """Report whether the selected input is present, refusing unusable input."""

    try:
        info = absolute.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise PreparationError(
            f"unreadable input: {display(relative)}: {error.strerror}"
        ) from error
    if not stat.S_ISREG(info.st_mode):
        raise PreparationError(f"unsupported input file type: {display(relative)}")
    try:
        with absolute.open("rb"):
            pass
    except OSError as error:
        raise PreparationError(
            f"unreadable input: {display(relative)}: {error.strerror}"
        ) from error
    return True


def select_inputs(source: Path) -> tuple[list[bytes], list[bytes]]:
    """Return the present input files to overlay and the deletions to apply."""

    tracked = tracked_inputs(source)
    refuse_special_inputs(source)
    candidates = list(tracked)
    candidates.extend(path for path in new_inputs(source) if path not in tracked)
    present: list[bytes] = []
    for relative in candidates:
        absolute = source / os.fsdecode(relative)
        if require_readable_regular_file(absolute, relative):
            present.append(relative)
    deletions = sorted(set(committed_inputs(source)) - set(present))
    return sorted(present), deletions


def materialize(source: Path, destination: Path, present: list[bytes], deletions: list[bytes]) -> None:
    for relative in deletions:
        target = destination / os.fsdecode(relative)
        if target.is_symlink() or target.exists():
            target.unlink()
    for relative in present:
        origin = source / os.fsdecode(relative)
        target = destination / os.fsdecode(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            target.unlink()
        target.write_bytes(origin.read_bytes())
        target.chmod(stat.S_IMODE(origin.lstat().st_mode))


def stage(destination: Path, paths: list[bytes]) -> None:
    if not paths:
        return
    result = subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "add",
            "-A",
            "--pathspec-from-file=-",
            "--pathspec-file-nul",
        ],
        input=b"\0".join(paths),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise PreparationError(f"staging the prepared source failed: {detail}")


def clone(source: Path, destination: Path) -> None:
    result = subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", str(source), str(destination)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise PreparationError(f"cloning the smoke source failed: {detail}")


def prepare(source: Path, destination: Path, tag: str, message: str) -> dict[str, object]:
    if not (source / ".git").exists():
        raise PreparationError(f"not a Git repository: {source}")
    if destination.exists():
        raise PreparationError(f"destination already exists: {destination}")
    present, deletions = select_inputs(source)
    clone(source, destination)
    materialize(source, destination, present, deletions)
    git(destination, "config", "user.name", "Smoke Source")
    git(destination, "config", "user.email", "smoke-source@example.invalid")
    stage(destination, present + deletions)
    git(destination, "commit", "--allow-empty", "-qm", message)
    git(destination, "tag", "-f", tag)
    return {
        "source": str(destination),
        "ref": tag,
        "overlaid": len(present),
        "deleted": len(deletions),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--message", default="Create isolated smoke candidate")
    arguments = parser.parse_args(argv)
    try:
        summary = prepare(
            arguments.source.resolve(),
            arguments.destination,
            arguments.tag,
            arguments.message,
        )
    except PreparationError as error:
        print(f"smoke source preparation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
