#!/usr/bin/env python3
"""Verify a downstream Copier update in a disposable clone."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Sequence


SCHEMA_VERSION = 1
MANIFEST_NAME = "verification-manifest.json"
ANSWERS_PATH = ".copier-answers.yml"
ISOLATED_SOURCE_PATH = "../source"
# Copier decides whether a recorded template source names a repository to clone or a
# directory on this machine, and it uses these exact rules to do it. They are
# reproduced rather than approximated: a value this helper called remote while Copier
# would read it as a local path would be verified against a source the real update
# never uses, and the run would report a success the project could not reproduce.
GIT_ALIAS_REPLACEMENTS = (
    (re.compile(r"^gh:/?(.*\.git)$"), r"https://github.com/\1"),
    (re.compile(r"^gh:/?(.*)$"), r"https://github.com/\1.git"),
    (re.compile(r"^gl:/?(.*\.git)$"), r"https://gitlab.com/\1"),
    (re.compile(r"^gl:/?(.*)$"), r"https://gitlab.com/\1.git"),
)
GIT_PREFIXES = ("git@", "git://", "git+", "https://github.com/", "https://gitlab.com/")
GIT_POSTFIX = ".git"
# Being a repository is not the same as being out of reach. A local directory may be a
# repository Copier would clone, and substituting the isolated checkout for it would
# skip the absolute, escaping and overlapping refusals that a path on this machine
# must still face, so only an address carried over the network is substituted.
NETWORK_SCHEME_RE = re.compile(r"^(?:git|ssh|https?)://")
SCP_ADDRESS_RE = re.compile(r"^[^/\s:]+@[^/\s:]+:")
WORKFLOW_DIR = ".project-agent-workflow"
UPDATE_WRAPPER = f"{WORKFLOW_DIR}/scripts/update-from-copier.sh"
UPDATE_VALIDATOR = f"{WORKFLOW_DIR}/scripts/validate-copier-update.py"
CHANGE_VALIDATOR = f"{WORKFLOW_DIR}/scripts/validate-changes.py"
OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
VERSION_RE = re.compile(r"^v(?P<major>[0-9]+)(?:\.|$)")
SHARED_INDEX_RE = re.compile(r"^sharedindex\.[0-9a-f]{40,64}$")
SAFE_GIT_CONFIG = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]
MAX_GIT_STATE_FILE_BYTES = 64 * 1024 * 1024


class VerificationStop(RuntimeError):
    """A bounded verification result that must be recorded."""

    def __init__(self, result: str, reason_code: str, detail: str):
        super().__init__(detail)
        self.result = result
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True)
class CommandResult:
    label: str
    executable: str
    argv_sha256: str
    exit_code: int
    stdout_log: str
    stdout_sha256: str
    stderr_log: str
    stderr_sha256: str

    def to_json(self) -> dict[str, object]:
        return {
            "label": self.label,
            "executable": self.executable,
            "argv_sha256": self.argv_sha256,
            "exit_code": self.exit_code,
            "stdout_log": self.stdout_log,
            "stdout_sha256": self.stdout_sha256,
            "stderr_log": self.stderr_log,
            "stderr_sha256": self.stderr_sha256,
        }


@dataclass(frozen=True)
class RepositorySnapshot:
    head_oid: str
    head_identity: str
    status: bytes
    refs: bytes
    index_identity: str
    split_index_identity: str
    tracked_worktree_identity: str
    ignored_identity: str


def stop(result: str, reason_code: str, detail: str) -> NoReturn:
    raise VerificationStop(result, reason_code, detail)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def require_plain_directory(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        stop("blocked", f"{label}_unavailable", f"{label} is unavailable: {exc}")
    if stat.S_ISLNK(metadata.st_mode):
        stop("blocked", f"{label}_symlink", f"{label} must not be a symbolic link")
    if not stat.S_ISDIR(metadata.st_mode):
        stop("blocked", f"{label}_not_directory", f"{label} is not a directory")
    return path.resolve()


def require_new_external_output(raw: Path, target: Path, source: Path) -> Path:
    if raw.exists() or raw.is_symlink():
        stop("blocked", "output_exists", "output directory must not already exist")
    parent = raw.parent.resolve()
    if not parent.is_dir():
        stop("blocked", "output_parent_missing", "output directory parent does not exist")
    output = parent / raw.name
    if is_relative_to(output, target) or is_relative_to(output, source):
        stop("blocked", "output_inside_repository", "output directory must be outside both repositories")
    if is_relative_to(target, output) or is_relative_to(source, output):
        stop("blocked", "output_contains_repository", "output directory must not contain either repository")
    output.mkdir(mode=0o700)
    return output


def bounded_environment(workspace: Path) -> dict[str, str]:
    private_home = workspace / "home"
    private_tmp = workspace / "tmp"
    private_home.mkdir(mode=0o700)
    private_tmp.mkdir(mode=0o700)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(private_home),
        "TMPDIR": str(private_tmp),
        "LANG": "C",
        "LC_ALL": "C",
        "CI": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def parse_json_argv(raw: str, label: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        stop("blocked", "invalid_command_json", f"{label} is not valid JSON: {exc.msg}")
    if not isinstance(parsed, list) or not parsed:
        stop("blocked", "invalid_command_argv", f"{label} must be a nonempty JSON array")
    if any(not isinstance(item, str) or not item or "\x00" in item for item in parsed):
        stop("blocked", "invalid_command_argv", f"{label} entries must be nonempty strings without NUL")
    return parsed


def require_safe_copier_launcher(argv: Sequence[str]) -> None:
    direct = len(argv) == 1 and Path(argv[0]).name == "copier"
    uv = (
        len(argv) == 3
        and Path(argv[0]).name == "uv"
        and argv[1] == "run"
        and Path(argv[2]).name == "copier"
    )
    if not (direct or uv):
        stop(
            "blocked",
            "unsafe_copier_launcher",
            "Copier launcher must be copier or uv run copier without extra arguments",
        )


def safe_label(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return normalized[:48] or "command"


class Recorder:
    def __init__(self, output: Path):
        self.output = output
        self.logs = output / "logs"
        self.logs.mkdir(mode=0o700)
        self.commands: list[CommandResult] = []

    def run(
        self,
        label: str,
        argv: Sequence[str],
        cwd: Path,
        environment: dict[str, str],
        *,
        failure_result: str,
        failure_code: str,
    ) -> subprocess.CompletedProcess[bytes]:
        sequence = len(self.commands) + 1
        prefix = f"{sequence:02d}-{safe_label(label)}"
        stdout_path = self.logs / f"{prefix}.stdout"
        stderr_path = self.logs / f"{prefix}.stderr"
        try:
            process = subprocess.run(
                list(argv),
                cwd=cwd,
                env=environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            stop("blocked", "command_unavailable", f"{label} could not start")
        stdout_path.write_bytes(process.stdout)
        stderr_path.write_bytes(process.stderr)
        argv_digest = sha256_bytes(
            json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        record = CommandResult(
            label=label,
            executable=Path(argv[0]).name,
            argv_sha256=argv_digest,
            exit_code=process.returncode,
            stdout_log=str(stdout_path.relative_to(self.output)),
            stdout_sha256=sha256_bytes(process.stdout),
            stderr_log=str(stderr_path.relative_to(self.output)),
            stderr_sha256=sha256_bytes(process.stderr),
        )
        self.commands.append(record)
        if process.returncode != 0:
            stop(
                failure_result,
                failure_code,
                f"{label} exited with status {process.returncode}; inspect {record.stderr_log}",
            )
        return process


def read_git(
    repository: Path,
    arguments: Sequence[str],
    environment: dict[str, str],
    reason_code: str,
) -> bytes:
    try:
        process = subprocess.run(
            ["git", *SAFE_GIT_CONFIG, "-C", str(repository), *arguments],
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        stop("blocked", "git_unavailable", "Git could not start")
    if process.returncode != 0:
        stop("blocked", reason_code, "Git inspection failed; use the bounded reason code")
    return process.stdout


def git_state_path(
    repository: Path,
    arguments: Sequence[str],
    environment: dict[str, str],
    reason_code: str,
) -> Path:
    raw = read_git(repository, arguments, environment, reason_code)
    try:
        value = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        stop("blocked", reason_code, "Git returned a non-UTF-8 state path")
    path = Path(value)
    if not path.is_absolute():
        stop("blocked", reason_code, "Git returned a non-absolute state path")
    return path


def hash_regular_state_file(
    path: Path,
    label: str,
    *,
    max_bytes: int | None = MAX_GIT_STATE_FILE_BYTES,
) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        stop("blocked", f"{label}_unavailable", f"{label} is unavailable")
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            stop("blocked", f"{label}_not_regular", f"{label} must be a regular file")
        if max_bytes is not None and before.st_size > max_bytes:
            stop("blocked", f"{label}_too_large", f"{label} exceeds the bounded size limit")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                stop("blocked", f"{label}_short_read", f"{label} changed while it was read")
            digest.update(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after:
            stop("blocked", f"{label}_changed", f"{label} changed while it was read")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def split_index_identity(
    repository: Path,
    environment: dict[str, str],
    label: str,
) -> str:
    directories = {
        git_state_path(
            repository,
            ["rev-parse", "--absolute-git-dir"],
            environment,
            f"{label}_git_dir_failed",
        ),
        git_state_path(
            repository,
            ["rev-parse", "--path-format=absolute", "--git-common-dir"],
            environment,
            f"{label}_common_dir_failed",
        ),
    }
    entries: list[tuple[str, str]] = []
    for directory in sorted(directories, key=os.fspath):
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            stop("blocked", f"{label}_split_index_scan_failed", "Git split-index state is unavailable")
        for child in children:
            if SHARED_INDEX_RE.fullmatch(child.name):
                entries.append((child.name, hash_regular_state_file(child, f"{label}_split_index")))
    return sha256_bytes(json.dumps(entries, separators=(",", ":")).encode("ascii"))


def ignored_file_identity(
    repository: Path,
    environment: dict[str, str],
    label: str,
) -> str:
    raw_paths = read_git(
        repository,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
        environment,
        f"{label}_ignored_files_failed",
    )
    digest = hashlib.sha256()
    for raw_path in (item for item in raw_paths.split(b"\0") if item):
        path = repository / raw_path.decode("utf-8", errors="surrogateescape")
        try:
            metadata = path.lstat()
        except OSError:
            stop(
                "blocked",
                f"{label}_ignored_file_unavailable",
                "an ignored file became unavailable during inspection",
            )
        digest.update(len(raw_path).to_bytes(8, "big"))
        digest.update(raw_path)
        identity = (
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
            metadata.st_ino,
            metadata.st_dev,
        )
        digest.update(json.dumps(identity, separators=(",", ":")).encode("ascii"))
        if stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(path)
            except OSError:
                stop(
                    "blocked",
                    f"{label}_ignored_symlink_unavailable",
                    "an ignored symbolic link became unavailable during inspection",
                )
            digest.update(os.fsencode(target))
    return digest.hexdigest()


def require_default_index_flags(
    repository: Path,
    environment: dict[str, str],
    label: str,
) -> None:
    entries = read_git(
        repository,
        ["ls-files", "-v", "-z"],
        environment,
        f"{label}_index_flags_failed",
    )
    for entry in (item for item in entries.split(b"\0") if item):
        if len(entry) < 3 or entry[1:2] != b" ":
            stop("blocked", f"{label}_index_flags_invalid", "Git returned invalid index flags")
        tag = entry[:1]
        if tag == b"S" or b"a" <= tag <= b"z":
            stop(
                "blocked",
                f"{label}_index_flags_unsupported",
                f"{label} must not use assume-unchanged or skip-worktree index flags",
            )


def require_no_external_clean_filters(
    repository: Path,
    environment: dict[str, str],
    label: str,
) -> None:
    try:
        process = subprocess.run(
            [
                "git",
                *SAFE_GIT_CONFIG,
                "-C",
                str(repository),
                "config",
                "--includes",
                "--name-only",
                "--get-regexp",
                "^filter\\.",
            ],
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        stop("blocked", "git_unavailable", "Git could not start")
    if process.returncode not in {0, 1}:
        stop("blocked", f"{label}_filter_config_failed", "Git filter configuration is unavailable")
    names = [line.decode("utf-8", errors="replace").lower() for line in process.stdout.splitlines()]
    if any(name.endswith(".clean") or name.endswith(".process") for name in names):
        stop(
            "blocked",
            f"{label}_external_filter_unsupported",
            f"{label} must not configure external clean or process filters",
        )


def tracked_worktree_identity(
    repository: Path,
    environment: dict[str, str],
    label: str,
) -> str:
    entries = read_git(
        repository,
        ["ls-files", "--stage", "-z"],
        environment,
        f"{label}_tracked_files_failed",
    )
    digest = hashlib.sha256()
    for entry in (item for item in entries.split(b"\0") if item):
        try:
            raw_metadata, raw_path = entry.split(b"\t", 1)
            raw_mode, _raw_oid, raw_stage = raw_metadata.split(b" ", 2)
        except ValueError:
            stop("blocked", f"{label}_tracked_files_invalid", "Git returned an invalid tracked entry")
        if raw_stage != b"0":
            stop("blocked", f"{label}_unmerged_index", f"{label} must not have unmerged entries")
        mode = raw_mode.decode("ascii", errors="strict")
        path = repository / raw_path.decode("utf-8", errors="surrogateescape")
        digest.update(len(raw_path).to_bytes(8, "big"))
        digest.update(raw_path)
        digest.update(raw_mode)
        if mode == "160000":
            stop(
                "blocked",
                f"{label}_submodule_unsupported",
                f"{label} must not contain Git submodule entries",
            )
        try:
            metadata = path.lstat()
        except OSError:
            stop("blocked", f"{label}_tracked_file_unavailable", "a tracked file is unavailable")
        digest.update(str(metadata.st_mode & 0o7777).encode("ascii"))
        if mode == "120000":
            if not stat.S_ISLNK(metadata.st_mode):
                stop("blocked", f"{label}_tracked_type_mismatch", "a tracked symlink type differs")
            try:
                target = os.readlink(path)
            except OSError:
                stop("blocked", f"{label}_tracked_symlink_unavailable", "a tracked symlink is unavailable")
            raw = os.fsencode(target)
            digest.update(len(raw).to_bytes(8, "big"))
            digest.update(raw)
        elif mode in {"100644", "100755"}:
            if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                stop("blocked", f"{label}_tracked_type_mismatch", "a tracked file type differs")
            digest.update(
                hash_regular_state_file(
                    path,
                    f"{label}_tracked_file",
                    max_bytes=None,
                ).encode("ascii")
            )
        else:
            stop("blocked", f"{label}_tracked_mode_unsupported", "Git returned an unsupported tracked mode")
    return digest.hexdigest()


def capture_repository_snapshot(
    repository: Path,
    label: str,
    environment: dict[str, str],
    *,
    require_clean: bool,
) -> RepositorySnapshot:
    top = Path(
        read_git(repository, ["rev-parse", "--show-toplevel"], environment, f"{label}_not_git_root")
        .decode("utf-8", errors="strict")
        .strip()
    ).resolve()
    if top != repository:
        stop("blocked", f"{label}_not_git_root", f"{label} must be the Git repository root")
    require_no_external_clean_filters(repository, environment, label)
    tracked_before_status = tracked_worktree_identity(repository, environment, label)
    status = read_git(
        repository,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        environment,
        f"{label}_status_failed",
    )
    tracked_after_status = tracked_worktree_identity(repository, environment, label)
    if tracked_after_status != tracked_before_status:
        stop(
            "rejected",
            f"{label}_snapshot_changed_worktree",
            f"Git inspection changed the {label} tracked worktree",
        )
    if require_clean and status:
        stop("blocked", f"{label}_dirty", f"{label} worktree must be clean")
    if require_clean:
        require_default_index_flags(repository, environment, label)
    oid = (
        read_git(repository, ["rev-parse", "HEAD^{commit}"], environment, f"{label}_head_missing")
        .decode("ascii", errors="strict")
        .strip()
    )
    if not OID_RE.fullmatch(oid):
        stop("blocked", f"{label}_invalid_oid", f"{label} HEAD did not resolve to a commit OID")
    refs = read_git(
        repository,
        ["for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)%00"],
        environment,
        f"{label}_refs_failed",
    )
    head_path = git_state_path(
        repository,
        ["rev-parse", "--path-format=absolute", "--git-path", "HEAD"],
        environment,
        f"{label}_head_path_failed",
    )
    index_path = git_state_path(
        repository,
        ["rev-parse", "--path-format=absolute", "--git-path", "index"],
        environment,
        f"{label}_index_path_failed",
    )
    return RepositorySnapshot(
        head_oid=oid,
        head_identity=hash_regular_state_file(head_path, f"{label}_head_state"),
        status=status,
        refs=refs,
        index_identity=hash_regular_state_file(index_path, f"{label}_index_state"),
        split_index_identity=split_index_identity(repository, environment, label),
        tracked_worktree_identity=tracked_before_status,
        ignored_identity=ignored_file_identity(repository, environment, label),
    )


def resolve_commit(repository: Path, selector: str, environment: dict[str, str], code: str) -> str:
    if not selector or selector == "latest" or selector.startswith("-"):
        stop("blocked", code, "source ref must name an immutable resolvable selector, not latest")
    oid = (
        read_git(repository, ["rev-parse", "--verify", f"{selector}^{{commit}}"], environment, code)
        .decode("ascii", errors="strict")
        .strip()
    )
    if not OID_RE.fullmatch(oid):
        stop("blocked", code, "source ref did not resolve to a commit OID")
    return oid


def require_clone_unchanged(
    repository: Path,
    expected_oid: str,
    environment: dict[str, str],
    reason_prefix: str,
) -> None:
    observed_oid = resolve_commit(
        repository,
        "HEAD",
        environment,
        f"{reason_prefix}_head_missing",
    )
    observed_status = read_git(
        repository,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        environment,
        f"{reason_prefix}_status_failed",
    )
    if observed_oid != expected_oid or observed_status:
        stop(
            "rejected",
            f"{reason_prefix}_changed",
            "the isolated source clone changed during verification",
        )


def git_blob(repository: Path, oid: str, path: str, environment: dict[str, str]) -> bytes:
    return read_git(repository, ["show", f"{oid}:{path}"], environment, "answers_missing")


def copier_repository_url(recorded_source: str) -> str | None:
    """Return the address Copier would clone, or None when it would read a path.

    Copier resolves its aliases first, then accepts the value as a repository when it
    carries a known Git prefix or suffix. A value that satisfies neither is a path on
    this machine, however much it may resemble a URL.
    """

    url = recorded_source
    for pattern, replacement in GIT_ALIAS_REPLACEMENTS:
        url = pattern.sub(replacement, url)
    if url.endswith(GIT_POSTFIX) or url.startswith(GIT_PREFIXES):
        return url
    return None


def is_remote_source(recorded_source: str) -> bool:
    """Report whether the recorded source names a repository this run cannot reach.

    A value must be both a repository Copier would clone and an address carried over
    the network. A repository that lives on this machine, however it is spelled, stays
    a path so that it still faces every refusal a path faces.
    """

    url = copier_repository_url(recorded_source)
    if url is None:
        return False
    if url.startswith("git+"):
        url = url[len("git+") :]
    return bool(NETWORK_SCHEME_RE.match(url) or SCP_ADDRESS_RE.match(url))


def rewrite_recorded_source(clone: Path, recorded_source: str, isolated_source: str) -> None:
    """Point the disposable baseline's recorded template path at the local checkout.

    Copier refuses to update a dirty repository, so the rewrite is committed in the
    clone and the caller compares later HEADs against that commit instead of the
    original baseline.
    """

    answers = clone / ANSWERS_PATH
    try:
        text = answers.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        stop("blocked", "isolated_answers_unavailable", "the cloned Copier answers file could not be read")
    expression = re.compile(r"^_src_path:[ \t]*.*$", re.MULTILINE)
    replaced, count = expression.subn(f"_src_path: {isolated_source}", text, count=1)
    if count != 1 or replaced == text:
        stop(
            "blocked",
            "isolated_answers_rewrite_failed",
            f"the cloned Copier answers file does not record exactly one rewritable {recorded_source}",
        )
    try:
        answers.write_text(replaced, encoding="utf-8")
    except OSError:
        stop("blocked", "isolated_answers_unwritable", "the cloned Copier answers file could not be rewritten")


def parse_answer_scalar(raw: bytes, key: str) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        stop("blocked", "answers_not_utf8", "Copier answers file is not UTF-8")
    matches = []
    expression = re.compile(rf"^{re.escape(key)}:\s*(.*?)\s*$")
    for line in text.splitlines():
        match = expression.match(line)
        if match:
            matches.append(match.group(1))
    if len(matches) != 1 or not matches[0]:
        stop("blocked", "answers_field_invalid", f"Copier answers must contain exactly one {key}")
    value = matches[0]
    if value[0] in {'"', "'"}:
        if len(value) < 2 or value[-1] != value[0]:
            stop("blocked", "answers_field_invalid", f"Copier answer {key} has unsupported quoting")
        value = value[1:-1]
    return value


def clone_at(
    source: Path,
    destination: Path,
    oid: str,
    recorder: Recorder,
    environment: dict[str, str],
    label: str,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    recorder.run(
        f"clone {label}",
        ["git", "clone", "--quiet", "--no-checkout", "--no-hardlinks", str(source), str(destination)],
        cwd=destination.parent,
        environment=environment,
        failure_result="blocked",
        failure_code=f"{label}_clone_failed",
    )
    recorder.run(
        f"checkout {label}",
        ["git", "checkout", "--quiet", "--detach", oid],
        cwd=destination,
        environment=environment,
        failure_result="blocked",
        failure_code=f"{label}_checkout_failed",
    )


def selected_source_ref(source: Path, selector: str, oid: str, environment: dict[str, str]) -> str:
    try:
        process = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--verify", f"refs/tags/{selector}^{{commit}}"],
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return oid
    if process.returncode == 0 and process.stdout.decode("ascii", errors="ignore").strip() == oid:
        return selector
    return oid


def parse_porcelain_paths(raw: bytes) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    fields = [field for field in raw.split(b"\0") if field]
    index = 0
    while index < len(fields):
        field = fields[index]
        if len(field) < 4 or field[2:3] != b" ":
            stop("rejected", "status_parse_failed", "Git returned an unsupported porcelain record")
        status = field[:2].decode("ascii", errors="replace")
        path = field[3:].decode("utf-8", errors="surrogateescape")
        entries.append({"status": status, "path": path})
        if "R" in status or "C" in status:
            index += 1
            if index >= len(fields):
                stop("rejected", "status_parse_failed", "Git rename record is incomplete")
            entries[-1]["source_path"] = fields[index].decode("utf-8", errors="surrogateescape")
        index += 1
    return entries


def require_regular_executable(path: Path, code: str) -> None:
    try:
        metadata = path.lstat()
    except OSError:
        stop("rejected", code, "required generated executable is unavailable")
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_mode & 0o111 == 0
    ):
        stop("rejected", code, "required generated executable must be executable, regular, and non-symlinked")


def git_blob_oid(raw: bytes, hexadecimal_length: int) -> str:
    payload = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    if hexadecimal_length == 40:
        return hashlib.sha1(payload).hexdigest()
    if hexadecimal_length == 64:
        return hashlib.sha256(payload).hexdigest()
    stop("blocked", "unsupported_object_format", "Git returned an unsupported object ID length")


def require_index_matches_worktree(
    repository: Path,
    environment: dict[str, str],
) -> str:
    entries = read_git(
        repository,
        ["ls-files", "--stage", "-z"],
        environment,
        "staged_index_failed",
    )
    for entry in (item for item in entries.split(b"\0") if item):
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            raw_mode, raw_oid, raw_stage = metadata.split(b" ", 2)
        except ValueError:
            stop("blocked", "staged_index_parse_failed", "Git returned an unsupported index entry")
        mode = raw_mode.decode("ascii", errors="strict")
        oid = raw_oid.decode("ascii", errors="strict")
        if raw_stage != b"0":
            stop("rejected", "staged_index_unmerged", "the disposable index contains an unmerged entry")
        path = repository / raw_path.decode("utf-8", errors="surrogateescape")
        if mode == "160000":
            continue
        try:
            metadata_on_disk = path.lstat()
        except OSError:
            stop("rejected", "staged_worktree_mismatch", "a staged path is unavailable")
        if mode == "120000":
            if not stat.S_ISLNK(metadata_on_disk.st_mode):
                stop("rejected", "staged_worktree_mismatch", "staged symlink type differs from worktree")
            raw = os.fsencode(os.readlink(path))
        elif mode in {"100644", "100755"}:
            if not stat.S_ISREG(metadata_on_disk.st_mode) or stat.S_ISLNK(metadata_on_disk.st_mode):
                stop("rejected", "staged_worktree_mismatch", "staged file type differs from worktree")
            observed_mode = "100755" if metadata_on_disk.st_mode & 0o111 else "100644"
            if observed_mode != mode:
                stop("rejected", "staged_worktree_mismatch", "staged executable mode differs from worktree")
            raw = path.read_bytes()
        else:
            stop("blocked", "unsupported_index_mode", f"unsupported Git index mode: {mode}")
        if git_blob_oid(raw, len(oid)) != oid:
            stop("rejected", "staged_worktree_mismatch", "staged bytes differ from the verified worktree")
    untracked = read_git(
        repository,
        ["ls-files", "--others", "--exclude-standard", "-z"],
        environment,
        "staged_untracked_check_failed",
    )
    if untracked:
        stop("rejected", "staged_untracked_paths", "git add left non-ignored untracked paths")
    return (
        read_git(repository, ["write-tree"], environment, "staged_tree_failed")
        .decode("ascii", errors="strict")
        .strip()
    )


def write_manifest(output: Path, manifest: dict[str, object]) -> None:
    temporary = output / f".{MANIFEST_NAME}.tmp"
    final = output / MANIFEST_NAME
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, final)


def run_verification(args: argparse.Namespace) -> tuple[int, Path]:
    target = require_plain_directory(args.target, "target")
    source = require_plain_directory(args.source, "source")
    if target == source or is_relative_to(target, source) or is_relative_to(source, target):
        stop("blocked", "repository_overlap", "target and source repositories must be separate")
    output = require_new_external_output(args.output_dir, target, source)
    workspace = output / "workspace"
    workspace.mkdir(mode=0o700)
    environment = bounded_environment(workspace)
    recorder = Recorder(output)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "result": "blocked",
        "reason_code": "verification_incomplete",
        "detail": "verification did not complete",
        "target": {"repository": target.name},
        "source": {"repository": source.name, "selector": args.source_ref},
        "update_path": None,
        "changed_paths": [],
        "commands": [],
        "unresolved": [],
    }
    exit_code = 2
    target_snapshot: RepositorySnapshot | None = None
    source_snapshot: RepositorySnapshot | None = None
    postcheck_required = False
    try:
        copier_argv = parse_json_argv(args.copier_command_json, "copier command")
        require_safe_copier_launcher(copier_argv)
        validations = [
            parse_json_argv(raw, f"validation command {index}")
            for index, raw in enumerate(args.validation_command_json, start=1)
        ]
        if not validations:
            stop("blocked", "validation_missing", "at least one target-specific validation command is required")
        if not args.trust_template_tasks:
            stop("blocked", "template_trust_missing", "template-task trust must be explicit")
        target_snapshot = capture_repository_snapshot(
            target, "target", environment, require_clean=True
        )
        source_snapshot = capture_repository_snapshot(
            source, "source", environment, require_clean=True
        )
        postcheck_required = True
        target_head = target_snapshot.head_oid
        source_head = source_snapshot.head_oid
        target_oid = resolve_commit(target, args.target_ref or "HEAD", environment, "target_ref_missing")
        source_oid = resolve_commit(source, args.source_ref, environment, "source_ref_missing")
        manifest["target"] = {
            "repository": target.name,
            "starting_head_oid": target_head,
            "baseline_oid": target_oid,
        }
        manifest["source"] = {
            "repository": source.name,
            "starting_head_oid": source_head,
            "selector": args.source_ref,
            "commit_oid": source_oid,
        }

        answers = git_blob(target, target_oid, ANSWERS_PATH, environment)
        recorded_source = parse_answer_scalar(answers, "_src_path")
        recorded_commit = parse_answer_scalar(answers, "_commit")
        manifest["target"]["recorded_template_commit"] = recorded_commit
        manifest["source"]["recorded_src_path"] = recorded_source
        # A remote _src_path names no path this run may reach. The isolated clone
        # replaces it with a fixed sibling checkout so the recorded template ref is
        # still what gets verified, without the run reaching the network.
        remote_source = is_remote_source(recorded_source)
        source_path = Path(ISOLATED_SOURCE_PATH) if remote_source else Path(recorded_source)
        manifest["source"]["isolated_src_path"] = str(source_path)
        if source_path.is_absolute():
            stop("blocked", "absolute_source_path", "isolated verification requires a relative _src_path")

        target_clone = workspace / "target"
        isolated_source = (target_clone / source_path).resolve()
        if not is_relative_to(isolated_source, workspace):
            stop("blocked", "source_path_escape", "_src_path escapes the disposable workspace")
        if (
            isolated_source == target_clone
            or is_relative_to(isolated_source, target_clone)
            or is_relative_to(target_clone, isolated_source)
        ):
            stop("blocked", "source_path_overlap", "_src_path must resolve to a sibling of the target clone")
        scratch_roots = (Path(environment["HOME"]), Path(environment["TMPDIR"]))
        if any(
            isolated_source == scratch
            or is_relative_to(isolated_source, scratch)
            or is_relative_to(scratch, isolated_source)
            for scratch in scratch_roots
        ):
            stop(
                "blocked",
                "source_path_scratch_overlap",
                "_src_path must not overlap the private HOME or TMPDIR",
            )

        clone_at(target, target_clone, target_oid, recorder, environment, "target")
        clone_at(source, isolated_source, source_oid, recorder, environment, "source")
        clone_baseline_oid = target_oid
        if remote_source:
            rewrite_recorded_source(target_clone, recorded_source, str(source_path))
            recorder.run(
                "record the isolated template path",
                [
                    "git",
                    *SAFE_GIT_CONFIG,
                    "-c",
                    "user.name=Copier Verification",
                    "-c",
                    "user.email=copier-verification@example.invalid",
                    "commit",
                    "--quiet",
                    "--no-verify",
                    "-m",
                    "Point the isolated baseline at the local template checkout",
                    "--",
                    ANSWERS_PATH,
                ],
                target_clone,
                environment,
                failure_result="blocked",
                failure_code="isolated_answers_commit_failed",
            )
            clone_baseline_oid = resolve_commit(
                target_clone, "HEAD", environment, "isolated_baseline_missing"
            )
            manifest["target"]["isolated_baseline_oid"] = clone_baseline_oid
        source_argument = selected_source_ref(isolated_source, args.source_ref, source_oid, environment)

        wrapper = target_clone / UPDATE_WRAPPER
        if os.path.lexists(wrapper):
            require_regular_executable(wrapper, "update_wrapper_invalid")
            if shutil.which("copier", path=environment["PATH"]) is None:
                stop("blocked", "copier_unavailable", "generated update wrapper requires copier on PATH")
            update_argv = [str(wrapper), "--defaults", "--vcs-ref", source_argument]
            manifest["update_path"] = "generated_wrapper"
        else:
            match = VERSION_RE.match(recorded_commit)
            if match is None or int(match.group("major")) < 1 or not (target_clone / WORKFLOW_DIR).is_dir():
                stop("blocked", "adoption_required", "baseline requires the separate pre-v1 adoption workflow")
            if shutil.which(copier_argv[0], path=environment["PATH"]) is None:
                stop("blocked", "copier_launcher_unavailable", "configured Copier launcher is not on PATH")
            update_argv = [*copier_argv, "update", "--trust", "--defaults", "--vcs-ref", source_argument]
            manifest["update_path"] = "direct_supported_v1"

        recorder.run(
            "initial Copier update",
            update_argv,
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="update_failed",
        )
        require_clone_unchanged(isolated_source, source_oid, environment, "update_source")
        validator = target_clone / UPDATE_VALIDATOR
        require_regular_executable(validator, "updated_validator_missing")
        recorder.run(
            "updated Copier validator",
            [sys.executable, str(validator), "--destination", "."],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="updated_validator_failed",
        )
        recorder.run(
            "updated diff check",
            ["git", *SAFE_GIT_CONFIG, "diff", "--check", "--no-ext-diff", "--no-textconv"],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="diff_check_failed",
        )
        expected_head = resolve_commit(
            target_clone, "HEAD", environment, "updated_head_missing"
        )
        if expected_head != clone_baseline_oid:
            stop("rejected", "update_changed_head", "Copier update changed the disposable baseline HEAD")
        expected_status = read_git(
            target_clone,
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            environment,
            "updated_status_failed",
        )
        manifest["changed_paths"] = parse_porcelain_paths(expected_status)
        change_validator = target_clone / CHANGE_VALIDATOR
        require_regular_executable(change_validator, "change_validator_missing")
        recorder.run(
            "generated change-aware validation",
            [sys.executable, str(change_validator), "--all"],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="change_validation_failed",
        )
        for index, validation in enumerate(validations, start=1):
            recorder.run(
                f"target validation {index}",
                validation,
                target_clone,
                environment,
                failure_result="rejected",
                failure_code="target_validation_failed",
            )
        require_clone_unchanged(isolated_source, source_oid, environment, "validation_source")
        validated_head = resolve_commit(
            target_clone, "HEAD", environment, "validated_head_missing"
        )
        if validated_head != clone_baseline_oid:
            stop(
                "rejected",
                "validation_changed_head",
                "a validation command changed the disposable baseline HEAD",
            )
        validated_status = read_git(
            target_clone,
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            environment,
            "validated_status_failed",
        )
        if validated_status != expected_status:
            stop(
                "rejected",
                "validation_changed_worktree",
                "a validation command changed the disposable update result",
            )
        recorder.run(
            "post-validation Copier validator",
            [sys.executable, str(validator), "--destination", "."],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="post_validation_validator_failed",
        )
        recorder.run(
            "post-validation diff check",
            ["git", *SAFE_GIT_CONFIG, "diff", "--check", "--no-ext-diff", "--no-textconv"],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="post_validation_diff_failed",
        )
        final_precommit_status = read_git(
            target_clone,
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            environment,
            "precommit_status_failed",
        )
        if final_precommit_status != expected_status:
            stop(
                "rejected",
                "post_validation_changed_worktree",
                "post-validation checks changed the disposable update result",
            )
        recorder.run(
            "stage disposable update",
            ["git", *SAFE_GIT_CONFIG, "add", "-A"],
            target_clone,
            environment,
            failure_result="blocked",
            failure_code="disposable_stage_failed",
        )
        expected_tree = require_index_matches_worktree(target_clone, environment)
        recorder.run(
            "commit disposable update",
            [
                "git",
                *SAFE_GIT_CONFIG,
                "-c",
                "user.name=Copier Verification",
                "-c",
                "user.email=copier-verification@example.invalid",
                "commit",
                "--quiet",
                "--allow-empty",
                "--no-verify",
                "-m",
                "Verify isolated Copier update",
            ],
            target_clone,
            environment,
            failure_result="blocked",
            failure_code="disposable_commit_failed",
        )
        committed_tree = (
            read_git(
                target_clone,
                ["rev-parse", "HEAD^{tree}"],
                environment,
                "committed_tree_missing",
            )
            .decode("ascii", errors="strict")
            .strip()
        )
        if committed_tree != expected_tree:
            stop("rejected", "committed_tree_mismatch", "disposable commit tree differs from staged tree")
        committed_status = read_git(
            target_clone,
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            environment,
            "committed_status_failed",
        )
        if committed_status:
            stop("rejected", "commit_changed_worktree", "disposable commit changed the verified worktree")
        recorder.run(
            "idempotence Copier update",
            update_argv,
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="idempotence_update_failed",
        )
        recorder.run(
            "idempotence Copier validator",
            [sys.executable, str(validator), "--destination", "."],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="idempotence_validator_failed",
        )
        recorder.run(
            "idempotence diff check",
            ["git", *SAFE_GIT_CONFIG, "diff", "--check", "--no-ext-diff", "--no-textconv"],
            target_clone,
            environment,
            failure_result="rejected",
            failure_code="idempotence_diff_failed",
        )
        require_clone_unchanged(isolated_source, source_oid, environment, "idempotence_source")
        second_status = read_git(
            target_clone,
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            environment,
            "idempotence_status_failed",
        )
        if second_status:
            stop("rejected", "not_idempotent", "same-ref update left a second worktree change")

        manifest.update(
            {
                "result": "verified",
                "reason_code": "all_checks_passed",
                "detail": "all required checks passed for the recorded commit OIDs",
                "unresolved": [],
            }
        )
        exit_code = 0
    except VerificationStop as exc:
        manifest.update(
            {
                "result": exc.result,
                "reason_code": exc.reason_code,
                "detail": exc.detail,
                "unresolved": [exc.detail] if exc.result == "blocked" else [],
            }
        )
        exit_code = 1 if exc.result == "rejected" else 2
    except KeyboardInterrupt:
        manifest.update(
            {
                "result": "blocked",
                "reason_code": "interrupted",
                "detail": "verification was interrupted",
                "unresolved": ["verification was interrupted"],
            }
        )
        exit_code = 2
    finally:
        original_failure: VerificationStop | None = None
        if postcheck_required:
            assert target_snapshot is not None and source_snapshot is not None
            try:
                final_target_snapshot = capture_repository_snapshot(
                    target, "final_target", environment, require_clean=False
                )
            except VerificationStop:
                original_failure = VerificationStop(
                    "rejected",
                    "original_target_state_unavailable",
                    "the original target repository could not be compared after verification",
                )
            else:
                if final_target_snapshot != target_snapshot:
                    original_failure = VerificationStop(
                        "rejected",
                        "original_target_changed",
                        "the original target repository changed during verification",
                    )
            try:
                final_source_snapshot = capture_repository_snapshot(
                    source, "final_source", environment, require_clean=False
                )
            except VerificationStop:
                if original_failure is None:
                    original_failure = VerificationStop(
                        "rejected",
                        "original_source_state_unavailable",
                        "the original source repository could not be compared after verification",
                    )
            else:
                if final_source_snapshot != source_snapshot and original_failure is None:
                    original_failure = VerificationStop(
                        "rejected",
                        "original_source_changed",
                        "the original source repository changed during verification",
                    )
        if original_failure is not None:
            manifest.update(
                {
                    "result": original_failure.result,
                    "reason_code": original_failure.reason_code,
                    "detail": original_failure.detail,
                    "unresolved": [],
                }
            )
            exit_code = 1
        manifest["commands"] = [command.to_json() for command in recorder.commands]
        write_manifest(output, manifest)
    return exit_code, output / MANIFEST_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--target-ref")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--trust-template-tasks", action="store_true")
    parser.add_argument(
        "--copier-command-json",
        default='["copier"]',
        help="JSON argv prefix used only by the supported direct v1 update path",
    )
    parser.add_argument(
        "--validation-command-json",
        action="append",
        default=[],
        help="repeatable target-specific validation command as a JSON argv array",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        exit_code, manifest = run_verification(args)
    except VerificationStop as exc:
        print(f"{exc.result}: {exc.detail}", file=sys.stderr)
        return 1 if exc.result == "rejected" else 2
    print(f"verification manifest: {manifest}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
