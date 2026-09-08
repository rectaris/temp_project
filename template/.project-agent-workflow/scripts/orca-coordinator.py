#!/usr/bin/env python3
"""Start or reuse one bounded Orca terminal for grouped candidate dispatch."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
import re
import secrets
import selectors
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA_VERSION = 1
MINIMUM_ORCA_VERSION = (1, 4, 197)
MAX_JSON_BYTES = 256 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_STATE_BYTES = 512 * 1024
MAX_ARGUMENT_BYTES = 16 * 1024
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 300.0
TOKEN_RE = re.compile(r"[0-9a-f]{64}")
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
PLAN_PATH_RE = re.compile(
    r"docs/plan/active/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md"
)
PHASES = frozenset(
    {"prepared", "claimed", "bound", "running", "completed", "failed", "uncertain"}
)
ACTIVE_PHASES = frozenset({"bound", "running"})
SETTLED_PHASES = frozenset({"completed", "failed"})
BINDING_KEYS = {
    "repository_identity",
    "group_id",
    "group_description_digest",
    "plan_path",
    "permit_id",
    "baseline_generation",
    "source_commit",
    "worktree_path",
    "group_state_path",
    "permit_path",
    "output_path",
    "candidate_manifest_path",
    "worker_bin",
    "worker_args",
    "coordinator_terminal_handle",
    "coordinator_terminal_incarnation",
    "orca_bin",
    "lock_path",
}


class BridgeError(RuntimeError):
    """One fail-closed bridge error."""


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_sibling_module(name: str, filename: str) -> ModuleType:
    path = Path(__file__).resolve().with_name(filename)
    if not path.is_file():
        raise BridgeError(f"required sibling command is unavailable: {filename}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BridgeError(f"could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ADAPTER: ModuleType | None = None


def adapter() -> ModuleType:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = load_sibling_module(
            "orca_grouped_execution_adapter", "run-parallel-plans.py"
        )
    return _ADAPTER


def command_output(
    command: list[str], *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> bytes:
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise BridgeError(f"command is unavailable: {command[0]}") from exc
    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, ("stdout", MAX_JSON_BYTES))
    selector.register(process.stderr, selectors.EVENT_READ, ("stderr", MAX_STDERR_BYTES))
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise BridgeError(f"command timed out: {command[0]}")
            events = selector.select(remaining)
            if not events:
                continue
            for key, _ in events:
                name, limit = key.data
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[name].extend(chunk)
                if len(buffers[name]) > limit:
                    process.kill()
                    process.wait()
                    raise BridgeError(f"{name} reply exceeds its byte bound")
        returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise BridgeError(f"command timed out: {command[0]}") from exc
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if returncode != 0:
        raise BridgeError(f"command failed with exit status {returncode}")
    return bytes(buffers["stdout"])


def parse_json_reply(raw: bytes, label: str) -> dict[str, Any]:
    if len(raw) > MAX_JSON_BYTES:
        raise BridgeError(f"{label} exceeds its byte bound")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise BridgeError(f"{label} must contain one JSON object")
    if value.get("ok") is not True or not isinstance(value.get("result"), dict):
        raise BridgeError(f"{label} does not report a successful result")
    if not set(value).issubset({"id", "ok", "result", "_meta"}):
        raise BridgeError(f"{label} contains unexpected top-level fields")
    return value


def parse_version(raw: bytes) -> tuple[int, int, int]:
    text = raw.decode("utf-8", "strict").strip()
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", text)
    if match is None:
        raise BridgeError("Orca version output is malformed")
    return tuple(int(part) for part in match.groups())


def validate_runtime(orca_bin: str, timeout: float) -> dict[str, Any]:
    version = parse_version(command_output([orca_bin, "--version"], timeout=timeout))
    if version < MINIMUM_ORCA_VERSION:
        raise BridgeError(
            "Orca runtime is incompatible; version 1.4.197 or newer is required"
        )
    reply = parse_json_reply(
        command_output([orca_bin, "status", "--json"], timeout=timeout),
        "Orca status reply",
    )
    result = reply["result"]
    app = result.get("app")
    runtime = result.get("runtime")
    if not isinstance(app, dict) or app.get("running") is not True:
        raise BridgeError("Orca application is not running")
    if (
        not isinstance(runtime, dict)
        or runtime.get("state") != "ready"
        or runtime.get("reachable") is not True
        or runtime.get("connectionState") != "connected"
    ):
        raise BridgeError("Orca runtime is not ready and connected")
    runtime_id = require_identifier(
        reply.get("_meta", {}).get("runtimeId"), "Orca runtime id"
    )
    return {"runtime_id": runtime_id, "version": ".".join(map(str, version))}


def require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise BridgeError(f"{label} must be a bounded identifier")
    return value


def require_commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
        raise BridgeError(f"{label} must be a full 40-character commit id")
    return value


def normalized_absolute(path: str, label: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise BridgeError(f"{label} must be an absolute path")
    return Path(os.path.abspath(os.path.normpath(candidate)))


def reject_symlink_ancestors(path: Path, *, include_target: bool) -> None:
    absolute = path.absolute()
    current = Path(absolute.parts[0])
    limit = len(absolute.parts) if include_target else len(absolute.parts) - 1
    for part in absolute.parts[1:limit]:
        current /= part
        if current.is_symlink():
            raise BridgeError(f"symlink path component is not allowed: {current}")


def git_text(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise BridgeError(f"git {' '.join(arguments)} failed")
    return completed.stdout.strip()


def repository_worktrees(root: Path) -> list[Path]:
    lines = git_text(root, "worktree", "list", "--porcelain").splitlines()
    paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in lines
        if line.startswith("worktree ")
    ]
    if not paths:
        raise BridgeError("Git reported no repository worktrees")
    return paths


def require_outside_worktrees(path: Path, label: str, root: Path) -> None:
    for worktree in repository_worktrees(root):
        try:
            path.relative_to(worktree)
        except ValueError:
            continue
        raise BridgeError(f"{label} must be outside every repository worktree")


def open_private_file(
    path: Path, label: str, root: Path | None, flags: int
) -> tuple[int, int, os.stat_result]:
    if root is not None:
        require_outside_worktrees(path, label, root)
    reject_symlink_ancestors(path, include_target=True)
    parent_descriptor = os.open(
        path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    descriptor = -1
    try:
        parent_metadata = os.fstat(parent_descriptor)
        parent_path_metadata = os.stat(path.parent, follow_symlinks=False)
        if (
            parent_metadata.st_dev,
            parent_metadata.st_ino,
        ) != (
            parent_path_metadata.st_dev,
            parent_path_metadata.st_ino,
        ):
            raise BridgeError(f"{label} parent directory changed while opening")
        descriptor = os.open(
            path.name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_descriptor
        )
        metadata = os.fstat(descriptor)
        path_metadata = os.stat(
            path.name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        if not stat.S_ISREG(metadata.st_mode):
            raise BridgeError(f"{label} must be a regular file")
        if metadata.st_nlink != 1:
            raise BridgeError(f"{label} must not be hard linked")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise BridgeError(f"{label} must have mode 0600")
        if (metadata.st_dev, metadata.st_ino) != (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ):
            raise BridgeError(f"{label} changed while opening")
        return parent_descriptor, descriptor, metadata
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)
        raise


def recheck_open_file(
    parent_descriptor: int, descriptor: int, path: Path, label: str
) -> None:
    parent_metadata = os.fstat(parent_descriptor)
    parent_path_metadata = os.stat(path.parent, follow_symlinks=False)
    metadata = os.fstat(descriptor)
    path_metadata = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
    if (parent_metadata.st_dev, parent_metadata.st_ino) != (
        parent_path_metadata.st_dev,
        parent_path_metadata.st_ino,
    ):
        raise BridgeError(f"{label} parent directory changed")
    if (metadata.st_dev, metadata.st_ino) != (
        path_metadata.st_dev,
        path_metadata.st_ino,
    ):
        raise BridgeError(f"{label} pathname was replaced")


def require_private_file(path: Path, label: str, root: Path) -> os.stat_result:
    parent_descriptor, descriptor, metadata = open_private_file(
        path, label, root, os.O_RDONLY
    )
    try:
        recheck_open_file(parent_descriptor, descriptor, path, label)
        return metadata
    finally:
        os.close(descriptor)
        os.close(parent_descriptor)


def read_state(path: Path, root: Path) -> dict[str, Any] | None:
    parent_descriptor, descriptor, metadata = open_private_file(
        path, "bridge state", root, os.O_RDONLY
    )
    try:
        if metadata.st_size == 0:
            recheck_open_file(
                parent_descriptor, descriptor, path, "bridge state"
            )
            return None
        if metadata.st_size > MAX_STATE_BYTES:
            raise BridgeError("bridge state exceeds its byte bound")
        raw = os.read(descriptor, MAX_STATE_BYTES + 1)
        recheck_open_file(parent_descriptor, descriptor, path, "bridge state")
    finally:
        os.close(descriptor)
        os.close(parent_descriptor)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError("bridge state is not valid UTF-8 JSON") from exc
    validate_state(value)
    return value


def validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BridgeError("bridge state must contain one JSON object")
    expected = {
        "schema_version",
        "phase",
        "binding",
        "start_token",
        "runtime",
        "terminal",
        "bind_deadline_monotonic_ns",
        "worker_returncode",
        "uncertain_reason",
    }
    if set(value) != expected:
        raise BridgeError("bridge state has unexpected fields")
    if value["schema_version"] != SCHEMA_VERSION or value["phase"] not in PHASES:
        raise BridgeError("bridge state schema or phase is invalid")
    binding = value["binding"]
    if not isinstance(binding, dict) or set(binding) != BINDING_KEYS:
        raise BridgeError("bridge state binding has unexpected fields")
    require_identifier(binding["repository_identity"], "repository identity")
    require_identifier(binding["group_id"], "group id")
    require_identifier(binding["group_description_digest"], "group description digest")
    if not isinstance(binding["plan_path"], str) or not PLAN_PATH_RE.fullmatch(
        binding["plan_path"]
    ):
        raise BridgeError("bridge state plan path is invalid")
    require_identifier(binding["permit_id"], "permit id")
    if not isinstance(binding["baseline_generation"], int) or isinstance(
        binding["baseline_generation"], bool
    ):
        raise BridgeError("bridge state baseline generation must be an integer")
    require_commit(binding["source_commit"], "bridge source commit")
    for field in (
        "worktree_path",
        "group_state_path",
        "permit_path",
        "output_path",
        "lock_path",
    ):
        normalized_absolute(binding[field], f"bridge state {field}")
    for field in ("candidate_manifest_path", "worker_bin"):
        if not isinstance(binding[field], str):
            raise BridgeError(f"bridge state {field} must be text")
        if binding[field]:
            normalized_absolute(binding[field], f"bridge state {field}")
    if not isinstance(binding["worker_args"], list) or any(
        not isinstance(argument, str)
        or not argument
        or len(argument.encode("utf-8")) > MAX_ARGUMENT_BYTES
        for argument in binding["worker_args"]
    ):
        raise BridgeError("bridge state worker arguments are invalid")
    require_identifier(
        binding["coordinator_terminal_handle"], "coordinator terminal handle"
    )
    require_identifier(
        binding["coordinator_terminal_incarnation"],
        "coordinator terminal incarnation",
    )
    if not isinstance(binding["orca_bin"], str) or not binding["orca_bin"]:
        raise BridgeError("bridge state Orca executable is invalid")
    if not isinstance(value["start_token"], str) or not TOKEN_RE.fullmatch(
        value["start_token"]
    ):
        raise BridgeError("bridge state start token is invalid")
    runtime = value["runtime"]
    terminal = value["terminal"]
    if not isinstance(runtime, dict) or set(runtime) != {"runtime_id", "version"}:
        raise BridgeError("bridge runtime record is invalid")
    require_identifier(runtime["runtime_id"], "bridge runtime id")
    if not isinstance(runtime["version"], str):
        raise BridgeError("bridge runtime version is invalid")
    if not isinstance(terminal, dict) or set(terminal) != {
        "handle",
        "incarnation_id",
    }:
        raise BridgeError("bridge runtime and terminal records must be objects")
    for field in ("handle", "incarnation_id"):
        if not isinstance(terminal[field], str):
            raise BridgeError(f"bridge terminal {field} must be text")
        if terminal[field]:
            require_identifier(terminal[field], f"bridge terminal {field}")
    if value["phase"] in ACTIVE_PHASES | SETTLED_PHASES:
        if not terminal["handle"] or not terminal["incarnation_id"]:
            raise BridgeError("active or settled bridge state lacks terminal identity")
    if value["phase"] in {"prepared", "claimed"} and (
        terminal["handle"] or terminal["incarnation_id"]
    ):
        raise BridgeError("unbound bridge state already contains terminal identity")
    deadline = value["bind_deadline_monotonic_ns"]
    if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline <= 0:
        raise BridgeError("bridge bind deadline is invalid")
    returncode = value["worker_returncode"]
    if value["phase"] in SETTLED_PHASES:
        if not isinstance(returncode, int) or isinstance(returncode, bool):
            raise BridgeError("settled bridge state lacks a worker return code")
    elif returncode is not None:
        raise BridgeError("unsettled bridge state contains a worker return code")
    if not isinstance(value["uncertain_reason"], str):
        raise BridgeError("bridge uncertain reason must be text")
    if value["phase"] == "uncertain":
        require_identifier(value["uncertain_reason"], "bridge uncertain reason")
    elif value["uncertain_reason"]:
        raise BridgeError("non-uncertain bridge state contains an uncertainty reason")
    return value


def write_state(path: Path, state: dict[str, Any], root: Path) -> None:
    validate_state(state)
    payload = (
        json.dumps(state, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_STATE_BYTES:
        raise BridgeError("bridge state exceeds its byte bound")
    directory_descriptor, state_descriptor, _ = open_private_file(
        path, "bridge state", root, os.O_RDONLY
    )
    temporary = f".{path.name}.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=directory_descriptor,
        )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        recheck_open_file(
            directory_descriptor, state_descriptor, path, "bridge state"
        )
        os.replace(
            temporary,
            path.name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        os.fsync(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_descriptor)
        except FileNotFoundError:
            pass
        os.close(state_descriptor)
        os.close(directory_descriptor)


@contextlib.contextmanager
def lock_file(path: Path, root: Path):
    parent_descriptor, descriptor, _ = open_private_file(
        path, "bridge lock", root, os.O_RDWR
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        recheck_open_file(parent_descriptor, descriptor, path, "bridge lock")
        yield
        recheck_open_file(parent_descriptor, descriptor, path, "bridge lock")
    finally:
        os.close(descriptor)
        os.close(parent_descriptor)


def require_external_output(path: Path, label: str, root: Path) -> None:
    require_outside_worktrees(path, label, root)
    reject_symlink_ancestors(path, include_target=True)
    if path.exists() or path.is_symlink():
        raise BridgeError(f"{label} already exists")
    if not path.parent.is_dir():
        raise BridgeError(f"{label} parent directory does not exist")


def terminal_from_reply(reply: dict[str, Any], label: str) -> dict[str, Any]:
    result = reply["result"]
    terminal = result.get("terminal", result)
    if not isinstance(terminal, dict):
        raise BridgeError(f"{label} terminal is malformed")
    handle = require_identifier(terminal.get("handle"), f"{label} terminal handle")
    incarnation = terminal.get("incarnationId")
    if incarnation is not None:
        incarnation = require_identifier(incarnation, f"{label} incarnation")
    worktree_path = terminal.get("worktreePath")
    if worktree_path is not None and not isinstance(worktree_path, str):
        raise BridgeError(f"{label} worktree path is malformed")
    connected = terminal.get("connected")
    if connected is not None and not isinstance(connected, bool):
        raise BridgeError(f"{label} connected flag is malformed")
    return {
        "handle": handle,
        "incarnation_id": incarnation or "",
        "worktree_path": worktree_path or "",
        "connected": connected,
    }


def show_terminal(
    orca_bin: str, handle: str, timeout: float, expected_worktree: Path | None
) -> dict[str, str]:
    reply = parse_json_reply(
        command_output(
            [orca_bin, "terminal", "show", "--terminal", handle, "--json"],
            timeout=timeout,
        ),
        "Orca terminal show reply",
    )
    terminal = terminal_from_reply(reply, "Orca terminal show reply")
    if terminal["handle"] != handle:
        raise BridgeError("Orca terminal show returned a different handle")
    if not terminal["incarnation_id"]:
        raise BridgeError("Orca terminal show omitted the incarnation id")
    if terminal["connected"] is not True:
        raise BridgeError("Orca terminal is not connected")
    if expected_worktree is not None:
        observed = normalized_absolute(
            terminal["worktree_path"], "Orca terminal worktree path"
        )
        if observed != expected_worktree:
            raise BridgeError("Orca terminal belongs to a different worktree")
    return {
        "handle": terminal["handle"],
        "incarnation_id": terminal["incarnation_id"],
    }


def binding_from_args(args: argparse.Namespace, context: dict[str, Any]) -> dict[str, Any]:
    permit = context["permit"]
    root = context["root"]
    worktree = normalized_absolute(args.worktree, "member worktree")
    if git_text(worktree, "rev-parse", "--show-toplevel") != str(worktree):
        raise BridgeError("member worktree is not its Git top level")
    source_commit = require_commit(args.source_commit, "source commit")
    if git_text(worktree, "rev-parse", "HEAD") != source_commit:
        raise BridgeError("member worktree HEAD differs from the requested source commit")
    if permit["base_commit"] != source_commit:
        raise BridgeError("group permit is bound to a different source commit")
    adapter().require_clean_checkout(worktree)
    adapter().require_member_worktree(worktree, args.plan)
    output = normalized_absolute(args.output, "candidate readiness output")
    require_external_output(output, "candidate readiness output", root)
    candidate_manifest = ""
    if args.candidate_manifest:
        candidate = normalized_absolute(args.candidate_manifest, "candidate manifest")
        require_external_output(candidate, "candidate manifest", root)
        candidate_manifest = str(candidate)
    worker_bin = ""
    if args.worker_bin:
        worker = normalized_absolute(args.worker_bin, "worker binary")
        if not worker.is_file():
            raise BridgeError("worker binary is unavailable")
        worker_bin = str(worker)
    worker_args = list(args.worker_arg)
    if any(
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > MAX_ARGUMENT_BYTES
        for value in worker_args
    ):
        raise BridgeError("worker arguments must be non-empty and bounded")
    return {
        "repository_identity": context["state"]["repository_identity"],
        "group_id": permit["group_id"],
        "group_description_digest": permit["group_description_digest"],
        "plan_path": args.plan,
        "permit_id": permit["permit_id"],
        "baseline_generation": permit["baseline_generation"],
        "source_commit": source_commit,
        "worktree_path": str(worktree),
        "group_state_path": str(normalized_absolute(args.group_state, "group state")),
        "permit_path": str(normalized_absolute(args.permit, "group permit")),
        "output_path": str(output),
        "candidate_manifest_path": candidate_manifest,
        "worker_bin": worker_bin,
        "worker_args": worker_args,
        "coordinator_terminal_handle": require_identifier(
            args.coordinator_terminal, "coordinator terminal handle"
        ),
        "coordinator_terminal_incarnation": "",
        "orca_bin": args.orca_bin,
        "lock_path": str(normalized_absolute(args.lock, "bridge lock")),
    }


def dispatch_vector(binding: dict[str, Any]) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("run-parallel-plans.py")),
        "dispatch",
        "--state",
        binding["group_state_path"],
        "--permit",
        binding["permit_path"],
        "--plan",
        binding["plan_path"],
        "--worktree",
        binding["worktree_path"],
        "--output",
        binding["output_path"],
    ]
    if binding["candidate_manifest_path"]:
        command.extend(["--candidate-manifest", binding["candidate_manifest_path"]])
    if binding["worker_bin"]:
        command.extend(["--worker-bin", binding["worker_bin"]])
    for value in binding["worker_args"]:
        command.extend(["--worker-arg", value])
    return command


def run_dispatch(command: list[str], worktree: str) -> int:
    return subprocess.run(command, check=False, cwd=worktree).returncode


def mark_uncertain(
    state_path: Path, lock_path: Path, root: Path, reason: str
) -> None:
    with lock_file(lock_path, root):
        state = read_state(state_path, root)
        if state is None or state["phase"] in SETTLED_PHASES:
            return
        state["phase"] = "uncertain"
        state["uncertain_reason"] = reason
        write_state(state_path, state, root)


def wait_for_phase(
    state_path: Path,
    lock_path: Path,
    root: Path,
    allowed: frozenset[str],
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with lock_file(lock_path, root):
            state = read_state(state_path, root)
            if state is None:
                raise BridgeError("bridge state disappeared")
            if state["phase"] in allowed:
                return state
            if state["phase"] in SETTLED_PHASES | {"uncertain"}:
                raise BridgeError(f"bridge entered terminal phase {state['phase']}")
        time.sleep(0.02)
    raise BridgeError("bridge state transition timed out")


def remaining_bind_seconds(state: dict[str, Any]) -> float:
    remaining_ns = state["bind_deadline_monotonic_ns"] - time.monotonic_ns()
    if remaining_ns <= 0:
        raise BridgeError("worker entry binding deadline expired")
    remaining = remaining_ns / 1_000_000_000
    if remaining > MAX_TIMEOUT_SECONDS:
        raise BridgeError("worker entry binding deadline exceeds its allowed horizon")
    return remaining


def prepare_attempt(
    state_path: Path,
    lock_path: Path,
    root: Path,
    binding: dict[str, Any],
    runtime: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any], bool]:
    with lock_file(lock_path, root):
        existing = read_state(state_path, root)
        if existing is not None:
            if existing["binding"] != binding:
                raise BridgeError("bridge state is bound to a different attempt")
            if existing["runtime"] != runtime:
                raise BridgeError(
                    "bridge state belongs to a different Orca runtime incarnation"
                )
            if existing["phase"] in SETTLED_PHASES:
                raise BridgeError("bridge attempt is already settled")
            if existing["phase"] == "uncertain":
                raise BridgeError("bridge attempt is uncertain and cannot be retried")
            if existing["phase"] not in ACTIVE_PHASES:
                raise BridgeError(
                    "bridge attempt has an incomplete creation observation; automatic "
                    "duplicate creation is refused"
                )
            return existing, True
        token = secrets.token_hex(32)
        state = {
            "schema_version": SCHEMA_VERSION,
            "phase": "prepared",
            "binding": binding,
            "start_token": token,
            "runtime": runtime,
            "terminal": {"handle": "", "incarnation_id": ""},
            "bind_deadline_monotonic_ns": time.monotonic_ns()
            + int(timeout * 1_000_000_000),
            "worker_returncode": None,
            "uncertain_reason": "",
        }
        write_state(state_path, state, root)
        return state, False


def command_ensure(args: argparse.Namespace) -> None:
    bridge = adapter()
    state_path = normalized_absolute(args.state, "bridge state")
    lock_path = normalized_absolute(args.lock, "bridge lock")
    root = bridge.repository_root()
    if state_path == lock_path:
        raise BridgeError("bridge state and lock paths must differ")
    require_private_file(state_path, "bridge state", root)
    require_private_file(lock_path, "bridge lock", root)
    try:
        context = bridge.verified_member(
            Path(args.group_state), Path(args.permit), args.plan, "run"
        )
    except bridge.AdapterError as exc:
        raise BridgeError(str(exc)) from exc
    binding = binding_from_args(args, context)
    runtime = validate_runtime(args.orca_bin, args.timeout_seconds)
    coordinator = show_terminal(
        args.orca_bin,
        binding["coordinator_terminal_handle"],
        args.timeout_seconds,
        None,
    )
    binding["coordinator_terminal_incarnation"] = coordinator["incarnation_id"]
    state, reused = prepare_attempt(
        state_path, lock_path, root, binding, runtime, args.timeout_seconds
    )
    if reused:
        if state["phase"] == "bound":
            try:
                state = wait_for_phase(
                    state_path,
                    lock_path,
                    root,
                    frozenset({"running", "completed", "failed"}),
                    remaining_bind_seconds(state),
                )
            except BridgeError:
                mark_uncertain(state_path, lock_path, root, "entry_start_unverified")
                raise
        if state["phase"] in SETTLED_PHASES:
            raise BridgeError("bridge attempt settled before it could be reused")
        terminal = show_terminal(
            args.orca_bin,
            state["terminal"]["handle"],
            args.timeout_seconds,
            Path(binding["worktree_path"]),
        )
        if terminal != state["terminal"]:
            raise BridgeError("recorded Orca terminal incarnation changed")
        with lock_file(lock_path, root):
            current = read_state(state_path, root)
            if current is None or current["binding"] != binding:
                raise BridgeError("bridge state changed during terminal reuse")
            if current["phase"] != "running":
                raise BridgeError(
                    f"bridge attempt cannot be reused from phase {current['phase']}"
                )
        print(
            json.dumps(
                {"outcome": "reused", "terminal": terminal, "phase": "running"},
                sort_keys=True,
            )
        )
        return

    entry = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker-entry",
        "--state",
        str(state_path),
        "--start-token",
        state["start_token"],
    ]
    create_command = [
        args.orca_bin,
        "terminal",
        "create",
        "--worktree",
        f"path:{binding['worktree_path']}",
        "--title",
        f"Plan {Path(args.plan).name[:96]} candidate",
        "--command",
        shlex.join(entry),
        "--json",
    ]
    try:
        create_reply = parse_json_reply(
            command_output(create_command, timeout=args.timeout_seconds),
            "Orca terminal create reply",
        )
        created = terminal_from_reply(create_reply, "Orca terminal create reply")
        handle = created["handle"]
        wait_for_phase(
            state_path,
            lock_path,
            root,
            frozenset({"claimed"}),
            remaining_bind_seconds(state),
        )
        shown = show_terminal(
            args.orca_bin,
            handle,
            args.timeout_seconds,
            Path(binding["worktree_path"]),
        )
        if created["incarnation_id"] and created["incarnation_id"] != shown["incarnation_id"]:
            raise BridgeError("Orca create and show incarnation ids differ")
        with lock_file(lock_path, root):
            current = read_state(state_path, root)
            if current is None or current["phase"] != "claimed":
                raise BridgeError("worker entry claim changed before terminal binding")
            if current["binding"] != binding or current["start_token"] != state["start_token"]:
                raise BridgeError("worker entry claim is bound to different state")
            current["terminal"] = shown
            current["phase"] = "bound"
            write_state(state_path, current, root)
        started = wait_for_phase(
            state_path,
            lock_path,
            root,
            frozenset({"running", "completed", "failed"}),
            remaining_bind_seconds(state),
        )
        if started["phase"] == "failed":
            raise BridgeError("worker dispatch failed immediately after terminal binding")
    except BridgeError:
        mark_uncertain(state_path, lock_path, root, "terminal_creation_unverified")
        raise
    print(
        json.dumps(
            {"outcome": "created", "terminal": shown, "phase": started["phase"]},
            sort_keys=True,
        )
    )


def command_worker_entry(args: argparse.Namespace) -> None:
    state_path = normalized_absolute(args.state, "bridge state")
    token = args.start_token
    if not TOKEN_RE.fullmatch(token):
        raise BridgeError("worker entry start token is invalid")
    initial = read_state_without_root(state_path)
    lock_path = normalized_absolute(initial["binding"]["lock_path"], "bridge lock")
    root = Path(
        subprocess.check_output(
            [
                "git",
                "-C",
                initial["binding"]["worktree_path"],
                "rev-parse",
                "--show-toplevel",
            ],
            text=True,
        ).strip()
    ).resolve()
    require_private_file(state_path, "bridge state", root)
    require_private_file(lock_path, "bridge lock", root)
    with lock_file(lock_path, root):
        state = read_state(state_path, root)
        if state is None or state["phase"] != "prepared":
            raise BridgeError("worker entry cannot claim the current bridge phase")
        if not secrets.compare_digest(state["start_token"], token):
            raise BridgeError("worker entry start token mismatch")
        state["phase"] = "claimed"
        write_state(state_path, state, root)
    try:
        state = wait_for_phase(
            state_path,
            lock_path,
            root,
            frozenset({"bound"}),
            remaining_bind_seconds(initial),
        )
    except BridgeError:
        mark_uncertain(state_path, lock_path, root, "entry_bind_timeout")
        raise
    with lock_file(lock_path, root):
        current = read_state(state_path, root)
        if current is None or current["phase"] != "bound":
            raise BridgeError("worker entry lost its terminal binding")
        current["phase"] = "running"
        write_state(state_path, current, root)
        binding = current["binding"]
    returncode = run_dispatch(dispatch_vector(binding), binding["worktree_path"])
    with lock_file(lock_path, root):
        current = read_state(state_path, root)
        if current is None or current["phase"] != "running":
            raise BridgeError("worker entry result no longer owns the running phase")
        current["worker_returncode"] = returncode
        current["phase"] = "completed" if returncode == 0 else "failed"
        write_state(state_path, current, root)
    raise SystemExit(returncode)


def read_state_without_root(path: Path) -> dict[str, Any]:
    parent_descriptor, descriptor, metadata = open_private_file(
        path, "bridge state", None, os.O_RDONLY
    )
    try:
        raw = os.read(descriptor, MAX_STATE_BYTES + 1)
        recheck_open_file(parent_descriptor, descriptor, path, "bridge state")
    finally:
        os.close(descriptor)
        os.close(parent_descriptor)
    if len(raw) > MAX_STATE_BYTES:
        raise BridgeError("bridge state exceeds its byte bound")
    try:
        state = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError("bridge state is not valid UTF-8 JSON") from exc
    return validate_state(state)


def default_orca_bin() -> str:
    explicit = os.environ.get("ORCA_CLI_COMMAND", "").strip()
    if explicit:
        return explicit
    if os.environ.get("ORCA_DEV_REPO_ROOT"):
        return "orca-dev"
    if sys.platform.startswith("linux"):
        return "orca-ide"
    return "orca"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ensure = sub.add_parser(
        "ensure-worker", help="create or reuse one exact bounded worker terminal"
    )
    ensure.add_argument("--state", required=True)
    ensure.add_argument("--lock", required=True)
    ensure.add_argument("--group-state", required=True)
    ensure.add_argument("--permit", required=True)
    ensure.add_argument("--plan", required=True)
    ensure.add_argument("--worktree", required=True)
    ensure.add_argument("--source-commit", required=True)
    ensure.add_argument("--output", required=True)
    ensure.add_argument("--candidate-manifest")
    ensure.add_argument("--worker-bin")
    ensure.add_argument("--worker-arg", action="append", default=[])
    ensure.add_argument("--coordinator-terminal", required=True)
    ensure.add_argument("--orca-bin", default=default_orca_bin())
    ensure.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    ensure.set_defaults(handler=command_ensure)

    entry = sub.add_parser("worker-entry", help=argparse.SUPPRESS)
    entry.add_argument("--state", required=True)
    entry.add_argument("--start-token", required=True)
    entry.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    entry.set_defaults(handler=command_worker_entry)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout_seconds <= 0 or args.timeout_seconds > MAX_TIMEOUT_SECONDS:
        fail("timeout must be greater than zero and at most 300 seconds")
    try:
        args.handler(args)
    except BridgeError as exc:
        fail(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
