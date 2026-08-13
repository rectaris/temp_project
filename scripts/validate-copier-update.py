#!/usr/bin/env python3
"""Reject a Copier result that is unsafe to review or commit."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


ALLOWED_TRACKED_DELETIONS = {
    ".github/workflows/codex-ci-autofix.yml",
    "scripts/skillspector-scan.sh",
}
NON_REPOSITORY_DIAGNOSIS = (
    "fatal: not a git repository (or any of the parent directories): .git"
)


class UpdateValidationError(RuntimeError):
    """The final Copier result could not be proven safe."""


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
    except OSError as exc:
        raise UpdateValidationError(f"could not execute Git: {exc}") from exc


def require_git_success(
    repository: Path, *arguments: str
) -> subprocess.CompletedProcess[bytes]:
    result = run_git(repository, *arguments)
    if result.returncode != 0:
        diagnosis = result.stderr.decode("utf-8", errors="replace").strip()
        command = " ".join(arguments)
        raise UpdateValidationError(
            f"Git inspection failed for `git {command}` with exit "
            f"{result.returncode}: {diagnosis or 'no diagnostic'}"
        )
    return result


def inspect_git(repository: Path) -> None:
    result = run_git(repository, "rev-parse", "--show-toplevel")
    diagnosis = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode == 128 and diagnosis == NON_REPOSITORY_DIAGNOSIS:
        return
    if result.returncode != 0:
        raise UpdateValidationError(
            "Git repository inspection failed with exit "
            f"{result.returncode}: {diagnosis or 'no diagnostic'}"
        )

    reported_root = Path(
        result.stdout.decode("utf-8", errors="strict").strip()
    ).resolve()
    if reported_root != repository:
        raise UpdateValidationError(
            f"destination is not the Git repository root: {repository} "
            f"(Git reported {reported_root})"
        )

    unmerged = require_git_success(repository, "ls-files", "-u", "-z").stdout
    if unmerged:
        paths = sorted(
            {
                entry.split(b"\t", 1)[1].decode("utf-8", errors="surrogateescape")
                for entry in unmerged.split(b"\0")
                if b"\t" in entry
            }
        )
        raise UpdateValidationError(
            "Copier update left unresolved index conflicts: " + ", ".join(paths)
        )

    deleted_output = require_git_success(
        repository,
        "diff",
        "--name-only",
        "--diff-filter=D",
        "-z",
        "HEAD",
        "--",
    ).stdout
    deleted = {
        path.decode("utf-8", errors="surrogateescape")
        for path in deleted_output.split(b"\0")
        if path
    }
    unclassified = sorted(deleted - ALLOWED_TRACKED_DELETIONS)
    if unclassified:
        raise UpdateValidationError(
            "Copier update deleted tracked paths outside the allowlist: "
            + ", ".join(unclassified)
        )


def contains_complete_conflict(path: Path) -> bool:
    state = 0
    try:
        with path.open("rb") as stream:
            for line in stream:
                if state == 0 and line.startswith(b"<<<<<<<"):
                    state = 1
                elif state == 1 and line.startswith(b"======="):
                    state = 2
                elif state == 2 and line.startswith(b">>>>>>>"):
                    return True
    except OSError as exc:
        raise UpdateValidationError(f"could not inspect filesystem entry {path}: {exc}") from exc
    return False


def inspect_filesystem(repository: Path) -> None:
    rejection_paths: list[str] = []
    conflict_paths: list[str] = []
    pending = [repository]

    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise UpdateValidationError(f"could not scan directory {directory}: {exc}") from exc

        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(repository).as_posix()
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name != ".git":
                        pending.append(path)
                    if entry.name.endswith(".rej"):
                        rejection_paths.append(relative)
                    continue
                if entry.name.endswith(".rej"):
                    rejection_paths.append(relative)
                if entry.is_file(follow_symlinks=False) and contains_complete_conflict(path):
                    conflict_paths.append(relative)
            except OSError as exc:
                raise UpdateValidationError(
                    f"could not inspect filesystem entry {path}: {exc}"
                ) from exc

    findings: list[str] = []
    if rejection_paths:
        findings.append("rejection files: " + ", ".join(sorted(rejection_paths)))
    if conflict_paths:
        findings.append("complete conflict blocks: " + ", ".join(sorted(conflict_paths)))
    if findings:
        raise UpdateValidationError("Copier update left " + "; ".join(findings))


def inspect_external_access_profile(repository: Path) -> None:
    answers_path = repository / ".copier-answers.yml"
    policy_path = repository / "docs/agent/external-services.yaml"
    try:
        answers = answers_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError as exc:
        raise UpdateValidationError(f"could not read {answers_path}: {exc}") from exc
    match = re.search(r"^external_access_profile:\s*([^\s#]+)", answers, re.MULTILINE)
    if match is None or match.group(1).strip("\"'") != "task_scoped_default_allow":
        return
    try:
        policy = policy_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UpdateValidationError(
            "task_scoped_default_allow requires a project-owned version 2 "
            f"external-service policy: {exc}"
        ) from exc
    if not re.search(r"^version:\s*2\s*$", policy, re.MULTILINE) or not re.search(
        r"^access_profile:\s*task_scoped_default_allow\s*$", policy, re.MULTILINE
    ):
        raise UpdateValidationError(
            "task_scoped_default_allow was selected, but the project-owned "
            "docs/agent/external-services.yaml is not the matching version 2 policy; "
            "migrate and review that file explicitly before retrying the Copier update"
        )
    checker_path = (
        repository
        / ".project-agent-workflow/scripts/check-external-service-policy.py"
    )
    try:
        result = subprocess.run(
            [sys.executable, str(checker_path), "--policy", str(policy_path), "check"],
            cwd=repository,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise UpdateValidationError(
            f"could not run the version 2 external-service policy checker: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise UpdateValidationError(
            "task_scoped_default_allow selected an invalid version 2 external-service "
            f"policy: {detail or 'policy check failed'}"
        )


def validate(destination: Path) -> None:
    repository = destination.resolve()
    if not repository.is_dir():
        raise UpdateValidationError(f"destination is not a directory: {repository}")
    inspect_git(repository)
    inspect_filesystem(repository)
    inspect_external_access_profile(repository)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        validate(args.destination)
    except UpdateValidationError as exc:
        print(f"unsafe Copier update result: {exc}", file=sys.stderr)
        return 1
    print("Copier update result validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
