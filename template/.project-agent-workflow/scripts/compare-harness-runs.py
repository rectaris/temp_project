#!/usr/bin/env python3
"""Compare paired local harness runs for one model or instruction change.

The report is advisory derived information. It reads only the files named on the
command line, never discovers a run, never launches a model, never contacts a
network or provider, never looks up a price, and never writes a file or changes
plan lifecycle state. A value that the supplied records do not observe stays
``not_observed``; it never becomes zero, an estimate, or an adoption argument.

A digest proves that two records name the same bytes. It never proves that a
protocol was frozen before the runs, that a holdout stayed independent, or that
a local attestation is true. Those remain declared unless explicit independently
reviewed ordering evidence is supplied and its declared link verifies, and even
then this command reports who attested what rather than authenticating it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from typing import Any


MAX_INPUT_FILES = 64
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
MAX_OBSERVATIONS = 256
MAX_CASES = 64
MAX_REPETITIONS = 64

REPORT_SCHEMA_VERSION = 1
COMPARISON_PROTOCOL_SCHEMA_VERSION = 1
RUN_OBSERVATION_SCHEMA_VERSION = 1

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
MAX_ELAPSED_SECONDS = 31_536_000.0

CURRENT_INSTRUCTION_SLOTS = (
    "old_model_current_instructions",
    "new_model_current_instructions",
)
CANDIDATE_SLOT = "new_model_candidate_instructions"
SLOTS = CURRENT_INSTRUCTION_SLOTS + (CANDIDATE_SLOT,)

# Each comparison changes exactly one declared axis. Any other declared
# difference between the two configurations is an uncontrolled input.
COMPARISONS = (
    ("model_effect", "old_model_current_instructions", "new_model_current_instructions", "model"),
    ("instruction_effect", "new_model_current_instructions", CANDIDATE_SLOT, "instructions"),
)

OUTCOMES = ("completed", "failed", "timed_out", "model_unavailable")
NONTERMINAL_SUCCESS_OUTCOMES = ("failed", "timed_out", "model_unavailable")
FIXTURE_KINDS = ("synthetic", "operational")
HOLDOUT_STATES = ("withheld", "not_used", "used_for_tuning")
ORDERING_STATES = ("declared", "independently_reviewed")

ADMISSIBLE_JUDGMENT_KINDS = ("deterministic_test", "independent_evaluator")
JUDGMENT_KINDS = ADMISSIBLE_JUDGMENT_KINDS + ("agent_self_report",)

ELAPSED_BOUNDARY = "task_start_to_terminal_outcome"
COST_BOUNDARY = "directly_recorded_billed_amount"

PROTOCOL_KEYS = {
    "schema_version",
    "protocol_id",
    "repository_baseline",
    "invariant_digest",
    "authority_digest",
    "configurations",
    "cases",
    "repetitions",
    "budget",
    "metric_boundaries",
    "decision_limits",
    "freeze",
}
CONFIGURATION_KEYS = {
    "slot",
    "declared_model",
    "reasoning_settings",
    "instruction_asset_digests",
    "runtime",
    "configuration_digest",
}
CASE_KEYS = {"case_id", "task_digest", "acceptance_digest", "rubric_digest", "fixture_kind"}
OBSERVATION_KEYS = {
    "schema_version",
    "protocol_id",
    "slot",
    "case_id",
    "repetition",
    "task_digest",
    "acceptance_digest",
    "repository_baseline",
    "invariant_digest",
    "authority_digest",
    "configuration_digest",
    "fixture_kind",
    "observed_model",
    "observed_reasoning_settings",
    "observed_runtime",
    "instruction_loading",
    "outcome",
    "quality",
    "critical_violation",
    "elapsed_seconds",
    "billed_cost",
    "human_interventions",
    "evidence_digests",
}
JUDGMENT_KEYS = {
    "kind",
    "identity",
    "source_evidence_digest",
    "reviewer_provenance",
    "acceptance_item_digest",
    "rubric_digest",
}
DECISION_LIMIT_KEYS = {
    "require_all_critical_pass",
    "min_quality_pass_delta",
    "max_elapsed_ratio",
    "max_cost_ratio",
    "max_additional_interventions",
}
METRIC_BOUNDARY_KEYS = {"elapsed_seconds", "billed_cost", "human_interventions"}
BUDGET_KEYS = {"max_total_runs", "max_elapsed_seconds"}
FREEZE_KEYS = {"declared_frozen_at", "holdout_status", "ordering_evidence"}
ORDERING_EVIDENCE_KEYS = {"status", "reviewer_identity", "source", "attestation_digest"}

# Values this command never derives from anything else.
NEVER_INFERRED = (
    "billed_cost",
    "human_intervention_count",
    "provider_price",
    "quality_judgment",
    "token_counts",
)

# Statements a reader must be able to rely on without reading the source.
BOUNDARY_NOTES = (
    "This command reads only the supplied files and produces no provider, policy, "
    "or plan lifecycle effect.",
    "A verified digest proves content consistency, never preregistration, holdout "
    "independence, or the truth of a local attestation.",
    "Declared configuration is never treated as observed execution.",
    "A critical violation is never offset by lower cost, shorter elapsed time, or "
    "fewer interventions.",
    "Synthetic fixtures demonstrate tool behavior only and never support adoption.",
)


class ComparisonError(Exception):
    """An input or bound violation that must reject the whole report."""


def read_bounded_regular_file(path: str, label: str) -> bytes:
    """Read an explicitly supplied regular file without following a symlink."""

    # O_NONBLOCK classifies the file before any wait: opening a FIFO without it
    # blocks until a writer appears, so the regular-file check would never run.
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
    except OSError as exc:
        raise ComparisonError(f"{label} is not a readable regular file: {path}") from exc
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise ComparisonError(f"{label} must be a regular file: {path}")
        os.set_blocking(descriptor, True)
        if status.st_size > MAX_INPUT_BYTES:
            raise ComparisonError(
                f"{label} exceeds the {MAX_INPUT_BYTES}-byte input bound: {path}"
            )
        data = b""
        while len(data) <= MAX_INPUT_BYTES:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            data += chunk
        if len(data) > MAX_INPUT_BYTES:
            raise ComparisonError(
                f"{label} exceeds the {MAX_INPUT_BYTES}-byte input bound: {path}"
            )
        return data
    except OSError as exc:
        raise ComparisonError(f"{label} could not be read: {path}") from exc
    finally:
        os.close(descriptor)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def load_json_object(path: str, label: str) -> tuple[dict[str, Any], str]:
    data = read_bounded_regular_file(path, label)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ComparisonError(f"{label} must contain a JSON object: {path}")
    return value, digest_bytes(data)


def require_exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComparisonError(f"{label} must be a JSON object")
    supplied = set(value)
    missing = sorted(keys - supplied)
    unknown = sorted(supplied - keys)
    if missing or unknown:
        raise ComparisonError(
            f"{label} has an invalid exact field shape: missing={missing}, unknown={unknown}"
        )
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonError(f"{label} must be a nonempty string")
    return value


def require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not DIGEST_PATTERN.match(value):
        raise ComparisonError(f"{label} is not a well-formed sha256 digest")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ComparisonError(f"{label} must be a boolean")
    return value


def require_counter(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ComparisonError(f"{label} must be an integer of at least {minimum}")
    return value


def require_number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ComparisonError(f"{label} must be a finite number")
    if minimum is not None and number < minimum:
        raise ComparisonError(f"{label} must be at least {minimum}")
    return number


def require_choice(value: Any, choices: tuple[str, ...], label: str) -> str:
    if value not in choices:
        raise ComparisonError(f"{label} must be one of {list(choices)}")
    return value


def require_digest_map(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ComparisonError(f"{label} must be a nonempty object of sha256 digests")
    result: dict[str, str] = {}
    for name, digest in value.items():
        key = require_text(name, f"{label} key")
        result[key] = require_digest(digest, f"{label}[{key}]")
    return result


def require_version_map(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ComparisonError(f"{label} must be an object of version strings")
    return {
        require_text(name, f"{label} key"): require_text(version, f"{label}[{name}]")
        for name, version in value.items()
    }


def parse_reasoning_settings(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"supported", "effort"}:
        raise ComparisonError(f"{label} has an invalid exact field shape")
    supported = require_bool(value["supported"], f"{label} supported")
    effort = value["effort"]
    if supported:
        return {"supported": True, "effort": require_text(effort, f"{label} effort")}
    if effort is not None:
        raise ComparisonError(f"{label} must omit an effort when reasoning is unsupported")
    return {"supported": False, "effort": None}


def parse_runtime(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"cli_version", "tool_versions"}:
        raise ComparisonError(f"{label} has an invalid exact field shape")
    return {
        "cli_version": require_text(value["cli_version"], f"{label} cli_version"),
        "tool_versions": require_version_map(value["tool_versions"], f"{label} tool_versions"),
    }


def parse_configuration(value: Any, slot: str) -> dict[str, Any]:
    label = f"configuration {slot}"
    payload = require_exact_keys(value, CONFIGURATION_KEYS, label)
    if payload["slot"] != slot:
        raise ComparisonError(f"{label} declares a different slot: {payload['slot']}")
    return {
        "slot": slot,
        "declared_model": require_text(payload["declared_model"], f"{label} declared_model"),
        "reasoning_settings": parse_reasoning_settings(
            payload["reasoning_settings"], f"{label} reasoning_settings"
        ),
        "instruction_asset_digests": require_digest_map(
            payload["instruction_asset_digests"], f"{label} instruction_asset_digests"
        ),
        "runtime": parse_runtime(payload["runtime"], f"{label} runtime"),
        "configuration_digest": require_digest(
            payload["configuration_digest"], f"{label} configuration_digest"
        ),
    }


def parse_case(value: Any, index: int) -> dict[str, Any]:
    label = f"case[{index}]"
    payload = require_exact_keys(value, CASE_KEYS, label)
    return {
        "case_id": require_text(payload["case_id"], f"{label} case_id"),
        "task_digest": require_digest(payload["task_digest"], f"{label} task_digest"),
        "acceptance_digest": require_digest(
            payload["acceptance_digest"], f"{label} acceptance_digest"
        ),
        "rubric_digest": require_digest(payload["rubric_digest"], f"{label} rubric_digest"),
        "fixture_kind": require_choice(
            payload["fixture_kind"], FIXTURE_KINDS, f"{label} fixture_kind"
        ),
    }


def parse_ordering_evidence(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = require_exact_keys(value, ORDERING_EVIDENCE_KEYS, "freeze ordering_evidence")
    return {
        "status": require_choice(
            payload["status"], ORDERING_STATES, "freeze ordering_evidence status"
        ),
        "reviewer_identity": require_text(
            payload["reviewer_identity"], "freeze ordering_evidence reviewer_identity"
        ),
        "source": require_text(payload["source"], "freeze ordering_evidence source"),
        "attestation_digest": require_digest(
            payload["attestation_digest"], "freeze ordering_evidence attestation_digest"
        ),
    }


def parse_protocol(path: str) -> dict[str, Any]:
    payload, source_digest = load_json_object(path, "comparison protocol")
    protocol = require_exact_keys(payload, PROTOCOL_KEYS, "comparison protocol")
    if protocol["schema_version"] != COMPARISON_PROTOCOL_SCHEMA_VERSION:
        raise ComparisonError(
            "comparison protocol schema_version must be "
            f"{COMPARISON_PROTOCOL_SCHEMA_VERSION}"
        )

    configurations_value = protocol["configurations"]
    if not isinstance(configurations_value, dict):
        raise ComparisonError("comparison protocol configurations must be an object")
    unknown_slots = sorted(set(configurations_value) - set(SLOTS))
    if unknown_slots:
        raise ComparisonError(f"comparison protocol declares unknown slots: {unknown_slots}")
    for slot in CURRENT_INSTRUCTION_SLOTS:
        if slot not in configurations_value:
            raise ComparisonError(f"comparison protocol must declare the {slot} slot")
    configurations = {
        slot: parse_configuration(configurations_value[slot], slot)
        for slot in SLOTS
        if slot in configurations_value
    }

    cases_value = protocol["cases"]
    if not isinstance(cases_value, list) or not cases_value:
        raise ComparisonError("comparison protocol cases must be a nonempty list")
    if len(cases_value) > MAX_CASES:
        raise ComparisonError(f"comparison protocol declares more than {MAX_CASES} cases")
    cases: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for index, item in enumerate(cases_value):
        case = parse_case(item, index)
        if case["case_id"] in cases:
            raise ComparisonError(f"comparison protocol repeats case_id: {case['case_id']}")
        cases[case["case_id"]] = case
        order.append(case["case_id"])

    repetitions = require_counter(protocol["repetitions"], "repetitions", minimum=1)
    if repetitions > MAX_REPETITIONS:
        raise ComparisonError(f"repetitions must not exceed {MAX_REPETITIONS}")

    budget = require_exact_keys(protocol["budget"], BUDGET_KEYS, "budget")
    parsed_budget = {
        "max_total_runs": require_counter(budget["max_total_runs"], "budget max_total_runs", minimum=1),
        "max_elapsed_seconds": require_number(
            budget["max_elapsed_seconds"], "budget max_elapsed_seconds", minimum=0.0
        ),
    }
    expected_cells = len(cases) * repetitions * len(configurations)
    if parsed_budget["max_total_runs"] < expected_cells:
        raise ComparisonError(
            "budget max_total_runs is smaller than the enumerated "
            f"{expected_cells}-cell roster"
        )

    boundaries = require_exact_keys(
        protocol["metric_boundaries"], METRIC_BOUNDARY_KEYS, "metric_boundaries"
    )
    if boundaries["elapsed_seconds"] != ELAPSED_BOUNDARY:
        raise ComparisonError(
            f"metric_boundaries elapsed_seconds must be {ELAPSED_BOUNDARY!r}"
        )
    if boundaries["billed_cost"] != COST_BOUNDARY:
        raise ComparisonError(f"metric_boundaries billed_cost must be {COST_BOUNDARY!r}")
    intervention_rule = require_text(
        boundaries["human_interventions"], "metric_boundaries human_interventions"
    )

    limits = require_exact_keys(protocol["decision_limits"], DECISION_LIMIT_KEYS, "decision_limits")
    if limits["require_all_critical_pass"] is not True:
        raise ComparisonError("decision_limits require_all_critical_pass must be true")
    parsed_limits = {
        "require_all_critical_pass": True,
        "min_quality_pass_delta": require_number(
            limits["min_quality_pass_delta"], "decision_limits min_quality_pass_delta"
        ),
        "max_elapsed_ratio": require_number(
            limits["max_elapsed_ratio"], "decision_limits max_elapsed_ratio", minimum=0.0
        ),
        "max_cost_ratio": require_number(
            limits["max_cost_ratio"], "decision_limits max_cost_ratio", minimum=0.0
        ),
        "max_additional_interventions": require_counter(
            limits["max_additional_interventions"],
            "decision_limits max_additional_interventions",
        ),
    }

    freeze = require_exact_keys(protocol["freeze"], FREEZE_KEYS, "freeze")
    parsed_freeze = {
        "declared_frozen_at": require_text(freeze["declared_frozen_at"], "freeze declared_frozen_at"),
        "holdout_status": require_choice(
            freeze["holdout_status"], HOLDOUT_STATES, "freeze holdout_status"
        ),
        "ordering_evidence": parse_ordering_evidence(freeze["ordering_evidence"]),
    }

    record = {
        "protocol_id": require_text(protocol["protocol_id"], "protocol_id"),
        "repository_baseline": require_digest(
            protocol["repository_baseline"], "repository_baseline"
        ),
        "invariant_digest": require_digest(protocol["invariant_digest"], "invariant_digest"),
        "authority_digest": require_digest(protocol["authority_digest"], "authority_digest"),
        "configurations": configurations,
        "cases": cases,
        "case_order": order,
        "repetitions": repetitions,
        "budget": parsed_budget,
        "metric_boundaries": dict(boundaries),
        "intervention_rule_digest": digest_text(intervention_rule),
        "decision_limits": parsed_limits,
        "freeze": parsed_freeze,
        "source_digest": source_digest,
        "expected_cells": expected_cells,
    }
    require_controlled_axes(record)
    return record


def require_controlled_axes(protocol: dict[str, Any]) -> None:
    """Reject a protocol whose two paired configurations differ outside one axis."""

    configurations = protocol["configurations"]
    digests = {slot: config["configuration_digest"] for slot, config in configurations.items()}
    if len(set(digests.values())) != len(digests):
        raise ComparisonError("two configuration slots share one configuration_digest")
    for name, left_slot, right_slot, axis in COMPARISONS:
        left = configurations.get(left_slot)
        right = configurations.get(right_slot)
        if left is None or right is None:
            continue
        if left["runtime"] != right["runtime"]:
            raise ComparisonError(
                f"{name} declares uncontrolled runtime inputs between {left_slot} and {right_slot}"
            )
        same_model = left["declared_model"] == right["declared_model"]
        same_instructions = (
            left["instruction_asset_digests"] == right["instruction_asset_digests"]
        )
        if axis == "model":
            if same_model:
                raise ComparisonError(f"{name} does not change the declared model")
            if not same_instructions:
                raise ComparisonError(
                    f"{name} changes the declared instruction assets outside the model axis"
                )
        else:
            if not same_model:
                raise ComparisonError(
                    f"{name} changes the declared model outside the instruction axis"
                )
            if same_instructions:
                raise ComparisonError(f"{name} does not change the declared instruction assets")


def parse_status_value(
    value: Any,
    label: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Parse an object whose payload fields must all be absent when unobserved."""

    expected = {"status"} | set(fields)
    payload = require_exact_keys(value, expected, label)
    status = require_choice(payload["status"], ("observed", "not_observed"), f"{label} status")
    if status == "not_observed":
        for name in fields:
            if payload[name] is not None:
                raise ComparisonError(f"unobserved {label} must leave {name} null")
        return {"status": "not_observed", **{name: None for name in fields}}
    return {
        "status": "observed",
        **{name: parser(payload[name], f"{label} {name}") for name, parser in fields.items()},
    }


def parse_observed_model(value: Any) -> dict[str, Any]:
    label = "observed_model"
    payload = require_exact_keys(value, {"status", "identity", "resolved_snapshot"}, label)
    status = require_choice(payload["status"], ("observed", "not_observed"), f"{label} status")
    if status == "not_observed":
        if payload["identity"] is not None or payload["resolved_snapshot"] is not None:
            raise ComparisonError("unobserved observed_model must leave every field null")
        return {"status": "not_observed", "identity": None, "resolved_snapshot": None}
    snapshot = payload["resolved_snapshot"]
    return {
        "status": "observed",
        "identity": require_text(payload["identity"], f"{label} identity"),
        # A provider that does not expose a resolved snapshot stays unobserved
        # rather than inheriting the requested identity.
        "resolved_snapshot": (
            None if snapshot is None else require_text(snapshot, f"{label} resolved_snapshot")
        ),
    }


def parse_instruction_loading(value: Any) -> dict[str, Any]:
    label = "instruction_loading"
    payload = require_exact_keys(
        value, {"status", "effective_instruction_digests", "host_instructions"}, label
    )
    status = require_choice(payload["status"], ("observed", "not_observed"), f"{label} status")
    host = require_choice(
        payload["host_instructions"], ("known", "unknown"), f"{label} host_instructions"
    )
    if status == "not_observed":
        if payload["effective_instruction_digests"] is not None:
            raise ComparisonError(
                "unobserved instruction_loading must leave effective_instruction_digests null"
            )
        return {
            "status": "not_observed",
            "effective_instruction_digests": None,
            "host_instructions": host,
        }
    return {
        "status": "observed",
        "effective_instruction_digests": require_digest_map(
            payload["effective_instruction_digests"], f"{label} effective_instruction_digests"
        ),
        "host_instructions": host,
    }


def parse_billed_cost(value: Any) -> dict[str, Any]:
    """Read an explicit billed amount; never derive one from a price table."""

    label = "billed_cost"
    payload = require_exact_keys(value, {"status", "amount", "currency"}, label)
    status = require_choice(payload["status"], ("observed", "not_observed"), f"{label} status")
    if status == "not_observed":
        if payload["amount"] is not None or payload["currency"] is not None:
            raise ComparisonError("unobserved billed_cost must leave every field null")
        return {"status": "not_observed", "amount": None, "currency": None}
    amount = require_number(payload["amount"], f"{label} amount", minimum=0.0)
    currency = payload["currency"]
    if not isinstance(currency, str) or not CURRENCY_PATTERN.match(currency):
        raise ComparisonError("observed billed_cost requires an explicit ISO currency code")
    return {"status": "observed", "amount": amount, "currency": currency}


def parse_human_interventions(value: Any, rule_digest: str) -> dict[str, Any]:
    label = "human_interventions"
    payload = require_exact_keys(value, {"status", "count", "counting_rule_digest"}, label)
    status = require_choice(payload["status"], ("observed", "not_observed"), f"{label} status")
    declared_rule = require_digest(
        payload["counting_rule_digest"], f"{label} counting_rule_digest"
    )
    if declared_rule != rule_digest:
        raise ComparisonError(
            "human_interventions were counted under a different frozen counting rule"
        )
    if status == "not_observed":
        if payload["count"] is not None:
            raise ComparisonError("unobserved human_interventions must leave count null")
        return {"status": "not_observed", "count": None, "counting_rule_digest": declared_rule}
    return {
        "status": "observed",
        "count": require_counter(payload["count"], f"{label} count"),
        "counting_rule_digest": declared_rule,
    }


def parse_judgment(value: Any, case: dict[str, Any]) -> dict[str, Any]:
    label = "quality judgment"
    payload = require_exact_keys(value, JUDGMENT_KEYS, label)
    kind = require_choice(payload["kind"], JUDGMENT_KINDS, f"{label} kind")
    acceptance_item = require_digest(
        payload["acceptance_item_digest"], f"{label} acceptance_item_digest"
    )
    rubric = require_digest(payload["rubric_digest"], f"{label} rubric_digest")
    if acceptance_item != case["acceptance_digest"]:
        raise ComparisonError(
            f"{label} binds an acceptance item that differs from case {case['case_id']}"
        )
    if rubric != case["rubric_digest"]:
        raise ComparisonError(
            f"{label} binds a rubric that differs from case {case['case_id']}"
        )
    return {
        "kind": kind,
        "identity": require_text(payload["identity"], f"{label} identity"),
        "source_evidence_digest": require_digest(
            payload["source_evidence_digest"], f"{label} source_evidence_digest"
        ),
        "reviewer_provenance": require_text(
            payload["reviewer_provenance"], f"{label} reviewer_provenance"
        ),
        "acceptance_item_digest": acceptance_item,
        "rubric_digest": rubric,
        "admissible": kind in ADMISSIBLE_JUDGMENT_KINDS,
    }


def parse_quality(value: Any, case: dict[str, Any]) -> dict[str, Any]:
    label = "quality"
    payload = require_exact_keys(value, {"status", "acceptance_result", "judgment"}, label)
    status = require_choice(payload["status"], ("observed", "not_observed"), f"{label} status")
    if status == "not_observed":
        if payload["acceptance_result"] is not None or payload["judgment"] is not None:
            raise ComparisonError("unobserved quality must leave every field null")
        return {
            "status": "not_observed",
            "acceptance_result": None,
            "judgment": None,
            "admissible": False,
        }
    result = require_choice(
        payload["acceptance_result"], ("pass", "fail"), f"{label} acceptance_result"
    )
    judgment = parse_judgment(payload["judgment"], case)
    return {
        "status": "observed",
        "acceptance_result": result,
        "judgment": judgment,
        "admissible": judgment["admissible"],
    }


def parse_observation(path: str, protocol: dict[str, Any]) -> dict[str, Any]:
    payload, source_digest = load_json_object(path, "run observation")
    record = require_exact_keys(payload, OBSERVATION_KEYS, "run observation")
    if record["schema_version"] != RUN_OBSERVATION_SCHEMA_VERSION:
        raise ComparisonError(
            f"run observation schema_version must be {RUN_OBSERVATION_SCHEMA_VERSION}"
        )
    if record["protocol_id"] != protocol["protocol_id"]:
        raise ComparisonError("run observation names a different comparison protocol")

    slot = require_choice(record["slot"], SLOTS, "run observation slot")
    if slot not in protocol["configurations"]:
        raise ComparisonError(f"run observation names a slot the protocol does not declare: {slot}")
    configuration = protocol["configurations"][slot]

    case_id = require_text(record["case_id"], "run observation case_id")
    case = protocol["cases"].get(case_id)
    if case is None:
        raise ComparisonError(f"run observation names a case outside the roster: {case_id}")

    repetition = require_counter(record["repetition"], "run observation repetition", minimum=1)
    if repetition > protocol["repetitions"]:
        raise ComparisonError(
            f"run observation repetition {repetition} exceeds the frozen roster"
        )

    for field, expected, message in (
        ("task_digest", case["task_digest"], "task"),
        ("acceptance_digest", case["acceptance_digest"], "acceptance"),
        ("repository_baseline", protocol["repository_baseline"], "repository baseline"),
        ("invariant_digest", protocol["invariant_digest"], "invariant"),
        ("authority_digest", protocol["authority_digest"], "authority"),
        ("configuration_digest", configuration["configuration_digest"], "configuration"),
    ):
        if require_digest(record[field], f"run observation {field}") != expected:
            raise ComparisonError(
                f"run observation for {slot}/{case_id}#{repetition} declares a different "
                f"{message} digest than the frozen protocol"
            )
    if record["fixture_kind"] != case["fixture_kind"]:
        raise ComparisonError(
            f"run observation for {slot}/{case_id}#{repetition} declares a different fixture kind"
        )

    evidence_digests = require_digest_map(record["evidence_digests"], "evidence_digests")
    quality = parse_quality(record["quality"], case)
    outcome = require_choice(record["outcome"], OUTCOMES, "run observation outcome")
    elapsed = parse_status_value(
        record["elapsed_seconds"],
        "elapsed_seconds",
        {"value": lambda value, label: require_bounded_elapsed(value, label)},
    )
    if outcome == "timed_out" and elapsed["status"] != "observed":
        raise ComparisonError(
            f"timed-out run {slot}/{case_id}#{repetition} must record its elapsed seconds"
        )

    return {
        "slot": slot,
        "case_id": case_id,
        "repetition": repetition,
        "cell": f"{slot}/{case_id}#{repetition}",
        "fixture_kind": case["fixture_kind"],
        "source_digest": source_digest,
        "observed_model": parse_observed_model(record["observed_model"]),
        "observed_reasoning_settings": parse_status_value(
            record["observed_reasoning_settings"],
            "observed_reasoning_settings",
            {
                "supported": require_bool,
                "effort": lambda value, label: (
                    None if value is None else require_text(value, label)
                ),
            },
        ),
        "observed_runtime": parse_status_value(
            record["observed_runtime"],
            "observed_runtime",
            {
                "cli_version": require_text,
                "tool_versions": require_version_map,
            },
        ),
        "instruction_loading": parse_instruction_loading(record["instruction_loading"]),
        "outcome": outcome,
        "quality": quality,
        "critical_violation": require_bool(
            record["critical_violation"], "run observation critical_violation"
        ),
        "elapsed_seconds": elapsed,
        "billed_cost": parse_billed_cost(record["billed_cost"]),
        "human_interventions": parse_human_interventions(
            record["human_interventions"], protocol["intervention_rule_digest"]
        ),
        "evidence_digests": evidence_digests,
    }


def require_bounded_elapsed(value: Any, label: str) -> float:
    number = require_number(value, label, minimum=0.0)
    if number > MAX_ELAPSED_SECONDS:
        raise ComparisonError(f"{label} is outside the supported duration bound")
    return number


def load_observations(paths: list[str], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if len(paths) > MAX_OBSERVATIONS:
        raise ComparisonError(
            f"at most {MAX_OBSERVATIONS} run observations are supported per report"
        )
    observations: list[dict[str, Any]] = []
    seen_cells: dict[str, str] = {}
    seen_digests: set[str] = set()
    for path in paths:
        record = parse_observation(path, protocol)
        if record["source_digest"] in seen_digests:
            raise ComparisonError(
                f"the same run observation was supplied twice: {record['cell']}"
            )
        if record["cell"] in seen_cells:
            raise ComparisonError(f"duplicate run observation for cell {record['cell']}")
        seen_cells[record["cell"]] = record["source_digest"]
        seen_digests.add(record["source_digest"])
        observations.append(record)
    observations.sort(key=lambda record: (record["slot"], record["case_id"], record["repetition"]))
    return observations


def verify_evidence(
    observations: list[dict[str, Any]],
    protocol: dict[str, Any],
    evidence_paths: list[str],
    ordering_paths: list[str],
) -> dict[str, Any]:
    declared: dict[str, list[str]] = {}
    for record in observations:
        for name, digest in record["evidence_digests"].items():
            declared.setdefault(digest, []).append(f"{record['cell']}:{name}")
    for record in observations:
        judgment = record["quality"]["judgment"]
        if judgment is not None:
            declared.setdefault(judgment["source_evidence_digest"], []).append(
                f"{record['cell']}:quality_judgment"
            )

    verified: list[dict[str, Any]] = []
    for path in evidence_paths:
        data = read_bounded_regular_file(path, "evidence file")
        digest = digest_bytes(data)
        bindings = declared.get(digest)
        if bindings is None:
            raise ComparisonError(
                "supplied evidence file matches no declared evidence digest"
            )
        verified.append({"digest": digest, "bound_to": sorted(bindings), "verification": "matched"})

    ordering = protocol["freeze"]["ordering_evidence"]
    ordering_state = "absent"
    ordering_report: dict[str, Any] = {
        "state": "absent",
        "declared": None,
        "verification": "not_supplied",
    }
    if ordering is not None:
        ordering_report["declared"] = {
            "status": ordering["status"],
            "reviewer_identity": ordering["reviewer_identity"],
            "source": ordering["source"],
            "attestation_digest": ordering["attestation_digest"],
        }
        ordering_state = "declared_unverified"
        ordering_report["verification"] = "not_supplied"
    matched = False
    for path in ordering_paths:
        data = read_bounded_regular_file(path, "ordering evidence file")
        digest = digest_bytes(data)
        if ordering is None:
            raise ComparisonError(
                "ordering evidence was supplied but the protocol declares none"
            )
        if digest != ordering["attestation_digest"]:
            raise ComparisonError(
                "supplied ordering evidence does not match the declared attestation digest"
            )
        matched = True
    if ordering is not None and matched:
        ordering_report["verification"] = "digest_matched"
        ordering_state = (
            "independently_reviewed_link_verified"
            if ordering["status"] == "independently_reviewed"
            else "declared_link_verified"
        )
    ordering_report["state"] = ordering_state
    ordering_report["authentication_note"] = (
        "This command verifies the declared link and records its stated reviewer and "
        "source. It cannot authenticate the real-world truth of a local attestation."
    )

    verified.sort(key=lambda entry: entry["digest"])
    return {
        "evidence": verified,
        "declared_digest_count": len(declared),
        "ordering_evidence": ordering_report,
    }


def enumerate_cells(protocol: dict[str, Any]) -> list[str]:
    cells: list[str] = []
    for slot in SLOTS:
        if slot not in protocol["configurations"]:
            continue
        for case_id in protocol["case_order"]:
            for repetition in range(1, protocol["repetitions"] + 1):
                cells.append(f"{slot}/{case_id}#{repetition}")
    return cells


def summarize_coverage(
    protocol: dict[str, Any], observations: list[dict[str, Any]]
) -> dict[str, Any]:
    expected = enumerate_cells(protocol)
    observed = {record["cell"] for record in observations}
    missing = [cell for cell in expected if cell not in observed]
    return {
        "expected_cells": len(expected),
        "observed_cells": len(observed),
        "missing_cells": missing,
        "complete": not missing,
        "repetitions": protocol["repetitions"],
        "cases": len(protocol["case_order"]),
        "slots": sorted(protocol["configurations"]),
    }


def declared_evidence_digests(record: dict[str, Any]) -> set[str]:
    digests = set(record["evidence_digests"].values())
    judgment = record["quality"]["judgment"]
    if judgment is not None:
        digests.add(judgment["source_evidence_digest"])
    return digests


def summarize_slot(
    slot: str, records: list[dict[str, Any]], configuration: dict[str, Any]
) -> dict[str, Any]:
    total = len(records)
    declared_runtime = configuration["runtime"]
    declared_reasoning = configuration["reasoning_settings"]
    declared_instructions = configuration["instruction_asset_digests"]
    outcomes = {outcome: sum(1 for r in records if r["outcome"] == outcome) for outcome in OUTCOMES}
    completed = [r for r in records if r["outcome"] == "completed"]
    # A non-completed run stays in the denominator. Comparing only survivors
    # would hide the failure rate that the change is supposed to be judged on.
    passes = [
        r
        for r in records
        if r["outcome"] == "completed"
        and r["quality"]["status"] == "observed"
        and r["quality"]["acceptance_result"] == "pass"
    ]
    unevaluated = [
        r for r in completed if r["quality"]["status"] != "observed"
    ]
    inadmissible = [
        r
        for r in records
        if r["quality"]["status"] == "observed" and not r["quality"]["admissible"]
    ]
    elapsed_all = [r["elapsed_seconds"]["value"] for r in records if r["elapsed_seconds"]["status"] == "observed"]
    elapsed_completed = [
        r["elapsed_seconds"]["value"] for r in completed if r["elapsed_seconds"]["status"] == "observed"
    ]
    interventions = [
        r["human_interventions"]["count"]
        for r in records
        if r["human_interventions"]["status"] == "observed"
    ]
    cost_records = [r for r in records if r["billed_cost"]["status"] == "observed"]
    currencies = sorted({r["billed_cost"]["currency"] for r in cost_records})
    cost_total = round(sum(r["billed_cost"]["amount"] for r in cost_records), 6) if cost_records else None
    return {
        "slot": slot,
        "runs_total": total,
        "outcomes": outcomes,
        "critical_violations": sum(1 for r in records if r["critical_violation"]),
        "quality_pass_count": len(passes),
        "quality_denominator": total,
        "quality_pass_rate": round(len(passes) / total, 6) if total else None,
        "quality_unevaluated_completed": [r["cell"] for r in unevaluated],
        "quality_inadmissible": [r["cell"] for r in inadmissible],
        "elapsed_seconds_all_runs": {
            "total": round(sum(elapsed_all), 6) if elapsed_all else None,
            "mean": round(sum(elapsed_all) / len(elapsed_all), 6) if elapsed_all else None,
            "observation_count": len(elapsed_all),
            "denominator": total,
        },
        "elapsed_seconds_completed_runs": {
            "total": round(sum(elapsed_completed), 6) if elapsed_completed else None,
            "mean": (
                round(sum(elapsed_completed) / len(elapsed_completed), 6)
                if elapsed_completed
                else None
            ),
            "observation_count": len(elapsed_completed),
            "denominator": len(completed),
        },
        "billed_cost": {
            "status": "observed" if cost_records else "not_observed",
            "total": cost_total,
            "currencies": currencies,
            "observation_count": len(cost_records),
            "denominator": total,
        },
        "human_interventions": {
            "status": "observed" if interventions else "not_observed",
            "total": sum(interventions) if interventions else None,
            "observation_count": len(interventions),
            "denominator": total,
        },
        "instruction_loading_observed": sum(
            1 for r in records if r["instruction_loading"]["status"] == "observed"
        ),
        "unknown_host_instructions": sum(
            1 for r in records if r["instruction_loading"]["host_instructions"] == "unknown"
        ),
        "declared_model_confirmed": sum(
            1 for r in records if r["observed_model"]["status"] == "observed"
        ),
        # Declared configuration is confirmed only when a run observed it and the
        # observation matches the frozen declaration. An unobserved field is never
        # read as agreement.
        "declared_runtime_confirmed": sum(
            1
            for r in records
            if r["observed_runtime"]["status"] == "observed"
            and r["observed_runtime"]["cli_version"] == declared_runtime["cli_version"]
            and r["observed_runtime"]["tool_versions"] == declared_runtime["tool_versions"]
        ),
        "declared_reasoning_confirmed": sum(
            1
            for r in records
            if r["observed_reasoning_settings"]["status"] == "observed"
            and r["observed_reasoning_settings"]["supported"] == declared_reasoning["supported"]
            and r["observed_reasoning_settings"]["effort"] == declared_reasoning["effort"]
        ),
        "declared_instructions_confirmed": sum(
            1
            for r in records
            if r["instruction_loading"]["status"] == "observed"
            and r["instruction_loading"]["effective_instruction_digests"]
            == declared_instructions
        ),
        "effective_instruction_digest_sets": sorted(
            {
                json.dumps(r["instruction_loading"]["effective_instruction_digests"], sort_keys=True)
                for r in records
                if r["instruction_loading"]["status"] == "observed"
            }
        ),
        "declared_evidence_digests": sorted(
            {digest for r in records for digest in declared_evidence_digests(r)}
        ),
    }


def require_controlled_observations(
    name: str,
    axis: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> None:
    """Reject a pair whose observed runtime or model contradicts the declared axis."""

    left_runtime = left["observed_runtime"]
    right_runtime = right["observed_runtime"]
    if left_runtime["status"] == "observed" and right_runtime["status"] == "observed":
        if (
            left_runtime["cli_version"] != right_runtime["cli_version"]
            or left_runtime["tool_versions"] != right_runtime["tool_versions"]
        ):
            raise ComparisonError(
                f"{name} pair {left['case_id']}#{left['repetition']} observed uncontrolled "
                "runtime inputs"
            )
    left_model = left["observed_model"]
    right_model = right["observed_model"]
    if axis == "instructions" and left_model["status"] == "observed" and right_model["status"] == "observed":
        if left_model["identity"] != right_model["identity"]:
            raise ComparisonError(
                f"{name} pair {left['case_id']}#{left['repetition']} observed two different "
                "models on an instruction-only axis"
            )
    if axis == "model" and left_model["status"] == "observed" and right_model["status"] == "observed":
        if left_model["identity"] == right_model["identity"]:
            raise ComparisonError(
                f"{name} pair {left['case_id']}#{left['repetition']} observed the same model "
                "on a model-only axis"
            )


def axis_isolation(
    protocol: dict[str, Any], left_slot: str, right_slot: str
) -> dict[str, Any]:
    left = protocol["configurations"][left_slot]["reasoning_settings"]
    right = protocol["configurations"][right_slot]["reasoning_settings"]
    if left["supported"] != right["supported"]:
        return {
            "isolated": False,
            "kind": "configuration_comparison",
            "reason": "one configuration exposes reasoning settings and the other does not",
        }
    if left["supported"] and left["effort"] != right["effort"]:
        return {
            "isolated": False,
            "kind": "configuration_comparison",
            "reason": "the two configurations declare different reasoning effort",
        }
    return {"isolated": True, "kind": "single_axis_effect", "reason": None}


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def build_comparison(
    name: str,
    axis: str,
    baseline_slot: str,
    candidate_slot: str,
    protocol: dict[str, Any],
    by_slot: dict[str, list[dict[str, Any]]],
    slot_summaries: dict[str, dict[str, Any]],
    ordering_state: str,
    verified_digests: set[str],
) -> dict[str, Any]:
    baseline_records = {f"{r['case_id']}#{r['repetition']}": r for r in by_slot[baseline_slot]}
    candidate_records = {f"{r['case_id']}#{r['repetition']}": r for r in by_slot[candidate_slot]}
    paired_keys = sorted(set(baseline_records) & set(candidate_records))
    unpaired = sorted(set(baseline_records) ^ set(candidate_records))
    for key in paired_keys:
        require_controlled_observations(
            name, axis, baseline_records[key], candidate_records[key]
        )

    isolation = axis_isolation(protocol, baseline_slot, candidate_slot)
    baseline = slot_summaries[baseline_slot]
    candidate = slot_summaries[candidate_slot]
    limits = protocol["decision_limits"]

    quality_delta = None
    if baseline["quality_pass_rate"] is not None and candidate["quality_pass_rate"] is not None:
        quality_delta = round(
            candidate["quality_pass_rate"] - baseline["quality_pass_rate"], 6
        )
    elapsed_ratio = ratio(
        candidate["elapsed_seconds_all_runs"]["mean"], baseline["elapsed_seconds_all_runs"]["mean"]
    )
    cost_ratio = None
    cost_comparable = (
        baseline["billed_cost"]["status"] == "observed"
        and candidate["billed_cost"]["status"] == "observed"
        and baseline["billed_cost"]["currencies"] == candidate["billed_cost"]["currencies"]
        and len(baseline["billed_cost"]["currencies"]) == 1
    )
    if cost_comparable:
        cost_ratio = ratio(candidate["billed_cost"]["total"], baseline["billed_cost"]["total"])
    intervention_delta = None
    if (
        baseline["human_interventions"]["status"] == "observed"
        and candidate["human_interventions"]["status"] == "observed"
    ):
        intervention_delta = (
            candidate["human_interventions"]["total"] - baseline["human_interventions"]["total"]
        )

    evidence_blockers: list[str] = []
    limit_failures: list[str] = []
    critical_blockers: list[str] = []

    if not isolation["isolated"]:
        evidence_blockers.append("axis_not_isolated")
    if unpaired:
        evidence_blockers.append("unpaired_cells")
    if not paired_keys:
        evidence_blockers.append("no_paired_cells")
    expected_pairs = len(protocol["case_order"]) * protocol["repetitions"]
    if len(paired_keys) < expected_pairs:
        evidence_blockers.append("incomplete_coverage")
    if protocol["repetitions"] < 2:
        evidence_blockers.append("insufficient_repetitions")
    if any(
        protocol["cases"][case_id]["fixture_kind"] == "synthetic"
        for case_id in protocol["case_order"]
    ):
        evidence_blockers.append("synthetic_fixture")
    if protocol["freeze"]["holdout_status"] == "used_for_tuning":
        evidence_blockers.append("holdout_used_for_tuning")
    if ordering_state != "independently_reviewed_link_verified":
        evidence_blockers.append("ordering_evidence_not_independently_reviewed")
    for summary in (baseline, candidate):
        if summary["quality_unevaluated_completed"]:
            evidence_blockers.append("missing_quality_evidence")
        if summary["quality_inadmissible"]:
            evidence_blockers.append("inadmissible_quality_evidence")
        if summary["declared_model_confirmed"] < summary["runs_total"]:
            evidence_blockers.append("model_identity_not_observed")
        # A declared digest that was never supplied as a file is unverified
        # evidence. Counting it as present would let an unchecked claim carry an
        # adoption recommendation.
        if any(
            digest not in verified_digests for digest in summary["declared_evidence_digests"]
        ):
            evidence_blockers.append("declared_evidence_not_verified")
        if summary["declared_runtime_confirmed"] < summary["runs_total"]:
            evidence_blockers.append("runtime_not_confirmed")
        if summary["declared_reasoning_confirmed"] < summary["runs_total"]:
            evidence_blockers.append("reasoning_settings_not_confirmed")
        # A metric is comparable only when every run in the slot measured it.
        # A partial mean or a partial total would otherwise stand in for the
        # runs that recorded nothing.
        if summary["elapsed_seconds_all_runs"]["observation_count"] < summary["runs_total"]:
            evidence_blockers.append("elapsed_coverage_incomplete")
        if summary["billed_cost"]["observation_count"] < summary["runs_total"]:
            evidence_blockers.append("cost_coverage_incomplete")
        if summary["human_interventions"]["observation_count"] < summary["runs_total"]:
            evidence_blockers.append("intervention_coverage_incomplete")
    if axis == "instructions":
        for summary in (baseline, candidate):
            if summary["instruction_loading_observed"] < summary["runs_total"]:
                evidence_blockers.append("instruction_loading_not_observed")
            if summary["unknown_host_instructions"]:
                evidence_blockers.append("unknown_host_instructions")
            if summary["declared_instructions_confirmed"] < summary["runs_total"]:
                evidence_blockers.append("instruction_identity_not_confirmed")
        # An instruction effect requires the two sides to have actually loaded
        # different instructions. Identical observed instructions mean the axis
        # never moved, whatever the protocol declared.
        if (
            baseline["effective_instruction_digest_sets"]
            == candidate["effective_instruction_digest_sets"]
        ):
            evidence_blockers.append("instruction_change_not_observed")
    if quality_delta is None:
        evidence_blockers.append("quality_not_comparable")
    if elapsed_ratio is None:
        evidence_blockers.append("elapsed_not_comparable")
    if cost_ratio is None:
        evidence_blockers.append("cost_not_comparable")
    if intervention_delta is None:
        evidence_blockers.append("interventions_not_comparable")

    if candidate["critical_violations"] or baseline["critical_violations"]:
        critical_blockers.append("critical_violation_observed")
    # A candidate run that never reached a completed outcome is missing evidence
    # about the candidate, so it can never become adoption evidence. Baseline
    # failures stay in the totals because they are what the change is judged
    # against.
    if any(candidate["outcomes"][outcome] for outcome in NONTERMINAL_SUCCESS_OUTCOMES):
        evidence_blockers.append("candidate_run_not_completed")

    if quality_delta is not None and quality_delta < limits["min_quality_pass_delta"]:
        limit_failures.append("quality_limit_failed")
    if elapsed_ratio is not None and elapsed_ratio > limits["max_elapsed_ratio"]:
        limit_failures.append("elapsed_limit_failed")
    if cost_ratio is not None and cost_ratio > limits["max_cost_ratio"]:
        limit_failures.append("cost_limit_failed")
    if (
        intervention_delta is not None
        and intervention_delta > limits["max_additional_interventions"]
    ):
        limit_failures.append("intervention_limit_failed")

    evidence_blockers = sorted(set(evidence_blockers))
    limit_failures = sorted(set(limit_failures))

    if candidate["critical_violations"]:
        recommendation = "blocked_critical_failure"
    elif critical_blockers:
        recommendation = "insufficient_evidence"
    elif evidence_blockers:
        recommendation = "insufficient_evidence"
    elif limit_failures:
        recommendation = "keep_current"
    elif quality_delta is not None and quality_delta > 0:
        recommendation = "adopt_candidate"
    else:
        recommendation = "keep_current"

    return {
        "comparison": name,
        "axis": axis,
        "baseline_slot": baseline_slot,
        "candidate_slot": candidate_slot,
        "axis_isolation": isolation,
        "paired_cells": len(paired_keys),
        "expected_pairs": expected_pairs,
        "unpaired_cells": unpaired,
        "quality_pass_rate": {
            "baseline": baseline["quality_pass_rate"],
            "candidate": candidate["quality_pass_rate"],
            "delta": quality_delta,
            "denominator_note": "every enumerated run stays in the denominator",
        },
        "elapsed_ratio_all_runs": elapsed_ratio,
        "billed_cost_ratio": cost_ratio,
        "intervention_delta": intervention_delta,
        "critical_violations": {
            "baseline": baseline["critical_violations"],
            "candidate": candidate["critical_violations"],
        },
        "evidence_blockers": sorted(set(evidence_blockers)),
        "limit_failures": limit_failures,
        "critical_blockers": sorted(critical_blockers),
        "recommendation": recommendation,
        "empirical_recommendation_available": not evidence_blockers and not critical_blockers,
    }


def build_report(
    protocol: dict[str, Any],
    observations: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    by_slot = {slot: [] for slot in protocol["configurations"]}
    for record in observations:
        by_slot[record["slot"]].append(record)
    slot_summaries = {
        slot: summarize_slot(slot, records, protocol["configurations"][slot])
        for slot, records in by_slot.items()
    }
    ordering_state = evidence["ordering_evidence"]["state"]
    verified_digests = {entry["digest"] for entry in evidence["evidence"]}
    comparisons = []
    for name, baseline_slot, candidate_slot, axis in COMPARISONS:
        if baseline_slot in by_slot and candidate_slot in by_slot:
            comparisons.append(
                build_comparison(
                    name,
                    axis,
                    baseline_slot,
                    candidate_slot,
                    protocol,
                    by_slot,
                    slot_summaries,
                    ordering_state,
                    verified_digests,
                )
            )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": "paired_harness_comparison",
        "protocol": {
            "protocol_id": protocol["protocol_id"],
            "source_digest": protocol["source_digest"],
            "repository_baseline": protocol["repository_baseline"],
            "invariant_digest": protocol["invariant_digest"],
            "authority_digest": protocol["authority_digest"],
            "metric_boundaries": protocol["metric_boundaries"],
            "decision_limits": protocol["decision_limits"],
            "configurations": {
                slot: {
                    "declared_model": config["declared_model"],
                    "reasoning_settings": config["reasoning_settings"],
                    "configuration_digest": config["configuration_digest"],
                    "instruction_asset_digests": config["instruction_asset_digests"],
                    "runtime": config["runtime"],
                }
                for slot, config in protocol["configurations"].items()
            },
            "cases": [protocol["cases"][case_id] for case_id in protocol["case_order"]],
        },
        "declared_only": {
            "declared_frozen_at": protocol["freeze"]["declared_frozen_at"],
            "holdout_status": protocol["freeze"]["holdout_status"],
            "decision_limits": protocol["decision_limits"],
            "note": (
                "Freeze time, holdout status, and predeclared limits are declared by the "
                "operator. They are not independently reviewed ordering evidence."
            ),
        },
        "ordering_evidence": evidence["ordering_evidence"],
        "evidence": evidence["evidence"],
        "declared_evidence_digest_count": evidence["declared_digest_count"],
        "coverage": summarize_coverage(protocol, observations),
        "observations": [
            {
                "cell": record["cell"],
                "source_digest": record["source_digest"],
                "outcome": record["outcome"],
                "fixture_kind": record["fixture_kind"],
                "critical_violation": record["critical_violation"],
                "quality_status": record["quality"]["status"],
                "quality_result": record["quality"]["acceptance_result"],
                "quality_admissible": record["quality"]["admissible"],
                "quality_judgment": (
                    None
                    if record["quality"]["judgment"] is None
                    else {
                        "kind": record["quality"]["judgment"]["kind"],
                        "identity": record["quality"]["judgment"]["identity"],
                        "reviewer_provenance": record["quality"]["judgment"]["reviewer_provenance"],
                        "source_evidence_digest": record["quality"]["judgment"][
                            "source_evidence_digest"
                        ],
                    }
                ),
                "declared_model": protocol["configurations"][record["slot"]]["declared_model"],
                "observed_model": record["observed_model"],
                "observed_runtime": record["observed_runtime"],
                "instruction_loading": {
                    "status": record["instruction_loading"]["status"],
                    "host_instructions": record["instruction_loading"]["host_instructions"],
                },
                "elapsed_seconds": record["elapsed_seconds"],
                "billed_cost": record["billed_cost"],
                "human_interventions": record["human_interventions"],
            }
            for record in observations
        ],
        "configuration_summaries": [slot_summaries[slot] for slot in sorted(slot_summaries)],
        "comparisons": comparisons,
        "never_inferred": list(NEVER_INFERRED),
        "boundaries": list(BOUNDARY_NOTES),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = ["# Paired harness comparison", ""]
    protocol = report["protocol"]
    lines.append(f"protocol: {protocol['protocol_id']} source_digest={protocol['source_digest']}")
    lines.append(f"repository_baseline: {protocol['repository_baseline']}")
    coverage = report["coverage"]
    lines.append(
        "coverage: {observed_cells}/{expected_cells} enumerated cells "
        "({cases} cases x {repetitions} repetitions x {slot_count} configurations)".format(
            slot_count=len(coverage["slots"]), **coverage
        )
    )
    if coverage["missing_cells"]:
        lines.append(f"missing cells: {', '.join(coverage['missing_cells'])}")
    lines.append("")

    lines.append("## Declared, not verified")
    declared = report["declared_only"]
    lines.append(f"- declared_frozen_at: {declared['declared_frozen_at']}")
    lines.append(f"- holdout_status: {declared['holdout_status']}")
    lines.append(f"- {declared['note']}")
    ordering = report["ordering_evidence"]
    lines.append(f"- ordering_evidence: {ordering['state']} ({ordering['verification']})")
    if ordering["declared"] is not None:
        lines.append(
            f"  reviewer={ordering['declared']['reviewer_identity']} "
            f"source={ordering['declared']['source']}"
        )
    lines.append(f"- {ordering['authentication_note']}")
    lines.append("")

    lines.append("## Evidence")
    if not report["evidence"]:
        lines.append("- no raw evidence file was supplied for verification")
    for entry in report["evidence"]:
        lines.append(f"- {entry['digest']}: {entry['verification']} -> {', '.join(entry['bound_to'])}")
    lines.append("")

    lines.append("## Configurations")
    for summary in report["configuration_summaries"]:
        outcomes = summary["outcomes"]
        lines.append(
            f"- {summary['slot']}: runs={summary['runs_total']} "
            f"completed={outcomes['completed']} failed={outcomes['failed']} "
            f"timed_out={outcomes['timed_out']} model_unavailable={outcomes['model_unavailable']} "
            f"critical_violations={summary['critical_violations']}"
        )
        rate = summary["quality_pass_rate"]
        lines.append(
            f"  quality: {summary['quality_pass_count']}/{summary['quality_denominator']} "
            f"({'not_observed' if rate is None else rate})"
        )
        completed_timing = summary["elapsed_seconds_completed_runs"]
        all_timing = summary["elapsed_seconds_all_runs"]
        lines.append(
            "  elapsed_seconds: all_runs mean="
            f"{all_timing['mean'] if all_timing['mean'] is not None else 'not_observed'} "
            f"({all_timing['observation_count']}/{all_timing['denominator']}), "
            "completed_runs mean="
            f"{completed_timing['mean'] if completed_timing['mean'] is not None else 'not_observed'} "
            f"({completed_timing['observation_count']}/{completed_timing['denominator']})"
        )
        cost = summary["billed_cost"]
        lines.append(
            f"  billed_cost: {cost['status']} total="
            f"{cost['total'] if cost['total'] is not None else 'not_observed'} "
            f"currencies={cost['currencies'] or 'none'} "
            f"({cost['observation_count']}/{cost['denominator']})"
        )
        interventions = summary["human_interventions"]
        lines.append(
            f"  human_interventions: {interventions['status']} total="
            f"{interventions['total'] if interventions['total'] is not None else 'not_observed'} "
            f"({interventions['observation_count']}/{interventions['denominator']})"
        )
    lines.append("")

    lines.append("## Comparisons")
    if not report["comparisons"]:
        lines.append("- no comparable configuration pair is present")
    for comparison in report["comparisons"]:
        isolation = comparison["axis_isolation"]
        lines.append(
            f"- {comparison['comparison']} ({comparison['axis']} axis): "
            f"{isolation['kind']}"
        )
        if isolation["reason"]:
            lines.append(f"  reason: {isolation['reason']}")
        quality = comparison["quality_pass_rate"]
        lines.append(
            f"  quality_pass_rate: baseline={quality['baseline']} "
            f"candidate={quality['candidate']} delta={quality['delta']}"
        )
        lines.append(
            f"  elapsed_ratio_all_runs={comparison['elapsed_ratio_all_runs']} "
            f"billed_cost_ratio={comparison['billed_cost_ratio']} "
            f"intervention_delta={comparison['intervention_delta']}"
        )
        lines.append(
            f"  paired_cells={comparison['paired_cells']}/{comparison['expected_pairs']} "
            f"unpaired={comparison['unpaired_cells'] or 'none'}"
        )
        lines.append(
            "  critical_violations: baseline="
            f"{comparison['critical_violations']['baseline']} "
            f"candidate={comparison['critical_violations']['candidate']}"
        )
        lines.append(f"  evidence_blockers: {comparison['evidence_blockers'] or 'none'}")
        lines.append(f"  limit_failures: {comparison['limit_failures'] or 'none'}")
        lines.append(f"  recommendation: {comparison['recommendation']}")
    lines.append("")

    lines.append("## Never inferred")
    for name in report["never_inferred"]:
        lines.append(f"- {name}")
    lines.append("")

    lines.append("## Boundaries")
    for note in report["boundaries"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare paired local harness runs for one model or instruction change. "
            "The report is advisory; it is never acceptance or validation evidence."
        )
    )
    parser.add_argument("--protocol", required=True, metavar="PATH")
    parser.add_argument(
        "--observation",
        action="append",
        default=[],
        metavar="PATH",
        help="explicit local run observation record",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="PATH",
        help="explicit raw evidence file to hash and bind to a declared digest",
    )
    parser.add_argument(
        "--ordering-evidence",
        action="append",
        default=[],
        metavar="PATH",
        help="explicit independently reviewed ordering attestation file",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    supplied = [args.protocol] + list(args.observation) + list(args.evidence) + list(
        args.ordering_evidence
    )
    try:
        if len(supplied) > MAX_INPUT_FILES:
            raise ComparisonError(
                f"at most {MAX_INPUT_FILES} explicit input files are supported; "
                f"{len(supplied)} were supplied"
            )
        if not args.observation:
            raise ComparisonError("at least one run observation is required")
        protocol = parse_protocol(args.protocol)
        observations = load_observations(list(args.observation), protocol)
        evidence = verify_evidence(
            observations, protocol, list(args.evidence), list(args.ordering_evidence)
        )
        report = build_report(protocol, observations, evidence)
        if args.format == "json":
            rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        else:
            rendered = render_text(report)
        encoded = rendered.encode("utf-8")
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise ComparisonError(
                f"report exceeds the {MAX_OUTPUT_BYTES}-byte output bound; "
                "compare fewer records per invocation"
            )
    except ComparisonError as exc:
        print(f"compare-harness-runs failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
