#!/usr/bin/env python3
"""Run or apply a Bubblewrap-isolated plan worker patch."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Sequence


SCHEMA_VERSION = 1
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
CORRECTION_BRIEF_MAX_BYTES = 8192
MAX_CORRECTION_ROUNDS = 2
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
    "manifest.json",
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
    ) -> None:
        self.parent_fd = parent_fd
        self.target_name = target_name
        self.run_id = run_id
        self.unavailable = unavailable
        self.target_identity = target_identity

    def close(self) -> None:
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


def fail(message: str) -> None:
    print(f"sandboxed plan worker failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(SHA256_BUFFER):
            digest.update(chunk)
    return digest.hexdigest()


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


def ensure_no_symlink_path_trick(repo_root: Path, relative_path: str) -> None:
    current = repo_root
    for part in PurePosixPath(relative_path).parts:
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
            continue
        normalized.append(value)
        seen.add(value)
    collapsed: list[str] = []
    for entry in normalized:
        if any(parent.endswith("/") and entry.startswith(parent) for parent in normalized if parent != entry):
            continue
        collapsed.append(entry)
    return collapsed


def scope_allows_path(scope_entries: Sequence[str], relative_path: str) -> bool:
    for entry in scope_entries:
        if entry.endswith("/"):
            if relative_path.startswith(entry):
                return True
        elif relative_path == entry:
            return True
    return False


def load_plan(planlib: ModuleType, repo_root: Path, plan_arg: str) -> tuple[Path, str, dict[str, str | list[str]], list[str]]:
    plan_rel = normalize_manifest_path(repo_root, plan_arg)
    if not PLAN_PATTERN.fullmatch(plan_rel):
        raise RunnerError("run requires a numbered in-progress active plan under docs/plan/active/")
    plan_path = repo_root / plan_rel
    if not plan_path.is_file():
        raise RunnerError(f"missing active plan: {plan_rel}")
    values = planlib.require_manifest_fields(plan_path)
    status = planlib.manifest_scalar(values, "status")
    if status != "in_progress":
        raise RunnerError(f"plan must be in_progress: {plan_rel}")
    plan_id = plan_path.name[:3]
    planlib.check_active_mapping(plan_id, plan_rel, "in_progress")
    write_scope = values.get("write_scope", [])
    if not isinstance(write_scope, list):
        raise RunnerError(f"plan write_scope must be a list: {plan_rel}")
    normalized_scope = parse_write_scope(write_scope)
    return plan_path, plan_rel, values, normalized_scope


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
        )
        descriptor = -1
        return handle
    finally:
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


def build_worker_prompt(plan_rel: str, plan_digest: str) -> str:
    return textwrap.dedent(
        f"""\
        Implement plan {plan_rel} in this isolated clone.

        Constraints:
        - This clone is the only writable repository.
        - Do not spawn agents, commit, edit plan status, or touch paths outside the plan write_scope.
        - Keep context bounded: read the plan, AGENTS.md, the listed context/spec files, and only implementation files needed for this task.
        - Do not inspect logs or unrelated plans.
        - Run every validation command listed in the plan before finishing.
        - Write transient diagnostics, tool caches, and temporary artifacts only under
          $SANDBOXED_PLAN_WORKER_SCRATCH_DIR.

        The parent will reject any changed path outside write_scope.
        Report changed paths, validation results, blockers, remaining risks, and confirm whether any out-of-scope path changed.

        Plan digest: {plan_digest}
        """
    )


def build_correction_prompt(plan_rel: str, plan_digest: str) -> str:
    return textwrap.dedent(
        f"""\
        Correct the rejected candidate already applied in this fresh isolated clone for {plan_rel}.

        Constraints:
        - Read the parent-authored correction brief at $SANDBOXED_PLAN_WORKER_CORRECTION_BRIEF.
        - The brief is a read-only input. Do not search for or inspect any prior attempt artifact.
        - Preserve correct prior work and change only what the brief requires.
        - Do not spawn agents, commit, edit plan status, or touch paths outside write_scope.
        - Write transient diagnostics, caches, and temporary artifacts only under
          $SANDBOXED_PLAN_WORKER_SCRATCH_DIR.
        - Report changed paths and blockers. Do not run broad plan validation.

        The parent will admit one aggregate patch against the original source HEAD.
        Plan digest: {plan_digest}
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
) -> list[str]:
    argv = [
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
    ]
    for hidden in hidden_directories:
        argv.extend(("--tmpfs", str(hidden)))
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
    for shadow_path, clone_target in writable_shadows:
        argv.extend(("--bind", str(shadow_path), str(clone_target)))
    for read_only_input in read_only_inputs:
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
    """Create writable copies for scope entries without resolving repository symlinks."""
    shadows_root = scratch_dir / "writable-shadows"
    prepared: list[tuple[Path, Path, bool]] = []
    for entry in scope_entries:
        relative, is_prefix = normalize_repo_relpath(entry, allow_prefix=True, label="write_scope entry")
        body = relative[:-1] if is_prefix else relative
        ensure_no_symlink_path_trick(clone_dir, body)
        target = clone_dir / body
        shadow = shadows_root / body
        shadow.parent.mkdir(parents=True, exist_ok=True)
        if is_prefix:
            if target.exists():
                if not target.is_dir() or target.is_symlink():
                    raise RunnerError(f"prefix write_scope target must be a directory: {relative}")
                shutil.copytree(target, shadow, symlinks=True)
            else:
                target.mkdir(parents=True, exist_ok=False)
                shadow.mkdir()
        else:
            if not target.is_file() or target.is_symlink():
                raise RunnerError(f"exact write_scope target must be an existing regular file: {relative}")
            shutil.copy2(target, shadow, follow_symlinks=False)
        prepared.append((shadow, target, is_prefix))
    return prepared


def materialize_writable_shadows(shadows: Sequence[tuple[Path, Path, bool]]) -> None:
    """Copy only scope-shadow results back into the disposable candidate clone."""
    for shadow, target, is_prefix in shadows:
        if is_prefix:
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_dir():
                    raise RunnerError(f"prefix write_scope target changed shape: {target}")
                shutil.rmtree(target)
            shutil.copytree(shadow, target, symlinks=True)
        else:
            if not target.is_file() or target.is_symlink():
                raise RunnerError(f"exact write_scope target changed shape: {target}")
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


def derive_changed_paths_from_patch(repo_root: Path, git_bin: str, patch_path: Path, base_rev: str) -> list[str]:
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
        run_subprocess((git_bin, "apply", "--cached", "--check", "--binary", str(patch_path)), cwd=repo_root, env=env)
        run_subprocess((git_bin, "apply", "--cached", "--binary", str(patch_path)), cwd=repo_root, env=env)
        output = run_subprocess(
            (git_bin, "diff-index", "--cached", "--name-only", "-z", base_rev, "--"),
            cwd=repo_root,
            env=env,
        ).stdout
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def normalize_changed_paths(paths: Sequence[str], repo_root: Path) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        match = STATUS_PATTERN.fullmatch(raw)
        candidate = match.group(1) if match else raw
        value, _ = normalize_repo_relpath(candidate, label="changed path")
        ensure_no_symlink_path_trick(repo_root, value)
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
    prior_patch: Path | None = None,
    correction_brief: bytes | None = None,
) -> dict[str, Any]:
    attempt_root = workspace / label
    clone_dir = attempt_root / "clone"
    scratch_dir = attempt_root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=False)
    clone_at_head(repo_root, git_bin, head, clone_dir)
    initial_refs = git(clone_dir, git_bin, "show-ref", "--head", "--dereference").stdout
    if prior_patch is not None:
        run_subprocess((git_bin, "apply", "--check", "--binary", str(prior_patch)), cwd=clone_dir)
        run_subprocess((git_bin, "apply", "--binary", str(prior_patch)), cwd=clone_dir)
    shadows = prepare_writable_shadows(
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        scope_entries=normalized_scope,
    )

    include_codex_home = custom_command is None
    stdin: bytes | None = None
    last_message_path = scratch_dir / "worker-last-message.txt"
    read_only_inputs: list[Path] = []
    correction_brief_path: Path | None = None
    if correction_brief is not None:
        correction_brief_path = scratch_dir / "correction-brief.txt"
        correction_brief_path.write_bytes(correction_brief)
        correction_brief_path.chmod(0o400)
        read_only_inputs.append(correction_brief_path)
    if custom_command is None:
        if codex_bin is None or model is None or reasoning is None:
            raise RunnerError("Codex attempt requires an executable, model, and reasoning effort")
        command = default_worker_command(
            codex_bin=codex_bin,
            clone_dir=clone_dir,
            scratch_dir=scratch_dir,
            last_message_path=last_message_path,
            model=model,
            reasoning=reasoning,
        )
        stdin = (
            build_correction_prompt(plan_rel, plan_digest)
            if correction_brief is not None
            else build_worker_prompt(plan_rel, plan_digest)
        ).encode("utf-8")
    else:
        command = list(custom_command)

    env_vars = prepare_worker_environment(
        source_repo=repo_root,
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        plan_rel=plan_rel,
        extra_env=extra_env,
        include_codex_home=include_codex_home,
    )
    if correction_brief_path is not None:
        env_vars[f"{ENV_PREFIX}CORRECTION_BRIEF"] = str(correction_brief_path)
    attempt_started = time.monotonic()
    result = run_subprocess(
        build_bwrap_command(
            bwrap_bin=bwrap_bin,
            clone_dir=clone_dir,
            scratch_dir=scratch_dir,
            command=command,
            env_vars=env_vars,
            writable_shadows=[(shadow, target) for shadow, target, _is_prefix in shadows],
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
    attempt_last_message: Path | None = None
    if result.returncode == 0 and last_message_path.is_file():
        attempt_last_message = reserved_artifacts[f"{artifact_prefix}-last-message.txt"]
        attempt_last_message.write_bytes(last_message_path.read_bytes())
        record["last_message_path"] = str(attempt_last_message)
        record["last_message_digest"] = hash_file(attempt_last_message)
    return {
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
    }


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


def run_worker(args: argparse.Namespace) -> int:
    runner_started = time.monotonic()
    git_bin = require_executable("git", args.git_bin)
    bwrap_bin = require_executable("bwrap", args.bwrap_bin)
    ensure_bwrap_usable(bwrap_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    plan_path, plan_rel, values, normalized_scope = load_plan(planlib, repo_root, args.plan)
    implementation_risk = implementation_classification(values, "implementation_risk")
    implementation_ambiguity = implementation_classification(values, "implementation_ambiguity")
    selected_plan_model, selected_plan_reasoning = select_plan_writable_profile(values)
    head = git_text(repo_root, git_bin, "rev-parse", "HEAD")
    plan_digest = hash_file(plan_path)
    output_dir = materialize_output_dir(repo_root, args.output_dir)
    reserved_artifacts = reserve_output_artifacts(output_dir)
    state_path = args.availability_state
    run_id = args.orchestration_run_id
    if (state_path is None) != (run_id is None):
        raise RunnerError("availability state path and orchestration run identifier must be provided together")
    state_context = (
        open_availability_state(repo_root, state_path, run_id)
        if state_path is not None and run_id is not None
        else nullcontext(None)
    )

    with state_context as availability_state, tempfile.TemporaryDirectory(
        prefix="sandboxed-plan-worker-workspace-"
    ) as workspace_tmp:
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

        worker_result = select_attempt_artifacts(selected, reserved_artifacts)
        worker_result["kind"] = worker_kind
        if attempts:
            worker_result["attempts"] = attempts
            worker_result["selected_attempt"] = selected["record"]["label"]
        if fallback_reason is not None:
            worker_result["fallback_reason"] = fallback_reason

        materialize_writable_shadows(selected["shadows"])

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

        patch_path = reserved_artifacts["candidate.patch"]
        patch_digest = write_bytes(patch_path, patch_bytes)
        changed_paths = normalize_changed_paths(
            derive_changed_paths_from_patch(repo_root, git_bin, patch_path, head),
            repo_root,
        )
        if not changed_paths:
            raise RunnerError("worker produced no candidate changes")
        disallowed = [path for path in changed_paths if not scope_allows_path(normalized_scope, path)]
        if disallowed:
            raise RunnerError(f"worker changed paths outside write_scope: {', '.join(disallowed)}")

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
            "implementation_risk": implementation_risk,
            "implementation_ambiguity": implementation_ambiguity,
        }

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "source_head": head,
            "plan_path": plan_rel,
            "plan_digest": plan_digest,
            "allowed_write_scope": normalized_scope,
            "changed_paths": changed_paths,
            "patch_path": str(patch_path),
            "patch_digest": patch_digest,
            "worker_result": worker_result,
            "telemetry": telemetry,
        }
        manifest_path = reserved_artifacts["manifest.json"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
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
        derive_changed_paths_from_patch(repo_root, git_bin, patch_path, current_head),
        repo_root,
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
    disallowed = [path for path in changed_paths if not scope_allows_path(normalized_scope, path)]
    if disallowed:
        raise RunnerError(f"candidate patch changes paths outside the current write_scope: {', '.join(disallowed)}")
    for path in changed_paths:
        ensure_no_symlink_path_trick(repo_root, path)
    run_subprocess((git_bin, "apply", "--check", "--binary", str(patch_path)), cwd=repo_root)
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
        "patch_digest": patch_digest,
        "changed_paths": changed_paths,
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
        raise RunnerError("correction budget exhausted after two isolated corrections")
    return {
        "prior_manifest_digest": prior_manifest_digest,
        "prior_patch_digest": prior_patch_digest,
        "correction_round": correction_round,
        "correction_brief_digest": correction_brief_digest,
    }


def correct_worker(args: argparse.Namespace) -> int:
    runner_started = time.monotonic()
    git_bin = require_executable("git", args.git_bin)
    bwrap_bin = require_executable("bwrap", args.bwrap_bin)
    ensure_bwrap_usable(bwrap_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    plan_rel = normalize_manifest_path(repo_root, args.plan)
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
    if (args.availability_state is None) != (args.orchestration_run_id is None):
        raise RunnerError("availability state path and orchestration run identifier must be provided together")
    state_context = (
        open_availability_state(repo_root, args.availability_state, args.orchestration_run_id)
        if args.availability_state is not None and args.orchestration_run_id is not None
        else nullcontext(None)
    )
    hidden_prior = {
        prior_manifest_path.parent.resolve(),
        verified["patch_path"].parent.resolve(),
        brief_path.parent.resolve(),
    }
    with state_context as availability_state, tempfile.TemporaryDirectory(
        prefix="sandboxed-plan-worker-correction-workspace-"
    ) as workspace_tmp:
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
            "normalized_scope": verified["normalized_scope"],
            "bwrap_bin": bwrap_bin,
            "git_bin": git_bin,
            "reserved_artifacts": reserved_artifacts,
            "extra_env": args.worker_env,
            "prior_patch": verified["patch_path"],
            "correction_brief": brief,
        }
        if args.worker_binary is not None:
            worker_binary = require_executable("worker", args.worker_binary)
            selected = execute_isolated_attempt(
                **common,
                label="custom",
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
        worker_result = select_attempt_artifacts(selected, reserved_artifacts)
        worker_result["kind"] = worker_kind
        if attempts:
            worker_result["attempts"] = attempts
            worker_result["selected_attempt"] = selected["record"]["label"]
        if fallback_reason is not None:
            worker_result["fallback_reason"] = fallback_reason
        materialize_writable_shadows(selected["shadows"])
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
        patch_path = reserved_artifacts["candidate.patch"]
        patch_digest = write_bytes(patch_path, patch_bytes)
        changed_paths = normalize_changed_paths(
            derive_changed_paths_from_patch(repo_root, git_bin, patch_path, verified["head"]),
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
        run_subprocess((git_bin, "apply", "--check", "--binary", str(patch_path)), cwd=repo_root)
        ensure_clean_worktree(repo_root, git_bin)
        if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
            raise RunnerError("source HEAD changed during correction admission")
        telemetry_attempts = attempts if worker_kind == "codex" else [selected["record"]]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "source_head": verified["head"],
            "plan_path": verified["plan_rel"],
            "plan_digest": verified["plan_digest"],
            "allowed_write_scope": verified["normalized_scope"],
            "changed_paths": changed_paths,
            "patch_path": str(patch_path),
            "patch_digest": patch_digest,
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
                "candidate_generations": 1,
                "full_validation_count": 0,
                "implementation_risk": implementation_risk,
                "implementation_ambiguity": implementation_ambiguity,
            },
        }
        manifest_path = reserved_artifacts["manifest.json"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    ensure_clean_worktree(repo_root, git_bin)
    if git_text(repo_root, git_bin, "rev-parse", "HEAD") != verified["head"]:
        raise RunnerError("source HEAD changed after candidate preflight and before apply")
    run_subprocess((git_bin, "apply", "--binary", str(verified["patch_path"])), cwd=repo_root)
    print(str(verified["patch_path"]))
    return 0


def write_self_test_worker(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            from __future__ import annotations

            import os
            from pathlib import Path


            prefix = "{ENV_PREFIX}"
            worker_repo = Path(os.environ[prefix + "WORKER_REPO"])
            source_repo = Path(os.environ[prefix + "SOURCE_REPO"])
            scratch_dir = Path(os.environ[prefix + "SCRATCH_DIR"])
            outside_probe = Path(os.environ[prefix + "OUTSIDE_PROBE"])

            (worker_repo / "allowed.txt").write_text("changed in clone\\n", encoding="utf-8")
            (worker_repo / "dir" / "new.txt").parent.mkdir(parents=True, exist_ok=True)
            (worker_repo / "dir" / "new.txt").write_text("new file\\n", encoding="utf-8")
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
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def init_self_test_repo(repo_root: Path, git_bin: str) -> str:
    run_subprocess((git_bin, "init", "-q", "-b", "main"), cwd=repo_root)
    run_subprocess((git_bin, "config", "user.email", "self-test@example.invalid"), cwd=repo_root)
    run_subprocess((git_bin, "config", "user.name", "Self Test"), cwd=repo_root)
    (repo_root / "AGENTS.md").write_text("sandboxed worker self-test\n", encoding="utf-8")
    (repo_root / "docs/plan/active").mkdir(parents=True, exist_ok=True)
    (repo_root / "docs/plan/plan.md").write_text(
        "# Active Plan\n\nid\tpath\tstatus\n001\tdocs/plan/active/001-self-test.md\tin_progress\n",
        encoding="utf-8",
    )
    (repo_root / "allowed.txt").write_text("original\n", encoding="utf-8")
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
            write_scope:
              - allowed.txt
              - dir/
            context_files:
              - docs/agent/SPEC_USER_COMMUNICATION.md
            required_specs:
              - docs/agent/SPEC_PLAN_WORKFLOW.md
            validation:
              - python3 tests/test-sandboxed-plan-worker.py
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
    normalize_repo_relpath("dir/", allow_prefix=True, label="self-test prefix")
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
        original_cwd = Path.cwd()
        try:
            os.chdir(repo_root)
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
                    orchestration_run_id=None,
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
            apply_worker_result(
                argparse.Namespace(
                    git_bin=git_bin,
                    manifest=str(manifest_path),
                )
            )
            if (repo_root / "allowed.txt").read_text(encoding="utf-8") != "changed in clone\n":
                raise RunnerError("self-test apply did not update the source repository")
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
              run      execute a writable worker inside Bubblewrap and emit a candidate patch manifest
              correct  repair a verified candidate in a fresh isolated clone and emit an aggregate patch
              apply    re-check and apply a previously emitted candidate patch manifest
              self-test run a deterministic local end-to-end check without contacting Codex
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a sandboxed worker against one active plan")
    run_parser.add_argument("plan", help="repository-relative active plan path")
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
        help="nonblank identifier that binds an availability-state file to one orchestration run",
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
    correction_parser.add_argument("--orchestration-run-id")
    correction_parser.add_argument("--worker-binary")
    correction_parser.add_argument("--worker-arg", action="append", default=[])
    correction_parser.add_argument("--worker-env", action="append", default=[])
    correction_parser.set_defaults(handler=correct_worker)

    apply_parser = subparsers.add_parser("apply", help="apply a previously emitted candidate patch manifest")
    apply_parser.add_argument("manifest", help="path to manifest.json emitted by the run command")
    apply_parser.add_argument("--git-bin", default="git", help="git executable to use")
    apply_parser.set_defaults(handler=apply_worker_result)

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
        return int(args.handler(args))
    except RunnerError as exc:
        fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
