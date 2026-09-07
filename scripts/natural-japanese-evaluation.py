#!/usr/bin/env python3
"""Validate the bounded offline natural-japanese evaluation record."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MAX_PROMPT_BYTES = 4096
MAX_OUTPUT_BYTES = 8192
CLASSES = {"median", "edge", "holdout"}
RESULT_VALUES = {"pass", "fail", "partial", "not_applicable"}
EVALUATED_CANDIDATE_PATHS = (
    ".codex/skills/natural-japanese/SKILL.md",
    ".codex/skills/natural-japanese/references/workflow.md",
    "docs/agent/SPEC_JAPANESE_TECH_WRITING.md",
)
EVENT_SEQUENCE = (
    "scenarios_frozen",
    "nonholdout_generated_and_compared",
    "candidate_fixed",
    "holdout_revealed",
    "holdout_generated_and_compared",
)


class EvaluationError(RuntimeError):
    """The evaluation packet is incomplete or inconsistent."""


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return digest_bytes(encoded)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationError(message)


def load_json(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f"{path} must contain one JSON object")
    return value, raw


def validate_scenarios(packet: dict[str, object]) -> tuple[dict[str, dict], dict[str, bool]]:
    require(packet.get("schema_version") == 1, "scenario schema_version must be 1")
    require(packet.get("frozen_before_generation") is True, "scenarios must be frozen")
    requirements = packet.get("requirements")
    scenarios = packet.get("scenarios")
    require(isinstance(requirements, list) and requirements, "requirements must be non-empty")
    require(isinstance(scenarios, list) and scenarios, "scenarios must be non-empty")

    critical: dict[str, bool] = {}
    for item in requirements:
        require(isinstance(item, dict), "requirement entries must be objects")
        identifier = item.get("id")
        require(isinstance(identifier, str) and identifier, "requirement id must be nonblank")
        require(identifier not in critical, f"duplicate requirement id: {identifier}")
        require(isinstance(item.get("description"), str), f"requirement description missing: {identifier}")
        critical[identifier] = item.get("critical") is True
    require(any(critical.values()), "at least one critical requirement is required")

    indexed: dict[str, dict] = {}
    classes: set[str] = set()
    for item in scenarios:
        require(isinstance(item, dict), "scenario entries must be objects")
        identifier = item.get("id")
        scenario_class = item.get("class")
        prompt = item.get("prompt")
        require(isinstance(identifier, str) and identifier, "scenario id must be nonblank")
        require(identifier not in indexed, f"duplicate scenario id: {identifier}")
        require(scenario_class in CLASSES, f"invalid scenario class: {identifier}")
        require(isinstance(prompt, str) and prompt, f"scenario prompt must be nonblank: {identifier}")
        require(len(prompt.encode("utf-8")) <= MAX_PROMPT_BYTES, f"scenario prompt too large: {identifier}")
        required = item.get("requirements")
        require(isinstance(required, list) and required, f"scenario requirements missing: {identifier}")
        require(set(required).issubset(critical), f"scenario has unknown requirement: {identifier}")
        expected_tuning = scenario_class != "holdout"
        require(item.get("used_for_tuning") is expected_tuning, f"tuning boundary mismatch: {identifier}")
        indexed[identifier] = item
        classes.add(scenario_class)
    require(classes == CLASSES, "scenarios must include median, edge, and holdout")
    holdouts = [item for item in scenarios if item["class"] == "holdout"]
    require(len(holdouts) == 1, "exactly one holdout scenario is required")
    return indexed, critical


def validate_run(
    run: dict[str, object],
    scenario: dict[str, object],
    critical: dict[str, bool],
    label: str,
) -> None:
    required_keys = {
        "model",
        "session_id",
        "output",
        "output_sha256",
        "requirement_results",
        "unclear_points",
        "discretionary_assumptions",
        "retry_count",
        "tool_time_notes",
    }
    require(set(run) == required_keys, f"{label} run fields differ from the schema")
    for key in ("model", "session_id", "output", "tool_time_notes"):
        require(isinstance(run[key], str) and run[key], f"{label} {key} must be nonblank")
    output = run["output"]
    require(len(output.encode("utf-8")) <= MAX_OUTPUT_BYTES, f"{label} output exceeds byte bound")
    require(run["output_sha256"] == digest_bytes(output.encode("utf-8")), f"{label} output digest mismatch")
    require(isinstance(run["unclear_points"], list), f"{label} unclear_points must be a list")
    require(isinstance(run["discretionary_assumptions"], list), f"{label} assumptions must be a list")
    require(isinstance(run["retry_count"], int) and run["retry_count"] >= 0, f"{label} retry_count is invalid")

    results = run["requirement_results"]
    require(isinstance(results, dict), f"{label} requirement_results must be an object")
    require(set(results) == set(scenario["requirements"]), f"{label} requirement coverage mismatch")
    for identifier, result in results.items():
        require(result in RESULT_VALUES, f"{label} invalid result for {identifier}")
        if critical[identifier] and result != "pass":
            raise EvaluationError(f"{label} critical requirement did not pass: {identifier}")


def validate_results(
    packet: dict[str, object],
    scenario_bytes: bytes,
    evaluator_prompt_bytes: bytes,
    scenarios: dict[str, dict],
    critical: dict[str, bool],
) -> None:
    require(
        set(packet)
        == {
            "schema_version",
            "scenario_file_sha256",
            "evaluator_prompt_sha256",
            "evaluated_candidate_files",
            "event_sequence",
            "candidate_fixed_before_holdout",
            "records",
        },
        "result packet fields differ from the schema",
    )
    require(packet.get("schema_version") == 1, "result schema_version must be 1")
    require(packet.get("scenario_file_sha256") == digest_bytes(scenario_bytes), "scenario file digest mismatch")
    require(
        packet.get("evaluator_prompt_sha256") == digest_bytes(evaluator_prompt_bytes),
        "evaluator prompt digest mismatch",
    )
    candidate_files = packet.get("evaluated_candidate_files")
    require(
        isinstance(candidate_files, dict)
        and set(candidate_files) == set(EVALUATED_CANDIDATE_PATHS),
        "evaluated candidate file set mismatch",
    )
    for path in EVALUATED_CANDIDATE_PATHS:
        require(
            candidate_files[path] == digest_bytes(Path(path).read_bytes()),
            f"evaluated candidate digest mismatch: {path}",
        )
    require(
        packet.get("event_sequence") == list(EVENT_SEQUENCE),
        "evaluation event sequence is incomplete or out of order",
    )
    require(packet.get("candidate_fixed_before_holdout") is True, "candidate must be fixed before holdout")
    records = packet.get("records")
    require(isinstance(records, list), "records must be a list")
    require(len(records) == len(scenarios), "every scenario must have one record")

    observed: set[str] = set()
    for record in records:
        require(isinstance(record, dict), "record entries must be objects")
        required_keys = {
            "scenario_id",
            "scenario_sha256",
            "baseline",
            "adapted",
            "comparison",
            "holdout_revealed_after_candidate_fixed",
        }
        require(set(record) == required_keys, "record fields differ from the schema")
        scenario_id = record["scenario_id"]
        require(scenario_id in scenarios, f"unknown scenario result: {scenario_id}")
        require(scenario_id not in observed, f"duplicate scenario result: {scenario_id}")
        observed.add(scenario_id)
        scenario = scenarios[scenario_id]
        require(record["scenario_sha256"] == digest_json(scenario), f"scenario digest mismatch: {scenario_id}")
        baseline = record["baseline"]
        adapted = record["adapted"]
        require(isinstance(baseline, dict) and isinstance(adapted, dict), f"run records missing: {scenario_id}")
        validate_run(baseline, scenario, critical, f"{scenario_id} baseline")
        validate_run(adapted, scenario, critical, f"{scenario_id} adapted")
        require(baseline["model"] == adapted["model"], f"cross-model comparison is forbidden: {scenario_id}")
        require(baseline["session_id"] != adapted["session_id"], f"baseline and adapted sessions must differ: {scenario_id}")

        comparison = record["comparison"]
        require(isinstance(comparison, dict), f"comparison missing: {scenario_id}")
        require(
            set(comparison)
            == {
                "evaluator",
                "evaluator_session_id",
                "verdict",
                "fact_drift",
                "quote_drift",
                "uncertainty_drift",
                "code_block_drift",
                "requested_format_drift",
                "project_term_drift",
                "material_regression",
                "unclear_points",
                "discretionary_assumptions",
                "retry_count",
                "tool_time_notes",
                "notes",
            },
            f"comparison fields differ from the schema: {scenario_id}",
        )
        for key in ("evaluator", "evaluator_session_id", "tool_time_notes", "notes"):
            require(
                isinstance(comparison[key], str) and comparison[key],
                f"{scenario_id} comparison {key} must be nonblank",
            )
        require(
            isinstance(comparison["unclear_points"], list)
            and all(isinstance(item, str) for item in comparison["unclear_points"]),
            f"{scenario_id} comparison unclear_points must be a string list",
        )
        require(
            isinstance(comparison["discretionary_assumptions"], list)
            and all(
                isinstance(item, str)
                for item in comparison["discretionary_assumptions"]
            ),
            f"{scenario_id} comparison assumptions must be a string list",
        )
        require(
            isinstance(comparison["retry_count"], int)
            and not isinstance(comparison["retry_count"], bool)
            and comparison["retry_count"] >= 0,
            f"{scenario_id} comparison retry_count is invalid",
        )
        require(comparison["evaluator_session_id"] not in {baseline["session_id"], adapted["session_id"]}, f"comparison must be independent: {scenario_id}")
        require(comparison["verdict"] in {"adapted_better", "equivalent"}, f"adapted output is worse: {scenario_id}")
        for drift in (
            "fact_drift",
            "quote_drift",
            "uncertainty_drift",
            "code_block_drift",
            "requested_format_drift",
            "project_term_drift",
            "material_regression",
        ):
            require(comparison[drift] is False, f"{scenario_id} reports {drift}")
        is_holdout = scenario["class"] == "holdout"
        require(
            record["holdout_revealed_after_candidate_fixed"] is is_holdout,
            f"holdout reveal boundary mismatch: {scenario_id}",
        )
    require(observed == set(scenarios), "scenario result set mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("tests/fixtures/natural-japanese/scenarios.json"),
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("tests/fixtures/natural-japanese/evaluation-results.json"),
    )
    parser.add_argument(
        "--evaluator-prompt",
        type=Path,
        default=Path("tests/fixtures/natural-japanese/evaluator-prompt.md"),
    )
    args = parser.parse_args()
    try:
        scenario_packet, scenario_bytes = load_json(args.scenarios)
        result_packet, _ = load_json(args.results)
        evaluator_prompt_bytes = args.evaluator_prompt.read_bytes()
        scenarios, critical = validate_scenarios(scenario_packet)
        validate_results(
            result_packet,
            scenario_bytes,
            evaluator_prompt_bytes,
            scenarios,
            critical,
        )
    except (OSError, json.JSONDecodeError, EvaluationError) as exc:
        print(f"natural-japanese evaluation failed: {exc}")
        return 1
    print("natural-japanese evaluation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
