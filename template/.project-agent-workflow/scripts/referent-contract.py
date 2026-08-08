#!/usr/bin/env python3
"""Create and validate referent-first semantic contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TASK_KINDS = {
    "investigation",
    "state-design",
    "api-design",
    "data-design",
    "naming",
    "causal-summary",
    "general-design",
}
REFERENT_KINDS = {
    "condition",
    "state",
    "event",
    "value",
    "record",
    "actor",
    "action",
    "artifact",
    "input",
    "output",
    "error",
    "entity",
    "attribute",
    "identifier",
    "other",
}
REASONING_ROLES = {
    "purpose",
    "means",
    "evidence",
    "input",
    "output",
    "judgment",
    "result",
    "context",
    "other",
}
CERTAINTIES = {"confirmed", "inferred", "unknown", "disputed"}
NAMING_DECISIONS = {"pending", "blocked", "label", "concrete_text"}
STATES = {
    "source_registered",
    "unknowns_recorded",
    "referents_sealed",
    "labels_assigned",
    "draft_created",
    "semantic_review_passed",
    "closed_advisory",
}
ALLOWED_TRANSITIONS = {
    (None, "source_registered", "init"),
    ("source_registered", "unknowns_recorded", "review-unknowns"),
    ("unknowns_recorded", "referents_sealed", "seal-referents"),
    ("referents_sealed", "labels_assigned", "finalize-labels"),
    ("labels_assigned", "draft_created", "record-draft"),
    ("draft_created", "semantic_review_passed", "record-review"),
    ("draft_created", "closed_advisory", "close-advisory"),
}


class ContractError(ValueError):
    """Raised when a contract violates the lifecycle or schema."""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"missing contract: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("contract root must be an object")
    return value


def write_contract(path: Path, contract: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def transition(contract: dict[str, Any], target: str, action: str) -> None:
    source = contract.get("state")
    contract["state"] = target
    contract["updated_at"] = now()
    contract.setdefault("transitions", []).append(
        {"from": source, "to": target, "action": action, "at": contract["updated_at"]}
    )


def require_state(contract: dict[str, Any], *allowed: str) -> None:
    if contract.get("state") not in allowed:
        joined = ", ".join(allowed)
        raise ContractError(f"state is {contract.get('state')}, expected one of: {joined}")


def find_referent(contract: dict[str, Any], referent_id: str) -> dict[str, Any]:
    for referent in contract.get("referents", []):
        if referent.get("id") == referent_id:
            return referent
    raise ContractError(f"unknown referent id: {referent_id}")


def referent_projection(contract: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "purpose",
        "concrete_target",
        "referent_kind",
        "reasoning_role",
        "relations",
        "evidence",
        "certainty",
    )
    return {
        "schema_version": contract.get("schema_version"),
        "slug": contract.get("slug"),
        "task_kind": contract.get("task_kind"),
        "source": contract.get("source"),
        "target": contract.get("target"),
        "unknowns_reviewed": contract.get("unknowns_reviewed"),
        "unknowns": contract.get("unknowns", []),
        "referents": [
            {field: referent.get(field) for field in fields}
            for referent in contract.get("referents", [])
        ],
    }


def resolve_artifact(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else Path.cwd() / path


def nonempty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")


def unique_ids(items: list[dict[str, Any]], field: str) -> None:
    values = [item.get("id") for item in items]
    if any(not isinstance(value, str) or not value for value in values):
        raise ContractError(f"{field} ids must be non-empty strings")
    if len(values) != len(set(values)):
        raise ContractError(f"{field} ids must be unique")


def validate_contract(contract: dict[str, Any], *, check_files: bool = True) -> None:
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version must be {SCHEMA_VERSION}")
    nonempty_string(contract.get("slug"), "slug")
    if contract.get("task_kind") not in TASK_KINDS:
        raise ContractError(f"unsupported task_kind: {contract.get('task_kind')}")
    if contract.get("mode") not in {"advisory", "required"}:
        raise ContractError("mode must be advisory or required")
    if contract.get("state") not in STATES:
        raise ContractError(f"unsupported state: {contract.get('state')}")
    if not isinstance(contract.get("active"), bool):
        raise ContractError("active must be a boolean")
    if contract.get("state") in {"semantic_review_passed", "closed_advisory"}:
        if contract.get("active"):
            raise ContractError("completed contracts must not remain active")
    elif not contract.get("active"):
        raise ContractError("incomplete contracts must remain active")
    transitions = contract.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        raise ContractError("transitions must be a non-empty list")
    previous: str | None = None
    for index, record in enumerate(transitions):
        if not isinstance(record, dict):
            raise ContractError("transition records must be objects")
        source = record.get("from")
        target = record.get("to")
        action = record.get("action")
        if source != previous:
            raise ContractError(f"transition {index} does not continue from {previous}")
        if action == "reopen":
            if source not in STATES - {"source_registered", "unknowns_recorded"} or target != "unknowns_recorded":
                raise ContractError(f"transition {index} is not a valid reopen")
        elif (source, target, action) not in ALLOWED_TRANSITIONS:
            raise ContractError(f"transition {index} is not allowed: {source} -> {target} ({action})")
        nonempty_string(record.get("at"), f"transition {index} at")
        previous = target
    if previous != contract.get("state"):
        raise ContractError("final transition does not match contract state")
    if not isinstance(contract.get("source"), dict) or not isinstance(contract.get("target"), dict):
        raise ContractError("source and target must be objects")
    nonempty_string(contract["source"].get("path"), "source.path")
    nonempty_string(contract["target"].get("path"), "target.path")
    if not isinstance(contract.get("unknowns_reviewed"), bool):
        raise ContractError("unknowns_reviewed must be a boolean")
    unknowns = contract.get("unknowns")
    referents = contract.get("referents")
    if not isinstance(unknowns, list) or not all(isinstance(item, dict) for item in unknowns):
        raise ContractError("unknowns must be a list of objects")
    if not isinstance(referents, list) or not all(isinstance(item, dict) for item in referents):
        raise ContractError("referents must be a list of objects")
    unique_ids(unknowns, "unknown")
    unique_ids(referents, "referent")

    for unknown in unknowns:
        nonempty_string(unknown.get("description"), f"unknown {unknown.get('id')} description")
        nonempty_string(unknown.get("evidence_needed"), f"unknown {unknown.get('id')} evidence_needed")
        if not isinstance(unknown.get("blocks_naming"), bool):
            raise ContractError(f"unknown {unknown.get('id')} blocks_naming must be boolean")

    labels: dict[str, str] = {}
    for referent in referents:
        referent_id = referent.get("id")
        for field in ("purpose", "concrete_target", "evidence"):
            nonempty_string(referent.get(field), f"referent {referent_id} {field}")
        if referent.get("referent_kind") not in REFERENT_KINDS:
            raise ContractError(f"referent {referent_id} has unsupported referent_kind")
        if referent.get("reasoning_role") not in REASONING_ROLES:
            raise ContractError(f"referent {referent_id} has unsupported reasoning_role")
        relations = referent.get("relations")
        if not isinstance(relations, list) or not relations or not all(isinstance(value, str) and value for value in relations):
            raise ContractError(f"referent {referent_id} relations must contain non-empty strings")
        certainty = referent.get("certainty")
        decision = referent.get("naming_decision")
        if certainty not in CERTAINTIES:
            raise ContractError(f"referent {referent_id} has unsupported certainty")
        if decision not in NAMING_DECISIONS:
            raise ContractError(f"referent {referent_id} has unsupported naming_decision")
        label = referent.get("label")
        definition = referent.get("definition")
        if certainty in {"unknown", "disputed"}:
            if decision != "blocked" or label is not None or definition is not None:
                raise ContractError(f"referent {referent_id} cannot be named while certainty is {certainty}")
        elif decision == "blocked":
            raise ContractError(f"referent {referent_id} is label-eligible and cannot use blocked")
        if decision == "label":
            nonempty_string(label, f"referent {referent_id} label")
            nonempty_string(definition, f"referent {referent_id} definition")
            if label in labels:
                raise ContractError(f"label {label!r} maps to both {labels[label]} and {referent_id}")
            labels[label] = referent_id
        elif decision == "concrete_text":
            nonempty_string(referent.get("naming_reason"), f"referent {referent_id} naming_reason")
            if label is not None or definition is not None:
                raise ContractError(f"referent {referent_id} concrete_text decision cannot retain a label")
        elif decision in {"pending", "blocked"} and (label is not None or definition is not None):
            raise ContractError(f"referent {referent_id} has label data without a label decision")

    sealed_states = STATES - {"source_registered", "unknowns_recorded"}
    if contract.get("state") in sealed_states:
        if not contract.get("unknowns_reviewed"):
            raise ContractError("unknowns must be reviewed before referents are sealed")
        if not referents:
            raise ContractError("at least one referent is required")
        expected = canonical_sha256(referent_projection(contract))
        if contract.get("referent_snapshot_sha256") != expected:
            raise ContractError("sealed referent projection hash does not match the current contract")

    named_states = {"labels_assigned", "draft_created", "semantic_review_passed", "closed_advisory"}
    if contract.get("state") in named_states:
        pending = [item["id"] for item in referents if item.get("naming_decision") == "pending"]
        if pending:
            raise ContractError(f"label decisions remain pending: {', '.join(pending)}")

    if contract.get("state") in {"draft_created", "semantic_review_passed", "closed_advisory"}:
        target_hash = contract.get("target_sha256")
        nonempty_string(target_hash, "target_sha256")
        if check_files:
            target = resolve_artifact(contract["target"]["path"])
            if not target.is_file():
                raise ContractError(f"missing target: {target}")
            if file_sha256(target) != target_hash:
                raise ContractError("target hash does not match the recorded draft")

    reviews = contract.get("reviews")
    if not isinstance(reviews, list) or not all(isinstance(item, dict) for item in reviews):
        raise ContractError("reviews must be a list of objects")
    if contract.get("state") == "semantic_review_passed":
        passed = [review for review in reviews if review.get("status") == "passed"]
        if not passed:
            raise ContractError("semantic_review_passed requires a passing review")
        if passed[-1].get("reviewer") not in {"independent-agent", "human"}:
            raise ContractError("passing review must be independent-agent or human")
        if check_files:
            report = resolve_artifact(passed[-1].get("report", ""))
            if not report.is_file() or file_sha256(report) != passed[-1].get("sha256"):
                raise ContractError("review report is missing or changed")
    if contract.get("state") == "closed_advisory" and contract.get("mode") != "advisory":
        raise ContractError("required contracts cannot be closed without review")


def command_init(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    if path.exists():
        raise ContractError(f"contract already exists: {path}")
    timestamp = now()
    contract = {
        "schema_version": SCHEMA_VERSION,
        "slug": args.slug,
        "task_kind": args.task_kind,
        "mode": args.mode,
        "active": True,
        "source": {"path": args.source},
        "target": {"path": args.target},
        "state": "source_registered",
        "unknowns_reviewed": False,
        "unknowns": [],
        "referents": [],
        "referent_snapshot_sha256": None,
        "target_sha256": None,
        "reviews": [],
        "transitions": [{"from": None, "to": "source_registered", "action": "init", "at": timestamp}],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    validate_contract(contract, check_files=False)
    write_contract(path, contract)
    print(path)


def command_add_unknown(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "source_registered")
    if any(item.get("id") == args.id for item in contract["unknowns"]):
        raise ContractError(f"duplicate unknown id: {args.id}")
    contract["unknowns"].append(
        {
            "id": args.id,
            "description": args.description,
            "evidence_needed": args.evidence_needed,
            "blocks_naming": not args.nonblocking,
        }
    )
    contract["updated_at"] = now()
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_review_unknowns(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "source_registered")
    if not contract["unknowns"] and not args.none:
        raise ContractError("use --none to record that no unknowns were found")
    if contract["unknowns"] and args.none:
        raise ContractError("--none conflicts with recorded unknowns")
    contract["unknowns_reviewed"] = True
    transition(contract, "unknowns_recorded", "review-unknowns")
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_add_referent(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "unknowns_recorded")
    if any(item.get("id") == args.id for item in contract["referents"]):
        raise ContractError(f"duplicate referent id: {args.id}")
    blocked = args.certainty in {"unknown", "disputed"}
    contract["referents"].append(
        {
            "id": args.id,
            "purpose": args.purpose,
            "concrete_target": args.concrete_target,
            "referent_kind": args.kind,
            "reasoning_role": args.reasoning_role,
            "relations": args.relation,
            "evidence": args.evidence,
            "certainty": args.certainty,
            "naming_decision": "blocked" if blocked else "pending",
            "label": None,
            "definition": None,
            "naming_reason": "certainty does not permit naming" if blocked else None,
        }
    )
    contract["updated_at"] = now()
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_seal(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "unknowns_recorded")
    validate_contract(contract, check_files=False)
    if not contract["referents"]:
        raise ContractError("at least one referent is required before sealing")
    contract["referent_snapshot_sha256"] = canonical_sha256(referent_projection(contract))
    transition(contract, "referents_sealed", "seal-referents")
    validate_contract(contract, check_files=False)
    write_contract(path, contract)
    print(contract["referent_snapshot_sha256"])


def command_assign_label(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "referents_sealed")
    referent = find_referent(contract, args.id)
    if referent["certainty"] in {"unknown", "disputed"}:
        raise ContractError(f"referent {args.id} cannot be named while certainty is {referent['certainty']}")
    referent.update(
        {"naming_decision": "label", "label": args.label, "definition": args.definition, "naming_reason": None}
    )
    contract["updated_at"] = now()
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_use_concrete_text(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "referents_sealed")
    referent = find_referent(contract, args.id)
    if referent["certainty"] in {"unknown", "disputed"}:
        raise ContractError(f"referent {args.id} is already blocked from naming")
    referent.update(
        {"naming_decision": "concrete_text", "label": None, "definition": None, "naming_reason": args.reason}
    )
    contract["updated_at"] = now()
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_finalize_labels(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "referents_sealed")
    pending = [item["id"] for item in contract["referents"] if item["naming_decision"] == "pending"]
    if pending:
        raise ContractError(f"label decisions remain pending: {', '.join(pending)}")
    transition(contract, "labels_assigned", "finalize-labels")
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_record_draft(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "labels_assigned")
    validate_contract(contract, check_files=False)
    target = resolve_artifact(contract["target"]["path"])
    if not target.is_file():
        raise ContractError(f"missing target: {target}")
    text = target.read_text(encoding="utf-8")
    for referent in contract["referents"]:
        if referent["naming_decision"] == "label":
            if referent["label"] not in text:
                raise ContractError(f"target does not use controlled term: {referent['label']}")
            if referent["definition"] not in text:
                raise ContractError(f"target does not contain first-use definition for: {referent['label']}")
        elif referent["naming_decision"] == "concrete_text" and referent["concrete_target"] not in text:
            raise ContractError(f"target does not contain concrete referent text for: {referent['id']}")
    contract["target_sha256"] = file_sha256(target)
    transition(contract, "draft_created", "record-draft")
    validate_contract(contract)
    write_contract(path, contract)
    print(contract["target_sha256"])


def command_record_review(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "draft_created")
    report = resolve_artifact(args.report)
    if not report.is_file():
        raise ContractError(f"missing review report: {report}")
    review = {
        "status": args.status,
        "reviewer": args.reviewer,
        "report": args.report,
        "sha256": file_sha256(report),
        "at": now(),
    }
    contract["reviews"].append(review)
    if args.status == "passed":
        if args.reviewer not in {"independent-agent", "human"}:
            raise ContractError("a passing review must be independent-agent or human")
        contract["active"] = False
        transition(contract, "semantic_review_passed", "record-review")
    else:
        contract["updated_at"] = now()
    validate_contract(contract)
    write_contract(path, contract)


def command_close_advisory(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(contract, "draft_created")
    if contract["mode"] != "advisory":
        raise ContractError("required contracts cannot close without a passing review")
    contract["active"] = False
    contract["close_reason"] = args.reason
    transition(contract, "closed_advisory", "close-advisory")
    validate_contract(contract)
    write_contract(path, contract)


def command_reopen(args: argparse.Namespace) -> None:
    path = Path(args.contract)
    contract = load_contract(path)
    require_state(
        contract,
        "referents_sealed",
        "labels_assigned",
        "draft_created",
        "semantic_review_passed",
        "closed_advisory",
    )
    for referent in contract["referents"]:
        blocked = referent["certainty"] in {"unknown", "disputed"}
        referent.update(
            {
                "naming_decision": "blocked" if blocked else "pending",
                "label": None,
                "definition": None,
                "naming_reason": "certainty does not permit naming" if blocked else None,
            }
        )
    contract["referent_snapshot_sha256"] = None
    contract["target_sha256"] = None
    contract["reviews"] = []
    contract["active"] = True
    contract["reopen_reason"] = args.reason
    contract.pop("close_reason", None)
    transition(contract, "unknowns_recorded", "reopen")
    validate_contract(contract, check_files=False)
    write_contract(path, contract)


def command_check(args: argparse.Namespace) -> None:
    contract = load_contract(Path(args.contract))
    validate_contract(contract)
    if args.require_review and contract["state"] != "semantic_review_passed":
        raise ContractError("a passing semantic review is required")
    if contract["mode"] == "required" and contract["state"] != "semantic_review_passed":
        raise ContractError("required contract has not passed semantic review")
    print(f"referent contract passed: {args.contract} ({contract['state']})")


def md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def command_semantic_diff(args: argparse.Namespace) -> None:
    contract = load_contract(Path(args.contract))
    validate_contract(contract, check_files=False)
    previous_by_id: dict[str, dict[str, Any]] = {}
    if args.against:
        previous = load_contract(Path(args.against))
        validate_contract(previous, check_files=False)
        previous_by_id = {item["id"]: item for item in previous["referents"]}
    current_by_id = {item["id"]: item for item in contract["referents"]}
    print(f"# Semantic Diff: {contract['slug']}")
    print()
    print(f"- State: `{contract['state']}`")
    print(f"- Mode: `{contract['mode']}`")
    print(f"- Source: `{contract['source']['path']}`")
    print(f"- Target: `{contract['target']['path']}`")
    print()
    print("## Referents")
    print()
    print("| Change | ID | Concrete referent | Kind | Certainty | Naming decision | Label |")
    print("|---|---|---|---|---|---|---|")
    for referent in contract["referents"]:
        previous_referent = previous_by_id.get(referent["id"])
        change = "current" if not args.against else "added" if previous_referent is None else "unchanged" if previous_referent == referent else "changed"
        print(
            f"| {change} | {md(referent['id'])} | {md(referent['concrete_target'])} | "
            f"{md(referent['referent_kind'])} | {md(referent['certainty'])} | "
            f"{md(referent['naming_decision'])} | {md(referent['label'])} |"
        )
    for referent_id in sorted(previous_by_id.keys() - current_by_id.keys()):
        referent = previous_by_id[referent_id]
        print(
            f"| removed | {md(referent['id'])} | {md(referent['concrete_target'])} | "
            f"{md(referent['referent_kind'])} | {md(referent['certainty'])} | "
            f"{md(referent['naming_decision'])} | {md(referent['label'])} |"
        )
    print()
    print("## Unresolved facts")
    print()
    if not contract["unknowns"]:
        print("None recorded.")
    else:
        for unknown in contract["unknowns"]:
            print(f"- `{md(unknown['id'])}`: {md(unknown['description'])}; evidence needed: {md(unknown['evidence_needed'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("contract")
    init.add_argument("--slug", required=True)
    init.add_argument("--task-kind", choices=sorted(TASK_KINDS), required=True)
    init.add_argument("--source", required=True)
    init.add_argument("--target", required=True)
    init.add_argument("--mode", choices=("advisory", "required"), default="advisory")
    init.set_defaults(func=command_init)

    add_unknown = subparsers.add_parser("add-unknown")
    add_unknown.add_argument("contract")
    add_unknown.add_argument("--id", required=True)
    add_unknown.add_argument("--description", required=True)
    add_unknown.add_argument("--evidence-needed", required=True)
    add_unknown.add_argument("--nonblocking", action="store_true")
    add_unknown.set_defaults(func=command_add_unknown)

    review_unknowns = subparsers.add_parser("review-unknowns")
    review_unknowns.add_argument("contract")
    review_unknowns.add_argument("--none", action="store_true")
    review_unknowns.set_defaults(func=command_review_unknowns)

    add_referent = subparsers.add_parser("add-referent")
    add_referent.add_argument("contract")
    add_referent.add_argument("--id", required=True)
    add_referent.add_argument("--purpose", required=True)
    add_referent.add_argument("--concrete-target", required=True)
    add_referent.add_argument("--kind", choices=sorted(REFERENT_KINDS), required=True)
    add_referent.add_argument("--reasoning-role", choices=sorted(REASONING_ROLES), required=True)
    add_referent.add_argument("--relation", action="append", required=True)
    add_referent.add_argument("--evidence", required=True)
    add_referent.add_argument("--certainty", choices=sorted(CERTAINTIES), required=True)
    add_referent.set_defaults(func=command_add_referent)

    seal = subparsers.add_parser("seal-referents")
    seal.add_argument("contract")
    seal.set_defaults(func=command_seal)

    assign_label = subparsers.add_parser("assign-label")
    assign_label.add_argument("contract")
    assign_label.add_argument("--id", required=True)
    assign_label.add_argument("--label", required=True)
    assign_label.add_argument("--definition", required=True)
    assign_label.set_defaults(func=command_assign_label)

    concrete = subparsers.add_parser("use-concrete-text")
    concrete.add_argument("contract")
    concrete.add_argument("--id", required=True)
    concrete.add_argument("--reason", required=True)
    concrete.set_defaults(func=command_use_concrete_text)

    finalize = subparsers.add_parser("finalize-labels")
    finalize.add_argument("contract")
    finalize.set_defaults(func=command_finalize_labels)

    draft = subparsers.add_parser("record-draft")
    draft.add_argument("contract")
    draft.set_defaults(func=command_record_draft)

    review = subparsers.add_parser("record-review")
    review.add_argument("contract")
    review.add_argument("--report", required=True)
    review.add_argument("--status", choices=("passed", "failed"), required=True)
    review.add_argument("--reviewer", choices=("independent-agent", "human", "self"), required=True)
    review.set_defaults(func=command_record_review)

    close = subparsers.add_parser("close-advisory")
    close.add_argument("contract")
    close.add_argument("--reason", required=True)
    close.set_defaults(func=command_close_advisory)

    reopen = subparsers.add_parser("reopen")
    reopen.add_argument("contract")
    reopen.add_argument("--reason", required=True)
    reopen.set_defaults(func=command_reopen)

    check = subparsers.add_parser("check")
    check.add_argument("contract")
    check.add_argument("--require-review", action="store_true")
    check.set_defaults(func=command_check)

    semantic_diff = subparsers.add_parser("semantic-diff")
    semantic_diff.add_argument("contract")
    semantic_diff.add_argument("--against")
    semantic_diff.set_defaults(func=command_semantic_diff)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ContractError as exc:
        print(f"referent contract error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
