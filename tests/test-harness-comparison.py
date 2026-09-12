#!/usr/bin/env python3
"""Behavior tests for the local paired harness comparison command.

The fixtures in this suite are synthetic. They establish what the command
reports from supplied records. They are never observed model performance.

Run with ``--generated`` to compare the root wrapper against an isolated
rendered generated-project command over the same portable fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_COMMAND = ROOT / "scripts/compare-harness-runs.py"
TEMPLATE_COMMAND = ROOT / "template/.project-agent-workflow/scripts/compare-harness-runs.py"
GENERATED_RELATIVE = ".project-agent-workflow/scripts/compare-harness-runs.py"

RUNTIME = {"cli_version": "1.4.5", "tool_versions": {"git": "2.43.0", "python": "3.12.3"}}
ALTERNATE_RUNTIME = {"cli_version": "1.4.6", "tool_versions": {"git": "2.43.0", "python": "3.12.3"}}
INTERVENTION_RULE = "One intervention is one human message that changes the task after it starts."
ORDERING_ATTESTATION = b"reviewed by an independent reviewer before any run outcome existed\n"

CASE_IDS = ("small-fix", "cross-file-change")


def sha(tag: str) -> str:
    return "sha256:" + hashlib.sha256(tag.encode("utf-8")).hexdigest()


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def configuration(
    slot: str,
    model: str,
    instructions: str,
    *,
    runtime: dict | None = None,
    effort: str | None = "medium",
) -> dict:
    return {
        "slot": slot,
        "declared_model": model,
        "reasoning_settings": (
            {"supported": True, "effort": effort}
            if effort is not None
            else {"supported": False, "effort": None}
        ),
        "instruction_asset_digests": {"AGENTS.md": sha(instructions)},
        "runtime": runtime or RUNTIME,
        "configuration_digest": sha(f"configuration:{slot}"),
    }


def case(case_id: str, fixture_kind: str = "operational") -> dict:
    return {
        "case_id": case_id,
        "task_digest": sha(f"task:{case_id}"),
        "acceptance_digest": sha(f"acceptance:{case_id}"),
        "rubric_digest": sha(f"rubric:{case_id}"),
        "fixture_kind": fixture_kind,
    }


def protocol(
    *,
    fixture_kind: str = "operational",
    repetitions: int = 2,
    holdout_status: str = "withheld",
    ordering_status: str | None = "independently_reviewed",
    include_candidate: bool = True,
    candidate_effort: str | None = "medium",
    candidate_runtime: dict | None = None,
    candidate_model: str | None = None,
    new_instructions: str = "instructions-current",
) -> dict:
    configurations = {
        "old_model_current_instructions": configuration(
            "old_model_current_instructions", "model-old", "instructions-current"
        ),
        "new_model_current_instructions": configuration(
            "new_model_current_instructions", "model-new", new_instructions
        ),
    }
    if include_candidate:
        configurations["new_model_candidate_instructions"] = configuration(
            "new_model_candidate_instructions",
            candidate_model or "model-new",
            "instructions-candidate",
            runtime=candidate_runtime,
            effort=candidate_effort,
        )
    ordering = None
    if ordering_status is not None:
        ordering = {
            "status": ordering_status,
            "reviewer_identity": "independent-reviewer-1",
            "source": "parent-owned attestation outside the repository",
            "attestation_digest": digest_bytes(ORDERING_ATTESTATION),
        }
    cases = [case(case_id, fixture_kind) for case_id in CASE_IDS]
    return {
        "schema_version": 1,
        "protocol_id": "harness-comparison-fixture",
        "repository_baseline": sha("baseline"),
        "invariant_digest": sha("invariant"),
        "authority_digest": sha("authority"),
        "configurations": configurations,
        "cases": cases,
        "repetitions": repetitions,
        "budget": {"max_total_runs": 256, "max_elapsed_seconds": 86400.0},
        "metric_boundaries": {
            "elapsed_seconds": "task_start_to_terminal_outcome",
            "billed_cost": "directly_recorded_billed_amount",
            "human_interventions": INTERVENTION_RULE,
        },
        "decision_limits": {
            "require_all_critical_pass": True,
            "min_quality_pass_delta": 0.0,
            "max_elapsed_ratio": 1.5,
            "max_cost_ratio": 1.5,
            "max_additional_interventions": 0,
        },
        "freeze": {
            "declared_frozen_at": "2026-09-01T00:00:00Z",
            "holdout_status": holdout_status,
            "ordering_evidence": ordering,
        },
    }


OBSERVED_MODEL_BY_SLOT = {
    "old_model_current_instructions": "model-old",
    "new_model_current_instructions": "model-new",
    "new_model_candidate_instructions": "model-new",
}

# The effective instructions a run actually loaded. They match the declared
# assets of the slot, so a controlled roster confirms its declaration instead of
# leaving it unobserved.
LOADED_INSTRUCTIONS_BY_SLOT = {
    "old_model_current_instructions": "instructions-current",
    "new_model_current_instructions": "instructions-current",
    "new_model_candidate_instructions": "instructions-candidate",
}


def evidence_payloads(records: list[dict]) -> list[bytes]:
    """Every raw evidence file a roster declares, in a stable order."""

    tags: list[str] = []
    for record in records:
        cell = f"{record['slot']}/{record['case_id']}#{record['repetition']}"
        tags.append(f"transcript:{cell}")
        if record["quality"]["judgment"] is not None:
            tags.append(f"judgment:{cell}")
    return [tag.encode("utf-8") for tag in dict.fromkeys(tags)]


def observation(
    slot: str,
    case_id: str,
    repetition: int,
    *,
    outcome: str = "completed",
    acceptance_result: str = "pass",
    judgment_kind: str = "deterministic_test",
    quality_observed: bool = True,
    critical_violation: bool = False,
    elapsed: float | None = 100.0,
    cost: float | None = 1.0,
    interventions: int | None = 0,
    model_identity: str | None = None,
    model_observed: bool = True,
    runtime: dict | None = None,
    runtime_observed: bool = True,
    loading_observed: bool = True,
    host_instructions: str = "known",
    fixture_kind: str = "operational",
    reasoning_effort: str | None = "medium",
    loaded_instructions: str | None = None,
) -> dict:
    cell = f"{slot}/{case_id}#{repetition}"
    quality: dict = {"status": "not_observed", "acceptance_result": None, "judgment": None}
    if quality_observed:
        quality = {
            "status": "observed",
            "acceptance_result": acceptance_result,
            "judgment": {
                "kind": judgment_kind,
                "identity": "focused-acceptance-check",
                "source_evidence_digest": sha(f"judgment:{cell}"),
                "reviewer_provenance": "independent-reviewer-2 session 7",
                "acceptance_item_digest": sha(f"acceptance:{case_id}"),
                "rubric_digest": sha(f"rubric:{case_id}"),
            },
        }
    return {
        "schema_version": 1,
        "protocol_id": "harness-comparison-fixture",
        "slot": slot,
        "case_id": case_id,
        "repetition": repetition,
        "task_digest": sha(f"task:{case_id}"),
        "acceptance_digest": sha(f"acceptance:{case_id}"),
        "repository_baseline": sha("baseline"),
        "invariant_digest": sha("invariant"),
        "authority_digest": sha("authority"),
        "configuration_digest": sha(f"configuration:{slot}"),
        "fixture_kind": fixture_kind,
        "observed_model": (
            {
                "status": "observed",
                "identity": model_identity or OBSERVED_MODEL_BY_SLOT[slot],
                "resolved_snapshot": None,
            }
            if model_observed
            else {"status": "not_observed", "identity": None, "resolved_snapshot": None}
        ),
        "observed_reasoning_settings": {
            "status": "observed",
            "supported": reasoning_effort is not None,
            "effort": reasoning_effort,
        },
        "observed_runtime": (
            {
                "status": "observed",
                "cli_version": (runtime or RUNTIME)["cli_version"],
                "tool_versions": (runtime or RUNTIME)["tool_versions"],
            }
            if runtime_observed
            else {"status": "not_observed", "cli_version": None, "tool_versions": None}
        ),
        "instruction_loading": (
            {
                "status": "observed",
                "effective_instruction_digests": {
                    "AGENTS.md": sha(
                        loaded_instructions or LOADED_INSTRUCTIONS_BY_SLOT[slot]
                    )
                },
                "host_instructions": host_instructions,
            }
            if loading_observed
            else {
                "status": "not_observed",
                "effective_instruction_digests": None,
                "host_instructions": host_instructions,
            }
        ),
        "outcome": outcome,
        "quality": quality,
        "critical_violation": critical_violation,
        "elapsed_seconds": (
            {"status": "observed", "value": elapsed}
            if elapsed is not None
            else {"status": "not_observed", "value": None}
        ),
        "billed_cost": (
            {"status": "observed", "amount": cost, "currency": "USD"}
            if cost is not None
            else {"status": "not_observed", "amount": None, "currency": None}
        ),
        "human_interventions": (
            {
                "status": "observed",
                "count": interventions,
                "counting_rule_digest": sha(INTERVENTION_RULE),
            }
            if interventions is not None
            else {
                "status": "not_observed",
                "count": None,
                "counting_rule_digest": sha(INTERVENTION_RULE),
            }
        ),
        "evidence_digests": {"external_transcript": sha(f"transcript:{cell}")},
    }


# One passing roster where the candidate is strictly better on both axes.
FAILING_CELLS = {
    "old_model_current_instructions": {("small-fix", 1), ("cross-file-change", 2)},
    "new_model_current_instructions": {("cross-file-change", 2)},
    "new_model_candidate_instructions": set(),
}


def adoptable_observations(slots: tuple[str, ...] | None = None) -> list[dict]:
    records = []
    for slot in slots or tuple(OBSERVED_MODEL_BY_SLOT):
        for case_id in CASE_IDS:
            for repetition in (1, 2):
                records.append(
                    observation(
                        slot,
                        case_id,
                        repetition,
                        acceptance_result=(
                            "fail" if (case_id, repetition) in FAILING_CELLS[slot] else "pass"
                        ),
                    )
                )
    return records


class HarnessComparisonBase(unittest.TestCase):
    command = ROOT_COMMAND

    def run_comparison(
        self,
        protocol_payload: dict,
        observations: list[dict],
        *,
        evidence: list[bytes] | None = None,
        ordering_evidence: list[bytes] | None = None,
        fmt: str = "json",
        command: Path | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(
                json.dumps(protocol_payload, indent=2) + "\n", encoding="utf-8"
            )
            args = ["--protocol", str(protocol_path)]
            for index, record in enumerate(observations):
                path = root / f"observation-{index:03d}.json"
                path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                args += ["--observation", str(path)]
            for index, payload in enumerate(
                evidence_payloads(observations) if evidence is None else evidence
            ):
                path = root / f"evidence-{index:03d}.bin"
                path.write_bytes(payload)
                args += ["--evidence", str(path)]
            for index, payload in enumerate(ordering_evidence or []):
                path = root / f"ordering-{index:03d}.txt"
                path.write_bytes(payload)
                args += ["--ordering-evidence", str(path)]
            args += ["--format", fmt]
            return subprocess.run(
                [sys.executable, str(command or self.command), *args],
                cwd=str(cwd or ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

    def report(self, *args, **kwargs) -> dict:
        result = self.run_comparison(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def rejection(self, *args, **kwargs) -> str:
        result = self.run_comparison(*args, **kwargs)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("compare-harness-runs failed:", result.stderr)
        return result.stderr

    def comparison(self, report: dict, name: str) -> dict:
        for entry in report["comparisons"]:
            if entry["comparison"] == name:
                return entry
        self.fail(f"report does not contain the {name} comparison")


class ControlledInputTest(HarnessComparisonBase):
    """Completion condition 1: reject uncontrolled inputs, separate both axes."""

    def test_rejects_altered_task_digest(self) -> None:
        records = adoptable_observations()
        records[0]["task_digest"] = sha("task:tampered")
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("different task digest", message)

    def test_rejects_altered_acceptance_digest(self) -> None:
        records = adoptable_observations()
        records[0]["acceptance_digest"] = sha("acceptance:tampered")
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("different acceptance digest", message)

    def test_rejects_altered_repository_baseline(self) -> None:
        records = adoptable_observations()
        records[1]["repository_baseline"] = sha("baseline:other")
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("different repository baseline digest", message)

    def test_rejects_altered_invariant_and_authority_digests(self) -> None:
        for field, message in (
            ("invariant_digest", "different invariant digest"),
            ("authority_digest", "different authority digest"),
        ):
            records = adoptable_observations()
            records[2][field] = sha(f"{field}:other")
            self.assertIn(
                message,
                self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION]),
            )

    def test_rejects_altered_configuration_digest(self) -> None:
        records = adoptable_observations()
        records[3]["configuration_digest"] = sha("configuration:other")
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("different configuration digest", message)

    def test_rejects_declared_uncontrolled_runtime(self) -> None:
        message = self.rejection(
            protocol(candidate_runtime=ALTERNATE_RUNTIME),
            adoptable_observations(),
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        self.assertIn("uncontrolled runtime inputs", message)

    def test_rejects_hidden_observed_runtime_difference(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["observed_runtime"] = {
                    "status": "observed",
                    "cli_version": ALTERNATE_RUNTIME["cli_version"],
                    "tool_versions": ALTERNATE_RUNTIME["tool_versions"],
                }
            records.append(record)
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("observed uncontrolled runtime inputs", message)

    def test_rejects_protocol_that_moves_two_axes(self) -> None:
        message = self.rejection(
            protocol(candidate_model="model-newer"),
            adoptable_observations(),
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        self.assertIn("changes the declared model outside the instruction axis", message)

    def test_rejects_model_axis_without_a_model_change(self) -> None:
        payload = protocol()
        payload["configurations"]["new_model_current_instructions"]["declared_model"] = "model-old"
        message = self.rejection(
            payload, adoptable_observations(), ordering_evidence=[ORDERING_ATTESTATION]
        )
        self.assertIn("does not change the declared model", message)

    def test_rejects_observed_model_that_contradicts_the_axis(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["observed_model"]["identity"] = "model-other"
            records.append(record)
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("two different models on an instruction-only axis", message)

    def test_separates_the_model_and_instruction_comparisons(self) -> None:
        report = self.report(
            protocol(), adoptable_observations(), ordering_evidence=[ORDERING_ATTESTATION]
        )
        names = [entry["comparison"] for entry in report["comparisons"]]
        self.assertEqual(names, ["model_effect", "instruction_effect"])
        model = self.comparison(report, "model_effect")
        instruction = self.comparison(report, "instruction_effect")
        self.assertEqual(model["axis"], "model")
        self.assertEqual(model["baseline_slot"], "old_model_current_instructions")
        self.assertEqual(model["candidate_slot"], "new_model_current_instructions")
        self.assertEqual(instruction["axis"], "instructions")
        self.assertEqual(instruction["baseline_slot"], "new_model_current_instructions")
        self.assertEqual(instruction["candidate_slot"], "new_model_candidate_instructions")

    def test_reports_a_model_only_comparison_without_the_candidate_slot(self) -> None:
        report = self.report(
            protocol(include_candidate=False),
            adoptable_observations(
                ("old_model_current_instructions", "new_model_current_instructions")
            ),
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        self.assertEqual(
            [entry["comparison"] for entry in report["comparisons"]], ["model_effect"]
        )

    def test_mismatched_reasoning_degrades_to_a_configuration_comparison(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["observed_reasoning_settings"]["effort"] = "high"
            records.append(record)
        report = self.report(
            protocol(candidate_effort="high"), records, ordering_evidence=[ORDERING_ATTESTATION]
        )
        instruction = self.comparison(report, "instruction_effect")
        self.assertEqual(instruction["axis_isolation"]["kind"], "configuration_comparison")
        self.assertFalse(instruction["axis_isolation"]["isolated"])
        self.assertIn("axis_not_isolated", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_rejects_an_intervention_count_from_another_counting_rule(self) -> None:
        records = adoptable_observations()
        records[0]["human_interventions"]["counting_rule_digest"] = sha("another rule")
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("different frozen counting rule", message)


class EvidenceAndFailureTest(HarnessComparisonBase):
    """Completion condition 2: keep observed metrics, refuse unfounded adoption."""

    def test_complete_evidence_supports_adoption_on_both_axes(self) -> None:
        report = self.report(
            protocol(), adoptable_observations(), ordering_evidence=[ORDERING_ATTESTATION]
        )
        for name in ("model_effect", "instruction_effect"):
            entry = self.comparison(report, name)
            self.assertEqual(entry["evidence_blockers"], [], name)
            self.assertEqual(entry["limit_failures"], [], name)
            self.assertEqual(entry["recommendation"], "adopt_candidate", name)
            self.assertTrue(entry["empirical_recommendation_available"], name)

    def test_declared_evidence_that_was_never_supplied_blocks_adoption(self) -> None:
        report = self.report(
            protocol(),
            adoptable_observations(),
            evidence=[],
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        for name in ("model_effect", "instruction_effect"):
            entry = self.comparison(report, name)
            self.assertIn("declared_evidence_not_verified", entry["evidence_blockers"], name)
            self.assertEqual(entry["recommendation"], "insufficient_evidence", name)
            self.assertFalse(entry["empirical_recommendation_available"], name)

    def test_partial_metric_coverage_cannot_stand_in_for_unmeasured_runs(self) -> None:
        records = []
        for record in adoptable_observations():
            if (
                record["slot"] == "new_model_candidate_instructions"
                and record["case_id"] == "small-fix"
                and record["repetition"] == 1
            ):
                record["elapsed_seconds"] = {"status": "not_observed", "value": None}
                record["billed_cost"] = {
                    "status": "not_observed",
                    "amount": None,
                    "currency": None,
                }
                record["human_interventions"] = {
                    "status": "not_observed",
                    "count": None,
                    "counting_rule_digest": sha(INTERVENTION_RULE),
                }
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        for blocker in (
            "elapsed_coverage_incomplete",
            "cost_coverage_incomplete",
            "intervention_coverage_incomplete",
        ):
            self.assertIn(blocker, instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")
        summaries = {entry["slot"]: entry for entry in report["configuration_summaries"]}
        candidate = summaries["new_model_candidate_instructions"]
        self.assertEqual(candidate["elapsed_seconds_all_runs"]["observation_count"], 3)
        self.assertEqual(candidate["elapsed_seconds_all_runs"]["denominator"], 4)

    def test_report_retains_quality_time_cost_and_intervention_coverage(self) -> None:
        report = self.report(
            protocol(), adoptable_observations(), ordering_evidence=[ORDERING_ATTESTATION]
        )
        summaries = {entry["slot"]: entry for entry in report["configuration_summaries"]}
        old = summaries["old_model_current_instructions"]
        self.assertEqual(old["quality_pass_count"], 2)
        self.assertEqual(old["quality_denominator"], 4)
        self.assertEqual(old["quality_pass_rate"], 0.5)
        self.assertEqual(old["elapsed_seconds_all_runs"]["observation_count"], 4)
        self.assertEqual(old["elapsed_seconds_all_runs"]["mean"], 100.0)
        self.assertEqual(old["billed_cost"]["total"], 4.0)
        self.assertEqual(old["billed_cost"]["currencies"], ["USD"])
        self.assertEqual(old["human_interventions"]["total"], 0)
        self.assertEqual(old["human_interventions"]["status"], "observed")
        model = self.comparison(report, "model_effect")
        self.assertEqual(model["quality_pass_rate"]["delta"], 0.25)
        self.assertEqual(model["elapsed_ratio_all_runs"], 1.0)
        self.assertEqual(model["billed_cost_ratio"], 1.0)
        self.assertEqual(model["intervention_delta"], 0)

    def test_failed_and_timed_out_runs_stay_in_the_quality_denominator(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions" and record["case_id"] == "small-fix":
                if record["repetition"] == 1:
                    record.update(
                        observation(
                            record["slot"],
                            record["case_id"],
                            record["repetition"],
                            outcome="timed_out",
                            quality_observed=False,
                            elapsed=900.0,
                        )
                    )
                else:
                    record.update(
                        observation(
                            record["slot"],
                            record["case_id"],
                            record["repetition"],
                            outcome="model_unavailable",
                            quality_observed=False,
                        )
                    )
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        summaries = {entry["slot"]: entry for entry in report["configuration_summaries"]}
        candidate = summaries["new_model_candidate_instructions"]
        self.assertEqual(candidate["quality_denominator"], 4)
        self.assertEqual(candidate["quality_pass_count"], 2)
        self.assertEqual(candidate["outcomes"]["timed_out"], 1)
        self.assertEqual(candidate["outcomes"]["model_unavailable"], 1)
        # Successful-run timing is reported beside its own denominator and never
        # replaces the all-run denominator.
        self.assertEqual(candidate["elapsed_seconds_completed_runs"]["denominator"], 2)
        self.assertEqual(candidate["elapsed_seconds_all_runs"]["denominator"], 4)
        self.assertEqual(candidate["elapsed_seconds_completed_runs"]["mean"], 100.0)
        self.assertEqual(candidate["elapsed_seconds_all_runs"]["mean"], 300.0)
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("candidate_run_not_completed", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_timed_out_run_must_record_its_elapsed_seconds(self) -> None:
        records = adoptable_observations()
        records[0].update(
            observation(
                records[0]["slot"],
                records[0]["case_id"],
                records[0]["repetition"],
                outcome="timed_out",
                quality_observed=False,
                elapsed=None,
            )
        )
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("must record its elapsed seconds", message)

    def test_critical_violation_blocks_adoption_despite_faster_and_cheaper_runs(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["elapsed_seconds"] = {"status": "observed", "value": 1.0}
                record["billed_cost"] = {"status": "observed", "amount": 0.01, "currency": "USD"}
                if record["case_id"] == "small-fix" and record["repetition"] == 1:
                    record["critical_violation"] = True
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertEqual(instruction["critical_violations"]["candidate"], 1)
        self.assertEqual(instruction["recommendation"], "blocked_critical_failure")
        self.assertFalse(instruction["empirical_recommendation_available"])

    def test_baseline_critical_violation_withholds_the_empirical_recommendation(self) -> None:
        records = []
        for record in adoptable_observations():
            if (
                record["slot"] == "new_model_current_instructions"
                and record["case_id"] == "small-fix"
                and record["repetition"] == 1
            ):
                record["critical_violation"] = True
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertEqual(instruction["critical_violations"]["baseline"], 1)
        self.assertEqual(instruction["critical_violations"]["candidate"], 0)
        self.assertIn("critical_violation_observed", instruction["critical_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")
        self.assertFalse(instruction["empirical_recommendation_available"])

    def test_missing_quality_evidence_blocks_adoption(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions" and record["case_id"] == "small-fix":
                record["quality"] = {
                    "status": "not_observed",
                    "acceptance_result": None,
                    "judgment": None,
                }
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("missing_quality_evidence", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_agent_self_report_judgment_is_inadmissible(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["quality"]["judgment"]["kind"] = "agent_self_report"
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("inadmissible_quality_evidence", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")
        cells = {entry["cell"]: entry for entry in report["observations"]}
        sample = cells["new_model_candidate_instructions/small-fix#1"]
        self.assertFalse(sample["quality_admissible"])
        self.assertEqual(sample["quality_judgment"]["kind"], "agent_self_report")

    def test_judgment_must_bind_the_frozen_acceptance_item_and_rubric(self) -> None:
        for field, message in (
            ("acceptance_item_digest", "acceptance item that differs"),
            ("rubric_digest", "rubric that differs"),
        ):
            records = adoptable_observations()
            records[0]["quality"]["judgment"][field] = sha("stale")
            self.assertIn(
                message,
                self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION]),
            )

    def test_unpaired_runs_cannot_produce_an_adoption_recommendation(self) -> None:
        records = [
            record
            for record in adoptable_observations()
            if not (
                record["slot"] == "new_model_candidate_instructions"
                and record["case_id"] == "cross-file-change"
                and record["repetition"] == 2
            )
        ]
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertFalse(report["coverage"]["complete"])
        self.assertEqual(
            report["coverage"]["missing_cells"],
            ["new_model_candidate_instructions/cross-file-change#2"],
        )
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("unpaired_cells", instruction["evidence_blockers"])
        self.assertIn("incomplete_coverage", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_synthetic_fixtures_cannot_produce_an_adoption_recommendation(self) -> None:
        records = [
            observation(slot, case_id, repetition, fixture_kind="synthetic")
            for slot in OBSERVED_MODEL_BY_SLOT
            for case_id in CASE_IDS
            for repetition in (1, 2)
        ]
        report = self.report(
            protocol(fixture_kind="synthetic"), records, ordering_evidence=[ORDERING_ATTESTATION]
        )
        for name in ("model_effect", "instruction_effect"):
            entry = self.comparison(report, name)
            self.assertIn("synthetic_fixture", entry["evidence_blockers"])
            self.assertEqual(entry["recommendation"], "insufficient_evidence")

    def test_single_repetition_is_inconclusive(self) -> None:
        records = [
            observation(slot, case_id, 1)
            for slot in OBSERVED_MODEL_BY_SLOT
            for case_id in CASE_IDS
        ]
        report = self.report(
            protocol(repetitions=1), records, ordering_evidence=[ORDERING_ATTESTATION]
        )
        model = self.comparison(report, "model_effect")
        self.assertIn("insufficient_repetitions", model["evidence_blockers"])
        self.assertEqual(model["recommendation"], "insufficient_evidence")

    def test_duplicate_cell_is_rejected(self) -> None:
        records = adoptable_observations()
        duplicate = json.loads(json.dumps(records[0]))
        duplicate["evidence_digests"] = {"external_transcript": sha("other")}
        records.append(duplicate)
        message = self.rejection(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        self.assertIn("duplicate run observation for cell", message)

    def test_evidence_file_must_match_a_declared_digest(self) -> None:
        message = self.rejection(
            protocol(),
            adoptable_observations(),
            evidence=[b"unrelated bytes\n"],
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        self.assertIn("matches no declared evidence digest", message)

    def test_verified_evidence_is_bound_to_its_observation(self) -> None:
        records = adoptable_observations()
        payload = b"transcript bytes\n"
        records[0]["evidence_digests"] = {"external_transcript": digest_bytes(payload)}
        report = self.report(
            protocol(),
            records,
            evidence=[payload],
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        self.assertEqual(len(report["evidence"]), 1)
        entry = report["evidence"][0]
        self.assertEqual(entry["verification"], "matched")
        self.assertEqual(entry["digest"], digest_bytes(payload))
        self.assertTrue(any(":external_transcript" in bound for bound in entry["bound_to"]))

    def test_nonregular_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fifo = Path(tmp) / "protocol.json"
            os.mkfifo(fifo)
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.command),
                    "--protocol",
                    str(fifo),
                    "--observation",
                    str(fifo),
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must be a regular file", result.stderr)

    def test_slower_and_costlier_candidate_keeps_the_current_configuration(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["elapsed_seconds"] = {"status": "observed", "value": 400.0}
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertEqual(instruction["evidence_blockers"], [])
        self.assertIn("elapsed_limit_failed", instruction["limit_failures"])
        self.assertEqual(instruction["recommendation"], "keep_current")

    def test_equal_results_keep_the_current_configuration(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["quality"]["acceptance_result"] = (
                    "fail" if record["case_id"] == "cross-file-change" and record["repetition"] == 2 else "pass"
                )
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertEqual(instruction["quality_pass_rate"]["delta"], 0.0)
        self.assertEqual(instruction["evidence_blockers"], [])
        self.assertEqual(instruction["recommendation"], "keep_current")

    def test_unobserved_cost_is_never_inferred(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["billed_cost"] = {"status": "not_observed", "amount": None, "currency": None}
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        summaries = {entry["slot"]: entry for entry in report["configuration_summaries"]}
        candidate = summaries["new_model_candidate_instructions"]
        self.assertEqual(candidate["billed_cost"]["status"], "not_observed")
        self.assertIsNone(candidate["billed_cost"]["total"])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIsNone(instruction["billed_cost_ratio"])
        self.assertIn("cost_not_comparable", instruction["evidence_blockers"])
        self.assertIn("billed_cost", report["never_inferred"])


class DeclaredVersusVerifiedTest(HarnessComparisonBase):
    """Completion condition 3: separate declaration from reviewed evidence."""

    def test_declared_limits_and_holdout_status_stay_declared(self) -> None:
        report = self.report(
            protocol(), adoptable_observations(), ordering_evidence=[ORDERING_ATTESTATION]
        )
        declared = report["declared_only"]
        self.assertEqual(declared["holdout_status"], "withheld")
        self.assertEqual(declared["declared_frozen_at"], "2026-09-01T00:00:00Z")
        self.assertIn("not independently reviewed ordering evidence", declared["note"])
        self.assertEqual(declared["decision_limits"]["max_elapsed_ratio"], 1.5)

    def test_unobserved_runtime_is_never_read_as_a_controlled_runtime(self) -> None:
        records = [
            observation(
                record["slot"],
                record["case_id"],
                record["repetition"],
                acceptance_result=record["quality"]["acceptance_result"],
                runtime_observed=record["slot"] != "new_model_candidate_instructions",
            )
            for record in adoptable_observations()
        ]
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("runtime_not_confirmed", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_observed_reasoning_settings_must_confirm_the_declaration(self) -> None:
        records = [
            observation(
                record["slot"],
                record["case_id"],
                record["repetition"],
                acceptance_result=record["quality"]["acceptance_result"],
                reasoning_effort=(
                    "high"
                    if record["slot"] == "new_model_candidate_instructions"
                    else "medium"
                ),
            )
            for record in adoptable_observations()
        ]
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("reasoning_settings_not_confirmed", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_an_instruction_effect_requires_an_observed_instruction_change(self) -> None:
        records = [
            observation(
                record["slot"],
                record["case_id"],
                record["repetition"],
                acceptance_result=record["quality"]["acceptance_result"],
                loaded_instructions="instructions-current",
            )
            for record in adoptable_observations()
        ]
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("instruction_identity_not_confirmed", instruction["evidence_blockers"])
        self.assertIn("instruction_change_not_observed", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")
        # The model axis never depended on the instruction identity, so it is
        # unaffected by an unchanged instruction observation.
        self.assertEqual(
            self.comparison(report, "model_effect")["recommendation"], "adopt_candidate"
        )

    def test_absent_ordering_evidence_withholds_every_recommendation(self) -> None:
        report = self.report(
            protocol(ordering_status=None), adoptable_observations()
        )
        self.assertEqual(report["ordering_evidence"]["state"], "absent")
        for name in ("model_effect", "instruction_effect"):
            entry = self.comparison(report, name)
            self.assertIn(
                "ordering_evidence_not_independently_reviewed", entry["evidence_blockers"]
            )
            self.assertEqual(entry["recommendation"], "insufficient_evidence")

    def test_unsupplied_ordering_attestation_stays_unverified(self) -> None:
        report = self.report(protocol(), adoptable_observations())
        ordering = report["ordering_evidence"]
        self.assertEqual(ordering["state"], "declared_unverified")
        self.assertEqual(ordering["verification"], "not_supplied")
        self.assertIn("cannot authenticate", ordering["authentication_note"])
        self.assertEqual(
            self.comparison(report, "model_effect")["recommendation"], "insufficient_evidence"
        )

    def test_declared_only_ordering_evidence_is_not_independent_review(self) -> None:
        report = self.report(
            protocol(ordering_status="declared"),
            adoptable_observations(),
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        ordering = report["ordering_evidence"]
        self.assertEqual(ordering["state"], "declared_link_verified")
        self.assertEqual(ordering["verification"], "digest_matched")
        self.assertEqual(
            self.comparison(report, "model_effect")["recommendation"], "insufficient_evidence"
        )

    def test_mismatched_ordering_attestation_is_rejected(self) -> None:
        message = self.rejection(
            protocol(), adoptable_observations(), ordering_evidence=[b"other attestation\n"]
        )
        self.assertIn("does not match the declared attestation digest", message)

    def test_holdout_used_for_tuning_blocks_adoption(self) -> None:
        report = self.report(
            protocol(holdout_status="used_for_tuning"),
            adoptable_observations(),
            ordering_evidence=[ORDERING_ATTESTATION],
        )
        self.assertEqual(report["declared_only"]["holdout_status"], "used_for_tuning")
        for name in ("model_effect", "instruction_effect"):
            entry = self.comparison(report, name)
            self.assertIn("holdout_used_for_tuning", entry["evidence_blockers"])
            self.assertEqual(entry["recommendation"], "insufficient_evidence")

    def test_unobserved_instruction_loading_blocks_instruction_attribution(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["instruction_loading"] = {
                    "status": "not_observed",
                    "effective_instruction_digests": None,
                    "host_instructions": "known",
                }
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("instruction_loading_not_observed", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")
        # The model axis does not depend on instruction loading evidence.
        self.assertEqual(
            self.comparison(report, "model_effect")["recommendation"], "adopt_candidate"
        )

    def test_unknown_host_instructions_block_instruction_attribution(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_candidate_instructions":
                record["instruction_loading"]["host_instructions"] = "unknown"
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        instruction = self.comparison(report, "instruction_effect")
        self.assertIn("unknown_host_instructions", instruction["evidence_blockers"])
        self.assertEqual(instruction["recommendation"], "insufficient_evidence")

    def test_declared_configuration_never_stands_in_for_observed_execution(self) -> None:
        records = []
        for record in adoptable_observations():
            if record["slot"] == "new_model_current_instructions":
                record["observed_model"] = {
                    "status": "not_observed",
                    "identity": None,
                    "resolved_snapshot": None,
                }
            records.append(record)
        report = self.report(protocol(), records, ordering_evidence=[ORDERING_ATTESTATION])
        cells = {entry["cell"]: entry for entry in report["observations"]}
        sample = cells["new_model_current_instructions/small-fix#1"]
        self.assertEqual(sample["declared_model"], "model-new")
        self.assertEqual(sample["observed_model"]["status"], "not_observed")
        model = self.comparison(report, "model_effect")
        self.assertIn("model_identity_not_observed", model["evidence_blockers"])
        self.assertEqual(model["recommendation"], "insufficient_evidence")

    def test_text_report_states_its_boundaries(self) -> None:
        result = self.run_comparison(
            protocol(),
            adoptable_observations(),
            ordering_evidence=[ORDERING_ATTESTATION],
            fmt="text",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for marker in (
            "## Declared, not verified",
            "cannot authenticate the real-world truth",
            "produces no provider, policy, or plan lifecycle effect",
            "never offset by lower cost",
            "recommendation: adopt_candidate",
        ):
            self.assertIn(marker, result.stdout)


class GeneratedProjectParityTest(HarnessComparisonBase):
    """Completion condition 4: root and generated parity with narrow routing."""

    def render_generated_command(self, destination: Path) -> Path:
        scripts = destination / ".project-agent-workflow" / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        rendered = destination / GENERATED_RELATIVE
        shutil.copy2(TEMPLATE_COMMAND, rendered)
        return rendered

    def test_root_wrapper_and_rendered_generated_command_agree(self) -> None:
        payload = protocol()
        records = adoptable_observations()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "generated-project"
            project.mkdir()
            rendered = self.render_generated_command(project)
            self.assertTrue(rendered.is_file())
            for fmt in ("json", "text"):
                root_result = self.run_comparison(
                    payload,
                    records,
                    ordering_evidence=[ORDERING_ATTESTATION],
                    fmt=fmt,
                    command=ROOT_COMMAND,
                    cwd=ROOT,
                )
                generated_result = self.run_comparison(
                    payload,
                    records,
                    ordering_evidence=[ORDERING_ATTESTATION],
                    fmt=fmt,
                    command=Path(GENERATED_RELATIVE),
                    cwd=project,
                )
                self.assertEqual(root_result.returncode, 0, root_result.stderr)
                self.assertEqual(generated_result.returncode, 0, generated_result.stderr)
                self.assertEqual(root_result.stdout, generated_result.stdout, fmt)

    def test_root_and_generated_commands_reject_identically(self) -> None:
        payload = protocol()
        records = adoptable_observations()
        records[0]["repository_baseline"] = sha("baseline:other")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "generated-project"
            project.mkdir()
            self.render_generated_command(project)
            root_result = self.run_comparison(
                payload, records, command=ROOT_COMMAND, cwd=ROOT
            )
            generated_result = self.run_comparison(
                payload, records, command=Path(GENERATED_RELATIVE), cwd=project
            )
        self.assertEqual(root_result.returncode, 1)
        self.assertEqual(generated_result.returncode, 1)
        self.assertEqual(root_result.stderr, generated_result.stderr)

    def test_root_wrapper_delegates_to_the_template_implementation(self) -> None:
        wrapper = ROOT_COMMAND.read_text(encoding="utf-8")
        self.assertIn("template", wrapper)
        self.assertIn("compare-harness-runs.py", wrapper)
        for command in (ROOT_COMMAND, TEMPLATE_COMMAND):
            self.assertTrue(command.stat().st_mode & 0o111, command)

    def test_specifications_stay_aligned(self) -> None:
        root_spec = (ROOT / "docs/agent/SPEC_HARNESS_EVALUATION.md").read_text(encoding="utf-8")
        generated_spec = (
            ROOT / "template/.project-agent-workflow/docs/agent/SPEC_HARNESS_EVALUATION.md"
        ).read_text(encoding="utf-8")
        normalized = (
            generated_spec.replace(".project-agent-workflow/skills/", ".codex/skills/")
            .replace(".project-agent-workflow/", "")
            .replace(".agents/skills/", ".codex/skills/")
        )
        self.assertEqual(root_spec, normalized)
        self.assertIn("`scripts/compare-harness-runs.py`", root_spec)
        self.assertIn(
            "`.project-agent-workflow/scripts/compare-harness-runs.py`", generated_spec
        )

    def test_routing_applies_only_to_harness_comparison_work(self) -> None:
        for path, prefix in (
            ("docs/agent/spec-index.yaml", ""),
            (
                "template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja",
                ".project-agent-workflow/",
            ),
        ):
            text = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("  harness_evaluation:", text)
            self.assertIn(f"      - {prefix}docs/agent/SPEC_HARNESS_EVALUATION.md", text)
            route = text.split("  harness_evaluation:", 1)[1].split("\n\n", 1)[0]
            self.assertIn("paired local harness run records", route)
            self.assertIn("not general benchmarking, planning, or validation work", route)
            # The new specification must not be forced onto unrelated routes.
            others = text.replace(route, "")
            self.assertNotIn("SPEC_HARNESS_EVALUATION.md", others)

    def test_command_is_distributed_through_the_existing_inventory(self) -> None:
        inventory = (ROOT / "scripts/project_workflow/copier_inventory.py").read_text(
            encoding="utf-8"
        )
        for entry in (
            '"scripts/compare-harness-runs.py"',
            '"template/.project-agent-workflow/scripts/compare-harness-runs.py"',
            '".project-agent-workflow/scripts/compare-harness-runs.py"',
            '"docs/agent/SPEC_HARNESS_EVALUATION.md"',
            '"template/.project-agent-workflow/docs/agent/SPEC_HARNESS_EVALUATION.md"',
            '".project-agent-workflow/docs/agent/SPEC_HARNESS_EVALUATION.md"',
            '"tests/test-harness-comparison.py"',
            '"tests/fixtures/harness-comparison/cases.json"',
            '"tests/fixtures/harness-comparison/evaluation-protocol.md"',
        ):
            self.assertIn(entry, inventory)

    def test_focused_checks_are_registered_in_the_required_lint(self) -> None:
        lint = (ROOT / "scripts/lint-project-workflow.sh").read_text(encoding="utf-8")
        self.assertIn('python3 "$root/tests/test-harness-comparison.py"', lint)
        self.assertIn('python3 "$root/tests/test-harness-comparison.py" --generated', lint)
        smoke = (ROOT / "tests/smoke.sh").read_text(encoding="utf-8")
        self.assertIn(".project-agent-workflow/scripts/compare-harness-runs.py", smoke)
        self.assertIn("harness_evaluation:", smoke)

    def test_fixtures_are_declared_synthetic_and_hold_no_holdout(self) -> None:
        fixture = json.loads(
            (ROOT / "tests/fixtures/harness-comparison/cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["fixture_kind"], "synthetic")
        self.assertFalse(fixture["holdout"]["present"])
        kinds = {item["workload_kind"] for item in fixture["tuning_cases"]}
        self.assertEqual(
            kinds,
            {"small_fix", "cross_file_change", "preserved_dirty_edit", "ambiguous_request"},
        )
        self.assertTrue(fixture["historical_failure_cases"])
        for item in fixture["historical_failure_cases"]:
            self.assertEqual(item["workload_kind"], "previous_verification_failure")
        recipe = (ROOT / "tests/fixtures/harness-comparison/evaluation-protocol.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "never use its result to retune",
            "A holdout result is used to tune the candidate further.",
            "Only successful runs are compared.",
            "performance remains",
        ):
            self.assertIn(marker, recipe)


def build_suite(generated_only: bool) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    if generated_only:
        return loader.loadTestsFromTestCase(GeneratedProjectParityTest)
    suite = unittest.TestSuite()
    for case_class in (
        ControlledInputTest,
        EvidenceAndFailureTest,
        DeclaredVersusVerifiedTest,
        GeneratedProjectParityTest,
    ):
        suite.addTests(loader.loadTestsFromTestCase(case_class))
    return suite


if __name__ == "__main__":
    generated = "--generated" in sys.argv[1:]
    unexpected = [item for item in sys.argv[1:] if item != "--generated"]
    if unexpected:
        raise SystemExit(f"unsupported arguments: {unexpected}")
    runner = unittest.TextTestRunner(verbosity=1)
    raise SystemExit(0 if runner.run(build_suite(generated)).wasSuccessful() else 1)
