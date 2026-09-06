#!/usr/bin/env python3
"""Deterministic tests for the Bubblewrap sandboxed plan worker."""

from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run-sandboxed-plan-worker.py"
ENV_PREFIX = "SANDBOXED_PLAN_WORKER_"
TEMPLATE_SCRIPT = ROOT / "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
WORKER_CONTRACT_SCENARIOS = ROOT / "tests/fixtures/orchestration/worker-contract-scenarios.json"
WORKER_CONTRACT_HOLDOUT = ROOT / "tests/fixtures/orchestration/worker-contract-holdout.json"
WORKER_CONTRACT_SCENARIOS_SHA256 = "ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf"
WORKER_CONTRACT_HOLDOUT_SHA256 = "a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27"
WORKER_CONTRACT_COVERAGE = {
    "exact_derivation",
    "lineage_binding",
    "explicit_new_non_authority_path",
    "source_plan_mutation",
    "digest_mismatch",
    "lineage_mismatch",
    "missing_primary_invariant",
    "duplicate_field",
    "unknown_field",
    "path_traversal",
    "symlink_escape",
    "oversized_input",
    "contract_mutation",
    "read_only_mount",
    "authority_widening",
    "directory_prefix_scope",
}
WORKER_CONTRACT_HOLDOUT_COVERAGE = {
    "authority_widening",
    "explicit_new_path",
    "missing_parent_path",
}
WORKER_COMPLETION_RECEIPT_SCENARIOS = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-scenarios.json"
WORKER_COMPLETION_RECEIPT_HOLDOUT = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-holdout.json"
WORKER_COMPLETION_RECEIPT_REPLACEMENT_HOLDOUT = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-holdout-v2.json"
WORKER_COMPLETION_RECEIPT_EVIDENCE = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-evidence.json"
WORKER_COMPLETION_RECEIPT_SCENARIOS_SHA256 = "264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a"
WORKER_COMPLETION_RECEIPT_HOLDOUT_SHA256 = "4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76"
WORKER_COMPLETION_RECEIPT_REPLACEMENT_HOLDOUT_SHA256 = "ddbbedb5c65cfe16ae48763b403c1beb16c241b7a77ab9379a88f98c8dd0f8de"
WORKER_COMPLETION_RECEIPT_COVERAGE = {
    "successful_attempt",
    "failed_attempt",
    "initial_attempt",
    "correction_attempt",
    "failure_before_candidate",
    "partial_command_execution",
    "stale_receipt",
    "replayed_receipt",
    "plan_mismatch",
    "contract_mismatch",
    "patch_mismatch",
    "changed_path_mismatch",
    "false_success_claim",
    "missing_out_of_scope_declaration",
    "unknown_field",
    "duplicate_field",
    "oversized_receipt",
    "oversized_value",
    "path_traversal",
    "symlink_escape",
    "secret_inclusion",
    "raw_output_inclusion",
}
WORKER_COMPLETION_RECEIPT_HOLDOUT_COVERAGE = {
    "host_path_inclusion",
    "raw_output_inclusion",
    "residual_risk_bound",
}


def require_fixture_lineage(value: object, *, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"worker-contract lineage is not an object: {label}")
    kind = value.get("attempt_kind")
    required = {"attempt_kind", "correction_round", "attempt_label"}
    if kind == "correction":
        required.add("prior_manifest_digest")
    if set(value) != required:
        raise ValueError(f"worker-contract lineage has an invalid exact shape: {label}")
    if kind not in {"initial", "correction"}:
        raise ValueError(f"worker-contract lineage kind is invalid: {label}")
    if isinstance(value["correction_round"], bool) or not isinstance(value["correction_round"], int) or value["correction_round"] < 0:
        raise ValueError(f"worker-contract correction round is invalid: {label}")
    if not isinstance(value["attempt_label"], str) or not value["attempt_label"]:
        raise ValueError(f"worker-contract attempt label is invalid: {label}")
    if kind == "initial" and value["correction_round"] != 0:
        raise ValueError(f"worker-contract initial lineage has a correction round: {label}")
    if kind == "correction":
        digest = value["prior_manifest_digest"]
        if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
            raise ValueError(f"worker-contract prior manifest digest is invalid: {label}")


def require_fixture_string_map(value: object, *, label: str) -> None:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"worker-contract string map is empty: {label}")
    if any(not isinstance(key, str) or not key or not isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"worker-contract string map is invalid: {label}")


def require_fixture_string_list(value: object, *, label: str) -> None:
    if not isinstance(value, list) or not value or len(value) != len(set(value)):
        raise ValueError(f"worker-contract string list is invalid: {label}")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"worker-contract string list item is invalid: {label}")


def require_worker_contract_case_input(operation: str, value: object, *, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"worker-contract input is not an object: {label}")
    if operation == "derive_twice":
        if set(value) not in (set(), {"attempt_lineage"}):
            raise ValueError(f"derive_twice input has an invalid exact shape: {label}")
        if "attempt_lineage" in value:
            require_fixture_lineage(value["attempt_lineage"], label=label)
        return
    if operation == "validate_write_scope":
        if set(value) != {"write_scope"}:
            raise ValueError(f"validate_write_scope input has an invalid exact shape: {label}")
        require_fixture_string_list(value["write_scope"], label=label)
        return
    if operation == "derive_after_plan_mutation":
        if set(value) != {"append_to_plan"} or not isinstance(value["append_to_plan"], str) or not value["append_to_plan"]:
            raise ValueError(f"plan mutation input has an invalid exact shape: {label}")
        return
    if operation == "verify_contract_mutation":
        if set(value) != {"mutation"} or not isinstance(value["mutation"], dict):
            raise ValueError(f"contract mutation input has an invalid exact shape: {label}")
        mutation = value["mutation"]
        kind = mutation.get("kind")
        expected_keys = {
            "manifest_digest": {"kind", "value"},
            "attempt_lineage": {"kind", "value"},
            "add_field": {"kind", "name", "value"},
        }.get(kind)
        if expected_keys is None or set(mutation) != expected_keys:
            raise ValueError(f"contract mutation has an invalid exact shape: {label}")
        if kind == "manifest_digest":
            digest = mutation["value"]
            if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
                raise ValueError(f"contract mutation digest is invalid: {label}")
        elif kind == "attempt_lineage":
            require_fixture_lineage(mutation["value"], label=label)
        elif not isinstance(mutation["name"], str) or not mutation["name"]:
            raise ValueError(f"contract mutation field name is invalid: {label}")
        return
    if operation == "derive_with_plan_replacement":
        if set(value) == {"remove_line_prefix"}:
            if not isinstance(value["remove_line_prefix"], str) or not value["remove_line_prefix"]:
                raise ValueError(f"plan replacement prefix is invalid: {label}")
            return
        if set(value) == {"replace_write_scope"}:
            require_fixture_string_list(value["replace_write_scope"], label=label)
            return
        raise ValueError(f"plan replacement input has an invalid exact shape: {label}")
    if operation == "verify_serialized_contract":
        if set(value) == {"json_prefix"}:
            if not isinstance(value["json_prefix"], str) or not value["json_prefix"]:
                raise ValueError(f"serialized contract prefix is invalid: {label}")
            return
        if set(value) == {"byte_count", "fill_byte"}:
            if isinstance(value["byte_count"], bool) or not isinstance(value["byte_count"], int) or value["byte_count"] <= 0:
                raise ValueError(f"serialized contract byte count is invalid: {label}")
            if not isinstance(value["fill_byte"], str) or len(value["fill_byte"].encode("utf-8")) != 1:
                raise ValueError(f"serialized contract fill byte is invalid: {label}")
            return
        raise ValueError(f"serialized contract input has an invalid exact shape: {label}")
    if operation == "derive_with_repository_mutation":
        if set(value) != {"replace_with_symlink"} or not isinstance(value["replace_with_symlink"], dict):
            raise ValueError(f"repository mutation input has an invalid exact shape: {label}")
        symlink = value["replace_with_symlink"]
        if set(symlink) != {"path", "target"} or any(not isinstance(symlink[key], str) or not symlink[key] for key in symlink):
            raise ValueError(f"repository symlink mutation is invalid: {label}")
        return
    if operation == "attempt_worker_write":
        if set(value) != {"target", "content"} or any(not isinstance(value[key], str) or not value[key] for key in value):
            raise ValueError(f"worker write input has an invalid exact shape: {label}")
        return
    raise ValueError(f"worker-contract operation is unsupported: {operation}")


def load_worker_contract_fixture(path: Path, *, used_for_tuning: bool) -> dict[str, object]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    required_top = {"schema_version", "suite", "used_for_tuning", "base", "cases"}
    if used_for_tuning:
        required_top.add("holdout_file")
    if not isinstance(fixture, dict) or set(fixture) != required_top:
        raise ValueError(f"worker-contract fixture has an invalid exact shape: {path.name}")
    if fixture["schema_version"] != 1 or fixture["suite"] != "worker-execution-contract":
        raise ValueError(f"worker-contract fixture has an unsupported identity: {path.name}")
    if fixture["used_for_tuning"] is not used_for_tuning:
        raise ValueError(f"worker-contract fixture tuning flag differs: {path.name}")
    base = fixture["base"]
    if not isinstance(base, dict) or set(base) != {
        "plan_path", "plan_bytes", "repository_files", "orchestration_run_id", "attempt_lineage"
    }:
        raise ValueError(f"worker-contract fixture base has an invalid exact shape: {path.name}")
    if not all(isinstance(base[key], str) and base[key] for key in ("plan_path", "plan_bytes", "orchestration_run_id")):
        raise ValueError(f"worker-contract fixture base has an invalid scalar: {path.name}")
    require_fixture_string_map(base["repository_files"], label=path.name)
    require_fixture_lineage(base["attempt_lineage"], label=path.name)
    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"worker-contract fixture cases are empty: {path.name}")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "id", "class", "used_for_tuning", "covers", "operation", "input", "expected"
        }:
            raise ValueError(f"worker-contract case has an invalid exact shape: {path.name}")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"worker-contract case identifier is invalid: {path.name}")
        seen.add(case_id)
        expected_class = "holdout" if not used_for_tuning else case["class"]
        if expected_class not in {"median", "edge", "negative", "holdout"}:
            raise ValueError(f"worker-contract case class is invalid: {case_id}")
        if not used_for_tuning and case["class"] != "holdout":
            raise ValueError(f"worker-contract holdout class differs: {case_id}")
        if case["used_for_tuning"] is not used_for_tuning:
            raise ValueError(f"worker-contract case tuning flag differs: {case_id}")
        covers = case["covers"]
        require_fixture_string_list(covers, label=case_id)
        allowed_coverage = WORKER_CONTRACT_COVERAGE if used_for_tuning else WORKER_CONTRACT_HOLDOUT_COVERAGE
        if any(marker not in allowed_coverage for marker in covers):
            raise ValueError(f"worker-contract coverage marker is unknown: {case_id}")
        operation = case["operation"]
        if not isinstance(operation, str) or not operation:
            raise ValueError(f"worker-contract operation is invalid: {case_id}")
        require_worker_contract_case_input(operation, case["input"], label=case_id)
        expected = case["expected"]
        if not isinstance(expected, dict) or set(expected) != {"result", "error_code"}:
            raise ValueError(f"worker-contract expected outcome is invalid: {case_id}")
        if expected["result"] not in {"accepted", "rejected"}:
            raise ValueError(f"worker-contract expected result is invalid: {case_id}")
        if (expected["result"] == "accepted") != (expected["error_code"] is None):
            raise ValueError(f"worker-contract error code is inconsistent: {case_id}")
        if expected["error_code"] is not None and (not isinstance(expected["error_code"], str) or not expected["error_code"]):
            raise ValueError(f"worker-contract error code is invalid: {case_id}")
    return fixture


def evaluate_worker_contract_fixture(
    path: Path,
    evaluator,
    *,
    used_for_tuning: bool,
) -> list[dict[str, object]]:
    """Evaluate only the caller-selected fixture and compare exact observed outcomes."""
    fixture = load_worker_contract_fixture(path, used_for_tuning=used_for_tuning)
    observations: list[dict[str, object]] = []
    for case in fixture["cases"]:
        observed = evaluator(fixture["base"], case)
        if observed != case["expected"]:
            raise AssertionError(
                f"worker-contract scenario {case['id']} observed {observed!r}, expected {case['expected']!r}"
            )
        observations.append({"id": case["id"], "observed": observed})
    return observations


def require_receipt_fixture_digest(value: object, *, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise ValueError(f"worker-completion-receipt digest is invalid: {label}")


def require_receipt_fixture_string_list(
    value: object, *, label: str, allow_empty: bool = True
) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"worker-completion-receipt string list is invalid: {label}")
    if len(value) != len(set(value)):
        raise ValueError(f"worker-completion-receipt string list has duplicates: {label}")
    if not allow_empty and not value:
        raise ValueError(f"worker-completion-receipt string list is empty: {label}")


def require_receipt_fixture_attempt(value: object, *, label: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "attempt_id", "attempt_kind", "correction_round", "correction_lineage"
    }:
        raise ValueError(f"worker-completion-receipt attempt shape is invalid: {label}")
    if not isinstance(value["attempt_id"], str) or not value["attempt_id"]:
        raise ValueError(f"worker-completion-receipt attempt id is invalid: {label}")
    if value["attempt_kind"] not in {"initial", "correction"}:
        raise ValueError(f"worker-completion-receipt attempt kind is invalid: {label}")
    round_value = value["correction_round"]
    if isinstance(round_value, bool) or not isinstance(round_value, int) or round_value < 0:
        raise ValueError(f"worker-completion-receipt correction round is invalid: {label}")
    lineage = value["correction_lineage"]
    if value["attempt_kind"] == "initial":
        if round_value != 0 or lineage is not None:
            raise ValueError(f"worker-completion-receipt initial lineage is invalid: {label}")
        return
    if round_value < 1 or not isinstance(lineage, dict) or set(lineage) != {"prior_manifest_digest"}:
        raise ValueError(f"worker-completion-receipt correction lineage is invalid: {label}")
    require_receipt_fixture_digest(lineage["prior_manifest_digest"], label=label)


def require_receipt_fixture_candidate(value: object, *, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"patch_digest", "changed_paths"}:
        raise ValueError(f"worker-completion-receipt candidate shape is invalid: {label}")
    require_receipt_fixture_digest(value["patch_digest"], label=label)
    require_receipt_fixture_string_list(value["changed_paths"], label=label, allow_empty=False)


def require_receipt_fixture_process(value: object, *, label: str) -> None:
    if not isinstance(value, dict) or set(value) != {"exit_status", "diagnostic_codes"}:
        raise ValueError(f"worker-completion-receipt process shape is invalid: {label}")
    if isinstance(value["exit_status"], bool) or not isinstance(value["exit_status"], int):
        raise ValueError(f"worker-completion-receipt process status is invalid: {label}")
    require_receipt_fixture_string_list(value["diagnostic_codes"], label=label)


def require_receipt_fixture_claims(value: object, *, label: str) -> None:
    required = {
        "attempt_result", "acceptance_evidence", "commands_attempted", "blockers",
        "residual_risks", "out_of_scope_change",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"worker-completion-receipt claims shape is invalid: {label}")
    if value["attempt_result"] not in {"success", "failure"}:
        raise ValueError(f"worker-completion-receipt attempt result is invalid: {label}")
    evidence = value["acceptance_evidence"]
    if not isinstance(evidence, list):
        raise ValueError(f"worker-completion-receipt evidence list is invalid: {label}")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"acceptance_digest", "claim"}:
            raise ValueError(f"worker-completion-receipt evidence item is invalid: {label}")
        require_receipt_fixture_digest(item["acceptance_digest"], label=label)
        if item["claim"] not in {"satisfied", "not_satisfied"}:
            raise ValueError(f"worker-completion-receipt evidence claim is invalid: {label}")
    commands = value["commands_attempted"]
    if not isinstance(commands, list):
        raise ValueError(f"worker-completion-receipt commands list is invalid: {label}")
    for item in commands:
        if not isinstance(item, dict) or set(item) != {"command_id", "exit_status"}:
            raise ValueError(f"worker-completion-receipt command item is invalid: {label}")
        if not isinstance(item["command_id"], str) or not item["command_id"]:
            raise ValueError(f"worker-completion-receipt command id is invalid: {label}")
        if isinstance(item["exit_status"], bool) or not isinstance(item["exit_status"], int):
            raise ValueError(f"worker-completion-receipt command status is invalid: {label}")
    require_receipt_fixture_string_list(value["blockers"], label=label)
    require_receipt_fixture_string_list(value["residual_risks"], label=label)
    if not isinstance(value["out_of_scope_change"], bool):
        raise ValueError(f"worker-completion-receipt out-of-scope declaration is invalid: {label}")


def require_worker_completion_receipt_case_input(
    operation: str, value: object, *, label: str
) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"worker-completion-receipt input is not an object: {label}")
    if operation == "derive_twice":
        if value:
            raise ValueError(f"derive_twice input is not empty: {label}")
        return
    if operation == "derive_failure_before_candidate":
        if set(value) != {"exit_status", "diagnostic_codes"}:
            raise ValueError(f"failure-before-candidate input shape is invalid: {label}")
        require_receipt_fixture_process(value, label=label)
        return
    if operation == "derive_correction_failure":
        if set(value) != {"attempt_id", "correction_round", "prior_manifest_digest", "exit_status"}:
            raise ValueError(f"correction failure input shape is invalid: {label}")
        if not isinstance(value["attempt_id"], str) or not value["attempt_id"]:
            raise ValueError(f"correction attempt id is invalid: {label}")
        if isinstance(value["correction_round"], bool) or not isinstance(value["correction_round"], int) or value["correction_round"] < 1:
            raise ValueError(f"correction round is invalid: {label}")
        require_receipt_fixture_digest(value["prior_manifest_digest"], label=label)
        if isinstance(value["exit_status"], bool) or not isinstance(value["exit_status"], int):
            raise ValueError(f"correction exit status is invalid: {label}")
        return
    if operation == "derive_correction_success":
        if set(value) != {
            "attempt_id", "correction_round", "prior_manifest_digest", "patch_digest",
            "changed_paths",
        }:
            raise ValueError(f"successful correction input shape is invalid: {label}")
        if not isinstance(value["attempt_id"], str) or not value["attempt_id"]:
            raise ValueError(f"successful correction attempt id is invalid: {label}")
        if isinstance(value["correction_round"], bool) or not isinstance(value["correction_round"], int) or value["correction_round"] < 1:
            raise ValueError(f"successful correction round is invalid: {label}")
        require_receipt_fixture_digest(value["prior_manifest_digest"], label=label)
        require_receipt_fixture_digest(value["patch_digest"], label=label)
        require_receipt_fixture_string_list(value["changed_paths"], label=label, allow_empty=False)
        return
    if operation == "derive_partial_commands":
        if set(value) != {"commands_attempted", "blockers", "exit_status"}:
            raise ValueError(f"partial-command input shape is invalid: {label}")
        require_receipt_fixture_claims(
            {
                "attempt_result": "failure",
                "acceptance_evidence": [],
                "commands_attempted": value["commands_attempted"],
                "blockers": value["blockers"],
                "residual_risks": [],
                "out_of_scope_change": False,
            },
            label=label,
        )
        if isinstance(value["exit_status"], bool) or not isinstance(value["exit_status"], int):
            raise ValueError(f"partial-command exit status is invalid: {label}")
        return
    if operation == "verify_identity_mismatch":
        if set(value) != {"field", "value"} or value["field"] not in {
            "source_head", "plan_digest", "worker_contract_digest"
        } or not isinstance(value["value"], str) or not value["value"]:
            raise ValueError(f"identity mismatch input shape is invalid: {label}")
        return
    if operation == "verify_replay":
        if set(value) != {"consumed_attempt_id"} or not isinstance(value["consumed_attempt_id"], str) or not value["consumed_attempt_id"]:
            raise ValueError(f"receipt replay input shape is invalid: {label}")
        return
    if operation == "verify_candidate_mismatch":
        if set(value) != {"field", "value"} or value["field"] not in {"patch_digest", "changed_paths"}:
            raise ValueError(f"candidate mismatch input shape is invalid: {label}")
        if value["field"] == "patch_digest":
            require_receipt_fixture_digest(value["value"], label=label)
        else:
            require_receipt_fixture_string_list(value["value"], label=label, allow_empty=False)
        return
    if operation == "verify_false_success":
        if set(value) != {"process_exit_status", "attempt_result"} or value["attempt_result"] != "success":
            raise ValueError(f"false-success input shape is invalid: {label}")
        if isinstance(value["process_exit_status"], bool) or not isinstance(value["process_exit_status"], int):
            raise ValueError(f"false-success process status is invalid: {label}")
        return
    if operation == "verify_receipt_mutation":
        if set(value) != {"mutation"} or not isinstance(value["mutation"], dict):
            raise ValueError(f"receipt mutation input shape is invalid: {label}")
        mutation = value["mutation"]
        kind = mutation.get("kind")
        expected_keys = {
            "remove_claim_field": {"kind", "name"},
            "add_top_field": {"kind", "name", "value"},
            "oversized_claim_value": {"kind", "field", "byte_count"},
        }.get(kind)
        if expected_keys is None or set(mutation) != expected_keys:
            raise ValueError(f"receipt mutation shape is invalid: {label}")
        if kind == "remove_claim_field" and mutation["name"] != "out_of_scope_change":
            raise ValueError(f"receipt removed field is invalid: {label}")
        if kind == "add_top_field" and (not isinstance(mutation["name"], str) or not mutation["name"]):
            raise ValueError(f"receipt added field is invalid: {label}")
        if kind == "oversized_claim_value" and (
            mutation["field"] not in {"blockers", "residual_risks"}
            or isinstance(mutation["byte_count"], bool)
            or not isinstance(mutation["byte_count"], int)
            or mutation["byte_count"] <= 0
        ):
            raise ValueError(f"receipt oversized value input is invalid: {label}")
        return
    if operation == "verify_serialized_receipt":
        if set(value) == {"json_prefix"} and isinstance(value["json_prefix"], str) and value["json_prefix"]:
            return
        if set(value) == {"byte_count", "fill_byte"}:
            if isinstance(value["byte_count"], bool) or not isinstance(value["byte_count"], int) or value["byte_count"] <= 0:
                raise ValueError(f"receipt byte count is invalid: {label}")
            if not isinstance(value["fill_byte"], str) or len(value["fill_byte"].encode()) != 1:
                raise ValueError(f"receipt fill byte is invalid: {label}")
            return
        raise ValueError(f"serialized receipt input shape is invalid: {label}")
    if operation == "verify_output_path":
        if set(value) not in ({"path"}, {"path", "symlink_target"}) or any(
            not isinstance(item, str) or not item for item in value.values()
        ):
            raise ValueError(f"receipt output path input is invalid: {label}")
        return
    if operation == "verify_prohibited_content":
        if set(value) != {"field", "value"} or value["field"] not in {"blockers", "residual_risks"}:
            raise ValueError(f"prohibited content input shape is invalid: {label}")
        if not isinstance(value["value"], str) or not value["value"]:
            raise ValueError(f"prohibited content sentinel is invalid: {label}")
        return
    raise ValueError(f"worker-completion-receipt operation is unsupported: {operation}")


def load_worker_completion_receipt_fixture(
    path: Path, *, used_for_tuning: bool
) -> dict[str, object]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    required_top = {"schema_version", "suite", "used_for_tuning", "base", "cases"}
    if used_for_tuning:
        required_top.add("holdout_file")
    if not isinstance(fixture, dict) or set(fixture) != required_top:
        raise ValueError(f"worker-completion-receipt fixture has an invalid exact shape: {path.name}")
    if fixture["schema_version"] != 1 or fixture["suite"] != "worker-completion-receipt":
        raise ValueError(f"worker-completion-receipt fixture has an unsupported identity: {path.name}")
    if fixture["used_for_tuning"] is not used_for_tuning:
        raise ValueError(f"worker-completion-receipt tuning flag differs: {path.name}")
    base = fixture["base"]
    required_base = {
        "receipt_relative_path", "repository_identity", "source_head", "plan_path",
        "plan_digest", "worker_contract_digest", "orchestration_run_id", "attempt",
        "candidate", "process", "claims",
    }
    if not isinstance(base, dict) or set(base) != required_base:
        raise ValueError(f"worker-completion-receipt base has an invalid exact shape: {path.name}")
    for field in ("receipt_relative_path", "plan_path", "orchestration_run_id"):
        if not isinstance(base[field], str) or not base[field]:
            raise ValueError(f"worker-completion-receipt base scalar is invalid: {path.name}")
    for field in ("repository_identity", "plan_digest", "worker_contract_digest"):
        require_receipt_fixture_digest(base[field], label=path.name)
    if not isinstance(base["source_head"], str) or len(base["source_head"]) != 40 or any(
        char not in "0123456789abcdef" for char in base["source_head"]
    ):
        raise ValueError(f"worker-completion-receipt source head is invalid: {path.name}")
    require_receipt_fixture_attempt(base["attempt"], label=path.name)
    require_receipt_fixture_candidate(base["candidate"], label=path.name)
    require_receipt_fixture_process(base["process"], label=path.name)
    require_receipt_fixture_claims(base["claims"], label=path.name)
    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"worker-completion-receipt cases are empty: {path.name}")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "id", "class", "used_for_tuning", "covers", "operation", "input", "expected"
        }:
            raise ValueError(f"worker-completion-receipt case has an invalid exact shape: {path.name}")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"worker-completion-receipt case id is invalid: {path.name}")
        seen.add(case_id)
        if used_for_tuning:
            if case["class"] not in {"median", "edge", "negative"}:
                raise ValueError(f"worker-completion-receipt case class is invalid: {case_id}")
        elif case["class"] != "holdout":
            raise ValueError(f"worker-completion-receipt holdout class differs: {case_id}")
        if case["used_for_tuning"] is not used_for_tuning:
            raise ValueError(f"worker-completion-receipt case tuning flag differs: {case_id}")
        require_receipt_fixture_string_list(case["covers"], label=case_id, allow_empty=False)
        allowed_coverage = (
            WORKER_COMPLETION_RECEIPT_COVERAGE
            if used_for_tuning
            else WORKER_COMPLETION_RECEIPT_HOLDOUT_COVERAGE
        )
        if any(marker not in allowed_coverage for marker in case["covers"]):
            raise ValueError(f"worker-completion-receipt coverage marker is unknown: {case_id}")
        if not isinstance(case["operation"], str) or not case["operation"]:
            raise ValueError(f"worker-completion-receipt operation is invalid: {case_id}")
        require_worker_completion_receipt_case_input(
            case["operation"], case["input"], label=case_id
        )
        expected = case["expected"]
        if not isinstance(expected, dict) or set(expected) != {"result", "error_code"}:
            raise ValueError(f"worker-completion-receipt expected shape is invalid: {case_id}")
        if expected["result"] not in {"accepted", "rejected"}:
            raise ValueError(f"worker-completion-receipt expected result is invalid: {case_id}")
        if (expected["result"] == "accepted") != (expected["error_code"] is None):
            raise ValueError(f"worker-completion-receipt error code is inconsistent: {case_id}")
        if expected["error_code"] is not None and (
            not isinstance(expected["error_code"], str) or not expected["error_code"]
        ):
            raise ValueError(f"worker-completion-receipt error code is invalid: {case_id}")
    return fixture


def evaluate_worker_completion_receipt_fixture(
    path: Path,
    evaluator,
    *,
    used_for_tuning: bool,
) -> list[dict[str, object]]:
    """Evaluate only the caller-selected receipt fixture and compare exact outcomes."""
    fixture = load_worker_completion_receipt_fixture(path, used_for_tuning=used_for_tuning)
    observations: list[dict[str, object]] = []
    for case in fixture["cases"]:
        observed = evaluator(fixture["base"], case)
        if observed != case["expected"]:
            raise AssertionError(
                f"worker-completion-receipt scenario {case['id']} observed {observed!r}, expected {case['expected']!r}"
            )
        observations.append({"id": case["id"], "observed": observed})
    return observations


def load_runner_module():
    spec = importlib.util.spec_from_file_location("sandboxed_plan_worker", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import runner module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner_module()


def run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    child_env = dict(os.environ)
    if env:
        child_env.update(env)
    command_args = list(args)
    operations = {"run", "correct", "validate", "apply", "finalize-apply"}
    manifest_path = None
    if command_args and command_args[0] in operations:
        if command_args[0] == "correct" and len(command_args) >= 3:
            manifest_path = Path(command_args[2])
        elif command_args[0] in {"validate", "apply", "finalize-apply"} and len(command_args) >= 2:
            manifest_path = Path(command_args[1])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path and manifest_path.is_file() else None
        if "--lifecycle-state" not in command_args:
            if manifest:
                lifecycle_path = manifest["lifecycle_state_path"]
                run_id = manifest["orchestration_run_id"]
            else:
                output_path = (
                    Path(command_args[command_args.index("--output-dir") + 1]).absolute()
                    if "--output-dir" in command_args
                    else Path(tempfile.mkdtemp(prefix="test-lifecycle-")) / "output"
                )
                lifecycle_path = str(output_path.with_name(output_path.name + ".lifecycle.json"))
                run_id = hashlib.sha256(lifecycle_path.encode()).hexdigest()[:24]
            command_args.extend(["--lifecycle-state", lifecycle_path])
            if "--orchestration-run-id" not in command_args:
                command_args.extend(["--orchestration-run-id", run_id])
        lifecycle_path = command_args[command_args.index("--lifecycle-state") + 1]
        run_id = command_args[command_args.index("--orchestration-run-id") + 1]
        if "--plan-execution-state" not in command_args:
            execution_state = str(Path(lifecycle_path).with_name(Path(lifecycle_path).name + f".{run_id}.plan-execution.json"))
            plan_rel = manifest["plan_path"] if manifest else command_args[1]
            plan_file = repo / plan_rel
            if not Path(execution_state).exists():
                plan_text = plan_file.read_text(encoding="utf-8")
                invariant_match = __import__("re").search(r"^primary_invariant: (.+)$", plan_text, flags=__import__("re").MULTILINE)
                invariant = invariant_match.group(1) if invariant_match else "legacy candidate invariant"
                initialized = subprocess.run(
                    [
                        sys.executable, str(ROOT / "scripts/plan-execution-state.py"), "init", execution_state,
                        "--run-id", run_id, "--plan", plan_rel,
                        "--plan-digest", "sha256:" + hashlib.sha256(plan_file.read_bytes()).hexdigest(),
                        "--source-head", git(repo, "rev-parse", "HEAD").stdout.strip(),
                        "--primary-invariant-digest", "sha256:" + hashlib.sha256(invariant.encode()).hexdigest(),
                        "--lifecycle-state", lifecycle_path, "--implementation-mode", "candidate",
                    ], cwd=repo, env=dict(os.environ), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if initialized.returncode != 0:
                    return initialized
            command_args.extend(["--plan-execution-state", execution_state])
        else:
            execution_state = command_args[command_args.index("--plan-execution-state") + 1]
        if command_args[0] == "correct":
            execution_payload = json.loads(Path(execution_state).read_text(encoding="utf-8"))
            open_attempt = execution_payload.get("open_attempt_id")
            if open_attempt:
                lifecycle_bytes = Path(lifecycle_path).read_bytes()
                lifecycle = json.loads(lifecycle_bytes)
                candidate = "sha256:" + lifecycle["current_manifest_digest"]
                prior_candidates = {
                    event.get("candidate_digest")
                    for event in execution_payload.get("events", [])
                    if event.get("candidate_digest")
                }
                reason_codes = (
                    "acceptance_unmet", "required_spec_missed", "focused_validation_failed"
                )
                reason = reason_codes[min(execution_payload["correction_rounds"], 2)]
                close_command = [
                    sys.executable, str(ROOT / "scripts/plan-execution-state.py"),
                    "close", execution_state, "--run-id", run_id,
                    "--attempt-id", open_attempt, "--outcome", "correction_requested",
                    "--review-author", "parent", "--review-reason-code", reason,
                    "--review-evidence-digest", "sha256:" + hashlib.sha256(
                        f"{run_id}:{open_attempt}:{reason}".encode()
                    ).hexdigest(),
                    "--invariant-digest", execution_payload["primary_invariant_digest"],
                    "--lifecycle-state", lifecycle_path,
                ]
                if candidate not in prior_candidates:
                    close_command.extend((
                        "--candidate-digest", candidate,
                        "--candidate-lifecycle-digest",
                        "sha256:" + hashlib.sha256(lifecycle_bytes).hexdigest(),
                    ))
                closed = subprocess.run(
                    close_command, cwd=repo, env=child_env, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if closed.returncode != 0:
                    return closed
        if command_args[0] == "apply" and manifest_path is not None and manifest_path.is_file():
            try:
                lifecycle = json.loads(Path(lifecycle_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                lifecycle = {}
            validation_base = [
                sys.executable, str(SCRIPT), "validate", str(manifest_path),
                "--parent-diff-approved", "--critical-invariants-approved",
                "--lifecycle-state", lifecycle_path, "--orchestration-run-id", run_id,
                "--plan-execution-state", execution_state,
            ]
            if lifecycle.get("phase") == "admitted" and lifecycle.get("focused_required"):
                focused = subprocess.run(
                    [*validation_base, "--suite", "focused", "--output-dir", tempfile.mkdtemp(prefix="auto-focused-", dir=manifest_path.parent)],
                    cwd=repo, env=child_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if focused.returncode != 0:
                    return focused
                lifecycle = json.loads(Path(lifecycle_path).read_text(encoding="utf-8"))
            if lifecycle.get("phase") in {"admitted", "focused_passed"}:
                authoritative = subprocess.run(
                    [*validation_base, "--suite", "authoritative", "--output-dir", tempfile.mkdtemp(prefix="auto-authoritative-", dir=manifest_path.parent)],
                    cwd=repo, env=child_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if authoritative.returncode != 0:
                    return authoritative
    return subprocess.run(
        [sys.executable, str(SCRIPT), *command_args],
        cwd=repo,
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def object_directory(repo: Path) -> Path:
    output = git(repo, "rev-parse", "--path-format=absolute", "--git-path", "objects").stdout.strip()
    return Path(output).resolve()


def object_database_snapshot(repo: Path) -> dict[str, bytes]:
    objects = object_directory(repo)
    return {
        str(path.relative_to(objects)): path.read_bytes()
        for path in objects.rglob("*")
        if path.is_file()
    }


def execution_state_path(manifest: dict[str, object]) -> Path:
    lifecycle = Path(str(manifest["lifecycle_state_path"]))
    run_id = str(manifest["orchestration_run_id"])
    return lifecycle.with_name(lifecycle.name + f".{run_id}.plan-execution.json")


def write_worker(path: Path, body: str) -> None:
    header = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        from __future__ import annotations

        import atexit
        import hashlib
        import json
        import os
        from pathlib import Path


        prefix = "{ENV_PREFIX}"
        worker_repo = Path(os.environ[prefix + "WORKER_REPO"])
        source_repo = Path(os.environ[prefix + "SOURCE_REPO"])
        scratch_dir = Path(os.environ[prefix + "SCRATCH_DIR"])
        new_file_root = Path(os.environ[prefix + "NEW_FILE_ROOT"])
        plan_path = os.environ[prefix + "PLAN_PATH"]


        def write_default_completion_claims() -> None:
            target = Path(os.environ[prefix + "COMPLETION_CLAIMS"])
            if target.exists() or target.is_symlink():
                return
            contract = json.loads(Path(os.environ[prefix + "WORKER_CONTRACT"]).read_text(encoding="utf-8"))
            evidence = [
                {{"acceptance_digest": "sha256:" + hashlib.sha256(item.encode("utf-8")).hexdigest(), "claim": "satisfied"}}
                for item in contract["acceptance"]
            ]
            target.write_text(json.dumps({{
                "attempt_result": "success",
                "acceptance_evidence": evidence,
                "commands_attempted": [],
                "blockers": [],
                "residual_risks": ["parent_review_required"],
                "out_of_scope_change": False,
            }}, sort_keys=True) + "\\n", encoding="utf-8")


        atexit.register(write_default_completion_claims)
        """
    )
    path.write_text(header + textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def write_fake_codex(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            from __future__ import annotations

            import atexit
            import hashlib
            import json
            import os
            import sys
            from pathlib import Path


            args = sys.argv[1:]
            model = args[args.index("--model") + 1]
            config = args[args.index("--config") + 1]
            reasoning = config.split('=', 1)[1].strip('"')
            scenario = os.environ["FAKE_CODEX_SCENARIO"]
            primary_model = os.environ.get("FAKE_PRIMARY_MODEL", "gpt-5.3-codex-spark")
            fallback_model = os.environ.get("FAKE_FALLBACK_MODEL", "gpt-5.6-luna")
            primary_reasoning = os.environ.get("FAKE_PRIMARY_REASONING", "medium")
            fallback_reasoning = os.environ.get("FAKE_FALLBACK_REASONING", "max")
            worker_repo = Path(os.environ["{ENV_PREFIX}WORKER_REPO"])
            scratch_dir = Path(os.environ["{ENV_PREFIX}SCRATCH_DIR"])
            target = worker_repo / "allowed.txt"
            last_message = None
            if "--output-last-message" in args:
                last_message = Path(args[args.index("--output-last-message") + 1])

            def write_default_completion_claims() -> None:
                target = Path(os.environ["{ENV_PREFIX}COMPLETION_CLAIMS"])
                if target.exists() or target.is_symlink():
                    return
                contract = json.loads(Path(os.environ["{ENV_PREFIX}WORKER_CONTRACT"]).read_text(encoding="utf-8"))
                evidence = [
                    {{"acceptance_digest": "sha256:" + hashlib.sha256(item.encode("utf-8")).hexdigest(), "claim": "satisfied"}}
                    for item in contract["acceptance"]
                ]
                target.write_text(json.dumps({{
                    "attempt_result": "success",
                    "acceptance_evidence": evidence,
                    "commands_attempted": [],
                    "blockers": [],
                    "residual_risks": ["parent_review_required"],
                    "out_of_scope_change": False,
                }}, sort_keys=True) + "\\n", encoding="utf-8")

            atexit.register(write_default_completion_claims)

            if model == primary_model:
                if reasoning != primary_reasoning:
                    raise SystemExit(f"unexpected primary reasoning: {{reasoning}}")
                if scenario == "primary_success":
                    target.write_text("preferred\\n", encoding="utf-8")
                elif scenario in {{"unavailable_then_success", "unavailable_then_failure", "both_unavailable"}}:
                    target.write_text("discarded-primary\\n", encoding="utf-8")
                    if last_message is not None:
                        last_message.write_text("failed preferred output\\n", encoding="utf-8")
                    print("ERROR: You've hit your usage limit for the preferred model.", file=sys.stderr)
                    raise SystemExit(1)
                elif scenario == "nonavailability_failure":
                    target.write_text("discarded-error\\n", encoding="utf-8")
                    print("ERROR: worker validation failed", file=sys.stderr)
                    raise SystemExit(1)
                else:
                    raise SystemExit(f"unexpected scenario: {{scenario}}")
            elif model == fallback_model:
                if reasoning != fallback_reasoning:
                    raise SystemExit(f"unexpected fallback reasoning: {{reasoning}}")
                expected_starts = {{"initial candidate\\n", "fallback\\n"}} if "{ENV_PREFIX}CORRECTION_BRIEF" in os.environ else {{"original\\n"}}
                if target.read_text(encoding="utf-8") not in expected_starts:
                    raise SystemExit("fallback inherited preferred-attempt changes")
                host_codex_home = Path(os.environ["FAKE_HOST_CODEX_HOME"])
                output_dir = Path(os.environ["FAKE_OUTPUT_DIR"])
                primary_root = scratch_dir.parents[1] / "primary"
                for forbidden in (
                    host_codex_home / "auth.json",
                    output_dir / "worker-primary.stderr",
                    primary_root / "clone" / "allowed.txt",
                ):
                    if forbidden.exists():
                        raise SystemExit(f"fallback can read hidden attempt state: {{forbidden}}")
                if scenario == "unavailable_then_success":
                    target.write_text("fallback\\n", encoding="utf-8")
                elif scenario == "unavailable_then_failure":
                    print("ERROR: fallback implementation failed", file=sys.stderr)
                    raise SystemExit(2)
                elif scenario == "both_unavailable":
                    print("FATAL: rate limit exceeded", file=sys.stderr)
                    raise SystemExit(1)
                else:
                    raise SystemExit("fallback ran unexpectedly")
            else:
                raise SystemExit(f"unexpected model: {{model}}")

            if last_message is not None:
                last_message.write_text(f"completed with {{model}}\\n", encoding="utf-8")
            print(f"completed with {{model}}")
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


class SandboxedPlanWorkerTests(unittest.TestCase):
    def test_dependent_attempt_forwards_reviewer_registry(self) -> None:
        args = argparse.Namespace(
            plan_execution_state="/tmp/execution.json",
            orchestration_run_id="run-1",
            plan="docs/plan/active/001-test.md",
            lifecycle_state="/tmp/lifecycle.json",
            predecessor_plan_execution_state="/tmp/predecessor.json",
            predecessor_session_checkpoint="/tmp/checkpoint.json",
            root_session_manifest="/tmp/root-manifest.json",
            reviewer_registry="/tmp/reviewer-registry.jsonl",
        )
        with mock.patch.object(
            RUNNER.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, b"", b""),
        ) as run:
            RUNNER.begin_plan_execution_attempt(args, attempt_kind="initial")
        command = run.call_args.args[0]
        self.assertIn("--reviewer-registry", command)
        self.assertEqual(
            command[command.index("--reviewer-registry") + 1],
            args.reviewer_registry,
        )

        args.reviewer_registry = None
        with self.assertRaisesRegex(
            RUNNER.RunnerError,
            "reviewer registry must be supplied together",
        ):
            RUNNER.begin_plan_execution_attempt(args, attempt_kind="initial")

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("git") is None:
            raise RuntimeError("git is required for sandboxed plan worker tests")
        bwrap = shutil.which("bwrap")
        if bwrap is None:
            raise RuntimeError("bwrap is required for sandboxed plan worker tests")
        RUNNER.ensure_bwrap_usable(bwrap)

    def make_repo(
        self,
        write_scope: list[str],
        files: dict[str, str] | None = None,
        *,
        repo_name: str = "repo",
        validation: list[str] | None = None,
        focused_validation: list[str] | None = None,
        validation_authority_scope: list[str] | None = None,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory()
        repo = Path(temporary.name) / repo_name
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        git(repo, "remote", "add", "origin", f"https://example.invalid/{repo_name}.git")
        (repo / "AGENTS.md").write_text("sandboxed test repo\n", encoding="utf-8")
        (repo / "docs/plan/active").mkdir(parents=True, exist_ok=True)
        (repo / "docs/agent").mkdir(parents=True, exist_ok=True)
        (repo / "docs/agent/SPEC_USER_COMMUNICATION.md").write_text("fixture\n", encoding="utf-8")
        (repo / "docs/agent/SPEC_PLAN_WORKFLOW.md").write_text("fixture\n", encoding="utf-8")
        (repo / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nid\tpath\tstatus\n001\tdocs/plan/active/001-sandboxed.md\tin_progress\n",
            encoding="utf-8",
        )
        for relative, content in (files or {"allowed.txt": "original\n"}).items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        plan = repo / "docs/plan/active/001-sandboxed.md"
        lines = [
            "# Sandboxed worker test",
            "",
            "status: in_progress",
            "task_types:",
            "  - template_workflow",
            "review_class: B",
            "human_design_required: no",
            "human_approval_status: not_required",
            "implementation_risk: low",
            "implementation_ambiguity: low",
            "primary_invariant: mutate only the declared fixture files",
            "write_scope:",
            *(f"  - {entry}" for entry in write_scope),
            "context_files:",
            "  - docs/agent/SPEC_USER_COMMUNICATION.md",
            "required_specs:",
            "  - docs/agent/SPEC_PLAN_WORKFLOW.md",
            "validation:",
            *(f"  - {command}" for command in (validation or ["git diff --check"])),
            *(
                ["focused_validation:", *(f"  - {command}" for command in focused_validation)]
                if focused_validation is not None
                else []
            ),
            *(
                ["validation_authority_scope:", *(f"  - {entry}" for entry in validation_authority_scope)]
                if validation_authority_scope is not None
                else []
            ),
            "acceptance:",
            "  - Test fixture.",
            "checked_summary_ja: fixture",
            "",
            "## Tasks",
            "",
            "- [ ] Fixture.",
            "",
        ]
        plan.write_text("\n".join(lines), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "baseline")
        return temporary, repo, "docs/plan/active/001-sandboxed.md"

    def run_with_worker(
        self,
        repo: Path,
        plan_path: str,
        worker_body: str,
        *,
        output_dir: Path | None = None,
        worker_env: dict[str, str] | None = None,
        parent_env: dict[str, str] | None = None,
        extra_args: tuple[str, ...] = (),
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temp_root = output_dir.parent if output_dir is not None else Path(tempfile.mkdtemp(prefix="sandboxed-worker-run-"))
        actual_output = output_dir if output_dir is not None else temp_root / "output"
        worker_path = temp_root / "worker.py"
        write_worker(worker_path, worker_body)
        args = [
            "run",
            plan_path,
            "--output-dir",
            str(actual_output),
            "--worker-binary",
            sys.executable,
            "--worker-arg",
            str(worker_path),
            *extra_args,
        ]
        for key, value in (worker_env or {}).items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env=parent_env), actual_output, worker_path

    def run_with_fake_codex(
        self,
        repo: Path,
        plan_path: str,
        scenario: str,
        *,
        output_dir: Path,
        extra_args: tuple[str, ...] = (),
        fake_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        fake_codex = output_dir.parent / f"fake-codex-{scenario}.py"
        write_fake_codex(fake_codex)
        codex_home = output_dir.parent / f"codex-home-{scenario}-{output_dir.name}"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text('{"token":"fixture"}\n', encoding="utf-8")
        args = [
            "run",
            plan_path,
            "--output-dir",
            str(output_dir),
            "--codex-bin",
            str(fake_codex),
            *extra_args,
        ]
        worker_env = {
            "FAKE_CODEX_SCENARIO": scenario,
            "FAKE_HOST_CODEX_HOME": str(codex_home),
            "FAKE_OUTPUT_DIR": str(output_dir),
            **(fake_env or {}),
        }
        for key, value in worker_env.items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env={"CODEX_HOME": str(codex_home)})

    def run_correction_with_worker(
        self,
        repo: Path,
        plan_path: str,
        prior_manifest: Path,
        correction_brief: Path,
        worker_body: str,
        *,
        output_dir: Path,
        extra_args: tuple[str, ...] = (),
        worker_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        worker_root = Path(tempfile.mkdtemp(prefix="sandboxed-correction-worker-"))
        self.addCleanup(shutil.rmtree, worker_root, True)
        worker = worker_root / "worker.py"
        write_worker(worker, worker_body)
        args = [
            "correct",
            plan_path,
            str(prior_manifest),
            str(correction_brief),
            "--output-dir",
            str(output_dir),
            "--worker-binary",
            sys.executable,
            "--worker-arg",
            str(worker),
            *extra_args,
        ]
        for key, value in (worker_env or {}).items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args)

    def run_correction_with_fake_codex(
        self,
        repo: Path,
        plan_path: str,
        prior_manifest: Path,
        correction_brief: Path,
        scenario: str,
        *,
        output_dir: Path,
        extra_args: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        tool_root = Path(tempfile.mkdtemp(prefix="sandboxed-correction-codex-"))
        self.addCleanup(shutil.rmtree, tool_root, True)
        fake_codex = tool_root / "fake-codex.py"
        write_fake_codex(fake_codex)
        codex_home = tool_root / "codex-home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text('{"token":"fixture"}\n', encoding="utf-8")
        args = [
            "correct",
            plan_path,
            str(prior_manifest),
            str(correction_brief),
            "--output-dir",
            str(output_dir),
            "--codex-bin",
            str(fake_codex),
            *extra_args,
        ]
        for key, value in {
            "FAKE_CODEX_SCENARIO": scenario,
            "FAKE_HOST_CODEX_HOME": str(codex_home),
            "FAKE_OUTPUT_DIR": str(output_dir),
        }.items():
            args.extend(["--worker-env", f"{key}={value}"])
        return run_cli(repo, *args, env={"CODEX_HOME": str(codex_home)})

    def assert_no_workspace_directories(self, tmpdir_root: Path) -> None:
        leftovers = sorted(path.name for path in tmpdir_root.glob("sandboxed-plan-worker-workspace-*"))
        self.assertEqual(leftovers, [])

    def write_availability_state(
        self,
        path: Path,
        run_id: str,
        entries: list[dict[str, str]],
        **extra: object,
    ) -> None:
        payload: dict[str, object] = {
            "schema_version": 1,
            "orchestration_run_id": run_id,
            "unavailable_models": entries,
            **extra,
        }
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    def test_default_worker_command_uses_supported_external_sandbox_flags(self) -> None:
        command = RUNNER.default_worker_command(
            codex_bin="/usr/bin/codex",
            clone_dir=Path("/tmp/clone"),
            scratch_dir=Path("/tmp/scratch"),
            last_message_path=Path("/tmp/last-message.txt"),
            model="model",
            reasoning="medium",
        )
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ephemeral", command)
        self.assertNotIn("--sandbox", command)
        self.assertNotIn("--ask-for-approval", command)
        self.assertNotIn("--dangerously-bypass-hook-trust", command)
        prompt = RUNNER.build_worker_prompt()
        self.assertIn("Do not run plan validation", prompt)
        self.assertNotIn("Run every validation command", prompt)
        self.assertIn("SANDBOXED_PLAN_WORKER_CONTRACT first", prompt)
        self.assertNotIn("docs/plan/active/001-test.md", prompt)

    def test_repository_identity_is_stable_origin_bound_and_credential_free(self) -> None:
        self.assertEqual(
            RUNNER.canonical_repository_origin("git@example.invalid:org/repo.git"),
            RUNNER.canonical_repository_origin("https://token@example.invalid/org/repo.git"),
        )
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        first = RUNNER.derive_repository_identity(repo, "git")
        (repo / "unrelated.txt").write_text("later\n", encoding="utf-8")
        git(repo, "add", "unrelated.txt")
        git(repo, "commit", "-qm", "later commit")
        self.assertEqual(RUNNER.derive_repository_identity(repo, "git"), first)
        git(repo, "remote", "set-url", "origin", "https://example.invalid/distinct.git")
        self.assertNotEqual(RUNNER.derive_repository_identity(repo, "git"), first)
        git(repo, "remote", "remove", "origin")
        with self.assertRaisesRegex(RUNNER.RunnerError, "canonical remote.origin.url"):
            RUNNER.derive_repository_identity(repo, "git")

    def test_linked_parent_worktree_resolves_and_clones_without_hardlinks(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        linked = Path(temporary.name) / "linked-parent"
        git(repo, "worktree", "add", "-q", "-b", "parent-plan", str(linked), "HEAD")
        with mock.patch.object(Path, "cwd", return_value=linked):
            self.assertEqual(RUNNER.detect_repo_root("git"), linked.resolve())

        clone = Path(temporary.name) / "worker-clone"
        head = git(linked, "rev-parse", "HEAD").stdout.strip()
        RUNNER.clone_at_head(linked, "git", head, clone)
        self.assertEqual((clone / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        self.assertEqual(git(clone, "rev-parse", "HEAD").stdout.strip(), head)

        source_objects = object_directory(linked)
        clone_objects = object_directory(clone)
        shared_loose_objects = []
        for source in source_objects.glob("[0-9a-f][0-9a-f]/*"):
            candidate = clone_objects / source.relative_to(source_objects)
            if candidate.is_file():
                shared_loose_objects.append(source.stat().st_ino == candidate.stat().st_ino)
        self.assertTrue(shared_loose_objects)
        self.assertFalse(any(shared_loose_objects))

    def evaluate_worker_contract_case(
        self, base: dict[str, object], case: dict[str, object]
    ) -> dict[str, object]:
        error_fragments = {
            "source_plan_changed": "changed while deriving",
            "contract_digest_mismatch": "digest no longer matches",
            "lineage_mismatch": "lineage differs",
            "missing_primary_invariant": "primary_invariant",
            "duplicate_contract_field": "duplicate field",
            "unknown_contract_field": "unknown or missing fields",
            "path_traversal": "dot-dot traversal",
            "symlink_escape": "symlink",
            "contract_too_large": "byte bound",
            "read_only_contract": "worker exited with 73",
            "validation_authority_write": "validation authority",
            "non_exact_write_path": "explicit file path",
        }
        expected = case["expected"]
        operation = case["operation"]
        inputs = case["input"]
        with tempfile.TemporaryDirectory(prefix="worker-contract-fixture-") as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")
            git(repo, "config", "user.email", "fixture@example.invalid")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "remote", "add", "origin", "git@example.invalid:fixtures/worker-contract.git")
            (repo / "AGENTS.md").write_text("fixture policy\n", encoding="utf-8")
            for relative, content in base["repository_files"].items():
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            plan_rel = base["plan_path"]
            plan = repo / plan_rel
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(base["plan_bytes"], encoding="utf-8")
            (repo / "docs/plan/plan.md").write_text(
                f"# Active Plan\n\nid\tpath\tstatus\n001\t{plan_rel}\tin_progress\n",
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "fixture baseline")
            values = RUNNER.load_planlib().parse_manifest(plan)
            head = git(repo, "rev-parse", "HEAD").stdout.strip()
            plan_digest = RUNNER.hash_file(plan)
            scope = RUNNER.parse_write_scope(values["write_scope"])
            lineage = dict(base["attempt_lineage"])
            if "attempt_lineage" in inputs:
                lineage = dict(inputs["attempt_lineage"])
                if "prior_manifest_digest" in lineage:
                    lineage["prior_manifest_digest"] = lineage["prior_manifest_digest"].removeprefix("sha256:")
                    lineage.setdefault("prior_patch_digest", "2" * 64)
                    lineage.setdefault("correction_brief_digest", "3" * 64)

            def derive() -> bytes:
                return RUNNER.derive_worker_contract(
                    repo_root=repo,
                    git_bin="git",
                    head=head,
                    plan_path=plan,
                    plan_rel=plan_rel,
                    plan_digest=plan_digest,
                    values=values,
                    normalized_scope=scope,
                    run_id=base["orchestration_run_id"],
                    plan_execution_attempt_id="attempt-fixture-ledger",
                    lineage=lineage,
                )

            try:
                if operation == "derive_twice":
                    first = derive()
                    if first != derive():
                        raise AssertionError("worker contract derivation is not exact")
                elif operation == "validate_write_scope":
                    candidate_scope = RUNNER.parse_write_scope(inputs["write_scope"])
                    RUNNER.require_safe_delegated_write_scope(repo, plan_rel, values, candidate_scope)
                elif operation == "derive_after_plan_mutation":
                    plan.write_text(
                        plan.read_text(encoding="utf-8") + inputs["append_to_plan"],
                        encoding="utf-8",
                    )
                    derive()
                elif operation == "derive_with_plan_replacement":
                    text = plan.read_text(encoding="utf-8")
                    if "remove_line_prefix" in inputs:
                        prefix = inputs["remove_line_prefix"]
                        text = "\n".join(
                            line for line in text.splitlines() if not line.startswith(prefix)
                        ) + "\n"
                        plan.write_text(text, encoding="utf-8")
                        values = RUNNER.load_planlib().parse_manifest(plan)
                        scope = RUNNER.parse_write_scope(values["write_scope"])
                        plan_digest = RUNNER.hash_file(plan)
                        derive()
                    else:
                        RUNNER.parse_write_scope(inputs["replace_write_scope"])
                elif operation == "derive_with_repository_mutation":
                    mutation = inputs["replace_with_symlink"]
                    target = repo / mutation["path"]
                    target.unlink()
                    (repo / "outside-spec.md").write_text("outside\n", encoding="utf-8")
                    target.symlink_to(mutation["target"])
                    derive()
                elif operation == "verify_contract_mutation":
                    content = derive()
                    contract = json.loads(content)
                    manifest = {
                        "source_head": head,
                        "plan_path": plan_rel,
                        "plan_digest": plan_digest,
                        "orchestration_run_id": base["orchestration_run_id"],
                        "worker_attempt_label": base["attempt_lineage"]["attempt_label"],
                    }
                    mutation = inputs["mutation"]
                    if mutation["kind"] == "manifest_digest":
                        pass
                    elif mutation["kind"] == "attempt_lineage":
                        contract["attempt_lineage"] = mutation["value"]
                        content = (json.dumps(contract, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    else:
                        contract[mutation["name"]] = mutation["value"]
                        content = (json.dumps(contract, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    output = root / "output"
                    output.mkdir()
                    contract_path = output / "worker-contract.json"
                    contract_path.write_bytes(content)
                    manifest["worker_contract_path"] = str(contract_path)
                    manifest["worker_contract_digest"] = (
                        inputs["mutation"]["value"].removeprefix("sha256:")
                        if mutation["kind"] == "manifest_digest"
                        else RUNNER.hash_file(contract_path)
                    )
                    manifest_path = output / "manifest.json"
                    manifest_path.write_text("{}\n", encoding="utf-8")
                    RUNNER.verify_worker_contract(
                        repo_root=repo, git_bin="git", manifest_path=manifest_path,
                        manifest=manifest, plan_path=plan, plan_rel=plan_rel,
                        values=values, normalized_scope=scope,
                    )
                elif operation == "verify_serialized_contract":
                    if "json_prefix" in inputs:
                        valid = derive().decode("utf-8")
                        RUNNER.load_exact_json_object(
                            (inputs["json_prefix"] + valid[1:]).encode("utf-8"),
                            label="worker execution contract",
                        )
                    else:
                        oversized = root / "oversized.json"
                        oversized.write_bytes(inputs["fill_byte"].encode() * inputs["byte_count"])
                        RUNNER.read_bounded_regular_file(
                            oversized, RUNNER.WORKER_CONTRACT_MAX_BYTES, "worker execution contract"
                        )
                elif operation == "attempt_worker_write":
                    result, _output, _worker = self.run_with_worker(
                        repo,
                        plan_rel,
                        textwrap.dedent(
                            """\
                            contract = Path(os.environ[prefix + "WORKER_CONTRACT"])
                            try:
                                contract.write_text("mutated\\n", encoding="utf-8")
                            except OSError:
                                raise SystemExit(73)
                            raise SystemExit("contract unexpectedly writable")
                            """
                        ),
                        output_dir=root / "attempt-write",
                    )
                    if result.returncode != 0:
                        raise RUNNER.RunnerError(result.stderr.strip())
                else:
                    raise AssertionError(f"unsupported tuned operation: {operation}")
            except RUNNER.RunnerError as exc:
                expected_code = expected["error_code"]
                fragment = error_fragments.get(expected_code)
                if fragment is None or fragment not in str(exc):
                    return {"result": "rejected", "error_code": "unexpected_error"}
                return {"result": "rejected", "error_code": expected_code}
            return {"result": "accepted", "error_code": None}

    def test_tuned_worker_contract_fixture_is_frozen_and_evaluator_is_generic(self) -> None:
        self.assertEqual(
            hashlib.sha256(WORKER_CONTRACT_SCENARIOS.read_bytes()).hexdigest(),
            WORKER_CONTRACT_SCENARIOS_SHA256,
        )
        fixture = load_worker_contract_fixture(WORKER_CONTRACT_SCENARIOS, used_for_tuning=True)
        self.assertEqual(fixture["holdout_file"], WORKER_CONTRACT_HOLDOUT.name)
        self.assertEqual(
            hashlib.sha256(WORKER_CONTRACT_HOLDOUT.read_bytes()).hexdigest(),
            WORKER_CONTRACT_HOLDOUT_SHA256,
        )
        self.assertEqual({case["class"] for case in fixture["cases"]}, {"median", "edge", "negative"})
        self.assertEqual(
            {coverage for case in fixture["cases"] for coverage in case["covers"]},
            WORKER_CONTRACT_COVERAGE,
        )
        observations = evaluate_worker_contract_fixture(
            WORKER_CONTRACT_SCENARIOS,
            self.evaluate_worker_contract_case,
            used_for_tuning=True,
        )
        self.assertEqual([item["id"] for item in observations], [case["id"] for case in fixture["cases"]])
        with self.assertRaisesRegex(AssertionError, "observed"):
            evaluate_worker_contract_fixture(
                WORKER_CONTRACT_SCENARIOS,
                lambda _base, _case: {"result": "rejected", "error_code": "wrong"},
                used_for_tuning=True,
            )

    def evaluate_worker_completion_receipt_case(
        self, base: dict[str, object], case: dict[str, object]
    ) -> dict[str, object]:
        receipt = {
            "schema_version": RUNNER.WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION,
            **{
                key: json.loads(json.dumps(value))
                for key, value in base.items()
                if key != "receipt_relative_path"
            },
        }
        receipt["plan_execution_attempt_id"] = "attempt-fixture-ledger"
        for index, command in enumerate(
            receipt["claims"]["commands_attempted"], start=1
        ):
            command["command_id"] = f"worker-check-{index}"
        expected_identity = {
            key: json.loads(json.dumps(receipt[key]))
            for key in (
                "repository_identity", "source_head", "plan_path", "plan_digest",
                "worker_contract_digest", "orchestration_run_id", "attempt", "candidate",
                "plan_execution_attempt_id",
            )
        }
        operation = case["operation"]
        inputs = case["input"]
        expected = case["expected"]
        error_fragments = {
            "stale_receipt": "stale receipt source HEAD",
            "replayed_receipt": "replays a consumed attempt",
            "plan_mismatch": "plan digest mismatch",
            "contract_mismatch": "worker contract digest mismatch",
            "patch_mismatch": "patch digest mismatch",
            "changed_path_mismatch": "changed paths mismatch",
            "false_success_claim": "false success claim",
            "missing_out_of_scope_declaration": "missing the out-of-scope declaration",
            "unknown_receipt_field": "unknown or missing fields",
            "duplicate_receipt_field": "duplicate field",
            "receipt_too_large": "exceeds the byte bound",
            "receipt_value_too_large": "prohibited or oversized",
            "receipt_path_traversal": "dot-dot traversal",
            "receipt_symlink_escape": "symlink",
            "prohibited_receipt_content": "prohibited or oversized",
        }
        try:
            if operation == "derive_twice":
                first = RUNNER.serialize_worker_completion_receipt(receipt)
                if first != RUNNER.serialize_worker_completion_receipt(receipt):
                    raise AssertionError("receipt derivation is not deterministic")
                RUNNER.validate_worker_completion_receipt(
                    RUNNER.load_worker_completion_receipt(first), expected=expected_identity
                )
            elif operation == "derive_failure_before_candidate":
                receipt["candidate"] = None
                receipt["process"] = dict(inputs)
                receipt["claims"] = RUNNER.safe_failure_claims("worker_failed")
                RUNNER.load_worker_completion_receipt(
                    RUNNER.serialize_worker_completion_receipt(receipt)
                )
            elif operation in {"derive_correction_failure", "derive_correction_success"}:
                receipt["attempt"] = {
                    "attempt_id": inputs["attempt_id"],
                    "attempt_kind": "correction",
                    "correction_round": inputs["correction_round"],
                    "correction_lineage": {
                        "prior_manifest_digest": inputs["prior_manifest_digest"]
                    },
                }
                if operation == "derive_correction_failure":
                    receipt["candidate"] = None
                    receipt["process"] = {
                        "exit_status": inputs["exit_status"],
                        "diagnostic_codes": ["worker_failed"],
                    }
                    receipt["claims"] = RUNNER.safe_failure_claims("worker_failed")
                else:
                    receipt["candidate"] = {
                        "patch_digest": inputs["patch_digest"],
                        "changed_paths": inputs["changed_paths"],
                    }
                RUNNER.load_worker_completion_receipt(
                    RUNNER.serialize_worker_completion_receipt(receipt)
                )
            elif operation == "derive_partial_commands":
                receipt["candidate"] = None
                receipt["process"] = {
                    "exit_status": inputs["exit_status"],
                    "diagnostic_codes": ["worker_failed"],
                }
                receipt["claims"] = {
                    "attempt_result": "failure",
                    "acceptance_evidence": [],
                    "commands_attempted": inputs["commands_attempted"],
                    "blockers": inputs["blockers"],
                    "residual_risks": [],
                    "out_of_scope_change": False,
                }
                RUNNER.load_worker_completion_receipt(
                    RUNNER.serialize_worker_completion_receipt(receipt)
                )
            elif operation == "verify_identity_mismatch":
                receipt[inputs["field"]] = inputs["value"]
                RUNNER.validate_worker_completion_receipt(receipt, expected=expected_identity)
            elif operation == "verify_replay":
                RUNNER.validate_worker_completion_receipt(
                    receipt,
                    expected=expected_identity,
                    consumed_attempt_ids=[inputs["consumed_attempt_id"]],
                )
            elif operation == "verify_candidate_mismatch":
                receipt["candidate"][inputs["field"]] = inputs["value"]
                RUNNER.validate_worker_completion_receipt(receipt, expected=expected_identity)
            elif operation == "verify_false_success":
                receipt["process"]["exit_status"] = inputs["process_exit_status"]
                receipt["claims"]["attempt_result"] = inputs["attempt_result"]
                RUNNER.validate_worker_completion_receipt(receipt)
            elif operation == "verify_receipt_mutation":
                mutation = inputs["mutation"]
                if mutation["kind"] == "remove_claim_field":
                    del receipt["claims"][mutation["name"]]
                elif mutation["kind"] == "add_top_field":
                    receipt[mutation["name"]] = mutation["value"]
                else:
                    receipt["claims"][mutation["field"]] = [
                        "x" * mutation["byte_count"]
                    ]
                RUNNER.validate_worker_completion_receipt(receipt)
            elif operation == "verify_serialized_receipt":
                if "json_prefix" in inputs:
                    valid = RUNNER.serialize_worker_completion_receipt(receipt).decode("utf-8")
                    content = (inputs["json_prefix"] + valid[1:]).encode("utf-8")
                else:
                    content = inputs["fill_byte"].encode("utf-8") * inputs["byte_count"]
                RUNNER.load_worker_completion_receipt(content)
            elif operation == "verify_output_path":
                with tempfile.TemporaryDirectory(prefix="completion-receipt-path-") as temporary:
                    output = Path(temporary)
                    if "symlink_target" in inputs:
                        (output / inputs["path"]).symlink_to(inputs["symlink_target"])
                    RUNNER.verify_worker_completion_receipt_path(output, inputs["path"])
            elif operation == "verify_prohibited_content":
                receipt["claims"][inputs["field"]] = [inputs["value"]]
                RUNNER.validate_worker_completion_receipt(receipt)
            else:
                raise AssertionError(f"unsupported tuned receipt operation: {operation}")
        except RUNNER.RunnerError as exc:
            expected_code = expected["error_code"]
            fragment = error_fragments.get(expected_code)
            if fragment is None or fragment not in str(exc):
                return {"result": "rejected", "error_code": "unexpected_error"}
            return {"result": "rejected", "error_code": expected_code}
        return {"result": "accepted", "error_code": None}

    def test_tuned_worker_completion_receipt_fixture_is_frozen_and_evaluator_is_generic(self) -> None:
        self.assertEqual(
            hashlib.sha256(WORKER_COMPLETION_RECEIPT_SCENARIOS.read_bytes()).hexdigest(),
            WORKER_COMPLETION_RECEIPT_SCENARIOS_SHA256,
        )
        fixture = load_worker_completion_receipt_fixture(
            WORKER_COMPLETION_RECEIPT_SCENARIOS, used_for_tuning=True
        )
        self.assertEqual(fixture["holdout_file"], WORKER_COMPLETION_RECEIPT_HOLDOUT.name)
        self.assertEqual(
            hashlib.sha256(WORKER_COMPLETION_RECEIPT_HOLDOUT.read_bytes()).hexdigest(),
            WORKER_COMPLETION_RECEIPT_HOLDOUT_SHA256,
        )
        self.assertEqual(
            {case["class"] for case in fixture["cases"]},
            {"median", "edge", "negative"},
        )
        self.assertEqual(
            {coverage for case in fixture["cases"] for coverage in case["covers"]},
            WORKER_COMPLETION_RECEIPT_COVERAGE,
        )
        observations = evaluate_worker_completion_receipt_fixture(
            WORKER_COMPLETION_RECEIPT_SCENARIOS,
            self.evaluate_worker_completion_receipt_case,
            used_for_tuning=True,
        )
        self.assertEqual(
            [item["id"] for item in observations],
            [case["id"] for case in fixture["cases"]],
        )
        with self.assertRaisesRegex(AssertionError, "observed"):
            evaluate_worker_completion_receipt_fixture(
                WORKER_COMPLETION_RECEIPT_SCENARIOS,
                lambda _base, _case: {"result": "rejected", "error_code": "wrong"},
                used_for_tuning=True,
            )

    def test_exposed_worker_completion_receipt_holdout_is_a_known_regression(self) -> None:
        observations = evaluate_worker_completion_receipt_fixture(
            WORKER_COMPLETION_RECEIPT_HOLDOUT,
            self.evaluate_worker_completion_receipt_case,
            used_for_tuning=False,
        )
        self.assertEqual(
            observations,
            [
                {
                    "id": "holdout-host-path-raw-output-in-residual-risk",
                    "observed": {
                        "result": "rejected",
                        "error_code": "prohibited_receipt_content",
                    },
                }
            ],
        )

    def test_worker_completion_receipt_integration_evidence_matches_all_fixtures(self) -> None:
        evidence = json.loads(WORKER_COMPLETION_RECEIPT_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(
            hashlib.sha256(WORKER_COMPLETION_RECEIPT_REPLACEMENT_HOLDOUT.read_bytes()).hexdigest(),
            WORKER_COMPLETION_RECEIPT_REPLACEMENT_HOLDOUT_SHA256,
        )
        actual = []
        for path, used_for_tuning in (
            (WORKER_COMPLETION_RECEIPT_SCENARIOS, True),
            (WORKER_COMPLETION_RECEIPT_HOLDOUT, False),
            (WORKER_COMPLETION_RECEIPT_REPLACEMENT_HOLDOUT, False),
        ):
            fixture = load_worker_completion_receipt_fixture(
                path, used_for_tuning=used_for_tuning
            )
            observations = evaluate_worker_completion_receipt_fixture(
                path,
                self.evaluate_worker_completion_receipt_case,
                used_for_tuning=used_for_tuning,
            )
            observed_by_id = {item["id"]: item["observed"] for item in observations}
            actual.extend(
                {
                    "id": case["id"],
                    "class": case["class"],
                    "used_for_tuning": case["used_for_tuning"],
                    **observed_by_id[case["id"]],
                }
                for case in fixture["cases"]
            )
        self.assertEqual(actual, evidence["observations"])
        implementation_commit = evidence["implementation_commit"]
        committed_digests = []
        for relative in (
            "scripts/run-sandboxed-plan-worker.py",
            "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
        ):
            content = subprocess.run(
                ["git", "show", f"{implementation_commit}:{relative}"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            committed_digests.append(hashlib.sha256(content).hexdigest())
        self.assertEqual(
            committed_digests,
            [evidence["runner_sha256"], evidence["template_runner_sha256"]],
        )
        source_contract = json.loads(
            (ROOT / "docs/plan/replanned/contracts/114-validate-structured-worker-completion.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            evidence["source_acceptance"],
            [
                {"digest": item["digest"].removeprefix("sha256:"), "result": "passed"}
                for item in source_contract["source"]["acceptance"]
            ],
        )
    def test_codex_unavailability_classifier_is_bounded_to_cli_error_lines(self) -> None:
        cases = (
            (b"", b"ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.", "usage_limit"),
            (b"", b"ERROR: Usage limit exceeded for model GPT-5.3-Codex-Spark.", "usage_limit"),
            (b"", b"FATAL: rate limit exceeded", "rate_limit"),
            (b"", b"ERROR: model preferred is unavailable", "model_unavailable"),
            (b"", b"ERROR: The model gpt-x does not exist or you do not have access to it.", "model_unavailable"),
            (b"", b"ERROR: you don't have access to this model", "model_access_denied"),
            (b"", b"ERROR: Access to model gpt-x is denied.", "model_access_denied"),
            (b"ERROR: worker validation failed", b"", None),
            (b"ERROR: rate limit exceeded", b"", None),
            (b"report says rate limit exceeded", b"", None),
            (b"", b"ERROR: dependency API rate limit exceeded", None),
            (b"", b"ERROR: rate limit exceeded\nERROR: authentication failed", None),
            (b"", b"authentication failed", None),
            (b"", b"network unavailable", None),
        )
        for stdout, stderr, expected in cases:
            with self.subTest(stderr=stderr):
                self.assertEqual(RUNNER.classify_codex_unavailability(stdout, stderr), expected)

    def test_plan_writable_profile_selection_and_invalid_classifications(self) -> None:
        self.assertEqual(
            RUNNER.select_plan_writable_profile(
                {"implementation_risk": "low", "implementation_ambiguity": "low"}
            ),
            ("gpt-5.3-codex-spark", "medium"),
        )
        self.assertEqual(
            RUNNER.select_plan_writable_profile(
                {"implementation_risk": "ordinary", "implementation_ambiguity": "low"}
            ),
            ("gpt-5.6-terra", "medium"),
        )
        self.assertEqual(RUNNER.select_plan_writable_profile({}), ("gpt-5.6-terra", "medium"))
        invalid = (
            {"implementation_risk": "high", "implementation_ambiguity": "low"},
            {"implementation_risk": "low", "implementation_ambiguity": "high"},
            {"implementation_risk": "", "implementation_ambiguity": "low"},
            {"implementation_risk": "   ", "implementation_ambiguity": "low"},
            {"implementation_risk": ["low"], "implementation_ambiguity": "low"},
            {"implementation_risk": "unknown", "implementation_ambiguity": "low"},
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaisesRegex(RUNNER.RunnerError, "implementation"):
                    RUNNER.select_plan_writable_profile(values)

    def test_writable_model_and_reasoning_overrides_are_strict(self) -> None:
        self.assertEqual(RUNNER.require_writable_model("custom-writable", "preferred"), "custom-writable")
        self.assertEqual(RUNNER.require_reasoning_effort("high", "preferred"), "high")
        for model in (None, "", "   ", "gpt-5.6-sol", "GPT-5.6-SOL"):
            with self.subTest(model=model):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.require_writable_model(model, "preferred")
        for reasoning in (None, "", "   "):
            with self.subTest(reasoning=reasoning):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.require_reasoning_effort(reasoning, "preferred")

    def test_default_worker_stages_minimal_private_codex_home_under_scratch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_codex_home = root / "host-codex-home"
            host_codex_home.mkdir()
            (host_codex_home / "auth.json").write_text('{"token":"secret"}\n', encoding="utf-8")
            for excluded in ("config.toml", "history.jsonl", "models_cache.json"):
                (host_codex_home / excluded).write_text("excluded\n", encoding="utf-8")
            for excluded_dir in ("logs", "sessions", "skills", "hooks", "databases"):
                (host_codex_home / excluded_dir).mkdir()
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()

            with mock.patch.dict(os.environ, {"CODEX_HOME": str(host_codex_home)}):
                env = RUNNER.prepare_worker_environment(
                    source_repo=root / "source",
                    clone_dir=root / "clone",
                    scratch_dir=scratch_dir,
                    plan_rel="docs/plan/active/001-test.md",
                    extra_env=(),
                    include_codex_home=True,
                )

            staged_home = Path(env["CODEX_HOME"])
            self.assertEqual(staged_home, scratch_dir / "codex-home")
            self.assertEqual(staged_home.stat().st_mode & 0o777, 0o700)
            self.assertEqual({path.name for path in staged_home.iterdir()}, {"auth.json"})
            self.assertEqual((staged_home / "auth.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((staged_home / "auth.json").read_text(encoding="utf-8"), '{"token":"secret"}\n')

    def test_default_worker_fails_closed_when_host_auth_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_codex_home = root / "host-codex-home"
            host_codex_home.mkdir()
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(host_codex_home)}):
                with self.assertRaisesRegex(RUNNER.RunnerError, "default Codex worker requires an auth file"):
                    RUNNER.prepare_worker_environment(
                        source_repo=root / "source",
                        clone_dir=root / "clone",
                        scratch_dir=scratch_dir,
                        plan_rel="docs/plan/active/001-test.md",
                        extra_env=(),
                        include_codex_home=True,
                    )

    def test_custom_worker_does_not_receive_or_stage_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(root / "host-codex-home")}):
                env = RUNNER.prepare_worker_environment(
                    source_repo=root / "source",
                    clone_dir=root / "clone",
                    scratch_dir=scratch_dir,
                    plan_rel="docs/plan/active/001-test.md",
                    extra_env=(),
                    include_codex_home=False,
                )
            self.assertNotIn("CODEX_HOME", env)
            self.assertFalse((scratch_dir / "codex-home").exists())

    def test_worker_environment_routes_caches_to_scratch_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scratch_dir = root / "scratch"
            scratch_dir.mkdir()
            env = RUNNER.prepare_worker_environment(
                source_repo=root / "source",
                clone_dir=root / "clone",
                scratch_dir=scratch_dir,
                plan_rel="docs/plan/active/001-test.md",
                extra_env=(),
                include_codex_home=False,
            )
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(env["PYTHONPYCACHEPREFIX"], str(scratch_dir / "python-pycache"))
            self.assertEqual(env["PIP_CACHE_DIR"], str(scratch_dir / "pip-cache"))
            self.assertEqual(env["UV_CACHE_DIR"], str(scratch_dir / "uv-cache"))
            self.assertEqual(env["UV_PROJECT_ENVIRONMENT"], str(scratch_dir / "uv-project-environment"))
            self.assertEqual(len(env), len(set(env)))

    def test_workspace_temporary_directory_cleanup_removes_staged_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_codex_home = root / "host-codex-home"
            host_codex_home.mkdir()
            (host_codex_home / "auth.json").write_text("secret\n", encoding="utf-8")
            workspace_tmp = tempfile.TemporaryDirectory(dir=root)
            workspace = Path(workspace_tmp.name)
            scratch_dir = workspace / "scratch"
            scratch_dir.mkdir()
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(host_codex_home)}):
                staged_home = RUNNER.stage_codex_home(scratch_dir)
            self.assertTrue((staged_home / "auth.json").is_file())
            workspace_tmp.cleanup()
            self.assertFalse(workspace.exists())

    def test_runner_scripts_have_matching_executable_modes(self) -> None:
        root_mode = SCRIPT.stat().st_mode & 0o777
        template_mode = TEMPLATE_SCRIPT.stat().st_mode & 0o777
        self.assertEqual(root_mode, template_mode)
        self.assertTrue(root_mode & 0o111)

    def test_run_rejects_missing_prerequisites(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        cases = (
            ("git", ("run", plan_path, "--git-bin", "/missing/git")),
            ("bwrap", ("run", plan_path, "--bwrap-bin", "/missing/bwrap", "--worker-binary", sys.executable)),
            ("codex", ("run", plan_path, "--codex-bin", "/missing/codex")),
        )
        for label, argv in cases:
            with self.subTest(prerequisite=label):
                result = run_cli(repo, *argv)
                self.assertEqual(result.returncode, 1)
                self.assertIn("executable is unavailable", result.stderr)

    def test_run_refuses_dirty_source_repo(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must be clean", result.stderr)

    def test_run_rejects_reserved_worker_env_override(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        for env_key in ("HOME", f"{ENV_PREFIX}SOURCE_REPO"):
            with self.subTest(env_key=env_key):
                result, _output_dir, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
                    worker_env={env_key: "/tmp/override"},
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("must not override reserved environment variable", result.stderr)

    def test_run_and_apply_in_scope_patch(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt", "dir/nested.txt"],
            files={"allowed.txt": "original\n", "dir/nested.txt": "before\n"},
        )
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _worker_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "allowed.txt").write_text("updated\\n", encoding="utf-8")
                target = worker_repo / "dir" / "nested.txt"
                target.write_text("created\\n", encoding="utf-8")
                (scratch_dir / "note.txt").write_text(plan_path + "\\n", encoding="utf-8")
                """
            ),
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt", "dir/nested.txt"])
        self.assertEqual(manifest["worker_result"]["kind"], "custom")
        self.assertNotIn("attempts", manifest["worker_result"])
        self.assertNotIn("fallback_reason", manifest["worker_result"])
        receipt_path = Path(manifest["worker_completion_receipt_path"])
        receipt_bytes = receipt_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(receipt_bytes).hexdigest(),
            manifest["worker_completion_receipt_digest"],
        )
        receipt = RUNNER.load_worker_completion_receipt(receipt_bytes)
        lifecycle = json.loads(Path(manifest["lifecycle_state_path"]).read_text(encoding="utf-8"))
        contract = json.loads(Path(manifest["worker_contract_path"]).read_text(encoding="utf-8"))
        self.assertEqual(
            {
                manifest["plan_execution_attempt_id"],
                lifecycle["plan_execution_attempt_id"],
                contract["plan_execution_attempt_id"],
                receipt["plan_execution_attempt_id"],
            },
            {manifest["plan_execution_attempt_id"]},
        )
        self.assertEqual(receipt["process"], {"exit_status": 0, "diagnostic_codes": []})
        self.assertTrue(receipt["attempt"]["attempt_id"].startswith("initial-0-custom-"))
        self.assertEqual(receipt["candidate"]["changed_paths"], manifest["changed_paths"])
        self.assertEqual(
            receipt["candidate"]["patch_digest"], "sha256:" + manifest["patch_digest"]
        )
        self.assertEqual(receipt["claims"]["attempt_result"], "success")
        process_path = Path(manifest["worker_process_result_path"])
        process_bytes = process_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(process_bytes).hexdigest(), manifest["worker_process_result_digest"]
        )
        process_result = RUNNER.validate_attempt_process_result(json.loads(process_bytes))
        self.assertEqual(process_result["attempt_id"], receipt["attempt"]["attempt_id"])
        self.assertEqual(process_result["exit_status"], receipt["process"]["exit_status"])
        telemetry = manifest["telemetry"]
        self.assertEqual(
            {key: telemetry[key] for key in (
                "schema_version",
                "model_starts",
                "availability_failures",
                "skipped_known_unavailable_starts",
                "candidate_generations",
                "full_validation_count",
                "implementation_risk",
                "implementation_ambiguity",
            )},
            {
                "schema_version": 1,
                "model_starts": 0,
                "availability_failures": 0,
                "skipped_known_unavailable_starts": 0,
                "candidate_generations": 1,
                "full_validation_count": 0,
                "implementation_risk": "low",
                "implementation_ambiguity": "low",
            },
        )
        self.assertEqual(len(telemetry["attempt_durations_seconds"]), 1)
        self.assertGreaterEqual(telemetry["attempt_durations_seconds"][0], 0)
        self.assertGreaterEqual(telemetry["runner_duration_seconds"], telemetry["attempt_durations_seconds"][0])
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        self.assertEqual((repo / "dir" / "nested.txt").read_text(encoding="utf-8"), "before\n")
        manifest["bounded_padding"] = "x" * 70_000
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.assertGreater(manifest_path.stat().st_size, 65_536)
        lifecycle["current_manifest_digest"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        Path(manifest["lifecycle_state_path"]).write_text(
            json.dumps(lifecycle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "updated\n")
        self.assertEqual((repo / "dir" / "nested.txt").read_text(encoding="utf-8"), "created\n")
        self.assertEqual(git(repo, "diff", "--cached", "--name-only").stdout.strip(), "")
        self.assertEqual(
            git(repo, "status", "--porcelain=1", "--untracked-files=all").stdout.splitlines(),
            [" M allowed.txt", " M dir/nested.txt"],
        )
        git(repo, "add", "allowed.txt", "dir/nested.txt")
        git(repo, "commit", "-qm", "accept exact candidate")
        accepted_head = git(repo, "rev-parse", "HEAD").stdout.strip()
        lifecycle_path = Path(manifest["lifecycle_state_path"])
        lifecycle_bytes = lifecycle_path.read_bytes()
        execution_state = lifecycle_path.with_name(
            lifecycle_path.name
            + f".{manifest['orchestration_run_id']}.plan-execution.json"
        )
        execution_payload = json.loads(execution_state.read_text(encoding="utf-8"))
        closed = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts/plan-execution-state.py"),
                "close", str(execution_state),
                "--run-id", manifest["orchestration_run_id"],
                "--attempt-id", manifest["plan_execution_attempt_id"],
                "--outcome", "accepted", "--review-author", "parent",
                "--review-evidence-digest", "sha256:" + hashlib.sha256(b"accepted").hexdigest(),
                "--invariant-digest", execution_payload["primary_invariant_digest"],
                "--candidate-digest", "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "--candidate-manifest", str(manifest_path),
                "--candidate-lifecycle-digest", "sha256:" + hashlib.sha256(lifecycle_bytes).hexdigest(),
                "--accepted-source-head", accepted_head,
                "--lifecycle-state", str(lifecycle_path),
            ],
            cwd=repo, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(closed.returncode, 0)
        self.assertIn("accepted candidate identity lacks a bounded review", closed.stderr)

    def test_malformed_completion_claims_fail_closed_without_retaining_prohibited_content(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "malformed-completion-claims"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")
                claims = Path(os.environ[prefix + "COMPLETION_CLAIMS"])
                claims.write_text(json.dumps({
                    "attempt_result": "success",
                    "acceptance_evidence": [],
                    "commands_attempted": [],
                    "blockers": ["CREDENTIAL_SENTINEL"],
                    "residual_risks": [],
                    "out_of_scope_change": False,
                }), encoding="utf-8")
                """
            ),
            output_dir=output,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("completion claims were rejected", result.stderr)
        receipt_bytes = (output / "worker-completion-receipt.json").read_bytes()
        self.assertNotIn(b"CREDENTIAL_SENTINEL", receipt_bytes)
        receipt = RUNNER.load_worker_completion_receipt(receipt_bytes)
        self.assertEqual(receipt["claims"]["attempt_result"], "failure")
        self.assertEqual(receipt["process"]["exit_status"], 0)
        process_result = RUNNER.validate_attempt_process_result(
            json.loads((output / "worker-process-result.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(process_result["exit_status"], 0)
        self.assertEqual(process_result["attempt_id"], receipt["attempt"]["attempt_id"])
        self.assertFalse((output / "candidate.patch").exists())
        self.assertFalse((output / "manifest.json").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_worker_completion_claim_tampering_cannot_advance_candidate_lifecycle(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        receipt_path = Path(manifest["worker_completion_receipt_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["claims"]["attempt_result"] = "failure"
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("receipt digest no longer matches", apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        self.assertFalse((output / "validation.json").exists())

    def test_completion_claim_codes_reject_lowercase_token_shaped_secrets(self) -> None:
        base = {
            "attempt_result": "failure",
            "acceptance_evidence": [],
            "commands_attempted": [],
            "blockers": [],
            "residual_risks": [],
            "out_of_scope_change": False,
        }
        for field, value in (
            ("blockers", "credential_sentinel"),
            ("residual_risks", "a" * 64),
        ):
            with self.subTest(field=field, value=value):
                claims = {**base, field: [value]}
                with self.assertRaisesRegex(RUNNER.RunnerError, "non-allowlisted"):
                    RUNNER.validate_worker_completion_claims(claims)

    def test_completion_command_claims_are_consecutive_and_status_bounded(self) -> None:
        base = {
            "attempt_result": "failure",
            "acceptance_evidence": [],
            "blockers": ["command_failed"],
            "residual_risks": [],
            "out_of_scope_change": False,
        }
        cases = (
            [{"command_id": "worker-check-2", "exit_status": 1}],
            [{"command_id": "worker-check-1", "exit_status": 256}],
            [{"command_id": "worker-check-1", "exit_status": 10**100}],
        )
        for commands in cases:
            with self.subTest(commands=commands):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.validate_worker_completion_claims(
                        {**base, "commands_attempted": commands}
                    )

    def test_pathological_completion_claims_still_emit_safe_receipts(self) -> None:
        cases = {
            "huge-integer": (
                '{"attempt_result":"success","acceptance_evidence":[],"commands_attempted":'
                '[{"command_id":"worker-check-1","exit_status":' + "9" * 5000 + '}],'
                '"blockers":[],"residual_risks":[],"out_of_scope_change":false}'
            ),
            "deep-nesting": "[" * 1500 + "0" + "]" * 1500,
        }
        for name, raw_claims in cases.items():
            with self.subTest(name=name):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"], repo_name=name)
                self.addCleanup(temporary.cleanup)
                output = Path(temporary.name) / f"pathological-{name}"
                result, _output, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    textwrap.dedent(
                        f"""\
                        (worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")
                        Path(os.environ[prefix + "COMPLETION_CLAIMS"]).write_text(
                            {raw_claims!r}, encoding="utf-8"
                        )
                        """
                    ),
                    output_dir=output,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("completion claims were rejected", result.stderr)
                receipt = RUNNER.load_worker_completion_receipt(
                    (output / "worker-completion-receipt.json").read_bytes()
                )
                self.assertEqual(receipt["claims"]["blockers"], ["invalid_completion_claims"])
                self.assertTrue((output / "worker-process-result.json").is_file())

    def test_worker_reported_failure_keeps_parent_derived_candidate_binding(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "reported-failure-candidate"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                import hashlib
                import json
                (worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")
                contract = json.loads(Path(os.environ[prefix + "WORKER_CONTRACT"]).read_text(encoding="utf-8"))
                evidence = [
                    {"acceptance_digest": "sha256:" + hashlib.sha256(item.encode()).hexdigest(), "claim": "not_satisfied"}
                    for item in contract["acceptance"]
                ]
                Path(os.environ[prefix + "COMPLETION_CLAIMS"]).write_text(json.dumps({
                    "attempt_result": "failure",
                    "acceptance_evidence": evidence,
                    "commands_attempted": [],
                    "blockers": ["implementation_failed"],
                    "residual_risks": ["incomplete_change"],
                    "out_of_scope_change": False,
                }), encoding="utf-8")
                """
            ),
            output_dir=output,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("receipt reports failure", result.stderr)
        receipt = RUNNER.load_worker_completion_receipt(
            (output / "worker-completion-receipt.json").read_bytes()
        )
        patch_bytes = (output / "candidate.patch").read_bytes()
        self.assertEqual(
            receipt["candidate"]["patch_digest"],
            "sha256:" + hashlib.sha256(patch_bytes).hexdigest(),
        )
        self.assertEqual(receipt["candidate"]["changed_paths"], ["allowed.txt"])
        self.assertEqual(receipt["claims"]["attempt_result"], "failure")
        self.assertFalse((output / "manifest.json").exists())

    def test_worker_reported_failure_without_candidate_keeps_receipt_and_process_result(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "reported-failure-without-candidate"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                import json
                Path(os.environ[prefix + "COMPLETION_CLAIMS"]).write_text(json.dumps({
                    "attempt_result": "failure",
                    "acceptance_evidence": [],
                    "commands_attempted": [],
                    "blockers": ["implementation_failed"],
                    "residual_risks": ["incomplete_change"],
                    "out_of_scope_change": False,
                }), encoding="utf-8")
                raise SystemExit(7)
                """
            ),
            output_dir=output,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("worker exited with 7", result.stderr)
        receipt = RUNNER.load_worker_completion_receipt(
            (output / "worker-completion-receipt.json").read_bytes()
        )
        self.assertIsNone(receipt["candidate"])
        self.assertEqual(receipt["claims"]["attempt_result"], "failure")
        self.assertEqual(receipt["claims"]["acceptance_evidence"], [])
        process_result = RUNNER.validate_attempt_process_result(
            json.loads((output / "worker-process-result.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(process_result["exit_status"], 7)
        self.assertEqual(process_result["attempt_id"], receipt["attempt"]["attempt_id"])
        self.assertFalse((output / "candidate.patch").exists())
        self.assertFalse((output / "manifest.json").exists())

    def test_malformed_correction_claims_do_not_publish_an_unbound_patch(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial\\n", encoding="utf-8")',
            output_dir=root / "malformed-correction-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        brief = root / "malformed-correction-brief.txt"
        brief.write_text("Correct the candidate.\n", encoding="utf-8")
        output = root / "malformed-correction-output"
        correction = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            textwrap.dedent(
                """\
                (worker_repo / "allowed.txt").write_text("corrected\\n", encoding="utf-8")
                Path(os.environ[prefix + "COMPLETION_CLAIMS"]).write_text(
                    '{"attempt_result":"success","acceptance_evidence":[],"commands_attempted":'
                    '[{"command_id":"worker-check-1","exit_status":' + "9" * 5000 + '}],'
                    '"blockers":[],"residual_risks":[],"out_of_scope_change":false}',
                    encoding="utf-8",
                )
                """
            ),
            output_dir=output,
        )
        self.assertEqual(correction.returncode, 1)
        self.assertIn("correction completion claims were rejected", correction.stderr)
        receipt = RUNNER.load_worker_completion_receipt(
            (output / "worker-completion-receipt.json").read_bytes()
        )
        self.assertIsNone(receipt["candidate"])
        self.assertEqual(receipt["claims"]["blockers"], ["invalid_completion_claims"])
        self.assertTrue((output / "worker-process-result.json").is_file())
        self.assertFalse((output / "candidate.patch").exists())
        self.assertFalse((output / "manifest.json").exists())

    def test_open_attempt_blocks_same_run_regeneration_and_fresh_run_rejects_replayed_receipt(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        lifecycle = root / "same-run.lifecycle.json"
        common = (
            "--lifecycle-state", str(lifecycle),
            "--orchestration-run-id", "same-run-replay-test",
        )
        first, first_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            "raise SystemExit(7)",
            output_dir=root / "first-failure",
            extra_args=common,
        )
        self.assertEqual(first.returncode, 1)
        first_receipt_bytes = (first_output / "worker-completion-receipt.json").read_bytes()
        first_receipt = RUNNER.load_worker_completion_receipt(first_receipt_bytes)
        blocked, _blocked_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "blocked-regeneration",
            extra_args=common,
        )
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("already open", blocked.stderr)
        execution_state = lifecycle.with_name(
            lifecycle.name + ".same-run-replay-test.plan-execution.json"
        )
        execution_payload = json.loads(execution_state.read_text(encoding="utf-8"))
        closed = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts/plan-execution-state.py"),
                "close", str(execution_state), "--run-id", "same-run-replay-test",
                "--attempt-id", execution_payload["open_attempt_id"],
                "--outcome", "rejected", "--review-author", "parent",
                "--review-reason-code", "evidence_incomplete",
                "--review-evidence-digest", "sha256:" + hashlib.sha256(
                    b"first failure review"
                ).hexdigest(),
                "--invariant-digest", execution_payload["primary_invariant_digest"],
                "--lifecycle-state", str(lifecycle),
            ],
            cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        fresh_lifecycle = root / "fresh-run.lifecycle.json"
        second, _second_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "second-success",
            extra_args=(
                "--lifecycle-state", str(fresh_lifecycle),
                "--orchestration-run-id", "fresh-run-replay-test",
            ),
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        manifest_path = Path(second.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        second_receipt_path = Path(manifest["worker_completion_receipt_path"])
        second_receipt = RUNNER.load_worker_completion_receipt(second_receipt_path.read_bytes())
        self.assertNotEqual(
            first_receipt["attempt"]["attempt_id"], second_receipt["attempt"]["attempt_id"]
        )
        second_receipt_path.write_bytes(first_receipt_bytes)
        manifest["worker_completion_receipt_digest"] = hashlib.sha256(
            first_receipt_bytes
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("worker contract digest mismatch", apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_explicit_missing_file_preserves_absence_until_worker_creation(self) -> None:
        for action in ("create", "noop"):
            with self.subTest(action=action):
                temporary, repo, plan_path = self.make_repo(
                    ["dir/new.txt"],
                    files={"dir/existing.txt": "existing\n"},
                    repo_name=f"missing-{action}",
                )
                self.addCleanup(temporary.cleanup)
                body = textwrap.dedent(
                    """\
                    clone_target = worker_repo / "dir/new.txt"
                    staged_target = new_file_root / "dir/new.txt"
                    if clone_target.exists() or staged_target.exists():
                        raise SystemExit("missing path was materialized before worker creation")
                    """
                )
                if action == "create":
                    body += 'staged_target.write_text("created\\n", encoding="utf-8")\n'
                result, _output, _worker = self.run_with_worker(repo, plan_path, body)
                self.assertFalse((repo / "dir/new.txt").exists())
                if action == "noop":
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("worker produced no candidate changes", result.stderr)
                    continue
                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
                self.assertEqual(manifest["changed_paths"], ["dir/new.txt"])
                applied = run_cli(repo, "apply", result.stdout.strip())
                self.assertEqual(applied.returncode, 0, applied.stderr)
                self.assertEqual((repo / "dir/new.txt").read_text(encoding="utf-8"), "created\n")

    def test_changed_path_derivation_keeps_candidate_blobs_out_of_source_objects(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        candidate_content = b"unique path-derivation candidate\n"
        (repo / "allowed.txt").write_bytes(candidate_content)
        patch_path = Path(temporary.name) / "candidate.patch"
        patch_path.write_bytes(git(repo, "diff", "--binary", "HEAD").stdout.encode("utf-8"))
        before = object_database_snapshot(repo)
        candidate_oid = subprocess.run(
            ["git", "hash-object", "--stdin"],
            cwd=repo,
            input=candidate_content,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.decode("ascii").strip()

        self.assertEqual(
            RUNNER.derive_changed_paths_from_patch(repo, "git", patch_path.read_bytes(), git(repo, "rev-parse", "HEAD").stdout.strip()),
            ["allowed.txt"],
        )
        self.assertEqual(object_database_snapshot(repo), before)
        self.assertNotIn(f"{candidate_oid[:2]}/{candidate_oid[2:]}", before)

    def test_manifest_generation_isolated_for_colon_path_alternate_and_ambient_git_overrides(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            repo_name="repo:候補",
        )
        self.addCleanup(temporary.cleanup)
        source_objects = object_directory(repo)
        alternate = Path(temporary.name) / "alternate:既存"
        alternate.mkdir()
        (source_objects / "info").mkdir(exist_ok=True)
        (source_objects / "info" / "alternates").write_text(f"{alternate}\n", encoding="utf-8")
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repo,
            env={**os.environ, "GIT_OBJECT_DIRECTORY": str(alternate)},
            input=b"existing alternate object\n",
            stdout=subprocess.PIPE,
            check=True,
        )
        before = object_database_snapshot(repo)
        output_dir = Path(temporary.name) / "artifacts"
        ambient_objects = Path(temporary.name) / "ambient-objects"
        ambient_git_dir = Path(temporary.name) / "ambient-git-dir"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("unique colon candidate\\n", encoding="utf-8")',
            output_dir=output_dir,
            parent_env={
                "GIT_OBJECT_DIRECTORY": str(ambient_objects),
                "GIT_DIR": str(ambient_git_dir),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(RUNNER.resolve_source_object_directory(repo, "git"), source_objects)
        self.assertEqual(object_database_snapshot(repo), before)
        self.assertFalse(ambient_objects.exists())
        quoted = RUNNER.git_c_quote_path(source_objects)
        self.assertTrue(quoted.startswith('"') and quoted.endswith('"'))
        self.assertIn(":", quoted)

    def test_manifest_generation_from_linked_worktree_keeps_common_objects_clean(self) -> None:
        temporary, main_repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        linked_repo = Path(temporary.name) / "linked:worktree"
        git(main_repo, "worktree", "add", "-q", "-b", "linked", str(linked_repo))
        before = object_database_snapshot(main_repo)
        output_dir = Path(temporary.name) / "linked-artifacts"
        result, _output, _worker = self.run_with_worker(
            linked_repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("unique linked candidate\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(object_directory(linked_repo), object_directory(main_repo))
        self.assertEqual(object_database_snapshot(main_repo), before)

    def test_rejected_apply_preflight_keeps_source_objects_clean(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "preflight-artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("unique rejected candidate\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["changed_paths"] = ["unexpected.txt"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        before = object_database_snapshot(repo)
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("changed paths do not match", apply.stderr)
        self.assertEqual(object_database_snapshot(repo), before)

    def test_preferred_codex_success_does_not_start_fallback(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "preferred-output"
        result = self.run_with_fake_codex(
            repo, plan_path, "primary_success", output_dir=output_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        worker_result = manifest["worker_result"]
        self.assertEqual(worker_result["selected_attempt"], "primary")
        self.assertNotIn("fallback_reason", worker_result)
        self.assertEqual(
            [(attempt["model"], attempt["reasoning_effort"], attempt["selected"]) for attempt in worker_result["attempts"]],
            [("gpt-5.3-codex-spark", "medium", True)],
        )
        self.assertFalse((output_dir / "worker-fallback.stdout").exists())

    def test_ordinary_plan_selects_terra_and_explicit_override_is_honored(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        plan = repo / plan_path
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("implementation_risk: low", "implementation_risk: ordinary"),
            encoding="utf-8",
        )
        git(repo, "add", plan_path)
        git(repo, "commit", "-qm", "ordinary classification")
        terra_output = Path(temporary.name) / "terra-output"
        terra = self.run_with_fake_codex(
            repo,
            plan_path,
            "primary_success",
            output_dir=terra_output,
            fake_env={"FAKE_PRIMARY_MODEL": "gpt-5.6-terra"},
        )
        self.assertEqual(terra.returncode, 0, terra.stderr)
        terra_manifest = json.loads(Path(terra.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(terra_manifest["worker_result"]["attempts"][0]["model"], "gpt-5.6-terra")

        override_output = Path(temporary.name) / "override-output"
        override = self.run_with_fake_codex(
            repo,
            plan_path,
            "primary_success",
            output_dir=override_output,
            extra_args=(
                "--codex-model",
                "custom-writable",
                "--codex-reasoning-effort",
                "high",
            ),
            fake_env={"FAKE_PRIMARY_MODEL": "custom-writable", "FAKE_PRIMARY_REASONING": "high"},
        )
        self.assertEqual(override.returncode, 0, override.stderr)
        override_manifest = json.loads(Path(override.stdout.strip()).read_text(encoding="utf-8"))
        attempt = override_manifest["worker_result"]["attempts"][0]
        self.assertEqual((attempt["model"], attempt["reasoning_effort"]), ("custom-writable", "high"))

    def test_cli_refuses_high_classifications_blank_values_and_writable_sol(self) -> None:
        classification_cases = (
            ("implementation_risk: low", "implementation_risk: high"),
            ("implementation_ambiguity: low", "implementation_ambiguity: high"),
            ("implementation_risk: low", "implementation_risk:"),
            ("implementation_risk: low", "implementation_risk:\n  - low"),
            ("implementation_risk: low", "implementation_risk: unknown"),
        )
        for index, (before, after) in enumerate(classification_cases):
            with self.subTest(classification=after):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"])
                self.addCleanup(temporary.cleanup)
                plan = repo / plan_path
                plan.write_text(plan.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
                git(repo, "add", plan_path)
                git(repo, "commit", "-qm", f"invalid classification {index}")
                result, output_dir, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    '(worker_repo / "allowed.txt").write_text("must not run\\n", encoding="utf-8")',
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("implementation_", result.stderr)
                self.assertFalse((output_dir / "candidate.patch").exists())

        override_cases = (
            ("--codex-model", ""),
            ("--codex-reasoning-effort", "  "),
            ("--codex-model", "gpt-5.6-sol"),
            ("--fallback-codex-model", "GPT-5.6-SOL"),
        )
        for index, override in enumerate(override_cases):
            with self.subTest(override=override):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"])
                self.addCleanup(temporary.cleanup)
                output_dir = Path(temporary.name) / f"rejected-override-{index}"
                result = self.run_with_fake_codex(
                    repo,
                    plan_path,
                    "primary_success",
                    output_dir=output_dir,
                    extra_args=override,
                )
                self.assertEqual(result.returncode, 1)
                self.assertRegex(result.stderr, "non-empty|reserved for independent review")
                self.assertFalse((output_dir / "worker-primary.stdout").exists())

    def test_unavailable_preferred_codex_uses_fresh_fallback_clone_and_records_provenance(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "fallback-output"
        result = self.run_with_fake_codex(
            repo, plan_path, "unavailable_then_success", output_dir=output_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        worker_result = manifest["worker_result"]
        self.assertEqual(worker_result["selected_attempt"], "fallback")
        self.assertEqual(worker_result["fallback_reason"], "usage_limit")
        self.assertEqual(
            [
                (attempt["label"], attempt["model"], attempt["reasoning_effort"], attempt["returncode"], attempt["selected"])
                for attempt in worker_result["attempts"]
            ],
            [
                ("primary", "gpt-5.3-codex-spark", "medium", 1, False),
                ("fallback", "gpt-5.6-luna", "max", 0, True),
            ],
        )
        for attempt in worker_result["attempts"]:
            self.assertEqual(len(attempt["stdout_digest"]), 64)
            self.assertEqual(len(attempt["stderr_digest"]), 64)
            self.assertNotIn("usage limit", json.dumps(attempt).lower())
        self.assertFalse((output_dir / "worker-primary-last-message.txt").exists())
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "fallback\n")

    def test_availability_state_records_and_skips_preferred_with_bounded_telemetry(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        state_path = Path(temporary.name) / "availability.json"
        common_args = (
            "--availability-state",
            str(state_path),
            "--orchestration-run-id",
            "run-routing-001",
        )
        first_output = Path(temporary.name) / "availability-first"
        first = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=first_output,
            extra_args=common_args,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state,
            {
                "schema_version": 1,
                "orchestration_run_id": "run-routing-001",
                "unavailable_models": [
                    {"model": "gpt-5.3-codex-spark", "reason": "usage_limit"}
                ],
            },
        )
        self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("prompt", json.dumps(state).lower())
        self.assertNotIn("credential", json.dumps(state).lower())
        first_manifest = json.loads(Path(first.stdout.strip()).read_text(encoding="utf-8"))
        first_telemetry = first_manifest["telemetry"]
        self.assertEqual(first_telemetry["model_starts"], 2)
        self.assertEqual(first_telemetry["availability_failures"], 1)
        self.assertEqual(first_telemetry["skipped_known_unavailable_starts"], 0)
        self.assertEqual(first_telemetry["candidate_generations"], 1)
        self.assertEqual(first_telemetry["full_validation_count"], 0)
        self.assertEqual(len(first_telemetry["attempt_durations_seconds"]), 2)

        second_output = Path(temporary.name) / "availability-second"
        second = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=second_output,
            extra_args=common_args,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        second_manifest = json.loads(Path(second.stdout.strip()).read_text(encoding="utf-8"))
        attempts = second_manifest["worker_result"]["attempts"]
        self.assertEqual([(item["label"], item["model"]) for item in attempts], [("fallback", "gpt-5.6-luna")])
        second_telemetry = second_manifest["telemetry"]
        self.assertEqual(second_telemetry["model_starts"], 1)
        self.assertEqual(second_telemetry["availability_failures"], 0)
        self.assertEqual(second_telemetry["skipped_known_unavailable_starts"], 1)
        self.assertEqual(len(second_telemetry["attempt_durations_seconds"]), 1)
        for value in [
            second_telemetry["runner_duration_seconds"],
            *second_telemetry["attempt_durations_seconds"],
        ]:
            self.assertIsInstance(value, (int, float))
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, RUNNER.TELEMETRY_MAX_DURATION_SECONDS)

    def test_availability_state_records_fallback_failure_and_skips_both_models(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        state_path = Path(temporary.name) / "both-unavailable.json"
        args = (
            "--availability-state",
            str(state_path),
            "--orchestration-run-id",
            "run-both-unavailable",
        )
        first_output = Path(temporary.name) / "both-first"
        first = self.run_with_fake_codex(
            repo,
            plan_path,
            "both_unavailable",
            output_dir=first_output,
            extra_args=args,
        )
        self.assertEqual(first.returncode, 1)
        self.assertIn("fallback worker exited", first.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["unavailable_models"],
            [
                {"model": "gpt-5.3-codex-spark", "reason": "usage_limit"},
                {"model": "gpt-5.6-luna", "reason": "rate_limit"},
            ],
        )
        second_output = Path(temporary.name) / "both-second"
        second = self.run_with_fake_codex(
            repo,
            plan_path,
            "both_unavailable",
            output_dir=second_output,
            extra_args=args,
        )
        self.assertEqual(second.returncode, 1)
        self.assertIn("already recorded unavailable", second.stderr)
        self.assertFalse((second_output / "worker-primary.stdout").exists())
        self.assertFalse((second_output / "worker-fallback.stdout").exists())

    def test_known_unavailable_fallback_is_skipped_after_one_preferred_start(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        state_path = Path(temporary.name) / "fallback-known.json"
        self.write_availability_state(
            state_path,
            "run-fallback-known",
            [{"model": "gpt-5.6-luna", "reason": "rate_limit"}],
        )
        output_dir = Path(temporary.name) / "fallback-known-output"
        result = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=output_dir,
            extra_args=(
                "--availability-state",
                str(state_path),
                "--orchestration-run-id",
                "run-fallback-known",
            ),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("already recorded unavailable", result.stderr)
        self.assertTrue((output_dir / "worker-primary.stdout").is_file())
        self.assertFalse((output_dir / "worker-fallback.stdout").exists())
        entries = json.loads(state_path.read_text(encoding="utf-8"))["unavailable_models"]
        self.assertEqual({entry["model"] for entry in entries}, {"gpt-5.3-codex-spark", "gpt-5.6-luna"})

    def test_availability_state_schema_identity_and_size_bounds_fail_closed(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        cases: list[tuple[str, object, str]] = [
            ("schema", {"schema_version": 2, "orchestration_run_id": "run", "unavailable_models": []}, "schema version"),
            ("shape", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [], "extra": True}, "field shape"),
            ("entries-type", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": {}}, "must be a list"),
            ("duplicates", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m", "reason": "usage_limit"}, {"model": "m", "reason": "rate_limit"}]}, "duplicate model"),
            ("entry-shape", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m", "reason": "usage_limit", "raw": "secret"}]}, "field shape"),
            ("reason", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m", "reason": "validation"}]}, "availability code"),
            ("model-bound", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": "m" * 129, "reason": "usage_limit"}]}, "byte bound"),
            ("count-bound", {"schema_version": 1, "orchestration_run_id": "run", "unavailable_models": [{"model": f"m-{index}", "reason": "usage_limit"} for index in range(17)]}, "entry-count"),
        ]
        for label, payload, message in cases:
            with self.subTest(case=label):
                path = root / f"invalid-{label}.json"
                path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(RUNNER.RunnerError, message):
                    RUNNER.open_availability_state(repo, str(path), "run")

        oversized = root / "oversized.json"
        oversized.write_bytes(b"x" * (RUNNER.AVAILABILITY_STATE_MAX_BYTES + 1))
        with self.assertRaisesRegex(RUNNER.RunnerError, "byte bound"):
            RUNNER.open_availability_state(repo, str(oversized), "run")
        valid = root / "different-run.json"
        self.write_availability_state(valid, "run-a", [])
        with self.assertRaisesRegex(RUNNER.RunnerError, "different orchestration run"):
            RUNNER.open_availability_state(repo, str(valid), "run-b")
        for run_id in ("", "   ", "r" * 129):
            with self.subTest(run_id=run_id):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.open_availability_state(repo, str(root / "missing.json"), run_id)

    def test_availability_state_rejects_symlinks_and_target_swap(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        real = root / "real.json"
        self.write_availability_state(real, "run", [])
        target_link = root / "target-link.json"
        target_link.symlink_to(real)
        with self.assertRaisesRegex(RUNNER.RunnerError, "symlink"):
            RUNNER.open_availability_state(repo, str(target_link), "run")
        real_parent = root / "real-parent"
        real_parent.mkdir()
        ancestor_link = root / "ancestor-link"
        ancestor_link.symlink_to(real_parent, target_is_directory=True)
        with self.assertRaisesRegex(RUNNER.RunnerError, "ancestor"):
            RUNNER.open_availability_state(repo, str(ancestor_link / "state.json"), "run")
        with self.assertRaisesRegex(RUNNER.RunnerError, "outside"):
            RUNNER.open_availability_state(repo, str(repo / "state.json"), "run")

        swapped = root / "swapped.json"
        self.write_availability_state(swapped, "run", [])
        with RUNNER.open_availability_state(repo, str(swapped), "run") as state:
            swapped.unlink()
            swapped.write_text("attacker\n", encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.RunnerError, "target changed"):
                state.record("model-a", "usage_limit")
        self.assertEqual(swapped.read_text(encoding="utf-8"), "attacker\n")

    def test_availability_state_parent_fd_does_not_follow_parent_swap(self) -> None:
        temporary, repo, _plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        parent = root / "state-parent"
        parent.mkdir()
        moved_parent = root / "state-parent-original"
        attacker = root / "attacker"
        attacker.mkdir()
        with RUNNER.open_availability_state(repo, str(parent / "state.json"), "run-parent") as state:
            parent.rename(moved_parent)
            parent.symlink_to(attacker, target_is_directory=True)
            state.record("model-a", "usage_limit")
        self.assertTrue((moved_parent / "state.json").is_file())
        self.assertFalse((attacker / "state.json").exists())

    def test_telemetry_duration_bounds_are_finite_and_nonnegative(self) -> None:
        self.assertEqual(RUNNER.bounded_duration(4.0, 4.0), 0.0)
        self.assertEqual(RUNNER.bounded_duration(1.0, 2.5), 1.5)
        for started, finished in (
            (2.0, 1.0),
            (0.0, math.inf),
            (0.0, math.nan),
            (0.0, RUNNER.TELEMETRY_MAX_DURATION_SECONDS + 1),
        ):
            with self.subTest(started=started, finished=finished):
                with self.assertRaisesRegex(RUNNER.RunnerError, "finite nonnegative"):
                    RUNNER.bounded_duration(started, finished)

    def test_availability_state_path_and_run_identifier_must_be_paired(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_root = Path(temporary.name)
        cases = (("--availability-state", str(output_root / "state.json")),)
        for index, extra_args in enumerate(cases):
            with self.subTest(extra_args=extra_args):
                worker = output_root / f"paired-worker-{index}.py"
                write_worker(
                    worker,
                    '(worker_repo / "allowed.txt").write_text("must-not-run\\n", encoding="utf-8")',
                )
                command = [
                    "run",
                    plan_path,
                    "--output-dir",
                    str(output_root / f"pair-cli-{index}"),
                    "--worker-binary",
                    sys.executable,
                    "--worker-arg",
                    str(worker),
                    *extra_args,
                ]
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        *command,
                        "--lifecycle-state",
                        str(output_root / "lifecycle.json"),
                    ],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("orchestration-run-id", result.stderr)
                self.assertFalse((output_root / f"pair-cli-{index}" / "candidate.patch").exists())

    def test_correction_emits_verified_aggregate_patch_without_mutating_source_or_objects(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial_output = root / "initial-output"
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial candidate\\n", encoding="utf-8")',
            output_dir=initial_output,
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        prior_manifest = Path(initial.stdout.strip())
        prior_manifest_digest = RUNNER.hash_file(prior_manifest)
        prior_patch_digest = RUNNER.hash_file(initial_output / "candidate.patch")
        brief = root / "correction.txt"
        brief.write_text("Replace the candidate marker with the corrected marker.\n", encoding="utf-8")
        before_objects = object_database_snapshot(repo)
        correction_output = root / "correction-output"
        correction = self.run_correction_with_worker(
            repo,
            plan_path,
            prior_manifest,
            brief,
            textwrap.dedent(
                """\
                brief = Path(os.environ[prefix + "CORRECTION_BRIEF"])
                if brief.read_text(encoding="utf-8") != "Replace the candidate marker with the corrected marker.\\n":
                    raise SystemExit("correction brief mismatch")
                try:
                    brief.write_text("tamper\\n", encoding="utf-8")
                except OSError:
                    pass
                else:
                    raise SystemExit("correction brief was writable")
                if (worker_repo / "allowed.txt").read_text(encoding="utf-8") != "initial candidate\\n":
                    raise SystemExit("verified prior patch was not applied")
                forbidden = Path(os.environ["FORBIDDEN_PRIOR"])
                if forbidden.exists():
                    raise SystemExit("prior attempt state is visible")
                (worker_repo / "allowed.txt").write_text("corrected candidate\\n", encoding="utf-8")
                """
            ),
            output_dir=correction_output,
            worker_env={"FORBIDDEN_PRIOR": str(initial_output / "worker.stdout")},
        )
        self.assertEqual(correction.returncode, 0, correction.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        self.assertEqual(object_database_snapshot(repo), before_objects)
        manifest_path = Path(correction.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])
        self.assertEqual(
            manifest["correction_lineage"],
            {
                "prior_manifest_digest": prior_manifest_digest,
                "prior_patch_digest": prior_patch_digest,
                "correction_round": 1,
                "correction_brief_digest": RUNNER.hash_file(brief),
            },
        )
        receipt = RUNNER.load_worker_completion_receipt(
            Path(manifest["worker_completion_receipt_path"]).read_bytes()
        )
        self.assertEqual(receipt["attempt"]["attempt_kind"], "correction")
        self.assertEqual(receipt["attempt"]["correction_round"], 1)
        self.assertEqual(
            receipt["attempt"]["correction_lineage"]["prior_manifest_digest"],
            "sha256:" + prior_manifest_digest,
        )
        self.assertNotIn("Replace the candidate", json.dumps(manifest))
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "corrected candidate\n")

    def test_correction_lineage_allows_one_round_and_rejects_second(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("round zero\\n", encoding="utf-8")',
            output_dir=root / "round-zero",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        first_brief = root / "brief-1.txt"
        first_brief.write_text("Correction round 1.\n", encoding="utf-8")
        first = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            first_brief,
            '(worker_repo / "allowed.txt").write_text("round 1\\n", encoding="utf-8")',
            output_dir=root / "round-1",
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        prior = Path(first.stdout.strip())
        accepted = json.loads(prior.read_text(encoding="utf-8"))
        self.assertEqual(accepted["correction_lineage"]["correction_round"], 1)
        second_brief = root / "brief-2.txt"
        second_brief.write_text("Second correction must be refused.\n", encoding="utf-8")
        second = self.run_correction_with_worker(
            repo,
            plan_path,
            prior,
            second_brief,
            '(worker_repo / "allowed.txt").write_text("round 2\\n", encoding="utf-8")',
            output_dir=root / "round-2",
        )
        self.assertEqual(second.returncode, 1)
        self.assertIn("stopped for restructuring", second.stderr)
        self.assertFalse((root / "round-2" / "worker.stdout").exists())
        self.assertFalse((root / "round-2" / "candidate.patch").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")
        with self.assertRaisesRegex(RUNNER.RunnerError, "correction budget exhausted"):
            RUNNER.next_correction_lineage(
                accepted,
                prior_manifest_digest="0" * 64,
                prior_patch_digest="0" * 64,
                correction_brief_digest="0" * 64,
            )

    def test_correction_rejects_tampered_prior_manifest_and_brief_boundaries(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "tamper-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        original_manifest = json.loads(Path(initial.stdout.strip()).read_text(encoding="utf-8"))
        brief = root / "brief.txt"
        brief.write_text("Correct it.\n", encoding="utf-8")
        cases = {
            "head": ("source_head", "0" * 40, "source HEAD"),
            "plan": ("plan_digest", "0" * 64, "plan digest"),
            "scope": ("allowed_write_scope", ["other.txt"], "write scope"),
            "patch": ("patch_digest", "0" * 64, "patch digest"),
            "paths": ("changed_paths", ["other.txt"], "changed paths"),
            "schema": ("schema_version", 999, "schema version"),
        }
        for index, (label, (key, value, message)) in enumerate(cases.items()):
            with self.subTest(case=label):
                manifest = dict(original_manifest)
                manifest[key] = value
                path = initial_output / f"tampered-{label}.json"
                path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
                result = self.run_correction_with_worker(
                    repo,
                    plan_path,
                    path,
                    brief,
                    '(worker_repo / "allowed.txt").write_text("must not run\\n", encoding="utf-8")',
                    output_dir=root / f"tampered-output-{index}",
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        lineage_manifest = dict(original_manifest)
        lineage_manifest["correction_lineage"] = {
            "prior_manifest_digest": "0" * 64,
            "prior_patch_digest": "0" * 64,
            "correction_round": 0,
            "correction_brief_digest": "0" * 64,
        }
        lineage_path = initial_output / "bad-lineage.json"
        lineage_path.write_text(json.dumps(lineage_manifest) + "\n", encoding="utf-8")
        lineage = self.run_correction_with_worker(
            repo,
            plan_path,
            lineage_path,
            brief,
            "pass",
            output_dir=root / "bad-lineage-output",
        )
        self.assertEqual(lineage.returncode, 1)
        self.assertIn("lineage differs", lineage.stderr)

        oversized = root / "oversized-brief.txt"
        oversized.write_bytes(b"x" * (RUNNER.CORRECTION_BRIEF_MAX_BYTES + 1))
        too_large = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            oversized,
            "pass",
            output_dir=root / "oversized-brief-output",
        )
        self.assertEqual(too_large.returncode, 1)
        self.assertIn("byte bound", too_large.stderr)
        brief_link = root / "brief-link.txt"
        brief_link.symlink_to(brief)
        linked = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief_link,
            "pass",
            output_dir=root / "linked-brief-output",
        )
        self.assertEqual(linked.returncode, 1)
        self.assertIn("symlink", linked.stderr)

    def test_correction_failure_leaves_no_candidate_and_keeps_source_clean(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "failure-initial",
        )
        brief = root / "failure-brief.txt"
        brief.write_text("Fail safely.\n", encoding="utf-8")
        output = root / "failure-output"
        failed = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            "raise SystemExit(7)",
            output_dir=output,
        )
        self.assertEqual(failed.returncode, 1)
        self.assertIn("correction worker exited with 7", failed.stderr)
        receipt = RUNNER.load_worker_completion_receipt(
            (output / "worker-completion-receipt.json").read_bytes()
        )
        self.assertEqual(receipt["process"]["exit_status"], 7)
        self.assertEqual(receipt["claims"]["attempt_result"], "failure")
        self.assertIsNone(receipt["candidate"])
        process_result = RUNNER.validate_attempt_process_result(
            json.loads((output / "worker-process-result.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(process_result["exit_status"], 7)
        self.assertEqual(process_result["attempt_id"], receipt["attempt"]["attempt_id"])
        self.assertFalse((output / "candidate.patch").exists())
        self.assertFalse((output / "manifest.json").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_correction_reuses_same_run_availability_and_only_falls_back_for_availability(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        state = root / "correction-state.json"
        common = (
            "--availability-state",
            str(state),
            "--orchestration-run-id",
            "same-correction-run",
        )
        initial = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_success",
            output_dir=root / "availability-correction-initial",
            extra_args=common,
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        initial_manifest = json.loads(Path(initial.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(initial_manifest["telemetry"]["model_starts"], 2)
        self.assertEqual(initial_manifest["telemetry"]["availability_failures"], 1)
        self.assertEqual(
            json.loads(state.read_text(encoding="utf-8"))["unavailable_models"],
            [{"model": "gpt-5.3-codex-spark", "reason": "usage_limit"}],
        )
        brief = root / "availability-correction-brief.txt"
        brief.write_text("Correct the candidate.\n", encoding="utf-8")
        correction_output = root / "correction-availability-reuse"
        correction = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            "unavailable_then_success",
            output_dir=correction_output,
            extra_args=common,
        )
        self.assertEqual(correction.returncode, 0, correction.stderr)
        correction_manifest = json.loads(Path(correction.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(correction_manifest["correction_lineage"]["correction_round"], 1)
        self.assertEqual(correction_manifest["telemetry"]["model_starts"], 1)
        self.assertEqual(correction_manifest["telemetry"]["availability_failures"], 0)
        self.assertEqual(correction_manifest["telemetry"]["skipped_known_unavailable_starts"], 1)
        self.assertEqual(
            [attempt["label"] for attempt in correction_manifest["worker_result"]["attempts"]],
            ["fallback"],
        )
        self.assertFalse((correction_output / "worker-primary.stdout").exists())

        mismatch_state = root / "correction-mismatch-state.json"
        mismatch_initial = self.run_with_fake_codex(
            repo,
            plan_path,
            "primary_success",
            output_dir=root / "correction-mismatch-initial",
            extra_args=(
                "--availability-state",
                str(mismatch_state),
                "--orchestration-run-id",
                "mismatch-correction-run",
            ),
        )
        self.assertEqual(mismatch_initial.returncode, 0, mismatch_initial.stderr)
        mismatched = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            Path(mismatch_initial.stdout.strip()),
            brief,
            "primary_success",
            output_dir=root / "correction-run-mismatch",
            extra_args=(
                "--availability-state",
                str(mismatch_state),
                "--orchestration-run-id",
                "different-run",
            ),
        )
        self.assertEqual(mismatched.returncode, 1)
        self.assertIn("run identifier differs", mismatched.stderr)
        self.assertFalse((root / "correction-run-mismatch").exists())

        semantic_initial = self.run_with_fake_codex(
            repo,
            plan_path,
            "primary_success",
            output_dir=root / "correction-semantic-initial",
        )
        self.assertEqual(semantic_initial.returncode, 0, semantic_initial.stderr)
        semantic = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            Path(semantic_initial.stdout.strip()),
            brief,
            "nonavailability_failure",
            output_dir=root / "correction-semantic-failure",
        )
        self.assertEqual(semantic.returncode, 1)
        self.assertIn(
            "sandboxed plan worker failed: correction worker exited with 1;", semantic.stderr
        )
        self.assertTrue((root / "correction-semantic-failure" / "worker-primary.stdout").is_file())
        self.assertFalse((root / "correction-semantic-failure" / "worker-fallback.stdout").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_correction_classifies_unavailable_preferred_model_and_records_fallback(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _initial_output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial candidate\\n", encoding="utf-8")',
            output_dir=root / "classification-initial",
            extra_args=("--orchestration-run-id", "classification-correction-run"),
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        brief = root / "classification-brief.txt"
        brief.write_text("Correct the candidate.\n", encoding="utf-8")
        state = root / "classification-state.json"
        output_dir = root / "correction-classification"
        correction = self.run_correction_with_fake_codex(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            "unavailable_then_success",
            output_dir=output_dir,
            extra_args=(
                "--availability-state",
                str(state),
                "--orchestration-run-id",
                "classification-correction-run",
            ),
        )
        self.assertEqual(correction.returncode, 0, correction.stderr)
        manifest = json.loads(Path(correction.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["correction_lineage"]["correction_round"], 1)
        self.assertEqual(manifest["telemetry"]["model_starts"], 2)
        self.assertEqual(manifest["telemetry"]["availability_failures"], 1)
        self.assertEqual(manifest["telemetry"]["skipped_known_unavailable_starts"], 0)
        worker_result = manifest["worker_result"]
        self.assertEqual(worker_result["selected_attempt"], "fallback")
        self.assertEqual(worker_result["fallback_reason"], "usage_limit")
        self.assertEqual(
            [attempt["label"] for attempt in worker_result["attempts"]], ["primary", "fallback"]
        )
        self.assertNotIn("usage limit", json.dumps(worker_result).lower())
        self.assertEqual(
            json.loads(state.read_text(encoding="utf-8")),
            {
                "schema_version": 1,
                "orchestration_run_id": "classification-correction-run",
                "unavailable_models": [{"model": "gpt-5.3-codex-spark", "reason": "usage_limit"}],
            },
        )
        self.assertTrue((output_dir / "worker-primary.stdout").is_file())
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_correction_sandbox_denies_source_out_of_scope_and_git_metadata_writes(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("initial candidate\\n", encoding="utf-8")',
            output_dir=root / "denial-initial",
        )
        brief = root / "denial-brief.txt"
        brief.write_text("Verify correction sandbox denials.\n", encoding="utf-8")
        correction = self.run_correction_with_worker(
            repo,
            plan_path,
            Path(initial.stdout.strip()),
            brief,
            textwrap.dedent(
                """\
                denied = []
                for target, label in (
                    (source_repo / "blocked.txt", "source"),
                    (worker_repo / "outside-scope.txt", "scope"),
                    (worker_repo / ".git" / "refs" / "heads" / "evil", "git"),
                ):
                    try:
                        target.write_text("blocked\\n", encoding="utf-8")
                    except OSError:
                        denied.append(label)
                    else:
                        raise SystemExit(f"unexpected write success: {label}")
                if denied != ["source", "scope", "git"]:
                    raise SystemExit(f"unexpected denial set: {denied}")
                (worker_repo / "allowed.txt").write_text("safe correction\\n", encoding="utf-8")
                """
            ),
            output_dir=root / "denial-correction",
        )
        self.assertEqual(correction.returncode, 0, correction.stderr)
        self.assertFalse((repo / "blocked.txt").exists())
        self.assertFalse((repo / "outside-scope.txt").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_parent_authorized_focused_and_authoritative_validation_use_fresh_clone(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            validation=["git diff --check"],
            focused_validation=["git diff --check"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate for validation\\n", encoding="utf-8")',
            output_dir=root / "validation-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest = Path(initial.stdout.strip())
        for suite, focused_count, authoritative_count in (
            ("focused", 1, 0),
            ("authoritative", 1, 1),
        ):
            with self.subTest(suite=suite):
                output = root / f"validation-{suite}"
                result = run_cli(
                    repo,
                    "validate",
                    str(manifest),
                    "--suite",
                    suite,
                    "--parent-diff-approved",
                    "--critical-invariants-approved",
                    "--output-dir",
                    str(output),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
                self.assertTrue(report["passed"])
                self.assertEqual(report["suite"], suite)
                self.assertEqual(len(report["commands"]), 1)
                self.assertEqual(report["commands"][0]["argv"], ["git", "diff", "--check"])
                self.assertEqual(report["telemetry"]["focused_validation_count"], focused_count)
                self.assertEqual(report["telemetry"]["authoritative_validation_count"], authoritative_count)
                self.assertEqual(report["telemetry"]["full_validation_count"], authoritative_count)
                self.assertNotIn("candidate for validation", json.dumps(report))
                self.assertGreaterEqual(report["telemetry"]["duration_seconds"], 0)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def write_npm_dependency_tree(self, repo: Path) -> None:
        package_record = {
            "version": "1.0.0",
            "dev": True,
            "bin": {"verify-tool": "bin/verify-tool"},
        }
        package_lock = {
            "name": "dependency-snapshot-fixture",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {
                "": {
                    "name": "dependency-snapshot-fixture",
                    "version": "1.0.0",
                    "devDependencies": {"verify-tool": "1.0.0"},
                },
                "node_modules/verify-tool": package_record,
            },
        }
        hidden_lock = {
            "name": "dependency-snapshot-fixture",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {"node_modules/verify-tool": package_record},
        }
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "dependency-snapshot-fixture",
                    "version": "1.0.0",
                    "private": True,
                    "scripts": {"verify": "verify-tool"},
                    "devDependencies": {"verify-tool": "1.0.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (repo / "package-lock.json").write_text(
            json.dumps(package_lock, indent=2) + "\n", encoding="utf-8"
        )
        node_version = subprocess.run(
            ["node", "--version"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        (repo / ".node-version").write_text(
            node_version.removeprefix("v").split(".", 1)[0] + "\n", encoding="utf-8"
        )
        git(repo, "add", "package.json", "package-lock.json", ".node-version")
        git(repo, "commit", "-qm", "add npm validation fixture")
        dependency = repo / "node_modules/verify-tool"
        (dependency / "bin").mkdir(parents=True)
        (repo / "node_modules/.package-lock.json").write_text(
            json.dumps(hidden_lock, indent=2) + "\n", encoding="utf-8"
        )
        (dependency / "package.json").write_text(
            json.dumps(
                {
                    "name": "verify-tool",
                    "version": "1.0.0",
                    "bin": {"verify-tool": "bin/verify-tool"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        executable = dependency / "bin/verify-tool"
        executable.write_text(
            '''#!/bin/sh
module_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
case "$(command -v npm)" in
  /usr/*|/bin/*) echo "npm fell back to the system runtime" >&2; exit 5 ;;
esac
case "$(command -v npx)" in
  /usr/*|/bin/*) echo "npx fell back to the system runtime" >&2; exit 4 ;;
esac
npm --version >/dev/null
npx --version >/dev/null
for cache in .vite .vite-temp; do
  if [ -e "$module_root/$cache/snapshot-cache" ]; then
    echo "snapshot cache content was exposed" >&2
    exit 8
  fi
  if [ -e "$module_root/$cache/command-cache" ]; then
    echo "dependency cache was shared between validation commands" >&2
    exit 6
  fi
  echo command-local >"$module_root/$cache/command-cache"
done
if [ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ] && \
   [ ! -f "$PLAYWRIGHT_BROWSERS_PATH/chromium_headless_shell-1/browser-marker" ]; then
  echo "Playwright browser snapshot was unavailable" >&2
  exit 7
fi
if touch "$(dirname "$0")/unexpected-write" 2>/dev/null; then
  echo "dependency snapshot was writable" >&2
  exit 9
fi
echo dependency-snapshot-verified
''',
            encoding="utf-8",
        )
        executable.chmod(0o755)
        binary_dir = repo / "node_modules/.bin"
        binary_dir.mkdir()
        (binary_dir / "verify-tool").symlink_to("../verify-tool/bin/verify-tool")
        cache_dir = repo / "node_modules/.vite"
        cache_dir.mkdir()
        (cache_dir / "snapshot-cache").write_text("must remain hidden\n", encoding="utf-8")

    def test_missing_dependency_cache_mountpoints_are_temporary_and_digest_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency_tree = root / "node_modules"
            dependency_tree.mkdir()
            (dependency_tree / "package.txt").write_text("locked\n", encoding="utf-8")
            expected_digest = RUNNER.digest_tree(dependency_tree)

            created = RUNNER.ensure_dependency_cache_mountpoints(dependency_tree)
            self.assertEqual(
                [path.name for path in created],
                list(RUNNER.DEPENDENCY_WRITABLE_CACHE_PATHS),
            )
            (root / "scratch").mkdir()
            shadows = RUNNER.dependency_cache_shadows(
                dependency_tree, root / "clone/node_modules", root / "scratch"
            )
            self.assertEqual(
                [target.name for _shadow, target in shadows],
                list(RUNNER.DEPENDENCY_WRITABLE_CACHE_PATHS),
            )
            for shadow, _target in shadows:
                (shadow / "command-cache").write_text("disposable\n", encoding="utf-8")

            RUNNER.verify_private_dependency_integrity(
                dependency_tree, expected_digest, created
            )
            self.assertEqual((dependency_tree / "package.txt").read_text(), "locked\n")

    def install_npm_workerd_hardlink_tree(self, repo: Path) -> tuple[Path, Path]:
        platform_package = repo / "fixtures/workerd-linux-64"
        wrapper_package = repo / "fixtures/workerd"
        (platform_package / "bin").mkdir(parents=True)
        (wrapper_package / "bin").mkdir(parents=True)
        (platform_package / "package.json").write_text(
            json.dumps(
                {
                    "name": "@cloudflare/workerd-linux-64",
                    "version": "1.0.0",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (platform_package / "bin/workerd").write_text(
            "workerd fixture\n", encoding="utf-8"
        )
        (wrapper_package / "package.json").write_text(
            json.dumps(
                {
                    "name": "workerd",
                    "version": "1.0.0",
                    "scripts": {"postinstall": "node postinstall.js"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (wrapper_package / "bin/workerd").write_text(
            "replaced during npm ci\n", encoding="utf-8"
        )
        (wrapper_package / "postinstall.js").write_text(
            """const fs = require("node:fs");
const path = require("node:path");
const source = path.join(__dirname, "..", "@cloudflare", "workerd-linux-64", "bin", "workerd");
const target = path.join(__dirname, "bin", "workerd");
fs.rmSync(target, { force: true });
fs.linkSync(source, target);
""",
            encoding="utf-8",
        )
        npm_environment = dict(os.environ)
        npm_environment.update(
            {
                "npm_config_audit": "false",
                "npm_config_cache": str(repo.parent / "npm-cache"),
                "npm_config_fund": "false",
                "npm_config_update_notifier": "false",
            }
        )

        def pack(source: Path) -> str:
            packed = subprocess.run(
                [
                    "npm",
                    "pack",
                    "--ignore-scripts",
                    "--pack-destination",
                    str(repo / "fixtures"),
                ],
                cwd=source,
                env=npm_environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(packed.returncode, 0, packed.stderr)
            return packed.stdout.strip().splitlines()[-1]

        platform_archive = pack(platform_package)
        wrapper_archive = pack(wrapper_package)
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "workerd-hardlink-fixture",
                    "version": "1.0.0",
                    "private": True,
                    "dependencies": {
                        "@cloudflare/workerd-linux-64": f"file:fixtures/{platform_archive}",
                        "workerd": f"file:fixtures/{wrapper_archive}",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        lock = subprocess.run(
            ["npm", "install", "--package-lock-only", "--ignore-scripts", "--offline"],
            cwd=repo,
            env=npm_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(lock.returncode, 0, lock.stderr)
        git(repo, "add", "package.json", "package-lock.json", "fixtures")
        git(repo, "commit", "-qm", "add npm ci Workerd hard-link fixture")
        installed = subprocess.run(
            ["npm", "ci", "--offline"],
            cwd=repo,
            env=npm_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stderr)
        return (
            repo / "node_modules/@cloudflare/workerd-linux-64/bin/workerd",
            repo / "node_modules/workerd/bin/workerd",
        )

    def test_prepare_dependencies_breaks_npm_workerd_hardlinks(self) -> None:
        if shutil.which("npm") is None:
            if os.environ.get("REQUIRE_NPM") == "1":
                self.fail("npm is required for the Workerd hard-link regression")
            self.skipTest("npm is unavailable")
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        platform_binary, wrapper_binary = self.install_npm_workerd_hardlink_tree(repo)
        self.assertTrue(os.path.samefile(platform_binary, wrapper_binary))
        self.assertEqual(platform_binary.stat().st_nlink, 2)
        with self.assertRaisesRegex(RUNNER.RunnerError, "hard-linked file"):
            RUNNER.digest_tree(repo / "node_modules")

        prepared = run_cli(
            repo,
            "prepare-dependencies",
            "--output-dir",
            str(root / "dependency-snapshot"),
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        snapshot_root = Path(prepared.stdout.strip()).parent / "node_modules"
        copied_platform = snapshot_root / "@cloudflare/workerd-linux-64/bin/workerd"
        copied_wrapper = snapshot_root / "workerd/bin/workerd"
        self.assertFalse(os.path.samefile(copied_platform, copied_wrapper))
        self.assertEqual(copied_platform.stat().st_nlink, 1)
        self.assertEqual(copied_wrapper.stat().st_nlink, 1)
        self.assertEqual(copied_platform.read_bytes(), platform_binary.read_bytes())
        self.assertEqual(copied_wrapper.read_bytes(), wrapper_binary.read_bytes())
        RUNNER.verify_dependency_snapshot(repo, Path(prepared.stdout.strip()))

    def test_source_tree_metadata_fingerprint_detects_restored_hardlink_count(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        self.write_npm_dependency_tree(repo)
        dependency_tree = repo / "node_modules"
        executable = dependency_tree / "verify-tool/bin/verify-tool"
        before = RUNNER.source_tree_metadata_fingerprint(dependency_tree)
        external_link = Path(temporary.name) / "temporary-hardlink"
        os.link(executable, external_link)
        external_link.unlink()
        after = RUNNER.source_tree_metadata_fingerprint(dependency_tree)
        self.assertNotEqual(before, after)

    def test_npm_validation_uses_a_lock_bound_read_only_snapshot_in_a_fresh_clone(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"},
            validation=["npm run verify", "npm run verify"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        browser_dir = root / "chromium_headless_shell-1"
        browser_dir.mkdir()
        (browser_dir / "browser-marker").write_text("verified browser\n", encoding="utf-8")
        snapshot_dir = root / "dependency-snapshot"
        prepared = run_cli(
            repo,
            "prepare-dependencies",
            "--output-dir",
            str(snapshot_dir),
            "--playwright-browser-dir",
            str(browser_dir),
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        snapshot_manifest = Path(prepared.stdout.strip())
        snapshot = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["package_manager"], "npm")
        self.assertRegex(snapshot["tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            (snapshot_dir / "node_modules/.playwright-browsers/chromium_headless_shell-1/browser-marker").read_text(),
            "verified browser\n",
        )

        shutil.rmtree(repo / "node_modules")
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "npm-validation-initial",
        )
        worker_detail = root / "npm-validation-initial/worker.stderr"
        self.assertEqual(
            initial.returncode,
            0,
            initial.stderr
            + (worker_detail.read_text(encoding="utf-8") if worker_detail.is_file() else ""),
        )
        result = run_cli(
            repo,
            "validate",
            initial.stdout.strip(),
            "--suite",
            "authoritative",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "npm-validation-output"),
            "--dependency-snapshot",
            str(snapshot_manifest),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(
            [command["argv"] for command in report["commands"]],
            [["npm", "run", "verify"], ["npm", "run", "verify"]],
        )
        self.assertEqual(report["dependency_snapshot"]["tree_sha256"], snapshot["tree_sha256"])
        self.assertEqual(
            report["node_runtime"]["requested_version"],
            subprocess.run(
                ["node", "--version"], check=True, text=True, stdout=subprocess.PIPE
            ).stdout.strip().removeprefix("v").split(".", 1)[0],
        )
        self.assertRegex(report["node_runtime"]["node_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(report["node_runtime"]["npm_tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertFalse((repo / "node_modules").exists())

    def test_npm_runtime_must_match_the_project_node_major(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={".node-version": "999\n"}
        )
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(RUNNER.RunnerError, "does not match .node-version"):
            RUNNER.resolve_project_node_runtime(repo)

    def test_npm_runtime_rejects_an_ignored_untracked_node_version(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={".gitignore": ".node-version\n"}
        )
        self.addCleanup(temporary.cleanup)
        (repo / ".node-version").write_text("24\n", encoding="utf-8")
        with self.assertRaisesRegex(RUNNER.RunnerError, "tracked HEAD file"):
            RUNNER.resolve_project_node_runtime(repo)

    @unittest.skipUnless(
        Path("/usr/bin/node").is_file()
        and Path("/usr/bin/npm").resolve() == Path("/usr/share/nodejs/npm/bin/npm-cli.js"),
        "split Debian system npm runtime is unavailable",
    )
    def test_split_system_npm_runtime_is_rejected_after_private_staging(self) -> None:
        system_version = subprocess.run(
            ["/usr/bin/node", "--version"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"],
            files={
                ".node-version": system_version.removeprefix("v").split(".", 1)[0] + "\n"
            },
        )
        self.addCleanup(temporary.cleanup)
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            runtime = RUNNER.resolve_project_node_runtime(repo)
        root = Path(temporary.name)
        with self.assertRaisesRegex(RUNNER.RunnerError, "not self-contained"):
            RUNNER.materialize_project_node_runtime(
                runtime, root / "private-node-runtime"
            )

    @unittest.skipUnless(
        Path("/usr/bin/node").is_file()
        and Path("/usr/bin/npm").resolve() == Path("/usr/share/nodejs/npm/bin/npm-cli.js"),
        "split Debian system npm runtime is unavailable",
    )
    def test_runtime_prerequisite_failure_does_not_consume_validation_attempt(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"},
            validation=["npm run verify"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        system_version = subprocess.run(
            ["/usr/bin/node", "--version"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        (repo / ".node-version").write_text(
            system_version.removeprefix("v").split(".", 1)[0] + "\n",
            encoding="utf-8",
        )
        git(repo, "add", ".node-version")
        git(repo, "commit", "-qm", "select split system Node fixture")
        prepared = run_cli(
            repo,
            "prepare-dependencies",
            "--output-dir",
            str(root / "dependency-snapshot"),
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        shutil.rmtree(repo / "node_modules")
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "runtime-prerequisite-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        lifecycle_path = Path(manifest["lifecycle_state_path"])
        for attempt in (1, 2):
            result = run_cli(
                repo,
                "validate",
                str(manifest_path),
                "--suite",
                "authoritative",
                "--parent-diff-approved",
                "--critical-invariants-approved",
                "--output-dir",
                str(root / f"runtime-prerequisite-validation-{attempt}"),
                "--dependency-snapshot",
                prepared.stdout.strip(),
                env={"PATH": "/usr/bin:/bin"},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not self-contained", result.stderr)
            lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
            self.assertEqual(lifecycle["phase"], "admitted")
            self.assertEqual(lifecycle["authoritative_validation_count"], 0)

    def test_playwright_browser_snapshot_rejects_an_unallowlisted_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            target = root / "node_modules"
            target.mkdir()
            browser = root / "arbitrary-browser"
            browser.mkdir()
            with self.assertRaisesRegex(RUNNER.RunnerError, "unsupported Playwright"):
                RUNNER.copy_playwright_browser_artifacts(repo, [str(browser)], target)

    def test_dependency_snapshot_rejects_tree_and_lockfile_tampering(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot"))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = Path(prepared.stdout.strip())
        (manifest.parent / "node_modules/verify-tool/bin/verify-tool").write_text(
            "#!/bin/sh\necho tampered\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RUNNER.RunnerError, "tree digest"):
            RUNNER.verify_dependency_snapshot(repo, manifest)

        shutil.rmtree(manifest.parent)
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot-two"))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = Path(prepared.stdout.strip())
        (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(RUNNER.RunnerError, "package-lock.json digest"):
            RUNNER.verify_dependency_snapshot(repo, manifest)

    def test_dependency_snapshot_rejects_reused_output_hardlinks_and_path_swap(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)

        existing = root / "existing-output"
        existing.mkdir()
        rejected = run_cli(repo, "prepare-dependencies", "--output-dir", str(existing))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("must not already exist", rejected.stderr)

        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot"))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = Path(prepared.stdout.strip())
        manifest_link = root / "manifest-hardlink.json"
        os.link(manifest, manifest_link)
        with self.assertRaisesRegex(RUNNER.RunnerError, "regular file"):
            RUNNER.verify_dependency_snapshot(repo, manifest)
        manifest_link.unlink()

        snapshot = RUNNER.verify_dependency_snapshot(repo, manifest)
        original_tree = manifest.parent / "node_modules"
        moved_tree = manifest.parent / "verified-before-swap"
        original_tree.rename(moved_tree)
        shutil.copytree(moved_tree, original_tree, symlinks=True)
        (original_tree / "verify-tool/bin/verify-tool").write_text(
            "#!/bin/sh\necho path-swapped\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RUNNER.RunnerError, "verified tree digest"):
            RUNNER.materialize_verified_dependency_tree(
                repo, snapshot, root / "private-dependency-copy"
            )

    def test_dependency_snapshot_rejects_a_symlink_that_escapes_node_modules(self) -> None:
        temporary, repo, _plan_path = self.make_repo(
            ["allowed.txt"], files={"allowed.txt": "original\n", ".gitignore": "node_modules/\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.write_npm_dependency_tree(repo)
        (repo / "node_modules/.bin/escape").symlink_to("../../outside-node-modules")
        prepared = run_cli(repo, "prepare-dependencies", "--output-dir", str(root / "snapshot"))
        self.assertEqual(prepared.returncode, 1)
        self.assertIn("symlink escapes node_modules", prepared.stderr)
        self.assertFalse((root / "snapshot").exists())

    def test_focused_validation_absence_is_compatible_and_requires_parent_approvals(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"], validation=["git diff --check"]
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "optional-focused-initial",
        )
        manifest = Path(initial.stdout.strip())
        denied = run_cli(
            repo,
            "validate",
            str(manifest),
            "--suite",
            "focused",
            "--output-dir",
            str(root / "approval-denied"),
        )
        self.assertEqual(denied.returncode, 1)
        self.assertIn("explicit parent diff", denied.stderr)
        approved = run_cli(
            repo,
            "validate",
            str(manifest),
            "--suite",
            "focused",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "optional-focused-approved"),
        )
        self.assertEqual(approved.returncode, 1)
        self.assertIn("no focused validation stage", approved.stderr)

    def test_validation_rejects_candidate_modified_plan_and_records_bounded_failure(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt", "docs/plan/active/001-sandboxed.md"],
            validation=["git diff --check"],
            focused_validation=["python3 -m pytest tests/missing-focused.py"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        modified_plan, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                plan = worker_repo / plan_path
                plan.write_text(plan.read_text(encoding="utf-8") + "\\nworker change\\n", encoding="utf-8")
                """
            ),
            output_dir=root / "modified-plan-candidate",
        )
        self.assertEqual(modified_plan.returncode, 1)
        self.assertIn("read-only plan", modified_plan.stderr)

        plan = repo / plan_path
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "  - docs/plan/active/001-sandboxed.md\n", ""
            ),
            encoding="utf-8",
        )
        git(repo, "add", plan_path)
        git(repo, "commit", "-qm", "remove protected plan scope")

        failing, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("failing validation candidate\\n", encoding="utf-8")',
            output_dir=root / "failing-validation-candidate",
        )
        failure_output = root / "failing-validation-report"
        failed = run_cli(
            repo,
            "validate",
            failing.stdout.strip(),
            "--suite",
            "focused",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(failure_output),
        )
        self.assertEqual(failed.returncode, 1)
        self.assertIn("bounded report saved", failed.stderr)
        report = json.loads((failure_output / "validation.json").read_text(encoding="utf-8"))
        self.assertFalse(report["passed"])
        self.assertEqual(
            report["plan_execution_attempt_id"],
            json.loads(Path(failing.stdout.strip()).read_text(encoding="utf-8"))[
                "plan_execution_attempt_id"
            ],
        )
        self.assertNotEqual(report["commands"][0]["returncode"], 0)
        self.assertNotIn("stdout_body", report["commands"][0])
        self.assertNotIn("stderr_body", report["commands"][0])
        self.assertIn("stdout_digest", report["commands"][0])
        self.assertIn("stderr_digest", report["commands"][0])
        failure = report["failure"]
        self.assertEqual(failure["kind"], "command")
        self.assertEqual(failure["command_index"], 0)
        self.assertEqual(failure["observed_exit_status"], report["commands"][0]["returncode"])
        identity = {
            "suite": "focused",
            "kind": "command",
            "command_index": 0,
            "argv": report["commands"][0]["argv"],
        }
        self.assertEqual(
            failure["operation_digest"],
            "sha256:" + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
        self.assertNotIn("stdout", json.dumps(failure))
        self.assertNotIn("stderr", json.dumps(failure))
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_validation_setup_failure_persists_bounded_report_and_failed_lifecycle(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={"allowed.txt": "original\n", "scripts/lint-project-workflow.sh": "#!/bin/sh\n"},
            focused_validation=["scripts/lint-project-workflow.sh"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "setup-failure-candidate",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest = Path(initial.stdout.strip())
        manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
        report_dir = root / "setup-failure-report"
        failed = run_cli(
            repo,
            "validate",
            str(manifest),
            "--suite",
            "focused",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(report_dir),
        )
        self.assertEqual(failed.returncode, 1)
        report = json.loads((report_dir / "validation.json").read_text(encoding="utf-8"))
        self.assertFalse(report["passed"])
        self.assertEqual(report["failure"]["kind"], "runner_setup")
        self.assertEqual(report["failure"]["observed_exit_status"], 1)
        self.assertEqual(report["commands"][0]["returncode"], 0)
        lifecycle = json.loads(
            Path(manifest_value["lifecycle_state_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(lifecycle["phase"], "focused_failed")
        self.assertEqual(lifecycle["focused_validation_count"], 1)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_nonavailability_failure_and_disabled_fallback_do_not_retry(self) -> None:
        for scenario, extra_args in (
            ("nonavailability_failure", ()),
            ("unavailable_then_success", ("--no-model-fallback",)),
        ):
            with self.subTest(scenario=scenario, extra_args=extra_args):
                temporary, repo, plan_path = self.make_repo(["allowed.txt"])
                self.addCleanup(temporary.cleanup)
                output_dir = Path(temporary.name) / f"no-fallback-{scenario}"
                result = self.run_with_fake_codex(
                    repo,
                    plan_path,
                    scenario,
                    output_dir=output_dir,
                    extra_args=extra_args,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("worker exited", result.stderr)
                self.assertFalse((output_dir / "worker-fallback.stdout").exists())
                self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_fallback_failure_stops_without_candidate_and_cli_overrides_are_honored(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "failed-fallback-output"
        result = self.run_with_fake_codex(
            repo,
            plan_path,
            "unavailable_then_failure",
            output_dir=output_dir,
            extra_args=(
                "--codex-model",
                "preferred-override",
                "--codex-reasoning-effort",
                "high",
                "--fallback-codex-model",
                "fallback-override",
                "--fallback-codex-reasoning-effort",
                "xhigh",
            ),
            fake_env={
                "FAKE_PRIMARY_MODEL": "preferred-override",
                "FAKE_PRIMARY_REASONING": "high",
                "FAKE_FALLBACK_MODEL": "fallback-override",
                "FAKE_FALLBACK_REASONING": "xhigh",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("fallback worker exited with 2", result.stderr)
        self.assertTrue((output_dir / "worker-primary.stderr").is_file())
        self.assertTrue((output_dir / "worker-fallback.stderr").is_file())
        primary_receipt = RUNNER.load_worker_completion_receipt(
            (output_dir / "worker-primary-completion-receipt.json").read_bytes()
        )
        fallback_receipt = RUNNER.load_worker_completion_receipt(
            (output_dir / "worker-fallback-completion-receipt.json").read_bytes()
        )
        self.assertNotEqual(
            primary_receipt["attempt"]["attempt_id"],
            fallback_receipt["attempt"]["attempt_id"],
        )
        self.assertEqual(primary_receipt["process"]["exit_status"], 1)
        self.assertEqual(fallback_receipt["process"]["exit_status"], 2)
        primary_process = RUNNER.validate_attempt_process_result(
            json.loads((output_dir / "worker-primary-process-result.json").read_text(encoding="utf-8"))
        )
        fallback_process = RUNNER.validate_attempt_process_result(
            json.loads((output_dir / "worker-fallback-process-result.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(primary_process["attempt_id"], primary_receipt["attempt"]["attempt_id"])
        self.assertEqual(fallback_process["attempt_id"], fallback_receipt["attempt"]["attempt_id"])
        self.assertFalse((output_dir / "candidate.patch").exists())
        self.assertFalse((output_dir / "manifest.json").exists())
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_run_rejects_empty_candidate_patch(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output_dir, _worker = self.run_with_worker(repo, plan_path, "pass")
        self.assertEqual(result.returncode, 1)
        self.assertIn("produced no candidate changes", result.stderr)

    def test_run_rejects_out_of_scope_change(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "forbidden.txt").write_text("oops\\n", encoding="utf-8")',
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("worker exited", result.stderr)

    def test_apply_rejects_mismatched_head(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("head mismatch\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        (repo / "second.txt").write_text("next head\n", encoding="utf-8")
        git(repo, "add", "second.txt")
        git(repo, "commit", "-qm", "advance head")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("source HEAD differs from the execution baseline", apply.stderr)

    def test_run_rejects_worker_commit_or_ref_change(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                import subprocess

                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=Worker",
                        "-c",
                        "user.email=worker@example.invalid",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "malicious commit",
                    ],
                    cwd=worker_repo,
                    check=True,
                )
                """
            ),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("worker exited", result.stderr)

    def test_apply_rejects_mismatched_plan_digest(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("digest mismatch\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        plan_file = repo / plan_path
        plan_file.write_text(plan_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        git(repo, "add", plan_path)
        git(repo, "commit", "-qm", "change plan digest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_head"] = git(repo, "rev-parse", "HEAD").stdout.strip()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("source HEAD differs from the execution baseline", apply.stderr)

    def test_apply_rejects_mismatched_patch_digest(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("patch mismatch\\n", encoding="utf-8")',
            output_dir=output_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = Path(result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        patch_path = Path(manifest["patch_path"])
        patch_path.write_bytes(patch_path.read_bytes() + b"\n")
        apply = run_cli(repo, "apply", str(manifest_path))
        self.assertEqual(apply.returncode, 1)
        self.assertIn("candidate patch digest no longer matches", apply.stderr)

    def test_bubblewrap_probe_blocks_source_and_host_temp_writes(self) -> None:
        temporary, repo, plan_path = self.make_repo(["probe.txt"], {"probe.txt": "original\\n"})
        self.addCleanup(temporary.cleanup)
        outside_path = Path(temporary.name) / "outside-host.txt"
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "probe.txt").write_text("inside clone\\n", encoding="utf-8")
                (scratch_dir / "probe-scratch.txt").write_text("inside scratch\\n", encoding="utf-8")
                if os.environ.get("PARENT_ONLY_SENTINEL") is not None:
                    raise SystemExit("parent sentinel leaked into the sandbox")
                denied = []
                for target, label in (
                    (source_repo / "source-write.txt", "source"),
                    (Path(os.environ[prefix + "OUTSIDE_PROBE"]), "outside"),
                ):
                    try:
                        target.write_text("blocked\\n", encoding="utf-8")
                    except OSError:
                        denied.append(label)
                    else:
                        raise SystemExit(f"unexpected write success: {label}")
                if denied != ["source", "outside"]:
                    raise SystemExit(f"unexpected denied set: {denied}")
                """
            ),
            output_dir=output_dir,
            worker_env={f"{ENV_PREFIX}OUTSIDE_PROBE": str(outside_path)},
            parent_env={"PARENT_ONLY_SENTINEL": "host-only"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((repo / "source-write.txt").exists())
        self.assertFalse(outside_path.exists())
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["probe.txt"])

    def test_patch_collection_keeps_clean_filter_inside_bubblewrap(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        outside_path = Path(temporary.name) / "outside-host.txt"
        output_dir = Path(temporary.name) / "artifacts"
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                f"""\
                import subprocess

                filter_script = scratch_dir / "clean-filter.py"
                filter_script.write_text(
                    {repr(textwrap.dedent(f'''\
                    #!/usr/bin/env python3
                    from __future__ import annotations

                    import os
                    import sys
                    from pathlib import Path


                    target = Path(os.environ["{ENV_PREFIX}OUTSIDE_PROBE"])
                    try:
                        target.write_text("blocked\\n", encoding="utf-8")
                    except OSError:
                        pass
                    else:
                        raise SystemExit("unexpected host write success")
                    sys.stdout.write(sys.stdin.read())
                    '''))},
                    encoding="utf-8",
                )
                filter_script.chmod(0o755)
                subprocess.run(["git", "config", "--global", "filter.leak.clean", str(filter_script)], cwd=worker_repo, check=True)
                attributes = Path(os.environ["HOME"]) / "global-attributes"
                attributes.write_text("allowed.txt filter=leak\\n", encoding="utf-8")
                subprocess.run(["git", "config", "--global", "core.attributesfile", str(attributes)], cwd=worker_repo, check=True)
                (worker_repo / "allowed.txt").write_text("through filter\\n", encoding="utf-8")
                """
            ),
            output_dir=output_dir,
            worker_env={f"{ENV_PREFIX}OUTSIDE_PROBE": str(outside_path)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(outside_path.exists())
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])

    def test_exact_scope_denies_all_unscoped_mutations_during_worker_execution(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"], {"allowed.txt": "original\n", "outside.txt": "outside\n"}
        )
        self.addCleanup(temporary.cleanup)
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                denied = []
                targets = (
                    (worker_repo / "outside.txt", lambda p: p.write_text("changed\\n", encoding="utf-8")),
                    (worker_repo / "created.txt", lambda p: p.write_text("created\\n", encoding="utf-8")),
                    (worker_repo / "outside.txt", lambda p: p.unlink()),
                    (worker_repo / "outside.txt", lambda p: p.chmod(0o755)),
                    (worker_repo / "outside.txt", lambda p: p.rename(worker_repo / "renamed.txt")),
                )
                for target, operation in targets:
                    try:
                        operation(target)
                    except OSError:
                        denied.append(target.name)
                    else:
                        raise SystemExit("unscoped mutation unexpectedly succeeded")
                if len(denied) != 5:
                    raise SystemExit(f"unexpected denied operations: {denied}")
                (worker_repo / "allowed.txt").write_text("allowed\\n", encoding="utf-8")
                """
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(manifest["changed_paths"], ["allowed.txt"])

    def test_exact_scope_rejects_removal_and_atomic_replacement(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        result, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                replacement = scratch_dir / "replacement.txt"
                replacement.write_text("replacement\\n", encoding="utf-8")
                for operation in (
                    lambda: (worker_repo / "allowed.txt").unlink(),
                    lambda: replacement.replace(worker_repo / "allowed.txt"),
                ):
                    try:
                        operation()
                    except OSError:
                        pass
                    else:
                        raise SystemExit("exact-file replacement unexpectedly succeeded")
                (worker_repo / "allowed.txt").write_text("updated\\n", encoding="utf-8")
                """
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def enroll_plan_in_group(
        self, repo: Path, plan_path: str, write_scope: list[str]
    ) -> None:
        """Commit a valid two-member execution group enrolling the runner plan."""

        (repo / "docs/plan/execution-groups").mkdir(parents=True, exist_ok=True)
        partner_path = "docs/plan/active/002-partner.md"
        partner_body = (
            "# Partner\n\nstatus: in_progress\n"
            "plan_purpose: implementation\n"
            "primary_invariant: partner invariant\n"
            "write_scope:\n  - partner.txt\n"
            "context_files:\n  - AGENTS.md\n"
            "\n## Tasks\n\n- [ ] implement\n"
        )
        (repo / partner_path).write_text(partner_body, encoding="utf-8")

        def group_digest(value) -> str:
            data = value if isinstance(value, bytes) else str(value).encode("utf-8")
            return "sha256:" + hashlib.sha256(data).hexdigest()

        plan_bytes = (repo / plan_path).read_bytes()
        description = {
            "schema_version": 1,
            "group_id": "runner-group",
            "target_ref": "refs/heads/main",
            "declared_independence": "disjoint fixture modules with no shared interface",
            "members": [
                {
                    "plan_id": "001",
                    "plan_path": plan_path,
                    "plan_digest": group_digest(plan_bytes),
                    "write_scope_digest": group_digest(
                        json.dumps(write_scope, sort_keys=True, separators=(",", ":"))
                    ),
                },
                {
                    "plan_id": "002",
                    "plan_path": partner_path,
                    "plan_digest": group_digest(partner_body.encode("utf-8")),
                    "write_scope_digest": group_digest(
                        json.dumps(["partner.txt"], sort_keys=True, separators=(",", ":"))
                    ),
                },
            ],
        }
        (repo / "docs/plan/execution-groups/runner-group.json").write_text(
            json.dumps(description, indent=2) + "\n", encoding="utf-8"
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "enroll runner plan")

    def test_enrolled_group_member_is_refused_before_worker_prerequisites(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        self.enroll_plan_in_group(repo, plan_path, ["allowed.txt"])
        original = Path.cwd()
        os.chdir(repo)
        try:
            for operation in ("run", "correct"):
                with self.subTest(operation=operation):
                    with self.assertRaises(RUNNER.RunnerError) as caught:
                        RUNNER.enforce_parallel_group_gate(plan_path, operation)
                    self.assertIn("enrolled in execution group", str(caught.exception))
        finally:
            os.chdir(original)

    def test_ungrouped_plan_passes_the_parallel_group_gate(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        original = Path.cwd()
        os.chdir(repo)
        try:
            RUNNER.enforce_parallel_group_gate(plan_path, "run")
        finally:
            os.chdir(original)

    def test_directory_prefix_scope_is_rejected_before_worker_start(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["dir/"], {"allowed.txt": "sibling\n", "dir/keep.txt": "before\n", "dir/remove.txt": "remove\n"}
        )
        self.addCleanup(temporary.cleanup)
        result, output, _worker = self.run_with_worker(
            repo,
            plan_path,
            textwrap.dedent(
                """\
                (worker_repo / "dir" / "keep.txt").write_text("after\\n", encoding="utf-8")
                (worker_repo / "dir" / "remove.txt").unlink()
                (worker_repo / "dir" / "new.txt").write_text("new\\n", encoding="utf-8")
                try:
                    (worker_repo / "allowed.txt").write_text("blocked\\n", encoding="utf-8")
                except OSError:
                    pass
                else:
                    raise SystemExit("sibling write unexpectedly succeeded")
                """
            ),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("explicit file path", result.stderr)
        self.assertFalse((output / "worker.stdout").exists())

    def test_shadow_setup_rejects_invalid_exact_targets_and_symlink_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clone = root / "clone"
            clone.mkdir()
            (clone / "directory").mkdir()
            (clone / "regular.txt").write_text("regular\n", encoding="utf-8")
            (clone / "link.txt").symlink_to("regular.txt")
            (clone / "linked-parent").symlink_to(root)
            for index, (scope, expected) in enumerate((
                (["directory"], "regular file"),
                (["link.txt"], "path resolves through a symlink"),
                (["linked-parent/new/"], "does not allow a directory prefix"),
            )):
                with self.subTest(scope=scope):
                    scratch = root / f"scratch-{index}"
                    scratch.mkdir()
                    with self.assertRaisesRegex(RUNNER.RunnerError, expected):
                        RUNNER.prepare_writable_shadows(clone_dir=clone, scratch_dir=scratch, scope_entries=scope)
            self.assertFalse((root / "new").exists())

    def test_prefix_shadow_is_rejected_even_when_contents_are_regular(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clone = root / "clone"
            scratch = root / "scratch"
            (clone / "dir").mkdir(parents=True)
            scratch.mkdir()
            (clone / "dir" / "target.txt").write_text("target\n", encoding="utf-8")
            (clone / "dir" / "inside-link").symlink_to("target.txt")
            with self.assertRaisesRegex(RUNNER.RunnerError, "does not allow a directory prefix"):
                RUNNER.prepare_writable_shadows(clone_dir=clone, scratch_dir=scratch, scope_entries=["dir/"])

    def test_run_rejects_symlinked_or_preexisting_output_artifacts(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)

        real_dir = Path(temporary.name) / "real-output"
        real_dir.mkdir()
        symlink_dir = Path(temporary.name) / "output-link"
        symlink_dir.symlink_to(real_dir, target_is_directory=True)
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
            output_dir=symlink_dir,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("symlink", result.stderr)

        preexisting_dir = Path(temporary.name) / "preexisting-output"
        preexisting_dir.mkdir()
        (preexisting_dir / "manifest.json").write_text("occupied\n", encoding="utf-8")
        result, _output_dir, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")',
            output_dir=preexisting_dir,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not already exist", result.stderr)

    def test_workspace_cleanup_removes_temporary_clone_and_scratch(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        cleanup_root = Path(temporary.name) / "cleanup-root"
        cleanup_root.mkdir()

        for label, worker_body, expected_code in (
            ("success", '(worker_repo / "allowed.txt").write_text("changed\\n", encoding="utf-8")', 0),
            ("failure", '(worker_repo / "forbidden.txt").write_text("blocked\\n", encoding="utf-8")', 1),
        ):
            with self.subTest(case=label):
                output_dir = Path(temporary.name) / f"{label}-output"
                result, _output, _worker = self.run_with_worker(
                    repo,
                    plan_path,
                    worker_body,
                    output_dir=output_dir,
                    parent_env={"TMPDIR": str(cleanup_root)},
                )
                self.assertEqual(result.returncode, expected_code, result.stderr)
                self.assert_no_workspace_directories(cleanup_root)

    def test_apply_requires_digest_bound_authoritative_lifecycle_receipt(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "lifecycle-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        execution_state = str(
            Path(manifest["lifecycle_state_path"]).with_name(
                Path(manifest["lifecycle_state_path"]).name
                + f".{manifest['orchestration_run_id']}.plan-execution.json"
            )
        )
        direct = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "apply",
                str(manifest_path),
                "--lifecycle-state",
                manifest["lifecycle_state_path"],
                "--orchestration-run-id",
                manifest["orchestration_run_id"],
                "--plan-execution-state",
                execution_state,
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(direct.returncode, 1)
        self.assertIn("authoritative validation", direct.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "original\n")

    def test_validation_rejects_candidate_owned_authority_paths(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["tests/original.py"], files={"tests/original.py": "pass\n"}
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "tests" / "original.py").write_text("raise SystemExit(0)\\n", encoding="utf-8")',
            output_dir=root / "authority-initial",
        )
        self.assertEqual(initial.returncode, 1)
        self.assertIn("validation authority", initial.stderr)

    def test_validation_authority_classifier_covers_indirect_and_generated_paths(self) -> None:
        for path in (
            ".project-agent-workflow/scripts/validate-changes.py",
            "template/app/tests/check.py",
            "nested/conftest.py",
            "src/widget.test.ts",
            "pytest.ini",
            "Cargo.toml",
            "webpack.config.js",
            "tsconfig.build.json",
            "build.rs",
            "packages/app/package.json",
            "packages/app/pyproject.toml",
            "packages/app/pnpm-lock.yaml",
        ):
            with self.subTest(path=path):
                self.assertTrue(RUNNER.is_validation_authority_path(path))
        self.assertFalse(RUNNER.is_validation_authority_path("src/widget.ts"))

    def test_validation_rejects_nested_workspace_manifest_bypass(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["packages/app/package.json"],
            files={
                "package.json": '{"scripts":{"test":"npm --prefix packages/app test"}}\n',
                "packages/app/package.json": '{"scripts":{"test":"exit 1"}}\n',
            },
            validation=["npm run test"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "packages" / "app" / "package.json").write_text(\'{"scripts":{"test":"exit 0"}}\\n\', encoding="utf-8")',
            output_dir=root / "workspace-authority-initial",
        )
        self.assertEqual(initial.returncode, 1)
        self.assertIn("validation authority", initial.stderr)

    def test_plan_declared_validation_authority_rejects_transitive_harness(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["tools/harness.js"],
            files={
                "package.json": '{"scripts":{"test":"node tools/harness.js"}}\n',
                "tools/harness.js": "process.exit(1)\n",
            },
            validation=["npm run test"],
            validation_authority_scope=["tools/"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "tools" / "harness.js").write_text("process.exit(0)\\n", encoding="utf-8")',
            output_dir=root / "declared-authority-initial",
        )
        self.assertEqual(initial.returncode, 1)
        self.assertIn("validation authority", initial.stderr)

    def test_manifest_operations_reject_execution_ledger_for_another_plan(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        other_plan = "docs/plan/active/002-other.md"
        (repo / other_plan).write_text(
            (repo / plan_path).read_text(encoding="utf-8").replace(
                "# Sandboxed worker test", "# Other plan"
            ),
            encoding="utf-8",
        )
        with (repo / "docs/plan/plan.md").open("a", encoding="utf-8") as handle:
            handle.write(f"002\t{other_plan}\tin_progress\n")
        git(repo, "add", other_plan, "docs/plan/plan.md")
        git(repo, "commit", "-qm", "add another active plan")

        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "wrong-ledger-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        wrong_state = root / "wrong-plan-execution.json"
        other_bytes = (repo / other_plan).read_bytes()
        initialized = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/plan-execution-state.py"),
                "init",
                str(wrong_state),
                "--run-id",
                manifest["orchestration_run_id"],
                "--plan",
                other_plan,
                "--plan-digest",
                "sha256:" + hashlib.sha256(other_bytes).hexdigest(),
                "--source-head",
                manifest["source_head"],
                "--primary-invariant-digest",
                "sha256:" + hashlib.sha256(b"mutate only the declared fixture files").hexdigest(),
                "--lifecycle-state",
                manifest["lifecycle_state_path"],
                "--implementation-mode",
                "candidate",
            ],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)

        common = [
            "--orchestration-run-id",
            manifest["orchestration_run_id"],
            "--lifecycle-state",
            manifest["lifecycle_state_path"],
            "--plan-execution-state",
            str(wrong_state),
        ]
        commands = (
            ["finalize-apply", str(manifest_path), *common],
            ["apply", str(manifest_path), *common],
            [
                "validate",
                str(manifest_path),
                "--suite",
                "authoritative",
                "--parent-diff-approved",
                "--critical-invariants-approved",
                "--output-dir",
                str(root / "wrong-ledger-validation"),
                *common,
            ],
        )
        for command in commands:
            with self.subTest(operation=command[0]):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *command],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("plan path mismatch", result.stderr)

    def test_verified_patch_bytes_survive_path_swap_before_apply(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("safe\\n", encoding="utf-8")',
            output_dir=root / "swap-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validated = run_cli(
            repo,
            "validate",
            str(manifest_path),
            "--suite",
            "authoritative",
            "--parent-diff-approved",
            "--critical-invariants-approved",
            "--output-dir",
            str(root / "swap-validation"),
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        original_verify = RUNNER.verify_candidate_manifest

        def swap_after_verify(**kwargs):
            verified = original_verify(**kwargs)
            Path(manifest["patch_path"]).write_text(
                "diff --git a/blocked.txt b/blocked.txt\nnew file mode 100644\nindex 0000000..e69de29\n",
                encoding="utf-8",
            )
            return verified

        previous_cwd = Path.cwd()
        try:
            os.chdir(repo)
            with mock.patch.object(RUNNER, "verify_candidate_manifest", side_effect=swap_after_verify):
                RUNNER.apply_worker_result(
                    argparse.Namespace(
                        manifest=str(manifest_path),
                        git_bin="git",
                        lifecycle_state=manifest["lifecycle_state_path"],
                        orchestration_run_id=manifest["orchestration_run_id"],
                        plan_execution_state=str(execution_state_path(manifest)),
                    )
                )
        finally:
            os.chdir(previous_cwd)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "safe\n")
        self.assertFalse((repo / "blocked.txt").exists())

    def test_validation_head_mutation_consumes_exactly_once_attempt(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={
                "allowed.txt": "original\n",
                "tests/smoke.sh": "#!/bin/sh\ngit -c user.name=Test -c user.email=test@example.invalid commit --allow-empty -qm validation-mutation\n",
            },
            validation=["tests/smoke.sh"],
        )
        self.addCleanup(temporary.cleanup)
        (repo / "tests/smoke.sh").chmod(0o755)
        git(repo, "add", "tests/smoke.sh")
        git(repo, "commit", "-qm", "make smoke executable")
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "head-mutation-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        args = (
            "validate", initial.stdout.strip(), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "head-mutation-validation"),
        )
        first = run_cli(repo, *args)
        self.assertEqual(first.returncode, 1)
        self.assertIn("changed review-clone HEAD", first.stderr)
        replay = run_cli(repo, *args[:-1], str(root / "head-mutation-replay"))
        self.assertEqual(replay.returncode, 1)
        self.assertIn("already been attempted", replay.stderr)

    def test_validation_ignores_ambient_home_toolchain_path(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["allowed.txt"],
            files={"allowed.txt": "original\n", "scripts/check.py": "value = 1\n"},
            validation=["python3 -m py_compile scripts/check.py"],
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fake_bin = root / "home" / ".local" / "bin"
        fake_bin.mkdir(parents=True)
        sentinel = root / "ambient-python-used"
        fake_python = fake_bin / "python3"
        fake_python.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n", encoding="utf-8")
        fake_python.chmod(0o755)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("candidate\\n", encoding="utf-8")',
            output_dir=root / "trusted-path-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        result = run_cli(
            repo, "validate", initial.stdout.strip(), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "trusted-path-validation"),
            env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(sentinel.exists())

    def test_apply_finalization_failure_leaves_recoverable_applying_state(self) -> None:
        temporary, repo, plan_path = self.make_repo(["allowed.txt"])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, _output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "allowed.txt").write_text("applied\\n", encoding="utf-8")',
            output_dir=root / "apply-recovery-initial",
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        manifest_path = Path(initial.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validated = run_cli(
            repo, "validate", str(manifest_path), "--suite", "authoritative",
            "--parent-diff-approved", "--critical-invariants-approved",
            "--output-dir", str(root / "apply-recovery-validation"),
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        original_persist = RUNNER.LifecycleState.persist

        def fail_finalization(state, data):
            if data.get("phase") == "applied":
                raise OSError("injected finalization failure")
            return original_persist(state, data)

        previous_cwd = Path.cwd()
        try:
            os.chdir(repo)
            with mock.patch.object(RUNNER.LifecycleState, "persist", new=fail_finalization):
                with self.assertRaisesRegex(RUNNER.RunnerError, "source patch was applied"):
                    RUNNER.apply_worker_result(
                        argparse.Namespace(
                            manifest=str(manifest_path), git_bin="git",
                            lifecycle_state=manifest["lifecycle_state_path"],
                            orchestration_run_id=manifest["orchestration_run_id"],
                            plan_execution_state=str(execution_state_path(manifest)),
                        )
                    )
        finally:
            os.chdir(previous_cwd)
        self.assertEqual((repo / "allowed.txt").read_text(encoding="utf-8"), "applied\n")
        lifecycle = json.loads(Path(manifest["lifecycle_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual(lifecycle["phase"], "applying")
        previous_cwd = Path.cwd()
        try:
            os.chdir(repo)
            RUNNER.finalize_apply(
                argparse.Namespace(
                    manifest=str(manifest_path), git_bin="git",
                    lifecycle_state=manifest["lifecycle_state_path"],
                    orchestration_run_id=manifest["orchestration_run_id"],
                    plan_execution_state=str(execution_state_path(manifest)),
                )
            )
        finally:
            os.chdir(previous_cwd)
        lifecycle = json.loads(Path(manifest["lifecycle_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual(lifecycle["phase"], "applied")

    def test_apply_recovery_rejects_directory_prefix_before_symlink_creation(self) -> None:
        temporary, repo, plan_path = self.make_repo(
            ["links/"],
            files={"target.txt": "target\n", "other.txt": "other\n"},
        )
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        initial, output, _worker = self.run_with_worker(
            repo,
            plan_path,
            '(worker_repo / "links").mkdir(exist_ok=True)\n'
            '(worker_repo / "links" / "created").symlink_to("../target.txt")',
            output_dir=root / "symlink-recovery",
        )
        self.assertEqual(initial.returncode, 1)
        self.assertIn("explicit file path", initial.stderr)
        self.assertFalse((output / "worker.stdout").exists())

def evaluate_selected_worker_contract_fixture(
    path: Path, *, used_for_tuning: bool
) -> list[dict[str, object]]:
    """Run one explicitly selected sealed fixture through the production runner behavior."""
    SandboxedPlanWorkerTests.setUpClass()
    evaluator = SandboxedPlanWorkerTests(
        methodName="test_default_worker_command_uses_supported_external_sandbox_flags"
    )
    return evaluate_worker_contract_fixture(
        path,
        evaluator.evaluate_worker_contract_case,
        used_for_tuning=used_for_tuning,
    )



ADAPTER_SCRIPT = ROOT / "scripts/run-parallel-plans.py"
GROUP_AUTHORITY_SCRIPT = ROOT / "scripts/parallel-plan-state.py"
TEMPLATE_ADAPTER_SCRIPT = (
    ROOT / "template/.project-agent-workflow/scripts/run-parallel-plans.py"
)


def adapter_digest(value) -> str:
    data = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


class GroupedExecutionAdapterTests(unittest.TestCase):
    """Ordered integration of independent member candidates by the parent.

    Every scenario uses mocked bounded candidate manifests and isolated local
    Git repositories. No live external agent, network, or credential is used.
    """

    ALPHA = "docs/plan/active/284-alpha.md"
    BETA = "docs/plan/active/285-beta.md"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.repo = self.base / "repo"
        (self.repo / "docs/plan/active").mkdir(parents=True)
        (self.repo / "docs/plan/execution-groups").mkdir(parents=True)
        (self.repo / "src").mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", "https://example.invalid/owner/repo.git")
        (self.repo / "AGENTS.md").write_text("fixture\n", encoding="utf-8")
        (self.repo / "src/alpha.py").write_text(
            "def alpha(value):\n    return value\n", encoding="utf-8"
        )
        (self.repo / "src/beta.py").write_text(
            "from src.alpha import alpha\n\n\ndef beta():\n    return alpha(1)\n",
            encoding="utf-8",
        )
        self.write_plan("284", "alpha", ["src/alpha.py", "src/alpha_extra.py"])
        self.write_plan("285", "beta", ["src/beta.py"])
        self.write_description()
        self.start_commit = self.commit("baseline")
        self.state = self.base / "group-state.json"
        self.initialize_group()

    # -- fixture helpers ------------------------------------------------

    def git(self, *arguments: str, cwd: Path | None = None) -> str:
        completed = subprocess.run(
            ["git", "-C", str(cwd or self.repo), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return completed.stdout.strip()

    def write_plan(self, plan_id: str, slug: str, write_scope: list[str]) -> Path:
        body = (
            f"# Plan {plan_id}\n\n"
            "status: in_progress\n"
            "plan_purpose: implementation\n"
            f"primary_invariant: invariant {plan_id}\n"
            "write_scope:\n"
            + "".join(f"  - {entry}\n" for entry in write_scope)
            + "context_files:\n  - AGENTS.md\n"
            "\n## Tasks\n\n- [ ] implement\n"
        )
        path = self.repo / f"docs/plan/active/{plan_id}-{slug}.md"
        path.write_text(body, encoding="utf-8")
        return path

    def scope_digest(self, entries: list[str]) -> str:
        return adapter_digest(
            json.dumps(entries, sort_keys=True, separators=(",", ":"))
        )

    def write_description(self) -> None:
        document = {
            "schema_version": 1,
            "group_id": "alpha-beta",
            "target_ref": "refs/heads/main",
            "declared_independence": "disjoint product modules with no shared interface",
            "members": [
                {
                    "plan_id": "284",
                    "plan_path": self.ALPHA,
                    "plan_digest": adapter_digest(
                        (self.repo / self.ALPHA).read_bytes()
                    ),
                    "write_scope_digest": self.scope_digest(
                        ["src/alpha.py", "src/alpha_extra.py"]
                    ),
                },
                {
                    "plan_id": "285",
                    "plan_path": self.BETA,
                    "plan_digest": adapter_digest((self.repo / self.BETA).read_bytes()),
                    "write_scope_digest": self.scope_digest(["src/beta.py"]),
                },
            ],
        }
        (self.repo / "docs/plan/execution-groups/alpha-beta.json").write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_group(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GROUP_AUTHORITY_SCRIPT), *arguments],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_adapter(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ADAPTER_SCRIPT), *arguments],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def initialize_group(self) -> None:
        completed = self.run_group(
            "group-init",
            str(self.state),
            "--group-description",
            "docs/plan/execution-groups/alpha-beta.json",
            "--target-ref",
            "refs/heads/main",
            "--start-commit",
            self.start_commit,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def issue_permit(self, member: str, permit_id: str) -> Path:
        output = self.base / f"{permit_id}.json"
        completed = self.run_group(
            "permit-issue",
            str(self.state),
            "--member",
            member,
            "--permit-id",
            permit_id,
            "--workspace-digest",
            adapter_digest(permit_id),
            "--output",
            str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return output

    def transfer_permit(
        self, member: str, prior: str, permit_id: str, base_commit: str
    ) -> Path:
        completed = self.run_group(
            "transfer-baseline",
            str(self.state),
            "--member",
            member,
            "--prior-permit-id",
            prior,
            "--new-permit-id",
            permit_id,
            "--new-base-commit",
            base_commit,
            "--workspace-digest",
            adapter_digest(permit_id),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return self.reissue_permit_document(member, permit_id)

    def reissue_permit_document(self, member: str, permit_id: str) -> Path:
        """Materialize the permit document the authority bound to the member."""

        state = json.loads(self.state.read_text(encoding="utf-8"))
        member_state = state["members"][member]
        permit = {
            "schema_version": 1,
            "group_id": state["group_id"],
            "group_description_digest": state["group_description_digest"],
            "plan_path": member,
            "permit_id": permit_id,
            "baseline_generation": member_state["baseline_generation"],
            "base_commit": member_state["base_commit"],
            "repository_identity": state["repository_identity"],
            "state_digest": "",
        }
        path = self.base / f"{permit_id}.json"
        path.write_text(json.dumps(permit, indent=2) + "\n", encoding="utf-8")
        return path

    def candidate(
        self, member: str, source_head: str, edits: dict[str, str], label: str
    ) -> Path:
        """Build one bounded mocked worker candidate against an exact baseline."""

        workspace = self.base / f"candidate-{label}"
        workspace.mkdir()
        clone = workspace / "clone"
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--local",
                "--no-checkout",
                str(self.repo),
                str(clone),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.git("checkout", "--detach", "--force", source_head, cwd=clone)
        for relative, content in edits.items():
            target = clone / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.git("add", "--all", cwd=clone)
        patch = subprocess.run(
            [
                "git",
                "-C",
                str(clone),
                "-c",
                "core.abbrev=40",
                "diff",
                "--cached",
                "--binary",
                "--full-index",
                "--no-color",
                "--no-ext-diff",
                "--src-prefix=a/",
                "--dst-prefix=b/",
                source_head,
            ],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout
        patch_path = workspace / "candidate.patch"
        patch_path.write_bytes(patch)
        manifest = {
            "schema_version": 1,
            "plan_path": member,
            "source_head": source_head,
            "patch_path": str(patch_path),
            "patch_digest": hashlib.sha256(patch).hexdigest(),
            "changed_paths": sorted(edits),
            "worker_completion_receipt_digest": hashlib.sha256(
                label.encode("utf-8")
            ).hexdigest(),
        }
        manifest_path = workspace / "candidate-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest_path

    def assemble(
        self, member: str, permit: Path, manifest: Path, label: str, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return self.run_adapter(
            "assemble",
            "--state",
            str(self.state),
            "--permit",
            str(permit),
            "--plan",
            member,
            "--manifest",
            str(manifest),
            "--output",
            str(self.base / f"assembly-{label}.json"),
            *extra,
        )

    def record_review(
        self, member: str, record: dict, *, count: str = "1", chain: str = "chain"
    ) -> None:
        completed = self.run_group(
            "record-review",
            str(self.state),
            "--member",
            member,
            "--registry-path-digest",
            adapter_digest("registry"),
            "--registry-event-count",
            count,
            "--registry-event-chain-digest",
            adapter_digest(chain),
            "--assembly-record-digest",
            record["record_digest"],
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def reviewed_commit(self, record: dict, branch: str) -> str:
        """Create one descendant commit whose whole diff equals the assembly."""

        patch = Path(record["assembled_patch_path"]).read_bytes()
        self.git("checkout", "-q", "-b", branch, record["base_commit"])
        subprocess.run(
            ["git", "-C", str(self.repo), "apply", "--whitespace=nowarn", "-"],
            input=patch,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"reviewed {branch}")
        commit = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        return commit

    def publish(
        self, member: str, permit: Path, label: str, commit: str, owner: str
    ) -> subprocess.CompletedProcess[str]:
        acquired = self.run_group(
            "lease-acquire", str(self.state), "--member", member, "--owner", owner
        )
        self.assertEqual(acquired.returncode, 0, acquired.stderr)
        try:
            return self.run_adapter(
                "publish",
                "--state",
                str(self.state),
                "--permit",
                str(permit),
                "--plan",
                member,
                "--assembly",
                str(self.base / f"assembly-{label}.json"),
                "--commit",
                commit,
                "--owner",
                owner,
                "--journal",
                str(self.base / f"journal-{label}.json"),
            )
        finally:
            self.run_group(
                "lease-release", str(self.state), "--owner", owner
            )

    def assembly_record(self, label: str) -> dict:
        return json.loads(
            (self.base / f"assembly-{label}.json").read_text(encoding="utf-8")
        )

    def integrate_alpha(self) -> tuple[dict, str]:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value, scale=1):\n    return value * scale\n"},
            "alpha",
        )
        assembled = self.assemble(self.ALPHA, permit, manifest, "alpha")
        self.assertEqual(assembled.returncode, 0, assembled.stderr)
        record = self.assembly_record("alpha")
        commit = self.reviewed_commit(record, "review-alpha")
        self.record_review(self.ALPHA, record)
        published = self.publish(self.ALPHA, permit, "alpha", commit, "parent-alpha")
        self.assertEqual(published.returncode, 0, published.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), commit)
        return record, commit

    def test_assembly_carries_added_files_and_scope_checks_them(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {
                "src/alpha.py": "from src.alpha_extra import helper\n\n\ndef alpha(value):\n    return helper(value)\n",
                "src/alpha_extra.py": "def helper(value):\n    return value + 1\n",
            },
            "alpha",
        )
        assembled = self.assemble(self.ALPHA, permit, manifest, "alpha")
        self.assertEqual(assembled.returncode, 0, assembled.stderr)
        record = self.assembly_record("alpha")
        self.assertEqual(
            record["changed_paths"], ["src/alpha.py", "src/alpha_extra.py"]
        )
        patch = (self.base / "assembly-alpha.json.patch").read_bytes()
        self.assertIn(b"src/alpha_extra.py", patch)
        commit = self.reviewed_commit(record, "review-alpha")
        self.record_review(self.ALPHA, record)
        published = self.publish(self.ALPHA, permit, "alpha", commit, "parent-alpha")
        self.assertEqual(published.returncode, 0, published.stderr)
        self.assertEqual(
            (self.repo / "src/alpha_extra.py").read_text(encoding="utf-8"),
            "def helper(value):\n    return value + 1\n",
        )

    def test_added_file_outside_the_member_scope_is_refused(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {
                "src/alpha.py": "def alpha(value):\n    return value + 1\n",
                "src/smuggled.py": "SMUGGLED = True\n",
            },
            "alpha",
        )
        assembled = self.assemble(self.ALPHA, permit, manifest, "alpha")
        self.assertEqual(assembled.returncode, 1)
        self.assertIn("outside the member write scope", assembled.stderr)
        self.assertIn("src/smuggled.py", assembled.stderr)
        self.assertFalse((self.base / "assembly-alpha.json").exists())

    def test_publication_refuses_an_unreviewed_replacement_assembly(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        first = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "first",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, first, "first").returncode, 0
        )
        reviewed = self.assembly_record("first")
        self.record_review(self.ALPHA, reviewed)
        second = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 2\n"},
            "second",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, second, "second").returncode, 0
        )
        replacement = self.assembly_record("second")
        self.assertNotEqual(replacement["record_digest"], reviewed["record_digest"])
        commit = self.reviewed_commit(replacement, "review-second")
        published = self.publish(self.ALPHA, permit, "second", commit, "parent-alpha")
        self.assertEqual(published.returncode, 1)
        self.assertIn("independent review", published.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), self.start_commit)
        self.record_review(self.ALPHA, replacement, count="2", chain="chain-2")
        accepted = self.publish(self.ALPHA, permit, "second", commit, "parent-alpha")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), commit)

    # -- ordered integration --------------------------------------------

    def test_adapter_version_is_reported_and_mirrored_in_the_template(self) -> None:
        completed = self.run_adapter("adapter-version")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"adapter_version": 1})
        self.assertEqual(
            ADAPTER_SCRIPT.read_bytes(), TEMPLATE_ADAPTER_SCRIPT.read_bytes()
        )
        self.assertEqual(
            ADAPTER_SCRIPT.stat().st_mode & 0o777,
            TEMPLATE_ADAPTER_SCRIPT.stat().st_mode & 0o777,
        )

    def test_first_member_publishes_and_the_later_member_reuses_the_new_target(
        self,
    ) -> None:
        alpha_record, alpha_commit = self.integrate_alpha()
        self.assertEqual(alpha_record["resolution_kind"], "unchanged_application")
        self.assertEqual(alpha_record["result_author"], "worker")

        beta_permit = self.issue_permit(self.BETA, "permit-b1")
        beta_manifest = self.candidate(
            self.BETA,
            self.start_commit,
            {
                "src/beta.py": "from src.alpha import alpha\n\n\ndef beta():\n"
                "    return alpha(2)\n"
            },
            "beta",
        )
        stale = self.assemble(self.BETA, beta_permit, beta_manifest, "beta-stale")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("superseded baseline", stale.stderr)

        transferred = self.transfer_permit(
            self.BETA, "permit-b1", "permit-b2", alpha_commit
        )
        assembled = self.assemble(self.BETA, transferred, beta_manifest, "beta")
        self.assertEqual(assembled.returncode, 0, assembled.stderr)
        beta_record = self.assembly_record("beta")
        self.assertEqual(beta_record["base_commit"], alpha_commit)
        self.assertEqual(beta_record["original_source_head"], self.start_commit)
        self.assertEqual(beta_record["changed_paths"], ["src/beta.py"])
        self.assertEqual(
            beta_record["original_manifest_digest"],
            adapter_digest(beta_manifest.read_bytes()),
        )

        beta_commit = self.reviewed_commit(beta_record, "review-beta")
        self.record_review(self.BETA, beta_record)
        published = self.publish(
            self.BETA, transferred, "beta", beta_commit, "parent-beta"
        )
        self.assertEqual(published.returncode, 0, published.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), beta_commit)
        self.assertIn(
            "value * scale", (self.repo / "src/alpha.py").read_text(encoding="utf-8")
        )
        self.assertIn("alpha(2)", (self.repo / "src/beta.py").read_text(encoding="utf-8"))

        complete = self.run_group("group-complete", str(self.state))
        self.assertEqual(complete.returncode, 0, complete.stderr)

    def test_textual_conflict_needs_the_reserved_parent_adjustment_slot(self) -> None:
        beta_permit = self.issue_permit(self.BETA, "permit-b1")
        beta_manifest = self.candidate(
            self.BETA,
            self.start_commit,
            {
                "src/beta.py": "from src.alpha import alpha\n\n\ndef beta():\n"
                "    return alpha(2)\n"
            },
            "beta",
        )
        # One independently authorized target change rewrites the same lines.
        (self.repo / "src/beta.py").write_text(
            "from src.alpha import alpha\n\n\ndef beta(offset=0):\n"
            "    return alpha(1) + offset\n",
            encoding="utf-8",
        )
        moved = self.commit("independently authorized change")
        transferred = self.transfer_permit(
            self.BETA, "permit-b1", "permit-b2", moved
        )

        conflicted = self.assemble(self.BETA, transferred, beta_manifest, "beta")
        self.assertEqual(conflicted.returncode, 1)
        self.assertIn("does not apply to the current baseline", conflicted.stderr)

        resolution = self.parent_resolution(
            moved,
            {
                "src/beta.py": "from src.alpha import alpha\n\n\ndef beta(offset=0):\n"
                "    return alpha(2) + offset\n"
            },
            "beta-resolution",
        )
        unreserved = self.assemble(
            self.BETA,
            transferred,
            beta_manifest,
            "beta",
            "--resolution",
            str(resolution),
        )
        self.assertEqual(unreserved.returncode, 1)
        self.assertIn("reserved parent adjustment slot", unreserved.stderr)

        reserved = self.run_group(
            "adjust-reserve",
            str(self.state),
            "--member",
            self.BETA,
            "--permit-id",
            "permit-b2",
            "--incoming-candidate-digest",
            adapter_digest(beta_manifest.read_bytes()),
            "--base-digest",
            adapter_digest(moved),
        )
        self.assertEqual(reserved.returncode, 0, reserved.stderr)
        resolved = self.assemble(
            self.BETA,
            transferred,
            beta_manifest,
            "beta",
            "--resolution",
            str(resolution),
        )
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        record = self.assembly_record("beta")
        self.assertEqual(record["resolution_kind"], "parent_adjusted")
        self.assertEqual(record["result_author"], "parent")

        state = json.loads(self.state.read_text(encoding="utf-8"))
        member = state["members"][self.BETA]
        self.assertEqual(member["parent_adjustment"]["state"], "closed")
        self.assertEqual(member["counters"]["corrections"], 1)

        # The single slot excludes a second substantive parent edit.
        again = self.run_group(
            "adjust-reserve",
            str(self.state),
            "--member",
            self.BETA,
            "--permit-id",
            "permit-b2",
            "--incoming-candidate-digest",
            adapter_digest(beta_manifest.read_bytes()),
            "--base-digest",
            adapter_digest(moved),
        )
        self.assertEqual(again.returncode, 1)
        self.assertIn("single correction slot", again.stderr)

    def parent_resolution(
        self, base_commit: str, edits: dict[str, str], label: str
    ) -> Path:
        manifest = self.candidate(self.BETA, base_commit, edits, label)
        return Path(json.loads(manifest.read_text(encoding="utf-8"))["patch_path"])

    def test_parent_resolution_may_not_leave_the_member_write_scope(self) -> None:
        beta_permit = self.issue_permit(self.BETA, "permit-b1")
        beta_manifest = self.candidate(
            self.BETA,
            self.start_commit,
            {
                "src/beta.py": "from src.alpha import alpha\n\n\ndef beta():\n"
                "    return alpha(2)\n"
            },
            "beta",
        )
        (self.repo / "src/beta.py").write_text(
            "from src.alpha import alpha\n\n\ndef beta(offset=0):\n"
            "    return alpha(1) + offset\n",
            encoding="utf-8",
        )
        moved = self.commit("independently authorized change")
        transferred = self.transfer_permit(self.BETA, "permit-b1", "permit-b2", moved)
        self.run_group(
            "adjust-reserve",
            str(self.state),
            "--member",
            self.BETA,
            "--permit-id",
            "permit-b2",
            "--incoming-candidate-digest",
            adapter_digest(beta_manifest.read_bytes()),
            "--base-digest",
            adapter_digest(moved),
        )
        resolution = self.parent_resolution(
            moved,
            {
                "src/beta.py": "from src.alpha import alpha\n\n\ndef beta(offset=0):\n"
                "    return alpha(2) + offset\n",
                "src/alpha.py": "def alpha(value):\n    return value + 1\n",
            },
            "beta-drift",
        )
        drifted = self.assemble(
            self.BETA,
            transferred,
            beta_manifest,
            "beta",
            "--resolution",
            str(resolution),
        )
        self.assertEqual(drifted.returncode, 1)
        self.assertIn("outside the member write scope", drifted.stderr)

    def test_semantic_conflict_applies_cleanly_and_still_requires_validation(
        self,
    ) -> None:
        """A disjoint contract change is not detected by patch application."""

        alpha_record, alpha_commit = self.integrate_alpha()
        self.assertEqual(alpha_record["resolution_kind"], "unchanged_application")
        beta_permit = self.issue_permit(self.BETA, "permit-b1")
        beta_manifest = self.candidate(
            self.BETA,
            self.start_commit,
            {
                "src/beta.py": "from src.alpha import alpha\n\n\ndef beta():\n"
                "    return alpha()\n"
            },
            "beta",
        )
        transferred = self.transfer_permit(
            self.BETA, "permit-b1", "permit-b2", alpha_commit
        )
        assembled = self.assemble(self.BETA, transferred, beta_manifest, "beta")
        self.assertEqual(assembled.returncode, 0, assembled.stderr)
        record = self.assembly_record("beta")
        self.assertEqual(record["resolution_kind"], "unchanged_application")
        # Mechanical applicability is not acceptance: review and validation stay
        # required because the caller still uses the superseded contract.
        self.assertTrue(record["review_required"])
        self.assertTrue(record["validation_required"])

    def test_publication_requires_a_review_at_the_current_baseline(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "alpha",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, manifest, "alpha").returncode, 0
        )
        record = self.assembly_record("alpha")
        commit = self.reviewed_commit(record, "review-alpha")
        unreviewed = self.publish(self.ALPHA, permit, "alpha", commit, "parent-alpha")
        self.assertEqual(unreviewed.returncode, 1)
        self.assertIn("qualifying independent review", unreviewed.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), self.start_commit)

    def test_publication_rejects_a_commit_that_is_not_the_admitted_patch(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "alpha",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, manifest, "alpha").returncode, 0
        )
        self.record_review(self.ALPHA, self.assembly_record("alpha"))
        self.git("checkout", "-q", "-b", "review-alpha", self.start_commit)
        (self.repo / "src/alpha.py").write_text(
            "def alpha(value):\n    return value + 99\n", encoding="utf-8"
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "different result")
        commit = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        published = self.publish(self.ALPHA, permit, "alpha", commit, "parent-alpha")
        self.assertEqual(published.returncode, 1)
        self.assertIn("differs from the admitted", published.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), self.start_commit)

    def test_publication_refuses_a_moved_target_and_preserves_it(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "alpha",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, manifest, "alpha").returncode, 0
        )
        record = self.assembly_record("alpha")
        commit = self.reviewed_commit(record, "review-alpha")
        self.record_review(self.ALPHA, record)
        moved = self.commit("intervening target movement")
        published = self.publish(self.ALPHA, permit, "alpha", commit, "parent-alpha")
        self.assertEqual(published.returncode, 1)
        self.assertIn("target moved after review", published.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), moved)

    def test_publication_defers_instead_of_discarding_dirty_target_work(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "alpha",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, manifest, "alpha").returncode, 0
        )
        record = self.assembly_record("alpha")
        commit = self.reviewed_commit(record, "review-alpha")
        self.record_review(self.ALPHA, record)
        (self.repo / "AGENTS.md").write_text("user work in progress\n", encoding="utf-8")
        published = self.publish(self.ALPHA, permit, "alpha", commit, "parent-alpha")
        self.assertEqual(published.returncode, 1)
        self.assertIn("uncommitted work", published.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), self.start_commit)
        self.assertEqual(
            (self.repo / "AGENTS.md").read_text(encoding="utf-8"),
            "user work in progress\n",
        )
        self.assertFalse((self.base / "journal-alpha.json").exists())

    def test_interrupted_publication_finalizes_only_the_planned_transition(
        self,
    ) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "alpha",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, manifest, "alpha").returncode, 0
        )
        record = self.assembly_record("alpha")
        commit = self.reviewed_commit(record, "review-alpha")
        self.record_review(self.ALPHA, record)
        journal = self.base / "journal-manual.json"
        self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.ALPHA,
            "--owner",
            "parent-alpha",
        )
        self.addCleanup(
            self.run_group, "lease-release", str(self.state), "--owner", "parent-alpha"
        )

        # An interruption before the ref moves aborts without source effects.
        self.write_journal(journal, self.ALPHA, "permit-a1", commit, record)
        aborted = self.run_adapter("publish-recover", "--journal", str(journal))
        self.assertEqual(aborted.returncode, 0, aborted.stderr)
        self.assertEqual(json.loads(aborted.stdout)["recovery"], "aborted")
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), self.start_commit)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertFalse(state["members"][self.ALPHA]["publication"]["published"])

        # An interruption after the ref moved finalizes the same transition once.
        journal_after = self.base / "journal-after.json"
        self.write_journal(journal_after, self.ALPHA, "permit-a1", commit, record)
        self.git("merge", "--ff-only", commit)
        finalized = self.run_adapter("publish-recover", "--journal", str(journal_after))
        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        self.assertEqual(json.loads(finalized.stdout)["recovery"], "finalized")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertTrue(state["members"][self.ALPHA]["publication"]["published"])
        self.assertEqual(
            state["members"][self.ALPHA]["publication"]["commit"], commit
        )
        replayed = self.run_adapter("publish-recover", "--journal", str(journal_after))
        self.assertEqual(replayed.returncode, 0, replayed.stderr)
        self.assertEqual(json.loads(replayed.stdout)["recovery"], "noop")

    def test_ambiguous_crash_evidence_preserves_the_target(self) -> None:
        permit = self.issue_permit(self.ALPHA, "permit-a1")
        manifest = self.candidate(
            self.ALPHA,
            self.start_commit,
            {"src/alpha.py": "def alpha(value):\n    return value + 1\n"},
            "alpha",
        )
        self.assertEqual(
            self.assemble(self.ALPHA, permit, manifest, "alpha").returncode, 0
        )
        record = self.assembly_record("alpha")
        commit = self.reviewed_commit(record, "review-alpha")
        journal = self.base / "journal-ambiguous.json"
        self.write_journal(journal, self.ALPHA, "permit-a1", commit, record)
        moved = self.commit("unrelated target movement")
        recovered = self.run_adapter("publish-recover", "--journal", str(journal))
        self.assertEqual(recovered.returncode, 1)
        self.assertIn("publication is not replayed", recovered.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), moved)

    def write_journal(
        self, path: Path, member: str, permit_id: str, commit: str, record: dict
    ) -> None:
        journal = {
            "schema_version": 1,
            "adapter_version": 1,
            "state": "intended",
            "group_id": "alpha-beta",
            "plan_path": member,
            "permit_id": permit_id,
            "owner": "parent-alpha",
            "target_ref": "refs/heads/main",
            "expected_old_commit": record["base_commit"],
            "new_commit": commit,
            "assembly_record_path": str(self.base / "assembly-alpha.json"),
            "assembled_patch_digest": record["assembled_patch_digest"],
            "assembly_record_digest": record["record_digest"],
            "target_checkout": str(self.repo),
            "state_path": str(self.state),
        }
        journal["journal_digest"] = adapter_digest(
            json.dumps(journal, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        )
        path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)

    def test_stopped_member_preserves_the_published_partner(self) -> None:
        _record, alpha_commit = self.integrate_alpha()
        stopped = self.run_group(
            "member-stop",
            str(self.state),
            "--member",
            self.BETA,
            "--reason",
            "replan_required",
        )
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), alpha_commit)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertTrue(state["members"][self.ALPHA]["publication"]["published"])
        incomplete = self.run_group("group-complete", str(self.state))
        self.assertEqual(incomplete.returncode, 1)
        self.assertIn(self.BETA, incomplete.stderr)
        completion = self.run_group(
            "check-enrollment",
            "--plan",
            self.ALPHA,
            "--operation",
            "completion",
            "--group-state",
            str(self.state),
        )
        self.assertEqual(completion.returncode, 0, completion.stderr)
        refused = self.run_group(
            "check-enrollment",
            "--plan",
            self.BETA,
            "--operation",
            "completion",
            "--group-state",
            str(self.state),
        )
        self.assertEqual(refused.returncode, 1)
        self.assertIn("has not published", refused.stderr)

    def test_duplicate_publication_is_refused(self) -> None:
        _record, commit = self.integrate_alpha()
        # Publication consumes the member permit, so a replay is refused before
        # it can reach the target at all.
        again = self.publish(
            self.ALPHA, self.base / "permit-a1.json", "alpha", commit, "parent-alpha"
        )
        self.assertEqual(again.returncode, 1)
        self.assertIn("not the current open permit", again.stderr)
        self.assertEqual(self.git("rev-parse", "refs/heads/main"), commit)

        acquired = self.run_group(
            "lease-acquire",
            str(self.state),
            "--member",
            self.ALPHA,
            "--owner",
            "parent-alpha",
        )
        self.assertEqual(acquired.returncode, 0, acquired.stderr)
        self.addCleanup(
            self.run_group, "lease-release", str(self.state), "--owner", "parent-alpha"
        )
        duplicate = self.run_group(
            "publication-record",
            str(self.state),
            "--member",
            self.ALPHA,
            "--permit-id",
            "permit-a1",
            "--commit",
            commit,
            "--assembly-digest",
            adapter_digest("assembly"),
        )
        self.assertEqual(duplicate.returncode, 1)
        self.assertIn("already published", duplicate.stderr)


ROOT_GUARD = ROOT / "scripts/project_workflow/worktree_guard.py"
ROOT_WORKTREE_MANAGER = ROOT / "scripts/manage-plan-worktrees.py"


class RunnerTaskWorktreeBoundaryTests(unittest.TestCase):
    """The runner and the grouped adapter must start from their bound worktree.

    Both tools write where they were started, so a check that runs after the
    first repository effect would report a boundary that was already crossed.
    """

    PLAN = "docs/plan/active/001-sandboxed.md"
    OTHER = "docs/plan/active/002-other.md"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.home.mkdir()
        home_patch = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.allowed_root = self.base / "worktrees"
        self.allowed_root.mkdir(mode=0o700)
        self.repo = self.base / "repo"
        (self.repo / "docs/plan/active").mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "dev")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "remote", "add", "origin", "https://example.invalid/owner/repo.git")
        for selector in (self.PLAN, self.OTHER):
            (self.repo / selector).write_text("# fixture\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("fixture\n", encoding="utf-8")

    def ship_guard(self) -> None:
        package = self.repo / "scripts/project_workflow"
        package.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_GUARD, package / "worktree_guard.py")
        shutil.copy2(ROOT_WORKTREE_MANAGER, self.repo / "scripts/manage-plan-worktrees.py")

    def commit(self) -> None:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "baseline", "--no-verify")

    def prepare(self, selector: str) -> Path:
        result = subprocess.run(
            [
                sys.executable,
                str(self.repo / "scripts/manage-plan-worktrees.py"),
                "prepare",
                selector,
                "--allowed-root",
                str(self.allowed_root),
                "--owner-id",
                "boundary-test",
            ],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["worktree"])

    def test_repository_without_the_guard_keeps_previous_behaviour(self) -> None:
        self.commit()
        RUNNER.require_plan_worktree(self.repo, self.PLAN, "running a sandboxed plan worker")

    def test_pre_existing_checkout_is_refused(self) -> None:
        self.ship_guard()
        self.commit()
        with self.assertRaises(RUNNER.RunnerError) as raised:
            RUNNER.require_plan_worktree(self.repo, self.PLAN, "running a sandboxed plan worker")
        self.assertIn("must not run in the pre-existing checkout", str(raised.exception))
        self.assertIn("manage-plan-worktrees.py", str(raised.exception))

    def test_bound_plan_worktree_is_accepted(self) -> None:
        self.ship_guard()
        self.commit()
        worktree = self.prepare(self.PLAN)
        RUNNER.require_plan_worktree(worktree, self.PLAN, "running a sandboxed plan worker")

    def test_another_members_worktree_is_refused(self) -> None:
        self.ship_guard()
        self.commit()
        worktree = self.prepare(self.PLAN)
        with self.assertRaises(RUNNER.RunnerError) as raised:
            RUNNER.require_plan_worktree(worktree, self.OTHER, "running a sandboxed plan worker")
        self.assertIn(self.OTHER, str(raised.exception))

    def test_grouped_dispatch_refuses_an_unbound_member_checkout(self) -> None:
        self.ship_guard()
        self.commit()
        adapter = load_adapter_module()
        with self.assertRaises(adapter.AdapterError) as raised:
            adapter.require_member_worktree(self.repo, self.PLAN)
        self.assertIn("must not run in the pre-existing checkout", str(raised.exception))
        worktree = self.prepare(self.PLAN)
        adapter.require_member_worktree(worktree, self.PLAN)


def load_adapter_module():
    spec = importlib.util.spec_from_file_location(
        "grouped_execution_adapter_under_test", ADAPTER_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
