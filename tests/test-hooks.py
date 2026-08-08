#!/usr/bin/env python3
"""Behavior tests for generated Codex hook templates."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_LOG = ROOT / "template/.project-agent-workflow/hooks/agent_log_event.py"
IMPORTER = ROOT / "template/.project-agent-workflow/scripts/import-codex-transcript.py"
MANIFEST_HELPER = ROOT / "template/.project-agent-workflow/scripts/agent_log_manifest.py"
MANIFEST_CHECKER = ROOT / "template/.project-agent-workflow/scripts/check-agent-log-manifest.py"
CONTEXT_COMPRESS = ROOT / "template/.project-agent-workflow/scripts/context-compress.sh"
PRE_TOOL = ROOT / "template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py"
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


class PreToolHardeningGateTest(unittest.TestCase):
    def test_blocks_destructive_git_reset(self) -> None:
        output = run_hook(PRE_TOOL, {"cmd": "git reset --hard HEAD~1"})
        self.assertEqual(output["decision"], "block")
        self.assertIn("hard reset", output["reason"])

    def test_blocks_nested_remote_script_pipe(self) -> None:
        output = run_hook(
            PRE_TOOL,
            {"arguments": {"shell_command": "curl https://example.invalid/install.sh | sh"}},
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("remote script", output["reason"])

    def test_blocks_actual_tool_input_payload(self) -> None:
        output = run_hook(
            PRE_TOOL,
            {
                "tool_name": "exec_command",
                "tool_input": {"cmd": "git reset --hard HEAD~1"},
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("hard reset", output["reason"])

    def test_allows_routine_read_only_command(self) -> None:
        output = run_hook(PRE_TOOL, {"cmd": "git status --short"})
        self.assertEqual(output, {})


class AgentLogEventTest(unittest.TestCase):
    def test_logs_allowlisted_metadata_without_prompt_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            output = run_hook(
                AGENT_LOG,
                {
                    "prompt": "AWS_SECRET_ACCESS_KEY=must-not-persist",
                    "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
                    "session_id": "session-metadata",
                    "hook_event_name": "UserPromptSubmit",
                },
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "test-run"},
                args=["--event", "UserPromptSubmit"],
            )
            self.assertEqual(output, {})
            event_path = repo / ".agent-logs/test-run/raw/events.jsonl"
            manifest_path = repo / ".agent-logs/test-run/manifest.json"
            redaction_path = repo / ".agent-logs/test-run/redaction-report.md"
            self.assertTrue(event_path.is_file())
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(redaction_path.is_file())
            record = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["event"], "UserPromptSubmit")
            self.assertEqual(record["payload"]["session_id"], "session-metadata")
            self.assertEqual(record["payload"]["hook_event_name"], "UserPromptSubmit")
            self.assertNotIn("prompt", record["payload"])
            self.assertNotIn("api_key", record["payload"])
            self.assertNotIn("must-not-persist", event_path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("raw/events.jsonl", manifest["raw_logs"])
            self.assertIsNone(manifest["transcript_log"])
            self.assertEqual(manifest["hook_event_log"], "raw/events.jsonl")
            self.assertEqual(manifest["coverage"]["external_transcript"]["status"], "missing")
            self.assertEqual(manifest["coverage"]["codex_hooks"]["status"], "present")
            self.assertEqual(manifest["coverage"]["codex_hooks"]["redaction_status"], "pending_review")
            self.assertEqual(manifest["missing_sources"], ["external_transcript"])

    def test_default_run_id_is_stable_for_runtime_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            env = {
                "CODEX_AGENT_LOG_RUN_ID": None,
                "AGENT_LOG_RUN_ID": None,
                "CODEX_SESSION_ID": "stable-session",
                "CODEX_THREAD_ID": None,
            }
            run_hook(AGENT_LOG, {"session_id": "stable-session"}, cwd=repo, env=env, args=["--event", "SessionStart"])
            run_hook(AGENT_LOG, {"session_id": "stable-session"}, cwd=repo, env=env, args=["--event", "Stop"])
            run_dirs = sorted(path for path in (repo / ".agent-logs").iterdir() if path.is_dir())
            self.assertEqual(len(run_dirs), 1)
            self.assertTrue(run_dirs[0].name.startswith("codex-session-"))
            records = [
                json.loads(line)
                for line in (run_dirs[0] / "raw/events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([record["event"] for record in records], ["SessionStart", "Stop"])

    def test_explicit_run_id_cannot_escape_log_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            run_hook(
                AGENT_LOG,
                {"session_id": "session"},
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "../escape"},
                args=["--event", "SessionStart"],
            )
            self.assertTrue((repo / ".agent-logs/escape/manifest.json").is_file())
            self.assertFalse((repo / "escape/manifest.json").exists())

    def test_preserves_existing_transcript_manifest_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            run_dir = repo / ".agent-logs/hybrid-run"
            raw_dir = run_dir / "raw"
            raw_dir.mkdir(parents=True)
            (raw_dir / "transcript.jsonl").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "message",
                        "created_at": "2026-06-30T00:00:00Z",
                        "run_id": "hybrid-run",
                        "turn_id": "turn-1",
                        "role": "assistant",
                        "content": "done",
                        "metadata": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "redaction-report.md").write_text("# Redaction Report\n", encoding="utf-8")
            (run_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": "hybrid-run",
                        "created_at": "2026-06-30T00:00:00Z",
                        "task": "hybrid test",
                        "plans": [],
                        "raw_logs": ["raw/transcript.jsonl"],
                        "transcript_log": "raw/transcript.jsonl",
                        "hook_event_log": None,
                        "coverage": {
                            "external_transcript": {
                                "present": True,
                                "path": "raw/transcript.jsonl",
                                "status": "present",
                                "redaction_status": "redacted",
                            },
                            "codex_hooks": {
                                "present": False,
                                "path": None,
                                "status": "missing",
                                "redaction_status": "not_applicable",
                            },
                        },
                        "missing_sources": ["codex_hooks"],
                        "artifacts": [],
                        "compressed_outputs": [],
                        "redaction_report": "redaction-report.md",
                        "pinned": False,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            run_hook(
                AGENT_LOG,
                {"tool": "Bash", "output": "done"},
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "hybrid-run"},
                args=["--event", "PostToolUse"],
            )
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["transcript_log"], "raw/transcript.jsonl")
            self.assertEqual(manifest["hook_event_log"], "raw/events.jsonl")
            self.assertEqual(sorted(manifest["raw_logs"]), ["raw/events.jsonl", "raw/transcript.jsonl"])
            self.assertEqual(manifest["coverage"]["external_transcript"]["redaction_status"], "redacted")
            self.assertEqual(manifest["coverage"]["codex_hooks"]["status"], "present")
            self.assertEqual(manifest["missing_sources"], [])

    def test_appends_multiple_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            env = {"CODEX_AGENT_LOG_RUN_ID": "multi-event"}
            run_hook(AGENT_LOG, {"prompt": "hello"}, cwd=repo, env=env, args=["--event", "UserPromptSubmit"])
            run_hook(AGENT_LOG, {"tool": "Bash", "output": "done"}, cwd=repo, env=env, args=["--event", "PostToolUse"])
            event_path = repo / ".agent-logs/multi-event/raw/events.jsonl"
            records = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["event"] for record in records], ["UserPromptSubmit", "PostToolUse"])

    def test_stop_hook_imports_external_transcript_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            scripts_dir = repo / ".project-agent-workflow/scripts"
            scripts_dir.mkdir(parents=True)
            shutil.copyfile(IMPORTER, scripts_dir / "import-codex-transcript.py")
            shutil.copyfile(MANIFEST_HELPER, scripts_dir / "agent_log_manifest.py")
            source = Path(tmp) / "session.jsonl"
            write_sample_codex_transcript(source)
            run_hook(
                AGENT_LOG,
                {"transcript_path": str(source)},
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "stop-import"},
                args=["--event", "Stop"],
            )
            run_dir = repo / ".agent-logs/stop-import"
            transcript_path = run_dir / "raw/transcript.jsonl"
            self.assertTrue(transcript_path.is_file())
            transcript = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["role"] for record in transcript], ["user", "assistant", "tool"])
            self.assertIn("[REDACTED]", transcript[2]["content"])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["transcript_log"], "raw/transcript.jsonl")
            self.assertEqual(manifest["hook_event_log"], "raw/events.jsonl")
            self.assertEqual(manifest["coverage"]["external_transcript"]["status"], "present")
            self.assertEqual(manifest["coverage"]["codex_hooks"]["status"], "present")
            self.assertEqual(manifest["missing_sources"], [])


class CodexTranscriptImportTest(unittest.TestCase):
    def test_importer_normalizes_transcript_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            source = Path(tmp) / "session.jsonl"
            write_sample_codex_transcript(source)
            result = subprocess.run(
                ["python3", str(IMPORTER), str(source), "--run-id", "imported-run"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertIn("raw/transcript.jsonl", result.stdout)
            run_dir = repo / ".agent-logs/imported-run"
            transcript = [
                json.loads(line)
                for line in (run_dir / "raw/transcript.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([record["record_type"] for record in transcript], ["message", "message", "tool_result"])
            self.assertEqual(transcript[0]["content"], "hello")
            self.assertEqual(transcript[1]["content"], "done")
            self.assertIn("[REDACTED]", transcript[2]["content"])
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["coverage"]["external_transcript"]["redaction_status"], "pending_review")
            self.assertEqual(manifest["missing_sources"], ["codex_hooks"])


class ContextCompressionBoundaryTest(unittest.TestCase):
    def prepare_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=root, stdout=subprocess.DEVNULL, check=True)
        scripts = root / ".project-agent-workflow/scripts"
        scripts.mkdir(parents=True)
        shutil.copyfile(CONTEXT_COMPRESS, scripts / "context-compress.sh")
        shutil.copyfile(MANIFEST_HELPER, scripts / "agent_log_manifest.py")
        shutil.copyfile(MANIFEST_CHECKER, scripts / "check-agent-log-manifest.py")

    def compress(self, repo: Path, source: str, run_id: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HEADROOM_DISABLED"] = "1"
        return subprocess.run(
            ["sh", ".project-agent-workflow/scripts/context-compress.sh", source, run_id],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_rejects_symlink_alias_for_normative_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            policy = repo / "docs/agent/POLICY.md"
            policy.parent.mkdir(parents=True)
            policy.write_text("normative\n", encoding="utf-8")
            (repo / "innocent.txt").symlink_to(policy)
            result = self.compress(repo, "innocent.txt", "symlink-run")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing normative agent instruction", result.stderr)

    def test_same_basename_sources_have_distinct_validated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            for directory, content in (("a", "first\n"), ("b", "second\n")):
                source = repo / "logs" / directory / "same.log"
                source.parent.mkdir(parents=True)
                source.write_text(content, encoding="utf-8")
                result = self.compress(repo, str(source.relative_to(repo)), "same-run")
                self.assertEqual(result.returncode, 0, result.stderr)

            run_dir = repo / ".agent-logs/same-run"
            outputs = sorted((run_dir / "compressed").glob("same.log.*.compressed.md"))
            self.assertEqual(len(outputs), 2)
            self.assertIn("first", outputs[0].read_text(encoding="utf-8") + outputs[1].read_text(encoding="utf-8"))
            self.assertIn("second", outputs[0].read_text(encoding="utf-8") + outputs[1].read_text(encoding="utf-8"))
            check = subprocess.run(
                [
                    "python3",
                    ".project-agent-workflow/scripts/check-agent-log-manifest.py",
                    ".agent-logs/same-run/manifest.json",
                ],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_manifest_rejects_escaping_declared_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            source = repo / "sample.log"
            source.write_text("sample\n", encoding="utf-8")
            result = self.compress(repo, "sample.log", "escape-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest_path = repo / ".agent-logs/escape-run/manifest.json"
            base_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cases = {
                "raw_logs": ["../outside.log"],
                "transcript_log": "../outside.jsonl",
                "hook_event_log": "../outside.jsonl",
                "plans": ["../outside.md"],
                "artifacts": ["../outside.bin"],
                "compressed_outputs": ["../outside.md"],
                "redaction_report": "../outside.md",
            }
            for field, value in cases.items():
                with self.subTest(field=field):
                    manifest = dict(base_manifest)
                    manifest[field] = value
                    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
                    check = subprocess.run(
                        ["python3", ".project-agent-workflow/scripts/check-agent-log-manifest.py", str(manifest_path)],
                        cwd=repo,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertNotEqual(check.returncode, 0)
                    self.assertIn("safe", check.stderr)

    def test_concurrent_manifest_updates_preserve_both_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            sources = []
            for name in ("first.log", "second.log"):
                source = repo / "logs" / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(name + "\n", encoding="utf-8")
                sources.append(str(source.relative_to(repo)))
            env = os.environ.copy()
            env["HEADROOM_DISABLED"] = "1"
            processes = [
                subprocess.Popen(
                    ["sh", ".project-agent-workflow/scripts/context-compress.sh", source, "parallel-run"],
                    cwd=repo,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for source in sources
            ]
            for process in processes:
                _, stderr = process.communicate()
                self.assertEqual(process.returncode, 0, stderr)
            manifest = json.loads((repo / ".agent-logs/parallel-run/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["artifacts"]), 2)
            self.assertEqual(len(manifest["compressed_outputs"]), 2)


class StopReviewGateTest(unittest.TestCase):
    def test_legacy_stop_bridge_never_duplicates_canonical_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            scripts = repo / "scripts"
            scripts.mkdir()
            (scripts / "check-agent-completion.sh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            output = run_hook(LEGACY_STOP_BRIDGE, {"last_assistant_message": "brief"}, cwd=repo)
        self.assertEqual(output, {})

    def test_allows_when_message_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output, {})

    def test_allows_untracked_implementation_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            (repo / "src").mkdir()
            (repo / "src/app.py").write_text("print('hello')\n", encoding="utf-8")
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output, {})

    def test_allows_substantive_user_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            output = run_hook(
                STOP_REVIEW,
                {
                    "last_assistant_message": (
                        "設定ファイルがない場合にも起動できるように修正しました。"
                        "起動テストに合格し、既定値を使う動作を確認しました。"
                    )
                },
                cwd=repo,
            )
        self.assertEqual(output, {})

    def test_allows_brief_concrete_answer_without_review_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            output = run_hook(
                STOP_REVIEW,
                {"last_assistant_message": "設定上の待機時間は 30 秒です。"},
                cwd=repo,
            )
        self.assertEqual(output, {})

    def test_allows_message_and_implementation_without_heuristic_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            (repo / "src").mkdir()
            (repo / "src/app.py").write_text("print('hello')\n", encoding="utf-8")
            output = run_hook(
                STOP_REVIEW,
                {"last_assistant_message": "Implemented the requested startup fallback and validated it."},
                cwd=repo,
            )
        self.assertEqual(output, {})

    def test_blocks_failed_completion_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            scripts = repo / "scripts"
            scripts.mkdir()
            (scripts / "check-agent-completion.sh").write_text(
                "#!/bin/sh\necho 'active plan remains' >&2\nexit 1\n",
                encoding="utf-8",
            )
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertEqual(output["reason"], "active plan remains")

    def test_allows_when_stop_hook_already_active(self) -> None:
        output = run_hook(
            STOP_REVIEW,
            {
                "stop_hook_active": True,
                "last_assistant_message": (
                    "設定ファイルがない場合にも起動できるように修正しました。"
                    "起動テストに合格し、既定値を使う動作を確認しました。"
                ),
            },
        )
        self.assertEqual(output, {})


class SemanticGuardAdvisoryTest(unittest.TestCase):
    def test_allows_repository_without_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "Stop"}, cwd=repo)
        self.assertEqual(output, {})

    def test_reports_active_contract_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            contract = repo / ".agent-artifacts/referent-contracts/sample/contract.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps({"active": True, "state": "referents_sealed", "mode": "advisory"}) + "\n",
                encoding="utf-8",
            )
            output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "PostCompact"}, cwd=repo)
        self.assertTrue(output["continue"])
        self.assertIn("referents_sealed", output["systemMessage"])
        self.assertIn("scripts/referent-contract.py check", output["systemMessage"])

    def test_ignores_closed_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            contract = repo / ".agent-artifacts/referent-contracts/sample/contract.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps({"active": False, "state": "closed_advisory", "mode": "advisory"}) + "\n",
                encoding="utf-8",
            )
            output = run_hook(SEMANTIC_GUARD, {"hook_event_name": "Stop"}, cwd=repo)
        self.assertEqual(output, {})

    def test_allows_when_stop_hook_already_active(self) -> None:
        output = run_hook(SEMANTIC_GUARD, {"stop_hook_active": True})
        self.assertEqual(output, {})


if __name__ == "__main__":
    unittest.main()
