#!/usr/bin/env python3
"""Reject a Copier result that is unsafe to review or commit."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path


ALLOWED_TRACKED_DELETIONS = {
    ".github/workflows/codex-ci-autofix.yml",
    "scripts/skillspector-scan.sh",
}
NON_REPOSITORY_DIAGNOSIS = (
    "fatal: not a git repository (or any of the parent directories): .git"
)
OWNERSHIP_PATH = ".project-agent-workflow/ownership.yaml"
LEGACY_SEQUENTIAL_WORKER_SHA256 = "744ed4f634e13ec1de27076dfa9f12411a8b01ff56ba27cfbc5151086fbe1ccb"
READ_ONLY_SEQUENTIAL_WORKER_SHA256 = "6011c848311f59e18a37f511af8620cc025e8cad72a54fc767a83dd8da7837d1"
FIXED_AGENT_PROFILES = {
    "change_reviewer": ("gpt-5.6-sol", "high"),
    "docs_researcher": ("gpt-5.6-luna", "medium"),
    "evidence_synthesizer": ("gpt-5.6-luna", "xhigh"),
    "fast_scoped_worker": ("gpt-5.3-codex-spark", "medium"),
    "repo_explorer": ("gpt-5.6-luna", "low"),
    "scoped_worker": ("gpt-5.6-terra", "medium"),
    "sequential_plan_worker": ("gpt-5.3-codex-spark", "medium"),
}
ROOT_ASSIGNMENT = re.compile(
    r"^[ \t]*(?P<field>model|model_reasoning_effort|\"model\"|\"model_reasoning_effort\"|'model'|'model_reasoning_effort')[ \t]*="
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


def require_clean_update_start(repository: Path) -> None:
    result = run_git(repository, "rev-parse", "--show-toplevel")
    diagnosis = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        raise UpdateValidationError(
            "Copier update must start from a Git repository root: "
            + (diagnosis or f"git exited {result.returncode}")
        )
    reported_root = Path(result.stdout.decode("utf-8", errors="strict").strip()).resolve()
    if reported_root != repository:
        raise UpdateValidationError(
            f"destination is not the Git repository root: {repository} "
            f"(Git reported {reported_root})"
        )
    status = require_git_success(
        repository, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).stdout
    if status:
        raise UpdateValidationError(
            "Copier update requires a clean worktree so committed HEAD can be the "
            "project-owned content baseline"
        )


def parse_ownership_inventory(raw: bytes) -> dict[str, tuple[str, ...]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UpdateValidationError("committed ownership inventory is not UTF-8") from exc
    if not re.search(r"^version:\s*1\s*$", text, re.MULTILINE):
        raise UpdateValidationError("committed ownership inventory is not supported version 1")
    wanted = {"copier_managed", "seeded_project_owned", "metadata", "migration_backup"}
    values: dict[str, list[str]] = {key: [] for key in wanted}
    current: str | None = None
    for line in text.splitlines():
        root = re.fullmatch(r"([a-z_]+):(?:\s.*)?", line)
        if root is not None:
            current = root.group(1) if root.group(1) in wanted else None
            continue
        if current is not None and (item := re.fullmatch(r"  - (\S.*)", line)) is not None:
            values[current].append(item.group(1))
    if not values["copier_managed"] or not values["seeded_project_owned"]:
        raise UpdateValidationError("committed ownership inventory is missing required path classes")
    return {key: tuple(entries) for key, entries in values.items()}


def ownership_pattern_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    expression = re.escape(pattern).replace(r"\*", "[^/]*")
    return re.fullmatch(expression, path) is not None


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(ownership_pattern_matches(path, pattern) for pattern in patterns)


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def scan_multiline_string(line: str, index: int, delimiter: str) -> int | None:
    while (end := line.find(delimiter, index)) >= 0:
        if delimiter == "'''" or not is_escaped(line, end):
            return end + len(delimiter)
        index = end + 1
    return None


def multiline_delimiter(line: str) -> str | None:
    index = 0
    while index < len(line):
        character = line[index]
        if character == "#":
            break
        if line.startswith('"""', index) or line.startswith("'''", index):
            delimiter = line[index : index + 3]
            end = scan_multiline_string(line, index + 3, delimiter)
            if end is None:
                return delimiter
            index = end
            continue
        if character in {'"', "'"}:
            quote = character
            index += 1
            while index < len(line):
                if line[index] == quote and (quote == "'" or not is_escaped(line, index)):
                    index += 1
                    break
                index += 1
            continue
        index += 1
    return None


def without_fixed_agent_lines(text: str) -> str:
    kept: list[str] = []
    delimiter: str | None = None
    in_root = True
    for line in text.splitlines(keepends=True):
        if delimiter is not None:
            kept.append(line)
            if (end := scan_multiline_string(line, 0, delimiter)) is not None:
                delimiter = multiline_delimiter(line[end:])
            continue
        if line.lstrip().startswith("["):
            in_root = False
        if not (in_root and ROOT_ASSIGNMENT.match(line)):
            kept.append(line)
        delimiter = multiline_delimiter(line)
    return "".join(kept)


def validate_agent_profile_transition(path: str, before: bytes, after: bytes) -> None:
    if path == ".codex/agents/sequential_plan_worker.toml":
        before_digest = hashlib.sha256(before).hexdigest()
        after_digest = hashlib.sha256(after).hexdigest()
        if (
            before_digest == LEGACY_SEQUENTIAL_WORKER_SHA256
            and after_digest == READ_ONLY_SEQUENTIAL_WORKER_SHA256
        ):
            return
    try:
        before_text = before.decode("utf-8")
        after_text = after.decode("utf-8")
        parsed = tomllib.loads(after_text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise UpdateValidationError(f"changed agent profile is not valid UTF-8 TOML: {path}") from exc
    name = parsed.get("name")
    expected = FIXED_AGENT_PROFILES.get(name) if isinstance(name, str) else None
    if expected is None or (parsed.get("model"), parsed.get("model_reasoning_effort")) != expected:
        raise UpdateValidationError(f"changed agent profile has unexpected fixed model fields: {path}")
    if without_fixed_agent_lines(before_text) != without_fixed_agent_lines(after_text):
        raise UpdateValidationError(
            f"Copier update changed project-owned agent profile content outside fixed model fields: {path}"
        )


def inspect_project_owned_content(repository: Path) -> None:
    worktree = run_git(repository, "rev-parse", "--is-inside-work-tree")
    diagnosis = worktree.stderr.decode("utf-8", errors="replace").strip()
    if worktree.returncode != 0:
        if diagnosis == NON_REPOSITORY_DIAGNOSIS:
            return
        raise UpdateValidationError(
            "could not determine whether Copier destination is a Git worktree: "
            + (diagnosis or f"git exited {worktree.returncode}")
        )
    if worktree.stdout.strip() != b"true":
        raise UpdateValidationError("Copier destination is not a Git worktree")
    ownership = run_git(repository, "show", f"HEAD:{OWNERSHIP_PATH}")
    if ownership.returncode != 0:
        diagnosis = ownership.stderr.decode("utf-8", errors="replace").strip()
        raise UpdateValidationError(
            f"could not load committed ownership inventory {OWNERSHIP_PATH}: "
            + (diagnosis or f"git exited {ownership.returncode}")
        )
    inventory = parse_ownership_inventory(ownership.stdout)
    changed = require_git_success(
        repository, "diff", "--name-only", "-z", "HEAD", "--"
    ).stdout
    rejected: list[str] = []
    for raw_path in changed.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        current_path = repository / path
        if path in ALLOWED_TRACKED_DELETIONS and not current_path.exists() and not current_path.is_symlink():
            continue
        if matches_any(path, inventory["copier_managed"]):
            continue
        if matches_any(path, inventory["metadata"]) or matches_any(
            path, inventory["migration_backup"]
        ):
            continue
        if ownership_pattern_matches(path, ".codex/agents/*.toml"):
            current = current_path
            if not current.is_file() or current.is_symlink():
                rejected.append(path)
                continue
            before = require_git_success(repository, "show", f"HEAD:{path}").stdout
            validate_agent_profile_transition(path, before, current.read_bytes())
            continue
        rejected.append(path)
    if rejected:
        raise UpdateValidationError(
            "Copier update changed existing project-owned or unclassified paths: "
            + ", ".join(sorted(rejected))
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
    inspect_project_owned_content(repository)
    inspect_filesystem(repository)
    inspect_external_access_profile(repository)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("."))
    parser.add_argument(
        "--before-update",
        action="store_true",
        help="require a clean Git repository before Copier starts",
    )
    args = parser.parse_args()
    try:
        if args.before_update:
            require_clean_update_start(args.destination.resolve())
        else:
            validate(args.destination)
    except UpdateValidationError as exc:
        print(f"unsafe Copier update result: {exc}", file=sys.stderr)
        return 1
    print("Copier update result validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
