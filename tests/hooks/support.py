"""Shared paths and fixtures for Hook tests."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_LOG = ROOT / "template/.project-agent-workflow/hooks/agent_log_event.py"
ROOT_HOOK_LOG = ROOT / ".project-agent-workflow/hooks/agent_log_event.py"
IMPORTER = ROOT / "template/.project-agent-workflow/scripts/import-codex-transcript.py"
MANIFEST_HELPER = ROOT / "template/.project-agent-workflow/scripts/agent_log_manifest.py"
MANIFEST_CHECKER = ROOT / "template/.project-agent-workflow/scripts/check-agent-log-manifest.py"
CONTEXT_COMPRESS = ROOT / "template/.project-agent-workflow/scripts/context-compress.sh"
ROOT_IMPORTER = ROOT / "scripts/import-codex-transcript.py"
ROOT_MANIFEST_CHECKER = ROOT / "scripts/check-agent-log-manifest.py"
ROOT_CONTEXT_COMPRESS = ROOT / "scripts/context-compress.sh"
PRE_TOOL = ROOT / "template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py"
ROOT_PRE_TOOL = ROOT / ".project-agent-workflow/hooks/pre_tool_hardening_gate.py"
TOOL_COMMAND_CONTEXT = ROOT / "template/.project-agent-workflow/scripts/tool_command_context.py"
ROOT_GUARD = ROOT / "scripts/project_workflow/worktree_guard.py"
ROOT_WORKTREE_MANAGER = ROOT / "scripts/manage-plan-worktrees.py"
PRE_COMMIT = ROOT / ".githooks/pre-commit"
TEMPLATE_PRE_COMMIT = ROOT / "template/.githooks/pre-commit"
STOP_REVIEW = ROOT / "template/.project-agent-workflow/hooks/stop_review_gate.py"
ROOT_STOP_REVIEW = ROOT / ".project-agent-workflow/hooks/stop_review_gate.py"
LEGACY_STOP_BRIDGE = ROOT / "template/.codex/hooks/stop_review_gate.py"
SEMANTIC_GUARD = ROOT / "template/.project-agent-workflow/hooks/semantic_guard_advisory.py"
CODEX_HOOK_CONFIG = ROOT / ".codex/hooks.json"
COPILOT_HOOK_CONFIG = ROOT / ".github/hooks/plan-lifecycle.json"
TEMPLATE_COPILOT_HOOK_CONFIG = ROOT / "template/.github/hooks/plan-lifecycle.json"


def init_gate_repository(repo: Path, gate: str | None = "#!/bin/sh\nexit 0\n") -> Path:
    """Create a Git repository whose staged tree ships the given completion gate.

    ``gate`` is the shell body written to ``scripts/check-agent-completion.sh``.
    Passing ``None`` leaves the repository without any completion gate.
    """

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
    if gate is not None:
        scripts = repo / "scripts"
        scripts.mkdir(exist_ok=True)
        (scripts / "check-agent-completion.sh").write_text(gate, encoding="utf-8")
    return repo


def init_guarded_repository(
    repo: Path,
    *,
    origin: str | None = "git@github.com:example/gate.git",
    gate: str | None = "#!/bin/sh\nexit 0\n",
) -> Path:
    """Create a Git repository that ships the shared task-worktree guard.

    Passing ``origin=None`` leaves the repository without a canonical remote,
    which is the case a task binding can never name and therefore never governs.
    """

    repo.mkdir(parents=True, exist_ok=True)
    init_gate_repository(repo, gate)
    subprocess.run(["git", "config", "user.name", "Gate Test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "gate@example.invalid"], cwd=repo, check=True
    )
    if origin is not None:
        subprocess.run(["git", "remote", "add", "origin", origin], cwd=repo, check=True)
    package = repo / "scripts/project_workflow"
    package.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_GUARD, package / "worktree_guard.py")
    shutil.copy2(ROOT_WORKTREE_MANAGER, repo / "scripts/manage-plan-worktrees.py")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "baseline", "--no-verify"], cwd=repo, check=True
    )
    return repo


def bind_direct_task_worktree(
    case: unittest.TestCase,
    repo: Path,
    allowed_root: Path,
    task_id: str = "gate-task",
) -> tuple[Path, list[Path]]:
    """Prepare one direct-task worktree and report it with its record paths.

    The ownership record lives in the account's own state directory, which the
    guard reads by design and no temporary directory can stand in for. The
    test that creates the record therefore has to remove it, or a validation
    run leaves work behind for a later owner to find and judge. The test case
    is required rather than optional so that a caller cannot forget.
    """

    allowed_root.mkdir(parents=True, exist_ok=True)
    allowed_root.chmod(0o700)
    owned = owned_record_paths(
        repo, {"kind": worktree_guard().DIRECT_TASK, "identity": {"id": task_id}}
    )
    # Ownership is taken before the records can exist, because a preparation
    # that fails partway still leaves the lock and the journal behind.
    own_records(case, owned)
    result = subprocess.run(
        [
            "python3",
            str(repo / "scripts/manage-plan-worktrees.py"),
            "prepare",
            "--direct-task",
            task_id,
            "--purpose",
            "exercise the completion boundary",
            "--allowed-root",
            str(allowed_root),
            "--owner-id",
            "gate-owner",
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return Path(json.loads(result.stdout)["worktree"]), owned


def worktree_guard():
    """The guard module, loaded from the repository it belongs to."""

    import importlib.util

    spec = importlib.util.spec_from_file_location("gate_worktree_guard", ROOT_GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard


def owned_record_paths(repo: Path, task: dict) -> list[Path]:
    """Where the guard keeps the records for one task in one repository."""

    paths = worktree_guard().metadata_paths(
        worktree_guard().repository_identity(repo), task
    )
    return [paths[key] for key in ("record", "journal", "lock")]


PENDING_RECORDS: set[Path] = set()


def own_records(case: unittest.TestCase, paths: list[Path]) -> None:
    """Take responsibility for records one test is about to create.

    The test's own cleanup removes them as soon as it ends. The process-wide
    set is the same responsibility held one level up, for an interrupt: a
    KeyboardInterrupt reaches the interpreter without unittest running any
    cleanup, so without it an interrupted run would leave records in the
    account's shared directory.

    A path that already exists belongs to whoever wrote it. The directory is
    shared by every run on the account, so a test that took a path it did not
    create could delete a record another run is still using.
    """

    ours = [path for path in paths if not path.exists()]
    PENDING_RECORDS.update(ours)
    case.addCleanup(remove_owned_records, ours)


def remove_owned_records(paths: list[Path]) -> None:
    """Remove the records one test created, and only those."""

    for path in paths:
        path.unlink(missing_ok=True)
        PENDING_RECORDS.discard(path)


def remove_pending_records() -> None:
    remove_owned_records(list(PENDING_RECORDS))


atexit.register(remove_pending_records)


def run_hook(
    script: Path,
    payload: dict,
    cwd: Path | None = None,
    env: dict[str, str | None] | None = None,
    args: list[str] | None = None,
) -> dict:
    child_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if value is None:
                child_env.pop(key, None)
            else:
                child_env[key] = value
    result = subprocess.run(
        ["python3", str(script), *(args or [])],
        input=json.dumps(payload),
        cwd=cwd,
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(result.stdout or "{}")


def exec_payload(
    command: str,
    workdir: str | None = None,
    container: str = "tool_input",
    workdir_key: str = "workdir",
) -> dict:
    """Build the payload an execution tool sends for one command.

    ``workdir`` is placed in the same argument object the command came from,
    which is where a real execution tool reports the directory it will run in.
    """

    arguments: dict[str, str] = {"cmd": command}
    if workdir is not None:
        arguments[workdir_key] = workdir
    return {"tool_name": "exec_command", container: arguments}


def load_command_context():
    """Import the shared invocation interpreter both gates use."""

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gate_tool_command_context", TOOL_COMMAND_CONTEXT
    )
    module = importlib.util.module_from_spec(spec)
    # `dataclass` resolves annotations through the module registry, so the
    # module must be registered before its body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_sample_codex_transcript(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-07-05T00:00:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "hello"}],
                            "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-07-05T00:00:01Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "done"}],
                            "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-07-05T00:00:02Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call-1",
                            "output": "token sk-abcdefghijklmnopqrstuvwxyz",
                            "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1"},
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
