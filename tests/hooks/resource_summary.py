"""Local run-resource summary behavior tests."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import (
    ROOT,
    build_model_observations,
    load_manifest_helper,
    write_model_evidence_hook_log,
    write_model_evidence_imported_log,
)


SUMMARY = ROOT / "template/.project-agent-workflow/scripts/summarize-agent-run.py"
ROOT_SUMMARY = ROOT / "scripts/summarize-agent-run.py"

RESOURCE_METRICS = (
    "provider_input_tokens",
    "provider_cached_input_tokens",
    "provider_output_tokens",
    "provider_reasoning_tokens",
    "model_response_count",
    "compaction_count",
    "helper_turn_count",
    "tool_call_count",
)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def not_observed_metrics() -> dict[str, dict[str, object]]:
    return {
        metric: {"status": "not_observed", "value": None, "provenance": "not_observed"}
        for metric in RESOURCE_METRICS
    }


def run_manifest(
    run_id: str = "run-a",
    *,
    metrics: dict[str, dict[str, object]] | None = None,
    evidence: dict[str, str | None] | None = None,
    session_digest: str | None = "sha256:" + "a" * 64,
    billed_cost: object = None,
) -> dict[str, object]:
    observations: dict[str, object] = {
        "schema_version": 1,
        "root_session_identity": (
            {"status": "observed", "digest": session_digest}
            if session_digest
            else {"status": "not_observed", "digest": None}
        ),
        "evidence_digests": evidence
        or {"external_transcript": None, "codex_hooks": "sha256:" + "b" * 64},
        "metrics": metrics or not_observed_metrics(),
    }
    if billed_cost is not None:
        observations["billed_cost"] = billed_cost
    return {"run_id": run_id, "resource_observations": observations}


def candidate_manifest(
    *,
    run_id: str = "orch-1",
    attempt: str = "attempt-1",
    patch_digest: str = "c" * 64,
    runner_duration: float = 12.5,
    attempt_durations: list[float] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "orchestration_run_id": run_id,
        "plan_execution_attempt_id": attempt,
        "patch_digest": patch_digest,
        "plan_path": "docs/plan/active/277-example.md",
        "telemetry": {
            "schema_version": 1,
            "attempt_durations_seconds": [4.0, 6.0] if attempt_durations is None else attempt_durations,
            "runner_duration_seconds": runner_duration,
            "model_starts": 1,
            "availability_failures": 0,
            "skipped_known_unavailable_starts": 0,
            "candidate_generations": 1,
            "full_validation_count": 0,
            "authoritative_validation_count": 0,
            "focused_validation_count": 0,
            "parent_review_rejections": 0,
            "correction_round": 0,
            "implementation_risk": "ordinary",
            "implementation_ambiguity": "low",
        },
    }


def execution_state(
    *,
    run_id: str = "exec-1",
    state: str = "descope_pending",
    elapsed: list[float] | None = None,
) -> dict[str, object]:
    events: list[dict[str, object]] = [
        {"event_type": "candidate_generation", "sequence": 1},
    ]
    for index, value in enumerate(elapsed or [30.0], start=2):
        events.append(
            {"event_type": "elapsed_checkpoint", "sequence": index, "elapsed_seconds": value}
        )
    return {
        "schema_version": 6,
        "run_id": run_id,
        "plan_path": "docs/plan/active/277-example.md",
        "state": state,
        "genesis_digest": "d" * 64,
        "events": events,
        "candidate_generations": 1,
        "correction_rounds": 0,
        "parent_direct_remediation_rounds": 1,
        "focused_validation_events": 1,
        "authoritative_validation_events": 0,
        "repair_reason_codes": [],
        "replan_reason_codes": [],
        "descope_reason_codes": [],
        "descope_pending_reason_codes": ["parent_remediation_budget_exhausted"],
        "review_reason_codes": [],
    }


def model_evidence_manifest(
    root: Path,
    run_id: str = "run-a",
    *,
    transcript: str | None = "imported.jsonl",
    hook_log: str | None = "hooks.jsonl",
) -> dict[str, object]:
    """Build a run manifest whose model observations come from the producer."""

    if transcript is not None:
        write_model_evidence_imported_log(root / transcript)
    if hook_log is not None:
        write_model_evidence_hook_log(root / hook_log)
    observations = build_model_observations(root, transcript=transcript, hook_log=hook_log)
    manifest = run_manifest(run_id)
    manifest["model_observations"] = observations
    # A real manifest names the sources it was derived from, and verification
    # depends on that declaration rather than on the summary.
    manifest["transcript_log"] = transcript
    manifest["hook_event_log"] = hook_log
    return manifest


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def run_summary(*args: str, command: Path = SUMMARY) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(command), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class ResourceSummaryTest(unittest.TestCase):
    def test_preserves_units_provenance_and_missingness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = not_observed_metrics()
            metrics["provider_input_tokens"] = {
                "status": "observed",
                "value": 1200,
                "provenance": "provider",
            }
            metrics["tool_call_count"] = {
                "status": "observed",
                "value": 0,
                "provenance": "deterministic_proxy",
            }
            manifest = write_json(root / "manifest.json", run_manifest(metrics=metrics))
            result = run_summary(str(manifest), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

            tokens = report["metrics"]["provider_input_tokens"]
            self.assertEqual(tokens["unit"], "tokens")
            self.assertEqual(tokens["totals_by_provenance"], {"provider": {"total": 1200, "records": 1}})

            # An observed zero is a measurement; a missing value never becomes one.
            calls = report["metrics"]["tool_call_count"]
            self.assertEqual(calls["unit"], "count")
            self.assertEqual(
                calls["totals_by_provenance"], {"deterministic_proxy": {"total": 0, "records": 1}}
            )
            self.assertEqual(calls["coverage"]["records_observed"], 1)

            missing = report["metrics"]["provider_output_tokens"]
            self.assertEqual(missing["totals_by_provenance"], {})
            self.assertEqual(missing["coverage"]["records_not_observed"], 1)

    def test_partial_hook_coverage_is_reported_beside_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observed = not_observed_metrics()
            observed["compaction_count"] = {
                "status": "observed",
                "value": 3,
                "provenance": "deterministic_proxy",
            }
            first = write_json(root / "a.json", run_manifest("run-a", metrics=observed))
            second = write_json(root / "b.json", run_manifest("run-b"))
            result = run_summary(str(first), str(second), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            coverage = json.loads(result.stdout)["metrics"]["compaction_count"]["coverage"]
            self.assertEqual(coverage, {"records_total": 2, "records_observed": 1, "records_not_observed": 1})

    def test_duplicate_record_is_counted_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = run_manifest("run-a")
            first = write_json(root / "a.json", payload)
            second = write_json(root / "copy.json", payload)
            result = run_summary(str(first), str(second), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["record_counts"]["run_manifest"], 1)
            statuses = [entry["status"] for entry in report["inputs"]]
            self.assertEqual(statuses, ["included", "duplicate_ignored"])

    def test_same_identity_with_different_bytes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            changed = not_observed_metrics()
            changed["helper_turn_count"] = {
                "status": "observed",
                "value": 2,
                "provenance": "deterministic_proxy",
            }
            first = write_json(root / "a.json", run_manifest("run-a"))
            second = write_json(root / "b.json", run_manifest("run-a", metrics=changed))
            result = run_summary(str(first), str(second))
            self.assertEqual(result.returncode, 1)
            self.assertIn("conflicting records", result.stderr)

    def test_proxy_count_cannot_claim_provider_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = not_observed_metrics()
            metrics["tool_call_count"] = {
                "status": "observed",
                "value": 9,
                "provenance": "provider",
            }
            manifest = write_json(root / "manifest.json", run_manifest(metrics=metrics))
            result = run_summary(str(manifest))
            self.assertEqual(result.returncode, 1)
            self.assertIn("incompatible provenance", result.stderr)

    def test_unsupported_schema_and_corrupt_input_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = run_manifest()
            stale["resource_observations"]["schema_version"] = 99  # type: ignore[index]
            unsupported = write_json(root / "stale.json", stale)
            self.assertEqual(run_summary(str(unsupported)).returncode, 1)

            corrupt = root / "corrupt.json"
            corrupt.write_text("{not json", encoding="utf-8")
            corrupt_result = run_summary(str(corrupt))
            self.assertEqual(corrupt_result.returncode, 1)
            self.assertIn("not valid UTF-8 JSON", corrupt_result.stderr)

            unknown = write_json(root / "unknown.json", {"hello": "world"})
            self.assertEqual(run_summary(str(unknown)).returncode, 1)

    def test_malformed_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(
                root / "manifest.json",
                run_manifest(evidence={"external_transcript": None, "codex_hooks": "sha256:zz"}),
            )
            result = run_summary(str(manifest))
            self.assertEqual(result.returncode, 1)
            self.assertIn("well-formed sha256 digest", result.stderr)

    def test_evidence_verification_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_file = root / "events.jsonl"
            evidence_file.write_text('{"event":"PreToolUse"}\n', encoding="utf-8")
            manifest = write_json(
                root / "manifest.json",
                run_manifest(
                    evidence={
                        "external_transcript": None,
                        "codex_hooks": digest_bytes(evidence_file.read_bytes()),
                    }
                ),
            )
            report = json.loads(
                run_summary(
                    str(manifest), "--evidence", str(evidence_file), "--format", "json"
                ).stdout
            )
            states = {entry["source"]: entry["verification"] for entry in report["evidence"]}
            self.assertEqual(states, {"codex_hooks": "verified", "external_transcript": "not_observed"})

            declared_only = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            self.assertEqual(declared_only["evidence"][1]["verification"], "declared_only")

    def test_changed_evidence_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_file = root / "events.jsonl"
            evidence_file.write_text('{"event":"PreToolUse"}\n', encoding="utf-8")
            manifest = write_json(
                root / "manifest.json",
                run_manifest(
                    evidence={
                        "external_transcript": None,
                        "codex_hooks": digest_bytes(evidence_file.read_bytes()),
                    }
                ),
            )
            evidence_file.write_text('{"event":"PreToolUse"}\n{"event":"Stop"}\n', encoding="utf-8")
            result = run_summary(str(manifest), "--evidence", str(evidence_file))
            self.assertEqual(result.returncode, 1)
            self.assertIn("matches no declared evidence digest", result.stderr)

    def test_unreadable_evidence_is_an_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", run_manifest())
            result = run_summary(str(manifest), "--evidence", str(root / "absent.jsonl"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("evidence file is not a readable regular file", result.stderr)

    def test_symlinked_and_nonregular_inputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", run_manifest())
            link = root / "link.json"
            os.symlink(manifest, link)
            link_result = run_summary(str(link))
            self.assertEqual(link_result.returncode, 1)
            self.assertIn("not a readable regular file", link_result.stderr)

            directory_result = run_summary(str(root))
            self.assertEqual(directory_result.returncode, 1)

            # A blocking FIFO must be classified before any wait, not opened.
            fifo = root / "fifo.json"
            os.mkfifo(fifo)
            fifo_result = subprocess.run(
                [sys.executable, str(SUMMARY), str(fifo)],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            self.assertEqual(fifo_result.returncode, 1)
            self.assertIn("must be a regular file", fifo_result.stderr)

    def test_oversized_input_is_rejected_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            huge = root / "huge.json"
            with huge.open("wb") as handle:
                handle.truncate(8 * 1024 * 1024 + 1)
            result = run_summary(str(huge))
            self.assertEqual(result.returncode, 1)
            self.assertIn("byte input bound", result.stderr)

    def test_input_file_count_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [
                str(write_json(root / f"m{index}.json", run_manifest(f"run-{index}")))
                for index in range(33)
            ]
            result = run_summary(*paths)
            self.assertEqual(result.returncode, 1)
            self.assertIn("at most 32 explicit input files", result.stderr)

    def test_duration_boundaries_stay_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = write_json(root / "candidate.json", candidate_manifest())
            state = write_json(root / "state.json", execution_state(elapsed=[30.0, 15.0]))
            report = json.loads(
                run_summary(str(candidate), str(state), "--format", "json").stdout
            )
            durations = report["durations"]
            self.assertEqual(durations["candidate_runner_duration"]["total"], 12.5)
            self.assertEqual(durations["candidate_attempt_duration"]["total"], 10.0)
            self.assertEqual(durations["execution_elapsed_checkpoint"]["total"], 45.0)
            for group in durations.values():
                self.assertEqual(group["unit"], "seconds")

    def test_execution_stop_reasons_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = write_json(root / "state.json", execution_state())
            report = json.loads(run_summary(str(state), "--format", "json").stdout)
            run = report["execution_runs"][0]
            self.assertEqual(run["state"], "descope_pending")
            self.assertEqual(
                run["reason_codes"]["descope_pending_reason_codes"],
                ["parent_remediation_budget_exhausted"],
            )
            self.assertEqual(run["counters"]["parent_direct_remediation_rounds"], 1)

    def test_billed_cost_and_derived_values_remain_not_observed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", run_manifest())
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            self.assertEqual(report["billed_cost"]["status"], "not_observed")
            self.assertEqual(report["billed_cost"]["totals_by_currency"], {})
            self.assertEqual(
                report["never_inferred"],
                [
                    "billed_cost",
                    "human_intervention_count",
                    "phase_durations_seconds",
                    "replan_count",
                    "wall_clock_total_seconds",
                ],
            )

    def test_explicit_billed_amount_is_reported_with_its_currency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(
                root / "manifest.json",
                run_manifest(
                    billed_cost={"status": "observed", "amount": 1.25, "currency": "USD"}
                ),
            )
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            self.assertEqual(report["billed_cost"]["status"], "observed")
            self.assertEqual(
                report["billed_cost"]["totals_by_currency"], {"USD": {"total": 1.25, "records": 1}}
            )

            without_currency = write_json(
                root / "bad.json",
                run_manifest("run-b", billed_cost={"status": "observed", "amount": 1.25, "currency": None}),
            )
            self.assertEqual(run_summary(str(without_currency)).returncode, 1)

    def test_report_writes_nothing_and_leaves_sources_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", run_manifest())
            state = write_json(root / "state.json", execution_state())
            before = {path.name: path.read_bytes() for path in sorted(root.iterdir())}
            result = run_summary(str(manifest), str(state), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            after = {path.name: path.read_bytes() for path in sorted(root.iterdir())}
            self.assertEqual(before, after)

    def test_implementation_makes_no_network_or_model_call(self) -> None:
        forbidden = {
            "socket",
            "ssl",
            "urllib",
            "http",
            "http.client",
            "requests",
            "subprocess",
            "ftplib",
            "smtplib",
            "asyncio",
            "xmlrpc",
        }
        for module_path in (SUMMARY, ROOT_SUMMARY):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Call):
                    target = node.func
                    name = getattr(target, "id", None) or getattr(target, "attr", None)
                    self.assertNotIn(
                        name,
                        {"eval", "exec", "__import__"},
                        f"{module_path.name} must not construct an import dynamically",
                    )
            for name in imported:
                self.assertNotIn(name.split(".")[0], forbidden, f"{module_path.name}: {name}")

    def test_text_report_shows_evidence_identity_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_file = root / "events.jsonl"
            evidence_file.write_text('{"event":"PreToolUse"}\n', encoding="utf-8")
            metrics = not_observed_metrics()
            metrics["provider_output_tokens"] = {
                "status": "observed",
                "value": 42,
                "provenance": "provider",
            }
            manifest = write_json(
                root / "manifest.json",
                run_manifest(
                    metrics=metrics,
                    evidence={
                        "external_transcript": None,
                        "codex_hooks": digest_bytes(evidence_file.read_bytes()),
                    },
                ),
            )
            candidate = write_json(root / "candidate.json", candidate_manifest())
            state = write_json(root / "state.json", execution_state())
            result = run_summary(
                str(manifest), str(candidate), str(state), "--evidence", str(evidence_file)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = result.stdout

            self.assertIn("## Sources", text)
            self.assertIn("## Evidence", text)
            self.assertIn("codex_hooks: verified", text)
            self.assertIn("external_transcript: not_observed", text)
            self.assertIn("root_session_identity: observed", text)
            self.assertIn("42 tokens [provenance=provider] (1/1 records observed)", text)
            self.assertIn("provider_input_tokens: not_observed (0/1 records)", text)
            self.assertIn("## Candidate runs", text)
            self.assertIn("## Execution runs", text)
            self.assertIn("source_digest=sha256:", text)

    def test_report_output_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Enough distinct record identities that the rendered report itself
            # exceeds the 256 KiB bound even though every input is in bounds.
            paths = [
                str(write_json(root / f"m{index}.json", run_manifest("run-" + str(index) * 20000)))
                for index in range(8)
            ]
            result = run_summary(*paths, "--format", "json")
            self.assertEqual(result.returncode, 1)
            self.assertIn("output bound", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_different_currencies_are_not_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            usd = write_json(
                root / "usd.json",
                run_manifest(
                    "run-usd", billed_cost={"status": "observed", "amount": 2.0, "currency": "USD"}
                ),
            )
            jpy = write_json(
                root / "jpy.json",
                run_manifest(
                    "run-jpy", billed_cost={"status": "observed", "amount": 300.0, "currency": "JPY"}
                ),
            )
            plain = write_json(root / "plain.json", run_manifest("run-plain"))
            report = json.loads(run_summary(str(usd), str(jpy), str(plain), "--format", "json").stdout)
            billed = report["billed_cost"]
            self.assertEqual(
                billed["totals_by_currency"],
                {"USD": {"total": 2.0, "records": 1}, "JPY": {"total": 300.0, "records": 1}},
            )
            self.assertEqual(billed["coverage"], {"records_total": 3, "records_observed": 2, "records_not_observed": 1})

    def test_model_statements_are_reported_by_evidence_class_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            manifest = write_json(root / "manifest.json", payload)
            report = json.loads(
                run_summary(
                    str(manifest),
                    "--evidence",
                    str(root / "imported.jsonl"),
                    "--evidence",
                    str(root / "hooks.jsonl"),
                    "--format",
                    "json",
                ).stdout
            )
            model = report["model_evidence"]
            self.assertEqual(model["manifests_with_observations"], 1)
            self.assertEqual(model["manifests_without_observations"], 0)

            runtime = model["values_by_evidence_class"]["runtime_reported"]
            self.assertEqual(
                sorted(bucket["value"] for bucket in runtime["model"]),
                ["example-model-a", "example-model-b"],
            )
            self.assertEqual(
                sorted(bucket["value"] for bucket in runtime["reasoning_effort"]),
                ["high", "medium"],
            )
            self.assertNotIn("requested", model["values_by_evidence_class"])
            self.assertNotIn("provider_reported", model["values_by_evidence_class"])

            for statement in model["statements"]:
                self.assertIn(statement["source_kind"], {
                    "transcript_turn_context",
                    "hook_event_metadata",
                })
                self.assertIsNotNone(statement["session_digest"])
                self.assertGreaterEqual(statement["record_line"], 1)
                # A session identity alone does not separate two executions,
                # so only a turn-scoped shape confirms a comparable scope.
                self.assertEqual(
                    statement["scope_confirmed"],
                    statement["source_kind"] == "transcript_turn_context",
                )
            self.assertEqual(model["unconfirmed_scope_statements"], 2)

            self.assertEqual(
                {statement["verification"] for statement in model["statements"]},
                {"recomputed"},
            )

    def test_model_evidence_never_reattributes_run_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = not_observed_metrics()
            metrics["provider_output_tokens"] = {
                "status": "observed",
                "value": 900,
                "provenance": "provider",
            }
            payload = model_evidence_manifest(root)
            payload["resource_observations"]["metrics"] = metrics  # type: ignore[index]
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest), "--format", "json")
            report = json.loads(result.stdout)

            totals = report["metrics"]["provider_output_tokens"]["totals_by_provenance"]
            self.assertEqual(totals["provider"]["total"], 900)
            self.assertEqual(totals["provider"]["records"], 1)
            self.assertEqual(
                report["model_evidence"]["attribution_unavailable"],
                [
                    "per_model_token_totals",
                    "per_model_billed_cost",
                    "per_model_completed_task_counts",
                ],
            )
            serialized = json.dumps(report["model_evidence"])
            self.assertNotIn("900", serialized)
            self.assertNotIn("tokens", serialized)

            text = run_summary(str(manifest)).stdout
            self.assertIn("A model statement names an observed model, never its resource usage.", text)
            self.assertIn("per_model_token_totals: not attributable", text)

    def test_distinct_turns_reporting_distinct_models_are_not_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            self.assertEqual(report["model_evidence"]["conflicts"], [])

    def test_incompatible_statements_in_one_scope_are_reported_as_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            observations = payload["model_observations"]
            statements = observations["statements"]  # type: ignore[index]
            twin = dict(statements[2])
            twin["turn_id"] = statements[0]["turn_id"]
            twin["root_turn_id"] = statements[0]["root_turn_id"]
            twin["record_line"] = 99
            twin["source_line"] = 99
            statements.append(twin)
            manifest = write_json(root / "manifest.json", payload)
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            conflicts = report["model_evidence"]["conflicts"]
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0]["kind"], "execution_scope")
            self.assertEqual(conflicts[0]["attribute"], "model")
            self.assertEqual(conflicts[0]["evidence_class"], "runtime_reported")
            self.assertEqual(conflicts[0]["values"], ["example-model-a", "example-model-b"])

    def test_summary_is_verified_by_recomputing_the_supplied_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = model_evidence_manifest(root)
            evidence = ["--evidence", str(root / "imported.jsonl"),
                        "--evidence", str(root / "hooks.jsonl")]

            def forged(mutate) -> None:
                payload = json.loads(json.dumps(base))
                mutate(payload["model_observations"])
                manifest = write_json(root / "bad.json", payload)
                result = run_summary(str(manifest), *evidence)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("does not reproduce the summary", result.stderr)

            def forge_value(observations: dict) -> None:
                for statement in observations["statements"]:
                    if statement["source"] == "external_transcript":
                        statement["value"] = "forged-model"
                        return

            def omit_evidence(observations: dict) -> None:
                observations["statements"] = [
                    statement
                    for statement in observations["statements"]
                    if statement["source"] != "external_transcript"
                ]

            def inflate_count(observations: dict) -> None:
                observations["coverage"]["external_transcript"]["records_scanned"] = 99

            def forge_scope(observations: dict) -> None:
                for statement in observations["statements"]:
                    if statement["source"] == "external_transcript":
                        statement["turn_id"] = "turn-forged"
                        return

            def forge_identity_count(observations: dict) -> None:
                observations["identity_counts"]["turn_ids"] = 99

            def forge_diagnostic(observations: dict) -> None:
                observations["diagnostics"] = ["source_too_large"]

            def forge_truncation(observations: dict) -> None:
                observations["truncated"] = True

            def forge_provider(observations: dict) -> None:
                observations["provider_context"]["model_provider"] = {
                    "status": "observed",
                    "values": ["forged-provider"],
                }

            forged(forge_value)
            forged(omit_evidence)
            forged(inflate_count)
            forged(forge_scope)
            forged(forge_identity_count)
            forged(forge_diagnostic)
            forged(forge_truncation)
            forged(forge_provider)

            manifest = write_json(root / "good.json", base)
            result = run_summary(str(manifest), *evidence, "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            self.assertTrue(model["statements"])
            self.assertEqual(
                {item["verification"] for item in model["statements"]}, {"recomputed"}
            )

    def test_partial_evidence_verifies_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            payload["model_observations"]["provider_context"]["model_provider"] = {
                "status": "observed",
                "values": ["forged-provider"],
            }
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest), "--evidence", str(root / "hooks.jsonl"), "--format", "json"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            # One supplied source cannot check a summary derived from both, so
            # nothing in this manifest may be presented as recomputed.
            self.assertEqual(
                {statement["verification"] for statement in model["statements"]},
                {"declared_only"},
            )
            self.assertEqual(
                {entry["verification"] for entry in model["coverage"]}, {"declared_only"}
            )

    def test_producer_truncated_summary_still_recomputes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = load_manifest_helper()
            records = []
            for index in range(1, 40):
                observation = helper.build_model_observation(
                    "transcript_turn_context",
                    runtime_model=f"example-model-{index}",
                    runtime_effort="medium",
                    session_id="session-parent",
                    turn_id=f"turn-{index}",
                )
                records.append(
                    {
                        "kind": "transcript",
                        "metadata": {
                            "source_type": "turn_context",
                            "source_line": index,
                            "model_observation": observation,
                        },
                    }
                )
            (root / "imported.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
            )
            observations = build_model_observations(root, transcript="imported.jsonl")
            # The producer bounds its own output; the reader must accept that
            # bounded output rather than reimplement the bound and reject it.
            self.assertTrue(observations["truncated"])
            self.assertIn("statements_truncated", observations["diagnostics"])
            payload = run_manifest("run-trunc")
            payload["model_observations"] = observations
            payload["transcript_log"] = "imported.jsonl"
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest), "--evidence", str(root / "imported.jsonl"), "--format", "json"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            self.assertEqual(
                {statement["verification"] for statement in model["statements"]}, {"recomputed"}
            )
            self.assertTrue(model["diagnostics"][0]["truncated"])

    def test_unrescannable_evidence_is_rejected_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            hostile = root / "imported.jsonl"
            body = '{"n": ' + "9" * 6000 + "}\n"
            hostile.write_text(body, encoding="utf-8")
            observations = payload["model_observations"]
            observations["evidence_digests"]["external_transcript"] = digest_bytes(
                body.encode("utf-8")
            )
            observations["statements"] = [
                statement
                for statement in observations["statements"]
                if statement["source"] != "external_transcript"
            ]
            observations["coverage"]["external_transcript"] = {
                "status": "present",
                "records_scanned": 1,
                "records_with_model_observation": 0,
            }
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest),
                "--evidence",
                str(hostile),
                "--evidence",
                str(root / "hooks.jsonl"),
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_source_kind_must_match_the_file_that_can_hold_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            statements = payload["model_observations"]["statements"]
            forged = dict(statements[0])
            self.assertEqual(forged["source"], "external_transcript")
            forged["source"] = "codex_hooks"
            statements.append(forged)
            manifest = write_json(root / "bad.json", payload)
            result = run_summary(str(manifest))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("cannot hold it", result.stderr)

    def test_unsupplied_source_is_never_called_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            model = report["model_evidence"]
            self.assertEqual(
                {statement["verification"] for statement in model["statements"]},
                {"declared_only"},
            )
            self.assertEqual(
                {entry["verification"] for entry in model["coverage"]}, {"declared_only"}
            )

    def test_stored_value_must_satisfy_every_producer_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = model_evidence_manifest(root)
            for bad in ("ghp_" + "a" * 20, " padded-model", "model\u0007bell", "[REDACTED]"):
                payload = json.loads(json.dumps(base))
                payload["model_observations"]["statements"][0]["value"] = bad
                manifest = write_json(root / "bad.json", payload)
                result = run_summary(str(manifest))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn(bad, result.stdout)

    def test_undecodable_report_text_is_rejected_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            payload["model_observations"]["statements"][0]["value"] = "model-\ud800"
            manifest = root / "bad.json"
            manifest.write_text(
                json.dumps(payload).replace("\\\\ud800", "\\ud800"), encoding="utf-8"
            )
            result = run_summary(str(manifest))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_contradictory_scope_for_one_record_is_kept_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = model_evidence_manifest(root, "run-a")
            second = json.loads(json.dumps(first))
            second["run_id"] = "run-b"
            for statement in second["model_observations"]["statements"]:
                if statement["source"] == "external_transcript":
                    statement["turn_id"] = "turn-other"
                    statement["root_turn_id"] = "turn-other"
                    break
            paths = [
                str(write_json(root / "a.json", first)),
                str(write_json(root / "b.json", second)),
            ]
            report = json.loads(run_summary(*paths, "--format", "json").stdout)
            model = report["model_evidence"]
            turns = {
                statement["turn_id"]
                for statement in model["statements"]
                if statement["source"] == "external_transcript"
                and statement["record_line"] == 2
                and statement["attribute"] == "model"
            }
            self.assertEqual(turns, {"turn-1", "turn-other"})
            self.assertIn(
                "record_position", [conflict["kind"] for conflict in model["conflicts"]]
            )

    def test_source_line_cannot_hide_a_record_position_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            statements = payload["model_observations"]["statements"]
            twin = dict(statements[0])
            twin["value"] = "example-model-forged"
            twin["source_line"] = 999
            twin["turn_id"] = None
            twin["root_turn_id"] = None
            statements.append(twin)
            manifest = write_json(root / "manifest.json", payload)
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            self.assertIn(
                "record_position",
                [conflict["kind"] for conflict in report["model_evidence"]["conflicts"]],
            )

    def test_session_only_shape_never_confirms_an_execution_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            model = report["model_evidence"]
            hooks = [
                statement
                for statement in model["statements"]
                if statement["source_kind"] == "hook_event_metadata"
            ]
            self.assertTrue(hooks)
            for statement in hooks:
                self.assertIsNotNone(statement["session_digest"])
                self.assertFalse(statement["scope_confirmed"])
            self.assertEqual(model["unconfirmed_scope_statements"], len(hooks))

    def test_statement_cannot_claim_an_unobservable_evidence_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = model_evidence_manifest(root)
            for source, source_kind, evidence_class in (
                ("external_transcript", "transcript_turn_context", "provider_reported"),
                ("external_transcript", "transcript_turn_context", "requested"),
                ("codex_hooks", "hook_event_metadata", "provider_reported"),
                ("external_transcript", "transcript_session_meta", "runtime_reported"),
            ):
                payload = json.loads(json.dumps(base))
                statements = payload["model_observations"]["statements"]
                forged = dict(statements[0])
                forged["source"] = source
                forged["source_kind"] = source_kind
                forged["evidence_class"] = evidence_class
                if source_kind != "transcript_turn_context":
                    forged["turn_id"] = None
                    forged["root_turn_id"] = None
                statements.append(forged)
                manifest = write_json(root / "bad.json", payload)
                result = run_summary(str(manifest))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("cannot observe", result.stderr)

    def test_two_sources_disagreeing_about_one_turn_are_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = model_evidence_manifest(root, "run-a")
            other = root / "other"
            other.mkdir()
            write_model_evidence_imported_log(other / "imported.jsonl")
            (other / "imported.jsonl").write_text(
                (other / "imported.jsonl")
                .read_text(encoding="utf-8")
                .replace("example-model-a", "example-model-q"),
                encoding="utf-8",
            )
            second = run_manifest("run-b")
            second["model_observations"] = build_model_observations(
                other, transcript="imported.jsonl", hook_log=None
            )
            paths = [
                str(write_json(root / "a.json", first)),
                str(write_json(root / "b.json", second)),
            ]
            report = json.loads(run_summary(*paths, "--format", "json").stdout)
            conflicts = report["model_evidence"]["conflicts"]
            kinds = {conflict["kind"] for conflict in conflicts}
            self.assertEqual(kinds, {"execution_scope"})
            for conflict in conflicts:
                self.assertIsNotNone(conflict["turn_id"])
                self.assertEqual(len(conflict["records"]), 2)

    def test_one_record_position_cannot_hold_two_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            statements = payload["model_observations"]["statements"]  # type: ignore[index]
            twin = dict(statements[0])
            twin["value"] = "example-model-forged"
            statements.append(twin)
            manifest = write_json(root / "manifest.json", payload)
            report = json.loads(run_summary(str(manifest), "--format", "json").stdout)
            kinds = [conflict["kind"] for conflict in report["model_evidence"]["conflicts"]]
            self.assertIn("record_position", kinds)

    def test_same_record_seen_through_two_manifests_is_counted_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = model_evidence_manifest(root, "run-a")
            second = run_manifest("run-b")
            second["model_observations"] = first["model_observations"]
            manifests = [
                str(write_json(root / "a.json", first)),
                str(write_json(root / "b.json", second)),
            ]
            report = json.loads(run_summary(*manifests, "--format", "json").stdout)
            model = report["model_evidence"]
            self.assertEqual(model["manifests_with_observations"], 2)
            self.assertEqual(len(model["statements"]), 6)
            for statement in model["statements"]:
                self.assertEqual(statement["run_ids"], ["run-a", "run-b"])
            for bucket in model["values_by_evidence_class"]["runtime_reported"]["model"]:
                if bucket["value"] == "example-model-a":
                    self.assertEqual(bucket["statement_count"], 3)
            self.assertEqual(model["conflicts"], [])

    def test_manifest_without_model_observations_stays_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", run_manifest())
            result = run_summary(str(manifest), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            self.assertEqual(model["manifests_with_observations"], 0)
            self.assertEqual(model["manifests_without_observations"], 1)
            self.assertEqual(model["statements"], [])
            self.assertEqual(model["coverage"], [])
            text = run_summary(str(manifest)).stdout
            self.assertIn("no supplied run manifest carries model observations", text)

    def test_statement_without_its_source_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            payload["model_observations"]["evidence_digests"]["codex_hooks"] = None  # type: ignore[index]
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest))
            self.assertEqual(result.returncode, 1)
            self.assertIn("no evidence digest", result.stderr)

    def test_session_scoped_source_cannot_claim_a_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            statements = payload["model_observations"]["statements"]  # type: ignore[index]
            forged = dict(statements[4])
            self.assertEqual(forged["source_kind"], "hook_event_metadata")
            forged["turn_id"] = "turn-1"
            statements.append(forged)
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest))
            self.assertEqual(result.returncode, 1)
            self.assertIn("cannot establish", result.stderr)

    def test_model_observation_shape_and_bounds_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = model_evidence_manifest(root)

            def rejected(mutate, expected: str) -> None:
                payload = json.loads(json.dumps(base))
                mutate(payload["model_observations"])
                manifest = write_json(root / "bad.json", payload)
                result = run_summary(str(manifest))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(expected, result.stderr)

            def set_schema(observations: dict) -> None:
                observations["schema_version"] = 2

            def add_field(observations: dict) -> None:
                observations["extra"] = True

            def bad_class(observations: dict) -> None:
                observations["statements"][0]["evidence_class"] = "guessed"

            def bad_kind(observations: dict) -> None:
                observations["statements"][0]["source_kind"] = "inferred_from_text"

            def long_value(observations: dict) -> None:
                observations["statements"][0]["value"] = "m" * 129

            def bad_digest(observations: dict) -> None:
                observations["statements"][0]["session_digest"] = "sha256:zz"

            def bad_diagnostic(observations: dict) -> None:
                observations["diagnostics"] = ["guessed_from_usage"]

            def unbounded_statements(observations: dict) -> None:
                observations["statements"] = [observations["statements"][0]] * 65

            def empty_provider(observations: dict) -> None:
                observations["provider_context"]["cli_version"] = {
                    "status": "observed",
                    "values": [],
                }

            rejected(set_schema, "unsupported model observation schema version")
            rejected(add_field, "unsupported field set")
            rejected(bad_class, "unsupported evidence class")
            rejected(bad_kind, "unsupported source kind")
            rejected(long_value, "bounded non-empty value")
            rejected(bad_digest, "model session digest")
            rejected(bad_diagnostic, "unsupported code")
            rejected(unbounded_statements, "bounded list")
            rejected(empty_provider, "requires a value")

    def test_model_evidence_matches_between_wrapper_and_generated_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            evidence = str(root / "imported.jsonl")
            direct = run_summary(str(manifest), "--evidence", evidence, "--format", "json")
            wrapped = run_summary(
                str(manifest), "--evidence", evidence, "--format", "json", command=ROOT_SUMMARY
            )
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
            self.assertEqual(direct.stdout, wrapped.stdout)
            self.assertNotEqual(json.loads(direct.stdout)["model_evidence"]["statements"], [])

    def test_summary_omitting_a_declared_source_never_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # The summary covers only the transcript, but the manifest declares
            # a hook log too, so the producer would have read both.
            payload = model_evidence_manifest(root, hook_log=None)
            write_model_evidence_hook_log(root / "hooks.jsonl")
            payload["hook_event_log"] = "hooks.jsonl"
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest), "--evidence", str(root / "imported.jsonl"), "--format", "json"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            self.assertTrue(model["statements"])
            self.assertEqual(
                {statement["verification"] for statement in model["statements"]},
                {"declared_only"},
            )

    def test_producer_recorded_unreadable_source_is_unverified_not_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root, hook_log=None)
            # The manifest declares a hook log the producer could not read, so
            # its digest is absent and no bytes exist to rebuild it from.
            payload["hook_event_log"] = "missing.jsonl"
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest), "--evidence", str(root / "imported.jsonl"), "--format", "json"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            # Absence belongs to the coverage status, not to the verification
            # label, which states only what this manifest was checked against.
            self.assertEqual(
                {entry["verification"] for entry in model["coverage"]}, {"declared_only"}
            )
            self.assertEqual(
                {entry["source"]: entry["status"] for entry in model["coverage"]},
                {"external_transcript": "present", "codex_hooks": "missing"},
            )

    def test_coverage_of_an_undeclared_source_still_reports_the_manifest_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root, hook_log=None)
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest), "--evidence", str(root / "imported.jsonl"), "--format", "json"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            self.assertEqual(
                {entry["verification"] for entry in model["coverage"]}, {"recomputed"}
            )
            absent = [
                entry for entry in model["coverage"] if entry["source"] == "codex_hooks"
            ]
            self.assertEqual([entry["digest"] for entry in absent], [None])

    def test_unrepresentable_number_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = run_manifest()
            payload["resource_observations"]["billed_cost"] = {
                "status": "observed",
                "amount": 10 ** 4000,
                "currency": "USD",
            }
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("outside the supported bound", result.stderr)

    def test_aliased_source_paths_with_different_digests_never_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            # One file cannot hold two different sets of bytes, so a manifest
            # naming one path for both sources with two digests is unverifiable.
            payload["hook_event_log"] = "imported.jsonl"
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest),
                "--evidence",
                str(root / "imported.jsonl"),
                "--evidence",
                str(root / "hooks.jsonl"),
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            self.assertEqual(
                {statement["verification"] for statement in model["statements"]},
                {"declared_only"},
            )

    def test_text_report_names_the_record_behind_each_statement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            result = run_summary(
                str(manifest),
                "--evidence",
                str(root / "imported.jsonl"),
                "--evidence",
                str(root / "hooks.jsonl"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            json_result = run_summary(
                str(manifest),
                "--evidence",
                str(root / "imported.jsonl"),
                "--evidence",
                str(root / "hooks.jsonl"),
                "--format",
                "json",
            )
            statements = json.loads(json_result.stdout)["model_evidence"]["statements"]
            self.assertTrue(statements)
            for statement in statements:
                # The default format has to let a reader reach the record, not
                # only the aggregate.
                self.assertIn(statement["source_digest"], result.stdout)
                self.assertIn(f"record {statement['record_line']} ", result.stdout)
                self.assertIn(f"{statement['run_ids'][0]}:", result.stdout)

    def test_unrenderable_aggregate_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for index, run_id in enumerate(("run-a", "run-b")):
                metrics = not_observed_metrics()
                metrics["provider_input_tokens"] = {
                    "status": "observed",
                    "value": 5 * 10 ** 4299,
                    "provenance": "provider",
                }
                paths.append(
                    str(write_json(root / f"m{index}.json", run_manifest(metrics=metrics, run_id=run_id)))
                )
            result = run_summary(*paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("could not be rendered", result.stderr)

    def test_report_is_written_regardless_of_the_stdout_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", run_manifest("run-\u00e9"))
            environment = dict(os.environ, PYTHONIOENCODING="ascii")
            result = subprocess.run(
                [sys.executable, str(SUMMARY), str(manifest)],
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("run-\u00e9".encode("utf-8"), result.stdout)

    def test_deeply_nested_manifest_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text("[" * 40000 + "]" * 40000, encoding="utf-8")
            result = run_summary(str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("not valid UTF-8 JSON", result.stderr)

    def test_oversized_integer_in_a_manifest_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text('{"run_id": ' + "9" * 5001 + "}", encoding="utf-8")
            result = run_summary(str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("not valid UTF-8 JSON", result.stderr)

    def test_line_separator_in_a_model_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            payload["model_observations"]["statements"][0]["value"] = (
                "example-model\u2028- forged: recomputed"
            )
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot be reported", result.stderr)
            self.assertNotIn("forged", result.stdout)

    def test_model_evidence_report_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "manifest.json", model_evidence_manifest(root))
            before = {path.name: path.read_bytes() for path in sorted(root.iterdir())}
            result = run_summary(
                str(root / "manifest.json"),
                "--evidence",
                str(root / "imported.jsonl"),
                "--evidence",
                str(root / "hooks.jsonl"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            # A report that reads the evidence and still leaves every byte in
            # place is the claim under test, so the reading has to be real.
            self.assertIn("## Model evidence", result.stdout)
            self.assertIn("recomputed", result.stdout)
            after = {path.name: path.read_bytes() for path in sorted(root.iterdir())}
            self.assertEqual(before, after)

    def test_documentation_describes_model_evidence_reporting(self) -> None:
        for spec in (
            ROOT / "docs/agent/SPEC_AGENT_LOGGING.md",
            ROOT / "template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md",
        ):
            text = spec.read_text(encoding="utf-8")
            self.assertIn("model_evidence", text)
            self.assertIn("per_model_token_totals", text)
            # The specification has to carry the claims the reader enforces,
            # not merely mention the section name.
            self.assertIn("all or nothing", text)
            self.assertIn("Rebuild from the bytes whose digest was verified", text)
            self.assertIn("Label every reported model component", text)
            self.assertIn("by type as well as by value", text)
            self.assertIn("never certifies", text)
            self.assertIn("bidirectional override", text)

    def test_every_model_component_carries_a_verification_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            result = run_summary(str(manifest), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            model = json.loads(result.stdout)["model_evidence"]
            for section in ("coverage", "statements", "provider_context",
                            "diagnostics", "identity_counts"):
                self.assertTrue(model[section], section)
                for entry in model[section]:
                    self.assertIn("verification", entry, section)
                    self.assertEqual(entry["verification"], "declared_only", section)

    def test_verification_does_not_depend_on_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Both manifests report the same transcript bytes, so they share
            # statements, but only one of them is fully supplied here.
            full = write_json(
                root / "full.json", model_evidence_manifest(root, "run-full")
            )
            partial = write_json(
                root / "partial.json",
                model_evidence_manifest(root, "run-partial", hook_log=None),
            )
            evidence = ["--evidence", str(root / "imported.jsonl")]
            first = run_summary(str(full), str(partial), *evidence, "--format", "json")
            second = run_summary(str(partial), str(full), *evidence, "--format", "json")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            statements = json.loads(first.stdout)["model_evidence"]["statements"]
            self.assertEqual(
                statements, json.loads(second.stdout)["model_evidence"]["statements"]
            )
            shared = [item for item in statements if len(item["runs"]) > 1]
            self.assertTrue(shared)
            for item in shared:
                self.assertEqual(item["verification"], "recomputed")
                self.assertEqual(
                    {run["run_id"]: run["verification"] for run in item["runs"]},
                    {"run-full": "declared_only", "run-partial": "recomputed"},
                )

    def test_same_digest_declared_for_both_sources_is_reported_consistently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            digests = payload["model_observations"]["evidence_digests"]
            digests["codex_hooks"] = digests["external_transcript"]
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest), "--evidence", str(root / "imported.jsonl"), "--format", "json"
            )
            # One file cannot be both declared sources, so the rebuild must not
            # reproduce the summary and the report must refuse it.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("model observations", result.stderr)

    def test_format_character_in_a_model_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            statement = payload["model_observations"]["statements"][0]
            statement["value"] = "example-model\u202egnol"
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest), "--format", "json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot be reported", result.stderr)

    def test_newline_in_a_run_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            payload["run_id"] = "run-a\n- forged: line"
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot be reported", result.stderr)

    def test_boolean_declared_for_a_count_is_not_an_exact_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = model_evidence_manifest(root)
            counts = payload["model_observations"]["identity_counts"]
            self.assertEqual(counts["turn_ids"], 2)
            counts["turn_ids"] = 2.0
            manifest = write_json(root / "manifest.json", payload)
            result = run_summary(
                str(manifest),
                "--evidence",
                str(root / "imported.jsonl"),
                "--evidence",
                str(root / "hooks.jsonl"),
                "--format",
                "json",
            )
            self.assertNotEqual(result.returncode, 0)

    def test_root_wrapper_delegates_to_the_generated_implementation(self) -> None:
        wrapper = ROOT_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("template", wrapper)
        self.assertIn("summarize-agent-run.py", wrapper)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_json(root / "manifest.json", model_evidence_manifest(root))
            evidence = ["--evidence", str(root / "imported.jsonl"),
                        "--evidence", str(root / "hooks.jsonl")]
            direct = run_summary(str(manifest), *evidence, "--format", "json")
            wrapped = run_summary(
                str(manifest), *evidence, "--format", "json", command=ROOT_SUMMARY
            )
            self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
            self.assertEqual(direct.stdout, wrapped.stdout)
            # Delegation only means something if the delegated output carries
            # the behaviour under test.
            self.assertTrue(json.loads(wrapped.stdout)["model_evidence"]["statements"])

    def test_command_is_distributed_through_the_existing_inventory(self) -> None:
        inventory = (ROOT / "scripts/project_workflow/copier_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"scripts/summarize-agent-run.py"', inventory)
        self.assertIn(
            '"template/.project-agent-workflow/scripts/summarize-agent-run.py"', inventory
        )
        self.assertIn('".project-agent-workflow/scripts/summarize-agent-run.py"', inventory)

    def test_documentation_describes_the_local_only_invocation(self) -> None:
        for spec in (
            ROOT / "docs/agent/SPEC_AGENT_LOGGING.md",
            ROOT / "template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md",
        ):
            text = spec.read_text(encoding="utf-8")
            self.assertIn("summarize-agent-run.py", text)
            self.assertIn("not_observed", text)


if __name__ == "__main__":
    unittest.main()
