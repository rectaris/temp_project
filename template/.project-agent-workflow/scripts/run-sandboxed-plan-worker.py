#!/usr/bin/env python3
"""Run or apply a Bubblewrap-isolated plan worker patch."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Sequence


SCHEMA_VERSION = 1
DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"
DEFAULT_CODEX_REASONING = "medium"
DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"
DEFAULT_FALLBACK_CODEX_REASONING = "max"
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
    }
)


class RunnerError(RuntimeError):
    """Raised when the sandboxed runner must fail closed."""


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
) -> dict[str, Any]:
    attempt_root = workspace / label
    clone_dir = attempt_root / "clone"
    scratch_dir = attempt_root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=False)
    clone_at_head(repo_root, git_bin, head, clone_dir)
    initial_refs = git(clone_dir, git_bin, "show-ref", "--head", "--dereference").stdout
    shadows = prepare_writable_shadows(
        clone_dir=clone_dir,
        scratch_dir=scratch_dir,
        scope_entries=normalized_scope,
    )

    include_codex_home = custom_command is None
    stdin: bytes | None = None
    last_message_path = scratch_dir / "worker-last-message.txt"
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
        stdin = build_worker_prompt(plan_rel, plan_digest).encode("utf-8")
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
        ),
        cwd=repo_root,
        env=sanitize_process_env(),
        stdin=stdin,
        check=False,
    )

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
    git_bin = require_executable("git", args.git_bin)
    bwrap_bin = require_executable("bwrap", args.bwrap_bin)
    ensure_bwrap_usable(bwrap_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    plan_path, plan_rel, _values, normalized_scope = load_plan(planlib, repo_root, args.plan)
    head = git_text(repo_root, git_bin, "rev-parse", "HEAD")
    plan_digest = hash_file(plan_path)
    output_dir = materialize_output_dir(repo_root, args.output_dir)
    reserved_artifacts = reserve_output_artifacts(output_dir)

    with tempfile.TemporaryDirectory(prefix="sandboxed-plan-worker-workspace-") as workspace_tmp:
        workspace = Path(workspace_tmp)
        attempts: list[dict[str, Any]] = []
        fallback_reason: str | None = None
        if args.worker_binary is None:
            codex_bin = require_executable("codex", args.codex_bin)
            if not args.codex_model or not args.codex_reasoning_effort:
                raise RunnerError("preferred Codex model and reasoning effort must be non-empty")
            if not args.no_model_fallback and (
                not args.fallback_codex_model or not args.fallback_codex_reasoning_effort
            ):
                raise RunnerError("fallback Codex model and reasoning effort must be non-empty")
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
                model=args.codex_model,
                reasoning=args.codex_reasoning_effort,
            )
            attempts.append(primary["record"])
            worker_kind = "codex"
            if primary["result"].returncode == 0:
                selected = primary
            else:
                fallback_reason = classify_codex_unavailability(
                    primary["result"].stdout, primary["result"].stderr
                )
                if args.no_model_fallback or fallback_reason is None:
                    raise RunnerError(
                        f"worker exited with {primary['result'].returncode}; stdout/stderr saved under {output_dir}"
                    )
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
                    hidden_directories=(output_dir, host_codex_home_path(), primary["attempt_root"]),
                    codex_bin=codex_bin,
                    model=args.fallback_codex_model,
                    reasoning=args.fallback_codex_reasoning_effort,
                )
                attempts.append(fallback["record"])
                if fallback["result"].returncode != 0:
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


def apply_worker_result(args: argparse.Namespace) -> int:
    git_bin = require_executable("git", args.git_bin)
    repo_root = detect_repo_root(git_bin)
    os.chdir(repo_root)
    planlib = load_planlib()
    ensure_clean_worktree(repo_root, git_bin)
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_manifest(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RunnerError(f"unsupported manifest schema version: {manifest.get('schema_version')}")
    plan_rel = manifest.get("plan_path")
    if not isinstance(plan_rel, str):
        raise RunnerError("manifest plan_path must be a string")
    plan_path, plan_rel, _values, normalized_scope = load_plan(planlib, repo_root, plan_rel)
    current_head = git_text(repo_root, git_bin, "rev-parse", "HEAD")
    if current_head != manifest.get("source_head"):
        raise RunnerError("source HEAD no longer matches the worker manifest")
    current_plan_digest = hash_file(plan_path)
    if current_plan_digest != manifest.get("plan_digest"):
        raise RunnerError("active plan digest no longer matches the worker manifest")

    patch_path_raw = manifest.get("patch_path")
    if not isinstance(patch_path_raw, str):
        raise RunnerError("manifest patch_path must be a string")
    patch_path = Path(patch_path_raw).expanduser().resolve()
    if not patch_path.is_file():
        raise RunnerError(f"candidate patch is missing: {patch_path}")
    patch_digest = hash_file(patch_path)
    if patch_digest != manifest.get("patch_digest"):
        raise RunnerError("candidate patch digest no longer matches the worker manifest")

    changed_paths = normalize_changed_paths(
        derive_changed_paths_from_patch(repo_root, git_bin, patch_path, current_head),
        repo_root,
    )
    manifest_changed = manifest.get("changed_paths", [])
    if not isinstance(manifest_changed, list):
        raise RunnerError("manifest changed_paths must be a list")
    normalized_manifest_changed = [normalize_repo_relpath(item, label="manifest changed path")[0] for item in manifest_changed]
    if changed_paths != normalized_manifest_changed:
        raise RunnerError("candidate patch changed paths do not match the worker manifest")
    disallowed = [path for path in changed_paths if not scope_allows_path(normalized_scope, path)]
    if disallowed:
        raise RunnerError(f"candidate patch changes paths outside the current write_scope: {', '.join(disallowed)}")
    for path in changed_paths:
        ensure_no_symlink_path_trick(repo_root, path)

    run_subprocess((git_bin, "apply", "--check", "--binary", str(patch_path)), cwd=repo_root)
    ensure_clean_worktree(repo_root, git_bin)
    if git_text(repo_root, git_bin, "rev-parse", "HEAD") != manifest.get("source_head"):
        raise RunnerError("source HEAD changed after candidate preflight and before apply")
    run_subprocess((git_bin, "apply", "--binary", str(patch_path)), cwd=repo_root)
    print(str(patch_path))
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
                    codex_model=DEFAULT_CODEX_MODEL,
                    codex_reasoning_effort=DEFAULT_CODEX_REASONING,
                    fallback_codex_model=DEFAULT_FALLBACK_CODEX_MODEL,
                    fallback_codex_reasoning_effort=DEFAULT_FALLBACK_CODEX_REASONING,
                    no_model_fallback=False,
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
        "--codex-model", default=DEFAULT_CODEX_MODEL, help="preferred Codex model for the default worker"
    )
    run_parser.add_argument(
        "--codex-reasoning-effort",
        default=DEFAULT_CODEX_REASONING,
        help="preferred Codex reasoning effort for the default worker",
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
    run_parser.add_argument("--worker-binary", help="override the default Codex worker with a custom executable")
    run_parser.add_argument("--worker-arg", action="append", default=[], help="append one argument for --worker-binary")
    run_parser.add_argument(
        "--worker-env",
        action="append",
        default=[],
        help="set one extra KEY=VALUE environment pair inside the sandbox",
    )
    run_parser.set_defaults(handler=run_worker)

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
