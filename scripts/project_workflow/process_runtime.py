"""Explicit local-child context and bounded queries with POSIX waitid custody.

This module grants no authorization and selects no provider/account context.
Callers retain their own deadlines, diagnostics and authenticated execution.
"""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import os
import selectors
import signal
import shutil
import subprocess
import tempfile
import time
from typing import NamedTuple


class CommandError(RuntimeError):
    """A local query could not finish within its declared process bounds."""


class Captured(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes | None
    stderr_digest: str


def local_environment() -> dict[str, str]:
    """No ambient credentials, account paths, loader overrides or tool settings."""
    environment = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
    if os.name == "nt" and "SystemRoot" in os.environ:
        environment["SystemRoot"] = os.environ["SystemRoot"]
    return environment


def workflow_environment() -> dict[str, str]:
    """Retain only the existing enforcement and grouped-session inputs."""
    environment = local_environment()
    for name in ("PROJECT_AGENT_WORKFLOW_REQUIRE_TASK_WORKTREE",
                 "PROJECT_AGENT_WORKFLOW_SESSION_ID", "CODEX_THREAD_ID"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


def immutable_git_capture(repository, *arguments, timeout=60, data=None,
                          limit=64 * 1024, stderr_limit=None, keep_stderr=True) -> Captured:
    """Read local metadata/objects, not worktrees, writers or authenticated remotes.

    The caller owns the command semantics and explicit output budget. Repository
    filters are not rejected here: metadata reads must not depend on unrelated
    worktree attributes. This profile must not be used for normalized comparisons.
    """
    executable = shutil.which("git", path=os.defpath)
    if executable is None:
        raise CommandError("trusted system Git is unavailable")
    environment = local_environment()
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_GRAFT_FILE": os.devnull, "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    })
    return capture(
        [executable, "--no-lazy-fetch", "-c", "core.fsmonitor=false",
         "-c", f"core.hooksPath={os.devnull}", "-c", "credential.helper=",
         "-c", "core.askPass=", "-c", "protocol.allow=never",
         "-C", str(repository), *arguments],
        cwd=repository, env=environment, timeout=timeout, data=data,
        limit=limit, stderr_limit=stderr_limit, keep_stderr=keep_stderr,
        description="immutable Git query")


def wait_unreaped(process: subprocess.Popen, deadline: float) -> None:
    """Observe our child without releasing the PID that owns its process group.

    The caller exclusively owns this child: no poll/wait or other reaper may run
    before terminate_owned_group. No process-wide signal handler is installed.
    """
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, 0)
        if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
            return
        time.sleep(min(0.01, remaining))


def terminate_owned_group(process: subprocess.Popen) -> int:
    """Terminate the still-owned group, then reap its original leader."""
    if process.returncode is not None:
        raise CommandError("the owned process-group leader was already reaped")
    # Establish that this is still our unreaped child before signalling its ID.
    os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        return process.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        raise CommandError("owned process-group cleanup did not finish") from error


def capture(argv, *, cwd, env, timeout=60, data=None, limit=64 * 1024,
            stderr_limit=None, keep_stderr=True, description="local command") -> Captured:
    """Bound each pipe and the deadline, including inherited-open-pipe hangs.

    Keep the leader unreaped until its group has been terminated on success and
    failure. Only descendants remaining in that owned group are covered.
    """
    if not (os.name == "posix" and callable(getattr(os, "waitid", None))
            and hasattr(os, "WNOWAIT")):
        raise CommandError("owned local queries require POSIX waitid(WNOWAIT)")
    output = bytearray()
    errors = bytearray() if keep_stderr else None
    stderr_hash = hashlib.sha256()
    stderr_size = 0
    error_limit = limit if stderr_limit is None else stderr_limit
    deadline = time.monotonic() + timeout
    source = tempfile.TemporaryFile() if data is not None else nullcontext(subprocess.DEVNULL)
    with source as stdin:
        if data is not None:
            stdin.write(data)
            stdin.seek(0)
        process = None
        selector = None
        try:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(argv, timeout)
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            selector = selectors.DefaultSelector()
            for pipe in (process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout)
                for key, _ in selector.select(remaining):
                    is_stdout = key.fileobj is process.stdout
                    size = len(output) if is_stdout else stderr_size
                    stream_limit = limit if is_stdout else error_limit
                    try:
                        chunk = os.read(key.fd, min(65536, stream_limit + 1 - size))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if size + len(chunk) > stream_limit:
                        raise CommandError(f"{description} exceeded its output bound")
                    if is_stdout:
                        output.extend(chunk)
                    else:
                        stderr_size += len(chunk)
                        stderr_hash.update(chunk)
                        if errors is not None:
                            errors.extend(chunk)
            wait_unreaped(process, deadline)
        except subprocess.TimeoutExpired as error:
            raise CommandError(f"{description} exceeded its deadline") from error
        finally:
            try:
                if process is not None:
                    status = terminate_owned_group(process)
            finally:
                try:
                    if selector is not None:
                        selector.close()
                finally:
                    if process is not None:
                        for pipe in (process.stdout, process.stderr):
                            pipe.close()
    return Captured(status, bytes(output), bytes(errors) if errors is not None else None,
                    "sha256:" + stderr_hash.hexdigest())
