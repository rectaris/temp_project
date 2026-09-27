"""Parse evaluation definitions and freeze one experiment before any run.

This module is root-only evaluation tooling for this repository. It reads the
schema-1 benchmark case, run configuration, environment configuration and
experiment definitions under `evals/`, binds the digest of every input an
experiment uses, derives the schema-2 comparison protocol that
`compare-harness-runs.py` judges, and fixes the complete run matrix.

Resolving launches no model, opens no network socket and writes only below
`.agent-artifacts/evaluations/<experiment-id>/`. The only subprocess it starts
is Git, with an isolated configuration, to build each case's baseline
repository inside that directory.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from types import ModuleType
from typing import Any


SCHEMA_VERSION = 1
EVALS_PREFIX = "evals/"
CAPABILITY_REGISTRY_PATH = "docs/agent/capability-registry.json"
EVALUATIONS_DIRECTORY = (".agent-artifacts", "evaluations")
COMPARISON_COMMAND = "template/.project-agent-workflow/scripts/compare-harness-runs.py"
PROFILE_CHECKER = "template/.project-agent-workflow/scripts/check-harness-profile.py"
HARNESS_PROFILE_CATALOG_PATH = "docs/agent/harness-instructions.json"
REPOSITORY_HARNESS_PROFILE_PATH = "docs/agent/harness-profile.json"
EXPERIMENT_RECORD = "experiment.json"
PROTOCOL_RECORD = "protocol.json"
MATRIX_RECORD = "matrix.json"
WORK_DIRECTORY = ".resolve-work"

MAX_DEFINITION_BYTES = 64 * 1024
MAX_TEXT_BYTES = 64 * 1024
MAX_INSTRUCTION_ASSET_BYTES = 256 * 1024
MAX_REGISTRY_BYTES = 256 * 1024
MAX_FIXTURE_FILE_BYTES = 1024 * 1024
MAX_FIXTURE_FILES = 256
MAX_FIXTURE_ENTRIES = 512
MAX_FIXTURE_TOTAL_BYTES = 8 * 1024 * 1024
MAX_FIXTURE_DEPTH = 16
MAX_SCALAR_BYTES = 400
MAX_PATH_ENTRIES = 64
MAX_INSTRUCTION_ASSETS = 16
MAX_TOOL_VERSIONS = 16
MAX_VALIDATION_COMMANDS = 16
MAX_ARGUMENTS = 64
MAX_ARGUMENT_BYTES = 4096
MAX_TIMEOUT_SECONDS = 7200
MAX_REPETITIONS = 64
MAX_EXPERIMENT_CASES = 64
MIN_CONFIGURATIONS = 2
MAX_CONFIGURATIONS = 8
MAX_ELAPSED_BUDGET_SECONDS = 31_536_000.0
EVIDENCE_FILES_PER_RUN = 4
GIT_TIMEOUT_SECONDS = 60

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")

FIXTURE_KINDS = ("synthetic", "operational")
HOLDOUT_STATES = ("withheld", "not_used", "used_for_tuning")
ORDERINGS = ("declared", "balanced")
SANDBOXES = ("bubblewrap",)
NETWORK_MODES = ("none", "shared_for_provider")
CACHE_POLICIES = ("cold",)
RESOURCE_CONTROLS = ("uncontrolled",)

CASE_KEYS = {
    "schema_version",
    "case_id",
    "suite",
    "category",
    "fixture_kind",
    "holdout",
    "timeout_seconds",
    "allowed_write_paths",
    "protected_paths",
    "validation_commands",
}
CONFIGURATION_KEYS = {
    "schema_version",
    "configuration_id",
    "backend",
    "runtime",
    "model",
    "reasoning",
    "instruction_assets",
    "harness_profile_selection",
    "context_policy",
    "tool_policy",
    "subagent_topology",
    "environment_id",
}
ENVIRONMENT_KEYS = {
    "schema_version",
    "environment_id",
    "sandbox",
    "network",
    "cache_policy",
    "cpu_limit",
    "memory_limit",
}
EXPERIMENT_KEYS = {
    "schema_version",
    "experiment_id",
    "invariant",
    "authority",
    "cases",
    "configurations",
    "comparisons",
    "repetitions",
    "ordering",
    "budget",
    "human_intervention_rule",
    "decision_limits",
}
RUNTIME_KEYS = {"cli_version", "tool_versions"}
REASONING_KEYS = {"supported", "effort"}
SELECTION_REFERENCE_KEYS = {"path"}
COMPARISON_KEYS = {"comparison_id", "baseline", "candidate"}
BUDGET_KEYS = {"max_total_runs", "max_elapsed_seconds"}
DECISION_LIMIT_KEYS = {
    "require_all_critical_pass",
    "min_quality_pass_delta",
    "max_elapsed_ratio",
    "max_cost_ratio",
    "max_additional_interventions",
}

# Every baseline commit is built from these fixed values, so the same fixture
# tree yields the same commit on every host and in every checkout, independent
# of this repository's history, the host clock, the umask and file modes.
BASELINE_IDENTITY = {
    "object_format": "sha256",
    "branch": "baseline",
    "author": "agent-eval baseline <agent-eval-baseline@example.invalid>",
    "committer": "agent-eval baseline <agent-eval-baseline@example.invalid>",
    "timestamp": "946684800 +0000",
    "file_mode": "100644",
    "message": "evaluation baseline\n",
}


class DefinitionError(ValueError):
    """A definition, reference, bound or resolve precondition that refuses."""


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    """Digest the canonical JSON form the comparison command recomputes."""

    return digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


# ---------------------------------------------------------------------------
# Bounded, confined reading


def _reject_constant(name: str) -> Any:
    raise DefinitionError(f"non-finite JSON number is not accepted: {name}")


def parse_json_object(data: bytes, label: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DefinitionError(f"{label} repeats the JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise DefinitionError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise DefinitionError(f"{label} must contain a JSON object")
    return value


def require_evals_path(value: Any, label: str) -> str:
    """Require a normalized repository-relative path inside `evals/`."""

    if not isinstance(value, str) or not value:
        raise DefinitionError(f"{label} must be a nonempty path string")
    if "\\" in value or CONTROL_CHARACTER.search(value):
        raise DefinitionError(f"{label} contains a backslash or control character: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise DefinitionError(f"{label} must be repository-relative, not absolute: {value}")
    if ".." in path.parts:
        raise DefinitionError(f"{label} must not traverse with '..': {value}")
    if path.as_posix() != value or "." in value.split("/"):
        raise DefinitionError(f"{label} must be a normalized path: {value}")
    if not value.startswith(EVALS_PREFIX) or value == EVALS_PREFIX.rstrip("/"):
        raise DefinitionError(f"{label} must name a file inside evals/: {value}")
    return value


def _walk_components(root: Path, relative: str, label: str, *, directory: bool) -> Path:
    """Reject a missing, symlinked or wrongly typed component of `relative`."""

    parts = PurePosixPath(relative).parts
    current = root
    info: os.stat_result | None = None
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError as exc:
            raise DefinitionError(f"{label} does not exist: {relative}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise DefinitionError(f"{label} has a symlinked component: {relative}")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise DefinitionError(f"{label} has a non-directory component: {relative}")
    if info is None:
        raise DefinitionError(f"{label} is empty")
    if directory and not stat.S_ISDIR(info.st_mode):
        raise DefinitionError(f"{label} is not a directory: {relative}")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise DefinitionError(f"{label} is not a regular file: {relative}")
    return current


def _open_confined(root: Path, relative: str, label: str) -> int:
    """Open `relative` below root one component at a time without following links.

    Each directory is opened relative to its parent with O_NOFOLLOW, so a
    component replaced by a symlink after the checks above still refuses.
    """

    parts = PurePosixPath(relative).parts
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    try:
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise DefinitionError(f"{label} root cannot be opened: {root}") from exc
    try:
        for part in parts[:-1]:
            following = os.open(part, directory_flags, dir_fd=current)
            os.close(current)
            current = following
        return os.open(parts[-1], file_flags, dir_fd=current)
    except OSError as exc:
        raise DefinitionError(f"{label} cannot be opened without following a link: {relative}") from exc
    finally:
        os.close(current)


def read_regular(root: Path, relative: str, label: str, limit: int) -> bytes:
    """Read one bounded regular file whose every component is a non-symlink."""

    _walk_components(root, relative, label, directory=False)
    descriptor = _open_confined(root, relative, label)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise DefinitionError(f"{label} is not a regular file: {relative}")
        if info.st_size > limit:
            raise DefinitionError(f"{label} exceeds {limit} bytes: {relative}")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    data = b"".join(chunks)
    if len(data) > limit:
        raise DefinitionError(f"{label} exceeds {limit} bytes: {relative}")
    return data


def read_definition(root: Path, relative: str, label: str) -> tuple[dict[str, Any], bytes]:
    data = read_regular(root, relative, label, MAX_DEFINITION_BYTES)
    return parse_json_object(data, f"{label} {relative}"), data


def read_text(root: Path, relative: str, label: str) -> bytes:
    data = read_regular(root, relative, label, MAX_TEXT_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DefinitionError(f"{label} is not UTF-8: {relative}") from exc
    if not text.strip():
        raise DefinitionError(f"{label} is empty: {relative}")
    return data


# ---------------------------------------------------------------------------
# Scalar checks


def require_exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DefinitionError(f"{label} must be a JSON object")
    missing = sorted(keys - set(value))
    unknown = sorted(set(value) - keys)
    if missing or unknown:
        raise DefinitionError(
            f"{label} has an invalid exact field shape: missing={missing}, unknown={unknown}"
        )
    return value


def require_schema_version(payload: dict[str, Any], label: str) -> None:
    version = payload["schema_version"]
    if type(version) is not int or version != SCHEMA_VERSION:
        raise DefinitionError(f"{label} schema_version must be the integer {SCHEMA_VERSION}")


def require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise DefinitionError(f"{label} must match {ID_PATTERN.pattern}: {value!r}")
    return value


def require_scalar_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DefinitionError(f"{label} must be a nonempty unpadded string")
    if CONTROL_CHARACTER.search(value):
        raise DefinitionError(f"{label} must not contain a control character")
    if len(value.encode("utf-8")) > MAX_SCALAR_BYTES:
        raise DefinitionError(f"{label} exceeds {MAX_SCALAR_BYTES} bytes")
    return value


def require_integer(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise DefinitionError(f"{label} must be an integer from {minimum} to {maximum}")
    return value


def require_number(value: Any, label: str, *, minimum: float | None = None) -> float | int:
    if type(value) not in (int, float) or value != value or value in (float("inf"), float("-inf")):
        raise DefinitionError(f"{label} must be a finite number")
    if minimum is not None and value < minimum:
        raise DefinitionError(f"{label} must be at least {minimum}")
    return value


def require_choice(value: Any, choices: tuple[str, ...], label: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise DefinitionError(f"{label} must be one of {list(choices)}")
    return value


def require_list(value: Any, label: str, *, minimum: int, maximum: int) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise DefinitionError(f"{label} must be a list of {minimum} to {maximum} entries")
    return value


def require_fixture_path(value: Any, label: str) -> str:
    """Require a normalized path relative to a case fixture repository."""

    if not isinstance(value, str) or not value:
        raise DefinitionError(f"{label} must be a nonempty path string")
    if "\\" in value or CONTROL_CHARACTER.search(value):
        raise DefinitionError(f"{label} contains a backslash or control character: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise DefinitionError(f"{label} must stay inside the fixture repository: {value}")
    if path.as_posix() != value or "." in value.split("/"):
        raise DefinitionError(f"{label} must be a normalized path: {value}")
    if ".git" in path.parts:
        raise DefinitionError(f"{label} must not name Git metadata: {value}")
    if len(value.encode("utf-8")) > MAX_SCALAR_BYTES:
        raise DefinitionError(f"{label} exceeds {MAX_SCALAR_BYTES} bytes")
    return value


def require_unique(values: list[str], label: str) -> list[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise DefinitionError(f"{label} repeats {value!r}")
        seen.add(value)
    return values


# ---------------------------------------------------------------------------
# Fixture trees and deterministic baselines


def read_fixture_tree(root: Path, relative: str, label: str) -> list[tuple[str, bytes]]:
    """Read every regular file below one fixture directory, sorted by path."""

    directory = _walk_components(root, relative, label, directory=True)
    files: list[tuple[str, bytes]] = []
    total = 0
    entry_count = 0

    def visit(current: Path, prefix: str, depth: int) -> None:
        nonlocal total, entry_count
        if depth > MAX_FIXTURE_DEPTH:
            raise DefinitionError(f"{label} is nested deeper than {MAX_FIXTURE_DEPTH}: {relative}")
        entries = []
        with os.scandir(current) as iterator:
            # Files and directories share one bound, counted before sorting,
            # so empty directories cannot make the traversal unbounded.
            for entry in iterator:
                entry_count += 1
                if entry_count > MAX_FIXTURE_ENTRIES:
                    raise DefinitionError(
                        f"{label} holds more than {MAX_FIXTURE_ENTRIES} files and directories: "
                        f"{relative}"
                    )
                entries.append(entry)
        entries.sort(key=lambda entry: entry.name)
        for entry in entries:
            name = entry.name
            try:
                name.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise DefinitionError(f"{label} has a non-UTF-8 file name below {relative}") from exc
            member = f"{prefix}{name}"
            require_fixture_path(member, f"{label} member")
            if entry.is_symlink():
                raise DefinitionError(f"{label} contains a symlink: {relative}/{member}")
            if entry.is_dir(follow_symlinks=False):
                visit(Path(entry.path), member + "/", depth + 1)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise DefinitionError(f"{label} contains a non-regular file: {relative}/{member}")
            if len(files) >= MAX_FIXTURE_FILES:
                raise DefinitionError(f"{label} holds more than {MAX_FIXTURE_FILES} files: {relative}")
            data = read_regular(root, f"{relative}/{member}", f"{label} file", MAX_FIXTURE_FILE_BYTES)
            total += len(data)
            if total > MAX_FIXTURE_TOTAL_BYTES:
                raise DefinitionError(
                    f"{label} exceeds {MAX_FIXTURE_TOTAL_BYTES} bytes in total: {relative}"
                )
            files.append((member, data))

    visit(directory, "", 0)
    if not files:
        raise DefinitionError(f"{label} holds no file: {relative}")
    return sorted(files)


def fixture_tree_manifest(files: list[tuple[str, bytes]]) -> list[dict[str, str]]:
    return [{"path": path, "digest": digest_bytes(data)} for path, data in files]


def _quote_fast_import_path(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def fast_import_stream(files: list[tuple[str, bytes]]) -> bytes:
    identity = BASELINE_IDENTITY
    message = identity["message"].encode("utf-8")
    chunks = [
        f"commit refs/heads/{identity['branch']}\n".encode("ascii"),
        f"author {identity['author']} {identity['timestamp']}\n".encode("utf-8"),
        f"committer {identity['committer']} {identity['timestamp']}\n".encode("utf-8"),
        f"data {len(message)}\n".encode("ascii"),
        message,
    ]
    for path, data in files:
        chunks.append(
            f"M {identity['file_mode']} inline {_quote_fast_import_path(path)}\n".encode("utf-8")
        )
        chunks.append(f"data {len(data)}\n".encode("ascii"))
        chunks.append(data)
        chunks.append(b"\n")
    chunks.append(b"done\n")
    return b"".join(chunks)


def git_environment(scratch: Path) -> dict[str, str]:
    """Return a Git environment that reads no host or user configuration."""

    home = scratch / "home"
    temporary = scratch / "tmp"
    home.mkdir(parents=True, exist_ok=True)
    temporary.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "TMPDIR": str(temporary),
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


def _run_git(arguments: list[str], environment: dict[str, str], *, stdin: bytes = b"") -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            input=stdin,
            capture_output=True,
            env=environment,
            cwd=environment["TMPDIR"],
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise DefinitionError("git is required to build fixture baselines") from exc
    except subprocess.TimeoutExpired as exc:
        raise DefinitionError(f"git {arguments[0]} exceeded {GIT_TIMEOUT_SECONDS} seconds") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise DefinitionError(
            f"git {arguments[0]} failed while building a fixture baseline: "
            + (detail[-1] if detail else f"exit {result.returncode}")
        )
    return result.stdout.decode("utf-8", "replace").strip()


def build_fixture_baseline(
    files: list[tuple[str, bytes]], destination: Path, scratch: Path
) -> str:
    """Build a bare SHA-256 repository holding one fixed baseline commit.

    The commit carries the fixed identity, timestamp and file mode in
    BASELINE_IDENTITY, so its id depends only on the fixture paths and bytes.
    Returns the 64-hex commit id.
    """

    if os.path.lexists(destination):
        raise DefinitionError(f"fixture baseline destination already exists: {destination}")
    environment = git_environment(scratch)
    identity = BASELINE_IDENTITY
    _run_git(
        [
            "init",
            "--bare",
            "--quiet",
            f"--object-format={identity['object_format']}",
            "--template=",
            f"--initial-branch={identity['branch']}",
            str(destination),
        ],
        environment,
    )
    _run_git(
        [f"--git-dir={destination}", "fast-import", "--quiet", "--done"],
        environment,
        stdin=fast_import_stream(files),
    )
    commit = _run_git(
        [
            f"--git-dir={destination}",
            "rev-parse",
            "--verify",
            f"refs/heads/{identity['branch']}^{{commit}}",
        ],
        environment,
    )
    if not re.fullmatch(r"[0-9a-f]{64}", commit):
        raise DefinitionError(f"fixture baseline is not a SHA-256 commit id: {commit!r}")
    return commit


# ---------------------------------------------------------------------------
# Definitions


def parse_case(root: Path, reference: Any, index: int) -> dict[str, Any]:
    label = f"experiment cases[{index}]"
    if not isinstance(reference, str) or reference.count("/") != 1:
        raise DefinitionError(f"{label} must name one case as '<suite>/<case-id>'")
    suite, case_id = reference.split("/")
    require_id(suite, f"{label} suite")
    require_id(case_id, f"{label} case id")
    directory = f"evals/cases/{suite}/{case_id}"
    definition_path = f"{directory}/case.json"
    payload, data = read_definition(root, definition_path, "benchmark case")
    label = f"benchmark case {reference}"
    require_exact_keys(payload, CASE_KEYS, label)
    require_schema_version(payload, label)
    if require_id(payload["case_id"], f"{label} case_id") != case_id:
        raise DefinitionError(f"{label} case_id differs from its directory name")
    if require_id(payload["suite"], f"{label} suite") != suite:
        raise DefinitionError(f"{label} suite differs from its directory name")
    allowed = require_unique(
        [
            require_fixture_path(item, f"{label} allowed_write_paths entry")
            for item in require_list(
                payload["allowed_write_paths"],
                f"{label} allowed_write_paths",
                minimum=1,
                maximum=MAX_PATH_ENTRIES,
            )
        ],
        f"{label} allowed_write_paths",
    )
    protected = require_unique(
        [
            require_fixture_path(item, f"{label} protected_paths entry")
            for item in require_list(
                payload["protected_paths"],
                f"{label} protected_paths",
                minimum=0,
                maximum=MAX_PATH_ENTRIES,
            )
        ],
        f"{label} protected_paths",
    )
    overlap = sorted(set(allowed) & set(protected))
    if overlap:
        raise DefinitionError(f"{label} declares paths both allowed and protected: {overlap}")
    commands: list[list[str]] = []
    for command_index, command in enumerate(
        require_list(
            payload["validation_commands"],
            f"{label} validation_commands",
            minimum=1,
            maximum=MAX_VALIDATION_COMMANDS,
        )
    ):
        command_label = f"{label} validation_commands[{command_index}]"
        argv = require_list(command, command_label, minimum=1, maximum=MAX_ARGUMENTS)
        for argument in argv:
            if (
                not isinstance(argument, str)
                or not argument
                or "\x00" in argument
                or len(argument.encode("utf-8")) > MAX_ARGUMENT_BYTES
            ):
                raise DefinitionError(
                    f"{command_label} arguments must be nonempty strings of at most "
                    f"{MAX_ARGUMENT_BYTES} bytes without NUL"
                )
        commands.append(list(argv))
    task_path = f"{directory}/task.md"
    acceptance_path = f"{directory}/acceptance.md"
    repository_path = f"{directory}/repository"
    task = read_text(root, task_path, f"{label} task")
    acceptance = read_text(root, acceptance_path, f"{label} acceptance")
    files = read_fixture_tree(root, repository_path, f"{label} fixture tree")
    manifest = fixture_tree_manifest(files)
    return {
        "reference": reference,
        "case_id": case_id,
        "suite": suite,
        "category": require_id(payload["category"], f"{label} category"),
        "fixture_kind": require_choice(payload["fixture_kind"], FIXTURE_KINDS, f"{label} fixture_kind"),
        "holdout": require_choice(payload["holdout"], HOLDOUT_STATES, f"{label} holdout"),
        "timeout_seconds": require_integer(
            payload["timeout_seconds"],
            f"{label} timeout_seconds",
            minimum=1,
            maximum=MAX_TIMEOUT_SECONDS,
        ),
        "allowed_write_paths": allowed,
        "protected_paths": protected,
        "validation_commands": commands,
        # The deterministic validation commands are the case rubric: they alone
        # decide acceptance, so their canonical digest is the rubric digest.
        "validation_commands_digest": canonical_digest(commands),
        "definition": {"path": definition_path, "digest": digest_bytes(data)},
        "task": {"path": task_path, "digest": digest_bytes(task)},
        "acceptance": {"path": acceptance_path, "digest": digest_bytes(acceptance)},
        "fixture_tree": {
            "path": repository_path,
            "digest": canonical_digest(manifest),
            "file_count": len(manifest),
            "files": manifest,
        },
        "_files": files,
    }


def parse_environment(root: Path, environment_id: str) -> dict[str, Any]:
    definition_path = f"evals/environments/{environment_id}.json"
    payload, data = read_definition(root, definition_path, "environment configuration")
    label = f"environment configuration {environment_id}"
    require_exact_keys(payload, ENVIRONMENT_KEYS, label)
    require_schema_version(payload, label)
    if require_id(payload["environment_id"], f"{label} environment_id") != environment_id:
        raise DefinitionError(f"{label} environment_id differs from its file name")
    return {
        "environment_id": environment_id,
        "definition": {"path": definition_path, "digest": digest_bytes(data)},
        "sandbox": require_choice(payload["sandbox"], SANDBOXES, f"{label} sandbox"),
        "network": require_choice(payload["network"], NETWORK_MODES, f"{label} network"),
        "cache_policy": require_choice(payload["cache_policy"], CACHE_POLICIES, f"{label} cache_policy"),
        "cpu_limit": require_choice(payload["cpu_limit"], RESOURCE_CONTROLS, f"{label} cpu_limit"),
        "memory_limit": require_choice(
            payload["memory_limit"], RESOURCE_CONTROLS, f"{label} memory_limit"
        ),
    }


def parse_harness_profile_selection(
    root: Path, value: Any, label: str, profile_checker: ModuleType
) -> dict[str, Any] | None:
    """Validate an optional Harness Profile selection with the existing checker.

    The selection is either the repository's own `docs/agent/harness-profile.json`
    or a selection document under `evals/`. `check-harness-profile.py` parses it
    and resolves it against the repository catalog exactly as its `check`
    command does, so the run configuration records which Harness Profile it
    selects without interpreting or redefining Harness Profile semantics.
    """

    if value is None:
        return None
    reference = require_exact_keys(value, SELECTION_REFERENCE_KEYS, f"{label} harness_profile_selection")
    path = reference["path"]
    if path != REPOSITORY_HARNESS_PROFILE_PATH:
        path = require_evals_path(path, f"{label} harness_profile_selection path")
    data = read_regular(root, path, "Harness Profile selection", MAX_DEFINITION_BYTES)
    parse_json_object(data, f"Harness Profile selection {path}")
    catalog_data = read_regular(
        root, HARNESS_PROFILE_CATALOG_PATH, "Harness Profile catalog", MAX_DEFINITION_BYTES
    )
    try:
        catalog, catalog_digest = profile_checker.parse_catalog(
            root / HARNESS_PROFILE_CATALOG_PATH, root
        )
        profile, profile_digest = profile_checker.parse_profile(root / path)
        selected = profile_checker.resolve(catalog, profile, root)
    except (OSError, profile_checker.ProfileError) as exc:
        raise DefinitionError(
            f"{label} harness_profile_selection is refused by check-harness-profile.py: {exc}"
        ) from exc
    if profile_digest != digest_bytes(data) or catalog_digest != digest_bytes(catalog_data):
        raise DefinitionError(f"{label} Harness Profile inputs changed while they were read")
    return {
        "path": path,
        "digest": profile_digest,
        "catalog": {"path": HARNESS_PROFILE_CATALOG_PATH, "digest": catalog_digest},
        "selected_revisions": [
            {key: item[key] for key in ("id", "revision", "content_digest", "asset_path")}
            for item in selected
        ],
    }


def parse_configuration(
    root: Path, configuration_id: str, profile_checker: ModuleType
) -> dict[str, Any]:
    definition_path = f"evals/configurations/{configuration_id}.json"
    payload, data = read_definition(root, definition_path, "run configuration")
    label = f"run configuration {configuration_id}"
    require_exact_keys(payload, CONFIGURATION_KEYS, label)
    require_schema_version(payload, label)
    if require_id(payload["configuration_id"], f"{label} configuration_id") != configuration_id:
        raise DefinitionError(f"{label} configuration_id differs from its file name")
    runtime = require_exact_keys(payload["runtime"], RUNTIME_KEYS, f"{label} runtime")
    tool_versions = runtime["tool_versions"]
    if not isinstance(tool_versions, dict) or len(tool_versions) > MAX_TOOL_VERSIONS:
        raise DefinitionError(
            f"{label} runtime tool_versions must be an object of at most {MAX_TOOL_VERSIONS} entries"
        )
    parsed_tools = {
        require_scalar_text(name, f"{label} runtime tool name"): require_scalar_text(
            version, f"{label} runtime tool_versions[{name}]"
        )
        for name, version in tool_versions.items()
    }
    reasoning = require_exact_keys(payload["reasoning"], REASONING_KEYS, f"{label} reasoning")
    if type(reasoning["supported"]) is not bool:
        raise DefinitionError(f"{label} reasoning supported must be a boolean")
    if reasoning["supported"]:
        reasoning_settings = {
            "supported": True,
            "effort": require_scalar_text(reasoning["effort"], f"{label} reasoning effort"),
        }
    elif reasoning["effort"] is not None:
        raise DefinitionError(f"{label} reasoning effort must be null when reasoning is unsupported")
    else:
        reasoning_settings = {"supported": False, "effort": None}
    asset_paths = require_unique(
        [
            require_evals_path(item, f"{label} instruction_assets entry")
            for item in require_list(
                payload["instruction_assets"],
                f"{label} instruction_assets",
                minimum=1,
                maximum=MAX_INSTRUCTION_ASSETS,
            )
        ],
        f"{label} instruction_assets",
    )
    assets = [
        {
            "path": path,
            "digest": digest_bytes(
                read_regular(root, path, "instruction asset", MAX_INSTRUCTION_ASSET_BYTES)
            ),
        }
        for path in asset_paths
    ]
    selection = parse_harness_profile_selection(
        root, payload["harness_profile_selection"], label, profile_checker
    )
    if selection is not None:
        overlap = sorted(
            {item["asset_path"] for item in selection["selected_revisions"]} & set(asset_paths)
        )
        if overlap:
            raise DefinitionError(
                f"{label} names Harness Profile assets as instruction_assets too: {overlap}"
            )
    return {
        "configuration_id": configuration_id,
        "definition": {"path": definition_path, "digest": digest_bytes(data)},
        "backend": require_id(payload["backend"], f"{label} backend"),
        "runtime": {
            "cli_version": require_scalar_text(runtime["cli_version"], f"{label} runtime cli_version"),
            "tool_versions": parsed_tools,
        },
        "model": require_scalar_text(payload["model"], f"{label} model"),
        "reasoning_settings": reasoning_settings,
        "instruction_assets": assets,
        "harness_profile_selection": selection,
        "context_policy": require_scalar_text(payload["context_policy"], f"{label} context_policy"),
        "tool_policy": require_scalar_text(payload["tool_policy"], f"{label} tool_policy"),
        "subagent_topology": require_scalar_text(
            payload["subagent_topology"], f"{label} subagent_topology"
        ),
        "environment_id": require_id(payload["environment_id"], f"{label} environment_id"),
    }


def require_experiment_path(value: Any) -> tuple[str, str]:
    path = require_evals_path(value, "experiment definition path")
    parts = PurePosixPath(path).parts
    if len(parts) != 3 or parts[1] != "experiments" or not parts[2].endswith(".json"):
        raise DefinitionError(f"experiment definition must be evals/experiments/<id>.json: {path}")
    return path, require_id(parts[2][: -len(".json")], "experiment file name")


def parse_experiment(root: Path, experiment_path: Any) -> dict[str, Any]:
    path, stem = require_experiment_path(experiment_path)
    payload, data = read_definition(root, path, "experiment definition")
    label = f"experiment definition {stem}"
    require_exact_keys(payload, EXPERIMENT_KEYS, label)
    require_schema_version(payload, label)
    if require_id(payload["experiment_id"], f"{label} experiment_id") != stem:
        raise DefinitionError(f"{label} experiment_id differs from its file name")

    case_references = require_list(
        payload["cases"], f"{label} cases", minimum=1, maximum=MAX_EXPERIMENT_CASES
    )
    require_unique([str(item) for item in case_references], f"{label} cases")
    configuration_ids = require_unique(
        [
            require_id(item, f"{label} configurations entry")
            for item in require_list(
                payload["configurations"],
                f"{label} configurations",
                minimum=MIN_CONFIGURATIONS,
                maximum=MAX_CONFIGURATIONS,
            )
        ],
        f"{label} configurations",
    )
    comparisons: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    pair_limit = len(configuration_ids) * (len(configuration_ids) - 1)
    for index, item in enumerate(
        require_list(payload["comparisons"], f"{label} comparisons", minimum=1, maximum=pair_limit)
    ):
        entry = require_exact_keys(item, COMPARISON_KEYS, f"{label} comparisons[{index}]")
        comparison_id = require_id(entry["comparison_id"], f"{label} comparison_id")
        if comparison_id in seen_ids:
            raise DefinitionError(f"{label} repeats comparison_id {comparison_id!r}")
        baseline = require_id(entry["baseline"], f"{label} comparison {comparison_id} baseline")
        candidate = require_id(entry["candidate"], f"{label} comparison {comparison_id} candidate")
        for role, configuration_id in (("baseline", baseline), ("candidate", candidate)):
            if configuration_id not in configuration_ids:
                raise DefinitionError(
                    f"{label} comparison {comparison_id} names an undeclared {role} "
                    f"configuration: {configuration_id}"
                )
        if baseline == candidate:
            raise DefinitionError(f"{label} comparison {comparison_id} pairs a configuration with itself")
        if (baseline, candidate) in seen_pairs:
            raise DefinitionError(f"{label} repeats the pair {baseline} -> {candidate}")
        seen_ids.add(comparison_id)
        seen_pairs.add((baseline, candidate))
        comparisons.append(
            {"comparison_id": comparison_id, "baseline": baseline, "candidate": candidate}
        )

    budget = require_exact_keys(payload["budget"], BUDGET_KEYS, f"{label} budget")
    limits = require_exact_keys(payload["decision_limits"], DECISION_LIMIT_KEYS, f"{label} decision_limits")
    if limits["require_all_critical_pass"] is not True:
        raise DefinitionError(f"{label} decision_limits require_all_critical_pass must be true")
    max_elapsed = require_number(
        budget["max_elapsed_seconds"], f"{label} budget max_elapsed_seconds", minimum=0.0
    )
    if max_elapsed <= 0 or max_elapsed > MAX_ELAPSED_BUDGET_SECONDS:
        raise DefinitionError(
            f"{label} budget max_elapsed_seconds must be above 0 and at most "
            f"{MAX_ELAPSED_BUDGET_SECONDS}"
        )
    return {
        "path": path,
        "digest": digest_bytes(data),
        "experiment_id": stem,
        "invariant": require_scalar_text(payload["invariant"], f"{label} invariant"),
        "authority": require_scalar_text(payload["authority"], f"{label} authority"),
        "case_references": case_references,
        "configuration_ids": configuration_ids,
        "comparisons": comparisons,
        "repetitions": require_integer(
            payload["repetitions"], f"{label} repetitions", minimum=1, maximum=MAX_REPETITIONS
        ),
        "ordering": require_choice(payload["ordering"], ORDERINGS, f"{label} ordering"),
        "budget": {
            "max_total_runs": require_integer(
                budget["max_total_runs"], f"{label} budget max_total_runs", minimum=1, maximum=1_000_000
            ),
            "max_elapsed_seconds": max_elapsed,
        },
        "human_intervention_rule": require_scalar_text(
            payload["human_intervention_rule"], f"{label} human_intervention_rule"
        ),
        "decision_limits": {
            "require_all_critical_pass": True,
            "min_quality_pass_delta": require_number(
                limits["min_quality_pass_delta"], f"{label} decision_limits min_quality_pass_delta"
            ),
            "max_elapsed_ratio": require_number(
                limits["max_elapsed_ratio"], f"{label} decision_limits max_elapsed_ratio", minimum=0.0
            ),
            "max_cost_ratio": require_number(
                limits["max_cost_ratio"], f"{label} decision_limits max_cost_ratio", minimum=0.0
            ),
            "max_additional_interventions": require_integer(
                limits["max_additional_interventions"],
                f"{label} decision_limits max_additional_interventions",
                minimum=0,
                maximum=1_000_000,
            ),
        },
    }


# ---------------------------------------------------------------------------
# Resolution


def load_tool_module(tool_root: Path, relative: str, name: str) -> ModuleType:
    """Load an existing command whose own parser judges an input."""

    path = tool_root / relative
    if not path.is_file():
        raise DefinitionError(f"required command is missing: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DefinitionError(f"required command cannot be loaded: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Loading a command must not write a bytecode cache beside it.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def configuration_dimensions(
    configuration: dict[str, Any], registry_digest: str, environment_digest: str
) -> dict[str, Any]:
    selection = configuration["harness_profile_selection"]
    asset_digests = {asset["path"]: asset["digest"] for asset in configuration["instruction_assets"]}
    if selection is not None:
        # The selected supplemental assets are instructions the configuration
        # uses, so they are bound beside its declared assets.
        asset_digests.update(
            {item["asset_path"]: item["content_digest"] for item in selection["selected_revisions"]}
        )
    return {
        "harness": {"backend": configuration["backend"], "runtime": configuration["runtime"]},
        "declared_model": configuration["model"],
        "reasoning_settings": configuration["reasoning_settings"],
        "instructions": {
            "instruction_asset_digests": asset_digests,
            "harness_profile_selection_digest": None if selection is None else selection["digest"],
        },
        "capability_registry_digest": registry_digest,
        "context_policy": configuration["context_policy"],
        "tool_policy": configuration["tool_policy"],
        "subagent_topology": configuration["subagent_topology"],
        "environment_configuration_digest": environment_digest,
    }


def order_runs(
    cases: list[dict[str, Any]],
    configuration_ids: list[str],
    repetitions: int,
    ordering: str,
) -> list[dict[str, Any]]:
    """List every case, configuration and repetition cell in execution order.

    Declared ordering runs the configurations in declared order for every case
    of every repetition. Balanced ordering rotates that order by one position
    per repetition, so with two configurations the one that runs first
    alternates between repetitions.
    """

    runs: list[dict[str, Any]] = []
    count = len(configuration_ids)
    for repetition in range(1, repetitions + 1):
        shift = (repetition - 1) % count if ordering == "balanced" else 0
        order = configuration_ids[shift:] + configuration_ids[:shift]
        for case in cases:
            for configuration_id in order:
                order_number = len(runs) + 1
                runs.append(
                    {
                        "order": order_number,
                        # Ids may contain hyphens, so joining them could name two
                        # cells alike. The execution position is unique instead.
                        "run_id": f"run-{order_number:03d}",
                        "repetition": repetition,
                        "case_id": case["case_id"],
                        "configuration_id": configuration_id,
                    }
                )
    require_unique([run["run_id"] for run in runs], "run matrix run ids")
    return runs


def require_run_count_bounds(
    experiment: dict[str, Any], run_count: int, comparison: ModuleType
) -> int:
    """Refuse a run count above its budget or one comparison invocation.

    The count follows from the experiment alone, so this runs before any case
    content is read. Returns the comparison input file count.
    """

    budget = experiment["budget"]
    if run_count > budget["max_total_runs"]:
        raise DefinitionError(
            f"the {run_count}-run matrix exceeds the declared budget of "
            f"{budget['max_total_runs']} runs"
        )
    if run_count > comparison.MAX_OBSERVATIONS:
        raise DefinitionError(
            f"the {run_count}-run matrix exceeds the comparison command's "
            f"{comparison.MAX_OBSERVATIONS}-observation limit"
        )
    input_files = 1 + run_count * (1 + EVIDENCE_FILES_PER_RUN)
    if input_files > comparison.MAX_INPUT_FILES:
        raise DefinitionError(
            f"the {run_count}-run matrix needs {input_files} comparison input files "
            f"(one protocol, one observation and {EVIDENCE_FILES_PER_RUN} evidence files per run), "
            f"above the comparison command's {comparison.MAX_INPUT_FILES}-file limit"
        )
    return input_files


def require_matrix_bounds(
    experiment: dict[str, Any], cases: list[dict[str, Any]], run_count: int, comparison: ModuleType
) -> dict[str, Any]:
    """Refuse a matrix that exceeds its budget or one comparison invocation."""

    input_files = require_run_count_bounds(experiment, run_count, comparison)
    budget = experiment["budget"]
    worst_case = sum(case["timeout_seconds"] for case in cases) * (
        len(experiment["configuration_ids"]) * experiment["repetitions"]
    )
    if worst_case > budget["max_elapsed_seconds"]:
        raise DefinitionError(
            f"the matrix's worst-case elapsed time of {worst_case} seconds exceeds the declared "
            f"budget of {budget['max_elapsed_seconds']} seconds"
        )
    return {
        "budget_max_total_runs": budget["max_total_runs"],
        "budget_max_elapsed_seconds": budget["max_elapsed_seconds"],
        "worst_case_elapsed_seconds": worst_case,
        "evidence_files_per_run": EVIDENCE_FILES_PER_RUN,
        "comparison_input_files": input_files,
        "comparison_max_input_files": comparison.MAX_INPUT_FILES,
        "comparison_max_observations": comparison.MAX_OBSERVATIONS,
        "comparison_max_file_bytes": comparison.MAX_INPUT_BYTES,
    }


def evaluation_directory(root: Path, experiment_id: str) -> Path:
    """Return the experiment directory after refusing symlinked ancestors."""

    current = root
    for part in EVALUATIONS_DIRECTORY:
        current = current / part
        if os.path.islink(current) or (os.path.lexists(current) and not current.is_dir()):
            raise DefinitionError(f"evaluation output ancestor is not a plain directory: {current}")
    return current / experiment_id


def write_record(path: Path, value: Any) -> bytes:
    data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
    finally:
        os.close(descriptor)
    return data


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_experiment(
    root: Path,
    experiment_path: str,
    *,
    tool_root: Path | None = None,
    frozen_at: str | None = None,
) -> dict[str, Any]:
    """Freeze one experiment and return its resolved record.

    Every definition, reference, bound and budget is checked before the first
    write. The only writes are the experiment directory and the files below it.
    """

    root = root.resolve()
    tool_root = (tool_root or Path(__file__).resolve().parents[2]).resolve()
    comparison = load_tool_module(tool_root, COMPARISON_COMMAND, "agent_eval_compare_harness_runs")
    profile_checker = load_tool_module(tool_root, PROFILE_CHECKER, "agent_eval_check_harness_profile")

    experiment = parse_experiment(root, experiment_path)
    require_run_count_bounds(
        experiment,
        len(experiment["case_references"])
        * len(experiment["configuration_ids"])
        * experiment["repetitions"],
        comparison,
    )
    cases = [
        parse_case(root, reference, index)
        for index, reference in enumerate(experiment["case_references"])
    ]
    require_unique([case["case_id"] for case in cases], "experiment case ids")
    holdout_states = sorted({case["holdout"] for case in cases})
    if len(holdout_states) != 1:
        raise DefinitionError(
            f"experiment cases must share one holdout status, found {holdout_states}"
        )
    configurations = [
        parse_configuration(root, item, profile_checker) for item in experiment["configuration_ids"]
    ]
    environments: dict[str, dict[str, Any]] = {}
    for configuration in configurations:
        environment_id = configuration["environment_id"]
        if environment_id not in environments:
            environments[environment_id] = parse_environment(root, environment_id)
    registry_data = read_regular(
        root, CAPABILITY_REGISTRY_PATH, "capability registry", MAX_REGISTRY_BYTES
    )
    parse_json_object(registry_data, "capability registry")
    registry = {"path": CAPABILITY_REGISTRY_PATH, "digest": digest_bytes(registry_data)}
    for configuration in configurations:
        environment = environments[configuration["environment_id"]]
        configuration["dimensions"] = configuration_dimensions(
            configuration, registry["digest"], environment["definition"]["digest"]
        )
        configuration["configuration_digest"] = comparison.canonical_digest(
            configuration["dimensions"]
        )

    runs = order_runs(
        cases, experiment["configuration_ids"], experiment["repetitions"], experiment["ordering"]
    )
    limits = require_matrix_bounds(experiment, cases, len(runs), comparison)

    output = evaluation_directory(root, experiment["experiment_id"])
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.mkdir(output, 0o755)
    except FileExistsError as exc:
        raise DefinitionError(
            f"experiment directory already exists; a changed definition needs a new "
            f"experiment id: {output}"
        ) from exc
    try:
        record = _write_resolved(
            output, experiment, cases, configurations, environments, registry, runs, limits,
            comparison, tool_root, frozen_at or utc_now(),
        )
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return record


def _write_resolved(
    output: Path,
    experiment: dict[str, Any],
    cases: list[dict[str, Any]],
    configurations: list[dict[str, Any]],
    environments: dict[str, dict[str, Any]],
    registry: dict[str, str],
    runs: list[dict[str, Any]],
    limits: dict[str, Any],
    comparison: ModuleType,
    tool_root: Path,
    frozen_at: str,
) -> dict[str, Any]:
    work = output / WORK_DIRECTORY
    work.mkdir()
    for index, case in enumerate(cases):
        commit = build_fixture_baseline(
            case.pop("_files"), work / "baselines" / f"{index}.git", work / "scratch"
        )
        case["baseline_commit"] = commit
        case["repository_baseline"] = f"sha256:{commit}"
    shutil.rmtree(work)

    by_case = {case["case_id"]: case for case in cases}
    by_configuration = {item["configuration_id"]: item for item in configurations}
    for run in runs:
        case = by_case[run["case_id"]]
        run["suite"] = case["suite"]
        run["repository_baseline"] = case["repository_baseline"]
        run["timeout_seconds"] = case["timeout_seconds"]
        run["configuration_digest"] = by_configuration[run["configuration_id"]]["configuration_digest"]

    protocol = {
        "schema_version": comparison.NAMED_SCHEMA_VERSION,
        "protocol_id": experiment["experiment_id"],
        "invariant_digest": comparison.digest_text(experiment["invariant"]),
        "authority_digest": comparison.digest_text(experiment["authority"]),
        "configurations": [
            {
                "configuration_id": item["configuration_id"],
                "dimensions": item["dimensions"],
                "configuration_digest": item["configuration_digest"],
            }
            for item in configurations
        ],
        "comparisons": experiment["comparisons"],
        "cases": [
            {
                "case_id": case["case_id"],
                "task_digest": case["task"]["digest"],
                "acceptance_digest": case["acceptance"]["digest"],
                "rubric_digest": case["validation_commands_digest"],
                "fixture_kind": case["fixture_kind"],
                "repository_baseline": case["repository_baseline"],
            }
            for case in cases
        ],
        "repetitions": experiment["repetitions"],
        "budget": experiment["budget"],
        "metric_boundaries": {
            "elapsed_seconds": comparison.ELAPSED_BOUNDARY,
            "billed_cost": comparison.COST_BOUNDARY,
            "human_interventions": experiment["human_intervention_rule"],
        },
        "decision_limits": experiment["decision_limits"],
        "freeze": {
            "declared_frozen_at": frozen_at,
            "holdout_status": cases[0]["holdout"],
            "ordering_evidence": None,
        },
    }
    protocol_path = output / PROTOCOL_RECORD
    protocol_bytes = write_record(protocol_path, protocol)
    try:
        parsed = comparison.parse_protocol(str(protocol_path))
    except comparison.ComparisonError as exc:
        raise DefinitionError(f"the comparison command refuses the derived protocol: {exc}") from exc
    for item in configurations:
        if parsed["configurations"][item["configuration_id"]]["configuration_digest"] != item[
            "configuration_digest"
        ]:
            raise DefinitionError("the derived protocol disagrees with its configuration digests")

    matrix = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "evaluation_run_matrix",
        "experiment_id": experiment["experiment_id"],
        "ordering": experiment["ordering"],
        "repetitions": experiment["repetitions"],
        "case_order": [case["case_id"] for case in cases],
        "configuration_order": experiment["configuration_ids"],
        "run_count": len(runs),
        "limits": limits,
        "runs": runs,
    }
    matrix_bytes = write_record(output / MATRIX_RECORD, matrix)

    comparison_bytes = (tool_root / COMPARISON_COMMAND).read_bytes()
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "resolved_evaluation_experiment",
        "experiment_id": experiment["experiment_id"],
        "frozen_at": frozen_at,
        "definition": {"path": experiment["path"], "digest": experiment["digest"]},
        "invariant_digest": protocol["invariant_digest"],
        "authority_digest": protocol["authority_digest"],
        "holdout_status": cases[0]["holdout"],
        "ordering": experiment["ordering"],
        "repetitions": experiment["repetitions"],
        "run_count": len(runs),
        "baseline_identity": BASELINE_IDENTITY,
        "capability_registry": registry,
        "cases": cases,
        "configurations": configurations,
        "environments": [environments[key] for key in sorted(environments)],
        "comparison_command": {"path": COMPARISON_COMMAND, "digest": digest_bytes(comparison_bytes)},
        "protocol": {"path": PROTOCOL_RECORD, "digest": digest_bytes(protocol_bytes)},
        "matrix": {"path": MATRIX_RECORD, "digest": digest_bytes(matrix_bytes)},
    }
    write_record(output / EXPERIMENT_RECORD, record)
    record["output_directory"] = str(output)
    return record
