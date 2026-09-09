#!/usr/bin/env python3
"""Run or apply a Bubblewrap-isolated plan worker patch."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from urllib.parse import urlsplit
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Sequence


SCHEMA_VERSION = 2
WORKER_CONTRACT_SCHEMA_VERSION = 2
WORKER_CONTRACT_MAX_BYTES = 65_536
WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION = 2
WORKER_COMPLETION_RECEIPT_MAX_BYTES = 65_536
WORKER_COMPLETION_RECEIPT_VALUE_MAX_BYTES = 1_024
WORKER_COMPLETION_RECEIPT_MAX_ITEMS = 64
WORKER_COMPLETION_BLOCKER_CODES = frozenset({
    "acceptance_evidence_mismatch", "candidate_not_derived", "command_failed",
    "false_success_claim", "implementation_failed", "incomplete_change",
    "invalid_completion_claims", "missing_completion_claims", "missing_input",
    "out_of_scope_change_reported", "worker_failed",
})
WORKER_COMPLETION_RISK_CODES = frozenset({
    "incomplete_change", "known_limitation", "parent_review_required", "validation_not_run",
})
WORKER_COMPLETION_DIAGNOSTIC_CODES = frozenset({"worker_failed"})
WORKER_COMPLETION_EXIT_STATUS_MIN = -255
WORKER_COMPLETION_EXIT_STATUS_MAX = 255
DEPENDENCY_SNAPSHOT_SCHEMA_VERSION = 1
DEPENDENCY_SNAPSHOT_MAX_BYTES = 16_384
DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"
DEFAULT_CODEX_REASONING = "medium"
DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"
DEFAULT_FALLBACK_CODEX_REASONING = "max"
TERRA_CODEX_MODEL = "gpt-5.6-terra"
IMPLEMENTATION_CLASSIFICATIONS = frozenset({"low", "ordinary", "high"})
WRITABLE_SOL_MODEL = "gpt-5.6-sol"
AVAILABILITY_STATE_SCHEMA_VERSION = 1
AVAILABILITY_STATE_MAX_BYTES = 4096
AVAILABILITY_STATE_MAX_ENTRIES = 16
AVAILABILITY_STATE_MAX_MODEL_BYTES = 128
ORCHESTRATION_RUN_ID_MAX_BYTES = 128
TELEMETRY_SCHEMA_VERSION = 1
TELEMETRY_MAX_DURATION_SECONDS = 31_536_000.0
LIFECYCLE_STATE_SCHEMA_VERSION = 2
LIFECYCLE_STATE_MAX_BYTES = 8192
PREFLIGHT_REPORT_SCHEMA_VERSION = 1
PREFLIGHT_CLAIM_SCHEMA_VERSION = 1
PREFLIGHT_DEFAULT_TIMEOUT_SECONDS = 60
PREFLIGHT_MAXIMUM_TIMEOUT_SECONDS = 120
PREFLIGHT_OUTPUT_LIMIT_BYTES = 65_536
PREFLIGHT_DRAIN_CHUNK_BYTES = 4096
PREFLIGHT_DRAIN_JOIN_SECONDS = 5.0
PREFLIGHT_LEDGER_READ_MAX_BYTES = 4_194_304
CORRECTION_BRIEF_MAX_BYTES = 8192
INDEPENDENT_REVIEW_LIMIT = 2
MAX_CORRECTION_ROUNDS = INDEPENDENT_REVIEW_LIMIT - 1
PLAN_PATTERN = re.compile(r"^docs/plan/active/\d{3}-[^/]+\.md$")
STATUS_PATTERN = re.compile(r"^(?:\?\?|[ MARCUDT][ MD]) (.+)$")
CODEX_ERROR_LINE = re.compile(r"^(?:ERROR|FATAL)(?::|\b)", re.IGNORECASE)
CODEX_UNAVAILABLE_PATTERNS = (
    (
        "usage_limit",
        re.compile(
            r"^(?:ERROR|FATAL):\s*(?:(?:you(?:'ve| have)?) hit your usage limit"
            r"|usage limit (?:has been )?exceeded)(?: for (?:model )?[^\n]+?)?[.!]?$",
            re.IGNORECASE,
        ),
    ),
    (
        "rate_limit",
        re.compile(
            r"^(?:ERROR|FATAL):\s*(?:rate limit exceeded|too many requests)"
            r"(?: for (?:model )?[^\n]+?)?[.!]?$",
            re.IGNORECASE,
        ),
    ),
    (
        "model_unavailable",
        re.compile(
            r"^(?:ERROR|FATAL):\s*(?:the )?model\b.*\b"
            r"(?:not available|unavailable|not found|unsupported|does not exist)\b[^\n]*$",
            re.IGNORECASE,
        ),
    ),
    (
        "model_access_denied",
        re.compile(
            r"^(?:ERROR|FATAL):\s*(?:"
            r"(?:the )?model\b.*\b(?:do not|don't|does not|doesn't) have access\b"
            r"|access to (?:the )?model\b.*\b(?:is )?denied\b"
            r"|(?:you )?(?:do not|don't) have access to (?:the |this )?model\b"
            r")[^\n]*$",
            re.IGNORECASE,
        ),
    ),
)
SHA256_BUFFER = 1024 * 1024
ENV_PREFIX = "SANDBOXED_PLAN_WORKER_"
DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEPENDENCY_WRITABLE_CACHE_PATHS = (".vite", ".vite-temp")
VALIDATION_AUTHORITY_SCOPE = (
    ".codex/",
    ".codex/hooks/",
    ".github/",
    ".project-agent-workflow/",
    "template/",
    "docs/agent/",
    "scripts/",
    "tests/",
    "AGENTS.md",
    "Makefile",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
    "go.mod",
    "go.sum",
    "package.json",
    "package-lock.json",
    ".node-version",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.cfg",
    "pytest.ini",
    "noxfile.py",
    "tox.ini",
)
VALIDATION_AUTHORITY_BASENAMES = frozenset(
    {
        "conftest.py",
        "sitecustomize.py",
        "usercustomize.py",
        "build.rs",
        "jest.config.js",
        "jest.config.cjs",
        "jest.config.mjs",
        "jest.config.ts",
        "vitest.config.js",
        "vitest.config.mjs",
        "vitest.config.ts",
        "vite.config.js",
        "vite.config.ts",
        "eslint.config.js",
        "eslint.config.mjs",
        "tsconfig.json",
    }
)
VALIDATION_MANIFEST_BASENAMES = frozenset(
    PurePosixPath(entry).name for entry in VALIDATION_AUTHORITY_SCOPE if not entry.endswith("/")
)
VALIDATION_TEST_NAME = re.compile(r"(?:^|/)(?:test_[^/]+|[^/]+[._-](?:test|spec))\.[^/]+$")
VALIDATION_CONFIG_NAME = re.compile(
    r"(?:^|/)(?:[^/]+\.config\.[^/]+|tsconfig[^/]*\.json|[^/]*(?:rc|rc\.[^/]+))$"
)
SANDBOX_SYSTEM_DIRECTORIES = ("/usr", "/bin", "/sbin", "/lib", "/lib64")
SANDBOX_SYSTEM_FILES = (
    "/etc/passwd",
    "/etc/group",
    "/etc/nsswitch.conf",
    "/etc/hosts",
    "/etc/resolv.conf",
)
SANDBOX_SYSTEM_OPTIONAL_DIRECTORIES = ("/etc/ssl", "/etc/alternatives")
ARTIFACT_NAMES = (
    "worker.stdout",
    "worker.stderr",
    "worker-last-message.txt",
    "worker-primary.stdout",
    "worker-primary.stderr",
    "worker-primary-last-message.txt",
    "worker-fallback.stdout",
    "worker-fallback.stderr",
    "worker-fallback-last-message.txt",
    "candidate.patch",
    "worker-contract.json",
    "worker-completion-receipt.json",
    "worker-primary-completion-receipt.json",
    "worker-fallback-completion-receipt.json",
    "worker-process-result.json",
    "worker-primary-process-result.json",
    "worker-fallback-process-result.json",
    "manifest.json",
    "validation.json",
)
RESERVED_WORKER_ENV = frozenset(
    {
        "HOME",
        "PATH",
        "TMPDIR",
        "TMP",
        "TEMP",
        "CODEX_HOME",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPYCACHEPREFIX",
        "PIP_CACHE_DIR",
        "UV_CACHE_DIR",
        "UV_PROJECT_ENVIRONMENT",
        f"{ENV_PREFIX}SOURCE_REPO",
        f"{ENV_PREFIX}WORKER_REPO",
        f"{ENV_PREFIX}SCRATCH_DIR",
        f"{ENV_PREFIX}PLAN_PATH",
        f"{ENV_PREFIX}WORKER_CONTRACT",
        f"{ENV_PREFIX}COMPLETION_CLAIMS",
        f"{ENV_PREFIX}NEW_FILE_ROOT",
        f"{ENV_PREFIX}CORRECTION_BRIEF",
    }
)


class RunnerError(RuntimeError):
    """Raised when the sandboxed runner must fail closed."""


class AvailabilityState:
    """Run-bound availability memory held through one verified parent directory fd."""

    def __init__(
        self,
        *,
        parent_fd: int,
        target_name: str,
        run_id: str,
        unavailable: dict[str, str],
        target_identity: tuple[int, int, int, int] | None,
        lock_fd: int,
    ) -> None:
        self.parent_fd = parent_fd
        self.target_name = target_name
        self.run_id = run_id
        self.unavailable = unavailable
        self.target_identity = target_identity
        self.lock_fd = lock_fd

    def close(self) -> None:
        if self.lock_fd >= 0:
            os.close(self.lock_fd)
            self.lock_fd = -1
        if self.parent_fd >= 0:
            os.close(self.parent_fd)
            self.parent_fd = -1

    def __enter__(self) -> AvailabilityState:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def reason_for(self, model: str) -> str | None:
        return self.unavailable.get(model)

    def record(self, model: str, reason: str) -> None:
        validate_model_name(model)
        if reason not in {item[0] for item in CODEX_UNAVAILABLE_PATTERNS}:
            raise RunnerError(f"availability reason is not allowlisted: {reason}")
        existing = self.unavailable.get(model)
        if existing is not None:
            if existing != reason:
                raise RunnerError(f"availability state has conflicting reasons for model: {model}")
            return
        if len(self.unavailable) >= AVAILABILITY_STATE_MAX_ENTRIES:
            raise RunnerError("availability state exceeds the entry-count bound")
        self.unavailable[model] = reason
        try:
            self._persist()
        except BaseException:
            self.unavailable.pop(model, None)
            raise

    def _current_target_identity(self) -> tuple[int, int, int, int] | None:
        try:
            descriptor = os.open(
                self.target_name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self.parent_fd,
            )
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise RunnerError("availability state target is not a regular non-symlink file") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise RunnerError("availability state target must be a regular file")
            return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
        finally:
            os.close(descriptor)

    def _persist(self) -> None:
        entries = [
            {"model": model, "reason": reason}
            for model, reason in sorted(self.unavailable.items())
        ]
        content = (
            json.dumps(
                {
                    "schema_version": AVAILABILITY_STATE_SCHEMA_VERSION,
                    "orchestration_run_id": self.run_id,
                    "unavailable_models": entries,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        if len(content) > AVAILABILITY_STATE_MAX_BYTES:
            raise RunnerError("availability state exceeds the byte bound")
        if self._current_target_identity() != self.target_identity:
            raise RunnerError("availability state target changed after it was opened")
        temporary_name = f".{self.target_name}.tmp-{os.getpid()}-{time.monotonic_ns()}"
        descriptor = -1
        try:
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self.parent_fd,
            )
            view = memoryview(content)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise RunnerError("availability state write made no progress")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            if self._current_target_identity() != self.target_identity:
                raise RunnerError("availability state target changed before atomic replacement")
            os.replace(
                temporary_name,
                self.target_name,
                src_dir_fd=self.parent_fd,
                dst_dir_fd=self.parent_fd,
            )
            os.fsync(self.parent_fd)
            self.target_identity = self._current_target_identity()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name, dir_fd=self.parent_fd)
            except FileNotFoundError:
                pass


class LifecycleState:
    """Locked run ledger that makes correction, validation, and apply transitions linear."""

    def __init__(self, *, parent_fd: int, target_name: str, lock_fd: int, run_id: str, data: dict[str, Any] | None) -> None:
        self.parent_fd = parent_fd
        self.target_name = target_name
        self.lock_fd = lock_fd
        self.run_id = run_id
        self.data = data

    def __enter__(self) -> LifecycleState:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        if self.lock_fd >= 0:
            os.close(self.lock_fd)
            self.lock_fd = -1
        if self.parent_fd >= 0:
            os.close(self.parent_fd)
            self.parent_fd = -1

    def require_existing(self) -> dict[str, Any]:
        if self.data is None:
            raise RunnerError("lifecycle state has not been initialized by candidate generation")
        return self.data

    def persist(self, data: dict[str, Any]) -> None:
        validate_lifecycle_payload(data, self.run_id)
        content = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if len(content) > LIFECYCLE_STATE_MAX_BYTES:
            raise RunnerError("lifecycle state exceeds the byte bound")
        temporary_name = f".{self.target_name}.tmp-{os.getpid()}-{time.monotonic_ns()}"
        descriptor = -1
        try:
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self.parent_fd,
            )
            view = memoryview(content)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise RunnerError("lifecycle state write made no progress")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary_name, self.target_name, src_dir_fd=self.parent_fd, dst_dir_fd=self.parent_fd)
            os.fsync(self.parent_fd)
            self.data = data
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name, dir_fd=self.parent_fd)
            except FileNotFoundError:
                pass


def fail(message: str) -> None:
    print(f"sandboxed plan worker failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(SHA256_BUFFER):
            digest.update(chunk)
    return digest.hexdigest()


def validation_failure_identity(
    *, suite: str, kind: str, command_index: int, argv: Sequence[str], exit_status: int
) -> dict[str, object]:
    identity = {
        "suite": suite,
        "kind": kind,
        "command_index": command_index,
        "argv": list(argv),
    }
    operation_digest = "sha256:" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "kind": kind,
        "command_index": command_index,
        "operation_digest": operation_digest,
        "observed_exit_status": exit_status,
    }


def digest_tree(
    root: Path, *, omit_external_symlinks: bool = False, allow_hardlinks: bool = False
) -> str:
    """Hash one dependency tree while rejecting file types and links unsafe to bind."""
    if root.is_symlink() or not root.is_dir():
        raise RunnerError(f"dependency tree must be a regular directory: {root}")
    digest = hashlib.sha256()
    pending = [root]
    entries: list[Path] = []
    while pending:
        directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise RunnerError(f"could not scan dependency tree: {exc}") from exc
        for child in children:
            path = Path(child.path)
            entries.append(path)
            if child.is_dir(follow_symlinks=False):
                pending.append(path)
    for path in sorted(entries, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if metadata.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
            raise RunnerError(
                f"dependency snapshot contains unsupported special permission bits: {relative}"
            )
        if stat.S_ISDIR(metadata.st_mode):
            kind = b"d"
            payload = b""
        elif stat.S_ISREG(metadata.st_mode):
            if metadata.st_nlink != 1 and not allow_hardlinks:
                raise RunnerError(f"dependency snapshot contains a hard-linked file: {relative}")
            kind = b"f"
            payload = bytes.fromhex(hash_file(path))
        elif stat.S_ISLNK(metadata.st_mode):
            kind = b"l"
            target = os.readlink(path)
            if os.path.isabs(target):
                if omit_external_symlinks:
                    continue
                raise RunnerError(f"dependency snapshot contains an absolute symlink: {relative}")
            resolved = (path.parent / target).resolve(strict=False)
            if not path_is_within(root, resolved):
                if omit_external_symlinks:
                    continue
                raise RunnerError(f"dependency snapshot symlink escapes node_modules: {relative}")
            payload = os.fsencode(target)
        else:
            raise RunnerError(f"dependency snapshot contains an unsupported file type: {relative}")
        encoded = relative.encode("utf-8", errors="surrogateescape")
        digest.update(kind)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update((stat.S_IMODE(metadata.st_mode) & 0o777).to_bytes(2, "big"))
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def source_tree_metadata_fingerprint(root: Path) -> str:
    """source_tree_metadata_fingerprint is the source entry identity and metadata digest."""
    if root.is_symlink() or not root.is_dir():
        raise RunnerError(f"dependency tree must be a regular directory: {root}")
    pending = [root]
    entries = [root]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise RunnerError(f"could not scan dependency tree metadata: {exc}") from exc
        for child in children:
            path = Path(child.path)
            entries.append(path)
            if child.is_dir(follow_symlinks=False):
                pending.append(path)
    digest = hashlib.sha256()
    for path in sorted(entries, key=lambda item: item.relative_to(root).as_posix()):
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            kind = b"d"
            link_target = b""
        elif stat.S_ISREG(metadata.st_mode):
            kind = b"f"
            link_target = b""
        elif stat.S_ISLNK(metadata.st_mode):
            kind = b"l"
            link_target = os.fsencode(os.readlink(path))
        else:
            raise RunnerError(f"dependency tree metadata contains an unsupported file type: {path}")
        fields = (
            path.relative_to(root).as_posix().encode("utf-8", errors="surrogateescape"),
            kind,
            str(metadata.st_dev).encode(),
            str(metadata.st_ino).encode(),
            str(metadata.st_nlink).encode(),
            str(metadata.st_mode).encode(),
            str(metadata.st_size).encode(),
            str(metadata.st_mtime_ns).encode(),
            str(metadata.st_ctime_ns).encode(),
            link_target,
        )
        for field in fields:
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RunnerError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"{label} must contain one JSON object: {path}")
    return value


def validate_npm_dependency_tree(
    repo_root: Path, dependency_tree: Path, *, allow_hardlinks: bool = False
) -> None:
    package_json = load_json_object(repo_root / "package.json", "package.json")
    root_lock = load_json_object(repo_root / "package-lock.json", "package-lock.json")
    hidden_lock = load_json_object(
        dependency_tree / ".package-lock.json", "node_modules hidden lockfile"
    )
    root_packages = root_lock.get("packages")
    installed_packages = hidden_lock.get("packages")
    if not isinstance(root_packages, dict) or not isinstance(installed_packages, dict):
        raise RunnerError("npm lockfiles must contain package record objects")
    root_record = root_packages.get("")
    if not isinstance(root_record, dict):
        raise RunnerError("package-lock.json is missing the root package record")
    for field in (
        "name",
        "version",
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        if package_json.get(field) != root_record.get(field):
            raise RunnerError(f"package.json does not match package-lock.json root field: {field}")
    installed_paths: set[str] = set()
    for raw_path, record in installed_packages.items():
        if not isinstance(raw_path, str) or not raw_path.startswith("node_modules/"):
            raise RunnerError(f"unsupported npm dependency record path: {raw_path!r}")
        if not isinstance(record, dict) or root_packages.get(raw_path) != record:
            raise RunnerError(f"installed npm package record differs from package-lock.json: {raw_path}")
        relative = raw_path.removeprefix("node_modules/")
        package_dir = dependency_tree / relative
        if package_dir.is_symlink() or not package_dir.is_dir():
            raise RunnerError(f"installed npm package directory is missing or linked: {raw_path}")
        installed_manifest = load_json_object(package_dir / "package.json", f"{raw_path}/package.json")
        if installed_manifest.get("version") != record.get("version"):
            raise RunnerError(f"installed npm package version differs from its lock record: {raw_path}")
        installed_paths.add(raw_path)
    for raw_path, record in root_packages.items():
        if raw_path == "" or raw_path in installed_paths:
            continue
        if not isinstance(raw_path, str) or not raw_path.startswith("node_modules/"):
            raise RunnerError(f"npm workspaces and non-node_modules lock paths are unsupported: {raw_path!r}")
        if not isinstance(record, dict) or record.get("optional") is not True:
            raise RunnerError(f"required npm package is absent from the dependency tree: {raw_path}")
    module_roots = [dependency_tree]
    physical_packages: set[str] = set()
    while module_roots:
        module_root = module_roots.pop()
        for child in sorted(module_root.iterdir(), key=lambda item: item.name):
            if child.name.startswith("."):
                continue
            candidates = (
                sorted(child.iterdir(), key=lambda item: item.name)
                if child.name.startswith("@") and child.is_dir() and not child.is_symlink()
                else [child]
            )
            for package_dir in candidates:
                if package_dir.is_symlink() or not package_dir.is_dir():
                    raise RunnerError(f"dependency tree contains an unsupported package entry: {package_dir}")
                relative = "node_modules/" + package_dir.relative_to(dependency_tree).as_posix()
                physical_packages.add(relative)
                nested = package_dir / "node_modules"
                if nested.is_dir() and not nested.is_symlink():
                    module_roots.append(nested)
    unexpected = sorted(physical_packages - installed_paths)
    if unexpected:
        raise RunnerError(
            "dependency tree contains packages absent from its hidden lockfile: "
            + ", ".join(unexpected)
        )
    digest_tree(dependency_tree, allow_hardlinks=allow_hardlinks)


def validate_dependency_snapshot_manifest(payload: Any) -> dict[str, Any]:
    required = {
        "schema_version",
        "package_manager",
        "source_head",
        "package_json_sha256",
        "package_lock_sha256",
        "dependency_path",
        "tree_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RunnerError("dependency snapshot manifest has an invalid exact field shape")
    if payload["schema_version"] != DEPENDENCY_SNAPSHOT_SCHEMA_VERSION:
        raise RunnerError("dependency snapshot manifest has an unsupported schema version")
    if payload["package_manager"] != "npm" or payload["dependency_path"] != "node_modules":
        raise RunnerError("dependency snapshot manifest must describe npm node_modules")
    for key in ("package_json_sha256", "package_lock_sha256", "tree_sha256"):
        if not isinstance(payload[key], str) or re.fullmatch(r"[0-9a-f]{64}", payload[key]) is None:
            raise RunnerError(f"dependency snapshot manifest has an invalid digest field: {key}")
    if not isinstance(payload["source_head"], str) or re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64})", payload["source_head"]
    ) is None:
        raise RunnerError("dependency snapshot source_head must be a full Git object id")
    return payload


def verify_dependency_snapshot(
    repo_root: Path, manifest_path: Path, git_bin: str | None = None
) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser()
    if not manifest_path.is_absolute():
        manifest_path = (Path.cwd() / manifest_path).absolute()
    ensure_no_symlink_components(manifest_path)
    if path_is_within(repo_root, manifest_path):
        raise RunnerError("dependency snapshot manifest must be outside the source repository")
    try:
        manifest_fd = os.open(
            manifest_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
    except OSError as exc:
        raise RunnerError(f"could not open dependency snapshot manifest: {exc}") from exc
    try:
        before_read = os.fstat(manifest_fd)
        if not stat.S_ISREG(before_read.st_mode) or before_read.st_nlink != 1:
            raise RunnerError("dependency snapshot manifest must be a single-link regular file")
        if before_read.st_size > DEPENDENCY_SNAPSHOT_MAX_BYTES:
            raise RunnerError("dependency snapshot manifest exceeds the byte bound")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                manifest_fd,
                min(4096, DEPENDENCY_SNAPSHOT_MAX_BYTES + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > DEPENDENCY_SNAPSHOT_MAX_BYTES:
                raise RunnerError("dependency snapshot manifest exceeds the byte bound")
        after_read = os.fstat(manifest_fd)
        if (
            target_identity(before_read) != target_identity(after_read)
            or before_read.st_ctime_ns != after_read.st_ctime_ns
            or after_read.st_nlink != 1
        ):
            raise RunnerError("dependency snapshot manifest changed while it was read")
        raw = b"".join(chunks)
    finally:
        os.close(manifest_fd)
    try:
        payload = validate_dependency_snapshot_manifest(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError("dependency snapshot manifest is not valid UTF-8 JSON") from exc
    if hash_file(repo_root / "package.json") != payload["package_json_sha256"]:
        raise RunnerError("dependency snapshot package.json digest differs from the source repository")
    if hash_file(repo_root / "package-lock.json") != payload["package_lock_sha256"]:
        raise RunnerError("dependency snapshot package-lock.json digest differs from the source repository")
    if git_bin is None:
        git_bin = require_executable("git", "git")
    if git_text(repo_root, git_bin, "rev-parse", "HEAD") != payload["source_head"]:
        raise RunnerError("dependency snapshot source HEAD differs from the source repository")
    dependency_tree = manifest_path.parent / payload["dependency_path"]
    validate_npm_dependency_tree(repo_root, dependency_tree)
    if digest_tree(dependency_tree) != payload["tree_sha256"]:
        raise RunnerError("dependency snapshot tree digest does not match its manifest")
    return {**payload, "manifest_path": manifest_path, "tree_path": dependency_tree}


def create_private_dependency_output_dir(repo_root: Path, requested: str) -> tuple[Path, int, tuple[int, int]]:
    output_dir = Path(requested).expanduser()
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() / output_dir).absolute()
    ensure_no_symlink_components(output_dir.parent)
    if path_is_within(repo_root, output_dir):
        raise RunnerError("dependency snapshot output directory must be outside the source repository")
    if not output_dir.parent.is_dir():
        raise RunnerError("dependency snapshot output parent must already be a directory")
    try:
        output_dir.mkdir(mode=0o700, exist_ok=False)
        descriptor = os.open(
            output_dir,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except FileExistsError as exc:
        raise RunnerError("dependency snapshot output directory must not already exist") from exc
    except OSError as exc:
        raise RunnerError(f"could not create dependency snapshot output directory: {exc}") from exc
    metadata = os.fstat(descriptor)
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        os.close(descriptor)
        raise RunnerError("dependency snapshot output directory must be runner-owned mode 0700")
    return output_dir, descriptor, (metadata.st_dev, metadata.st_ino)


def require_directory_identity(path: Path, identity: tuple[int, int]) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RunnerError("dependency snapshot output directory was replaced") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or path.is_symlink()
        or (metadata.st_dev, metadata.st_ino) != identity
    ):
        raise RunnerError("dependency snapshot output directory was replaced")


def write_private_dependency_manifest(directory_fd: int, payload: dict[str, Any]) -> None:
    content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = -1
    try:
        descriptor = os.open(
            "manifest.json",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise RunnerError("dependency snapshot manifest write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RunnerError("dependency snapshot manifest must have exactly one regular-file link")
        os.close(descriptor)
        descriptor = -1
        os.fsync(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def materialize_verified_dependency_tree(
    repo_root: Path, snapshot: dict[str, Any], target_tree: Path
) -> Path:
    if target_tree.exists() or target_tree.is_symlink():
        raise RunnerError("private dependency snapshot target must not already exist")
    try:
        shutil.copytree(snapshot["tree_path"], target_tree, symlinks=True)
        validate_npm_dependency_tree(repo_root, target_tree)
        if digest_tree(target_tree) != snapshot["tree_sha256"]:
            raise RunnerError("private dependency snapshot differs from its verified tree digest")
    except BaseException:
        shutil.rmtree(target_tree, ignore_errors=True)
        raise
    return target_tree


def ensure_dependency_cache_mountpoints(dependency_tree: Path) -> list[Path]:
    created: list[Path] = []
    for relative in DEPENDENCY_WRITABLE_CACHE_PATHS:
        target = dependency_tree / relative
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_dir():
                raise RunnerError(f"dependency cache mountpoint must be a directory: {relative}")
            continue
        target.mkdir(mode=0o700)
        created.append(target)
    return created


def dependency_cache_shadows(
    dependency_tree: Path, clone_dependency_target: Path, scratch_dir: Path
) -> list[tuple[Path, Path]]:
    shadows: list[tuple[Path, Path]] = []
    cache_root = scratch_dir / "dependency-caches"
    cache_root.mkdir()
    for relative in DEPENDENCY_WRITABLE_CACHE_PATHS:
        mountpoint = dependency_tree / relative
        if mountpoint.is_symlink() or not mountpoint.is_dir():
            raise RunnerError(f"dependency cache mountpoint changed shape: {relative}")
        shadow = cache_root / relative
        shadow.mkdir()
        shadows.append((shadow, clone_dependency_target / relative))
    return shadows


def verify_private_dependency_integrity(
    dependency_tree: Path, expected_digest: str, created_mountpoints: Sequence[Path]
) -> None:
    removed: list[Path] = []
    try:
        for mountpoint in reversed(created_mountpoints):
            if mountpoint.is_symlink() or not mountpoint.is_dir():
                raise RunnerError("private dependency cache mountpoint changed shape")
            try:
                mountpoint.rmdir()
            except OSError as exc:
                raise RunnerError("private dependency cache mountpoint was modified") from exc
            removed.append(mountpoint)
        if digest_tree(dependency_tree) != expected_digest:
            raise RunnerError("private dependency snapshot changed during validation")
    finally:
        for mountpoint in reversed(removed):
            mountpoint.mkdir(mode=0o700)


def cleanup_failed_dependency_output(
    output_dir: Path, directory_fd: int, identity: tuple[int, int]
) -> None:
    def make_removable(function: Any, raw_path: str, _error: Any) -> None:
        path = Path(raw_path)
        if not path.is_symlink():
            path.chmod(stat.S_IMODE(path.lstat().st_mode) | stat.S_IRWXU)
        function(raw_path)

    require_directory_identity(output_dir, identity)
    descriptor_root = Path(f"/proc/self/fd/{directory_fd}")
    target_tree = descriptor_root / "node_modules"
    if target_tree.is_dir() and not target_tree.is_symlink():
        shutil.rmtree(target_tree, onerror=make_removable)
    try:
        os.unlink("manifest.json", dir_fd=directory_fd)
    except FileNotFoundError:
        pass
    os.fsync(directory_fd)
    require_directory_identity(output_dir, identity)
    output_dir.rmdir()


def copy_playwright_browser_artifacts(
    repo_root: Path, raw_sources: Sequence[str], target_tree: Path
) -> None:
    if not raw_sources:
        return
    destination_root = target_tree / ".playwright-browsers"
    if destination_root.exists() or destination_root.is_symlink():
        raise RunnerError("dependency tree already contains .playwright-browsers")
    destination_root.mkdir(mode=0o700)
    seen: set[str] = set()
    for raw_source in raw_sources:
        source = Path(raw_source).expanduser()
        if not source.is_absolute():
            source = (Path.cwd() / source).absolute()
        ensure_no_symlink_components(source)
        if path_is_within(repo_root, source):
            raise RunnerError("Playwright browser source must be outside the repository")
        name = source.name
        if re.fullmatch(
            r"(?:chromium|chromium_headless_shell|firefox|webkit|ffmpeg)-[0-9]+", name
        ) is None:
            raise RunnerError(f"unsupported Playwright browser directory name: {name}")
        if name in seen:
            raise RunnerError(f"duplicate Playwright browser directory: {name}")
        seen.add(name)
        source_digest = digest_tree(source)
        destination = destination_root / name
        shutil.copytree(source, destination, symlinks=True)
        if digest_tree(source) != source_digest or digest_tree(destination) != source_digest:
            raise RunnerError(f"Playwright browser directory changed while copying: {name}")


def prepare_dependency_snapshot(args: argparse.Namespace) -> int:
    git_bin = require_executable("git", args.git_bin)
    repo_root = detect_repo_root(git_bin)
    ensure_clean_worktree(repo_root, git_bin)
    source_tree = repo_root / "node_modules"
    validate_npm_dependency_tree(repo_root, source_tree, allow_hardlinks=True)
    source_tree_digest = digest_tree(source_tree, allow_hardlinks=True)
    source_metadata_fingerprint = source_tree_metadata_fingerprint(source_tree)
    output_dir, output_fd, output_identity = create_private_dependency_output_dir(
        repo_root, args.output_dir
    )
    try:
        descriptor_root = Path(f"/proc/self/fd/{output_fd}")
        target_tree = descriptor_root / "node_modules"
        shutil.copytree(source_tree, target_tree, symlinks=True)
        validate_npm_dependency_tree(repo_root, target_tree)
        target_tree_digest = digest_tree(target_tree)
        if (
            source_tree_metadata_fingerprint(source_tree) != source_metadata_fingerprint
            or digest_tree(source_tree, allow_hardlinks=True) != source_tree_digest
            or target_tree_digest != source_tree_digest
        ):
            raise RunnerError("npm dependency tree changed while the snapshot was being copied")
        copy_playwright_browser_artifacts(
            repo_root, args.playwright_browser_dir, target_tree
        )
        validate_npm_dependency_tree(repo_root, target_tree)
        target_tree_digest = digest_tree(target_tree)
        payload = {
            "schema_version": DEPENDENCY_SNAPSHOT_SCHEMA_VERSION,
            "package_manager": "npm",
            "source_head": git_text(repo_root, git_bin, "rev-parse", "HEAD"),
            "package_json_sha256": hash_file(repo_root / "package.json"),
            "package_lock_sha256": hash_file(repo_root / "package-lock.json"),
            "dependency_path": "node_modules",
            "tree_sha256": target_tree_digest,
        }
        validate_dependency_snapshot_manifest(payload)
        write_private_dependency_manifest(output_fd, payload)
        require_directory_identity(output_dir, output_identity)
    except BaseException:
        cleanup_failed_dependency_output(output_dir, output_fd, output_identity)
        raise
    finally:
        os.close(output_fd)
    manifest_path = output_dir / "manifest.json"
    print(str(manifest_path))
    return 0


def write_bytes(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hash_file(path)


def load_planlib() -> ModuleType:
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir / "planlib.py",
        script_dir.parent / "template/.project-agent-workflow/scripts/planlib.py",
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("sandboxed_plan_worker_planlib", candidate)
        if spec is None or spec.loader is None:
            break
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    raise RunnerError("could not locate managed planlib.py")


WORKTREE_GUARD_MODULE_NAME = "worktree_guard"
WORKTREE_GUARD_CANDIDATES = (
    "scripts/project_workflow/worktree_guard.py",
    ".project-agent-workflow/scripts/worktree_guard.py",
)


def load_worktree_guard(repo_root: Path) -> ModuleType | None:
    """Load the worktree guard this repository ships, once per process.

    A repository that ships no guard is left with its previous behaviour. The
    loaded instance is reused because the guard holds process-local lock state
    that a second execution would silently duplicate, but only when it came from
    this repository: a cache keyed by name alone would let one repository's
    guard govern another that ships none.
    """

    resolved = None
    for relative in WORKTREE_GUARD_CANDIDATES:
        candidate = repo_root / relative
        if candidate.is_file():
            resolved = candidate.resolve()
            break
    if resolved is None:
        return None
    cached = sys.modules.get(WORKTREE_GUARD_MODULE_NAME)
    if cached is not None and Path(getattr(cached, "__file__", "") or "/").resolve() == resolved:
        return cached
    spec = importlib.util.spec_from_file_location(WORKTREE_GUARD_MODULE_NAME, resolved)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require_plan_worktree(repo_root: Path, plan_rel: str | None, action: str) -> None:
    """Require this runner operation to start from its bound plan worktree.

    The runner clones the source repository for isolation, so its writes land in
    the checkout it was started from. Starting it in the pre-existing checkout
    would therefore apply an accepted candidate there, which is the boundary
    this check keeps closed before any repository effect.
    """

    guard = load_worktree_guard(repo_root)
    if guard is None:
        return
    try:
        guard.require_task_worktree(
            repo_root, kind=guard.PLAN_TASK, plan=plan_rel, action=action
        )
    except guard.GuardError as exc:
        raise RunnerError(str(exc)) from exc


def load_plan_validation_commands() -> ModuleType:
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir / "plan_validation_commands.py",
        script_dir.parent / "template/.project-agent-workflow/scripts/plan_validation_commands.py",
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("sandboxed_plan_worker_validation_commands", candidate)
        if spec is None or spec.loader is None:
            break
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    raise RunnerError("could not locate managed plan_validation_commands.py")


def run_subprocess(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        list(argv),
        cwd=cwd,
        env=env,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or f"exit {result.returncode}"
        raise RunnerError(f"command failed ({' '.join(argv)}): {detail}")
    return result


def kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the whole session started for one bounded command.

    The command runs under Bubblewrap in its own session, so signalling the
    group reaches the sandbox and every descendant it started.
    """

    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except OSError:
            pass


def run_bounded_subprocess(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: float,
    output_limit_bytes: int,
) -> dict[str, Any]:
    """Run one command under a hard time bound and a hard output bound.

    Output is capped while it is read rather than after the command finishes,
    so a flooding command cannot exhaust memory before the limit applies.
    Reaching either bound kills the process group; neither bound is a retry
    signal, and the caller records the reason with the bounded output.

    A reader that cannot drain its pipe to completion fails closed. It kills
    the process group and reports the failure, so a partially read capture is
    never returned as if the command had simply produced little output.
    """

    process = subprocess.Popen(  # noqa: S603 - argv is parent-owned and fully resolved
        list(argv),
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    lock = threading.Lock()
    buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    budget = {"remaining": max(0, int(output_limit_bytes)), "truncated": False}
    read_failures: list[str] = []

    def drain(stream: Any, key: str) -> None:
        try:
            while True:
                chunk = stream.read(PREFLIGHT_DRAIN_CHUNK_BYTES)
                if not chunk:
                    return
                with lock:
                    room = budget["remaining"]
                    if room:
                        buffers[key] += chunk[:room]
                        budget["remaining"] = room - min(room, len(chunk))
                    overflowed = len(chunk) > room
                    if overflowed:
                        budget["truncated"] = True
                if overflowed:
                    kill_process_group(process)
                    return
        except (OSError, MemoryError) as exc:
            with lock:
                read_failures.append(f"{key} reader stopped early: {exc.__class__.__name__}")
            kill_process_group(process)
            return
        finally:
            try:
                stream.close()
            except OSError:
                pass

    threads = [
        threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_group(process)
        try:
            process.wait(timeout=PREFLIGHT_DRAIN_JOIN_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for thread in threads:
        thread.join(timeout=PREFLIGHT_DRAIN_JOIN_SECONDS)
    stalled = [thread for thread in threads if thread.is_alive()]
    if stalled:
        kill_process_group(process)
        for thread in stalled:
            thread.join(timeout=PREFLIGHT_DRAIN_JOIN_SECONDS)
        with lock:
            read_failures.append("a reader did not finish after the process group was killed")
    with lock:
        failures = sorted(set(read_failures))
        truncated = budget["truncated"]
        stdout = bytes(buffers["stdout"])
        stderr = bytes(buffers["stderr"])
    if failures:
        raise RunnerError(
            "bounded command output could not be read to completion: " + "; ".join(failures)
        )
    return {
        "returncode": int(process.returncode if process.returncode is not None else -1),
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "output_truncated": truncated,
    }


def require_executable(name: str, configured: str) -> str:
    if os.sep in configured:
        path = Path(configured)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RunnerError(f"{name} executable is unavailable: {configured}")
        return str(path.resolve())
    resolved = shutil.which(configured)
    if resolved is None:
        raise RunnerError(f"{name} executable is unavailable: {configured}")
    return resolved


def require_validation_executable(configured: str, clone_dir: Path) -> str:
    if os.sep in configured:
        candidate = (clone_dir / configured).resolve()
        if not path_is_within(clone_dir, candidate) or not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise RunnerError("validation script must be an executable parent-owned clone path")
        return str(candidate)
    resolved = shutil.which(configured, path=DEFAULT_PATH)
    if resolved is None or not any(
        path_is_within(Path(root), Path(resolved)) for root in SANDBOX_SYSTEM_DIRECTORIES
    ):
        raise RunnerError(f"validation command executable is unavailable on the trusted system path: {configured}")
    return str(Path(resolved).resolve())


def resolve_project_node_runtime(
    repo_root: Path, git_bin: str | None = None
) -> dict[str, Any]:
    version_file = repo_root / ".node-version"
    if version_file.is_symlink() or not version_file.is_file():
        raise RunnerError("npm validation requires a regular tracked .node-version file")
    if git_bin is None:
        git_bin = require_executable("git", "git")
    index_record = git(
        repo_root,
        git_bin,
        "ls-files",
        "--stage",
        "--error-unmatch",
        "--",
        ".node-version",
        check=False,
    )
    committed_version = git(
        repo_root, git_bin, "show", "HEAD:.node-version", check=False
    )
    version_bytes = version_file.read_bytes()
    if (
        index_record.returncode != 0
        or not re.fullmatch(
            rb"100(?:644|755) (?:[0-9a-f]{40}|[0-9a-f]{64}) 0\t\.node-version\n?",
            index_record.stdout,
        )
        or committed_version.returncode != 0
        or committed_version.stdout != version_bytes
    ):
        raise RunnerError("npm validation requires .node-version to be a regular tracked HEAD file")
    try:
        requested = version_bytes.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RunnerError(".node-version must be valid UTF-8") from exc
    requested_match = re.fullmatch(r"v?([1-9][0-9]*)(?:\.[0-9]+\.[0-9]+)?", requested)
    if requested_match is None:
        raise RunnerError(".node-version must contain one major or semantic Node version")

    host_path = os.environ.get("PATH", DEFAULT_PATH)
    raw_node = shutil.which("node", path=host_path)
    raw_npm = shutil.which("npm", path=host_path)
    if raw_node is None or raw_npm is None:
        raise RunnerError("npm validation requires host node and npm executables")
    node_path = Path(raw_node).resolve()
    npm_cli_path = Path(raw_npm).resolve()
    if not node_path.is_file() or not os.access(node_path, os.X_OK):
        raise RunnerError("project Node executable is unavailable")
    if not npm_cli_path.is_file():
        raise RunnerError("project npm executable is unavailable")
    npm_package_root: Path | None = None
    for parent in npm_cli_path.parents:
        package_manifest = parent / "package.json"
        if package_manifest.is_symlink() or not package_manifest.is_file():
            continue
        package = load_json_object(package_manifest, "host npm package.json")
        if package.get("name") == "npm":
            npm_package_root = parent
            break
    if npm_package_root is None:
        raise RunnerError("project npm executable must resolve inside an npm package tree")
    npm_cli_relative = npm_cli_path.relative_to(npm_package_root)
    npm_tree_sha256 = digest_tree(npm_package_root, omit_external_symlinks=True)
    result = run_subprocess((str(node_path), "--version"), env=sanitize_process_env())
    actual = result.stdout.decode("utf-8", errors="strict").strip()
    actual_match = re.fullmatch(r"v([1-9][0-9]*)\.[0-9]+\.[0-9]+", actual)
    if actual_match is None or actual_match.group(1) != requested_match.group(1):
        raise RunnerError(
            f"host Node {actual or 'unknown'} does not match .node-version major {requested_match.group(1)}"
        )
    return {
        "requested_version": requested,
        "actual_version": actual,
        "node_path": node_path,
        "npm_package_root": npm_package_root,
        "npm_cli_relative": npm_cli_relative,
        "node_sha256": hash_file(node_path),
        "npm_sha256": hash_file(npm_cli_path),
        "npm_tree_sha256": npm_tree_sha256,
    }


def materialize_project_node_runtime(
    runtime: dict[str, Any], target_root: Path
) -> dict[str, Any]:
    if target_root.exists() or target_root.is_symlink():
        raise RunnerError("private Node runtime target must not already exist")
    private_node = target_root / "bin/node"
    private_npm_root = target_root / "lib/node_modules/npm"
    private_node.parent.mkdir(parents=True)
    private_npm_root.parent.mkdir(parents=True)
    try:
        shutil.copy2(runtime["node_path"], private_node, follow_symlinks=True)
        npm_source_root = runtime["npm_package_root"]

        def omit_external_npm_links(directory: str, names: list[str]) -> set[str]:
            parent = Path(directory)
            omitted: set[str] = set()
            for name in names:
                candidate = parent / name
                if candidate.is_symlink():
                    target = os.readlink(candidate)
                    if os.path.isabs(target) or not path_is_within(
                        npm_source_root, candidate.parent / target
                    ):
                        omitted.add(name)
            return omitted

        shutil.copytree(
            npm_source_root,
            private_npm_root,
            symlinks=True,
            ignore=omit_external_npm_links,
        )
        private_npm_cli = private_npm_root / runtime["npm_cli_relative"]
        private_npx_cli = private_npm_root / "bin/npx-cli.js"
        if not private_npx_cli.is_file() or private_npx_cli.is_symlink():
            raise RunnerError("host npm package does not contain a regular npx CLI")
        (target_root / "bin/npm").symlink_to("../lib/node_modules/npm/bin/npm-cli.js")
        (target_root / "bin/npx").symlink_to("../lib/node_modules/npm/bin/npx-cli.js")
        if (
            hash_file(private_node) != runtime["node_sha256"]
            or digest_tree(private_npm_root) != runtime["npm_tree_sha256"]
            or hash_file(private_npm_cli) != runtime["npm_sha256"]
        ):
            raise RunnerError("private Node/npm runtime differs from its verified host inputs")
        probe = run_subprocess(
            (str(private_node), str(private_npm_cli), "--version"),
            env={
                **sanitize_process_env(),
                "HOME": str(target_root / "nonexistent-home"),
                "PATH": f"{target_root / 'bin'}:{DEFAULT_PATH}",
            },
            check=False,
        )
        if probe.returncode != 0:
            raise RunnerError(
                "host npm package is not self-contained after private staging; "
                "use a project-approved self-contained Node/npm distribution"
            )
        verify_project_node_runtime(runtime)
    except BaseException:
        shutil.rmtree(target_root, ignore_errors=True)
        raise
    return {
        "runtime_root": target_root,
        "node_path": private_node,
        "npm_cli_path": private_npm_cli,
        "npm_launcher": target_root / "bin/npm",
        "npx_launcher": target_root / "bin/npx",
    }


def verify_project_node_runtime(
    runtime: dict[str, Any], private_runtime: dict[str, Any] | None = None
) -> None:
    if hash_file(runtime["node_path"]) != runtime["node_sha256"]:
        raise RunnerError("project Node executable changed during validation")
    if (
        digest_tree(runtime["npm_package_root"], omit_external_symlinks=True)
        != runtime["npm_tree_sha256"]
    ):
        raise RunnerError("project npm package tree changed during validation")
    host_npm_cli = runtime["npm_package_root"] / runtime["npm_cli_relative"]
    if hash_file(host_npm_cli) != runtime["npm_sha256"]:
        raise RunnerError("project npm CLI changed during validation")
    if private_runtime is not None:
        if (
            hash_file(private_runtime["node_path"]) != runtime["node_sha256"]
            or digest_tree(private_runtime["runtime_root"] / "lib/node_modules/npm")
            != runtime["npm_tree_sha256"]
            or hash_file(private_runtime["npm_cli_path"]) != runtime["npm_sha256"]
        ):
            raise RunnerError("private Node/npm runtime changed during validation")
        expected_launchers = {
            private_runtime["npm_launcher"]: "../lib/node_modules/npm/bin/npm-cli.js",
            private_runtime["npx_launcher"]: "../lib/node_modules/npm/bin/npx-cli.js",
        }
        if any(
            not launcher.is_symlink() or os.readlink(launcher) != expected
            for launcher, expected in expected_launchers.items()
        ):
            raise RunnerError("private npm launcher changed during validation")


def ensure_bwrap_usable(bwrap_bin: str) -> None:
    probe = run_subprocess(
        (
            bwrap_bin,
            "--unshare-all",
            "--share-net",
            "--unshare-user",
            "--new-session",
            "--disable-userns",
            "--cap-drop",
            "ALL",
            "--die-with-parent",
            "--clearenv",
            "--ro-bind",
            "/",
            "/",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--",
            "/bin/true",
        ),
        check=False,
    )
    if probe.returncode != 0:
        detail = probe.stderr.decode("utf-8", errors="replace").strip() or probe.stdout.decode(
            "utf-8", errors="replace"
        ).strip()
        raise RunnerError(f"bwrap is installed but unusable: {detail or f'exit {probe.returncode}'}")


def git(
    repo_root: Path,
    git_bin: str,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return run_subprocess(
        (git_bin, *args),
        cwd=repo_root,
        env=sanitize_process_env() if env is None else env,
        check=check,
    )


def git_text(repo_root: Path, git_bin: str, *args: str, env: dict[str, str] | None = None) -> str:
    return git(repo_root, git_bin, *args, env=env).stdout.decode("utf-8").strip()


def detect_repo_root(git_bin: str) -> Path:
    path = git_text(Path.cwd(), git_bin, "rev-parse", "--show-toplevel")
    return Path(path).resolve()


def ensure_clean_worktree(repo_root: Path, git_bin: str) -> None:
    status = git_text(repo_root, git_bin, "status", "--porcelain=1", "--untracked-files=all")
    if status:
        raise RunnerError("source repository must be clean before running or applying a sandboxed worker")


def normalize_repo_relpath(raw: str, *, allow_prefix: bool = False, label: str = "path") -> tuple[str, bool]:
    if not raw:
        raise RunnerError(f"{label} must not be empty")
    is_prefix = allow_prefix and raw.endswith("/")
    body = raw[:-1] if is_prefix else raw
    candidate = PurePosixPath(body)
    if candidate.is_absolute():
        raise RunnerError(f"{label} must be repository-relative: {raw}")
    if body in {".", ""}:
        raise RunnerError(f"{label} must not be empty or dot: {raw}")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise RunnerError(f"{label} must not contain dot or dot-dot traversal: {raw}")
    if any(part == ".git" for part in candidate.parts):
        raise RunnerError(f"{label} must not reference .git: {raw}")
    normalized = candidate.as_posix()
    if normalized != body:
        raise RunnerError(f"{label} is malformed and must already be normalized: {raw}")
    return (f"{normalized}/" if is_prefix else normalized, is_prefix)


def normalize_manifest_path(repo_root: Path, raw: str) -> str:
    path = Path(raw)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (repo_root / path).resolve()
    try:
        relative = resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise RunnerError(f"path is outside the repository: {raw}") from exc
    normalized, _ = normalize_repo_relpath(relative.as_posix(), label="path")
    return normalized


def ensure_no_symlink_path_trick(
    repo_root: Path, relative_path: str, *, include_target: bool = True
) -> None:
    current = repo_root
    parts = PurePosixPath(relative_path).parts
    if not include_target:
        parts = parts[:-1]
    for part in parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if current.is_symlink():
                raise RunnerError(f"path resolves through a symlink and is rejected: {relative_path}")


def parse_write_scope(entries: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in entries:
        value, _ = normalize_repo_relpath(raw, allow_prefix=True, label="write_scope entry")
        if value in seen:
            raise RunnerError(f"write_scope must not contain duplicate entries: {value}")
        normalized.append(value)
        seen.add(value)
    for entry in normalized:
        if any(parent.endswith("/") and entry.startswith(parent) for parent in normalized if parent != entry):
            raise RunnerError(f"write_scope must not contain overlapping entries: {entry}")
    return normalized


def scope_allows_path(scope_entries: Sequence[str], relative_path: str) -> bool:
    for entry in scope_entries:
        if entry.endswith("/"):
            if relative_path.startswith(entry):
                return True
        elif relative_path == entry:
            return True
    return False


def is_validation_authority_path(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    if scope_allows_path(VALIDATION_AUTHORITY_SCOPE, relative_path):
        return True
    if path.name in VALIDATION_AUTHORITY_BASENAMES or path.name in VALIDATION_MANIFEST_BASENAMES:
        return True
    if path.parts and path.parts[0].startswith("."):
        return True
    return (
        VALIDATION_TEST_NAME.search(relative_path) is not None
        or VALIDATION_CONFIG_NAME.search(relative_path) is not None
    )


def scope_entries_overlap(left: str, right: str) -> bool:
    left_value, left_prefix = normalize_repo_relpath(left, allow_prefix=True, label="scope entry")
    right_value, right_prefix = normalize_repo_relpath(right, allow_prefix=True, label="protected entry")
    left_body = left_value[:-1] if left_prefix else left_value
    right_body = right_value[:-1] if right_prefix else right_value
    if left_body == right_body:
        return True
    if left_prefix and right_body.startswith(left_body + "/"):
        return True
    return right_prefix and left_body.startswith(right_body + "/")


def normalized_contract_paths(entries: object, *, label: str) -> list[str]:
    if not isinstance(entries, list):
        raise RunnerError(f"plan {label} must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, str):
            raise RunnerError(f"plan {label} entry must be text")
        value, _ = normalize_repo_relpath(raw, label=f"{label} entry")
        if value in seen:
            raise RunnerError(f"plan {label} must not contain duplicate entries: {value}")
        seen.add(value)
        normalized.append(value)
    return normalized


def require_safe_delegated_write_scope(
    repo_root: Path,
    plan_rel: str,
    values: dict[str, str | list[str]],
    normalized_scope: Sequence[str],
) -> None:
    context_files = normalized_contract_paths(values.get("context_files"), label="context_files")
    required_specs = normalized_contract_paths(values.get("required_specs"), label="required_specs")
    declared_authority = values.get("validation_authority_scope", [])
    if not isinstance(declared_authority, list):
        raise RunnerError("plan validation_authority_scope must be a list")
    normalized_declared_authority = parse_write_scope(declared_authority)
    protected = [plan_rel, *context_files, *required_specs]
    try:
        protected.append(Path(__file__).resolve().relative_to(repo_root.resolve()).as_posix())
    except ValueError:
        pass
    for entry in normalized_scope:
        if entry.endswith("/"):
            raise RunnerError(f"writable delegation requires one explicit file path, not a directory prefix: {entry}")
        if any(scope_entries_overlap(entry, item) for item in protected):
            raise RunnerError(f"write_scope overlaps a read-only plan, runner, context, or specification input: {entry}")
        if is_validation_authority_path(entry) or any(
            scope_entries_overlap(entry, item)
            for item in (*VALIDATION_AUTHORITY_SCOPE, *normalized_declared_authority)
        ):
            raise RunnerError(f"write_scope reaches parent-owned validation authority: {entry}")
        ensure_no_symlink_path_trick(repo_root, entry)
        target = repo_root / entry
        if target.exists() or target.is_symlink():
            if not target.is_file() or target.is_symlink():
                raise RunnerError(f"explicit write_scope target must be a regular file: {entry}")
            continue
        parent = target.parent
        ensure_no_symlink_path_trick(repo_root, parent.relative_to(repo_root).as_posix())
        if not parent.is_dir() or parent.is_symlink():
            raise RunnerError(f"new explicit write_scope target requires an existing regular parent directory: {entry}")


def load_plan(planlib: ModuleType, repo_root: Path, plan_arg: str) -> tuple[Path, str, dict[str, str | list[str]], list[str]]:
    plan_rel = normalize_manifest_path(repo_root, plan_arg)
    if not PLAN_PATTERN.fullmatch(plan_rel):
        raise RunnerError("run requires a numbered in-progress active plan under docs/plan/active/")
    plan_path = repo_root / plan_rel
    if not plan_path.is_file():
        raise RunnerError(f"missing active plan: {plan_rel}")
    values = planlib.require_manifest_fields(plan_path)
    if values.get("implementation_mode") == "parent_direct":
        raise RunnerError(
            "parent-direct plans cannot start a sandboxed candidate worker"
        )
    status = planlib.manifest_scalar(values, "status")
    if status != "in_progress":
        raise RunnerError(f"plan must be in_progress: {plan_rel}")
    plan_id = plan_path.name[:3]
    planlib.check_active_mapping(plan_id, plan_rel, "in_progress")
    write_scope = values.get("write_scope", [])
    if not isinstance(write_scope, list):
        raise RunnerError(f"plan write_scope must be a list: {plan_rel}")
    normalized_scope = parse_write_scope(write_scope)
    require_safe_delegated_write_scope(repo_root, plan_rel, values, normalized_scope)
    require_primary_invariant(plan_path, values)
    return plan_path, plan_rel, values, normalized_scope


def require_primary_invariant(plan_path: Path, values: dict[str, str | list[str]]) -> str:
    """Require one explicit delegation boundary without tightening archival parsing."""
    declarations = re.findall(
        r"^primary_invariant:\s*(.*)$",
        plan_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if len(declarations) != 1 or not declarations[0].strip():
        raise RunnerError("writable delegated plan must declare exactly one nonblank primary_invariant")
    value = values.get("primary_invariant")
    if not isinstance(value, str) or value.strip() != declarations[0].strip():
        raise RunnerError("plan primary_invariant is ambiguous")
    return value.strip()


def canonical_repository_origin(raw: str) -> str:
    """Normalize one credential-free network origin without retaining the raw URL."""
    if not raw or len(raw.encode("utf-8")) > 4096 or any(ord(char) < 0x20 for char in raw):
        raise RunnerError("repository origin must be one bounded nonblank URL")
    if "://" not in raw:
        match = re.fullmatch(r"(?:[^@/:\s]+@)?([^/:\s]+):(.+)", raw)
        if match is None:
            raise RunnerError("repository origin must be a clone-portable network URL")
        host = match.group(1).lower()
        path = match.group(2)
        port = ""
    else:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"https", "ssh", "git"} or parsed.hostname is None:
            raise RunnerError("repository origin must use https, ssh, or git")
        if parsed.query or parsed.fragment:
            raise RunnerError("repository origin must not contain a query or fragment")
        host = parsed.hostname.lower()
        try:
            parsed_port = parsed.port
        except ValueError as exc:
            raise RunnerError("repository origin has an invalid port") from exc
        default_port = {"https": 443, "ssh": 22, "git": 9418}[parsed.scheme.lower()]
        port = f":{parsed_port}" if parsed_port is not None and parsed_port != default_port else ""
        path = parsed.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not host or not path or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts):
        raise RunnerError("repository origin has an invalid repository path")
    return f"{host}{port}/{path}"


def derive_repository_identity(repo_root: Path, git_bin: str) -> str:
    result = git(repo_root, git_bin, "config", "--get", "remote.origin.url", check=False)
    if result.returncode != 0:
        raise RunnerError("worker execution contract requires a canonical remote.origin.url")
    try:
        origin = result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise RunnerError("repository origin is not valid UTF-8") from exc
    canonical = canonical_repository_origin(origin)
    return "origin-sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def unique_contract_text_items(entries: object, *, label: str, require_nonempty: bool) -> list[str]:
    if not isinstance(entries, list) or (require_nonempty and not entries):
        qualifier = "a nonempty list" if require_nonempty else "a list"
        raise RunnerError(f"plan {label} must be {qualifier} of nonblank text")
    seen: set[str] = set()
    validated: list[str] = []
    for item in entries:
        if not isinstance(item, str) or not item.strip():
            raise RunnerError(f"plan {label} must be a list of nonblank text")
        key = item.strip()
        if key in seen:
            raise RunnerError(f"plan {label} must not contain duplicate entries")
        seen.add(key)
        validated.append(item)
    return validated


def validate_contract_lineage(lineage: object) -> dict[str, object]:
    if not isinstance(lineage, dict):
        raise RunnerError("worker execution contract lineage must be an object")
    kind = lineage.get("attempt_kind")
    expected = {"attempt_kind", "correction_round", "attempt_label"}
    if kind == "correction":
        expected.update(
            {"prior_manifest_digest", "prior_patch_digest", "correction_brief_digest"}
        )
    if set(lineage) != expected:
        raise RunnerError("worker execution contract lineage has an invalid exact field shape")
    round_value = lineage.get("correction_round")
    if kind not in {"initial", "correction"} or isinstance(round_value, bool) or not isinstance(round_value, int):
        raise RunnerError("worker execution contract lineage has invalid values")
    if (kind == "initial" and round_value != 0) or (kind == "correction" and round_value < 1):
        raise RunnerError("worker execution contract lineage has an invalid correction round")
    if lineage.get("attempt_label") not in {"primary", "fallback", "custom"}:
        raise RunnerError("worker execution contract lineage has an invalid attempt label")
    if kind == "correction":
        for key in ("prior_manifest_digest", "prior_patch_digest", "correction_brief_digest"):
            value = lineage.get(key)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise RunnerError(f"worker execution contract lineage has an invalid digest: {key}")
    return lineage


def load_exact_json_object(content: bytes, *, label: str) -> dict[str, Any]:
    def exact_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RunnerError(f"{label} contains a duplicate field: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=exact_pairs)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise RunnerError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"{label} must contain one JSON object")
    return value


def prefixed_sha256(value: bytes | str) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def require_receipt_digest(value: object, *, label: str, allow_origin: bool = False) -> str:
    prefix = r"(?:origin-)?sha256" if allow_origin else "sha256"
    if not isinstance(value, str) or re.fullmatch(prefix + r":[0-9a-f]{64}", value) is None:
        raise RunnerError(f"worker completion receipt has an invalid {label}")
    return value


def require_receipt_code(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value.encode("utf-8")) > WORKER_COMPLETION_RECEIPT_VALUE_MAX_BYTES
        or re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", value) is None
    ):
        raise RunnerError(f"worker completion receipt contains prohibited or oversized {label}")
    return value


def require_receipt_code_list(
    value: object, *, label: str, allowed: frozenset[str]
) -> list[str]:
    if not isinstance(value, list) or len(value) > WORKER_COMPLETION_RECEIPT_MAX_ITEMS:
        raise RunnerError(f"worker completion receipt has an invalid {label} list")
    result = [require_receipt_code(item, label=label) for item in value]
    if any(item not in allowed for item in result):
        raise RunnerError(f"worker completion receipt contains a non-allowlisted {label}")
    if len(result) != len(set(result)):
        raise RunnerError(f"worker completion receipt has duplicate {label} entries")
    return result


def require_completion_exit_status(value: object, *, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not WORKER_COMPLETION_EXIT_STATUS_MIN <= value <= WORKER_COMPLETION_EXIT_STATUS_MAX
    ):
        raise RunnerError(f"worker completion receipt has an invalid or unbounded {label}")
    return value


def validate_worker_completion_claims(value: object) -> dict[str, Any]:
    required = {
        "attempt_result", "acceptance_evidence", "commands_attempted", "blockers",
        "residual_risks", "out_of_scope_change",
    }
    if not isinstance(value, dict) or set(value) != required:
        if isinstance(value, dict) and "out_of_scope_change" not in value:
            raise RunnerError("worker completion receipt is missing the out-of-scope declaration")
        raise RunnerError("worker completion receipt claims have unknown or missing fields")
    if value["attempt_result"] not in {"success", "failure"}:
        raise RunnerError("worker completion receipt has an invalid attempt result")
    evidence = value["acceptance_evidence"]
    if not isinstance(evidence, list) or len(evidence) > WORKER_COMPLETION_RECEIPT_MAX_ITEMS:
        raise RunnerError("worker completion receipt has invalid acceptance evidence")
    normalized_evidence: list[dict[str, str]] = []
    seen_evidence: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"acceptance_digest", "claim"}:
            raise RunnerError("worker completion receipt has invalid acceptance evidence")
        digest = require_receipt_digest(item["acceptance_digest"], label="acceptance digest")
        if digest in seen_evidence or item["claim"] not in {"satisfied", "not_satisfied"}:
            raise RunnerError("worker completion receipt has invalid acceptance evidence")
        seen_evidence.add(digest)
        normalized_evidence.append({"acceptance_digest": digest, "claim": item["claim"]})
    commands = value["commands_attempted"]
    if not isinstance(commands, list) or len(commands) > WORKER_COMPLETION_RECEIPT_MAX_ITEMS:
        raise RunnerError("worker completion receipt has invalid command evidence")
    normalized_commands: list[dict[str, object]] = []
    seen_commands: set[str] = set()
    for index, item in enumerate(commands, start=1):
        if not isinstance(item, dict) or set(item) != {"command_id", "exit_status"}:
            raise RunnerError("worker completion receipt has invalid command evidence")
        command_id = require_receipt_code(item["command_id"], label="command identifier")
        if command_id != f"worker-check-{index}":
            raise RunnerError("worker completion receipt contains a non-derived command identifier")
        status = require_completion_exit_status(
            item["exit_status"], label="command exit status"
        )
        if command_id in seen_commands:
            raise RunnerError("worker completion receipt has invalid command evidence")
        seen_commands.add(command_id)
        normalized_commands.append({"command_id": command_id, "exit_status": status})
    if not isinstance(value["out_of_scope_change"], bool):
        raise RunnerError("worker completion receipt has an invalid out-of-scope declaration")
    return {
        "attempt_result": value["attempt_result"],
        "acceptance_evidence": normalized_evidence,
        "commands_attempted": normalized_commands,
        "blockers": require_receipt_code_list(
            value["blockers"], label="blocker", allowed=WORKER_COMPLETION_BLOCKER_CODES
        ),
        "residual_risks": require_receipt_code_list(
            value["residual_risks"], label="residual risk", allowed=WORKER_COMPLETION_RISK_CODES
        ),
        "out_of_scope_change": value["out_of_scope_change"],
    }


def validate_receipt_attempt(value: object) -> dict[str, Any]:
    required = {"attempt_id", "attempt_kind", "correction_round", "correction_lineage"}
    if not isinstance(value, dict) or set(value) != required:
        raise RunnerError("worker completion receipt attempt has an invalid exact field shape")
    attempt_id = require_receipt_code(value["attempt_id"], label="attempt identifier")
    kind = value["attempt_kind"]
    round_value = value["correction_round"]
    lineage = value["correction_lineage"]
    if kind not in {"initial", "correction"} or isinstance(round_value, bool) or not isinstance(round_value, int):
        raise RunnerError("worker completion receipt attempt lineage is invalid")
    if kind == "initial":
        if round_value != 0 or lineage is not None:
            raise RunnerError("worker completion receipt attempt lineage is invalid")
    elif (
        round_value < 1
        or not isinstance(lineage, dict)
        or set(lineage) != {"prior_manifest_digest"}
    ):
        raise RunnerError("worker completion receipt attempt lineage is invalid")
    else:
        lineage = {
            "prior_manifest_digest": require_receipt_digest(
                lineage["prior_manifest_digest"], label="prior manifest digest"
            )
        }
    return {
        "attempt_id": attempt_id,
        "attempt_kind": kind,
        "correction_round": round_value,
        "correction_lineage": lineage,
    }


def validate_receipt_candidate(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"patch_digest", "changed_paths"}:
        raise RunnerError("worker completion receipt candidate has an invalid exact field shape")
    raw_paths = value["changed_paths"]
    if not isinstance(raw_paths, list) or not raw_paths or len(raw_paths) > WORKER_COMPLETION_RECEIPT_MAX_ITEMS:
        raise RunnerError("worker completion receipt changed paths are invalid")
    paths: list[str] = []
    for raw in raw_paths:
        if not isinstance(raw, str):
            raise RunnerError("worker completion receipt changed paths are invalid")
        normalized, _ = normalize_repo_relpath(raw, label="worker completion receipt changed path")
        paths.append(normalized)
    if len(paths) != len(set(paths)) or paths != sorted(paths):
        raise RunnerError("worker completion receipt changed paths are not unique and sorted")
    return {
        "patch_digest": require_receipt_digest(value["patch_digest"], label="patch digest"),
        "changed_paths": paths,
    }


def validate_worker_completion_receipt(
    value: object,
    *,
    expected: dict[str, object] | None = None,
    consumed_attempt_ids: Sequence[str] = (),
) -> dict[str, Any]:
    required = {
        "schema_version", "repository_identity", "source_head", "plan_path", "plan_digest",
        "worker_contract_digest", "orchestration_run_id", "plan_execution_attempt_id",
        "attempt", "candidate", "process", "claims",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RunnerError("worker completion receipt has unknown or missing fields")
    if value["schema_version"] != WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION:
        raise RunnerError("worker completion receipt has an unsupported schema version")
    repository_identity = require_receipt_digest(
        value["repository_identity"], label="repository identity", allow_origin=True
    )
    source_head = value["source_head"]
    if not isinstance(source_head, str) or re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise RunnerError("worker completion receipt has an invalid source HEAD")
    if not isinstance(value["plan_path"], str):
        raise RunnerError("worker completion receipt plan path is invalid")
    plan_path, _ = normalize_repo_relpath(
        value["plan_path"], label="worker completion receipt plan path"
    )
    plan_digest = require_receipt_digest(value["plan_digest"], label="plan digest")
    contract_digest = require_receipt_digest(
        value["worker_contract_digest"], label="worker contract digest"
    )
    run_id = value["orchestration_run_id"]
    validate_bounded_text(run_id, "worker completion receipt run identifier", ORCHESTRATION_RUN_ID_MAX_BYTES)
    plan_execution_attempt_id = require_receipt_code(
        value["plan_execution_attempt_id"], label="plan execution attempt identifier"
    )
    attempt = validate_receipt_attempt(value["attempt"])
    if attempt["attempt_id"] in consumed_attempt_ids:
        raise RunnerError("worker completion receipt replays a consumed attempt")
    candidate = validate_receipt_candidate(value["candidate"])
    process = value["process"]
    if not isinstance(process, dict) or set(process) != {"exit_status", "diagnostic_codes"}:
        raise RunnerError("worker completion receipt process has an invalid exact field shape")
    exit_status = require_completion_exit_status(
        process["exit_status"], label="process exit status"
    )
    diagnostic_codes = require_receipt_code_list(
        process["diagnostic_codes"],
        label="diagnostic",
        allowed=WORKER_COMPLETION_DIAGNOSTIC_CODES,
    )
    claims = validate_worker_completion_claims(value["claims"])
    if claims["attempt_result"] == "success" and exit_status != 0:
        raise RunnerError("worker completion receipt makes a false success claim")
    if claims["attempt_result"] == "success" and any(
        item["claim"] != "satisfied" for item in claims["acceptance_evidence"]
    ):
        raise RunnerError("worker completion receipt success has unsatisfied acceptance evidence")
    if candidate is not None and exit_status != 0:
        raise RunnerError("worker completion receipt binds a candidate to a failed process")
    if (exit_status == 0) != (not diagnostic_codes):
        raise RunnerError("worker completion receipt diagnostics differ from process status")
    if claims["attempt_result"] == "success" and (candidate is None or not claims["acceptance_evidence"]):
        raise RunnerError("worker completion receipt success lacks candidate evidence")
    if candidate is None and claims["acceptance_evidence"]:
        raise RunnerError("worker completion receipt has evidence without a candidate")
    if candidate is not None and not claims["acceptance_evidence"]:
        raise RunnerError("worker completion receipt candidate lacks acceptance evidence")
    normalized = {
        "schema_version": WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION,
        "repository_identity": repository_identity,
        "source_head": source_head,
        "plan_path": plan_path,
        "plan_digest": plan_digest,
        "worker_contract_digest": contract_digest,
        "orchestration_run_id": run_id,
        "plan_execution_attempt_id": plan_execution_attempt_id,
        "attempt": attempt,
        "candidate": candidate,
        "process": {"exit_status": exit_status, "diagnostic_codes": diagnostic_codes},
        "claims": claims,
    }
    if expected is not None:
        for field, error in (
            ("repository_identity", "repository identity mismatch"),
            ("source_head", "stale receipt source HEAD"),
            ("plan_path", "receipt plan path mismatch"),
            ("plan_digest", "receipt plan digest mismatch"),
            ("worker_contract_digest", "receipt worker contract digest mismatch"),
            ("orchestration_run_id", "receipt orchestration run mismatch"),
            ("plan_execution_attempt_id", "receipt plan execution attempt mismatch"),
            ("attempt", "receipt attempt lineage mismatch"),
        ):
            if field in expected and normalized[field] != expected[field]:
                raise RunnerError(error)
        if "candidate" in expected:
            expected_candidate = expected["candidate"]
            if normalized["candidate"] is None or not isinstance(expected_candidate, dict):
                if normalized["candidate"] != expected_candidate:
                    raise RunnerError("receipt candidate mismatch")
            else:
                if normalized["candidate"]["patch_digest"] != expected_candidate.get("patch_digest"):
                    raise RunnerError("receipt patch digest mismatch")
                if normalized["candidate"]["changed_paths"] != expected_candidate.get("changed_paths"):
                    raise RunnerError("receipt changed paths mismatch")
        if "acceptance_digests" in expected:
            expected_digests = expected["acceptance_digests"]
            observed_digests = [
                item["acceptance_digest"] for item in normalized["claims"]["acceptance_evidence"]
            ]
            if not isinstance(expected_digests, list) or set(observed_digests) != set(expected_digests):
                raise RunnerError("receipt acceptance evidence differs from the worker contract")
    return normalized


def serialize_worker_completion_receipt(value: object) -> bytes:
    normalized = validate_worker_completion_receipt(value)
    content = (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(content) > WORKER_COMPLETION_RECEIPT_MAX_BYTES:
        raise RunnerError("worker completion receipt exceeds the byte bound")
    return content


def load_worker_completion_receipt(content: bytes) -> dict[str, Any]:
    if len(content) > WORKER_COMPLETION_RECEIPT_MAX_BYTES:
        raise RunnerError("worker completion receipt exceeds the byte bound")
    return validate_worker_completion_receipt(
        load_exact_json_object(content, label="worker completion receipt")
    )


def verify_worker_completion_receipt_path(attempt_output: Path, relative_path: str) -> Path:
    normalized, _ = normalize_repo_relpath(relative_path, label="worker completion receipt path")
    if normalized != "worker-completion-receipt.json":
        raise RunnerError("worker completion receipt path must use the fixed attempt output name")
    path = attempt_output / normalized
    ensure_no_symlink_components(path)
    if path.is_symlink():
        raise RunnerError("worker completion receipt path must not be a symlink")
    return path


def receipt_attempt_from_contract_lineage(
    lineage: dict[str, object], *, attempt_id: str | None = None
) -> dict[str, Any]:
    validated = validate_contract_lineage(lineage)
    kind = validated["attempt_kind"]
    round_value = int(validated["correction_round"])
    label = str(validated["attempt_label"])
    return {
        "attempt_id": attempt_id or f"{kind}-{round_value}-{label}",
        "attempt_kind": kind,
        "correction_round": round_value,
        "correction_lineage": None if kind == "initial" else {
            "prior_manifest_digest": "sha256:" + str(validated["prior_manifest_digest"])
        },
    }


def safe_failure_claims(code: str) -> dict[str, Any]:
    if code not in WORKER_COMPLETION_BLOCKER_CODES:
        raise RunnerError("safe worker completion blocker is not allowlisted")
    return {
        "attempt_result": "failure",
        "acceptance_evidence": [],
        "commands_attempted": [],
        "blockers": [require_receipt_code(code, label="blocker")],
        "residual_risks": ["parent_review_required"],
        "out_of_scope_change": False,
    }


def load_attempt_completion_claims(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists() and not path.is_symlink():
        return None, "missing_completion_claims"
    try:
        content = read_bounded_regular_file(
            path, WORKER_COMPLETION_RECEIPT_MAX_BYTES, "worker completion claims"
        )
        claims = validate_worker_completion_claims(
            load_exact_json_object(content, label="worker completion claims")
        )
    except RunnerError:
        return None, "invalid_completion_claims"
    return claims, None


def completion_receipt_artifact_key(label: str) -> str:
    return (
        "worker-completion-receipt.json"
        if label == "custom"
        else f"worker-{label}-completion-receipt.json"
    )


def process_result_artifact_key(label: str) -> str:
    return "worker-process-result.json" if label == "custom" else f"worker-{label}-process-result.json"


def validate_attempt_process_result(value: object) -> dict[str, Any]:
    required = {
        "schema_version", "attempt_id", "exit_status", "diagnostic_codes",
        "stdout_digest", "stderr_digest",
    }
    if not isinstance(value, dict) or set(value) != required or value["schema_version"] != 1:
        raise RunnerError("worker process result has an invalid exact schema")
    attempt_id = require_receipt_code(value["attempt_id"], label="attempt identifier")
    exit_status = require_completion_exit_status(
        value["exit_status"], label="process exit status"
    )
    diagnostic_codes = require_receipt_code_list(
        value["diagnostic_codes"],
        label="diagnostic",
        allowed=WORKER_COMPLETION_DIAGNOSTIC_CODES,
    )
    if (exit_status == 0) != (not diagnostic_codes):
        raise RunnerError("worker process result diagnostics differ from exit status")
    stdout_digest = require_receipt_digest(value["stdout_digest"], label="stdout digest")
    stderr_digest = require_receipt_digest(value["stderr_digest"], label="stderr digest")
    return {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "exit_status": exit_status,
        "diagnostic_codes": diagnostic_codes,
        "stdout_digest": stdout_digest,
        "stderr_digest": stderr_digest,
    }


def write_attempt_process_result(
    *,
    label: str,
    attempt_id: str,
    result: subprocess.CompletedProcess[bytes],
    stdout_digest: str,
    stderr_digest: str,
    reserved_artifacts: dict[str, Path],
) -> tuple[Path, str, dict[str, Any]]:
    payload = validate_attempt_process_result(
        {
            "schema_version": 1,
            "attempt_id": attempt_id,
            "exit_status": result.returncode,
            "diagnostic_codes": [] if result.returncode == 0 else ["worker_failed"],
            "stdout_digest": "sha256:" + stdout_digest,
            "stderr_digest": "sha256:" + stderr_digest,
        }
    )
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path = reserved_artifacts[process_result_artifact_key(label)]
    path.write_bytes(content)
    return path, prefixed_sha256(content), payload


def write_attempt_completion_receipt(
    attempt: dict[str, Any],
    *,
    reserved_artifacts: dict[str, Path],
    candidate: dict[str, Any] | None,
    final: bool,
) -> dict[str, Any]:
    contract = load_exact_json_object(
        attempt["contract_bytes"], label="worker execution contract"
    )
    result: subprocess.CompletedProcess[bytes] = attempt["result"]
    claims = attempt["completion_claims"]
    claims_error = attempt["completion_claims_error"]
    diagnostic_codes = [] if result.returncode == 0 else ["worker_failed"]
    if claims_error is not None:
        selected_claims = safe_failure_claims(claims_error)
        selected_candidate = None
    elif result.returncode != 0 and claims["attempt_result"] == "success":
        selected_claims = safe_failure_claims("false_success_claim")
        selected_candidate = None
        attempt["completion_claims_error"] = "false_success_claim"
    elif not final:
        selected_claims = safe_failure_claims("candidate_not_derived")
        selected_candidate = None
    else:
        expected_acceptance_list = [
            prefixed_sha256(item) for item in contract["acceptance"]
        ]
        expected_acceptance = set(expected_acceptance_list)
        observed_acceptance = {
            item["acceptance_digest"] for item in claims["acceptance_evidence"]
        }
        bounded_failure_evidence = [
            {"acceptance_digest": digest, "claim": "not_satisfied"}
            for digest in expected_acceptance_list
        ]
        if claims["attempt_result"] == "failure":
            selected_claims = {
                **claims,
                "acceptance_evidence": (
                    bounded_failure_evidence if candidate is not None else []
                ),
            }
            selected_candidate = candidate
        elif observed_acceptance != expected_acceptance:
            selected_claims = {
                **safe_failure_claims("acceptance_evidence_mismatch"),
                "acceptance_evidence": bounded_failure_evidence,
            }
            selected_candidate = candidate
            attempt["completion_claims_error"] = "acceptance_evidence_mismatch"
        elif claims["out_of_scope_change"]:
            selected_claims = {
                **safe_failure_claims("out_of_scope_change_reported"),
                "acceptance_evidence": bounded_failure_evidence,
            }
            selected_candidate = candidate
            attempt["completion_claims_error"] = "out_of_scope_change_reported"
        else:
            selected_claims = claims
            selected_candidate = candidate
    receipt = {
        "schema_version": WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION,
        "repository_identity": contract["repository_identity"],
        "source_head": contract["source_head"],
        "plan_path": contract["plan_path"],
        "plan_digest": "sha256:" + contract["plan_digest"],
        "worker_contract_digest": prefixed_sha256(attempt["contract_bytes"]),
        "orchestration_run_id": contract["orchestration_run_id"],
        "plan_execution_attempt_id": contract["plan_execution_attempt_id"],
        "attempt": receipt_attempt_from_contract_lineage(
            contract["attempt_lineage"], attempt_id=attempt["attempt_id"]
        ),
        "candidate": selected_candidate,
        "process": {
            "exit_status": result.returncode,
            "diagnostic_codes": diagnostic_codes,
        },
        "claims": selected_claims,
    }
    content = serialize_worker_completion_receipt(receipt)
    receipt_path = verify_worker_completion_receipt_path(
        attempt["scratch_dir"], "worker-completion-receipt.json"
    )
    receipt_path.write_bytes(content)
    artifact_path = reserved_artifacts[completion_receipt_artifact_key(attempt["record"]["label"])]
    artifact_path.write_bytes(content)
    receipt_digest = prefixed_sha256(content)
    attempt["record"]["completion_receipt_path"] = str(artifact_path)
    attempt["record"]["completion_receipt_digest"] = receipt_digest
    attempt["record"]["completion_claims_valid"] = attempt["completion_claims_error"] is None
    attempt["record"]["completion_receipt_valid"] = True
    attempt["completion_receipt"] = receipt
    attempt["completion_receipt_path"] = artifact_path
    attempt["completion_receipt_digest"] = receipt_digest
    return receipt


def derive_worker_contract(
    *,
    repo_root: Path,
    git_bin: str,
    head: str,
    plan_path: Path,
    plan_rel: str,
    plan_digest: str,
    values: dict[str, str | list[str]],
    normalized_scope: Sequence[str],
    run_id: str,
    plan_execution_attempt_id: str,
    lineage: dict[str, object],
) -> bytes:
    """Project authoritative plan fields into one bounded, read-only worker input."""
    primary_invariant = require_primary_invariant(plan_path, values)
    context_files = normalized_contract_paths(values.get("context_files"), label="context_files")
    required_specs = normalized_contract_paths(values.get("required_specs"), label="required_specs")
    acceptance = unique_contract_text_items(values.get("acceptance"), label="acceptance", require_nonempty=True)
    focused_validation = unique_contract_text_items(
        values.get("focused_validation", []), label="focused_validation", require_nonempty=False
    )
    validated_lineage = validate_contract_lineage(lineage)
    require_safe_delegated_write_scope(repo_root, plan_rel, values, normalized_scope)
    for relative in [*context_files, *required_specs]:
        ensure_no_symlink_path_trick(repo_root, relative)
        target = repo_root / relative
        if not target.is_file() or target.is_symlink():
            raise RunnerError(f"worker contract input must be an existing regular file: {relative}")
    if hash_file(plan_path) != plan_digest:
        raise RunnerError("active plan changed while deriving the worker contract")
    if git(repo_root, git_bin, "show", f"{head}:{plan_rel}").stdout != plan_path.read_bytes():
        raise RunnerError("worker execution contract requires the exact committed active-plan bytes")
    contract = {
        "schema_version": WORKER_CONTRACT_SCHEMA_VERSION,
        "repository_identity": derive_repository_identity(repo_root, git_bin),
        "source_head": head,
        "plan_path": plan_rel,
        "plan_digest": plan_digest,
        "orchestration_run_id": run_id,
        "plan_execution_attempt_id": plan_execution_attempt_id,
        "attempt_lineage": validated_lineage,
        "primary_invariant": primary_invariant,
        "write_scope": list(normalized_scope),
        "context_files": context_files,
        "required_specs": required_specs,
        "acceptance": acceptance,
        "focused_validation": focused_validation,
        "explicit_exclusions": [
            "prompts", "worker_output", "environment_values", "credentials",
            "absolute_paths", "raw_logs", "undeclared_files",
        ],
        "hard_stop_conditions": [
            "plan_or_contract_mismatch", "unknown_or_duplicate_field",
            "path_escape_or_symlink", "authority_widening", "out_of_scope_change",
        ],
    }
    content = (
        json.dumps(contract, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")
    if len(content) > WORKER_CONTRACT_MAX_BYTES:
        raise RunnerError("worker execution contract exceeds the byte bound")
    return content


def verify_worker_contract(
    *,
    repo_root: Path,
    git_bin: str,
    manifest_path: Path,
    manifest: dict[str, Any],
    plan_path: Path,
    plan_rel: str,
    values: dict[str, str | list[str]],
    normalized_scope: Sequence[str],
) -> None:
    raw_path = manifest.get("worker_contract_path")
    digest = manifest.get("worker_contract_digest")
    if not isinstance(raw_path, str) or not isinstance(digest, str):
        raise RunnerError("candidate manifest is missing the worker execution contract binding")
    contract_path = Path(raw_path)
    if not contract_path.is_absolute() or contract_path.parent != manifest_path.parent:
        raise RunnerError("worker execution contract must be a sibling of the candidate manifest")
    content = read_bounded_regular_file(
        contract_path, WORKER_CONTRACT_MAX_BYTES, "worker execution contract"
    )
    if hash_file(contract_path) != digest:
        raise RunnerError("worker execution contract digest no longer matches the candidate manifest")
    contract = load_exact_json_object(content, label="worker execution contract")
    expected_fields = {
        "schema_version", "repository_identity", "source_head", "plan_path", "plan_digest",
        "orchestration_run_id", "plan_execution_attempt_id", "attempt_lineage",
        "primary_invariant", "write_scope",
        "context_files", "required_specs", "acceptance", "focused_validation",
        "explicit_exclusions", "hard_stop_conditions",
    }
    if set(contract) != expected_fields or contract.get("schema_version") != WORKER_CONTRACT_SCHEMA_VERSION:
        raise RunnerError("worker execution contract has unknown or missing fields")
    lineage = validate_contract_lineage(contract.get("attempt_lineage"))
    attempt_label = manifest.get("worker_attempt_label")
    if attempt_label not in {"primary", "fallback", "custom"}:
        raise RunnerError("candidate manifest has an invalid worker attempt label")
    manifest_lineage = manifest.get("correction_lineage")
    expected_lineage = (
        {
            "attempt_kind": "initial",
            "correction_round": 0,
            "attempt_label": attempt_label,
        }
        if manifest_lineage is None
        else {
            "attempt_kind": "correction",
            **manifest_lineage,
            "attempt_label": attempt_label,
        }
    )
    if any(lineage.get(key) != value for key, value in expected_lineage.items()):
        raise RunnerError("worker execution contract lineage differs from the candidate manifest")
    if contract.get("plan_execution_attempt_id") != manifest.get("plan_execution_attempt_id"):
        raise RunnerError("worker execution contract plan attempt differs from the candidate manifest")
    fresh = derive_worker_contract(
        repo_root=repo_root,
        git_bin=git_bin,
        head=str(manifest["source_head"]),
        plan_path=plan_path,
        plan_rel=plan_rel,
        plan_digest=str(manifest["plan_digest"]),
        values=values,
        normalized_scope=normalized_scope,
        run_id=str(manifest["orchestration_run_id"]),
        plan_execution_attempt_id=str(manifest["plan_execution_attempt_id"]),
        lineage=lineage,
    )
    if content != fresh:
        raise RunnerError("worker execution contract does not equal a fresh derivation")


def implementation_classification(values: dict[str, str | list[str]], key: str) -> str:
    """Read one optional scalar classification; only absence receives a default."""
    if key not in values:
        return "ordinary"
    raw = values[key]
    if not isinstance(raw, str):
        raise RunnerError(f"plan {key} must be one scalar classification")
    value = raw.strip().lower()
    if value not in IMPLEMENTATION_CLASSIFICATIONS:
        allowed = ", ".join(sorted(IMPLEMENTATION_CLASSIFICATIONS))
        raise RunnerError(f"plan {key} must be one of {allowed}; blank and unknown values are rejected")
    return value


def select_plan_writable_profile(values: dict[str, str | list[str]]) -> tuple[str, str]:
    """Select a writable model from separate risk and ambiguity declarations."""
    risk = implementation_classification(values, "implementation_risk")
    ambiguity = implementation_classification(values, "implementation_ambiguity")
    if "high" in {risk, ambiguity}:
        raise RunnerError(
            "writable sequential delegation is refused when implementation_risk or "
            "implementation_ambiguity is high"
        )
    if risk == ambiguity == "low":
        return DEFAULT_CODEX_MODEL, DEFAULT_CODEX_REASONING
    return TERRA_CODEX_MODEL, "medium"


def require_writable_model(model: str | None, label: str) -> str:
    if model is None or not model.strip():
        raise RunnerError(f"{label} Codex model must be non-empty")
    normalized = model.strip()
    if normalized.casefold() == WRITABLE_SOL_MODEL:
        raise RunnerError("gpt-5.6-sol is reserved for independent review and cannot be a writable worker")
    return normalized


def require_reasoning_effort(reasoning: str | None, label: str) -> str:
    if reasoning is None or not reasoning.strip():
        raise RunnerError(f"{label} Codex reasoning effort must be non-empty")
    return reasoning.strip()


def ensure_no_symlink_components(path: Path) -> None:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).absolute()
    current = Path(candidate.anchor or "/")
    for part in candidate.parts[1:]:
        current = current / part
        if current.exists() or current.is_symlink():
            if current.is_symlink():
                raise RunnerError(f"path resolves through a symlink and is rejected: {candidate}")


def path_is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve())
    except ValueError:
        return False
    return True


def validate_bounded_text(value: str | None, label: str, maximum_bytes: int) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise RunnerError(f"{label} must be a nonblank string")
    normalized = value.strip()
    if len(normalized.encode("utf-8")) > maximum_bytes:
        raise RunnerError(f"{label} exceeds the byte bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise RunnerError(f"{label} contains a control character")
    return normalized


def validate_model_name(model: str | None) -> str:
    return validate_bounded_text(model, "availability model", AVAILABILITY_STATE_MAX_MODEL_BYTES)


def target_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)


def read_bounded_fd(descriptor: int, maximum_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(4096, maximum_bytes + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum_bytes:
            raise RunnerError("availability state exceeds the byte bound")


def validate_availability_payload(payload: object, run_id: str) -> dict[str, str]:
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "orchestration_run_id",
        "unavailable_models",
    }:
        raise RunnerError("availability state has an invalid exact field shape")
    if payload["schema_version"] != AVAILABILITY_STATE_SCHEMA_VERSION:
        raise RunnerError("availability state has an unsupported schema version")
    stored_run_id = payload["orchestration_run_id"]
    if not isinstance(stored_run_id, str):
        raise RunnerError("availability state orchestration run identifier must be a string")
    stored_run_id = validate_bounded_text(
        stored_run_id, "availability state orchestration run identifier", ORCHESTRATION_RUN_ID_MAX_BYTES
    )
    if stored_run_id != run_id:
        raise RunnerError("availability state belongs to a different orchestration run identifier")
    entries = payload["unavailable_models"]
    if not isinstance(entries, list):
        raise RunnerError("availability state unavailable_models must be a list")
    if len(entries) > AVAILABILITY_STATE_MAX_ENTRIES:
        raise RunnerError("availability state exceeds the entry-count bound")
    allowed_reasons = {item[0] for item in CODEX_UNAVAILABLE_PATTERNS}
    unavailable: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"model", "reason"}:
            raise RunnerError("availability state entry has an invalid exact field shape")
        model = entry["model"]
        reason = entry["reason"]
        if not isinstance(model, str):
            raise RunnerError("availability state model must be a string")
        model = validate_model_name(model)
        if not isinstance(reason, str) or reason not in allowed_reasons:
            raise RunnerError("availability state reason must be one bounded availability code")
        if model in unavailable:
            raise RunnerError(f"availability state contains a duplicate model: {model}")
        unavailable[model] = reason
    return unavailable


def validate_lifecycle_payload(payload: object, run_id: str) -> dict[str, Any]:
    required = {
        "schema_version",
        "orchestration_run_id",
        "plan_execution_attempt_id",
        "current_manifest_digest",
        "current_patch_digest",
        "correction_round",
        "candidate_generations",
        "phase",
        "focused_required",
        "focused_validation_count",
        "authoritative_validation_count",
        "parent_review_rejections",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RunnerError("lifecycle state has an invalid exact field shape")
    if payload["schema_version"] != LIFECYCLE_STATE_SCHEMA_VERSION:
        raise RunnerError("lifecycle state has an unsupported schema version")
    if payload["orchestration_run_id"] != run_id:
        raise RunnerError("lifecycle state belongs to a different orchestration run identifier")
    require_receipt_code(
        payload["plan_execution_attempt_id"], label="lifecycle plan execution attempt identifier"
    )
    for key in ("current_manifest_digest", "current_patch_digest"):
        value = payload[key]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RunnerError(f"lifecycle state has an invalid digest: {key}")
    for key in (
        "correction_round",
        "candidate_generations",
        "focused_validation_count",
        "authoritative_validation_count",
        "parent_review_rejections",
    ):
        value = payload[key]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3:
            raise RunnerError(f"lifecycle state has an invalid bounded counter: {key}")
    if payload["candidate_generations"] != payload["correction_round"] + 1:
        raise RunnerError("lifecycle state generation count does not match correction lineage")
    if payload["parent_review_rejections"] != payload["correction_round"]:
        raise RunnerError("lifecycle state rejection count does not match correction lineage")
    if payload["correction_round"] > MAX_CORRECTION_ROUNDS:
        raise RunnerError("lifecycle state exceeds the correction budget")
    if payload["focused_validation_count"] > 1 or payload["authoritative_validation_count"] > 1:
        raise RunnerError("lifecycle state validation counters exceed exactly-once bounds")
    if not isinstance(payload["focused_required"], bool):
        raise RunnerError("lifecycle state focused_required must be boolean")
    if payload["phase"] not in {
        "admitted",
        "focused_passed",
        "focused_failed",
        "focused_running",
        "authoritative_passed",
        "authoritative_failed",
        "authoritative_running",
        "applying",
        "applied",
    }:
        raise RunnerError("lifecycle state has an invalid phase")
    phase = payload["phase"]
    focused_count = payload["focused_validation_count"]
    authoritative_count = payload["authoritative_validation_count"]
    if phase == "admitted" and (focused_count or authoritative_count):
        raise RunnerError("admitted lifecycle state cannot claim validation events")
    if phase.startswith("focused_") and (focused_count != 1 or authoritative_count != 0):
        raise RunnerError("focused lifecycle phase has inconsistent counters")
    if phase in {"authoritative_running", "authoritative_passed", "authoritative_failed", "applying", "applied"}:
        if authoritative_count != 1 or (payload["focused_required"] and focused_count != 1):
            raise RunnerError("authoritative lifecycle phase has inconsistent counters")
    return payload


def validate_manifest_telemetry(payload: object, correction_round: int) -> None:
    required = {
        "schema_version",
        "attempt_durations_seconds",
        "runner_duration_seconds",
        "model_starts",
        "availability_failures",
        "skipped_known_unavailable_starts",
        "candidate_generations",
        "full_validation_count",
        "authoritative_validation_count",
        "focused_validation_count",
        "parent_review_rejections",
        "correction_round",
        "implementation_risk",
        "implementation_ambiguity",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RunnerError("candidate telemetry has an invalid exact field shape")
    if payload["schema_version"] != TELEMETRY_SCHEMA_VERSION:
        raise RunnerError("candidate telemetry has an unsupported schema version")
    durations = payload["attempt_durations_seconds"]
    if not isinstance(durations, list) or len(durations) > 2:
        raise RunnerError("candidate telemetry attempt durations exceed the bound")
    for value in [*durations, payload["runner_duration_seconds"]]:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise RunnerError("candidate telemetry duration must be finite numeric data")
        if not 0 <= value <= TELEMETRY_MAX_DURATION_SECONDS:
            raise RunnerError("candidate telemetry duration is outside the bound")
    for key in (
        "model_starts",
        "availability_failures",
        "skipped_known_unavailable_starts",
        "candidate_generations",
        "full_validation_count",
        "authoritative_validation_count",
        "focused_validation_count",
        "parent_review_rejections",
        "correction_round",
    ):
        value = payload[key]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3:
            raise RunnerError(f"candidate telemetry counter is invalid: {key}")
    if payload["correction_round"] != correction_round:
        raise RunnerError("candidate telemetry correction round differs from lineage")
    if payload["candidate_generations"] != correction_round + 1:
        raise RunnerError("candidate telemetry generation count differs from lineage")
    if payload["parent_review_rejections"] != correction_round:
        raise RunnerError("candidate telemetry rejection count differs from lineage")
    if any(payload[key] != 0 for key in ("full_validation_count", "authoritative_validation_count", "focused_validation_count")):
        raise RunnerError("candidate manifest must not claim parent validation events")
    for key in ("implementation_risk", "implementation_ambiguity"):
        if payload[key] not in IMPLEMENTATION_CLASSIFICATIONS:
            raise RunnerError(f"candidate telemetry classification is invalid: {key}")


def open_lifecycle_state(repo_root: Path, raw_path: str, raw_run_id: str) -> LifecycleState:
    run_id = validate_bounded_text(
        raw_run_id, "orchestration run identifier", ORCHESTRATION_RUN_ID_MAX_BYTES
    )
    requested = Path(raw_path).expanduser()
    if not requested.is_absolute():
        requested = (Path.cwd() / requested).absolute()
    if requested.name in {"", ".", ".."}:
        raise RunnerError("lifecycle state path must name a file")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    lock_fd = -1
    try:
        for component in requested.parent.parts[1:]:
            next_descriptor = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        actual_parent = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        if path_is_within(repo_root, actual_parent / requested.name):
            raise RunnerError("lifecycle state path must be outside the source repository")
        lock_fd = os.open(
            f".{requested.name}.lock",
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
        if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
            raise RunnerError("lifecycle state lock must be a regular file")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        data: dict[str, Any] | None = None
        try:
            state_fd = os.open(
                requested.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=descriptor
            )
        except FileNotFoundError:
            state_fd = -1
        if state_fd >= 0:
            try:
                if not stat.S_ISREG(os.fstat(state_fd).st_mode):
                    raise RunnerError("lifecycle state target must be a regular file")
                raw = read_bounded_fd(state_fd, LIFECYCLE_STATE_MAX_BYTES)
            finally:
                os.close(state_fd)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RunnerError("lifecycle state is not valid UTF-8 JSON") from exc
            data = validate_lifecycle_payload(parsed, run_id)
        handle = LifecycleState(
            parent_fd=descriptor,
            target_name=requested.name,
            lock_fd=lock_fd,
            run_id=run_id,
            data=data,
        )
        descriptor = -1
        lock_fd = -1
        return handle
    except OSError as exc:
        raise RunnerError("lifecycle state path and lock must be nonsymlink files") from exc
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        if descriptor >= 0:
            os.close(descriptor)


def open_availability_state(repo_root: Path, raw_path: str, raw_run_id: str) -> AvailabilityState:
    run_id = validate_bounded_text(
        raw_run_id, "orchestration run identifier", ORCHESTRATION_RUN_ID_MAX_BYTES
    )
    requested = Path(raw_path).expanduser()
    if not requested.is_absolute():
        requested = (Path.cwd() / requested).absolute()
    if requested.name in {"", ".", ".."}:
        raise RunnerError("availability state path must name a file")
    parent_parts = requested.parent.parts
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    lock_fd = -1
    try:
        for component in parent_parts[1:]:
            try:
                next_descriptor = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except OSError as exc:
                raise RunnerError("availability state ancestor must exist and must not be a symlink") from exc
            os.close(descriptor)
            descriptor = next_descriptor
        try:
            actual_parent = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        except OSError as exc:
            raise RunnerError("could not verify availability state parent directory") from exc
        if path_is_within(repo_root, actual_parent / requested.name):
            raise RunnerError("availability state path must be outside the source repository")
        lock_fd = os.open(
            f".{requested.name}.lock",
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
        if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
            raise RunnerError("availability state lock must be a regular file")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        state_identity: tuple[int, int, int, int] | None = None
        unavailable: dict[str, str] = {}
        try:
            state_fd = os.open(
                requested.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
        except FileNotFoundError:
            state_fd = -1
        except OSError as exc:
            raise RunnerError("availability state target must not be a symlink") from exc
        if state_fd >= 0:
            try:
                metadata = os.fstat(state_fd)
                if not stat.S_ISREG(metadata.st_mode):
                    raise RunnerError("availability state target must be a regular file")
                state_identity = target_identity(metadata)
                raw = read_bounded_fd(state_fd, AVAILABILITY_STATE_MAX_BYTES)
            finally:
                os.close(state_fd)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RunnerError("availability state is not valid UTF-8 JSON") from exc
            unavailable = validate_availability_payload(payload, run_id)
        handle = AvailabilityState(
            parent_fd=descriptor,
            target_name=requested.name,
            run_id=run_id,
            unavailable=unavailable,
            target_identity=state_identity,
            lock_fd=lock_fd,
        )
        descriptor = -1
        lock_fd = -1
        return handle
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        if descriptor >= 0:
            os.close(descriptor)


def bounded_duration(started: float, finished: float) -> float:
    duration = finished - started
    if not math.isfinite(duration) or duration < 0 or duration > TELEMETRY_MAX_DURATION_SECONDS:
        raise RunnerError("telemetry duration is outside the finite nonnegative bound")
    return duration


def materialize_output_dir(repo_root: Path, requested: str | None) -> Path:
    if requested is None:
        output_dir = Path(tempfile.mkdtemp(prefix="sandboxed-plan-worker-output-")).resolve()
        if path_is_within(repo_root, output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
            raise RunnerError("default output directory resolved inside the source repository")
        return output_dir
    output_dir = Path(requested).expanduser()
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() / output_dir).absolute()
    ensure_no_symlink_components(output_dir)
    if path_is_within(repo_root, output_dir):
        raise RunnerError("output directory must be outside the source repository")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise RunnerError(f"output directory is not a directory: {output_dir}")
    else:
        output_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        output_dir.chmod(0o700)
    return output_dir


def reserve_output_artifacts(output_dir: Path) -> dict[str, Path]:
    reserved: dict[str, Path] = {}
    for name in ARTIFACT_NAMES:
        path = output_dir / name
        if path.exists() or path.is_symlink():
            raise RunnerError(f"output artifact path must not already exist: {path}")
        reserved[name] = path
    return reserved


def build_worker_prompt() -> str:
    return textwrap.dedent(
        """\
        Implement the assigned plan in this isolated clone.

        Constraints:
        - Read $SANDBOXED_PLAN_WORKER_CONTRACT first. Then read the exact active plan,
          AGENTS.md, context files, and required specifications named by that contract.
        - The active plan and directly read normative specifications are authoritative;
          the contract is a bounded read-only projection and cannot satisfy or amend them.
        - This clone is the only writable repository.
        - Do not spawn agents, commit, edit plan status, or touch paths outside the plan write_scope.
        - If an exact write_scope path is absent in the clone, create it under
          $SANDBOXED_PLAN_WORKER_NEW_FILE_ROOT using the same repository-relative path.
          Do not create a placeholder in the clone.
        - Read only implementation files needed for the assigned task after the required inputs.
        - Do not inspect logs or unrelated plans.
        - Do not run plan validation. The parent performs review and authorizes validation after admission.
        - Write transient diagnostics, tool caches, and temporary artifacts only under
          $SANDBOXED_PLAN_WORKER_SCRATCH_DIR.
        - Before exit, write one UTF-8 JSON object to
          $SANDBOXED_PLAN_WORKER_COMPLETION_CLAIMS with exactly these fields:
          attempt_result, acceptance_evidence, commands_attempted, blockers,
          residual_risks, and out_of_scope_change. Use only acceptance SHA-256 digests,
          positional command ids `worker-check-1` through `worker-check-64`, fixed policy
          blocker/risk codes, observed integer exit statuses, and booleans;
          worker blocker codes are command_failed, implementation_failed, incomplete_change,
          missing_input, or worker_failed; residual-risk codes are incomplete_change,
          known_limitation, parent_review_required, or validation_not_run.
          never include commands, output bodies, prompts, environment values, credentials,
          logs, patches, or absolute paths. The runner binds these advisory claims to Git,
          process, contract, and attempt facts in the final completion receipt.

        The parent will reject any changed path outside write_scope.
        Report changed paths, validation results, blockers, remaining risks, and confirm whether any out-of-scope path changed.
        """
    )


def build_correction_prompt() -> str:
    return textwrap.dedent(
        """\
        Correct the rejected candidate already applied in this fresh isolated clone.

        Constraints:
        - Read $SANDBOXED_PLAN_WORKER_CONTRACT first. Then read the exact active plan,
          AGENTS.md, context files, and required specifications named by that contract.
        - The active plan and directly read normative specifications are authoritative;
          the contract is a bounded read-only projection and cannot satisfy or amend them.
        - Read the parent-authored correction brief at $SANDBOXED_PLAN_WORKER_CORRECTION_BRIEF.
        - The brief is a read-only input. Do not search for or inspect any prior attempt artifact.
        - Preserve correct prior work and change only what the brief requires.
        - Do not spawn agents, commit, edit plan status, or touch paths outside write_scope.
        - If an exact write_scope path is absent in the clone, create it under
          $SANDBOXED_PLAN_WORKER_NEW_FILE_ROOT using the same repository-relative path.
          Do not create a placeholder in the clone.
        - Write transient diagnostics, caches, and temporary artifacts only under
          $SANDBOXED_PLAN_WORKER_SCRATCH_DIR.
        - Report changed paths and blockers. Do not run broad plan validation.
        - Before exit, write the same bounded advisory JSON claims object required by the
          initial prompt to $SANDBOXED_PLAN_WORKER_COMPLETION_CLAIMS.

        The parent will admit one aggregate patch against the original source HEAD.
        """
    )


def default_worker_command(
    *,
    codex_bin: str,
    clone_dir: Path,
    scratch_dir: Path,
    last_message_path: Path,
    model: str,
    reasoning: str,
) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--ignore-user-config",
        "--ephemeral",
        "--model",
        model,
        "--skip-git-repo-check",
        "--color",
        "never",
        "--cd",
        str(clone_dir),
        "--config",
        f'model_reasoning_effort="{reasoning}"',
        "--output-last-message",
        str(last_message_path),
        "-",
    ]


def classify_codex_unavailability(stdout: bytes, stderr: bytes) -> str | None:
    """Return a bounded reason only for a Codex CLI availability error line."""
    del stdout
    error_lines: list[str] = []
    text = stderr.decode("utf-8", errors="replace")
    for line in text.splitlines():
        candidate = line.strip()
        if CODEX_ERROR_LINE.match(candidate):
            error_lines.append(candidate)
    if not error_lines:
        return None
    reasons: set[str] = set()
    for candidate in error_lines:
        matched_reason: str | None = None
        for reason, pattern in CODEX_UNAVAILABLE_PATTERNS:
            if pattern.fullmatch(candidate):
                matched_reason = reason
                break
        if matched_reason is None:
            return None
        reasons.add(matched_reason)
    return reasons.pop() if len(reasons) == 1 else None


def build_bwrap_command(
    *,
    bwrap_bin: str,
    clone_dir: Path,
    scratch_dir: Path,
    command: Sequence[str],
    env_vars: dict[str, str],
    writable_shadows: Sequence[tuple[Path, Path]] = (),
    writable_clone: bool = False,
    hidden_directories: Sequence[Path] = (),
    read_only_inputs: Sequence[Path] = (),
    read_only_shadows: Sequence[tuple[Path, Path]] = (),
    network_enabled: bool = True,
) -> list[str]:
    argv = [
        bwrap_bin,
        "--unshare-all",
        "--unshare-user",
        "--new-session",
        "--disable-userns",
        "--cap-drop",
        "ALL",
        "--die-with-parent",
        "--clearenv",
        "--tmpfs",
        "/",
        "--dir",
        "/tmp",
        "--dir",
        "/run",
        "--dir",
        "/var",
        "--dir",
        "/etc",
        "--dir",
        "/home",
    ]
    if network_enabled:
        argv.insert(2, "--share-net")
    for raw in (*SANDBOX_SYSTEM_DIRECTORIES, *SANDBOX_SYSTEM_OPTIONAL_DIRECTORIES):
        path = Path(raw)
        if path.exists():
            argv.extend(("--ro-bind", raw, raw))
    for raw in SANDBOX_SYSTEM_FILES:
        path = Path(raw)
        if path.is_file():
            argv.extend(("--ro-bind", raw, raw))
    required_paths = [clone_dir, scratch_dir, *read_only_inputs, *(source for source, _ in read_only_shadows)]
    executable = Path(command[0]) if command else Path()
    runtime_root: Path | None = None
    if executable.is_absolute() and not any(path_is_within(Path(root), executable) for root in SANDBOX_SYSTEM_DIRECTORIES) and not any(
        path_is_within(visible, executable) for visible in (clone_dir, scratch_dir)
    ):
        runtime_root = next(
            (
                parent
                for parent in executable.parents
                if parent != Path("/") and (parent / "bin").is_dir() and (parent / "lib").is_dir()
            ),
            None,
        )
        executable_input = runtime_root or executable
        for parent in reversed(executable_input.parents):
            if parent != Path("/"):
                argv.extend(("--dir", str(parent)))
        argv.extend(("--ro-bind", str(executable_input), str(executable_input)))
    for required in required_paths:
        for parent in reversed(required.parents):
            if parent != Path("/"):
                argv.extend(("--dir", str(parent)))
    external_files = [
        path
        for path in read_only_inputs
        if not any(path_is_within(visible, path) for visible in (clone_dir, scratch_dir))
    ]
    if executable.is_absolute() and runtime_root is None and not any(
        path_is_within(visible, executable) for visible in (clone_dir, scratch_dir)
    ) and not any(path_is_within(Path(root), executable) for root in SANDBOX_SYSTEM_DIRECTORIES):
        external_files.append(executable)
    for index, parent in enumerate(sorted({path.parent for path in external_files}, key=str)):
        empty_parent = scratch_dir / "empty-host-parents" / str(index)
        empty_parent.mkdir(parents=True, exist_ok=True)
        for explicit_file in (path for path in external_files if path.parent == parent):
            shutil.copy2(explicit_file, empty_parent / explicit_file.name, follow_symlinks=True)
        empty_parent.chmod(0o555)
        argv.extend(("--ro-bind", str(empty_parent), str(parent)))
    argv.extend(
        [
        "--ro-bind" if not writable_clone else "--bind",
        str(clone_dir),
        str(clone_dir),
        "--bind",
        str(scratch_dir),
        str(scratch_dir),
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--chdir",
        str(clone_dir),
        ]
    )
    for shadow_path, clone_target in read_only_shadows:
        argv.extend(("--ro-bind", str(shadow_path), str(clone_target)))
    for shadow_path, clone_target in writable_shadows:
        argv.extend(("--bind", str(shadow_path), str(clone_target)))
    for read_only_input in read_only_inputs:
        if read_only_input not in external_files:
            argv.extend(("--ro-bind", str(read_only_input), str(read_only_input)))
    for key, value in env_vars.items():
        argv.extend(["--setenv", key, value])
    argv.append("--")
    argv.extend(command)
    return argv


def normalize_hidden_directories(
    candidates: Sequence[Path], *, visible_paths: Sequence[Path]
) -> list[Path]:
    hidden: list[Path] = []
    visible = [path.resolve() for path in visible_paths]
    for candidate in sorted({path.resolve() for path in candidates}, key=lambda path: len(path.parts)):
        if not candidate.is_dir() or candidate.is_symlink():
            raise RunnerError(f"hidden sandbox path must be an existing regular directory: {candidate}")
        if any(path_is_within(candidate, path) or path_is_within(path, candidate) for path in visible):
            raise RunnerError(f"hidden sandbox path overlaps required attempt state: {candidate}")
        if any(path_is_within(parent, candidate) for parent in hidden):
            continue
        hidden.append(candidate)
    return hidden


def prepare_writable_shadows(
    *, clone_dir: Path, scratch_dir: Path, scope_entries: Sequence[str]
) -> list[tuple[Path, Path, bool]]:
    """Create writable files for exact paths without granting a parent directory."""
    shadows_root = scratch_dir / "writable-shadows"
    shadows_root.mkdir(exist_ok=False)
    prepared: list[tuple[Path, Path, bool]] = []
    for entry in scope_entries:
        relative, is_prefix = normalize_repo_relpath(entry, allow_prefix=True, label="write_scope entry")
        if is_prefix:
            raise RunnerError(f"writable delegation does not allow a directory prefix: {relative}")
        body = relative
        ensure_no_symlink_path_trick(clone_dir, body)
        target = clone_dir / body
        shadow = shadows_root / body
        target_existed = target.exists() or target.is_symlink()
        if target_existed:
            shadow.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.is_symlink():
                raise RunnerError(f"exact write_scope target must be a regular file: {relative}")
            shutil.copy2(target, shadow, follow_symlinks=False)
        else:
            if not target.parent.is_dir() or target.parent.is_symlink():
                raise RunnerError(f"new exact write_scope target requires an existing parent: {relative}")
            shadow.parent.mkdir(parents=True, exist_ok=True)
        prepared.append((shadow, target, target_existed))
    return prepared


def materialize_writable_shadows(
    shadows: Sequence[tuple[Path, Path, bool]], shadows_root: Path
) -> None:
    """Copy only scope-shadow results back into the disposable candidate clone."""
    if not shadows_root.is_dir() or shadows_root.is_symlink():
        raise RunnerError("writable shadow root changed shape")
    for shadow, target, target_existed in shadows:
        if not target_existed and not shadow.exists() and not shadow.is_symlink():
            continue
        try:
            shadow_rel = shadow.relative_to(shadows_root).as_posix()
        except ValueError as exc:
            raise RunnerError("writable shadow escaped its staging root") from exc
        ensure_no_symlink_path_trick(shadows_root, shadow_rel)
        if target_existed and (not target.is_file() or target.is_symlink()):
            raise RunnerError(f"exact write_scope target changed shape: {target}")
        if not target_existed and (target.exists() or target.is_symlink()):
            raise RunnerError(f"new exact write_scope target unexpectedly exists: {target}")
        if not shadow.is_file() or shadow.is_symlink():
            raise RunnerError(f"writable shadow changed shape: {shadow}")
        shutil.copy2(shadow, target, follow_symlinks=False)

def git_c_quote_path(path: Path) -> str:
    """Quote one object path for Git's colon-separated alternate list."""
    quoted = ['"']
    for char in os.fsdecode(os.fsencode(str(path))):
        if char == '"':
            quoted.append('\\"')
        elif char == "\\":
            quoted.append('\\\\')
        elif char == "\n":
            quoted.append('\\n')
        elif char == "\r":
            quoted.append('\\r')
        elif char == "\t":
            quoted.append('\\t')
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            quoted.append(f"\\{ord(char):03o}")
        else:
            quoted.append(char)
    quoted.append('"')
    return "".join(quoted)


def resolve_source_object_directory(repo_root: Path, git_bin: str) -> Path:
    """Resolve the repository's primary object directory without ambient GIT_* state."""
    env = sanitize_process_env()
    output = run_subprocess(
        (git_bin, "rev-parse", "--path-format=absolute", "--git-path", "objects"),
        cwd=repo_root,
        env=env,
    ).stdout.decode("utf-8").strip()
    if not output:
        raise RunnerError("Git returned an empty source object directory")
    object_dir = Path(output)
    if not object_dir.is_absolute():
        git_dir = run_subprocess(
            (git_bin, "rev-parse", "--path-format=absolute", "--git-dir"),
            cwd=repo_root,
            env=env,
        ).stdout.decode("utf-8").strip()
        object_dir = Path(git_dir) / object_dir
    object_dir = object_dir.resolve()
    if not object_dir.is_dir():
        raise RunnerError(f"source object directory is not a directory: {object_dir}")
    return object_dir


def derive_changed_paths_from_patch(
    repo_root: Path, git_bin: str, patch_bytes: bytes, base_rev: str
) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="sandboxed-plan-worker-apply-index-") as tmp:
        index_path = Path(tmp) / "index"
        object_dir = Path(tmp) / "objects"
        object_dir.mkdir()
        source_object_dir = resolve_source_object_directory(repo_root, git_bin)
        env = sanitize_process_env()
        env["GIT_INDEX_FILE"] = str(index_path)
        env["GIT_OBJECT_DIRECTORY"] = str(object_dir)
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = git_c_quote_path(source_object_dir)
        run_subprocess((git_bin, "read-tree", base_rev), cwd=repo_root, env=env)
        run_subprocess(
            (git_bin, "apply", "--cached", "--check", "--binary", "-"),
            cwd=repo_root,
            env=env,
            stdin=patch_bytes,
        )
        run_subprocess(
            (git_bin, "apply", "--cached", "--binary", "-"),
            cwd=repo_root,
            env=env,
            stdin=patch_bytes,
        )
        output = run_subprocess(
            (git_bin, "diff-index", "--cached", "--name-only", "-z", base_rev, "--"),
            cwd=repo_root,
            env=env,
        ).stdout
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def collect_worktree_patch(repo_root: Path, git_bin: str, base_rev: str) -> bytes:
    """Render the current source worktree against base without writing its index or objects."""
    with tempfile.TemporaryDirectory(prefix="sandboxed-plan-worker-reconcile-index-") as tmp:
        index_path = Path(tmp) / "index"
        object_dir = Path(tmp) / "objects"
        object_dir.mkdir()
        env = sanitize_process_env()
        env["GIT_INDEX_FILE"] = str(index_path)
        env["GIT_OBJECT_DIRECTORY"] = str(object_dir)
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = git_c_quote_path(
            resolve_source_object_directory(repo_root, git_bin)
        )
        run_subprocess((git_bin, "read-tree", base_rev), cwd=repo_root, env=env)
        run_subprocess((git_bin, "add", "--all", "--"), cwd=repo_root, env=env)
        return run_subprocess(
            (git_bin, "diff", "--cached", "--binary", "--full-index", base_rev, "--"),
            cwd=repo_root,
            env=env,
        ).stdout


def normalize_changed_paths(
    paths: Sequence[str], repo_root: Path, *, include_symlink_targets: bool = True
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        match = STATUS_PATTERN.fullmatch(raw)
        candidate = match.group(1) if match else raw
        value, _ = normalize_repo_relpath(candidate, label="changed path")
        ensure_no_symlink_path_trick(
            repo_root, value, include_target=include_symlink_targets
        )
        if value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def clone_at_head(repo_root: Path, git_bin: str, head: str, destination: Path) -> None:
    env = sanitize_process_env()
    run_subprocess(
        (git_bin, "clone", "--quiet", "--no-hardlinks", str(repo_root), str(destination)),
        env=env,
    )
    run_subprocess((git_bin, "-C", str(destination), "checkout", "--quiet", head), env=env)


def stage_codex_home(scratch_dir: Path) -> Path:
    host_codex_home = host_codex_home_path()
    host_auth = host_codex_home / "auth.json"
    if not host_auth.is_file():
        raise RunnerError(f"default Codex worker requires an auth file: {host_auth}")
    scratch_codex_home = scratch_dir / "codex-home"
    scratch_codex_home.mkdir(mode=0o700)
    scratch_codex_home.chmod(0o700)
    scratch_auth = scratch_codex_home / "auth.json"
    shutil.copyfile(host_auth, scratch_auth)
    scratch_auth.chmod(0o600)
    return scratch_codex_home


def host_codex_home_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()


def prepare_worker_environment(
    *,
    source_repo: Path,
    clone_dir: Path,
    scratch_dir: Path,
    plan_rel: str,
    extra_env: Sequence[str],
    include_codex_home: bool,
) -> dict[str, str]:
    scratch_home = scratch_dir / "home"
    scratch_tmp = scratch_dir / "tmp"
    scratch_pycache = scratch_dir / "python-pycache"
    scratch_pip_cache = scratch_dir / "pip-cache"
    scratch_uv_cache = scratch_dir / "uv-cache"
    scratch_uv_environment = scratch_dir / "uv-project-environment"
    scratch_home.mkdir(parents=True, exist_ok=True)
    scratch_tmp.mkdir(parents=True, exist_ok=True)
    for directory in (scratch_pycache, scratch_pip_cache, scratch_uv_cache, scratch_uv_environment):
        directory.mkdir(parents=True, exist_ok=True)
    locale = os.environ.get("LC_ALL") or os.environ.get("LANG") or "C.UTF-8"
    env_vars = {
        "PATH": os.environ.get("PATH", DEFAULT_PATH),
        "LANG": locale,
        "LC_ALL": locale,
        "HOME": str(scratch_home),
        "TMPDIR": str(scratch_tmp),
        "TMP": str(scratch_tmp),
        "TEMP": str(scratch_tmp),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(scratch_pycache),
        "PIP_CACHE_DIR": str(scratch_pip_cache),
        "UV_CACHE_DIR": str(scratch_uv_cache),
        "UV_PROJECT_ENVIRONMENT": str(scratch_uv_environment),
        f"{ENV_PREFIX}SOURCE_REPO": str(source_repo),
        f"{ENV_PREFIX}WORKER_REPO": str(clone_dir),
        f"{ENV_PREFIX}SCRATCH_DIR": str(scratch_dir),
        f"{ENV_PREFIX}PLAN_PATH": plan_rel,
    }
    if include_codex_home:
        env_vars["CODEX_HOME"] = str(stage_codex_home(scratch_dir))
    for item in extra_env:
        if "=" not in item:
            raise RunnerError(f"--worker-env must use KEY=VALUE syntax: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise RunnerError(f"--worker-env key must not be empty: {item}")
        if key in RESERVED_WORKER_ENV:
            raise RunnerError(f"--worker-env must not override reserved environment variable: {key}")
        env_vars[key] = value
    return env_vars


def sanitize_process_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def collect_candidate_patch_in_sandbox(
    *,
    bwrap_bin: str,
    git_bin: str,
    clone_dir: Path,
    scratch_dir: Path,
    env_vars: dict[str, str],
) -> tuple[bytes, str, bytes]:
    index_path = scratch_dir / "collection-index"
    patch_path = scratch_dir / "candidate.patch"
    head_path = scratch_dir / "candidate-head.txt"
    refs_path = scratch_dir / "candidate-refs.txt"
    helper = textwrap.dedent(
        """\
        from __future__ import annotations

        import os
        import subprocess
        import sys
        from pathlib import Path


        def run_git(git_bin: str, clone_dir: str, env: dict[str, str], *args: str) -> bytes:
            result = subprocess.run(
                [git_bin, *args],
                cwd=clone_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0:
                sys.stderr.buffer.write(result.stderr or result.stdout)
                raise SystemExit(result.returncode)
            return result.stdout


        git_bin, clone_dir, index_path, patch_path, head_path, refs_path = sys.argv[1:]
        managed_env = dict(os.environ)
        managed_env["GIT_INDEX_FILE"] = index_path
        Path(index_path).unlink(missing_ok=True)
        run_git(git_bin, clone_dir, managed_env, "read-tree", "HEAD")
        run_git(git_bin, clone_dir, managed_env, "add", "--all", "--", ".")
        patch = run_git(git_bin, clone_dir, managed_env, "diff", "--cached", "--binary", "--full-index", "HEAD", "--")
        Path(patch_path).write_bytes(patch)
        head = run_git(git_bin, clone_dir, managed_env, "rev-parse", "HEAD")
        Path(head_path).write_text(head.decode("utf-8"), encoding="utf-8")
        refs = run_git(git_bin, clone_dir, managed_env, "show-ref", "--head", "--dereference")
        Path(refs_path).write_bytes(refs)
        """
    )
    command = [
        sys.executable,
        "-c",
        helper,
        git_bin,
        str(clone_dir),
        str(index_path),
        str(patch_path),
        str(head_path),
        str(refs_path),
    ]
    result = run_subprocess(
        build_bwrap_command(
            bwrap_bin=bwrap_bin,
            clone_dir=clone_dir,
            scratch_dir=scratch_dir,
            command=command,
            env_vars=env_vars,
            writable_clone=True,
        ),
        cwd=clone_dir,
        env=sanitize_process_env(),
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or result.stdout.decode(
            "utf-8", errors="replace"
        ).strip()
        raise RunnerError(f"candidate patch collection failed inside Bubblewrap: {detail or f'exit {result.returncode}'}")
    return patch_path.read_bytes(), head_path.read_text(encoding="utf-8").strip(), refs_path.read_bytes()


def execute_isolated_attempt(
    *,
    workspace: Path,
    label: str,
    repo_root: Path,
    head: str,
    plan_rel: str,
    plan_digest: str,
    values: dict[str, str | list[str]],
    run_id: str,
    plan_execution_attempt_id: str,
    attempt_lineage: dict[str, object],
    normalized_scope: Sequence[str],
    bwrap_bin: str,
    git_bin: str,
    reserved_artifacts: dict[str, Path],
    extra_env: Sequence[str],
    hidden_directories: Sequence[Path],
    codex_bin: str | None = None,
    model: str | None = None,
    reasoning: str | None = None,
    custom_command: Sequence[str] | None = None,
    prior_patch: bytes | None = None,
    correction_brief: bytes | None = None,
) -> dict[str, Any]:
    validated_attempt_lineage = validate_contract_lineage(attempt_lineage)
    attempt_id = (
        f"{validated_attempt_lineage['attempt_kind']}-"
        f"{validated_attempt_lineage['correction_round']}-{label}-{secrets.token_hex(16)}"
    )
    attempt_root = workspace / label
    clone_dir = attempt_root / "clone"
    scratch_dir = attempt_root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=False)
    clone_at_head(repo_root, git_bin, head, clone_dir)
    contract_bytes = derive_worker_contract(
        repo_root=repo_root,
        git_bin=git_bin,
        head=head,
        plan_path=repo_root / plan_rel,
        plan_rel=plan_rel,
        plan_digest=plan_digest,
        values=values,
        normalized_scope=normalized_scope,
        run_id=run_id,
        plan_execution_attempt_id=plan_execution_attempt_id,
        lineage=validated_attempt_lineage,
    )
    contract_path = scratch_dir / "worker-contract.json"
    contract_path.write_bytes(contract_bytes)
    contract_path.chmod(0o400)
    initial_refs = git(clone_dir, git_bin, "show-ref", "--head", "--dereference").stdout
    if prior_patch is not None:
        run_subprocess(
            (git_bin, "apply", "--check", "--binary", "-"), cwd=clone_dir, stdin=prior_patch
        )
        run_subprocess((git_bin, "apply", "--binary", "-"), cwd=clone_dir, stdin=prior_patch)
    shadows = prepare_writable_shadows(
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        scope_entries=normalized_scope,
    )

    include_codex_home = custom_command is None
    stdin: bytes | None = None
    last_message_path = scratch_dir / "worker-last-message.txt"
    read_only_inputs: list[Path] = [contract_path]
    correction_brief_path: Path | None = None
    if correction_brief is not None:
        correction_brief_path = scratch_dir / "correction-brief.txt"
        correction_brief_path.write_bytes(correction_brief)
        correction_brief_path.chmod(0o400)
        read_only_inputs.append(correction_brief_path)
    if custom_command is None:
        if codex_bin is None or model is None or reasoning is None:
            raise RunnerError("Codex attempt requires an executable, model, and reasoning effort")
        codex_path = Path(codex_bin)
        has_runtime_root = any(
            parent != Path("/") and (parent / "bin").is_dir() and (parent / "lib").is_dir()
            for parent in codex_path.parents
        )
        if codex_path.is_absolute() and not any(
            path_is_within(Path(root), codex_path) for root in SANDBOX_SYSTEM_DIRECTORIES
        ) and not has_runtime_root:
            copied_codex = scratch_dir / "codex-cli"
            shutil.copy2(codex_path, copied_codex, follow_symlinks=True)
            copied_codex.chmod(0o500)
            codex_bin = str(copied_codex)
        command = default_worker_command(
            codex_bin=codex_bin,
            clone_dir=clone_dir,
            scratch_dir=scratch_dir,
            last_message_path=last_message_path,
            model=model,
            reasoning=reasoning,
        )
        stdin = (
            build_correction_prompt()
            if correction_brief is not None
            else build_worker_prompt()
        ).encode("utf-8")
    else:
        command = [custom_command[0]]
        explicit_root = scratch_dir / "explicit-inputs"
        for index, item in enumerate(custom_command[1:]):
            item_path = Path(item)
            if item_path.is_absolute() and item_path.is_file():
                explicit_root.mkdir(exist_ok=True)
                copied_input = explicit_root / f"{index}-{item_path.name}"
                shutil.copy2(item_path, copied_input, follow_symlinks=True)
                command.append(str(copied_input))
            else:
                command.append(item)

    env_vars = prepare_worker_environment(
        source_repo=repo_root,
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        plan_rel=plan_rel,
        extra_env=extra_env,
        include_codex_home=include_codex_home,
    )
    env_vars[f"{ENV_PREFIX}WORKER_CONTRACT"] = str(contract_path)
    completion_claims_path = scratch_dir / "worker-completion-claims.json"
    env_vars[f"{ENV_PREFIX}COMPLETION_CLAIMS"] = str(completion_claims_path)
    env_vars[f"{ENV_PREFIX}NEW_FILE_ROOT"] = str(scratch_dir / "writable-shadows")
    if correction_brief_path is not None:
        env_vars[f"{ENV_PREFIX}CORRECTION_BRIEF"] = str(correction_brief_path)
    fresh_contract = derive_worker_contract(
        repo_root=repo_root,
        git_bin=git_bin,
        head=head,
        plan_path=repo_root / plan_rel,
        plan_rel=plan_rel,
        plan_digest=plan_digest,
        values=values,
        normalized_scope=normalized_scope,
        run_id=run_id,
        plan_execution_attempt_id=plan_execution_attempt_id,
        lineage=validated_attempt_lineage,
    )
    if fresh_contract != contract_bytes or contract_path.read_bytes() != contract_bytes:
        raise RunnerError("worker execution contract does not equal a fresh derivation")
    attempt_started = time.monotonic()
    result = run_subprocess(
        build_bwrap_command(
            bwrap_bin=bwrap_bin,
            clone_dir=clone_dir,
            scratch_dir=scratch_dir,
            command=command,
            env_vars=env_vars,
            writable_shadows=[
                (shadow, target) for shadow, target, target_existed in shadows if target_existed
            ],
            hidden_directories=normalize_hidden_directories(
                hidden_directories,
                visible_paths=(clone_dir, scratch_dir),
            ),
            read_only_inputs=read_only_inputs,
        ),
        cwd=repo_root,
        env=sanitize_process_env(),
        stdin=stdin,
        check=False,
    )
    attempt_duration = bounded_duration(attempt_started, time.monotonic())

    artifact_prefix = "worker" if label == "custom" else f"worker-{label}"
    stdout_path = reserved_artifacts[f"{artifact_prefix}.stdout"]
    stderr_path = reserved_artifacts[f"{artifact_prefix}.stderr"]
    stdout_digest = write_bytes(stdout_path, result.stdout)
    stderr_digest = write_bytes(stderr_path, result.stderr)
    record: dict[str, Any] = {
        "attempt_id": attempt_id,
        "label": label,
        "model": model,
        "reasoning_effort": reasoning,
        "returncode": result.returncode,
        "duration_seconds": attempt_duration,
        "stdout_path": str(stdout_path),
        "stdout_digest": stdout_digest,
        "stderr_path": str(stderr_path),
        "stderr_digest": stderr_digest,
        "selected": False,
    }
    process_result_path, process_result_digest, process_result = write_attempt_process_result(
        label=label,
        attempt_id=attempt_id,
        result=result,
        stdout_digest=stdout_digest,
        stderr_digest=stderr_digest,
        reserved_artifacts=reserved_artifacts,
    )
    record["process_result_path"] = str(process_result_path)
    record["process_result_digest"] = process_result_digest
    attempt_last_message: Path | None = None
    if result.returncode == 0 and last_message_path.is_file():
        attempt_last_message = reserved_artifacts[f"{artifact_prefix}-last-message.txt"]
        attempt_last_message.write_bytes(last_message_path.read_bytes())
        record["last_message_path"] = str(attempt_last_message)
        record["last_message_digest"] = hash_file(attempt_last_message)
    completion_claims, completion_claims_error = load_attempt_completion_claims(
        completion_claims_path
    )
    attempt = {
        "clone_dir": clone_dir,
        "attempt_root": attempt_root,
        "scratch_dir": scratch_dir,
        "initial_refs": initial_refs,
        "shadows": shadows,
        "env_vars": env_vars,
        "command": command,
        "result": result,
        "record": record,
        "last_message_path": attempt_last_message,
        "contract_bytes": contract_bytes,
        "attempt_id": attempt_id,
        "process_result": process_result,
        "process_result_path": process_result_path,
        "process_result_digest": process_result_digest,
        "completion_claims": completion_claims,
        "completion_claims_error": completion_claims_error,
    }
    write_attempt_completion_receipt(
        attempt,
        reserved_artifacts=reserved_artifacts,
        candidate=None,
        final=result.returncode != 0,
    )
    return attempt


def select_attempt_artifacts(
    attempt: dict[str, Any], reserved_artifacts: dict[str, Path]
) -> dict[str, Any]:
    result: subprocess.CompletedProcess[bytes] = attempt["result"]
    stdout_path = reserved_artifacts["worker.stdout"]
    stderr_path = reserved_artifacts["worker.stderr"]
    worker_result: dict[str, Any] = {
        "command": attempt["command"],
        "returncode": result.returncode,
        "stdout_path": str(stdout_path),
        "stdout_digest": write_bytes(stdout_path, result.stdout),
        "stderr_path": str(stderr_path),
        "stderr_digest": write_bytes(stderr_path, result.stderr),
    }
    attempt["record"]["selected"] = True
    last_message_path = attempt["last_message_path"]
    if last_message_path is not None:
        copied_last_message = reserved_artifacts["worker-last-message.txt"]
        copied_last_message.write_bytes(last_message_path.read_bytes())
        worker_result["last_message_path"] = str(copied_last_message)
        worker_result["last_message_digest"] = hash_file(copied_last_message)
    return worker_result


def enforce_parallel_group_gate(
    plan: str,
    operation: str,
    *,
    group_permit: str | None = None,
    group_state: str | None = None,
) -> None:
    """Admit an enrolled group member only through verified group authority.

    An ungrouped plan is unaffected. An enrolled member reaches this worker
    only with the grouped execution adapter installed and its exact current
    member permit bound to the live group execution record. The permit never
    grants source-write authority: the worker still produces one isolated
    candidate inside its disposable clone.
    """

    authority = Path(__file__).with_name("parallel-plan-state.py")
    if not authority.is_file():
        raise RunnerError("parallel plan group authority is unavailable")
    spec = importlib.util.spec_from_file_location(
        "sandboxed_worker_parallel_group", authority
    )
    if spec is None or spec.loader is None:
        raise RunnerError("could not load the parallel plan group authority")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.require_group_permit(
            module.repository_root(),
            plan,
            operation,
            permit=group_permit,
            state=group_state,
        )
    except module.GroupError as exc:
        raise RunnerError(str(exc)) from exc


def enforce_plan_execution_gate(
    args: argparse.Namespace,
    *,
    plan: str | None = None,
    open_attempt_id: str | None = None,
) -> None:
    state = args.plan_execution_state
    checker = Path(__file__).with_name("plan-execution-state.py")
    if not checker.is_file():
        raise RunnerError("plan execution state checker is unavailable")
    command = [
        sys.executable,
        str(checker),
        "check",
        state,
        "--run-id",
        args.orchestration_run_id,
        "--lifecycle-state",
        args.lifecycle_state,
    ]
    if plan is not None:
        command.extend(("--plan", plan))
    if open_attempt_id is not None:
        command.extend(("--open-attempt-id", open_attempt_id))
    completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise RunnerError(detail or "plan execution state gate rejected the operation")


def begin_plan_execution_attempt(
    args: argparse.Namespace,
    *,
    attempt_kind: str,
    prior_candidate_digest: str | None = None,
) -> None:
    checker = Path(__file__).with_name("plan-execution-state.py")
    if not checker.is_file():
        raise RunnerError("plan execution state checker is unavailable")
    attempt_id = f"attempt-{secrets.token_hex(16)}"
    command = [
        sys.executable,
        str(checker),
        "start",
        args.plan_execution_state,
        "--run-id",
        args.orchestration_run_id,
        "--plan",
        args.plan,
        "--attempt-id",
        attempt_id,
        "--attempt-kind",
        attempt_kind,
        "--lifecycle-state",
        args.lifecycle_state,
    ]
    predecessor_state = getattr(args, "predecessor_plan_execution_state", None)
    predecessor_checkpoint = getattr(args, "predecessor_session_checkpoint", None)
    root_session_manifest = getattr(args, "root_session_manifest", None)
    reviewer_registry = getattr(args, "reviewer_registry", None)
    if (
        predecessor_checkpoint
        or root_session_manifest
        or reviewer_registry
    ) and not predecessor_state:
        raise RunnerError(
            "session checkpoint controls require --predecessor-plan-execution-state"
        )
    if predecessor_state:
        command.extend(("--predecessor-state", predecessor_state))
        if len([
            item for item in (
                predecessor_checkpoint,
                root_session_manifest,
                reviewer_registry,
            )
            if item
        ]) not in {0, 3}:
            raise RunnerError(
                "predecessor session checkpoint, root session manifest, and reviewer "
                "registry must be supplied together"
            )
        if predecessor_checkpoint:
            command.extend((
                "--predecessor-checkpoint",
                predecessor_checkpoint,
                "--root-session-manifest",
                root_session_manifest,
                "--reviewer-registry",
                reviewer_registry,
            ))
    if prior_candidate_digest is not None:
        command.extend(("--prior-candidate-digest", prior_candidate_digest))
    completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise RunnerError(detail or "plan execution state rejected the writable attempt start")
    args.execution_attempt_id = attempt_id


def plan_execution_lease(args: argparse.Namespace):
    state = getattr(args, "plan_execution_state", None)
    if not state:
        return nullcontext()
    lock_path = Path(state).with_name(Path(state).name + ".lock")
    try:
        descriptor = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise RunnerError(f"could not open plan execution lease: {exc}") from exc
    handle = os.fdopen(descriptor, "rb")
    fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
    return handle


def run_worker(args: argparse.Namespace) -> int:
    runner_started = time.monotonic()
    git_bin = require_executable("git", args.git_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    plan_path, plan_rel, values, normalized_scope = load_plan(planlib, repo_root, args.plan)
    require_plan_worktree(repo_root, plan_rel, "running a sandboxed plan worker")
    implementation_risk = implementation_classification(values, "implementation_risk")
    implementation_ambiguity = implementation_classification(values, "implementation_ambiguity")
    selected_plan_model, selected_plan_reasoning = select_plan_writable_profile(values)
    with open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    ) as lifecycle_state:
        if lifecycle_state.data is not None:
            raise RunnerError("lifecycle state is already initialized for this orchestration run")
    begin_plan_execution_attempt(args, attempt_kind="initial")
    head = git_text(repo_root, git_bin, "rev-parse", "HEAD")
    plan_digest = hash_file(plan_path)
    output_dir = materialize_output_dir(repo_root, args.output_dir)
    reserved_artifacts = reserve_output_artifacts(output_dir)
    state_path = args.availability_state
    run_id = args.orchestration_run_id
    if state_path is not None and run_id is None:
        raise RunnerError("availability state requires an orchestration run identifier")
    state_context = (
        open_availability_state(repo_root, state_path, run_id)
        if state_path is not None and run_id is not None
        else nullcontext(None)
    )
    lifecycle_context = open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    )

    with plan_execution_lease(args), lifecycle_context as lifecycle_state, state_context as availability_state, tempfile.TemporaryDirectory(
        prefix="sandboxed-plan-worker-workspace-"
    ) as workspace_tmp:
        enforce_plan_execution_gate(
            args, plan=plan_rel, open_attempt_id=args.execution_attempt_id
        )
        bwrap_bin = require_executable("bwrap", args.bwrap_bin)
        ensure_bwrap_usable(bwrap_bin)
        if lifecycle_state.data is not None:
            raise RunnerError("lifecycle state is already initialized for this orchestration run")
        workspace = Path(workspace_tmp)
        attempts: list[dict[str, Any]] = []
        fallback_reason: str | None = None
        availability_failures = 0
        skipped_known_unavailable_starts = 0
        if args.worker_binary is None:
            codex_bin = require_executable("codex", args.codex_bin)
            primary_model = require_writable_model(
                args.codex_model if args.codex_model is not None else selected_plan_model,
                "preferred",
            )
            primary_reasoning = require_reasoning_effort(
                args.codex_reasoning_effort
                if args.codex_reasoning_effort is not None
                else selected_plan_reasoning,
                "preferred",
            )
            fallback_model = require_writable_model(args.fallback_codex_model, "fallback")
            fallback_reasoning_effort = require_reasoning_effort(
                args.fallback_codex_reasoning_effort, "fallback"
            )
            worker_kind = "codex"
            primary: dict[str, Any] | None = None
            known_primary_reason = (
                availability_state.reason_for(primary_model)
                if availability_state is not None
                else None
            )
            if known_primary_reason is not None:
                skipped_known_unavailable_starts += 1
                fallback_reason = known_primary_reason
            else:
                primary = execute_isolated_attempt(
                    workspace=workspace,
                    label="primary",
                    repo_root=repo_root,
                    head=head,
                    plan_rel=plan_rel,
                    plan_digest=plan_digest,
                    values=values,
                    run_id=args.orchestration_run_id,
                    plan_execution_attempt_id=args.execution_attempt_id,
                    attempt_lineage={"attempt_kind": "initial", "correction_round": 0, "attempt_label": "primary"},
                    normalized_scope=normalized_scope,
                    bwrap_bin=bwrap_bin,
                    git_bin=git_bin,
                    reserved_artifacts=reserved_artifacts,
                    extra_env=args.worker_env,
                    hidden_directories=(output_dir, host_codex_home_path()),
                    codex_bin=codex_bin,
                    model=primary_model,
                    reasoning=primary_reasoning,
                )
                attempts.append(primary["record"])
                if primary["result"].returncode == 0:
                    selected = primary
                else:
                    fallback_reason = classify_codex_unavailability(
                        primary["result"].stdout, primary["result"].stderr
                    )
                    if fallback_reason is None:
                        raise RunnerError(
                            f"worker exited with {primary['result'].returncode}; stdout/stderr saved under {output_dir}"
                        )
                    availability_failures += 1
                    if availability_state is not None:
                        availability_state.record(primary_model, fallback_reason)
            if primary is None or primary["result"].returncode != 0:
                if args.no_model_fallback:
                    if primary is not None:
                        raise RunnerError(
                            f"worker exited with {primary['result'].returncode}; stdout/stderr saved under {output_dir}"
                        )
                    raise RunnerError(
                        "preferred model is unavailable and model fallback is disabled"
                    )
                known_fallback_reason = (
                    availability_state.reason_for(fallback_model)
                    if availability_state is not None
                    else None
                )
                if known_fallback_reason is not None:
                    skipped_known_unavailable_starts += 1
                    raise RunnerError("fallback model is already recorded unavailable for this orchestration run")
                hidden_attempt_state = [output_dir, host_codex_home_path()]
                if primary is not None:
                    hidden_attempt_state.append(primary["attempt_root"])
                fallback = execute_isolated_attempt(
                    workspace=workspace,
                    label="fallback",
                    repo_root=repo_root,
                    head=head,
                    plan_rel=plan_rel,
                    plan_digest=plan_digest,
                    values=values,
                    run_id=args.orchestration_run_id,
                    plan_execution_attempt_id=args.execution_attempt_id,
                    attempt_lineage={"attempt_kind": "initial", "correction_round": 0, "attempt_label": "fallback"},
                    normalized_scope=normalized_scope,
                    bwrap_bin=bwrap_bin,
                    git_bin=git_bin,
                    reserved_artifacts=reserved_artifacts,
                    extra_env=args.worker_env,
                    hidden_directories=tuple(hidden_attempt_state),
                    codex_bin=codex_bin,
                    model=fallback_model,
                    reasoning=fallback_reasoning_effort,
                )
                attempts.append(fallback["record"])
                if fallback["result"].returncode != 0:
                    fallback_unavailable_reason = classify_codex_unavailability(
                        fallback["result"].stdout, fallback["result"].stderr
                    )
                    if fallback_unavailable_reason is not None:
                        availability_failures += 1
                        if availability_state is not None:
                            availability_state.record(fallback_model, fallback_unavailable_reason)
                    raise RunnerError(
                        f"fallback worker exited with {fallback['result'].returncode}; stdout/stderr saved under {output_dir}"
                    )
                selected = fallback
        else:
            worker_binary = require_executable("worker", args.worker_binary)
            selected = execute_isolated_attempt(
                workspace=workspace,
                label="custom",
                repo_root=repo_root,
                head=head,
                plan_rel=plan_rel,
                plan_digest=plan_digest,
                values=values,
                run_id=args.orchestration_run_id,
                plan_execution_attempt_id=args.execution_attempt_id,
                attempt_lineage={"attempt_kind": "initial", "correction_round": 0, "attempt_label": "custom"},
                normalized_scope=normalized_scope,
                bwrap_bin=bwrap_bin,
                git_bin=git_bin,
                reserved_artifacts=reserved_artifacts,
                extra_env=args.worker_env,
                hidden_directories=(output_dir,),
                custom_command=[worker_binary, *args.worker_arg],
            )
            worker_kind = "custom"
            if selected["result"].returncode != 0:
                raise RunnerError(
                    f"worker exited with {selected['result'].returncode}; stdout/stderr saved under {output_dir}"
                )

        if selected["completion_claims_error"] is not None:
            raise RunnerError(
                "worker completion claims were rejected; process diagnostics and a safe failure receipt "
                f"were saved under {output_dir}"
            )

        worker_result = select_attempt_artifacts(selected, reserved_artifacts)
        contract_path = reserved_artifacts["worker-contract.json"]
        contract_path.write_bytes(selected["contract_bytes"])
        contract_digest = hash_file(contract_path)
        worker_result["kind"] = worker_kind
        if attempts:
            worker_result["attempts"] = attempts
            worker_result["selected_attempt"] = selected["record"]["label"]
        if fallback_reason is not None:
            worker_result["fallback_reason"] = fallback_reason

        materialize_writable_shadows(
            selected["shadows"], selected["scratch_dir"] / "writable-shadows"
        )

        patch_bytes, clone_head_after_worker, refs_after_worker = collect_candidate_patch_in_sandbox(
            bwrap_bin=bwrap_bin,
            git_bin=git_bin,
            clone_dir=selected["clone_dir"],
            scratch_dir=selected["scratch_dir"],
            env_vars=selected["env_vars"],
        )
        if clone_head_after_worker != head:
            raise RunnerError("worker changed the clone HEAD and candidate changes were rejected")
        if refs_after_worker != selected["initial_refs"]:
            raise RunnerError("worker changed clone refs and candidate changes were rejected")
        if not patch_bytes:
            raise RunnerError("worker produced no candidate changes")

        patch_digest = hashlib.sha256(patch_bytes).hexdigest()
        changed_paths = normalize_changed_paths(
            derive_changed_paths_from_patch(repo_root, git_bin, patch_bytes, head),
            repo_root,
        )
        if not changed_paths:
            raise RunnerError("worker produced no candidate changes")
        disallowed = [path for path in changed_paths if not scope_allows_path(normalized_scope, path)]
        if disallowed:
            raise RunnerError(f"worker changed paths outside write_scope: {', '.join(disallowed)}")

        receipt_candidate = {
            "patch_digest": "sha256:" + patch_digest,
            "changed_paths": sorted(changed_paths),
        }
        completion_receipt = write_attempt_completion_receipt(
            selected,
            reserved_artifacts=reserved_artifacts,
            candidate=receipt_candidate,
            final=True,
        )
        patch_path = reserved_artifacts["candidate.patch"]
        if write_bytes(patch_path, patch_bytes) != patch_digest:
            raise RunnerError("candidate patch changed while it was published")
        if completion_receipt["claims"]["attempt_result"] != "success":
            raise RunnerError(
                "worker completion receipt reports failure; candidate was not admitted"
            )
        completion_receipt_path = selected["completion_receipt_path"]
        completion_receipt_digest = selected["completion_receipt_digest"]
        process_result_path = selected["process_result_path"]
        process_result_digest = selected["process_result_digest"]

        telemetry_attempts = attempts if worker_kind == "codex" else [selected["record"]]
        telemetry = {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "attempt_durations_seconds": [
                bounded_duration(0.0, float(attempt["duration_seconds"]))
                for attempt in telemetry_attempts
            ],
            "runner_duration_seconds": bounded_duration(runner_started, time.monotonic()),
            "model_starts": len(attempts) if worker_kind == "codex" else 0,
            "availability_failures": availability_failures,
            "skipped_known_unavailable_starts": skipped_known_unavailable_starts,
            "candidate_generations": 1,
            "full_validation_count": 0,
            "authoritative_validation_count": 0,
            "focused_validation_count": 0,
            "parent_review_rejections": 0,
            "correction_round": 0,
            "implementation_risk": implementation_risk,
            "implementation_ambiguity": implementation_ambiguity,
        }

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "source_head": head,
            "plan_path": plan_rel,
            "plan_digest": plan_digest,
            "worker_contract_path": str(contract_path),
            "worker_contract_digest": contract_digest,
            "worker_completion_receipt_path": str(completion_receipt_path),
            "worker_completion_receipt_digest": completion_receipt_digest.removeprefix("sha256:"),
            "worker_process_result_path": str(process_result_path),
            "worker_process_result_digest": process_result_digest.removeprefix("sha256:"),
            "worker_attempt_label": selected["record"]["label"],
            "worker_attempt_id": selected["attempt_id"],
            "allowed_write_scope": normalized_scope,
            "changed_paths": changed_paths,
            "patch_path": str(patch_path),
            "patch_digest": patch_digest,
            "orchestration_run_id": args.orchestration_run_id,
            "plan_execution_attempt_id": args.execution_attempt_id,
            "lifecycle_state_path": str(Path(args.lifecycle_state).expanduser().absolute()),
            "worker_result": worker_result,
            "telemetry": telemetry,
        }
        manifest_path = reserved_artifacts["manifest.json"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        focused_raw = values.get("focused_validation", [])
        lifecycle_state.persist(
            {
                "schema_version": LIFECYCLE_STATE_SCHEMA_VERSION,
                "orchestration_run_id": args.orchestration_run_id,
                "plan_execution_attempt_id": args.execution_attempt_id,
                "current_manifest_digest": hash_file(manifest_path),
                "current_patch_digest": patch_digest,
                "correction_round": 0,
                "candidate_generations": 1,
                "phase": "admitted",
                "focused_required": isinstance(focused_raw, list) and bool(focused_raw),
                "focused_validation_count": 0,
                "authoritative_validation_count": 0,
                "parent_review_rejections": 0,
            }
        )
    print(str(manifest_path))
    return 0


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunnerError(f"manifest is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"manifest is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RunnerError(f"manifest must contain a JSON object: {path}")
    return data


def read_bounded_regular_file(path: Path, maximum_bytes: int, label: str) -> bytes:
    if not path.is_absolute():
        path = (Path.cwd() / path).absolute()
    ensure_no_symlink_components(path)
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        )
    except OSError as exc:
        raise RunnerError(f"{label} must be a regular non-symlink file") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RunnerError(f"{label} must be a regular file")
        if metadata.st_size > maximum_bytes:
            raise RunnerError(f"{label} exceeds the byte bound")
        return read_bounded_fd(descriptor, maximum_bytes)
    finally:
        os.close(descriptor)


def verify_candidate_manifest(
    *,
    repo_root: Path,
    git_bin: str,
    planlib: ModuleType,
    manifest_path: Path,
    expected_plan: str | None = None,
    require_applicable: bool = True,
    require_clean: bool = True,
    allow_applied_symlink_targets: bool = False,
) -> dict[str, Any]:
    manifest_bytes = read_bounded_regular_file(manifest_path, 1024 * 1024, "candidate manifest")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError("candidate manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise RunnerError("candidate manifest must contain a JSON object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RunnerError(f"unsupported manifest schema version: {manifest.get('schema_version')}")
    run_id = manifest.get("orchestration_run_id")
    plan_execution_attempt_id = require_receipt_code(
        manifest.get("plan_execution_attempt_id"), label="manifest plan execution attempt identifier"
    )
    lifecycle_path = manifest.get("lifecycle_state_path")
    validate_bounded_text(run_id, "manifest orchestration run identifier", ORCHESTRATION_RUN_ID_MAX_BYTES)
    if not isinstance(lifecycle_path, str) or not Path(lifecycle_path).is_absolute():
        raise RunnerError("manifest lifecycle_state_path must be an absolute path")
    lineage = manifest.get("correction_lineage")
    correction_round = 0 if lineage is None else lineage.get("correction_round", -1) if isinstance(lineage, dict) else -1
    validate_manifest_telemetry(manifest.get("telemetry"), correction_round)
    plan_rel = manifest.get("plan_path")
    if not isinstance(plan_rel, str):
        raise RunnerError("manifest plan_path must be a string")
    if expected_plan is not None and plan_rel != expected_plan:
        raise RunnerError("prior manifest plan path does not match the requested correction plan")
    plan_path, plan_rel, values, normalized_scope = load_plan(planlib, repo_root, plan_rel)
    current_head = git_text(repo_root, git_bin, "rev-parse", "HEAD")
    if current_head != manifest.get("source_head"):
        raise RunnerError("source HEAD no longer matches the worker manifest")
    current_plan_digest = hash_file(plan_path)
    if current_plan_digest != manifest.get("plan_digest"):
        raise RunnerError("active plan digest no longer matches the worker manifest")
    manifest_scope = manifest.get("allowed_write_scope")
    if not isinstance(manifest_scope, list):
        raise RunnerError("manifest allowed_write_scope must be a list")
    normalized_manifest_scope = parse_write_scope(manifest_scope)
    if normalized_manifest_scope != normalized_scope:
        raise RunnerError("candidate manifest write scope differs from the current plan")
    verify_worker_contract(
        repo_root=repo_root,
        git_bin=git_bin,
        manifest_path=manifest_path,
        manifest=manifest,
        plan_path=plan_path,
        plan_rel=plan_rel,
        values=values,
        normalized_scope=normalized_scope,
    )
    patch_path_raw = manifest.get("patch_path")
    if not isinstance(patch_path_raw, str):
        raise RunnerError("manifest patch_path must be a string")
    patch_path = Path(patch_path_raw).expanduser()
    if not patch_path.is_absolute():
        patch_path = (manifest_path.parent / patch_path).absolute()
    patch_bytes = read_bounded_regular_file(patch_path, 128 * 1024 * 1024, "candidate patch")
    patch_digest = hashlib.sha256(patch_bytes).hexdigest()
    if patch_digest != manifest.get("patch_digest"):
        raise RunnerError("candidate patch digest no longer matches the worker manifest")
    changed_paths = normalize_changed_paths(
        derive_changed_paths_from_patch(repo_root, git_bin, patch_bytes, current_head),
        repo_root,
        include_symlink_targets=not allow_applied_symlink_targets,
    )
    manifest_changed = manifest.get("changed_paths", [])
    if not isinstance(manifest_changed, list):
        raise RunnerError("manifest changed_paths must be a list")
    normalized_manifest_changed = [
        normalize_repo_relpath(item, label="manifest changed path")[0]
        for item in manifest_changed
    ]
    if changed_paths != normalized_manifest_changed:
        raise RunnerError("candidate patch changed paths do not match the worker manifest")
    receipt_path_raw = manifest.get("worker_completion_receipt_path")
    receipt_digest = manifest.get("worker_completion_receipt_digest")
    if not isinstance(receipt_path_raw, str) or not isinstance(receipt_digest, str):
        raise RunnerError("candidate manifest is missing the worker completion receipt binding")
    receipt_path = Path(receipt_path_raw).expanduser()
    if not receipt_path.is_absolute():
        receipt_path = (manifest_path.parent / receipt_path).absolute()
    if receipt_path.parent != manifest_path.parent or receipt_path.name not in {
        "worker-completion-receipt.json",
        "worker-primary-completion-receipt.json",
        "worker-fallback-completion-receipt.json",
    }:
        raise RunnerError("worker completion receipt must be one fixed sibling of the candidate manifest")
    receipt_bytes = read_bounded_regular_file(
        receipt_path, WORKER_COMPLETION_RECEIPT_MAX_BYTES, "worker completion receipt"
    )
    if hashlib.sha256(receipt_bytes).hexdigest() != receipt_digest:
        raise RunnerError("worker completion receipt digest no longer matches the candidate manifest")
    receipt = load_worker_completion_receipt(receipt_bytes)
    attempt_label = manifest.get("worker_attempt_label")
    if attempt_label not in {"primary", "fallback", "custom"}:
        raise RunnerError("candidate manifest has an invalid worker attempt label")
    attempt_id = require_receipt_code(
        manifest.get("worker_attempt_id"), label="manifest attempt identifier"
    )
    process_path_raw = manifest.get("worker_process_result_path")
    process_digest = manifest.get("worker_process_result_digest")
    if not isinstance(process_path_raw, str) or not isinstance(process_digest, str):
        raise RunnerError("candidate manifest is missing the worker process result binding")
    process_path = Path(process_path_raw).expanduser()
    if not process_path.is_absolute():
        process_path = (manifest_path.parent / process_path).absolute()
    if process_path.parent != manifest_path.parent or process_path.name not in {
        "worker-process-result.json",
        "worker-primary-process-result.json",
        "worker-fallback-process-result.json",
    }:
        raise RunnerError("worker process result must be one fixed sibling of the candidate manifest")
    process_bytes = read_bounded_regular_file(
        process_path, WORKER_COMPLETION_RECEIPT_MAX_BYTES, "worker process result"
    )
    if hashlib.sha256(process_bytes).hexdigest() != process_digest:
        raise RunnerError("worker process result digest no longer matches the candidate manifest")
    process_result = validate_attempt_process_result(
        load_exact_json_object(process_bytes, label="worker process result")
    )
    correction_lineage = manifest.get("correction_lineage")
    if correction_lineage is None:
        expected_attempt = {
            "attempt_id": attempt_id,
            "attempt_kind": "initial",
            "correction_round": 0,
            "correction_lineage": None,
        }
    else:
        if not isinstance(correction_lineage, dict):
            raise RunnerError("candidate manifest correction lineage is invalid")
        expected_attempt = {
            "attempt_id": attempt_id,
            "attempt_kind": "correction",
            "correction_round": correction_lineage.get("correction_round"),
            "correction_lineage": {
                "prior_manifest_digest": "sha256:" + str(
                    correction_lineage.get("prior_manifest_digest")
                )
            },
        }
    expected_receipt = {
        "repository_identity": derive_repository_identity(repo_root, git_bin),
        "source_head": current_head,
        "plan_path": plan_rel,
        "plan_digest": "sha256:" + current_plan_digest,
        "worker_contract_digest": "sha256:" + str(manifest.get("worker_contract_digest")),
        "orchestration_run_id": run_id,
        "plan_execution_attempt_id": plan_execution_attempt_id,
        "attempt": expected_attempt,
        "candidate": {
            "patch_digest": "sha256:" + patch_digest,
            "changed_paths": changed_paths,
        },
        "acceptance_digests": [
            prefixed_sha256(item)
            for item in unique_contract_text_items(
                values.get("acceptance"), label="acceptance", require_nonempty=True
            )
        ],
    }
    receipt = validate_worker_completion_receipt(receipt, expected=expected_receipt)
    worker_result = manifest.get("worker_result")
    expected_process = {
        "exit_status": process_result["exit_status"],
        "diagnostic_codes": process_result["diagnostic_codes"],
    }
    if (
        not isinstance(worker_result, dict)
        or process_result["attempt_id"] != attempt_id
        or receipt["process"] != expected_process
        or process_result["exit_status"] != worker_result.get("returncode")
        or process_result["stdout_digest"] != "sha256:" + str(worker_result.get("stdout_digest"))
        or process_result["stderr_digest"] != "sha256:" + str(worker_result.get("stderr_digest"))
    ):
        raise RunnerError("worker completion receipt process status differs from preserved worker diagnostics")
    disallowed = [path for path in changed_paths if not scope_allows_path(normalized_scope, path)]
    if disallowed:
        raise RunnerError(f"candidate patch changes paths outside the current write_scope: {', '.join(disallowed)}")
    for path in changed_paths:
        ensure_no_symlink_path_trick(
            repo_root, path, include_target=not allow_applied_symlink_targets
        )
    if require_applicable:
        run_subprocess(
            (git_bin, "apply", "--check", "--binary", "-"), cwd=repo_root, stdin=patch_bytes
        )
    if require_clean:
        ensure_clean_worktree(repo_root, git_bin)
    if git_text(repo_root, git_bin, "rev-parse", "HEAD") != current_head:
        raise RunnerError("source HEAD changed during candidate verification")
    return {
        "manifest": manifest,
        "manifest_digest": hashlib.sha256(manifest_bytes).hexdigest(),
        "plan_path": plan_path,
        "plan_rel": plan_rel,
        "values": values,
        "normalized_scope": normalized_scope,
        "head": current_head,
        "plan_digest": current_plan_digest,
        "patch_path": patch_path,
        "patch_bytes": patch_bytes,
        "patch_digest": patch_digest,
        "changed_paths": changed_paths,
        "worker_completion_receipt": receipt,
        "worker_completion_receipt_path": receipt_path,
        "worker_completion_receipt_digest": receipt_digest,
        "worker_process_result": process_result,
        "worker_process_result_path": process_path,
        "worker_process_result_digest": process_digest,
    }


def next_correction_lineage(
    prior_manifest: dict[str, Any],
    *,
    prior_manifest_digest: str,
    prior_patch_digest: str,
    correction_brief_digest: str,
) -> dict[str, Any]:
    prior_lineage = prior_manifest.get("correction_lineage")
    if prior_lineage is None:
        prior_round = 0
    else:
        required = {
            "prior_manifest_digest",
            "prior_patch_digest",
            "correction_round",
            "correction_brief_digest",
        }
        if not isinstance(prior_lineage, dict) or set(prior_lineage) != required:
            raise RunnerError("prior correction lineage has an invalid exact field shape")
        prior_round = prior_lineage.get("correction_round")
        if not isinstance(prior_round, int) or isinstance(prior_round, bool) or prior_round < 1:
            raise RunnerError("prior correction lineage has an invalid correction round")
        for key in required - {"correction_round"}:
            value = prior_lineage.get(key)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise RunnerError(f"prior correction lineage has an invalid digest: {key}")
    correction_round = prior_round + 1
    if correction_round > MAX_CORRECTION_ROUNDS:
        raise RunnerError("correction budget exhausted after one isolated correction")
    return {
        "prior_manifest_digest": prior_manifest_digest,
        "prior_patch_digest": prior_patch_digest,
        "correction_round": correction_round,
        "correction_brief_digest": correction_brief_digest,
    }


def execute_validation_operation(
    *,
    repo_root: Path,
    git_bin: str,
    bwrap_bin: str,
    verified: dict[str, Any],
    workspace: Path,
    index: int,
    command: Any,
    private_dependency_tree: Path | None,
    private_node_runtime: dict[str, Any] | None,
    output_dir: Path,
    manifest_path: Path,
    bounds: tuple[float, int] | None = None,
    capture_sink: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path, bytes]:
    """Prepare and run one planned validation operation without mutating the source checkout."""
    command_root = workspace / f"command-{index}"
    clone_dir = command_root / "review-clone"
    scratch_dir = command_root / "scratch"
    scratch_dir.mkdir(parents=True)
    clone_at_head(repo_root, git_bin, verified["head"], clone_dir)
    initial_refs = git(clone_dir, git_bin, "show-ref", "--head", "--dereference").stdout
    run_subprocess(
        (git_bin, "apply", "--check", "--binary", "-"),
        cwd=clone_dir,
        stdin=verified["patch_bytes"],
    )
    run_subprocess(
        (git_bin, "apply", "--binary", "-"), cwd=clone_dir, stdin=verified["patch_bytes"]
    )
    read_only_shadows: list[tuple[Path, Path]] = []
    writable_shadows: list[tuple[Path, Path]] = []
    dependency_target: Path | None = None
    if private_dependency_tree is not None:
        dependency_target = clone_dir / "node_modules"
        dependency_target.mkdir()
        read_only_shadows.append((private_dependency_tree, dependency_target))
        writable_shadows.extend(
            dependency_cache_shadows(private_dependency_tree, dependency_target, scratch_dir)
        )
    env_vars = prepare_worker_environment(
        source_repo=repo_root,
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        plan_rel=verified["plan_rel"],
        extra_env=(),
        include_codex_home=False,
    )
    env_vars["PATH"] = (
        f"{private_node_runtime['runtime_root'] / 'bin'}:{DEFAULT_PATH}"
        if command.argv[0] == "npm" and private_node_runtime is not None
        else DEFAULT_PATH
    )
    playwright_browsers = (
        private_dependency_tree / ".playwright-browsers"
        if private_dependency_tree is not None
        else None
    )
    if playwright_browsers is not None and (
        playwright_browsers.exists() or playwright_browsers.is_symlink()
    ):
        if playwright_browsers.is_symlink() or not playwright_browsers.is_dir():
            raise RunnerError("private Playwright browser snapshot changed shape")
        assert dependency_target is not None
        env_vars["PLAYWRIGHT_BROWSERS_PATH"] = str(
            dependency_target / ".playwright-browsers"
        )
    validation_hidden = [output_dir, manifest_path.parent, host_codex_home_path()]
    host_home = Path.home().resolve()
    if host_home.is_dir():
        validation_hidden.append(host_home)
    command_argv = (
        (
            str(private_node_runtime["node_path"]),
            str(private_node_runtime["npm_cli_path"]),
            *command.argv[1:],
        )
        if command.argv[0] == "npm" and private_node_runtime is not None
        else (require_validation_executable(command.argv[0], clone_dir), *command.argv[1:])
    )
    started = time.monotonic()
    sandbox_argv = build_bwrap_command(
        bwrap_bin=bwrap_bin,
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        command=command_argv,
        env_vars=env_vars,
        writable_clone=True,
        writable_shadows=writable_shadows,
        hidden_directories=normalize_hidden_directories(
            validation_hidden,
            visible_paths=(clone_dir, scratch_dir),
        ),
        read_only_shadows=read_only_shadows,
        network_enabled=False,
    )
    if bounds is None:
        result = run_subprocess(
            sandbox_argv,
            cwd=repo_root,
            env=sanitize_process_env(),
            check=False,
        )
        returncode = result.returncode
        stdout_bytes = result.stdout
        stderr_bytes = result.stderr
    else:
        timeout_seconds, output_limit_bytes = bounds
        bounded = run_bounded_subprocess(
            sandbox_argv,
            cwd=repo_root,
            env=sanitize_process_env(),
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )
        returncode = bounded["returncode"]
        stdout_bytes = bounded["stdout"]
        stderr_bytes = bounded["stderr"]
        if capture_sink is not None:
            capture_sink.update(bounded)
    return (
        {
            "index": index,
            "argv": list(command.argv),
            "duration_seconds": bounded_duration(started, time.monotonic()),
            "returncode": returncode,
            "stdout_digest": hashlib.sha256(stdout_bytes).hexdigest(),
            "stderr_digest": hashlib.sha256(stderr_bytes).hexdigest(),
        },
        clone_dir,
        initial_refs,
    )


def preflight_execution_genesis(state_path: str) -> str:
    """Read the execution genesis identity from the parent-owned ledger.

    The read is bounded and does not interpret ledger history; the claim only
    needs the identity that distinguishes this execution from another one.
    """

    path = Path(state_path).expanduser()
    try:
        content = read_bounded_regular_file(
            path, PREFLIGHT_LEDGER_READ_MAX_BYTES, "plan execution state"
        )
    except RunnerError:
        raise
    except OSError as exc:
        raise RunnerError(f"could not read the plan execution state: {exc}") from exc
    payload = load_exact_json_object(content, label="plan execution state")
    genesis = payload.get("genesis_digest")
    if not isinstance(genesis, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", genesis):
        raise RunnerError("plan execution state has no usable execution genesis identity")
    return genesis


def require_preflight_claim_directory(raw: str, repo_root: Path) -> Path:
    """Return the parent-owned claim directory, refusing an unsafe location."""

    directory = Path(raw).expanduser()
    if not directory.is_absolute():
        raise RunnerError("preflight claim directory must be an absolute path")
    if directory.is_symlink():
        raise RunnerError("preflight claim directory must not be a symlink")
    if not directory.is_dir():
        raise RunnerError(f"preflight claim directory does not exist: {directory}")
    resolved = directory.resolve()
    if path_is_within(repo_root, resolved) or resolved == repo_root:
        raise RunnerError("preflight claim directory must live outside the repository")
    metadata = resolved.stat()
    if metadata.st_uid != os.getuid():
        raise RunnerError("preflight claim directory must be owned by the parent")
    if stat.S_IMODE(metadata.st_mode) & (stat.S_IRWXG | stat.S_IRWXO):
        raise RunnerError("preflight claim directory must not be group or world accessible")
    return resolved


def claim_single_preflight(claim_dir: Path, payload: dict[str, Any]) -> Path:
    """Claim the one preflight allowed for this candidate, or refuse.

    The claim is created exclusively, so a duplicate, concurrent, or replayed
    request cannot start a second process. An existing claim is never reused
    or repaired: incomplete evidence from an earlier crash keeps the candidate
    closed rather than granting another run.
    """

    claim_path = claim_dir / f"{payload['candidate_manifest_digest']}.json"
    content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        descriptor = os.open(
            claim_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
    except FileExistsError as exc:
        raise RunnerError(
            "this candidate has already claimed its one preflight; a further attempt is refused "
            f"even after failure: {claim_path}"
        ) from exc
    except OSError as exc:
        raise RunnerError(f"could not claim the preflight: {exc}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    return claim_path


def preflight_candidate(args: argparse.Namespace) -> int:
    """Run one bounded diagnostic command against an admitted candidate.

    This is parent-owned diagnostic feedback, not validation. It never records
    a validation event, never advances the lifecycle phase, never changes a
    counter, and never satisfies an acceptance witness. Its only permitted use
    is as evidence for the single correction the run already allows.
    """

    if not args.parent_diff_approved or not args.critical_invariants_approved:
        raise RunnerError(
            "candidate preflight requires explicit parent diff and critical-invariant approval"
        )
    preflight_started = time.monotonic()
    timeout_seconds = int(args.timeout_seconds)
    if not 1 <= timeout_seconds <= PREFLIGHT_MAXIMUM_TIMEOUT_SECONDS:
        raise RunnerError(
            f"preflight timeout must be between 1 and {PREFLIGHT_MAXIMUM_TIMEOUT_SECONDS} seconds"
        )
    git_bin = require_executable("git", args.git_bin)
    bwrap_bin = require_executable("bwrap", args.bwrap_bin)
    ensure_bwrap_usable(bwrap_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    validation_commands = load_plan_validation_commands()
    ensure_clean_worktree(repo_root, git_bin)
    claim_dir = require_preflight_claim_directory(args.preflight_claim_dir, repo_root)
    manifest_path = Path(args.manifest).expanduser().resolve()
    verified = verify_candidate_manifest(
        repo_root=repo_root,
        git_bin=git_bin,
        planlib=planlib,
        manifest_path=manifest_path,
    )
    require_plan_worktree(repo_root, verified["plan_rel"], "running a candidate preflight")
    enforce_plan_execution_gate(
        args,
        plan=verified["plan_rel"],
        open_attempt_id=verified["manifest"]["plan_execution_attempt_id"],
    )
    if args.orchestration_run_id != verified["manifest"]["orchestration_run_id"]:
        raise RunnerError("preflight run identifier differs from the verified manifest")
    if Path(args.lifecycle_state).expanduser().absolute() != Path(
        verified["manifest"]["lifecycle_state_path"]
    ):
        raise RunnerError("preflight lifecycle state path differs from the verified manifest")
    raw_commands = verified["values"].get("focused_validation", [])
    if not isinstance(raw_commands, list):
        raise RunnerError("plan focused_validation must be a list")
    try:
        commands = validation_commands.parse_validation_commands(raw_commands)
    except ValueError as exc:
        raise RunnerError(f"plan focused_validation contains an invalid command: {exc}") from exc
    if not commands:
        raise RunnerError("this plan has no focused validation stage to select a preflight from")
    index = int(args.command_index)
    if not 0 <= index < len(commands):
        raise RunnerError(
            f"preflight command index must select one declared focused command in 0..{len(commands) - 1}"
        )
    command = commands[index]
    if command.argv[:2] == ("npm", "run"):
        raise RunnerError(
            "preflight provisions no npm dependency tree; select another declared focused command"
        )
    output_dir = materialize_output_dir(repo_root, args.output_dir)
    report_path = output_dir / "preflight.json"
    if report_path.exists() or report_path.is_symlink():
        raise RunnerError(f"preflight report path is already present: {report_path}")
    genesis = preflight_execution_genesis(args.plan_execution_state)
    capture: dict[str, Any] = {}
    lifecycle_context = open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    )
    with lifecycle_context as lifecycle_state, tempfile.TemporaryDirectory(
        prefix="sandboxed-plan-worker-preflight-"
    ) as workspace_tmp:
        workspace = Path(workspace_tmp)
        lifecycle = lifecycle_state.require_existing()
        if (
            lifecycle["current_manifest_digest"] != verified["manifest_digest"]
            or lifecycle["current_patch_digest"] != verified["patch_digest"]
            or lifecycle["plan_execution_attempt_id"]
            != verified["manifest"]["plan_execution_attempt_id"]
        ):
            raise RunnerError("preflight manifest is not the current lifecycle leaf")
        if lifecycle["phase"] != "admitted":
            raise RunnerError(
                "preflight runs on an admitted candidate before validation, not after it"
            )
        enforce_plan_execution_gate(
            args,
            plan=verified["plan_rel"],
            open_attempt_id=verified["manifest"]["plan_execution_attempt_id"],
        )
        if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
            raise RunnerError("source HEAD changed before the preflight claim")
        claim_payload = {
            "schema_version": PREFLIGHT_CLAIM_SCHEMA_VERSION,
            "record_type": "candidate_preflight_claim",
            "plan_path": verified["plan_rel"],
            "plan_execution_attempt_id": verified["manifest"]["plan_execution_attempt_id"],
            "orchestration_run_id": args.orchestration_run_id,
            "execution_genesis_digest": genesis,
            "candidate_manifest_digest": verified["manifest_digest"],
            "candidate_patch_digest": verified["patch_digest"],
            "command_digest": prefixed_sha256("\u0000".join(command.argv)),
            "command_index": index,
            "source_head": verified["head"],
        }
        claim_path = claim_single_preflight(claim_dir, claim_payload)
        try:
            record, _clone_dir, _initial_refs = execute_validation_operation(
                repo_root=repo_root,
                git_bin=git_bin,
                bwrap_bin=bwrap_bin,
                verified=verified,
                workspace=workspace,
                index=index,
                command=command,
                private_dependency_tree=None,
                private_node_runtime=None,
                output_dir=output_dir,
                manifest_path=manifest_path,
                bounds=(float(timeout_seconds), PREFLIGHT_OUTPUT_LIMIT_BYTES),
                capture_sink=capture,
            )
        except (RunnerError, OSError) as exc:
            raise RunnerError(f"preflight execution failed to start or complete: {exc}") from exc
        ensure_clean_worktree(repo_root, git_bin)
        if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
            raise RunnerError("source HEAD changed during the candidate preflight")
    timed_out = bool(capture.get("timed_out"))
    truncated = bool(capture.get("output_truncated"))
    status = (
        "timed_out" if timed_out else "output_limit_exceeded" if truncated else "completed"
    )
    report = {
        "schema_version": PREFLIGHT_REPORT_SCHEMA_VERSION,
        "record_type": "candidate_preflight_diagnostic",
        "evidence_class": "diagnostic",
        "is_validation_evidence": False,
        "plan_path": verified["plan_rel"],
        "plan_digest": "sha256:" + verified["plan_digest"],
        "plan_execution_attempt_id": verified["manifest"]["plan_execution_attempt_id"],
        "execution_genesis_digest": genesis,
        "candidate_manifest_digest": verified["manifest_digest"],
        "candidate_patch_digest": verified["patch_digest"],
        "source_head": verified["head"],
        "claim_path_digest": prefixed_sha256(str(claim_path)),
        "command_index": index,
        "command_argv": list(command.argv),
        "command_digest": claim_payload["command_digest"],
        "timeout_seconds": timeout_seconds,
        "output_limit_bytes": PREFLIGHT_OUTPUT_LIMIT_BYTES,
        "status": status,
        "timed_out": timed_out,
        "output_truncated": truncated,
        "exit_status": record["returncode"],
        "passed": status == "completed" and record["returncode"] == 0,
        "stdout_digest": record["stdout_digest"],
        "stderr_digest": record["stderr_digest"],
        "stdout": capture.get("stdout", b"").decode("utf-8", errors="replace"),
        "stderr": capture.get("stderr", b"").decode("utf-8", errors="replace"),
        "duration_seconds": bounded_duration(preflight_started, time.monotonic()),
    }
    report_descriptor = os.open(
        report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(report_descriptor, "wb") as handle:
        handle.write((json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(str(report_path))
    return 0


def validate_candidate(args: argparse.Namespace) -> int:
    if not args.parent_diff_approved or not args.critical_invariants_approved:
        raise RunnerError(
            "candidate validation requires explicit parent diff and critical-invariant approval"
        )
    validation_started = time.monotonic()
    git_bin = require_executable("git", args.git_bin)
    bwrap_bin = require_executable("bwrap", args.bwrap_bin)
    ensure_bwrap_usable(bwrap_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    validation_commands = load_plan_validation_commands()
    ensure_clean_worktree(repo_root, git_bin)
    manifest_path = Path(args.manifest).expanduser().resolve()
    verified = verify_candidate_manifest(
        repo_root=repo_root,
        git_bin=git_bin,
        planlib=planlib,
        manifest_path=manifest_path,
    )
    require_plan_worktree(repo_root, verified["plan_rel"], "validating a sandboxed worker candidate")
    enforce_plan_execution_gate(
        args,
        plan=verified["plan_rel"],
        open_attempt_id=verified["manifest"]["plan_execution_attempt_id"],
    )
    if args.orchestration_run_id != verified["manifest"]["orchestration_run_id"]:
        raise RunnerError("validation run identifier differs from the verified manifest")
    if Path(args.lifecycle_state).expanduser().absolute() != Path(
        verified["manifest"]["lifecycle_state_path"]
    ):
        raise RunnerError("validation lifecycle state path differs from the verified manifest")
    immutable_selectors = {verified["plan_rel"]}
    try:
        immutable_selectors.add(str(Path(__file__).resolve().relative_to(repo_root)))
    except ValueError:
        pass
    changed_selectors = sorted(immutable_selectors.intersection(verified["changed_paths"]))
    if changed_selectors:
        raise RunnerError(
            "candidate must not change the active plan or runner that selects validation commands: "
            + ", ".join(changed_selectors)
        )
    changed_authority = sorted(
        path
        for path in verified["changed_paths"]
        if is_validation_authority_path(path)
    )
    declared_authority = verified["values"].get("validation_authority_scope", [])
    if not isinstance(declared_authority, list):
        raise RunnerError("plan validation_authority_scope must be a list")
    normalized_declared_authority = parse_write_scope(declared_authority)
    changed_authority.extend(
        path
        for path in verified["changed_paths"]
        if path not in changed_authority
        and scope_allows_path(normalized_declared_authority, path)
    )
    changed_authority.sort()
    if changed_authority:
        raise RunnerError(
            "candidate changes parent-owned validation authority and requires bounded parent "
            "implementation plus independent review: " + ", ".join(changed_authority)
        )
    key = "focused_validation" if args.suite == "focused" else "validation"
    raw_commands = verified["values"].get(key, [])
    if not isinstance(raw_commands, list):
        raise RunnerError(f"plan {key} must be a list")
    try:
        commands = validation_commands.parse_validation_commands(raw_commands)
    except ValueError as exc:
        raise RunnerError(f"plan {key} contains an invalid command: {exc}") from exc
    if args.suite == "focused" and not commands:
        raise RunnerError("this plan has no focused validation stage")
    requires_npm_dependencies = any(command.argv[:2] == ("npm", "run") for command in commands)
    node_runtime = (
        resolve_project_node_runtime(repo_root, git_bin)
        if requires_npm_dependencies
        else None
    )
    dependency_snapshot: dict[str, Any] | None = None
    dependency_snapshot_arg = getattr(args, "dependency_snapshot", None)
    if dependency_snapshot_arg is not None:
        dependency_snapshot = verify_dependency_snapshot(
            repo_root, Path(dependency_snapshot_arg), git_bin
        )
    if requires_npm_dependencies and dependency_snapshot is None:
        raise RunnerError(
            "npm validation requires a lock-bound --dependency-snapshot prepared outside the repository"
        )
    output_dir = materialize_output_dir(repo_root, args.output_dir)
    reserved = reserve_output_artifacts(output_dir)
    records: list[dict[str, Any]] = []
    failed = False
    failure: dict[str, object] | None = None
    lifecycle_context = open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    )
    with lifecycle_context as lifecycle_state, tempfile.TemporaryDirectory(
        prefix="sandboxed-plan-worker-validation-"
    ) as workspace_tmp:
        workspace = Path(workspace_tmp)
        private_dependency_tree: Path | None = None
        private_node_runtime: dict[str, Any] | None = None
        created_dependency_cache_mountpoints: list[Path] = []
        if dependency_snapshot is not None:
            private_dependency_tree = materialize_verified_dependency_tree(
                repo_root, dependency_snapshot, workspace / "verified-node_modules"
            )
            created_dependency_cache_mountpoints = ensure_dependency_cache_mountpoints(
                private_dependency_tree
            )
        if node_runtime is not None:
            private_node_runtime = materialize_project_node_runtime(
                node_runtime, workspace / "verified-node-runtime"
            )
        lifecycle = lifecycle_state.require_existing()
        if lifecycle["current_manifest_digest"] != verified["manifest_digest"] or lifecycle[
            "current_patch_digest"
        ] != verified["patch_digest"] or lifecycle["plan_execution_attempt_id"] != verified[
            "manifest"
        ]["plan_execution_attempt_id"]:
            raise RunnerError("validation manifest is not the current lifecycle leaf")
        expected_phase = (
            "focused_passed"
            if args.suite == "authoritative" and lifecycle["focused_required"]
            else "admitted"
        )
        if lifecycle["phase"] != expected_phase:
            raise RunnerError(
                f"{args.suite} validation is out of order or has already been attempted"
            )
        if args.suite == "focused" and not lifecycle["focused_required"]:
            raise RunnerError("lifecycle state does not require focused validation")
        focused_count = lifecycle["focused_validation_count"] + (args.suite == "focused")
        authoritative_count = lifecycle["authoritative_validation_count"] + (
            args.suite == "authoritative"
        )
        lifecycle_state.persist(
            {
                **lifecycle,
                "phase": f"{args.suite}_running",
                "focused_validation_count": int(focused_count),
                "authoritative_validation_count": int(authoritative_count),
            }
        )
        suite_error: RunnerError | None = None
        for index, command in enumerate(commands):
            started = time.monotonic()
            try:
                record, clone_dir, initial_refs = execute_validation_operation(
                    repo_root=repo_root,
                    git_bin=git_bin,
                    bwrap_bin=bwrap_bin,
                    verified=verified,
                    workspace=workspace,
                    index=index,
                    command=command,
                    private_dependency_tree=private_dependency_tree,
                    private_node_runtime=private_node_runtime,
                    output_dir=output_dir,
                    manifest_path=manifest_path,
                )
            except (RunnerError, OSError) as exc:
                failed = True
                suite_error = exc if isinstance(exc, RunnerError) else RunnerError(
                    "validation operation setup failed"
                )
                record = {
                    "index": index,
                    "argv": list(command.argv),
                    "duration_seconds": bounded_duration(started, time.monotonic()),
                    "returncode": 0,
                    "stdout_digest": hashlib.sha256(b"").hexdigest(),
                    "stderr_digest": hashlib.sha256(b"").hexdigest(),
                }
                records.append(record)
                failure = validation_failure_identity(
                    suite=args.suite,
                    kind="runner_setup",
                    command_index=index,
                    argv=command.argv,
                    exit_status=1,
                )
                break
            records.append(record)
            result_status = record["returncode"]
            if result_status != 0:
                failed = True
                failure = validation_failure_identity(
                    suite=args.suite,
                    kind="command",
                    command_index=index,
                    argv=command.argv,
                    exit_status=int(result_status),
                )
                break
            if dependency_snapshot is not None:
                try:
                    verify_private_dependency_integrity(
                        private_dependency_tree,
                        dependency_snapshot["tree_sha256"],
                        created_dependency_cache_mountpoints,
                    )
                except RunnerError as exc:
                    failed = True
                    suite_error = exc
                    failure = validation_failure_identity(
                        suite=args.suite,
                        kind="dependency_integrity",
                        command_index=index,
                        argv=command.argv,
                        exit_status=1,
                    )
                    break
            if node_runtime is not None:
                try:
                    verify_project_node_runtime(node_runtime, private_node_runtime)
                except RunnerError as exc:
                    failed = True
                    suite_error = exc
                    failure = validation_failure_identity(
                        suite=args.suite,
                        kind="runtime_integrity",
                        command_index=index,
                        argv=command.argv,
                        exit_status=1,
                    )
                    break
            try:
                observed_clone_head = git_text(clone_dir, git_bin, "rev-parse", "HEAD")
                observed_clone_refs = git(
                    clone_dir, git_bin, "show-ref", "--head", "--dereference"
                ).stdout
            except RunnerError as exc:
                failed = True
                suite_error = exc
                failure = validation_failure_identity(
                    suite=args.suite,
                    kind="runner_setup",
                    command_index=index,
                    argv=command.argv,
                    exit_status=1,
                )
                break
            if observed_clone_head != verified["head"]:
                failed = True
                suite_error = RunnerError("validation command changed review-clone HEAD")
                failure = validation_failure_identity(
                    suite=args.suite,
                    kind="head_immutability",
                    command_index=index,
                    argv=command.argv,
                    exit_status=1,
                )
                break
            if observed_clone_refs != initial_refs:
                failed = True
                suite_error = RunnerError("validation command changed review-clone refs")
                failure = validation_failure_identity(
                    suite=args.suite,
                    kind="ref_immutability",
                    command_index=index,
                    argv=command.argv,
                    exit_status=1,
                )
                break
        try:
            ensure_clean_worktree(repo_root, git_bin)
            if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
                raise RunnerError("source HEAD changed during candidate validation")
        except RunnerError as exc:
            if not records:
                raise
            if failed:
                suite_error = suite_error or exc
            else:
                failed = True
                suite_error = exc
                source_index = len(records) - 1
                source_command = commands[source_index]
                failure = validation_failure_identity(
                    suite=args.suite,
                    kind="source_integrity",
                    command_index=source_index,
                    argv=source_command.argv,
                    exit_status=1,
                )
        report = {
            "schema_version": 1,
            "candidate_manifest_digest": verified["manifest_digest"],
            "candidate_patch_digest": verified["patch_digest"],
            "plan_execution_attempt_id": verified["manifest"]["plan_execution_attempt_id"],
            "plan_path": verified["plan_rel"],
            "plan_digest": "sha256:" + verified["plan_digest"],
            "source_head": verified["head"],
            "implementation_mode": "candidate",
            "suite": args.suite,
            "parent_diff_approved": True,
            "critical_invariants_approved": True,
            "commands": records,
            "dependency_snapshot": (
                {
                    "package_manager": dependency_snapshot["package_manager"],
                    "package_json_sha256": dependency_snapshot["package_json_sha256"],
                    "package_lock_sha256": dependency_snapshot["package_lock_sha256"],
                    "tree_sha256": dependency_snapshot["tree_sha256"],
                }
                if dependency_snapshot is not None
                else None
            ),
            "node_runtime": (
                {
                    "requested_version": node_runtime["requested_version"],
                    "actual_version": node_runtime["actual_version"],
                    "node_sha256": node_runtime["node_sha256"],
                    "npm_sha256": node_runtime["npm_sha256"],
                    "npm_tree_sha256": node_runtime["npm_tree_sha256"],
                }
                if node_runtime is not None
                else None
            ),
            "passed": not failed,
            "failure": failure,
            "telemetry": {
                "duration_seconds": bounded_duration(validation_started, time.monotonic()),
                "focused_validation_count": focused_count,
                "authoritative_validation_count": authoritative_count,
                "full_validation_count": authoritative_count,
            },
        }
        report_path = reserved["validation.json"]
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        lifecycle_state.persist(
            {
                **lifecycle,
                "phase": f"{args.suite}_{'failed' if failed else 'passed'}",
                "focused_validation_count": int(focused_count),
                "authoritative_validation_count": int(authoritative_count),
            }
        )
        if suite_error is not None:
            raise suite_error
    if failed:
        raise RunnerError(f"{args.suite} validation failed; bounded report saved at {report_path}")
    print(str(report_path))
    return 0


def correct_worker(args: argparse.Namespace) -> int:
    runner_started = time.monotonic()
    git_bin = require_executable("git", args.git_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    plan_rel = normalize_manifest_path(repo_root, args.plan)
    require_plan_worktree(repo_root, plan_rel, "requesting a sandboxed worker correction")
    prior_manifest_path = Path(args.prior_manifest).expanduser()
    if not prior_manifest_path.is_absolute():
        prior_manifest_path = (Path.cwd() / prior_manifest_path).absolute()
    verified = verify_candidate_manifest(
        repo_root=repo_root,
        git_bin=git_bin,
        planlib=planlib,
        manifest_path=prior_manifest_path,
        expected_plan=plan_rel,
    )
    if args.orchestration_run_id != verified["manifest"]["orchestration_run_id"]:
        raise RunnerError("correction run identifier differs from the verified manifest")
    if Path(args.lifecycle_state).expanduser().absolute() != Path(
        verified["manifest"]["lifecycle_state_path"]
    ):
        raise RunnerError("correction lifecycle state path differs from the verified manifest")
    values = verified["values"]
    implementation_risk = implementation_classification(values, "implementation_risk")
    implementation_ambiguity = implementation_classification(values, "implementation_ambiguity")
    selected_plan_model, selected_plan_reasoning = select_plan_writable_profile(values)
    brief_path = Path(args.correction_brief).expanduser()
    if not brief_path.is_absolute():
        brief_path = (Path.cwd() / brief_path).absolute()
    if path_is_within(repo_root, brief_path):
        raise RunnerError("correction brief must be outside the source repository")
    brief = read_bounded_regular_file(brief_path, CORRECTION_BRIEF_MAX_BYTES, "correction brief")
    if not brief.strip():
        raise RunnerError("correction brief must be nonblank")
    brief_digest = hashlib.sha256(brief).hexdigest()
    lineage = next_correction_lineage(
        verified["manifest"],
        prior_manifest_digest=verified["manifest_digest"],
        prior_patch_digest=verified["patch_digest"],
        correction_brief_digest=brief_digest,
    )
    output_dir = materialize_output_dir(repo_root, args.output_dir)
    reserved_artifacts = reserve_output_artifacts(output_dir)
    if args.availability_state is not None and args.orchestration_run_id is None:
        raise RunnerError("availability state requires an orchestration run identifier")
    hidden_prior = {
        prior_manifest_path.parent.resolve(),
        verified["patch_path"].parent.resolve(),
        brief_path.parent.resolve(),
    }
    with open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    ) as lifecycle_state:
        lifecycle = lifecycle_state.require_existing()
        if lifecycle["current_manifest_digest"] != verified["manifest_digest"] or lifecycle[
            "current_patch_digest"
        ] != verified["patch_digest"] or lifecycle["plan_execution_attempt_id"] != verified[
            "manifest"
        ]["plan_execution_attempt_id"]:
            raise RunnerError("correction prior manifest is not the current lifecycle leaf")
        if lifecycle["phase"] not in {"admitted", "focused_passed"}:
            raise RunnerError("correction is not allowed after validation failure or final acceptance")
        if lifecycle["correction_round"] != lineage["correction_round"] - 1:
            raise RunnerError("correction lineage does not match the run-bound lifecycle round")
    begin_plan_execution_attempt(
        args,
        attempt_kind="correction",
        prior_candidate_digest="sha256:" + verified["manifest_digest"],
    )
    state_context = (
        open_availability_state(repo_root, args.availability_state, args.orchestration_run_id)
        if args.availability_state is not None and args.orchestration_run_id is not None
        else nullcontext(None)
    )
    lifecycle_context = open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    )
    with plan_execution_lease(args), lifecycle_context as lifecycle_state, state_context as availability_state, tempfile.TemporaryDirectory(
        prefix="sandboxed-plan-worker-correction-workspace-"
    ) as workspace_tmp:
        enforce_plan_execution_gate(
            args, plan=verified["plan_rel"], open_attempt_id=args.execution_attempt_id
        )
        bwrap_bin = require_executable("bwrap", args.bwrap_bin)
        ensure_bwrap_usable(bwrap_bin)
        lifecycle = lifecycle_state.require_existing()
        if lifecycle["current_manifest_digest"] != verified["manifest_digest"] or lifecycle[
            "current_patch_digest"
        ] != verified["patch_digest"] or lifecycle["plan_execution_attempt_id"] != verified[
            "manifest"
        ]["plan_execution_attempt_id"]:
            raise RunnerError("correction prior manifest is not the current lifecycle leaf")
        if lifecycle["phase"] not in {"admitted", "focused_passed"}:
            raise RunnerError("correction is not allowed after validation failure or final acceptance")
        if lifecycle["correction_round"] != lineage["correction_round"] - 1:
            raise RunnerError("correction lineage does not match the run-bound lifecycle round")
        workspace = Path(workspace_tmp)
        attempts: list[dict[str, Any]] = []
        fallback_reason: str | None = None
        availability_failures = 0
        skipped_known_unavailable_starts = 0
        common = {
            "workspace": workspace,
            "repo_root": repo_root,
            "head": verified["head"],
            "plan_rel": verified["plan_rel"],
            "plan_digest": verified["plan_digest"],
            "values": values,
            "run_id": args.orchestration_run_id,
            "plan_execution_attempt_id": args.execution_attempt_id,
            "normalized_scope": verified["normalized_scope"],
            "bwrap_bin": bwrap_bin,
            "git_bin": git_bin,
            "reserved_artifacts": reserved_artifacts,
            "extra_env": args.worker_env,
            "prior_patch": verified["patch_bytes"],
            "correction_brief": brief,
        }
        if args.worker_binary is not None:
            worker_binary = require_executable("worker", args.worker_binary)
            selected = execute_isolated_attempt(
                **common,
                label="custom",
                attempt_lineage={"attempt_kind": "correction", **lineage, "attempt_label": "custom"},
                hidden_directories=tuple({output_dir.resolve(), *hidden_prior}),
                custom_command=[worker_binary, *args.worker_arg],
            )
            worker_kind = "custom"
            if selected["result"].returncode != 0:
                raise RunnerError(
                    f"correction worker exited with {selected['result'].returncode}; stdout/stderr saved under {output_dir}"
                )
        else:
            codex_bin = require_executable("codex", args.codex_bin)
            primary_model = require_writable_model(
                args.codex_model if args.codex_model is not None else selected_plan_model,
                "preferred",
            )
            primary_reasoning = require_reasoning_effort(
                args.codex_reasoning_effort
                if args.codex_reasoning_effort is not None
                else selected_plan_reasoning,
                "preferred",
            )
            fallback_model = require_writable_model(args.fallback_codex_model, "fallback")
            fallback_reasoning = require_reasoning_effort(
                args.fallback_codex_reasoning_effort, "fallback"
            )
            worker_kind = "codex"
            primary: dict[str, Any] | None = None
            known_primary = availability_state.reason_for(primary_model) if availability_state else None
            if known_primary is not None:
                skipped_known_unavailable_starts += 1
                fallback_reason = known_primary
            else:
                primary = execute_isolated_attempt(
                    **common,
                    label="primary",
                    attempt_lineage={"attempt_kind": "correction", **lineage, "attempt_label": "primary"},
                    hidden_directories=tuple({output_dir.resolve(), host_codex_home_path(), *hidden_prior}),
                    codex_bin=codex_bin,
                    model=primary_model,
                    reasoning=primary_reasoning,
                )
                attempts.append(primary["record"])
                if primary["result"].returncode == 0:
                    selected = primary
                else:
                    fallback_reason = classify_codex_unavailability(
                        primary["result"].stdout, primary["result"].stderr
                    )
                    if fallback_reason is None:
                        raise RunnerError(
                            f"correction worker exited with {primary['result'].returncode}; stdout/stderr saved under {output_dir}"
                        )
                    availability_failures += 1
                    if availability_state:
                        availability_state.record(primary_model, fallback_reason)
            if primary is None or primary["result"].returncode != 0:
                if args.no_model_fallback:
                    raise RunnerError("preferred correction model is unavailable and fallback is disabled")
                if availability_state and availability_state.reason_for(fallback_model) is not None:
                    skipped_known_unavailable_starts += 1
                    raise RunnerError("fallback correction model is already recorded unavailable for this run")
                fallback = execute_isolated_attempt(
                    **common,
                    label="fallback",
                    attempt_lineage={"attempt_kind": "correction", **lineage, "attempt_label": "fallback"},
                    hidden_directories=tuple(
                        {
                            output_dir.resolve(),
                            host_codex_home_path(),
                            *hidden_prior,
                            *([primary["attempt_root"]] if primary is not None else []),
                        }
                    ),
                    codex_bin=codex_bin,
                    model=fallback_model,
                    reasoning=fallback_reasoning,
                )
                attempts.append(fallback["record"])
                if fallback["result"].returncode != 0:
                    reason = classify_codex_unavailability(
                        fallback["result"].stdout, fallback["result"].stderr
                    )
                    if reason is not None:
                        availability_failures += 1
                        if availability_state:
                            availability_state.record(fallback_model, reason)
                    raise RunnerError(
                        f"fallback correction worker exited with {fallback['result'].returncode}; stdout/stderr saved under {output_dir}"
                    )
                selected = fallback
        if selected["completion_claims_error"] is not None:
            raise RunnerError(
                "correction completion claims were rejected; process diagnostics and a safe failure "
                f"receipt were saved under {output_dir}"
            )
        worker_result = select_attempt_artifacts(selected, reserved_artifacts)
        contract_path = reserved_artifacts["worker-contract.json"]
        contract_path.write_bytes(selected["contract_bytes"])
        contract_digest = hash_file(contract_path)
        worker_result["kind"] = worker_kind
        if attempts:
            worker_result["attempts"] = attempts
            worker_result["selected_attempt"] = selected["record"]["label"]
        if fallback_reason is not None:
            worker_result["fallback_reason"] = fallback_reason
        materialize_writable_shadows(
            selected["shadows"], selected["scratch_dir"] / "writable-shadows"
        )
        patch_bytes, clone_head_after_worker, refs_after_worker = collect_candidate_patch_in_sandbox(
            bwrap_bin=bwrap_bin,
            git_bin=git_bin,
            clone_dir=selected["clone_dir"],
            scratch_dir=selected["scratch_dir"],
            env_vars=selected["env_vars"],
        )
        if clone_head_after_worker != verified["head"]:
            raise RunnerError("correction worker changed clone HEAD")
        if refs_after_worker != selected["initial_refs"]:
            raise RunnerError("correction worker changed clone refs")
        if not patch_bytes:
            raise RunnerError("correction produced no aggregate candidate changes")
        patch_digest = hashlib.sha256(patch_bytes).hexdigest()
        changed_paths = normalize_changed_paths(
            derive_changed_paths_from_patch(repo_root, git_bin, patch_bytes, verified["head"]),
            repo_root,
        )
        if not changed_paths:
            raise RunnerError("correction produced no aggregate candidate changes")
        disallowed = [
            path
            for path in changed_paths
            if not scope_allows_path(verified["normalized_scope"], path)
        ]
        if disallowed:
            raise RunnerError(f"correction changed paths outside write_scope: {', '.join(disallowed)}")
        for path in changed_paths:
            ensure_no_symlink_path_trick(repo_root, path)
        run_subprocess(
            (git_bin, "apply", "--check", "--binary", "-"), cwd=repo_root, stdin=patch_bytes
        )
        ensure_clean_worktree(repo_root, git_bin)
        if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
            raise RunnerError("source HEAD changed during correction admission")
        receipt_candidate = {
            "patch_digest": "sha256:" + patch_digest,
            "changed_paths": sorted(changed_paths),
        }
        completion_receipt = write_attempt_completion_receipt(
            selected,
            reserved_artifacts=reserved_artifacts,
            candidate=receipt_candidate,
            final=True,
        )
        patch_path = reserved_artifacts["candidate.patch"]
        if write_bytes(patch_path, patch_bytes) != patch_digest:
            raise RunnerError("correction patch changed while it was published")
        if completion_receipt["claims"]["attempt_result"] != "success":
            raise RunnerError(
                "correction completion receipt reports failure; candidate was not admitted"
            )
        completion_receipt_path = selected["completion_receipt_path"]
        completion_receipt_digest = selected["completion_receipt_digest"]
        process_result_path = selected["process_result_path"]
        process_result_digest = selected["process_result_digest"]
        telemetry_attempts = attempts if worker_kind == "codex" else [selected["record"]]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "source_head": verified["head"],
            "plan_path": verified["plan_rel"],
            "plan_digest": verified["plan_digest"],
            "worker_contract_path": str(contract_path),
            "worker_contract_digest": contract_digest,
            "worker_completion_receipt_path": str(completion_receipt_path),
            "worker_completion_receipt_digest": completion_receipt_digest.removeprefix("sha256:"),
            "worker_process_result_path": str(process_result_path),
            "worker_process_result_digest": process_result_digest.removeprefix("sha256:"),
            "worker_attempt_label": selected["record"]["label"],
            "worker_attempt_id": selected["attempt_id"],
            "allowed_write_scope": verified["normalized_scope"],
            "changed_paths": changed_paths,
            "patch_path": str(patch_path),
            "patch_digest": patch_digest,
            "orchestration_run_id": args.orchestration_run_id,
            "plan_execution_attempt_id": args.execution_attempt_id,
            "lifecycle_state_path": str(Path(args.lifecycle_state).expanduser().absolute()),
            "correction_lineage": lineage,
            "worker_result": worker_result,
            "telemetry": {
                "schema_version": TELEMETRY_SCHEMA_VERSION,
                "attempt_durations_seconds": [
                    bounded_duration(0.0, float(attempt["duration_seconds"]))
                    for attempt in telemetry_attempts
                ],
                "runner_duration_seconds": bounded_duration(runner_started, time.monotonic()),
                "model_starts": len(attempts) if worker_kind == "codex" else 0,
                "availability_failures": availability_failures,
                "skipped_known_unavailable_starts": skipped_known_unavailable_starts,
                "candidate_generations": lineage["correction_round"] + 1,
                "full_validation_count": 0,
                "authoritative_validation_count": 0,
                "focused_validation_count": 0,
                "parent_review_rejections": lineage["correction_round"],
                "correction_round": lineage["correction_round"],
                "implementation_risk": implementation_risk,
                "implementation_ambiguity": implementation_ambiguity,
            },
        }
        manifest_path = reserved_artifacts["manifest.json"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        focused_raw = values.get("focused_validation", [])
        lifecycle_state.persist(
            {
                **lifecycle,
                "plan_execution_attempt_id": args.execution_attempt_id,
                "current_manifest_digest": hash_file(manifest_path),
                "current_patch_digest": patch_digest,
                "correction_round": lineage["correction_round"],
                "candidate_generations": lineage["correction_round"] + 1,
                "phase": "admitted",
                "focused_required": isinstance(focused_raw, list) and bool(focused_raw),
                "focused_validation_count": 0,
                "authoritative_validation_count": 0,
                "parent_review_rejections": lineage["correction_round"],
            }
        )
    print(str(manifest_path))
    return 0


def apply_worker_result(args: argparse.Namespace) -> int:
    git_bin = require_executable("git", args.git_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    manifest_path = Path(args.manifest).expanduser().resolve()
    verified = verify_candidate_manifest(
        repo_root=repo_root,
        git_bin=git_bin,
        planlib=planlib,
        manifest_path=manifest_path,
    )
    require_plan_worktree(repo_root, verified["plan_rel"], "applying a sandboxed worker candidate")
    enforce_plan_execution_gate(
        args,
        plan=verified["plan_rel"],
        open_attempt_id=verified["manifest"]["plan_execution_attempt_id"],
    )
    if args.orchestration_run_id != verified["manifest"]["orchestration_run_id"]:
        raise RunnerError("apply run identifier differs from the verified manifest")
    if Path(args.lifecycle_state).expanduser().absolute() != Path(
        verified["manifest"]["lifecycle_state_path"]
    ):
        raise RunnerError("apply lifecycle state path differs from the verified manifest")
    lifecycle_context = open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    )
    with lifecycle_context as lifecycle_state:
        lifecycle = lifecycle_state.require_existing()
        if lifecycle["current_manifest_digest"] != verified["manifest_digest"] or lifecycle[
            "current_patch_digest"
        ] != verified["patch_digest"] or lifecycle["plan_execution_attempt_id"] != verified[
            "manifest"
        ]["plan_execution_attempt_id"]:
            raise RunnerError("apply manifest is not the current lifecycle leaf")
        if lifecycle["phase"] != "authoritative_passed" or lifecycle[
            "authoritative_validation_count"
        ] != 1:
            raise RunnerError("apply requires exactly one successful authoritative validation")
        ensure_clean_worktree(repo_root, git_bin)
        if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
            raise RunnerError("source HEAD changed after candidate preflight and before apply")
        lifecycle_state.persist({**lifecycle, "phase": "applying"})
        run_subprocess(
            (git_bin, "apply", "--binary", "-"), cwd=repo_root, stdin=verified["patch_bytes"]
        )
        try:
            lifecycle_state.persist({**lifecycle, "phase": "applied"})
        except BaseException as exc:
            raise RunnerError(
                "source patch was applied but lifecycle finalization failed; reconcile the applying state before retry"
            ) from exc
    print(str(verified["patch_path"]))
    return 0


def finalize_apply(args: argparse.Namespace) -> int:
    git_bin = require_executable("git", args.git_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    manifest_path = Path(args.manifest).expanduser().resolve()
    verified = verify_candidate_manifest(
        repo_root=repo_root,
        git_bin=git_bin,
        planlib=load_planlib(),
        manifest_path=manifest_path,
        require_applicable=False,
        require_clean=False,
        allow_applied_symlink_targets=True,
    )
    require_plan_worktree(repo_root, verified["plan_rel"], "finalizing a sandboxed worker apply")
    enforce_plan_execution_gate(
        args,
        plan=verified["plan_rel"],
        open_attempt_id=verified["manifest"]["plan_execution_attempt_id"],
    )
    if args.orchestration_run_id != verified["manifest"]["orchestration_run_id"]:
        raise RunnerError("finalize-apply run identifier differs from the verified manifest")
    if Path(args.lifecycle_state).expanduser().absolute() != Path(
        verified["manifest"]["lifecycle_state_path"]
    ):
        raise RunnerError("finalize-apply lifecycle state path differs from the verified manifest")
    with open_lifecycle_state(
        repo_root, args.lifecycle_state, args.orchestration_run_id
    ) as lifecycle_state:
        lifecycle = lifecycle_state.require_existing()
        if lifecycle["phase"] != "applying":
            raise RunnerError("finalize-apply requires an applying lifecycle state")
        if lifecycle["current_manifest_digest"] != verified["manifest_digest"] or lifecycle[
            "current_patch_digest"
        ] != verified["patch_digest"] or lifecycle["plan_execution_attempt_id"] != verified[
            "manifest"
        ]["plan_execution_attempt_id"]:
            raise RunnerError("finalize-apply manifest is not the current lifecycle leaf")
        if collect_worktree_patch(repo_root, git_bin, verified["head"]) != verified["patch_bytes"]:
            raise RunnerError("source worktree does not exactly match the verified applied patch")
        lifecycle_state.persist({**lifecycle, "phase": "applied"})
    print(str(verified["patch_path"]))
    return 0


def write_self_test_worker(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            from __future__ import annotations

            import hashlib
            import json
            import os
            from pathlib import Path


            prefix = "{ENV_PREFIX}"
            worker_repo = Path(os.environ[prefix + "WORKER_REPO"])
            source_repo = Path(os.environ[prefix + "SOURCE_REPO"])
            scratch_dir = Path(os.environ[prefix + "SCRATCH_DIR"])
            new_file_root = Path(os.environ[prefix + "NEW_FILE_ROOT"])
            outside_probe = Path(os.environ[prefix + "OUTSIDE_PROBE"])

            (worker_repo / "allowed.txt").write_text("changed in clone\\n", encoding="utf-8")
            new_target = new_file_root / "dir" / "new.txt"
            new_target.parent.mkdir(parents=True, exist_ok=True)
            new_target.write_text("new file\\n", encoding="utf-8")
            (scratch_dir / "scratch-ok.txt").write_text("scratch ok\\n", encoding="utf-8")

            denied = []
            for target, label in (
                (source_repo / "blocked.txt", "source"),
                (outside_probe, "outside"),
            ):
                try:
                    target.write_text("blocked\\n", encoding="utf-8")
                except OSError:
                    denied.append(label)
                else:
                    raise SystemExit(f"unexpected write success: {{label}}")
            if denied != ["source", "outside"]:
                raise SystemExit(f"unexpected denied set: {{denied}}")

            contract = json.loads(
                Path(os.environ[prefix + "WORKER_CONTRACT"]).read_text(encoding="utf-8")
            )
            acceptance_evidence = [
                {{
                    "acceptance_digest": "sha256:"
                    + hashlib.sha256(item.encode()).hexdigest(),
                    "claim": "satisfied",
                }}
                for item in contract["acceptance"]
            ]
            Path(os.environ[prefix + "COMPLETION_CLAIMS"]).write_text(
                json.dumps(
                    {{
                        "attempt_result": "success",
                        "acceptance_evidence": acceptance_evidence,
                        "commands_attempted": [],
                        "blockers": [],
                        "residual_risks": [],
                        "out_of_scope_change": False,
                    }},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\\n",
                encoding="utf-8",
            )
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def init_self_test_repo(repo_root: Path, git_bin: str) -> str:
    run_subprocess((git_bin, "init", "-q", "-b", "main"), cwd=repo_root)
    run_subprocess((git_bin, "config", "user.email", "self-test@example.invalid"), cwd=repo_root)
    run_subprocess((git_bin, "config", "user.name", "Self Test"), cwd=repo_root)
    run_subprocess(
        (git_bin, "remote", "add", "origin", "https://example.invalid/self-test.git"),
        cwd=repo_root,
    )
    (repo_root / "AGENTS.md").write_text("sandboxed worker self-test\n", encoding="utf-8")
    (repo_root / "docs/plan/active").mkdir(parents=True, exist_ok=True)
    (repo_root / "docs/agent").mkdir(parents=True, exist_ok=True)
    (repo_root / "docs/agent/SPEC_USER_COMMUNICATION.md").write_text("self-test\n", encoding="utf-8")
    (repo_root / "docs/agent/SPEC_PLAN_WORKFLOW.md").write_text("self-test\n", encoding="utf-8")
    (repo_root / "docs/plan/plan.md").write_text(
        "# Active Plan\n\nid\tpath\tstatus\n001\tdocs/plan/active/001-self-test.md\tin_progress\n",
        encoding="utf-8",
    )
    (repo_root / "allowed.txt").write_text("original\n", encoding="utf-8")
    (repo_root / "dir").mkdir()
    (repo_root / "dir/existing.txt").write_text("keep parent\n", encoding="utf-8")
    plan = repo_root / "docs/plan/active/001-self-test.md"
    plan.write_text(
        textwrap.dedent(
            """\
            # Self test

            status: in_progress
            task_types:
              - template_workflow
            review_class: B
            human_design_required: no
            human_approval_status: not_required
            implementation_risk: low
            implementation_ambiguity: low
            primary_invariant: self-test changes remain inside explicit file paths
            write_scope:
              - allowed.txt
              - dir/new.txt
            context_files:
              - docs/agent/SPEC_USER_COMMUNICATION.md
            required_specs:
              - docs/agent/SPEC_PLAN_WORKFLOW.md
            validation:
              - git diff --check
            acceptance:
              - Self-test patch applies cleanly.
            checked_summary_ja: self-test

            ## Tasks

            - [ ] Self test.
            """
        ),
        encoding="utf-8",
    )
    run_subprocess((git_bin, "add", "."), cwd=repo_root)
    run_subprocess((git_bin, "commit", "-qm", "baseline"), cwd=repo_root)
    return "docs/plan/active/001-self-test.md"


def run_self_test(args: argparse.Namespace) -> int:
    git_bin = require_executable("git", args.git_bin)
    ensure_bwrap_usable(require_executable("bwrap", args.bwrap_bin))
    try:
        normalize_repo_relpath("../bad", label="self-test invalid path")
    except RunnerError:
        pass
    else:
        raise RunnerError("self-test accepted dot-dot traversal")
    with tempfile.TemporaryDirectory(prefix="sandboxed-plan-worker-self-test-") as tmp:
        repo_root = Path(tmp) / "repo"
        repo_root.mkdir()
        plan_rel = init_self_test_repo(repo_root, git_bin)
        outside_probe = Path(tmp) / "outside.txt"
        worker = Path(tmp) / "worker.py"
        write_self_test_worker(worker)
        output_dir = Path(tmp) / "output"
        lifecycle_path = Path(tmp) / "lifecycle.json"
        execution_state_path = Path(tmp) / "plan-execution.json"
        run_id = "self-test-run"
        original_cwd = Path.cwd()
        try:
            os.chdir(repo_root)
            plan_digest = "sha256:" + hashlib.sha256((repo_root / plan_rel).read_bytes()).hexdigest()
            source_head = git_text(repo_root, git_bin, "rev-parse", "HEAD")
            run_subprocess(
                (
                    sys.executable,
                    str(Path(__file__).with_name("plan-execution-state.py")),
                    "init",
                    str(execution_state_path),
                    "--run-id",
                    run_id,
                    "--plan",
                    plan_rel,
                    "--plan-digest",
                    plan_digest,
                    "--source-head",
                    source_head,
                    "--primary-invariant-digest",
                    "sha256:" + hashlib.sha256(
                        b"self-test changes remain inside explicit file paths"
                    ).hexdigest(),
                    "--lifecycle-state",
                    str(lifecycle_path),
                    "--implementation-mode",
                    "candidate",
                ),
                cwd=repo_root,
            )
            run_worker(
                argparse.Namespace(
                    git_bin=git_bin,
                    bwrap_bin=args.bwrap_bin,
                    codex_bin=args.codex_bin,
                    codex_model=None,
                    codex_reasoning_effort=None,
                    fallback_codex_model=DEFAULT_FALLBACK_CODEX_MODEL,
                    fallback_codex_reasoning_effort=DEFAULT_FALLBACK_CODEX_REASONING,
                    no_model_fallback=False,
                    availability_state=None,
                    orchestration_run_id=run_id,
                    lifecycle_state=str(lifecycle_path),
                    plan_execution_state=str(execution_state_path),
                    output_dir=str(output_dir),
                    plan=plan_rel,
                    worker_binary=str(require_executable("python3", sys.executable)),
                    worker_arg=[str(worker)],
                    worker_env=[f"{ENV_PREFIX}OUTSIDE_PROBE={outside_probe}"],
                )
            )
            manifest_path = output_dir / "manifest.json"
            if not manifest_path.is_file():
                raise RunnerError("self-test did not produce a manifest")
            if (repo_root / "allowed.txt").read_text(encoding="utf-8") != "original\n":
                raise RunnerError("self-test mutated the source repository before apply")
            validate_candidate(
                argparse.Namespace(
                    git_bin=git_bin,
                    bwrap_bin=args.bwrap_bin,
                    manifest=str(manifest_path),
                    suite="authoritative",
                    parent_diff_approved=True,
                    critical_invariants_approved=True,
                    output_dir=str(Path(tmp) / "validation-output"),
                    orchestration_run_id=run_id,
                    lifecycle_state=str(lifecycle_path),
                    plan_execution_state=str(execution_state_path),
                )
            )
            apply_worker_result(
                argparse.Namespace(
                    git_bin=git_bin,
                    manifest=str(manifest_path),
                    orchestration_run_id=run_id,
                    lifecycle_state=str(lifecycle_path),
                    plan_execution_state=str(execution_state_path),
                )
            )
            if (repo_root / "allowed.txt").read_text(encoding="utf-8") != "changed in clone\n":
                raise RunnerError("self-test apply did not update the source repository")
            if (repo_root / "dir/new.txt").read_text(encoding="utf-8") != "new file\n":
                raise RunnerError("self-test apply did not create the declared new file")
        finally:
            os.chdir(original_cwd)
    print("sandboxed plan worker self-test passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Commands:
              prepare-dependencies copy a lock-matched npm tree outside the repository
              run      execute a writable worker inside Bubblewrap and emit a candidate patch manifest
              correct  repair a verified candidate in a fresh isolated clone and emit an aggregate patch
              validate run a parent-authorized suite in a fresh review clone after candidate admission
              preflight run one bounded diagnostic command against an admitted candidate; never validation
              apply    re-check and apply a previously emitted candidate patch manifest
              self-test run a deterministic local end-to-end check without contacting Codex
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dependency_parser = subparsers.add_parser(
        "prepare-dependencies",
        help="copy a lock-matched npm dependency snapshot outside the repository",
    )
    dependency_parser.add_argument("--output-dir", required=True)
    dependency_parser.add_argument("--git-bin", default="git")
    dependency_parser.add_argument(
        "--playwright-browser-dir",
        action="append",
        default=[],
        help="copy one allowlisted Playwright browser directory into the digested snapshot",
    )
    dependency_parser.set_defaults(handler=prepare_dependency_snapshot)

    run_parser = subparsers.add_parser("run", help="run a sandboxed worker against one active plan")
    run_parser.add_argument("plan", help="repository-relative active plan path")
    run_parser.add_argument(
        "--group-permit",
        default=None,
        help="exclusive execution group member permit issued by the group authority",
    )
    run_parser.add_argument(
        "--group-state",
        default=None,
        help="parent-owned group execution state record that binds the member permit",
    )
    run_parser.add_argument("--output-dir", help="directory outside the source repository for patch artifacts")
    run_parser.add_argument("--git-bin", default="git", help="git executable to use")
    run_parser.add_argument("--bwrap-bin", default="bwrap", help="Bubblewrap executable to use")
    run_parser.add_argument("--codex-bin", default="codex", help="Codex executable to use for the default worker")
    run_parser.add_argument(
        "--codex-model", default=None, help="preferred Codex model override for the default worker"
    )
    run_parser.add_argument(
        "--codex-reasoning-effort",
        default=None,
        help="preferred Codex reasoning effort override for the default worker",
    )
    run_parser.add_argument(
        "--fallback-codex-model",
        default=DEFAULT_FALLBACK_CODEX_MODEL,
        help="Codex model used once when the preferred model is unavailable",
    )
    run_parser.add_argument(
        "--fallback-codex-reasoning-effort",
        default=DEFAULT_FALLBACK_CODEX_REASONING,
        help="reasoning effort for the fallback Codex model",
    )
    run_parser.add_argument(
        "--no-model-fallback",
        action="store_true",
        help="disable automatic fallback when the preferred Codex model is unavailable",
    )
    run_parser.add_argument(
        "--availability-state",
        help="ephemeral availability-state JSON path outside the source repository",
    )
    run_parser.add_argument(
        "--orchestration-run-id",
        required=True,
        help="nonblank identifier that binds lifecycle and availability state to one run",
    )
    run_parser.add_argument("--lifecycle-state", required=True)
    run_parser.add_argument("--plan-execution-state", required=True)
    run_parser.add_argument(
        "--predecessor-plan-execution-state",
        help="accepted predecessor execution ledger bound into this dependent plan run",
    )
    run_parser.add_argument(
        "--predecessor-session-checkpoint",
        help="verified terminal checkpoint emitted by the accepted predecessor root session",
    )
    run_parser.add_argument(
        "--root-session-manifest",
        help="run manifest containing the directly observed root-session identity",
    )
    run_parser.add_argument(
        "--reviewer-registry",
        help="external append-only reviewer session registry bound to checkpoint claims",
    )
    run_parser.add_argument("--worker-binary", help="override the default Codex worker with a custom executable")
    run_parser.add_argument("--worker-arg", action="append", default=[], help="append one argument for --worker-binary")
    run_parser.add_argument(
        "--worker-env",
        action="append",
        default=[],
        help="set one extra KEY=VALUE environment pair inside the sandbox",
    )
    run_parser.set_defaults(handler=run_worker)

    correction_parser = subparsers.add_parser(
        "correct", help="correct a verified candidate in a fresh isolated clone"
    )
    correction_parser.add_argument("plan", help="repository-relative active plan path")
    correction_parser.add_argument(
        "--group-permit",
        default=None,
        help="exclusive execution group member permit issued by the group authority",
    )
    correction_parser.add_argument(
        "--group-state",
        default=None,
        help="parent-owned group execution state record that binds the member permit",
    )
    correction_parser.add_argument("prior_manifest", help="prior candidate manifest rejected by parent review")
    correction_parser.add_argument("correction_brief", help="bounded parent-authored correction brief outside the repository")
    correction_parser.add_argument("--output-dir", help="directory outside the source repository for patch artifacts")
    correction_parser.add_argument("--git-bin", default="git", help="git executable to use")
    correction_parser.add_argument("--bwrap-bin", default="bwrap", help="Bubblewrap executable to use")
    correction_parser.add_argument("--codex-bin", default="codex", help="Codex executable for the default worker")
    correction_parser.add_argument("--codex-model", default=None, help="preferred Codex model override")
    correction_parser.add_argument("--codex-reasoning-effort", default=None, help="preferred reasoning override")
    correction_parser.add_argument("--fallback-codex-model", default=DEFAULT_FALLBACK_CODEX_MODEL)
    correction_parser.add_argument(
        "--fallback-codex-reasoning-effort", default=DEFAULT_FALLBACK_CODEX_REASONING
    )
    correction_parser.add_argument("--no-model-fallback", action="store_true")
    correction_parser.add_argument("--availability-state")
    correction_parser.add_argument("--orchestration-run-id", required=True)
    correction_parser.add_argument("--lifecycle-state", required=True)
    correction_parser.add_argument("--plan-execution-state", required=True)
    correction_parser.add_argument("--worker-binary")
    correction_parser.add_argument("--worker-arg", action="append", default=[])
    correction_parser.add_argument("--worker-env", action="append", default=[])
    correction_parser.set_defaults(handler=correct_worker)

    validation_parser = subparsers.add_parser(
        "validate", help="run parent-authorized validation in a fresh review clone"
    )
    validation_parser.add_argument("manifest", help="verified candidate manifest")
    validation_parser.add_argument("--suite", choices=("focused", "authoritative"), required=True)
    validation_parser.add_argument("--parent-diff-approved", action="store_true")
    validation_parser.add_argument("--critical-invariants-approved", action="store_true")
    validation_parser.add_argument("--output-dir", required=True)
    validation_parser.add_argument("--orchestration-run-id", required=True)
    validation_parser.add_argument("--lifecycle-state", required=True)
    validation_parser.add_argument("--plan-execution-state", required=True)
    validation_parser.add_argument("--git-bin", default="git")
    validation_parser.add_argument("--bwrap-bin", default="bwrap")
    validation_parser.add_argument(
        "--dependency-snapshot",
        help="manifest from prepare-dependencies for lock-bound npm validation",
    )
    validation_parser.set_defaults(handler=validate_candidate)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="run one bounded parent-owned diagnostic command against an admitted candidate",
    )
    preflight_parser.add_argument("manifest", help="verified candidate manifest")
    preflight_parser.add_argument(
        "--command-index",
        type=int,
        required=True,
        help="zero-based index of the plan's declared focused_validation command to run",
    )
    preflight_parser.add_argument("--parent-diff-approved", action="store_true")
    preflight_parser.add_argument("--critical-invariants-approved", action="store_true")
    preflight_parser.add_argument("--output-dir", required=True)
    preflight_parser.add_argument(
        "--preflight-claim-dir",
        required=True,
        help="parent-owned claim directory outside the repository",
    )
    preflight_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=PREFLIGHT_DEFAULT_TIMEOUT_SECONDS,
        help=f"hard time bound, at most {PREFLIGHT_MAXIMUM_TIMEOUT_SECONDS} seconds",
    )
    preflight_parser.add_argument("--orchestration-run-id", required=True)
    preflight_parser.add_argument("--lifecycle-state", required=True)
    preflight_parser.add_argument("--plan-execution-state", required=True)
    preflight_parser.add_argument("--git-bin", default="git")
    preflight_parser.add_argument("--bwrap-bin", default="bwrap")
    preflight_parser.set_defaults(handler=preflight_candidate)

    apply_parser = subparsers.add_parser("apply", help="apply a previously emitted candidate patch manifest")
    apply_parser.add_argument("manifest", help="path to manifest.json emitted by the run command")
    apply_parser.add_argument("--orchestration-run-id", required=True)
    apply_parser.add_argument("--lifecycle-state", required=True)
    apply_parser.add_argument("--plan-execution-state", required=True)
    apply_parser.add_argument("--git-bin", default="git", help="git executable to use")
    apply_parser.set_defaults(handler=apply_worker_result)

    finalize_parser = subparsers.add_parser(
        "finalize-apply", help="reconcile an applied source patch after lifecycle finalization failure"
    )
    finalize_parser.add_argument("manifest")
    finalize_parser.add_argument("--orchestration-run-id", required=True)
    finalize_parser.add_argument("--lifecycle-state", required=True)
    finalize_parser.add_argument("--plan-execution-state", required=True)
    finalize_parser.add_argument("--git-bin", default="git")
    finalize_parser.set_defaults(handler=finalize_apply)

    self_test = subparsers.add_parser("self-test", help="run a deterministic local self-test")
    self_test.add_argument("--git-bin", default="git", help="git executable to use")
    self_test.add_argument("--bwrap-bin", default="bwrap", help="Bubblewrap executable to use")
    self_test.add_argument("--codex-bin", default="codex", help="Codex executable name for prerequisite checks")
    self_test.set_defaults(handler=run_self_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {"run", "correct"}:
            enforce_parallel_group_gate(
                args.plan,
                "run" if args.command == "run" else "correct",
                group_permit=getattr(args, "group_permit", None),
                group_state=getattr(args, "group_state", None),
            )
            enforce_plan_execution_gate(args, plan=args.plan)
            return int(args.handler(args))
        with plan_execution_lease(args):
            if args.command not in {"self-test", "prepare-dependencies"}:
                if args.command not in {"run", "correct"}:
                    enforce_plan_execution_gate(args)
            return int(args.handler(args))
    except RunnerError as exc:
        fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
