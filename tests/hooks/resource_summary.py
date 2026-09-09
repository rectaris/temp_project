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

from .support import ROOT


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

    def test_root_wrapper_delegates_to_the_generated_implementation(self) -> None:
        wrapper = ROOT_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("template", wrapper)
        self.assertIn("summarize-agent-run.py", wrapper)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_json(Path(tmp) / "manifest.json", run_manifest())
            direct = run_summary(str(manifest), "--format", "json")
            wrapped = run_summary(str(manifest), "--format", "json", command=ROOT_SUMMARY)
            self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
            self.assertEqual(direct.stdout, wrapped.stdout)

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
