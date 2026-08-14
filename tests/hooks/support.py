"""Shared paths and fixtures for Hook tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
STOP_REVIEW = ROOT / "template/.project-agent-workflow/hooks/stop_review_gate.py"
LEGACY_STOP_BRIDGE = ROOT / "template/.codex/hooks/stop_review_gate.py"
SEMANTIC_GUARD = ROOT / "template/.project-agent-workflow/hooks/semantic_guard_advisory.py"


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
