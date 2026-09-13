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
    load_manifest_helper,
    run_hook,
    write_model_evidence_codex_transcript,
    write_sample_codex_transcript,
)


def import_run(repo: Path, source: Path, run_id: str, *extra: str) -> dict:
    """Import one transcript and return the manifest the importer wrote."""

    result = subprocess.run(
        ["python3", str(IMPORTER), str(source), "--run-id", run_id, *extra],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(
        (repo / f".agent-logs/{run_id}/manifest.json").read_text(encoding="utf-8")
    )


def git_repo(tmp: str, name: str = "repo") -> Path:
    repo = Path(tmp) / name
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True)
    return repo


def statement_values(manifest: dict, attribute: str) -> list[tuple]:
    return [
        (item["evidence_class"], item["value"], item["turn_id"], item["root_turn_id"])
        for item in manifest["model_observations"]["statements"]
        if item["attribute"] == attribute
    ]


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

    def test_hooks_record_bounded_runtime_reported_model_metadata(self) -> None:
        for label, hook in (("generated", AGENT_LOG), ("root", ROOT_HOOK_LOG)):
            with self.subTest(hook=label), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                subprocess.run(
                    ["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True
                )
                run_hook(
                    hook,
                    {
                        "session_id": "hook-session",
                        "model": "example-hook-model",
                        "effort": "high",
                        "prompt": "AWS_SECRET_ACCESS_KEY=must-not-persist",
                    },
                    cwd=repo,
                    env={"CODEX_AGENT_LOG_RUN_ID": f"model-hook-{label}"},
                    args=["--event", "UserPromptSubmit"],
                )
                run_dir = repo / f".agent-logs/model-hook-{label}"
                record = json.loads(
                    (run_dir / "raw/events.jsonl").read_text(encoding="utf-8").splitlines()[0]
                )
                observation = record["payload"]["model_observation"]
                self.assertEqual(observation["schema_version"], 1)
                self.assertEqual(observation["source_kind"], "hook_event_metadata")
                self.assertEqual(
                    observation["attributes"]["model"]["runtime_reported"],
                    {"status": "observed", "value": "example-hook-model"},
                )
                self.assertEqual(
                    observation["attributes"]["model"]["requested"],
                    {"status": "not_observed", "value": None},
                )
                self.assertEqual(
                    observation["attributes"]["model"]["provider_reported"],
                    {"status": "not_observed", "value": None},
                )
                self.assertEqual(
                    observation["provider_context"]["model_provider"]["status"], "not_observed"
                )
                summary = json.loads(
                    (run_dir / "manifest.json").read_text(encoding="utf-8")
                )["model_observations"]
                self.assertEqual(
                    sorted((item["attribute"], item["value"]) for item in summary["statements"]),
                    [("model", "example-hook-model"), ("reasoning_effort", "high")],
                )
                self.assertEqual(summary["coverage"]["codex_hooks"]["status"], "present")
                self.assertEqual(summary["coverage"]["external_transcript"]["status"], "missing")
                self.assertNotIn("must-not-persist", (run_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_hooks_leave_unavailable_model_metadata_unobserved(self) -> None:
        for label, hook in (("generated", AGENT_LOG), ("root", ROOT_HOOK_LOG)):
            with self.subTest(hook=label), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                subprocess.run(
                    ["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True
                )
                run_hook(
                    hook,
                    {"session_id": "quiet-session", "model": ["unsupported"]},
                    cwd=repo,
                    env={"CODEX_AGENT_LOG_RUN_ID": f"quiet-{label}"},
                    args=["--event", "PreToolUse"],
                )
                run_dir = repo / f".agent-logs/quiet-{label}"
                record = json.loads(
                    (run_dir / "raw/events.jsonl").read_text(encoding="utf-8").splitlines()[0]
                )
                # A non-string model never reaches the allowlisted metadata, so
                # the hook has nothing to report rather than something to guess.
                self.assertNotIn("model", record["payload"])
                self.assertNotIn("model_observation", record["payload"])
                summary = json.loads(
                    (run_dir / "manifest.json").read_text(encoding="utf-8")
                )["model_observations"]
                self.assertEqual(summary["statements"], [])
                self.assertEqual(summary["identity_counts"], {"session_digests": 0, "turn_ids": 0})

    def test_hooks_drop_a_model_value_the_contract_refuses(self) -> None:
        for label, hook in (("generated", AGENT_LOG), ("root", ROOT_HOOK_LOG)):
            with self.subTest(hook=label), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                subprocess.run(
                    ["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True
                )
                run_hook(
                    hook,
                    {"session_id": "s", "model": "m" * 200, "effort": "sk-" + "a" * 20},
                    cwd=repo,
                    env={"CODEX_AGENT_LOG_RUN_ID": f"refused-{label}"},
                    args=["--event", "UserPromptSubmit"],
                )
                run_dir = repo / f".agent-logs/refused-{label}"
                events = (run_dir / "raw/events.jsonl").read_text(encoding="utf-8")
                payload = json.loads(events.splitlines()[0])["payload"]
                # A refused value is not evidence, so it is not retained raw
                # either; otherwise these keys become a storage channel.
                self.assertNotIn("model", payload)
                self.assertNotIn("effort", payload)
                self.assertNotIn("m" * 200, events)
                self.assertNotIn("sk-" + "a" * 20, events)
                summary = json.loads(
                    (run_dir / "manifest.json").read_text(encoding="utf-8")
                )["model_observations"]
                self.assertEqual(summary["statements"], [])
                self.assertEqual(
                    sorted(summary["diagnostics"]), ["redacted_value", "value_too_long"]
                )

    def test_hooks_report_an_unreadable_source_without_unverifiable_evidence(self) -> None:
        for label, hook in (("generated", AGENT_LOG), ("root", ROOT_HOOK_LOG)):
            with self.subTest(hook=label), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                subprocess.run(
                    ["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True
                )
                run_id = f"unreadable-{label}"
                env = {"CODEX_AGENT_LOG_RUN_ID": run_id}
                run_hook(hook, {"session_id": "s", "model": "first-model"}, cwd=repo,
                         env=env, args=["--event", "UserPromptSubmit"])
                run_dir = repo / f".agent-logs/{run_id}"
                manifest_path = run_dir / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                transcript = run_dir / "raw/transcript.jsonl"
                transcript.write_bytes(b"\xff\xfe not utf-8\n")
                manifest["transcript_log"] = "raw/transcript.jsonl"
                manifest["raw_logs"] = sorted(
                    set(manifest["raw_logs"]) | {"raw/transcript.jsonl"}
                )
                manifest["coverage"]["external_transcript"] = {
                    "status": "present",
                    "redaction_status": "redacted",
                }
                manifest["missing_sources"] = [
                    item for item in manifest["missing_sources"] if item != "external_transcript"
                ]
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                transcript.chmod(0o000)
                try:
                    run_hook(hook, {"session_id": "s", "model": "second-model"}, cwd=repo,
                             env=env, args=["--event", "PostToolUse"])
                finally:
                    transcript.chmod(0o644)
                summary = json.loads(manifest_path.read_text(encoding="utf-8"))[
                    "model_observations"
                ]
                self.assertEqual(
                    summary["coverage"]["external_transcript"]["status"], "unreadable"
                )
                self.assertIsNone(summary["evidence_digests"]["external_transcript"])
                self.assertIn("source_unreadable", summary["diagnostics"])
                # The hook evidence that is still readable is not discarded.
                self.assertEqual(
                    [item["value"] for item in summary["statements"]],
                    ["first-model", "second-model"],
                )

    def test_hook_model_summary_survives_appended_events_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(
                ["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True
            )
            env = {"CODEX_AGENT_LOG_RUN_ID": "append-model"}
            for model in ("first-hook-model", "second-hook-model"):
                run_hook(
                    AGENT_LOG,
                    {"session_id": "append-session", "model": model},
                    cwd=repo,
                    env=env,
                    args=["--event", "UserPromptSubmit"],
                )
            run_dir = repo / ".agent-logs/append-model"
            summary = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))[
                "model_observations"
            ]
            self.assertEqual(
                [(item["record_line"], item["value"]) for item in summary["statements"]],
                [(1, "first-hook-model"), (2, "second-hook-model")],
            )
            self.assertEqual(
                summary["evidence_digests"]["codex_hooks"],
                "sha256:"
                + hashlib.sha256((run_dir / "raw/events.jsonl").read_bytes()).hexdigest(),
            )
            self.assertEqual(summary["coverage"]["codex_hooks"]["records_scanned"], 2)


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

    def test_importer_retains_runtime_reported_model_for_each_execution_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            manifest = import_run(repo, source, "model-run")
            summary = manifest["model_observations"]
            self.assertEqual(summary["schema_version"], 1)
            self.assertEqual(
                statement_values(manifest, "model"),
                [
                    ("runtime_reported", "example-model-a", "turn-1", "turn-1"),
                    ("runtime_reported", "example-model-b", "turn-2", "turn-1"),
                    ("runtime_reported", "example-model-c", "turn-child", None),
                ],
            )
            self.assertEqual(
                [value for _, value, _, _ in statement_values(manifest, "reasoning_effort")],
                ["medium", "high", "low"],
            )
            # A model change between turns is a legitimate change, and the
            # interleaved child session is a separate scope. Neither may be
            # collapsed into one model for the whole run.
            self.assertEqual(summary["identity_counts"]["session_digests"], 2)
            self.assertEqual(summary["identity_counts"]["turn_ids"], 4)
            self.assertEqual(
                summary["provider_context"]["model_provider"]["values"], ["example-provider"]
            )
            self.assertEqual(summary["provider_context"]["cli_version"]["values"], ["0.154.0"])
            self.assertFalse(summary["truncated"])
            for statement in summary["statements"]:
                self.assertEqual(statement["source"], "external_transcript")
                self.assertTrue(statement["session_digest"] is None or statement["session_digest"].startswith("sha256:"))
            self.assertEqual(
                summary["evidence_digests"]["external_transcript"],
                "sha256:"
                + hashlib.sha256(
                    (repo / ".agent-logs/model-run/raw/transcript.jsonl").read_bytes()
                ).hexdigest(),
            )
            self.assertIsNone(summary["evidence_digests"]["codex_hooks"])

    def test_importer_keeps_requested_and_provider_reported_slots_unobserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            import_run(repo, source, "slot-run")
            records = [
                json.loads(line)
                for line in (repo / ".agent-logs/slot-run/raw/transcript.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            observed = [
                record["metadata"]["model_observation"]
                for record in records
                if "model_observation" in record["metadata"]
            ]
            self.assertTrue(observed)
            for observation in observed:
                for attribute in ("model", "reasoning_effort"):
                    classes = observation["attributes"][attribute]
                    self.assertEqual(classes["requested"]["status"], "not_observed")
                    self.assertEqual(classes["provider_reported"]["status"], "not_observed")
            provider_record = observed[0]
            self.assertEqual(provider_record["source_kind"], "transcript_session_meta")
            self.assertEqual(
                provider_record["provider_context"]["model_provider"]["value"],
                "example-provider",
            )

    def test_importer_leaves_unsupported_model_evidence_unobserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "unsupported.jsonl"
            source.write_text(
                "\n".join(
                    json.dumps(record)
                    for record in (
                        {"type": "turn_context", "payload": {"model": 5, "turn_id": "t-1"}},
                        {"type": "turn_context", "payload": {"model": "   ", "turn_id": "t-2"}},
                        {"type": "turn_context", "payload": {"model": "m" * 200, "turn_id": "t-3"}},
                        {"type": "session_meta", "payload": {"id": "s-1"}},
                        {"type": "unknown_shape", "payload": {"model": "not-a-source"}},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = import_run(repo, source, "unsupported-run")
            summary = manifest["model_observations"]
            self.assertEqual(summary["statements"], [])
            self.assertEqual(
                sorted(summary["diagnostics"]),
                ["malformed_value", "unsupported_type", "value_too_long"],
            )
            self.assertEqual(
                summary["provider_context"]["model_provider"]["status"], "not_observed"
            )
            self.assertNotIn("not-a-source", json.dumps(summary))

    def test_importer_does_not_carry_a_model_across_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            import_run(repo, source, "carry-run")
            records = [
                json.loads(line)
                for line in (repo / ".agent-logs/carry-run/raw/transcript.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            # The assistant message between the two turn contexts reports no
            # model of its own, so it must not inherit the preceding one.
            assistant = records[2]
            self.assertEqual(assistant["role"], "assistant")
            self.assertNotIn("model_observation", assistant["metadata"])

    def test_importer_refuses_a_secret_like_model_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "secret.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "type": "turn_context",
                        "payload": {
                            "model": "sk-abcdefghijklmnopqrstuvwxyz",
                            "turn_id": "t-1",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = import_run(repo, source, "secret-run")
            summary = manifest["model_observations"]
            # Substituting a redaction marker and keeping the slot observed
            # would publish a model identifier no source ever reported, so the
            # value is refused outright instead.
            self.assertEqual(summary["statements"], [])
            self.assertIn("redacted_value", summary["diagnostics"])
            transcript = (repo / ".agent-logs/secret-run/raw/transcript.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", transcript)
            self.assertNotIn("[REDACTED]", json.dumps(summary))

    def test_importer_refuses_an_oversized_model_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "long.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "type": "turn_context",
                        "payload": {"model": "m" * 200, "turn_id": "t-1"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = import_run(repo, source, "long-run")["model_observations"]
            self.assertEqual(summary["statements"], [])
            self.assertIn("value_too_long", summary["diagnostics"])

    def test_repeated_import_preserves_model_evidence_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            first = import_run(repo, source, "repeat-run")
            transcript = repo / ".agent-logs/repeat-run/raw/transcript.jsonl"
            original_bytes = transcript.read_bytes()
            second = import_run(repo, source, "repeat-run")
            self.assertEqual(transcript.read_bytes(), original_bytes)
            self.assertEqual(first["model_observations"], second["model_observations"])
            self.assertEqual(len(second["model_observations"]["statements"]), 6)

    def test_overwrite_import_recomputes_model_evidence_from_new_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "replaced.jsonl"
            source.write_text(
                json.dumps(
                    {"type": "turn_context", "payload": {"model": "first-model", "turn_id": "t-1"}}
                )
                + "\n",
                encoding="utf-8",
            )
            import_run(repo, source, "overwrite-model")
            source.write_text(
                json.dumps(
                    {"type": "turn_context", "payload": {"model": "second-model", "turn_id": "t-9"}}
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = import_run(repo, source, "overwrite-model", "--overwrite")
            summary = manifest["model_observations"]
            self.assertEqual(
                [item["value"] for item in summary["statements"]], ["second-model"]
            )
            self.assertEqual(
                summary["evidence_digests"]["external_transcript"],
                "sha256:"
                + hashlib.sha256(
                    (repo / ".agent-logs/overwrite-model/raw/transcript.jsonl").read_bytes()
                ).hexdigest(),
            )

    def test_model_evidence_does_not_reattribute_aggregate_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "usage-and-model.jsonl"
            source.write_text(
                "\n".join(
                    json.dumps(record)
                    for record in (
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "session_id": "usage-session",
                                "info": {"total_token_usage": {"input_tokens": 120}},
                            },
                        },
                        {
                            "type": "turn_context",
                            "payload": {"model": "usage-model", "turn_id": "t-1"},
                        },
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = import_run(repo, source, "usage-model-run")
            resources = manifest["resource_observations"]
            self.assertEqual(resources["schema_version"], 1)
            self.assertEqual(resources["metrics"]["provider_input_tokens"]["value"], 120)
            # No model statement may carry or receive a token value.
            self.assertNotIn("provider_input_tokens", json.dumps(manifest["model_observations"]))
            for statement in manifest["model_observations"]["statements"]:
                self.assertEqual(
                    set(statement),
                    {
                        "source",
                        "record_line",
                        "source_line",
                        "source_kind",
                        "attribute",
                        "evidence_class",
                        "value",
                        "session_digest",
                        "turn_id",
                        "root_turn_id",
                    },
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

    def test_root_and_template_importers_produce_the_same_model_summary(self) -> None:
        summaries = []
        for label, importer in (("template", IMPORTER), ("root", ROOT_IMPORTER)):
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                repo.mkdir()
                subprocess.run(
                    ["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL, check=True
                )
                source = Path(tmp) / "model-session.jsonl"
                write_model_evidence_codex_transcript(source)
                result = subprocess.run(
                    ["python3", str(importer), str(source), "--run-id", "parity-run"],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, f"{label}: {result.stderr}")
                summaries.append(
                    json.loads(
                        (repo / ".agent-logs/parity-run/manifest.json").read_text(encoding="utf-8")
                    )["model_observations"]
                )
        self.assertEqual(summaries[0], summaries[1])

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

    def test_checker_accepts_a_legacy_manifest_without_model_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "session.jsonl"
            write_sample_codex_transcript(source)
            import_run(repo, source, "legacy-run")
            manifest_path = repo / ".agent-logs/legacy-run/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("model_observations", None)
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
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_checker_rejects_model_evidence_after_source_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            import_run(repo, source, "tampered-run")
            transcript = repo / ".agent-logs/tampered-run/raw/transcript.jsonl"
            transcript.write_text(
                transcript.read_text(encoding="utf-8").replace(
                    "example-model-a", "example-model-z"
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3",
                    str(MANIFEST_CHECKER),
                    str(repo / ".agent-logs/tampered-run/manifest.json"),
                ],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("recomputed source file digest", result.stderr)

    def test_checker_rejects_a_model_statement_without_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            import_run(repo, source, "unbound-run")
            manifest_path = repo / ".agent-logs/unbound-run/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["model_observations"]["evidence_digests"]["external_transcript"] = None
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

    def test_a_source_cannot_report_evidence_its_shape_never_observes(self) -> None:
        helper = load_manifest_helper()
        observation = helper.build_model_observation(
            "transcript_turn_context",
            requested_model="requested-model",
            runtime_model="runtime-model",
            session_id="disagreement-session",
            turn_id="turn-1",
        )
        # A turn context reports what the runtime used. It never carries the
        # caller's request, so the producer leaves that slot unobserved
        # instead of copying a value the source never reported.
        self.assertEqual(
            observation["attributes"]["model"]["requested"],
            {"status": "not_observed", "value": None},
        )
        self.assertEqual(
            observation["attributes"]["model"]["runtime_reported"],
            {"status": "observed", "value": "runtime-model"},
        )
        forged = json.loads(json.dumps(observation))
        forged["attributes"]["model"]["requested"] = {
            "status": "observed",
            "value": "requested-model",
        }
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "disagreement"
            (run_dir / "raw").mkdir(parents=True)
            transcript = run_dir / "raw/transcript.jsonl"
            manifest = {"transcript_log": "raw/transcript.jsonl", "hook_event_log": None}

            def write(value: dict[str, object]) -> None:
                transcript.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "record_type": "system_event",
                            "created_at": "2026-09-01T00:00:00Z",
                            "run_id": "disagreement",
                            "turn_id": "turn-1",
                            "role": "system_event",
                            "content": "",
                            "metadata": {
                                "source_line": 1,
                                "source_type": "turn_context",
                                "payload_type": "turn_context",
                                "model_observation": value,
                            },
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            write(observation)
            summary = helper.compute_model_observations(run_dir, manifest)
            self.assertEqual(
                [
                    (item["evidence_class"], item["value"])
                    for item in summary["statements"]
                    if item["attribute"] == "model"
                ],
                [("runtime_reported", "runtime-model")],
            )
            # Two statements about one turn are one execution scope, not two.
            self.assertEqual(summary["identity_counts"], {"session_digests": 1, "turn_ids": 1})

            write(forged)
            forged_summary = helper.compute_model_observations(run_dir, manifest)
            self.assertEqual(forged_summary["statements"], [])
            self.assertEqual(
                forged_summary["coverage"]["external_transcript"][
                    "records_with_model_observation"
                ],
                0,
            )
            self.assertIn("unknown_source_shape", forged_summary["diagnostics"])

    def test_a_drifted_stored_observation_is_refused_whole(self) -> None:
        helper = load_manifest_helper()
        base = helper.build_model_observation(
            "transcript_turn_context", runtime_model="m-1", session_id="s", turn_id="t"
        )
        self.assertIsNotNone(helper.read_model_observation(base))

        def drifted(mutate) -> dict[str, object]:
            value = json.loads(json.dumps(base))
            mutate(value)
            return value

        mutations = {
            "unexpected top-level field": lambda v: v.__setitem__("extra", 1),
            "padded value": lambda v: v["attributes"]["model"]["runtime_reported"].__setitem__(
                "value", " m-1 "
            ),
            "secret value": lambda v: v["attributes"]["model"]["runtime_reported"].__setitem__(
                "value", "sk-" + "a" * 20
            ),
            "redaction marker": lambda v: v["attributes"]["model"]["runtime_reported"].__setitem__(
                "value", helper.REDACTION_MARKER
            ),
            "control character": lambda v: v["attributes"]["model"][
                "runtime_reported"
            ].__setitem__("value", "m\x001"),
            "evidence the shape cannot observe": lambda v: v["attributes"]["model"].__setitem__(
                "requested", {"status": "observed", "value": "r"}
            ),
        }
        for reason, mutate in mutations.items():
            with self.subTest(reason=reason):
                self.assertIsNone(helper.read_model_observation(drifted(mutate)))

    def test_an_observation_is_bound_to_the_shape_its_record_reports(self) -> None:
        helper = load_manifest_helper()
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "shapes.jsonl"
            source.write_text(
                "\n".join(
                    json.dumps(value)
                    for value in (
                        {
                            "type": "session_meta",
                            "payload": {
                                "id": "s-1",
                                "model_provider": "acme",
                                "cli_version": "9.9.9",
                            },
                        },
                        {
                            "type": "turn_context",
                            "payload": {
                                "model": "m-1",
                                "effort": "high",
                                "turn_id": "t-1",
                            },
                        },
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = import_run(repo, source, "shapes")
            run_dir = repo / ".agent-logs/shapes"
            lines = (run_dir / "raw/transcript.jsonl").read_text(encoding="utf-8").splitlines()
            stored = [
                json.loads(line)["metadata"]["model_observation"]
                for line in lines
                if "model_observation" in json.loads(line)["metadata"]
            ]
            self.assertEqual(
                [item["source_kind"] for item in stored],
                ["transcript_session_meta", "transcript_turn_context"],
            )
            # The session reported the provider. The turn reported the model.
            # Neither record's observation borrows the other's authority.
            self.assertEqual(
                stored[1]["provider_context"]["model_provider"],
                {"status": "not_observed", "value": None},
            )
            summary = manifest["model_observations"]
            self.assertEqual(summary["provider_context"]["model_provider"]["values"], ["acme"])
            self.assertEqual(
                {item["source_kind"] for item in summary["statements"]},
                {"transcript_turn_context"},
            )

            # A turn record cannot carry a session observation, so provider
            # context cannot be smuggled in under a second source kind.
            record = json.loads(lines[1])
            record["metadata"]["model_observation"] = json.loads(json.dumps(stored[0]))
            (run_dir / "raw/transcript.jsonl").write_text(
                lines[0] + "\n" + json.dumps(record, sort_keys=True) + "\n", encoding="utf-8"
            )
            recomputed = helper.compute_model_observations(
                run_dir, {"transcript_log": "raw/transcript.jsonl", "hook_event_log": None}
            )
            self.assertEqual(recomputed["statements"], [])
            self.assertEqual(recomputed["provider_context"]["model_provider"]["values"], ["acme"])
            self.assertEqual(
                recomputed["coverage"]["external_transcript"]["records_with_model_observation"], 1
            )
            self.assertIn("unknown_source_shape", recomputed["diagnostics"])

    def test_a_hook_record_cannot_claim_provider_context(self) -> None:
        helper = load_manifest_helper()
        observation = helper.build_model_observation(
            "hook_event_metadata",
            runtime_model="m-1",
            model_provider="acme",
            session_id="s",
            turn_id="t",
        )
        # A hook event sees the runtime statement and the session it ran in.
        # It never sees the provider name or the turn identity, so those slots
        # are not filled even when a caller supplies a value.
        self.assertEqual(
            observation["provider_context"]["model_provider"],
            {"status": "not_observed", "value": None},
        )
        self.assertEqual(
            observation["execution_scope"]["turn_id"],
            {"status": "not_observed", "value": None},
        )
        forged = json.loads(json.dumps(observation))
        forged["provider_context"]["model_provider"] = {"status": "observed", "value": "acme"}
        self.assertIsNone(helper.read_model_observation(forged))

    def test_a_dropped_provider_value_is_reported(self) -> None:
        helper = load_manifest_helper()
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "many-providers.jsonl"
            source.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "type": "session_meta",
                            "payload": {"id": "s", "model_provider": f"provider-{index}"},
                        }
                    )
                    for index in range(helper.MAX_MODEL_PROVIDER_VALUES + 3)
                )
                + "\n",
                encoding="utf-8",
            )
            summary = import_run(repo, source, "many-providers")["model_observations"]
            self.assertEqual(
                len(summary["provider_context"]["model_provider"]["values"]),
                helper.MAX_MODEL_PROVIDER_VALUES,
            )
            self.assertIn("provider_context_truncated", summary["diagnostics"])

    def test_summary_is_absent_when_no_source_file_exists(self) -> None:
        helper = load_manifest_helper()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(
                helper.compute_model_observations(
                    Path(tmp), {"transcript_log": None, "hook_event_log": None}
                )
            )

    def _reject_mutated_model_summary(self, mutate) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "model-session.jsonl"
            write_model_evidence_codex_transcript(source)
            import_run(repo, source, "mutate-run")
            run_dir = repo / ".agent-logs/mutate-run"
            manifest_path = run_dir / "manifest.json"
            accepted = subprocess.run(
                ["python3", str(MANIFEST_CHECKER), str(manifest_path)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            mutate(manifest, run_dir)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = subprocess.run(
                ["python3", str(MANIFEST_CHECKER), str(manifest_path)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(rejected.returncode, 0, "mutation was accepted")
            return rejected.stderr

    def test_checker_rejects_a_summary_that_omits_source_evidence(self) -> None:
        def drop_everything(manifest, _run_dir):
            summary = manifest["model_observations"]
            summary["statements"] = []
            summary["identity_counts"] = {"session_digests": 0, "turn_ids": 0}
            summary["provider_context"] = {
                field: {"status": "not_observed", "values": []}
                for field in summary["provider_context"]
            }

        self.assertIn("recomputed", self._reject_mutated_model_summary(drop_everything))

    def test_checker_rejects_a_forged_truncation_flag(self) -> None:
        self.assertIn(
            "truncated statement list",
            self._reject_mutated_model_summary(
                lambda manifest, _run_dir: manifest["model_observations"].__setitem__(
                    "truncated", True
                )
            ),
        )

    def test_checker_rejects_a_statement_backed_only_by_a_malformed_observation(self) -> None:
        def forge(manifest, run_dir):
            transcript = run_dir / "raw/transcript.jsonl"
            lines = transcript.read_text(encoding="utf-8").splitlines()
            record = json.loads(lines[0])
            # A dictionary that does not match the observation contract must
            # not be usable as backing for an invented statement.
            record["metadata"]["model_observation"] = {"source_kind": "hook_event_metadata"}
            lines[0] = json.dumps(record, sort_keys=True)
            transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
            digest = "sha256:" + hashlib.sha256(transcript.read_bytes()).hexdigest()
            manifest["model_observations"]["evidence_digests"]["external_transcript"] = digest
            manifest["resource_observations"]["evidence_digests"]["external_transcript"] = digest
            manifest["model_observations"]["statements"] = [
                {
                    "source": "external_transcript",
                    "record_line": 1,
                    "source_line": 1,
                    "source_kind": "hook_event_metadata",
                    "attribute": "model",
                    "evidence_class": "provider_reported",
                    "value": "forged-provider-model",
                    "session_digest": None,
                    "turn_id": None,
                    "root_turn_id": None,
                }
            ]
            manifest["model_observations"]["identity_counts"] = {
                "session_digests": 0,
                "turn_ids": 0,
            }

        self.assertIn("recomputed", self._reject_mutated_model_summary(forge))

    def test_summary_refuses_a_value_that_would_need_trimming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "spaced.jsonl"
            source.write_text(
                json.dumps(
                    {"type": "turn_context", "payload": {"model": " gpt-x \n", "turn_id": "t1"}}
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = import_run(repo, source, "spaced-run")
            summary = manifest["model_observations"]
            # Trimming would report an identifier the source never wrote.
            self.assertEqual(summary["statements"], [])
            self.assertIn("malformed_value", summary["diagnostics"])

    def test_checker_accepts_every_producer_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp)
            source = Path(tmp) / "diagnostics.jsonl"
            source.write_text(
                "\n".join(
                    json.dumps(record)
                    for record in (
                        {"type": "turn_context", "payload": {"model": "sk-" + "a" * 20}},
                        {"type": "turn_context", "payload": {"model": "m" * 200}},
                        {"type": "turn_context", "payload": {"model": ["unsupported"]}},
                        {"type": "turn_context", "payload": {"model": " spaced "}},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            summary = import_run(repo, source, "diag-run")["model_observations"]
            self.assertEqual(
                sorted(summary["diagnostics"]),
                ["malformed_value", "redacted_value", "unsupported_type", "value_too_long"],
            )
            result = subprocess.run(
                ["python3", str(MANIFEST_CHECKER), str(repo / ".agent-logs/diag-run/manifest.json")],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_oversized_source_is_never_read_or_bound(self) -> None:
        helper = load_manifest_helper()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "oversized"
            (run_dir / "raw").mkdir(parents=True)
            transcript = run_dir / "raw/transcript.jsonl"
            with transcript.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps({"metadata": {"source_line": 1}}) + "\n")
                handle.write("#" + "p" * (helper.MAX_MODEL_SOURCE_BYTES + 1) + "\n")
            summary = helper.compute_model_observations(
                run_dir, {"transcript_log": "raw/transcript.jsonl", "hook_event_log": None}
            )
            self.assertEqual(
                summary["coverage"]["external_transcript"],
                {"status": "unreadable", "records_scanned": 0, "records_with_model_observation": 0},
            )
            self.assertIsNone(summary["evidence_digests"]["external_transcript"])
            self.assertIn("source_too_large", summary["diagnostics"])

    def test_a_source_that_is_not_utf8_is_reported_unreadable(self) -> None:
        helper = load_manifest_helper()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "binary"
            (run_dir / "raw").mkdir(parents=True)
            (run_dir / "raw/events.jsonl").write_bytes(b"\xff\xfe\n")
            summary = helper.compute_model_observations(
                run_dir, {"transcript_log": None, "hook_event_log": "raw/events.jsonl"}
            )
            self.assertEqual(summary["coverage"]["codex_hooks"]["status"], "unreadable")
            self.assertIsNone(summary["evidence_digests"]["codex_hooks"])
            self.assertEqual(summary["statements"], [])
            self.assertIn("source_unreadable", summary["diagnostics"])



if __name__ == "__main__":
    unittest.main()
