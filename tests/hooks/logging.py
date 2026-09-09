"""Hook logging and transcript behavior tests."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .support import (
    AGENT_LOG,
    IMPORTER,
    MANIFEST_CHECKER,
    MANIFEST_HELPER,
    ROOT,
    ROOT_CONTEXT_COMPRESS,
    ROOT_HOOK_LOG,
    ROOT_IMPORTER,
    ROOT_MANIFEST_CHECKER,
    run_hook,
    write_sample_codex_transcript,
)


class AgentLogEventTest(unittest.TestCase):
    def test_root_pre_tool_use_wires_logging_before_hardening_gate(self) -> None:
        hooks = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        entries = hooks["hooks"]["PreToolUse"][0]["hooks"]
        commands = [entry["command"] for entry in entries]
        self.assertEqual(len(commands), 2)
        self.assertIn("agent_log_event.py", commands[0])
        self.assertIn("pre_tool_hardening_gate.py", commands[1])

    def test_root_hook_wired_from_session_start_config(self) -> None:
        hooks = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        for event, matchers in hooks["hooks"].items():
            for matcher in matchers:
                hooks_to_check = matcher.get("hooks") or []
                for entry in hooks_to_check:
                    command = entry.get("command", "")
                    if "agent_log_event.py" not in command:
                        continue
                    self.assertNotIn("template/.project-agent-workflow/hooks/agent_log_event.py", command)
                    self.assertIn(".project-agent-workflow/hooks/agent_log_event.py", command)

    def test_root_hook_logs_only_allowlisted_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            payload = {
                "prompt": "AWS_SECRET_ACCESS_KEY=must-not-persist",
                "tool_input": "cat /etc/passwd",
                "tool": "Bash",
                "tool_name": "Bash",
                "response": "tool output",
                "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
                "session_id": "session-metadata-root",
                "hook_event_name": "UserPromptSubmit",
                "tool_result": "should-not-log",
                "stop_hook_active": True,
            }
            output = run_hook(
                ROOT_HOOK_LOG,
                payload,
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "test-root-run"},
                args=["--event", "UserPromptSubmit"],
            )
            self.assertEqual(output, {})
            event_path = repo / ".agent-logs/test-root-run/raw/events.jsonl"
            manifest_path = repo / ".agent-logs/test-root-run/manifest.json"
            self.assertTrue(event_path.is_file())
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("raw/events.jsonl", manifest["raw_logs"])
            record = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["event"], "UserPromptSubmit")
            self.assertEqual(record["payload"]["session_id"], "session-metadata-root")
            self.assertEqual(record["payload"]["hook_event_name"], "UserPromptSubmit")
            self.assertEqual(record["payload"]["tool"], "Bash")
            self.assertTrue(record["payload"]["stop_hook_active"])
            self.assertNotIn("transcript_available", record["payload"])
            self.assertNotIn("prompt", record["payload"])
            self.assertNotIn("api_key", record["payload"])
            self.assertNotIn("tool_input", record["payload"])
            self.assertNotIn("tool_result", record["payload"])
            self.assertNotIn("response", record["payload"])
            self.assertNotIn("must-not-persist", event_path.read_text(encoding="utf-8"))

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
            resources = manifest["resource_observations"]
            self.assertEqual(resources["root_session_identity"]["status"], "observed")
            self.assertEqual(
                resources["metrics"]["tool_call_count"],
                {
                    "status": "observed",
                    "value": 0,
                    "provenance": "deterministic_proxy",
                },
            )
            self.assertEqual(
                resources["metrics"]["provider_input_tokens"]["status"],
                "not_observed",
            )

    def test_review_packet_start_records_bounded_turn_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            packet_digest = "sha256:" + "a" * 64
            run_hook(
                AGENT_LOG,
                {
                    "session_id": "review-session",
                    "hook_event_name": "ReviewPacketStart",
                    "review_packet_digest": packet_digest,
                    "inherited_turns": 0,
                    "prompt": "must not persist",
                },
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "review-turn-zero"},
                args=["--event", "ReviewPacketStart"],
            )
            event_path = repo / ".agent-logs/review-turn-zero/raw/events.jsonl"
            record = json.loads(event_path.read_text(encoding="utf-8"))
            self.assertEqual(record["event"], "ReviewPacketStart")
            self.assertEqual(record["payload"]["review_packet_digest"], packet_digest)
            self.assertEqual(record["payload"]["inherited_turns"], 0)
            self.assertEqual(record["payload"]["session_id"], "review-session")
            self.assertNotIn("prompt", record["payload"])
            checked = subprocess.run(
                ["python3", str(MANIFEST_CHECKER), str(
                    repo / ".agent-logs/review-turn-zero/manifest.json"
                )],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)

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
            resources = manifest["resource_observations"]
            self.assertEqual(
                resources["metrics"]["model_response_count"]["value"],
                1,
            )
            self.assertEqual(
                resources["metrics"]["tool_call_count"]["value"],
                0,
            )
            self.assertEqual(
                resources["metrics"]["provider_input_tokens"]["status"],
                "not_observed",
            )

    def test_importer_records_only_direct_provider_usage_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            source = Path(tmp) / "usage-session.jsonl"
            source.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "token_count",
                                    "session_id": "usage-session",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 120,
                                            "cached_input_tokens": 40,
                                            "output_tokens": 30,
                                            "reasoning_output_tokens": 10,
                                        }
                                    },
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "function_call",
                                    "name": "example",
                                    "arguments": json.dumps({"input_tokens": 999999}),
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(IMPORTER), str(source), "--run-id", "usage-run"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            resources = json.loads(
                (repo / ".agent-logs/usage-run/manifest.json").read_text(encoding="utf-8")
            )["resource_observations"]
            self.assertEqual(resources["root_session_identity"]["status"], "observed")
            self.assertEqual(resources["metrics"]["provider_input_tokens"]["value"], 120)
            self.assertEqual(resources["metrics"]["provider_cached_input_tokens"]["value"], 40)
            self.assertEqual(resources["metrics"]["provider_output_tokens"]["value"], 30)
            self.assertEqual(resources["metrics"]["provider_reasoning_tokens"]["value"], 10)
            self.assertEqual(resources["metrics"]["tool_call_count"]["value"], 1)

    def test_importer_preserves_review_packet_turn_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            source = Path(tmp) / "review-session.jsonl"
            packet_digest = "sha256:" + "b" * 64
            source.write_text(json.dumps({
                "timestamp": "2026-08-23T00:00:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "review_packet_start",
                    "session_id": "review-session",
                    "review_packet_digest": packet_digest,
                    "inherited_turns": 0,
                },
            }) + "\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(IMPORTER), str(source), "--run-id", "review-import"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(
                (repo / ".agent-logs/review-import/raw/transcript.jsonl").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(record["record_type"], "review_packet_start")
            self.assertEqual(record["metadata"]["review_packet_digest"], packet_digest)
            self.assertEqual(record["metadata"]["inherited_turns"], 0)
            self.assertEqual(record["metadata"]["session_id"], "review-session")

    def test_importer_overwrite_replaces_transcript_observations_from_normalized_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            source = Path(tmp) / "usage.jsonl"

            def write_usage(value: int) -> None:
                source.write_text(json.dumps({
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "internal_chat_message_metadata_passthrough": {
                            "session_id": "passthrough-session"
                        },
                        "info": {"total_token_usage": {"input_tokens": value}},
                    },
                }) + "\n", encoding="utf-8")

            write_usage(100)
            subprocess.run(
                ["python3", str(IMPORTER), str(source), "--run-id", "overwrite-run"],
                cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            write_usage(5)
            result = subprocess.run(
                [
                    "python3", str(IMPORTER), str(source), "--run-id", "overwrite-run",
                    "--overwrite",
                ],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = repo / ".agent-logs/overwrite-run"
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            resources = manifest["resource_observations"]
            self.assertEqual(resources["metrics"]["provider_input_tokens"]["value"], 5)
            self.assertEqual(
                resources["root_session_identity"]["digest"],
                "sha256:" + hashlib.sha256(b"passthrough-session").hexdigest(),
            )
            normalized = run_dir / "raw/transcript.jsonl"
            self.assertEqual(
                resources["evidence_digests"]["external_transcript"],
                "sha256:" + hashlib.sha256(normalized.read_bytes()).hexdigest(),
            )


class RootLoggingCliDelegationTest(unittest.TestCase):
    def test_root_importer_and_manifest_checker_self_tests(self) -> None:
        for command in (
            ["python3", str(ROOT_IMPORTER), "--self-test"],
            ["python3", str(ROOT_MANIFEST_CHECKER), "--self-test"],
        ):
            with self.subTest(command=command[1]):
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_root_context_compression_records_a_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            scripts = repo / "scripts"
            scripts.mkdir()
            shutil.copyfile(ROOT_CONTEXT_COMPRESS, scripts / "context-compress.sh")
            shutil.copyfile(ROOT_MANIFEST_CHECKER, scripts / "check-agent-log-manifest.py")
            template_scripts = repo / "template/.project-agent-workflow/scripts"
            template_scripts.mkdir(parents=True)
            shutil.copyfile(MANIFEST_HELPER, template_scripts / "agent_log_manifest.py")
            shutil.copyfile(MANIFEST_CHECKER, template_scripts / "check-agent-log-manifest.py")
            source = repo / "source.log"
            source.write_text("root context compression\n", encoding="utf-8")
            env = os.environ.copy()
            env["HEADROOM_DISABLED"] = "1"
            compress = subprocess.run(
                ["sh", "scripts/context-compress.sh", "source.log", "root-context-run"],
                cwd=repo,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(compress.returncode, 0, compress.stderr)
            manifest = repo / ".agent-logs/root-context-run/manifest.json"
            self.assertTrue(manifest.is_file())
            check = subprocess.run(
                ["python3", "scripts/check-agent-log-manifest.py", str(manifest)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)


class EvidenceDigestValidationTest(unittest.TestCase):
    def test_hook_binds_evidence_digest_to_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            run_hook(
                AGENT_LOG,
                {"session_id": "evidence-session"},
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "evidence-run"},
                args=["--event", "PreToolUse"],
            )
            manifest = json.loads(
                (repo / ".agent-logs/evidence-run/manifest.json").read_text(encoding="utf-8")
            )
            resources = manifest["resource_observations"]
            self.assertIn("evidence_digests", resources)
            self.assertIsNotNone(resources["evidence_digests"]["codex_hooks"])
            self.assertTrue(resources["evidence_digests"]["codex_hooks"].startswith("sha256:"))
            self.assertIsNone(resources["evidence_digests"]["external_transcript"])

    def test_importer_binds_evidence_digest_to_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            source = Path(tmp) / "session.jsonl"
            write_sample_codex_transcript(source)
            subprocess.run(
                ["python3", str(IMPORTER), str(source), "--run-id", "digest-run"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            manifest = json.loads(
                (repo / ".agent-logs/digest-run/manifest.json").read_text(encoding="utf-8")
            )
            resources = manifest["resource_observations"]
            self.assertIsNotNone(resources["evidence_digests"]["external_transcript"])
            self.assertTrue(resources["evidence_digests"]["external_transcript"].startswith("sha256:"))

    def test_checker_rejects_fabricated_identity_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            run_hook(
                AGENT_LOG,
                {"session_id": "fabricated-session"},
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "fabricated-run"},
                args=["--event", "SessionStart"],
            )
            manifest_path = repo / ".agent-logs/fabricated-run/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["resource_observations"]["evidence_digests"] = {
                "external_transcript": None,
                "codex_hooks": None,
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(MANIFEST_CHECKER), str(manifest_path)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bound evidence digest", result.stderr)

    def test_checker_rejects_mismatched_evidence_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
            run_hook(
                AGENT_LOG,
                {"session_id": "mismatch-session"},
                cwd=repo,
                env={"CODEX_AGENT_LOG_RUN_ID": "mismatch-run"},
                args=["--event", "SessionStart"],
            )
            manifest_path = repo / ".agent-logs/mismatch-run/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["resource_observations"]["evidence_digests"]["codex_hooks"] = "sha256:" + "f" * 64
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(MANIFEST_CHECKER), str(manifest_path)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("recomputed source file digest", result.stderr)



if __name__ == "__main__":
    unittest.main()
