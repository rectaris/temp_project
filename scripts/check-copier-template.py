#!/usr/bin/env python3
"""Static checks for the Copier template without requiring Copier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import re
import subprocess
import sys
import os
from typing import Any
from itertools import combinations, product
from pathlib import Path

from project_workflow.copier_inventory import (
    CONDITIONAL_GENERATED,
    EXPECTED_CHOICE_VALUES,
    EXPECTED_DEFAULT_VALUES,
    GENERATED_REQUIRED,
    JAPANESE_RE,
    PAIRWISE_FIXTURE,
    QUESTIONS,
    REMOVED_ACTIVATION_QUESTIONS,
    REMOVED_LOCAL_WORKFLOW_QUESTIONS,
    SOURCE_PYTHON_COMPILE,
    SOURCE_REQUIRED,
    SOURCE_SHELL_LINT,
)


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"template check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def normalized_template_core(path: str) -> str:
    return read(path).replace(".project-agent-workflow/", "").replace(".agents/skills/", ".codex/skills/")


def require_sequential_worker() -> None:
    path = ROOT / "template/.codex/agents/sequential_plan_worker.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "sequential_plan_worker"',
        'model = "gpt-5.3-codex-spark"',
        'model_reasoning_effort = "medium"',
        'sandbox_mode = "read-only"',
        "Do not process the next active plan",
        "Do not spawn descendant agents",
        "Do not edit the assigned plan's status",
        "Do not commit changes",
        ".project-agent-workflow/scripts/run-sandboxed-plan-worker.py run <plan>",
    )
    for marker in required:
        if marker not in text:
            fail(f"sequential worker missing required contract: {marker}")


def require_agent_model_profiles() -> None:
    expected = {
        "change_reviewer": ("gpt-5.6-sol", "high"),
        "docs_researcher": ("gpt-5.6-luna", "medium"),
        "evidence_synthesizer": ("gpt-5.6-luna", "xhigh"),
        "fast_scoped_worker": ("gpt-5.3-codex-spark", "medium"),
        "repo_explorer": ("gpt-5.6-luna", "low"),
        "scoped_worker": ("gpt-5.6-terra", "medium"),
        "sequential_plan_worker": ("gpt-5.3-codex-spark", "medium"),
    }
    for name, (model, effort) in expected.items():
        text = read(f"template/.codex/agents/{name}.toml")
        for marker in (f'model = "{model}"', f'model_reasoning_effort = "{effort}"'):
            if marker not in text:
                fail(f"{name} missing fixed model profile: {marker}")


def require_fast_scoped_worker() -> None:
    path = ROOT / "template/.codex/agents/fast_scoped_worker.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "fast_scoped_worker"',
        'model = "gpt-5.3-codex-spark"',
        'model_reasoning_effort = "medium"',
        'sandbox_mode = "workspace-write"',
        "Require an explicit write scope and predetermined validation",
        "Stop and report unexpected tracked-file deletion",
        "Do not spawn descendant agents",
        "Do not commit, tag, push, release",
    )
    for marker in required:
        if marker not in text:
            fail(f"fast scoped worker missing required contract: {marker}")


def require_evidence_synthesizer() -> None:
    path = ROOT / "template/.codex/agents/evidence_synthesizer.toml"
    text = path.read_text(encoding="utf-8")
    required = (
        'name = "evidence_synthesizer"',
        'model = "gpt-5.6-luna"',
        'model_reasoning_effort = "xhigh"',
        'sandbox_mode = "read-only"',
        "compares multiple repositories, logs, specifications, implementation alternatives, or cause hypotheses",
        "Do not edit files, execute external writes",
        "Do not spawn descendant agents",
        "final high-risk judgment",
    )
    for marker in required:
        if marker not in text:
            fail(f"evidence synthesizer missing required contract: {marker}")


def require_orchestration_policy_markers() -> None:
    template_spec = read("template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md").lower()
    template_agents = read("template/.project-agent-workflow/AGENTS.md.jinja").lower()
    template_plan_workflow = read("template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md").lower()
    root_orchestration = read("references/orchestration.md").lower()
    shared_markers = (
        "per-task user instruction",
        "repository-wide",
        "independent helper work",
        "main agent owns",
        "expected context reduction",
        "parallelism",
        "review value",
        "repository breadth alone",
        "proactively",
        "non-overlapping",
        "short deterministic",
        "cost",
        "write scope",
        "context files read-only",
        "advisory",
        "external writes",
        "authorization",
        "destructive",
        "secrets",
        "separate explicit policy",
        "final high-risk",
        "final report",
        "role",
        "acceptance",
        "admissible implementation slice",
        "implementation_risk",
        "implementation_ambiguity",
        "spark medium",
        "terra medium",
        "state path outside the repository",
        "orchestration run identifier",
        "symlinked targets or ancestors",
        "skipped known-unavailable starts",
        "finite and nonnegative",
        "prompts, raw output, environment values, or credentials",
        "worker completion receipt",
        "consumed-attempt replay rejection",
        "receipt claims are advisory only",
        "run-sandboxed-plan-worker.py correct",
        "aggregate patch",
        "at most two correction rounds",
        "rejected patch never touches the source",
        "candidate generation and correction do not run plan validation",
        "parent diff review",
        "critical-invariant review",
        "focused_validation",
        "validation_authority_scope",
        "validation_witness_map",
        "authoritative_only_reason",
        "earliest parent-owned witness",
        "network-isolated review clone",
        "authoritative",
        "bounded parent implementation",
        "independent change review",
        "diagnosis_required",
        "failed-operation digest",
        "observed exit status",
        "inconclusive",
        "disputed",
        "repair_required",
        "repair-evidence",
        "fresh plan digest",
        "replan_required",
        "requirement change needs separate explicit user authorization",
        "elapsed time is telemetry",
        "plan-execution-state.py",
        "independent-review receipt",
        "--plan-execution-state",
        "--predecessor-plan-execution-state",
        "predecessor_acceptance",
        "writable_attempt_started",
        "attempt_closed",
        "successor_claimed",
        "review_evidence_digest",
        "acceptance_unmet",
        "multiple_invariants_coupled",
        "global task lock",
        "plan_execution_attempt_id",
        "at least 30 percent lower median",
        "p95 time no more than 10 percent worse",
        "run-sandboxed-plan-worker.py run",
        "read-only",
        "worker completion receipt",
    )
    for marker in shared_markers:
        if marker not in template_spec:
            fail(f"template managed SPEC_ORCHESTRATION missing marker: {marker}")
    for marker in (
        "per-task user instruction",
        "do not delegate",
        "final ownership",
        "main session",
        "external writes",
        "secrets",
        "short deterministic",
        "authorization",
        "advisory",
        "role",
        "scope",
        "acceptance",
        "run-sandboxed-plan-worker.py",
        "read-only",
        "diagnosis_required",
        "confirmed",
        "inconclusive",
        "disputed",
        "repair_required",
        "source-plan scope",
        "validation authority",
        "invariant boundaries",
        "source plan `deferred`",
        "fresh run",
        "never reopen a stopped ledger run",
        "never relabel requirement, authority, or security-boundary drift",
    ):
        if marker not in template_agents:
            fail(f"template managed AGENTS missing marker: {marker}")
    for marker in (
        "repair_required",
        "diagnosis_required",
        "failed-operation digest",
        "observed exit status",
        "confirmed",
        "inconclusive",
        "disputed",
        "independently repairable defect",
        "bounded write and validation scope",
        "source-plan scope",
        "validation authority",
        "invariant boundaries",
        "source acceptance",
        "external-effect authority",
        "separate bounded repair plan",
        "never reopen a `repair_required` execution run",
        "fresh plan digest",
        "security-boundary",
    ):
        if marker not in template_plan_workflow:
            fail(f"template SPEC_PLAN_WORKFLOW missing independent-repair marker: {marker}")
    for marker in (
        "per-task user instruction",
        "without waiting for a per-task user instruction",
        "repository-wide",
        "proactively",
        "independent helper work",
        "short deterministic",
        "multiple independent",
        "cross-specification",
        "validation, security, or orchestration",
        "large or dense",
        "context files read-only",
        "advisory",
        "external writes",
        "authorization",
        "separate explicit policy",
        "secrets",
        "destructive",
        "final report",
        "final high-risk",
        "write scope",
        "acceptance",
        "run-sandboxed-plan-worker.py run",
        "read-only",
    ):
        if marker not in root_orchestration:
            fail(f"root orchestration policy missing marker for template parity: {marker}")

    try:
        staged = json.loads(read("tests/fixtures/orchestration/staged-acceptance.json"))
    except json.JSONDecodeError as exc:
        fail(f"invalid staged orchestration fixture: {exc}")
    if staged.get("schema_version") != 2:
        fail("staged orchestration fixture is missing the event-evidence schema")
    if staged.get("performance_claim_status") not in {"measurement_pending", "measured_pass"}:
        fail("staged orchestration performance claim status is invalid")
    if staged.get("measured_evidence_file") != "staged-paired-measured-example.json":
        fail("staged orchestration must identify its paired runner evidence")
    if staged.get("evidence_file") != "staged-baseline-events.json" or staged.get("holdout_file") != "staged-holdout-events.json":
        fail("staged orchestration evidence and holdout must remain physically separated")
    evidence = json.loads(read("tests/fixtures/orchestration/staged-baseline-events.json"))
    holdout = json.loads(read("tests/fixtures/orchestration/staged-holdout-events.json"))
    scenarios = [*evidence.get("scenarios", []), *holdout.get("scenarios", [])]
    thresholds = staged.get("thresholds", {})
    if evidence.get("schema_version") != 2 or holdout.get("schema_version") != 2:
        fail("staged orchestration evidence must use commit-backed schema")
    if evidence.get("version") != "2026-08-13-plans-062-064-070-v3":
        fail("staged orchestration fixture is missing the versioned baseline")
    if {item.get("class") for item in scenarios if isinstance(item, dict)} != {"median", "edge", "negative", "holdout"}:
        fail("staged orchestration fixture must cover median, edge, negative, and holdout")
    holdouts = [item for item in scenarios if isinstance(item, dict) and item.get("class") == "holdout"]
    if len(holdouts) != 1 or holdouts[0].get("used_for_tuning") is not False:
        fail("staged orchestration holdout must remain outside reusable tuning prompts")
    if thresholds != {
        "minimum_median_reduction_fraction": 0.3,
        "maximum_p95_regression_fraction": 0.1,
        "maximum_implementation_generations": 3,
        "maximum_known_unavailable_primary_starts": 1,
        "authoritative_full_suite_runs_per_accepted_candidate": 1,
        "maximum_unresolved_high_medium_findings": 0,
    }:
        fail("staged orchestration thresholds differ from the accepted contract")

    restructuring = json.loads(read("tests/fixtures/orchestration/plan-restructuring-scenarios.json"))
    restructuring_holdout = json.loads(read("tests/fixtures/orchestration/plan-restructuring-holdout.json"))
    if set(restructuring) != {"schema_version", "requirements", "holdout_file", "scenarios"}:
        fail("plan restructuring fixture has an invalid exact shape")
    if restructuring.get("schema_version") != 1 or restructuring.get("holdout_file") != "plan-restructuring-holdout.json":
        fail("plan restructuring fixture has an unsupported schema or holdout")
    requirements = restructuring.get("requirements")
    if not isinstance(requirements, list) or {item.get("id") for item in requirements if isinstance(item, dict)} != {"P1", "P2", "P3", "P4", "P5"}:
        fail("plan restructuring fixture lost a critical requirement")
    if any(not isinstance(item, dict) or item.get("critical") is not True for item in requirements):
        fail("plan restructuring requirements must remain critical")
    expected_cases = {
        "median-multiple-independent-invariants": ("median", ["P1", "P2", "P4"], "multiple_independent_invariants", "atomic_restructure", "replan_required"),
        "edge-delegated-correction-budget-exhausted": ("edge", ["P1", "P2", "P4"], "candidate_correction_budget_exhausted", "atomic_restructure", "replan_required"),
        "edge-parent-direct-review-budget-exhausted": ("edge", ["P1", "P2", "P4"], "parent_remediation_budget_exhausted", "atomic_restructure", "replan_required"),
        "negative-scope-drift": ("negative", ["P1", "P2", "P4"], "scope_drift", "atomic_restructure", "replan_required"),
        "negative-specification-drift": ("negative", ["P1", "P2", "P4"], "spec_drift", "atomic_restructure", "replan_required"),
        "negative-security-boundary-drift": ("negative", ["P1", "P2", "P4"], "security_boundary_drift", "atomic_restructure", "replan_required"),
        "negative-post-authoritative-design-change": ("negative", ["P1", "P2", "P4"], "post_authoritative_design_change", "atomic_restructure", "replan_required"),
        "median-plan119-independent-validation-authorization-repair": ("median", ["P1", "P4", "P5"], "independent_repair_required", "defer_source_and_create_bounded_repair_plan", "repair_required"),
        "edge-repair-required-run-cannot-continue": ("edge", ["P1", "P5"], "independent_repair_required", "reject_transition", "repair_required"),
        "edge-checked-repair-resumes-source-with-fresh-run": ("edge", ["P5"], "repair_prerequisite_satisfied", "resume_source_with_fresh_execution", "in_progress"),
        "negative-independent-repair-with-source-scope-drift": ("negative", ["P1", "P2", "P5"], "scope_drift", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-independent-repair-with-validation-authority-drift": ("negative", ["P1", "P2", "P5"], "spec_drift", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-independent-repair-with-invariant-boundary-drift": ("negative", ["P1", "P2", "P5"], "multiple_independent_invariants", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-independent-repair-with-altered-authority": ("negative", ["P1", "P2", "P3", "P5"], "security_boundary_drift", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-unauthorized-requirement-replacement": ("negative", ["P3"], "requirement_change_not_authorized", "reject_transition", "pending_user_authorization"),
    }
    scenarios = restructuring.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(expected_cases):
        fail("plan restructuring scenario set is incomplete")
    observed: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "class", "used_for_tuning", "requirements", "input", "expected"}:
            fail("plan restructuring scenario has an invalid exact shape")
        scenario_id = scenario["id"]
        if scenario_id not in expected_cases or scenario_id in observed:
            fail("plan restructuring scenario identifiers differ from the accepted contract")
        scenario_class, covered, reason, action, state = expected_cases[scenario_id]
        if scenario["class"] != scenario_class or scenario["used_for_tuning"] is not True:
            fail(f"plan restructuring scenario class/tuning differs: {scenario_id}")
        if scenario["requirements"] != covered or scenario["expected"] != {"state": state, "reason_code": reason, "next_action": action}:
            fail(f"plan restructuring expected result differs: {scenario_id}")
        observed.add(scenario_id)
    if observed != set(expected_cases):
        fail("plan restructuring scenario set differs from the accepted contract")
    expected_holdout = [{
        "id": "holdout-security-drift-with-dirty-product-path",
        "class": "holdout",
        "used_for_tuning": False,
        "requirements": ["P1", "P2", "P4"],
        "input": {"event": "security_boundary_drift", "dirty_product_path": "config/project-owned.yaml"},
        "expected": {"state": "replan_required", "reason_code": "security_boundary_drift", "next_action": "atomic_restructure_preserving_dirty_path"},
    }, {
        "id": "holdout-independent-repair-rejects-stopped-run-reuse",
        "class": "holdout",
        "used_for_tuning": False,
        "requirements": ["P1", "P5"],
        "input": {"source_plan_status": "deferred", "repair_plan_status": "checked", "execution_run": "stopped_repair_required_run"},
        "expected": {"state": "repair_required", "reason_code": "independent_repair_required", "next_action": "reject_transition_and_initialize_fresh_run"},
    }]
    if set(restructuring_holdout) != {"schema_version", "scenarios"} or restructuring_holdout.get("schema_version") != 1:
        fail("plan restructuring holdout has an invalid exact shape")
    if restructuring_holdout.get("scenarios") != expected_holdout:
        fail("plan restructuring holdout must remain fixed and outside tuning scenarios")

    worker_scenarios_path = "tests/fixtures/orchestration/worker-contract-scenarios.json"
    worker_holdout_path = "tests/fixtures/orchestration/worker-contract-holdout.json"
    worker_scenarios_bytes = (ROOT / worker_scenarios_path).read_bytes()
    if hashlib.sha256(worker_scenarios_bytes).hexdigest() != "ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf":
        fail("worker-contract tuned scenario bytes differ from the preimplementation seal")
    worker_scenarios = json.loads(worker_scenarios_bytes.decode("utf-8"))
    if set(worker_scenarios) != {"schema_version", "suite", "used_for_tuning", "holdout_file", "base", "cases"}:
        fail("worker-contract scenarios have an invalid exact shape")
    if (
        worker_scenarios.get("schema_version") != 1
        or worker_scenarios.get("suite") != "worker-execution-contract"
        or worker_scenarios.get("used_for_tuning") is not True
        or worker_scenarios.get("holdout_file") != Path(worker_holdout_path).name
    ):
        fail("worker-contract scenarios have an unsupported identity or holdout link")
    scenario_cases = worker_scenarios.get("cases")
    if not isinstance(scenario_cases, list) or {case.get("class") for case in scenario_cases if isinstance(case, dict)} != {"median", "edge", "negative"}:
        fail("worker-contract scenarios must preserve median, edge, and negative classes")
    if any(not isinstance(case, dict) or case.get("used_for_tuning") is not True for case in scenario_cases):
        fail("worker-contract scenarios must remain tuned inputs")
    worker_holdout_bytes = (ROOT / worker_holdout_path).read_bytes()
    if hashlib.sha256(worker_holdout_bytes).hexdigest() != "a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27":
        fail("worker-contract holdout bytes differ from the preimplementation seal")
    receipt_scenarios_path = "tests/fixtures/orchestration/worker-completion-receipt-scenarios.json"
    receipt_holdout_path = "tests/fixtures/orchestration/worker-completion-receipt-holdout.json"
    receipt_replacement_holdout_path = "tests/fixtures/orchestration/worker-completion-receipt-holdout-v2.json"
    receipt_scenarios_bytes = (ROOT / receipt_scenarios_path).read_bytes()
    if hashlib.sha256(receipt_scenarios_bytes).hexdigest() != "264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a":
        fail("worker-completion-receipt tuned scenario bytes differ from the preimplementation seal")
    receipt_scenarios = json.loads(receipt_scenarios_bytes.decode("utf-8"))
    if set(receipt_scenarios) != {"schema_version", "suite", "used_for_tuning", "holdout_file", "base", "cases"}:
        fail("worker-completion-receipt scenarios have an invalid exact shape")
    if (
        receipt_scenarios.get("schema_version") != 1
        or receipt_scenarios.get("suite") != "worker-completion-receipt"
        or receipt_scenarios.get("used_for_tuning") is not True
        or receipt_scenarios.get("holdout_file") != Path(receipt_holdout_path).name
    ):
        fail("worker-completion-receipt scenarios have an unsupported identity or holdout link")
    receipt_cases = receipt_scenarios.get("cases")
    if not isinstance(receipt_cases, list) or {case.get("class") for case in receipt_cases if isinstance(case, dict)} != {"median", "edge", "negative"}:
        fail("worker-completion-receipt scenarios must preserve median, edge, and negative classes")
    if any(not isinstance(case, dict) or case.get("used_for_tuning") is not True for case in receipt_cases):
        fail("worker-completion-receipt scenarios must remain tuned inputs")
    receipt_coverage = {
        marker
        for case in receipt_cases
        for marker in (case.get("covers", []) if isinstance(case, dict) else [])
    }
    expected_receipt_coverage = {
        "successful_attempt", "failed_attempt", "initial_attempt", "correction_attempt",
        "failure_before_candidate", "partial_command_execution", "stale_receipt",
        "replayed_receipt", "plan_mismatch", "contract_mismatch", "patch_mismatch",
        "changed_path_mismatch", "false_success_claim", "missing_out_of_scope_declaration",
        "unknown_field", "duplicate_field", "oversized_receipt", "oversized_value",
        "path_traversal", "symlink_escape", "secret_inclusion", "raw_output_inclusion",
    }
    if receipt_coverage != expected_receipt_coverage:
        fail("worker-completion-receipt scenarios do not cover the accepted boundary")
    receipt_holdout_bytes = (ROOT / receipt_holdout_path).read_bytes()
    if hashlib.sha256(receipt_holdout_bytes).hexdigest() != "4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76":
        fail("worker-completion-receipt holdout bytes differ from the preimplementation seal")
    receipt_replacement_holdout_bytes = (ROOT / receipt_replacement_holdout_path).read_bytes()
    if hashlib.sha256(receipt_replacement_holdout_bytes).hexdigest() != "ddbbedb5c65cfe16ae48763b403c1beb16c241b7a77ab9379a88f98c8dd0f8de":
        fail("worker-completion-receipt replacement holdout bytes differ from the independent seal")
    try:
        receipt_exposed_holdout = json.loads(receipt_holdout_bytes.decode("utf-8"))
        receipt_replacement_holdout = json.loads(receipt_replacement_holdout_bytes.decode("utf-8"))
        receipt_evidence = json.loads(
            (ROOT / "tests/fixtures/orchestration/worker-completion-receipt-evidence.json").read_text(
                encoding="utf-8"
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"worker-completion-receipt integration evidence is invalid: {exc}")
    if set(receipt_evidence) != {
        "schema_version", "suite", "implementation_commit", "tuned_fixture",
        "exposed_holdout_fixture", "replacement_holdout_fixture", "runner_sha256",
        "template_runner_sha256", "observations", "source_acceptance",
    }:
        fail("worker-completion-receipt integration evidence has an invalid exact shape")
    if (
        receipt_evidence.get("schema_version") != 1
        or receipt_evidence.get("suite") != "worker-completion-receipt-integration"
        or receipt_evidence.get("tuned_fixture") != {
            "path": receipt_scenarios_path,
            "sha256": hashlib.sha256(receipt_scenarios_bytes).hexdigest(),
        }
        or receipt_evidence.get("exposed_holdout_fixture") != {
            "path": receipt_holdout_path,
            "sha256": hashlib.sha256(receipt_holdout_bytes).hexdigest(),
            "evidence_status": "known_regression_after_initial_failure",
        }
        or receipt_evidence.get("replacement_holdout_fixture") != {
            "path": receipt_replacement_holdout_path,
            "sha256": hashlib.sha256(receipt_replacement_holdout_bytes).hexdigest(),
            "evidence_status": "untuned_holdout",
        }
    ):
        fail("worker-completion-receipt evidence fixture bindings differ")
    receipt_implementation_commit = receipt_evidence.get("implementation_commit")
    if not isinstance(receipt_implementation_commit, str) or re.fullmatch(r"[0-9a-f]{40}", receipt_implementation_commit) is None:
        fail("worker-completion-receipt evidence implementation commit is invalid")
    receipt_committed_digests = []
    for relative in (
        "scripts/run-sandboxed-plan-worker.py",
        "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
    ):
        result = subprocess.run(
            ["git", "show", f"{receipt_implementation_commit}:{relative}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            fail("worker-completion-receipt evidence implementation commit is unavailable")
        receipt_committed_digests.append(hashlib.sha256(result.stdout).hexdigest())
    if (
        receipt_evidence.get("runner_sha256") != receipt_committed_digests[0]
        or receipt_evidence.get("template_runner_sha256") != receipt_committed_digests[1]
        or receipt_committed_digests[0] != receipt_committed_digests[1]
    ):
        fail("worker-completion-receipt evidence runner bindings differ")
    expected_receipt_observations = [
        {
            "id": case["id"],
            "class": case["class"],
            "used_for_tuning": case["used_for_tuning"],
            **case["expected"],
        }
        for fixture in (
            receipt_scenarios,
            receipt_exposed_holdout,
            receipt_replacement_holdout,
        )
        for case in fixture["cases"]
    ]
    if receipt_evidence.get("observations") != expected_receipt_observations:
        fail("worker-completion-receipt evidence observations differ")
    receipt_source_contract = json.loads(
        (ROOT / "docs/plan/replanned/contracts/114-validate-structured-worker-completion.json").read_text(
            encoding="utf-8"
        )
    )
    expected_receipt_acceptance = [
        {"digest": item["digest"].removeprefix("sha256:"), "result": "passed"}
        for item in receipt_source_contract["source"]["acceptance"]
    ]
    if receipt_evidence.get("source_acceptance") != expected_receipt_acceptance:
        fail("worker-completion-receipt evidence acceptance bindings differ")
    evidence = json.loads(
        (ROOT / "tests/fixtures/orchestration/worker-contract-evidence.json").read_text(
            encoding="utf-8"
        )
    )
    if set(evidence) != {
        "schema_version", "suite", "implementation_commit", "tuned_fixture",
        "holdout_fixture", "runner_sha256", "template_runner_sha256",
        "observations", "source_acceptance",
    }:
        fail("worker-contract integration evidence has an invalid exact shape")
    if (
        evidence.get("schema_version") != 1
        or evidence.get("suite") != "worker-execution-contract-integration"
        or evidence.get("tuned_fixture") != {
            "path": worker_scenarios_path,
            "sha256": hashlib.sha256(worker_scenarios_bytes).hexdigest(),
        }
        or evidence.get("holdout_fixture") != {
            "path": worker_holdout_path,
            "sha256": hashlib.sha256(worker_holdout_bytes).hexdigest(),
        }
    ):
        fail("worker-contract integration evidence fixture bindings differ")
    current_runner_digest = hashlib.sha256(
        (ROOT / "scripts/run-sandboxed-plan-worker.py").read_bytes()
    ).hexdigest()
    current_template_runner_digest = hashlib.sha256(
        (ROOT / "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py").read_bytes()
    ).hexdigest()
    implementation_commit = evidence.get("implementation_commit")
    if not isinstance(implementation_commit, str) or re.fullmatch(r"[0-9a-f]{40}", implementation_commit) is None:
        fail("worker-contract integration evidence implementation commit is invalid")
    committed_digests = []
    for relative in (
        "scripts/run-sandboxed-plan-worker.py",
        "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
    ):
        result = subprocess.run(
            ["git", "show", f"{implementation_commit}:{relative}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            fail("worker-contract integration evidence implementation commit is unavailable")
        committed_digests.append(hashlib.sha256(result.stdout).hexdigest())
    if (
        evidence.get("runner_sha256") != committed_digests[0]
        or evidence.get("template_runner_sha256") != committed_digests[1]
        or committed_digests[0] != committed_digests[1]
        or current_runner_digest != current_template_runner_digest
    ):
        fail("worker-contract integration evidence runner bindings differ")
    expected_ids = [case["id"] for case in scenario_cases] + [
        "holdout-missing-parent-new-package-manifest"
    ]
    observations = evidence.get("observations")
    if not isinstance(observations, list) or [item.get("id") for item in observations] != expected_ids:
        fail("worker-contract integration evidence observations differ")
    replan_contract = json.loads(
        (ROOT / "docs/plan/replanned/contracts/113-generate-plan-bound-worker-contract.json").read_text(
            encoding="utf-8"
        )
    )
    expected_acceptance = [
        {"digest": item["digest"].removeprefix("sha256:"), "result": "passed"}
        for item in replan_contract["source"]["acceptance"]
    ]
    if evidence.get("source_acceptance") != expected_acceptance:
        fail("worker-contract integration evidence acceptance bindings differ")


def template_source_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "template"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line and (ROOT / line).is_file()}


def require_template_manifest_complete() -> None:
    tracked = template_source_files()
    listed = {path for path in SOURCE_REQUIRED if path.startswith("template/")}
    missing = sorted(tracked - listed)
    stale = sorted(listed - tracked)
    if missing or stale:
        fail(f"template source manifest mismatch: missing={missing}, stale={stale}")


def require_referent_first_alignment() -> None:
    pairs = (
        ("docs/agent/SPEC_REFERENT_FIRST.md", "template/.project-agent-workflow/docs/agent/SPEC_REFERENT_FIRST.md"),
        (".codex/skills/define-referents-first/SKILL.md", "template/.project-agent-workflow/skills/define-referents-first/SKILL.md"),
        (
            ".codex/skills/define-referents-first/agents/openai.yaml",
            "template/.project-agent-workflow/skills/define-referents-first/agents/openai.yaml",
        ),
        (
            ".codex/skills/define-referents-first/references/workflow.md",
            "template/.project-agent-workflow/skills/define-referents-first/references/workflow.md",
        ),
        ("scripts/referent-contract.py", "template/.project-agent-workflow/scripts/referent-contract.py"),
        (".codex/hooks/semantic_guard_advisory.py", "template/.codex/hooks/semantic_guard_advisory.py"),
        (
            ".project-agent-workflow/hooks/semantic_guard_advisory.py",
            "template/.project-agent-workflow/hooks/semantic_guard_advisory.py",
        ),
    )
    for root_path, template_path in pairs:
        template_text = read(template_path)
        if "/.project-agent-workflow/" in template_path and not root_path.startswith(".project-agent-workflow/"):
            template_text = normalized_template_core(template_path)
        if read(root_path) != template_text:
            fail(f"referent-first root/template files differ: {root_path} != {template_path}")


def require_user_communication_alignment() -> None:
    pairs = (
        ("docs/agent/SPEC_USER_COMMUNICATION.md", "template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md"),
        (".codex/skills/write-for-reader/SKILL.md", "template/.project-agent-workflow/skills/write-for-reader/SKILL.md"),
        (
            ".codex/skills/write-for-reader/agents/openai.yaml",
            "template/.project-agent-workflow/skills/write-for-reader/agents/openai.yaml",
        ),
        (".codex/hooks/stop_review_gate.py", "template/.codex/hooks/stop_review_gate.py"),
        (
            ".project-agent-workflow/hooks/stop_review_gate.py",
            "template/.project-agent-workflow/hooks/stop_review_gate.py",
        ),
    )
    for root_path, template_path in pairs:
        template_text = read(template_path)
        if "/.project-agent-workflow/" in template_path and not root_path.startswith(".project-agent-workflow/"):
            template_text = normalized_template_core(template_path)
        if read(root_path) != template_text:
            fail(f"user-communication root/template files differ: {root_path} != {template_path}")


def require_git_retirement_alignment() -> None:
    root_cli = ROOT / "scripts/retire-merged-worktrees.py"
    template_cli = ROOT / "template/.project-agent-workflow/scripts/retire-merged-worktrees.py"
    if root_cli.read_bytes() != template_cli.read_bytes():
        fail("root and generated Git-retirement CLIs differ")
    if (root_cli.stat().st_mode & 0o777) != (template_cli.stat().st_mode & 0o777):
        fail("root and generated Git-retirement CLI modes differ")

    root_spec = read("docs/agent/SPEC_GIT_RETIREMENT.md")
    template_spec = read("template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md")
    expected_template_spec = root_spec.replace(
        "`scripts/retire-merged-worktrees.py",
        "`.project-agent-workflow/scripts/retire-merged-worktrees.py",
    )
    if template_spec != expected_template_spec:
        fail("root and generated Git-retirement specifications differ beyond command paths")

    root_config = read("docs/agent/git-retirement.yaml")
    if root_config != (
        "version: 1\n"
        "enabled: true\n"
        "merge_target_refs:\n"
        "  - refs/heads/dev\n"
        "protected_local_branch_refs:\n"
        "  - refs/heads/main\n"
        "  - refs/heads/dev\n"
    ):
        fail("root Git-retirement configuration is not the explicit enabled profile")
    generated_config = read("template/docs/agent/git-retirement.yaml.jinja")
    if generated_config != (
        "version: 1\n"
        "enabled: false\n"
        "merge_target_refs: []\n"
        "protected_local_branch_refs: []\n"
    ):
        fail("generated Git-retirement configuration is not safe-disabled")

    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .project-agent-workflow/**" not in ownership:
        fail("Copier ownership does not cover the generated Git-retirement specification and CLI")
    if "seeded_project_owned:\n" not in ownership or "  - docs/agent/**" not in ownership:
        fail("Copier ownership does not preserve generated-project Git-retirement configuration")


def require_sandboxed_plan_worker_alignment() -> None:
    root_runner = read("scripts/run-sandboxed-plan-worker.py")
    template_runner = read("template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py")
    if root_runner != template_runner:
        fail("sandboxed plan worker root/template scripts differ")
    root_mode = os.stat(ROOT / "scripts/run-sandboxed-plan-worker.py").st_mode & 0o777
    template_mode = os.stat(ROOT / "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py").st_mode & 0o777
    if root_mode != template_mode:
        fail("sandboxed plan worker root/template script modes differ")
    if root_mode & 0o111 == 0:
        fail("sandboxed plan worker scripts must be executable")
    root_restructure = ROOT / "scripts/restructure-plan.py"
    template_restructure = ROOT / "template/.project-agent-workflow/scripts/restructure-plan.py"
    if root_restructure.read_bytes() != template_restructure.read_bytes():
        fail("plan restructuring root/template scripts differ")
    if (root_restructure.stat().st_mode & 0o777) != (template_restructure.stat().st_mode & 0o777):
        fail("plan restructuring root/template script modes differ")
    root_execution_state = ROOT / "scripts/plan-execution-state.py"
    template_execution_state = ROOT / "template/.project-agent-workflow/scripts/plan-execution-state.py"
    if root_execution_state.read_bytes() != template_execution_state.read_bytes():
        fail("plan execution state root/template scripts differ")
    if (root_execution_state.stat().st_mode & 0o777) != (template_execution_state.stat().st_mode & 0o777):
        fail("plan execution state root/template script modes differ")
    execution_state_text = root_execution_state.read_text(encoding="utf-8")
    for marker in (
        '"diagnosis_required"', "MAX_DIAGNOSIS_ATTEMPTS",
        '"authoritative_failure"', '"failure_diagnosis"',
        "def load_authoritative_failure", "def load_diagnosis_evidence",
        '"diagnosis_read"', '"repair_plan"',
    ):
        if marker not in execution_state_text:
            fail(f"plan execution state missing confirmed-diagnosis marker: {marker}")
    for marker in (
        'DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"',
        'DEFAULT_CODEX_REASONING = "medium"',
        'DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"',
        'DEFAULT_FALLBACK_CODEX_REASONING = "max"',
        "def classify_codex_unavailability",
        'label="fallback"',
        '"attempts"',
        '"selected_attempt"',
        '"fallback_reason"',
        '"--fallback-codex-model"',
        '"--fallback-codex-reasoning-effort"',
        '"--no-model-fallback"',
        "def select_plan_writable_profile",
        "implementation_risk",
        "implementation_ambiguity",
        "WRITABLE_SOL_MODEL",
        "AVAILABILITY_STATE_MAX_BYTES",
        "def open_availability_state",
        '"--availability-state"',
        '"--orchestration-run-id"',
        '"telemetry"',
        '"skipped_known_unavailable_starts"',
        "def correct_worker",
        "def verify_candidate_manifest",
        '"correct"',
        "MAX_CORRECTION_ROUNDS",
        '"correction_lineage"',
        "def validate_candidate",
        "def open_lifecycle_state",
        '"--lifecycle-state"',
        "VALIDATION_AUTHORITY_SCOPE",
        '"authoritative_passed"',
        '"apply requires exactly one successful authoritative validation"',
        "load_plan_validation_commands",
        '"focused_validation_count"',
        '"authoritative_validation_count"',
        "def validation_failure_identity",
        '"failure": failure',
        "network_enabled=False",
        '"prepare-dependencies"',
        '"--dependency-snapshot"',
        "def verify_dependency_snapshot",
        "def source_tree_metadata_fingerprint",
        "read_only_shadows",
        "WORKER_CONTRACT_SCHEMA_VERSION",
        "def derive_worker_contract",
        "def verify_worker_contract",
        "WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION",
        "def validate_worker_completion_receipt",
        "def write_attempt_completion_receipt",
        "def write_attempt_process_result",
        "worker_completion_receipt_path",
        "worker_process_result_path",
        "def derive_repository_identity",
        "worker_attempt_label",
        "require_safe_delegated_write_scope",
        "NEW_FILE_ROOT",
        "SANDBOXED_PLAN_WORKER_CONTRACT first",
    ):
        if marker not in template_runner:
            fail(f"sandboxed plan worker missing model fallback marker: {marker}")
    pairs = (
        (
            ".codex/skills/sequential-plan-orchestrator/SKILL.md",
            "template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md",
        ),
    )
    for root_path, template_path in pairs:
        template_text = normalized_template_core(template_path)
        if read(root_path) != template_text:
            fail(f"sandboxed plan worker orchestration text differs: {root_path} != {template_path}")
    for relative in (
        "template/.project-agent-workflow/AGENTS.md.jinja",
        "template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md",
        "template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md",
    ):
        text = read(relative).lower()
        for marker in (
            "gpt-5.3-codex-spark", "gpt-5.6-luna", "max", "usage limit", "rate limit",
            "primary_invariant", "exact file", "read-only", "contract",
        ):
            if marker not in text:
                fail(f"{relative} missing sandboxed model fallback policy marker: {marker}")

    planlib = read("template/.project-agent-workflow/scripts/planlib.py")
    for marker in (
        '"validation_witness_schema"',
        '"validation_witness_map"',
        "def validate_validation_witness_map",
        "def validate_legacy_witness_provenance",
        "def validate_resolved_context_files",
        "resolved-context-files",
        "authoritative_only_reason",
        "skips an available focused witness",
    ):
        if marker not in planlib:
            fail(f"generated plan parser missing validation-witness marker: {marker}")
    for relative in (
        "scripts/plan_validation_commands.py",
        "template/.project-agent-workflow/scripts/plan_validation_commands.py",
    ):
        text = read(relative)
        for marker in ("def load_planlib", "validate_validation_witness_map"):
            if marker not in text:
                fail(f"{relative} missing validation-witness check marker: {marker}")


def run_hook_payload(script_path: str, run_id: str, payload: dict[str, Any], cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["CODEX_AGENT_LOG_RUN_ID"] = run_id
    result = subprocess.run(
        [sys.executable, str(ROOT / script_path), "--event", str(payload.get("hook_event_name", "UserPromptSubmit"))],
        input=json.dumps(payload),
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if result.returncode != 0:
        fail(f"hook logger execution failed for {script_path}: {result.stderr}")
    event_path = cwd / ".agent-logs" / run_id / "raw" / "events.jsonl"
    if not event_path.is_file():
        fail(f"hook log file missing for {script_path}: {event_path}")
    lines = [line for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        fail(f"hook log file empty for {script_path}: {event_path}")
    try:
        return json.loads(lines[-1])
    except Exception as exc:
        fail(f"invalid hook log JSON for {script_path}: {event_path}: {exc}")


def require_hook_logging_parity() -> None:
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "hook-parity-session",
        "tool": "Bash",
        "tool_name": "bash",
        "prompt": "secret=should-not-log",
        "tool_input": "rm -rf /",
        "response": "tool result should not log",
        "output": "tool output should not log",
        "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
    }
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        root_record = run_hook_payload(".project-agent-workflow/hooks/agent_log_event.py", "root-parity", payload, repo)
        template_record = run_hook_payload("template/.project-agent-workflow/hooks/agent_log_event.py", "template-parity", payload, repo)
    if root_record.get("event") != template_record.get("event"):
        fail("root/template hook event field diverged")
    if root_record.get("payload", {}).get("session_id") != payload["session_id"]:
        fail("root hook payload stopped logging session_id")
    if template_record.get("payload", {}).get("session_id") != payload["session_id"]:
        fail("template hook payload stopped logging session_id")
    for field in ("prompt", "tool_input", "response", "output", "api_key"):
        if field in root_record.get("payload", {}):
            fail(f"root hook payload leaked disallowed field: {field}")
        if field in template_record.get("payload", {}):
            fail(f"template hook payload leaked disallowed field: {field}")

    if root_record.get("payload", {}) != template_record.get("payload", {}):
        fail("root/template hook payload structure diverged")


def require_root_pre_tool_hardening() -> None:
    hooks = json.loads(read(".codex/hooks.json"))
    entries = hooks.get("hooks", {}).get("PreToolUse", [{}])[0].get("hooks", [])
    commands = [entry.get("command", "") for entry in entries]
    if len(commands) != 2:
        fail("root PreToolUse must contain the event logger and hardening gate")
    if "agent_log_event.py" not in commands[0]:
        fail("root PreToolUse must run event logging before the hardening gate")
    if ".project-agent-workflow/hooks/pre_tool_hardening_gate.py" not in commands[1]:
        fail("root PreToolUse must run the hardening gate")


def parse_fixture(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            fail(f"fixture line is not key/value: {path}: {raw_line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in data:
            fail(f"fixture contains duplicate answer: {path}: {key}")
        data[key] = value.strip().strip("\"'")
    return data


def parse_pairwise_fixture(path: Path) -> list[dict[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    if not lines:
        fail(f"pairwise fixture is empty: {path}")
    header = lines[0].split("\t")
    expected_header = ["case", *EXPECTED_CHOICE_VALUES]
    if header != expected_header:
        fail(f"pairwise fixture header mismatch: expected={expected_header}, actual={header}")
    rows: list[dict[str, str]] = []
    seen_cases: set[str] = set()
    for raw_line in lines[1:]:
        values = raw_line.split("\t")
        if len(values) != len(header):
            fail(f"pairwise fixture column mismatch: {path}: {raw_line}")
        row = dict(zip(header, values, strict=True))
        case = row.pop("case")
        if not case or case in seen_cases:
            fail(f"pairwise fixture case must be non-empty and unique: {case!r}")
        seen_cases.add(case)
        rows.append(row)
    return rows


def require_valid_answers(answers: dict[str, str], source: str, *, complete: bool) -> None:
    if complete:
        missing = QUESTIONS - set(answers)
        unknown = set(answers) - QUESTIONS
        if missing or unknown:
            fail(f"{source} answer keys mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")
    for question, expected_values in EXPECTED_CHOICE_VALUES.items():
        value = answers.get(question)
        if value is not None and value not in expected_values:
            fail(f"{source} has invalid answer: {question}={value!r}")


def require_pairwise_coverage(answer_sets: list[dict[str, str]]) -> None:
    questions = list(EXPECTED_CHOICE_VALUES)
    missing: list[str] = []
    for first, second in combinations(questions, 2):
        observed = {(answers[first], answers[second]) for answers in answer_sets}
        expected = set(product(EXPECTED_CHOICE_VALUES[first], EXPECTED_CHOICE_VALUES[second]))
        for first_value, second_value in sorted(expected - observed):
            missing.append(f"{first}={first_value}, {second}={second_value}")
    if missing:
        fail(f"Copier fixture matrix is not pairwise complete: {missing}")


def expected_generated_paths(answers: dict[str, str]) -> list[str]:
    require_valid_answers(answers, "generated inventory input", complete=True)
    generated: set[str] = set()
    for source in template_source_files():
        relative = source.removeprefix("template/")
        if relative == "[[ _copier_conf.answers_file ]].jinja":
            output = ".copier-answers.yml"
        elif relative.endswith(".jinja"):
            output = relative.removesuffix(".jinja")
        else:
            output = relative
        condition = CONDITIONAL_GENERATED.get(output)
        if condition is not None:
            question, included_values = condition
            if answers[question] not in included_values:
                continue
        generated.add(output)
    return sorted(generated)


def copier_question_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line and not line.startswith(" ") and ":" in line:
            current = line.split(":", 1)[0]
            blocks[current] = []
            continue
        if current:
            blocks[current].append(line)
    return blocks


def require_japanese_prompts(copier_yml: str) -> None:
    blocks = copier_question_blocks(copier_yml)
    for question in QUESTIONS:
        body = blocks.get(question)
        if body is None:
            fail(f"copier.yml missing question: {question}")
        help_lines = [line for line in body if line.startswith("  help:")]
        if not help_lines:
            fail(f"copier.yml question missing help text: {question}")
        if not JAPANESE_RE.search(help_lines[0]):
            fail(f"copier.yml question help must be Japanese: {question}")

    for question, expected_values in EXPECTED_CHOICE_VALUES.items():
        body = blocks[question]
        values: set[str] = set()
        in_choices = False
        for line in body:
            if line == "  choices:":
                in_choices = True
                continue
            if in_choices and line.startswith("    ") and ":" in line:
                label, value = line.strip().split(":", 1)
                if not JAPANESE_RE.search(label):
                    fail(f"copier.yml choice label must be Japanese: {question}: {label}")
                values.add(value.strip().strip("\"'"))
                continue
            if in_choices and line and not line.startswith("    "):
                break
        if values != expected_values:
            fail(f"copier.yml choice values changed for {question}: {sorted(values)}")

    for question, expected_default in EXPECTED_DEFAULT_VALUES.items():
        if f'  default: "{expected_default}"' not in blocks[question]:
            fail(f"copier.yml default changed for {question}: expected {expected_default}")


def require_update_boundaries(copier_yml: str) -> None:
    root_owned = (
        "/AGENTS.md",
        "/README.md",
        "/.gitignore",
        "/.codex/config.toml",
        "/.codex/hooks.json",
        "/.codex/agents/*.toml",
        "/docs/agent/**",
        "/docs/plan/**",
    )
    for pattern in root_owned:
        if f'  - "{pattern}"' not in copier_yml:
            fail(f"copier.yml must root-anchor project-owned path: {pattern}")

    migration_markers = (
        "_migrations:",
        "version: v1.0.0",
        "scripts/migrate-to-namespaced-layout.py",
        "version: v1.1.1",
        "scripts/update_hook_wiring.py",
        "version: v1.2.2",
        "scripts/validate-copier-update.py",
        "version: v1.4.2",
        "scripts/migrate-sequential-plan-worker.py",
        'when: "[[ _stage == \'before\' ]]"',
        'when: "[[ _stage == \'after\' ]]"',
    )
    for marker in migration_markers:
        if marker not in copier_yml:
            fail(f"copier.yml missing namespaced-layout migration marker: {marker}")


def require_context_compression_boundary() -> None:
    wrapper = read("template/.project-agent-workflow/scripts/context-compress.sh")
    required = (
        ".project-agent-workflow/docs/agent|",
        ".project-agent-workflow/docs/agent/*|",
    )
    for marker in required:
        if marker not in wrapper:
            fail(f"generated context compression is missing normative path refusal: {marker}")


def require_agent_profile_task() -> None:
    copier_yml = read("copier.yml")
    required = (
        "_tasks:",
        '"[[ _copier_python ]]"',
        '"[[ _copier_conf.src_path ]]/scripts/update_agent_model_profiles.py"',
    )
    for marker in required:
        if marker not in copier_yml:
            fail(f"copier.yml missing fixed agent-profile task marker: {marker}")


def require_copier_documentation_contract() -> None:
    command_docs = (
        "README.md",
        "template/README.md.jinja",
        "SKILL.md",
    )
    skill_copy_commands: list[str] = []
    for path in command_docs:
        for line in read(path).splitlines():
            command = line.strip()
            if command.startswith(("copier copy ", "copier update ")) and "--trust" not in command:
                fail(f"{path} documents an untrusted Copier command: {command}")
            if path == "SKILL.md" and command.startswith("copier copy "):
                skill_copy_commands.append(command)
                tokens = command.split()
                if "--defaults" in tokens and any(token in ("-f", "--force") for token in tokens):
                    fail(f"SKILL.md non-interactive Copier command uses overwrite forcing: {command}")

    skill_trusted_noninteractive = 0
    skill_trusted_default = 0
    for command in skill_copy_commands:
        tokens = command.split()
        if "--trust" not in tokens:
            fail(f"SKILL.md documented Copier command is untrusted: {command}")
        if "--defaults" in tokens:
            if "--trust" in tokens:
                skill_trusted_noninteractive += 1
        elif "--trust" in tokens:
            skill_trusted_default += 1

    if skill_trusted_default == 0:
        fail("SKILL.md must document a trusted Copier copy command without --defaults")
    if skill_trusted_noninteractive == 0:
        fail("SKILL.md must document a trusted Copier copy command with --defaults")

    required_markers = {
        "AGENTS.md": (
            "Treat non-destructive Copier evolution as a repository invariant",
            "unclassified tracked-file deletion",
        ),
        "CHANGELOG.md": (
            "## 未リリース",
            "## v1.1.2",
            "`model` と `model_reasoning_effort` だけを固定値へ正規化",
            "生成先が削除した `docs/plan/` の `.gitkeep` を通常の update で再生成しない",
        ),
        "template/.project-agent-workflow/AGENTS.md.jinja": (
            "project-owned product code, policy, configuration, plan history",
            "unclassified tracked-file deletion",
        ),
        "references/template-development.md": (
            "Require `--trust` for every documented copy and update command",
            "template-fixed `model` and `model_reasoning_effort` fields",
            "preserve instructions and every unrelated project-owned field",
        ),
        "template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md": (
            "## Non-Destructive Update Contract",
            "copier copy --trust",
            ".project-agent-workflow/scripts/update-from-copier.sh",
            "The `model` and `model_reasoning_effort` fields are the only exceptions.",
            "`--trust` authorizes the bundled task; it does not prove that the resulting diff is safe to commit.",
        ),
        "template/.project-agent-workflow/ownership.yaml": (
            "field_overrides:",
            "  - path: .codex/agents/*.toml",
            "    template_fixed:\n      - model\n      - model_reasoning_effort",
            "    project_owned_remainder: true",
        ),
    }
    for path, markers in required_markers.items():
        text = read(path)
        for marker in markers:
            if marker not in text:
                fail(f"{path} missing Copier documentation contract marker: {marker}")

    if "requires `--trust` only" in read("references/template-development.md"):
        fail("template development documentation still limits --trust to migrations")

    source_validator = ROOT / "scripts/validate-copier-update.py"
    generated_validator = ROOT / "template/.project-agent-workflow/scripts/validate-copier-update.py"
    if source_validator.read_bytes() != generated_validator.read_bytes():
        fail("source and generated Copier update validators must be byte-identical")
    ownership_digest = hashlib.sha256(
        (ROOT / "template/.project-agent-workflow/ownership.yaml").read_bytes()
    ).hexdigest()
    if (
        f'CURRENT_OWNERSHIP_SHA256 = "{ownership_digest}"'
        not in source_validator.read_text(encoding="utf-8")
    ):
        fail("Copier update validator ownership digest differs from the current inventory")
    source_worker_migration = ROOT / "scripts/migrate-sequential-plan-worker.py"
    generated_worker_migration = (
        ROOT / "template/.project-agent-workflow/scripts/migrate-sequential-plan-worker.py"
    )
    if source_worker_migration.read_bytes() != generated_worker_migration.read_bytes():
        fail("source and generated sequential worker migrations must be byte-identical")
    if (source_worker_migration.stat().st_mode & 0o777) != (
        generated_worker_migration.stat().st_mode & 0o777
    ):
        fail("source and generated sequential worker migration modes differ")

    wrapper = read("template/.project-agent-workflow/scripts/update-from-copier.sh")
    for marker in (
        '"$script_dir/../.."',
        'exec "$script_dir/run-copier-update.sh" "$@"',
        "validate-copier-update.py --destination .",
        "--force|--force=*",
        "-*f*",
    ):
        if marker not in wrapper:
            fail(f"generated Copier update wrapper missing marker: {marker}")

    wrapper_bytes = (
        ROOT / "template/.project-agent-workflow/scripts/update-from-copier.sh"
    ).read_bytes()
    legacy_resume_suffix = (
        b"python3 .project-agent-workflow/scripts/validate-copier-update.py --destination .\n"
    )
    if wrapper_bytes[466:] != legacy_resume_suffix:
        fail("generated Copier update wrapper changed the exact v1.4.1 resume suffix")

    update_helper = read("template/.project-agent-workflow/scripts/run-copier-update.sh")
    for marker in (
        "main() {",
        "--force|--force=*",
        "-*f*",
        "--destination . --before-update",
        'copier update --trust "$@"',
        "validate-copier-update.py --destination .",
        'main "$@"; exit',
    ):
        if marker not in update_helper:
            fail(f"generated Copier update helper missing marker: {marker}")


def workflow_job(text: str, job_name: str) -> str:
    match = re.search(
        rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        fail(f"CI autofix workflow missing job: {job_name}")
    return match.group(0)


def require_markers(path: str, subject: str, text: str, markers: tuple[str, ...]) -> None:
    for marker in markers:
        if marker not in text:
            fail(f"{path} {subject} missing marker: {marker}")


def require_ci_autofix_boundaries(
    path: str,
    boundary_validation_command: str,
) -> None:
    text = read(path)
    required = (
        "ref: ${{ needs.prepare.outputs.head_sha }}",
        'git show "origin/${BASE_BRANCH}:.github/codex/prompts/ci-autofix.md" > "$RUNNER_TEMP/codex-ci-autofix-prompt.md"',
        'prompt-file: ${{ runner.temp }}/codex-ci-autofix-prompt.md',
        'output-file: ${{ runner.temp }}/codex-ci-autofix-output.md',
        'git diff --binary HEAD > "$RUNNER_TEMP/codex-ci-autofix.patch"',
        "git diff --check HEAD",
        boundary_validation_command,
        'path: ${{ runner.temp }}/codex-ci-autofix.patch',
        'path: ${{ runner.temp }}/codex-ci-autofix-output.md',
        'protected=$(git diff --name-only HEAD | grep -E \'^(\\.github/workflows/|\\.github/codex/|\\.env($|\\.)|.*production.*|.*deploy.*)\' || true)',
        'deleted_tests=$(git diff --diff-filter=D --name-only HEAD -- tests || true)',
        'git status --porcelain=v1 --untracked-files=all',
        'git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]',
        'echo "dependency setup changed tracked, staged, or non-ignored untracked paths" >&2',
        'let mode = "patch-only";',
    )
    require_markers(path, "workflow", text, required)

    prompt_guard = 'git diff --quiet "origin/${BASE_BRANCH}...HEAD" -- .github/codex/prompts/ci-autofix.md'
    require_markers(path, "workflow", text, (prompt_guard,))
    if text.index(prompt_guard) > text.index("- name: Run Codex"):
        fail(f"{path} must reject pull request prompt changes before Codex execution")

    if re.search(r"(?m)(^\s*max_attempts:\b|^\s*maxAttempts\b|max_attempts)", text):
        fail(f"{path} must not contain the obsolete commit-count max_attempts guard")
    for marker in ("direct-push", "validate-patch", "apply-patch", "patch-only-notice", "git push", "createComment", "git commit"):
        if marker in text:
            fail(f"{path} contains removed CI autofix write-path marker: {marker}")

    if re.search(r"(?m)^\s*permissions:\s+(?:write|write-all)\s*$", text):
        fail(f"{path} workflow permissions must not grant write-all or write")
    if re.search(r"(?m)^\s+[A-Za-z0-9_-]+:\s+write(?:-all)?\s*$", text):
        fail(f"{path} contains a job-level write permission")

    generate = workflow_job(text, "generate-fix")
    require_markers(
        path,
        "generate-fix job",
        generate,
        (
            "permissions:\n      actions: read\n      contents: read\n      pull-requests: read",
            prompt_guard,
        ),
    )
    if "contents: write" in generate:
        fail(f"{path} generate-fix job must not have branch write permission")


def require_ci_autofix_root_boundaries() -> None:
    require_ci_autofix_boundaries(
        ".github/workflows/codex-ci-autofix.yml",
        "python3 template/.project-agent-workflow/scripts/security-static-check.py --changed",
    )
    require_ci_autofix_boundaries(
        "template/.github/workflows/codex-ci-autofix.yml.jinja",
        "python3 .project-agent-workflow/scripts/security-static-check.py --changed",
    )


def require_generated_whitespace_range() -> None:
    path = "template/.github/workflows/project-agent-workflow.yml"
    text = read(path)
    required = (
        "BASE_SHA: ${{ github.event.pull_request.base.sha }}",
        "BEFORE_SHA: ${{ github.event.before }}",
        "EVENT_NAME: ${{ github.event_name }}",
        "HEAD_SHA: ${{ github.sha }}",
        "PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}",
        "REF_TYPE: ${{ github.ref_type }}",
        "if [ \"$EVENT_NAME\" = pull_request ]; then",
        'git diff --check "$BASE_SHA...$PR_HEAD_SHA"',
        '[ "$REF_TYPE" = tag ]',
        'git diff --check "$HEAD_SHA^..$HEAD_SHA"',
        '[ "$BEFORE_SHA" != 0000000000000000000000000000000000000000 ]',
        'git cat-file -e "$BEFORE_SHA^{commit}" 2>/dev/null',
        'git diff --check "$BEFORE_SHA..$HEAD_SHA"',
        "EMPTY_TREE=$(git hash-object -t tree /dev/null)",
        'git diff --check "$EMPTY_TREE" "$HEAD_SHA"',
    )
    require_markers(path, "whitespace range selection", text, required)
    if "run: git diff --check" in text:
        fail(f"{path} must not check only the clean worktree")


def require_namespaced_reference_paths() -> None:
    agents = read("AGENTS.md")
    japanese = read("docs/agent/SPEC_JAPANESE_TECH_WRITING.md")

    required_target = "template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    forbidden_target = "template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    for path, text in (("AGENTS.md", agents), ("docs/agent/SPEC_JAPANESE_TECH_WRITING.md", japanese)):
        if required_target not in text:
            fail(f"{path} missing generated Japanese-writing sync target: {required_target}")
        if forbidden_target in text:
            fail(f"{path} still references removed generated-writing sync target: {forbidden_target}")

    skill = read("SKILL.md")
    if ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md" not in skill:
        fail("SKILL.md missing reusable external-services spec path: .project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md")
    if "`SPEC_EXTERNAL_SERVICES.md`" in skill:
        fail("SKILL.md still references stale external-services spec path: `SPEC_EXTERNAL_SERVICES.md`")

    planning = read("references/planning.md")
    planning_required = (
        "`.project-agent-workflow/scripts/create-plan.sh active <slug>`",
        "`.project-agent-workflow/scripts/create-plan.sh backlog <slug>`",
        "`.project-agent-workflow/scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`",
        "`.project-agent-workflow/scripts/complete-plan.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/check-agent-completion.sh`",
        "`.project-agent-workflow/scripts/select-task-context.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/clean-handoffs.sh --dry-run`",
        "`.project-agent-workflow/scripts/lint-plan-docs.py`",
        "`.project-agent-workflow/scripts/lint-plan-docs.sh`",
        "`.project-agent-workflow/scripts/format-plan-docs.py`",
        "`.project-agent-workflow/scripts/format-plan-docs.sh --check`",
        "`.project-agent-workflow/scripts/search-plan-archive.py --text <term>`",
    )
    for marker in planning_required:
        if marker not in planning:
            fail(f"references/planning.md missing managed path marker: {marker}")

    planning_forbidden = (
        "`scripts/create-plan.sh active <slug>`",
        "`scripts/create-plan.sh backlog <slug>`",
        "`scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`",
        "`scripts/complete-plan.sh docs/plan/active/NNN-slug.md`",
        "`scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`",
        "`scripts/check-agent-completion.sh`",
        "`scripts/select-task-context.sh docs/plan/active/NNN-slug.md`",
        "`scripts/clean-handoffs.sh --dry-run`",
        "`scripts/format-plan-docs.py --check`",
    )
    for marker in planning_forbidden:
        if marker in planning:
            fail(f"references/planning.md still contains stale managed path marker: {marker}")

    require_current_plan_manifest_reference(planning)

    validation = read("references/validation.md")
    validation_required = (
        "`.project-agent-workflow/scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.",
        "`.project-agent-workflow/scripts/security-static-check.py`: scans common high-signal static risks.",
        "`.project-agent-workflow/scripts/skillspector-scan.sh`: optional NVIDIA SkillSpector wrapper for AI agent skill scans.",
        "`.project-agent-workflow/scripts/structure-map.py --check`: verifies basic agent workflow structure.",
        "`.project-agent-workflow/scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.",
    )
    for marker in validation_required:
        if marker not in validation:
            fail(f"references/validation.md missing managed path marker: {marker}")

    validation_forbidden = (
        "`scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.",
        "`scripts/security-static-check.py`: scans common high-signal static risks.",
        "`scripts/skillspector-scan.sh`: optional NVIDIA SkillSpector wrapper for AI agent skill scans.",
        "`scripts/structure-map.py --check`: verifies basic agent workflow structure.",
        "`scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.",
    )
    for marker in validation_forbidden:
        if marker in validation:
            fail(f"references/validation.md still contains stale managed path marker: {marker}")


def require_current_plan_manifest_reference(planning: str) -> None:
    required_fields = (
        "status",
        "task_types",
        "review_class",
        "human_design_required",
        "human_approval_status",
        "write_scope",
        "context_files",
        "required_specs",
        "validation",
        "acceptance",
        "checked_summary_ja",
    )
    optional_fields = (
        "target_json",
        "acceptance_focus",
        "completion_deferred_reason",
        "primary_invariant",
        "integration_gates",
        "replan_source",
        "replan_contract",
        "successor_plans",
        "inherited_acceptance_digests",
        "replan_reason_codes",
    )
    legacy_fields = ("task_type", "target_files", "expected_output")
    try:
        manifest_reference, _ = planning.split("## Lifecycle Scripts", 1)
        required_section, optional_section = manifest_reference.split(
            "Optional fields for new active and backlog plans:", 1
        )
    except ValueError:
        fail("references/planning.md missing current active-plan manifest sections")
    for field in required_fields:
        if f"- `{field}`" not in required_section:
            fail(f"references/planning.md missing required active-plan field: {field}")
    for field in optional_fields:
        if f"- `{field}`" not in optional_section:
            fail(f"references/planning.md missing optional active-plan field: {field}")
    for field in legacy_fields:
        if f"- `{field}`" in manifest_reference:
            fail(f"references/planning.md recommends removed active-plan field: {field}")
        if f"`{field}`" not in optional_section:
            fail(f"references/planning.md missing legacy archive note for: {field}")


def require_mcp_execution_context_contract() -> None:
    bridge = read("template/.agents/skills/mcp-ops/SKILL.md")
    if bridge != """---
name: mcp-ops
description: Apply the project external-service gate before MCP operations.
---

# MCP Operations Bridge

Read `.project-agent-workflow/skills/mcp-ops/SKILL.md` completely and follow it.
""":
        fail("mcp-ops discovery bridge trigger or routing changed")

    skill = read("template/.project-agent-workflow/skills/mcp-ops/SKILL.md")
    reference = read(
        "template/.project-agent-workflow/skills/mcp-ops/references/provider-call-execution-context.md"
    )
    specification = read("template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja")
    metadata = read("template/.project-agent-workflow/skills/mcp-ops/agents/openai.yaml")
    require_markers(
        "managed mcp-ops Skill",
        "same-context authentication routing",
        skill,
        (
            "references/provider-call-execution-context.md",
            "Do not claim `runtime_configured`",
            "exact provider, account, command boundary, and credential source",
            ".project-agent-workflow/scripts/check-external-service-policy.py check",
        ),
    )
    require_markers(
        "mcp-ops execution-context reference",
        "authentication, failure, and retry boundaries",
        reference,
        (
            "provider, command execution boundary, and credential source",
            "This decision excludes host execution approval",
            "cannot pass the normal `authorize` command",
            "exact selected credential source",
            "saved command-prefix approval",
            "credential-source unavailability",
            "provider-permission denial",
            "provider unavailability",
            "read the exact remote state",
            "Never read, print, persist, fixture, log, or send token values",
        ),
    )
    require_markers(
        "generated external-service specification",
        "provider-call execution context",
        specification,
        (
            "provider-call execution context",
            "would be circular",
            "this approval grants no provider operation, target, payload, or effect",
            "must not expose the exact credential-source binding",
            "saved command-prefix approval does not authorize an external write",
            "process-local credential-source unavailability",
            "read exact remote state before retrying",
            "preserve an existing project-owned version 2 policy byte-for-byte",
        ),
    )
    require_markers(
        "mcp-ops UI metadata",
        "same-context preflight",
        metadata,
        (
            "Bind provider authentication to each exact call",
            "without presuming authentication",
        ),
    )

    fixture = json.loads(read("tests/fixtures/mcp-ops/scenarios.json"))
    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not requirements or any(item.get("critical") is not True for item in requirements):
        fail("mcp-ops scenarios must keep every declared requirement critical")
    evaluator_spec = importlib.util.spec_from_file_location(
        "mcp_root_policy_evaluator", ROOT / "scripts/check-root-agent-policy.py"
    )
    if evaluator_spec is None or evaluator_spec.loader is None:
        fail("could not load the independent mcp scenario evaluator")
    evaluator = importlib.util.module_from_spec(evaluator_spec)
    evaluator_spec.loader.exec_module(evaluator)
    try:
        observed_ids = [item["id"] for item in scenarios]
        if (
            len(observed_ids) != len(set(observed_ids))
            or set(observed_ids) != evaluator.MCP_SCENARIO_IDS
        ):
            raise ValueError("mcp scenario identifiers differ from the accepted set")
        for item in scenarios:
            if evaluator.evaluate_mcp_scenario(item) != item["expected"]:
                raise ValueError(f"incorrect condition-to-action mapping: {item['id']}")
        evaluator.validate_mcp_blank_binding_mutations(scenarios)
    except (KeyError, TypeError, ValueError) as exc:
        fail(f"mcp-ops scenario evaluation failed: {exc}")
    if {item.get("class") for item in scenarios} != {"median", "edge", "negative", "holdout"}:
        fail("mcp-ops scenarios must cover median, edge, negative, and holdout classes")
    holdouts = [item for item in scenarios if item.get("class") == "holdout"]
    if len(holdouts) != 1 or holdouts[0].get("used_for_tuning") is not False:
        fail("mcp-ops holdout scenario must remain outside tuning")
    if any(item.get("used_for_tuning") is not True for item in scenarios if item.get("class") != "holdout"):
        fail("mcp-ops non-holdout scenarios must remain tuned inputs")


def require_browser_automation_contract() -> None:
    index = read("template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja")
    required_route = (
        "  browser_automation:",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
        ".project-agent-workflow/docs/agent/SPEC_SECURITY.md",
        ".agents/skills/browser-ops/SKILL.md",
        ".project-agent-workflow/skills/browser-ops/references/browser-run-policy.md",
    )
    require_markers("template spec index", "browser route", index, required_route)

    bridge = read("template/.agents/skills/browser-ops/SKILL.md")
    if ".project-agent-workflow/skills/browser-ops/SKILL.md" not in bridge:
        fail("browser discovery bridge does not point at managed skill")
    skill = read("template/.project-agent-workflow/skills/browser-ops/SKILL.md")
    require_markers(
        "managed browser skill",
        "policy reads",
        skill,
        (
            "references/browser-run-policy.md",
            ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
            "docs/agent/external-services.yaml",
        ),
    )
    policy = read("template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md")
    require_markers(
        "browser backend policy",
        "compatibility boundary",
        policy,
        (
            "https://blog.cloudflare.com/kitesurf/",
            "beta",
            "lower CPU and memory consumption",
            "configured_write_capable",
            "exact `write_authorization_rule` match",
            "current user authorization",
            "WebGL",
            "real TLS fingerprints",
            "ordinary HTTP retrieval",
            "Cloudflare Browser Run as one service",
            "distinct project-owned external-service record",
        ),
    )
    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .agents/skills/browser-ops/SKILL.md" not in ownership:
        fail("browser discovery bridge is not reserved by Copier ownership")
    fixture = json.loads(read("tests/fixtures/browser-ops/scenarios.json"))
    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not any(item.get("critical") is True for item in requirements):
        fail("browser scenarios need a critical requirement")
    classes = {item.get("class") for item in scenarios}
    if not {"median", "edge", "holdout"}.issubset(classes):
        fail("browser scenarios need median, edge, and holdout cases")
    expected = {"authorized Kitesurf", "Chromium fallback", "ordinary HTTP retrieval", "documented unavailable fallback", "deny browser write"}
    if not expected.issubset({item.get("expected") for item in scenarios}):
        fail("browser scenarios do not cover backend, plain HTTP, fallback, and write denial")
    expected_conditions = {
        "kitesurf-pdf": {
            "needs_rendered_browser": True,
            "access": "read",
            "browser_run_authorized": True,
            "provider_available": True,
            "requires_chromium": False,
        },
        "chromium-webgl": {
            "needs_rendered_browser": True,
            "access": "read",
            "browser_run_authorized": True,
            "provider_available": True,
            "requires_chromium": True,
        },
        "plain-http": {"needs_rendered_browser": False},
        "provider-unavailable": {
            "needs_rendered_browser": True,
            "access": "read",
            "browser_run_authorized": True,
            "provider_available": False,
            "requires_chromium": False,
        },
        "unauthorized-submit": {
            "needs_rendered_browser": True,
            "access": "write",
            "browser_run_authorized": True,
            "provider_available": True,
            "operation_allowlisted": True,
            "exact_write_authorization_rule": True,
            "current_user_authorization": False,
            "requires_chromium": False,
        },
    }
    actual_conditions = {item.get("id"): item.get("conditions") for item in scenarios}
    if actual_conditions != expected_conditions:
        fail("browser scenarios have incorrect condition-to-route mappings")
    for scenario_id in ("kitesurf-pdf", "chromium-webgl"):
        request = next(item["request"] for item in scenarios if item.get("id") == scenario_id)
        if "configured Browser Run record" not in request:
            fail(f"{scenario_id} request lacks configured Browser Run authorization premise")


def require_verify_copier_update_skill() -> None:
    root = ROOT / ".codex/skills/verify-copier-update"
    generated = ROOT / "template/.project-agent-workflow/skills/verify-copier-update"
    relative_files = (
        "SKILL.md",
        "agents/openai.yaml",
        "references/verification-contract.md",
        "scripts/verify-copier-update.py",
    )
    for relative in relative_files:
        if (root / relative).read_bytes() != (generated / relative).read_bytes():
            fail(f"verify-copier-update root/template file differs: {relative}")
    root_helper = root / "scripts/verify-copier-update.py"
    generated_helper = generated / "scripts/verify-copier-update.py"
    if (root_helper.stat().st_mode & 0o777) != (generated_helper.stat().st_mode & 0o777):
        fail("verify-copier-update helper modes differ")
    if root_helper.stat().st_mode & 0o111 == 0:
        fail("verify-copier-update helpers must be executable")

    bridge = read("template/.agents/skills/verify-copier-update/SKILL.md")
    if ".project-agent-workflow/skills/verify-copier-update/SKILL.md" not in bridge:
        fail("verify-copier-update discovery bridge does not point at the managed Skill")
    skill = read("template/.project-agent-workflow/skills/verify-copier-update/SKILL.md")
    require_markers(
        "verify-copier-update Skill",
        "isolation and result boundary",
        skill,
        (
            "references/verification-contract.md",
            "disposable clone",
            "target-specific validation command",
            "`verified`",
            "`rejected`",
            "`blocked`",
            "not for applying or committing a live update",
        ),
    )
    helper = read(
        "template/.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py"
    )
    require_markers(
        "verify-copier-update helper",
        "fail-closed execution boundary",
        helper,
        (
            '"--trust-template-tasks"',
            '"--validation-command-json"',
            '"--no-hardlinks"',
            "UPDATE_WRAPPER",
            "UPDATE_VALIDATOR",
            "CHANGE_VALIDATOR",
            '"GIT_OPTIONAL_LOCKS"',
            "tracked_worktree_identity",
            "external_filter_unsupported",
            "submodule_unsupported",
            '"original_target_changed"',
            '"not_idempotent"',
            '"output_inside_repository"',
        ),
    )
    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .agents/skills/verify-copier-update/SKILL.md" not in ownership:
        fail("verify-copier-update discovery bridge is not reserved by Copier ownership")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-source-required":
        print("\n".join(SOURCE_REQUIRED))
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--print-generated-required":
        print("\n".join(GENERATED_REQUIRED))
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--print-source-shell":
        print("\n".join(SOURCE_SHELL_LINT))
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--print-source-python":
        print("\n".join(SOURCE_PYTHON_COMPILE))
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "--print-expected-generated":
        print("\n".join(expected_generated_paths(parse_fixture(Path(sys.argv[2])))))
        return 0
    if len(sys.argv) > 1:
        fail(f"unknown arguments: {' '.join(sys.argv[1:])}")

    for rel in SOURCE_REQUIRED:
        if not (ROOT / rel).is_file():
            fail(f"missing required file: {rel}")

    copier_yml = read("copier.yml")
    for key in ("_subdirectory: template", "_templates_suffix: .jinja", "_answers_file: .copier-answers.yml"):
        if key not in copier_yml:
            fail(f"copier.yml missing {key}")
    for question in QUESTIONS:
        if not re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml missing question: {question}")
    require_japanese_prompts(copier_yml)
    require_update_boundaries(copier_yml)
    require_context_compression_boundary()
    require_agent_profile_task()
    require_copier_documentation_contract()
    require_ci_autofix_root_boundaries()
    require_generated_whitespace_range()
    require_namespaced_reference_paths()
    require_mcp_execution_context_contract()
    require_browser_automation_contract()
    require_verify_copier_update_skill()
    for question in REMOVED_LOCAL_WORKFLOW_QUESTIONS:
        if re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml still prompts for local workflow question: {question}")
    for question in REMOVED_ACTIVATION_QUESTIONS:
        if re.search(rf"^{re.escape(question)}:", copier_yml, re.MULTILINE):
            fail(f"copier.yml still prompts for activation boolean: {question}")

    if (ROOT / "assets/templates").exists():
        fail("assets/templates must not exist; template/ is the source of truth")

    answers_template = read("template/[[ _copier_conf.answers_file ]].jinja")
    if "_copier_answers|to_nice_yaml" not in answers_template:
        fail("answers template must persist _copier_answers for future updates")

    require_sequential_worker()
    require_agent_model_profiles()
    require_fast_scoped_worker()
    require_evidence_synthesizer()
    require_referent_first_alignment()
    require_user_communication_alignment()
    require_git_retirement_alignment()
    require_sandboxed_plan_worker_alignment()
    require_hook_logging_parity()
    require_root_pre_tool_hardening()
    require_orchestration_policy_markers()
    require_template_manifest_complete()

    fixture_answers: list[dict[str, str]] = []
    for fixture in sorted((ROOT / "tests/fixtures").glob("*.answers.yml")):
        answers = parse_fixture(fixture)
        require_valid_answers(answers, str(fixture), complete=True)
        fixture_answers.append(answers)
        obsolete = REMOVED_LOCAL_WORKFLOW_QUESTIONS & set(answers)
        if obsolete:
            fail(f"{fixture} still contains removed local workflow answers: {sorted(obsolete)}")
        obsolete_activation = REMOVED_ACTIVATION_QUESTIONS & set(answers)
        if obsolete_activation:
            fail(f"{fixture} still contains removed activation answers: {sorted(obsolete_activation)}")

    pairwise_answers = parse_pairwise_fixture(PAIRWISE_FIXTURE)
    for index, answers in enumerate(pairwise_answers, start=1):
        require_valid_answers(answers, f"{PAIRWISE_FIXTURE} row {index}", complete=False)
    require_pairwise_coverage([*fixture_answers, *pairwise_answers])

    print("copier template static check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
