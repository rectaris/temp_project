#!/usr/bin/env python3
"""Validate and render explicitly pinned supplemental harness instructions."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

MAX_BYTES = 1024 * 1024
MAX_SELECTIONS = 32
MAX_RENDER_BYTES = 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")
REVISION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class ProfileError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProfileError(f"{label} has an invalid exact field shape")
    return value


def read_regular(path: Path, label: str) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        raise ProfileError(f"{label} is not a readable regular file: {path}") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
            raise ProfileError(f"{label} must be a bounded regular file: {path}")
        os.set_blocking(fd, True)
        data = b""
        while len(data) <= MAX_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
        if len(data) > MAX_BYTES:
            raise ProfileError(f"{label} exceeds its byte bound: {path}")
        return data
    finally:
        os.close(fd)


def load_json(path: Path, label: str) -> tuple[dict[str, Any], str]:
    raw = read_regular(path, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"{label} must contain an object")
    return value, digest(raw)


def safe_repository_file(root: Path, value: str, label: str) -> Path:
    if not isinstance(value, str) or "\\" in value:
        raise ProfileError(f"{label} must be a repository-relative path")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or str(relative) != value
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ProfileError(f"{label} must be a normalized repository-relative path")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ProfileError(f"{label} must not contain a symlink")
    resolved = current.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ProfileError(f"{label} escapes the repository") from exc
    return resolved


def parse_catalog(path: Path, root: Path) -> tuple[dict[str, Any], str]:
    value, source_digest = load_json(path, "catalog")
    exact(value, {"schema_version", "governing_sources", "supplemental_revisions"}, "catalog")
    if value["schema_version"] != 1:
        raise ProfileError("unsupported catalog schema")
    governing_ids: set[str] = set()
    for index, raw in enumerate(value["governing_sources"]):
        item = exact(raw, {"id", "revision", "path", "content_digest", "rationale"}, f"governing_sources[{index}]")
        if (
            not isinstance(item["id"], str)
            or not isinstance(item["revision"], str)
            or not isinstance(item["path"], str)
            or not isinstance(item["content_digest"], str)
            or not ID_RE.fullmatch(item["id"])
            or not REVISION_RE.fullmatch(item["revision"])
        ):
            raise ProfileError("invalid governing source identity")
        if item["id"] in governing_ids:
            raise ProfileError("duplicate governing source id")
        governing_ids.add(item["id"])
        data = read_regular(safe_repository_file(root, item["path"], "governing source"), "governing source")
        if not DIGEST_RE.fullmatch(item["content_digest"]) or digest(data) != item["content_digest"]:
            raise ProfileError(f"governing source digest mismatch: {item['id']}")
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise ProfileError("governing source rationale is required")
    revisions: set[tuple[str, str]] = set()
    for index, raw in enumerate(value["supplemental_revisions"]):
        item = exact(
            raw,
            {"id", "revision", "content_digest", "applicability", "introduction_reason", "failure_case_references", "review_evidence", "status"},
            f"supplemental_revisions[{index}]",
        )
        identity = (item["id"], item["revision"])
        if (
            not isinstance(item["id"], str)
            or not isinstance(item["revision"], str)
            or not isinstance(item["content_digest"], str)
            or not ID_RE.fullmatch(item["id"])
            or not REVISION_RE.fullmatch(item["revision"])
            or identity in revisions
        ):
            raise ProfileError("invalid or duplicate supplemental revision")
        revisions.add(identity)
        if item["id"] in governing_ids or item["status"] not in {"active", "retired"}:
            raise ProfileError("supplemental revision conflicts with governing policy or status")
        if not DIGEST_RE.fullmatch(item["content_digest"]):
            raise ProfileError("invalid supplemental digest")
        applicability = exact(item["applicability"], {"task_types", "model_selector"}, "applicability")
        if (
            not isinstance(applicability["task_types"], list)
            or not applicability["task_types"]
            or any(
                not isinstance(task_type, str) or not ID_RE.fullmatch(task_type)
                for task_type in applicability["task_types"]
            )
            or (
                applicability["model_selector"] is not None
                and (
                    not isinstance(applicability["model_selector"], str)
                    or not applicability["model_selector"].strip()
                )
            )
        ):
            raise ProfileError("supplemental task_types must be non-empty")
        review = exact(item["review_evidence"], {"comparison_protocol_digest", "comparison_report_digest", "evidence_digests"}, "review_evidence")
        if (
            not isinstance(review["evidence_digests"], list)
            or not review["evidence_digests"]
            or any(
                not isinstance(entry, str) or not DIGEST_RE.fullmatch(entry)
                for entry in [
                    review["comparison_protocol_digest"],
                    review["comparison_report_digest"],
                    *review["evidence_digests"],
                ]
            )
        ):
            raise ProfileError("invalid review evidence digest")
        if (
            not isinstance(item["introduction_reason"], str)
            or not item["introduction_reason"].strip()
            or not isinstance(item["failure_case_references"], list)
            or not item["failure_case_references"]
            or any(
                not isinstance(reference, str) or not reference.strip()
                for reference in item["failure_case_references"]
            )
        ):
            raise ProfileError("supplemental rationale and failure references are required")
    return value, source_digest


def parse_profile(path: Path) -> tuple[dict[str, Any], str]:
    value, source_digest = load_json(path, "profile")
    exact(value, {"schema_version", "selections"}, "profile")
    if (
        value["schema_version"] != 1
        or not isinstance(value["selections"], list)
        or len(value["selections"]) > MAX_SELECTIONS
    ):
        raise ProfileError("unsupported profile schema")
    seen: set[str] = set()
    order: list[tuple[str, str, str]] = []
    for index, raw in enumerate(value["selections"]):
        item = exact(raw, {"id", "revision", "content_digest", "asset_path"}, f"selections[{index}]")
        if (
            not isinstance(item["id"], str)
            or not isinstance(item["revision"], str)
            or not isinstance(item["content_digest"], str)
            or not isinstance(item["asset_path"], str)
            or not ID_RE.fullmatch(item["id"])
            or not REVISION_RE.fullmatch(item["revision"])
            or item["id"] in seen
        ):
            raise ProfileError("invalid or duplicate profile selection")
        seen.add(item["id"])
        order.append((item["id"], item["revision"], item["asset_path"]))
        if not DIGEST_RE.fullmatch(item["content_digest"]):
            raise ProfileError("invalid selection digest")
    if order != sorted(order):
        raise ProfileError("profile selections must use canonical id/revision/path order")
    return value, source_digest


def resolve(catalog: dict[str, Any], profile: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    governing = {entry["id"] for entry in catalog["governing_sources"]}
    governing_paths = {entry["path"] for entry in catalog["governing_sources"]}
    revisions = {(entry["id"], entry["revision"]): entry for entry in catalog["supplemental_revisions"]}
    selected = []
    total_bytes = 0
    for item in profile["selections"]:
        if item["id"] in governing:
            raise ProfileError("governing sources cannot be selected as supplemental advice")
        if item["asset_path"] in governing_paths:
            raise ProfileError("governing source paths cannot be selected as supplemental advice")
        revision = revisions.get((item["id"], item["revision"]))
        if revision is None:
            raise ProfileError(f"unknown supplemental revision: {item['id']}@{item['revision']}")
        if item["content_digest"] != revision["content_digest"]:
            raise ProfileError("selection digest does not match catalog")
        data = read_regular(safe_repository_file(root, item["asset_path"], "supplemental asset"), "supplemental asset")
        total_bytes += len(data)
        if total_bytes > MAX_RENDER_BYTES:
            raise ProfileError("selected supplemental assets exceed the cumulative byte bound")
        if digest(data) != item["content_digest"]:
            raise ProfileError("supplemental asset digest mismatch")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProfileError("supplemental asset must be UTF-8") from exc
        selected.append({
            "id": item["id"],
            "revision": item["revision"],
            "content_digest": item["content_digest"],
            "asset_path": item["asset_path"],
            "availability": revision["status"],
            "text": text,
        })
    return selected


def governing_digest(catalog: dict[str, Any]) -> str:
    return digest(canonical_bytes(catalog["governing_sources"]))


def report(kind: str, catalog_digest: str, profile_digest: str, selected: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "report_kind": kind,
        "catalog_digest": catalog_digest,
        "profile_digest": profile_digest,
        "runtime_activation": "not_observed",
        "runtime_activation_note": "Rendering supplemental advice does not replace AGENTS.md, skills, or system/developer instructions, and does not prove that a host loaded this output.",
        "selected_revisions": [{key: item[key] for key in ("id", "revision", "content_digest", "availability")} for item in selected],
    }
    if kind == "harness_profile_render":
        result["governing_sources_included"] = False
        result["supplemental_instructions"] = "\n".join(item["text"].rstrip("\n") for item in selected)
    return result


def load_comparison() -> ModuleType:
    path = Path(__file__).with_name("compare-harness-runs.py")
    spec = importlib.util.spec_from_file_location("harness_comparison", path)
    if spec is None or spec.loader is None:
        raise ProfileError("harness comparison implementation is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def comparison_recommendation(comparison_report: dict[str, Any], name: str) -> str:
    comparisons = comparison_report.get("comparisons")
    if not isinstance(comparisons, list):
        raise ProfileError("comparison report has an invalid comparisons field")
    matches = [
        item
        for item in comparisons
        if isinstance(item, dict) and item.get("comparison") == name
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("recommendation"), str):
        raise ProfileError(f"comparison report does not contain exactly one {name} result")
    return matches[0]["recommendation"]


def selected_asset_digests(selected: list[dict[str, Any]]) -> dict[str, str]:
    return {item["asset_path"]: item["content_digest"] for item in selected}


def require_profile_comparison_binding(
    protocol: dict[str, Any],
    prior_selected: list[dict[str, Any]],
    proposed_selected: list[dict[str, Any]],
) -> None:
    configurations = protocol.get("configurations")
    if not isinstance(configurations, dict):
        raise ProfileError("comparison protocol has an invalid configurations field")
    slots = {
        "new_model_current_instructions": selected_asset_digests(prior_selected),
        "new_model_candidate_instructions": selected_asset_digests(proposed_selected),
    }
    known_paths = set(slots["new_model_current_instructions"]) | set(
        slots["new_model_candidate_instructions"]
    )
    configured_assets: dict[str, dict[str, str]] = {}
    for slot, expected in slots.items():
        configuration = configurations.get(slot)
        if not isinstance(configuration, dict):
            raise ProfileError(f"comparison protocol is missing {slot}")
        assets = configuration.get("instruction_asset_digests")
        if not isinstance(assets, dict):
            raise ProfileError(f"comparison protocol has invalid assets for {slot}")
        configured_assets[slot] = assets
        observed = {path: assets[path] for path in known_paths if path in assets}
        if observed != expected:
            raise ProfileError(f"comparison protocol does not match the {slot} profile")
    current_other = {
        path: value
        for path, value in configured_assets["new_model_current_instructions"].items()
        if path not in known_paths
    }
    candidate_other = {
        path: value
        for path, value in configured_assets["new_model_candidate_instructions"].items()
        if path not in known_paths
    }
    if current_other != candidate_other:
        raise ProfileError("comparison protocol changes instructions outside the profiles")


def check_adoption(args: argparse.Namespace, catalog: dict[str, Any]) -> dict[str, Any]:
    prior, prior_digest = parse_profile(args.prior_profile)
    proposed, proposed_digest = parse_profile(args.proposed_profile)
    prior_selected = resolve(catalog, prior, args.repository_root)
    proposed_selected = resolve(catalog, proposed, args.repository_root)
    prior_by_identity = {
        (item["id"], item["revision"]): item for item in prior_selected
    }
    newly_selected = [
        item
        for item in proposed_selected
        if prior_by_identity.get((item["id"], item["revision"])) != item
    ]
    if any(item["availability"] == "retired" for item in newly_selected):
        raise ProfileError("retired revisions cannot be newly adopted")
    record, _ = load_json(args.record, "adoption record")
    exact(record, {"schema_version", "decision", "prior_profile_digest", "proposed_profile_digest", "comparison_protocol_digest", "comparison_report_digest", "comparison_evidence_digests", "comparison_ordering_evidence_digests"}, "adoption record")
    if record["schema_version"] != 1 or record["decision"] not in {"adopt", "keep_current"}:
        raise ProfileError("invalid adoption decision")
    comparison = load_comparison()
    try:
        _, protocol_digest = comparison.load_json_object(str(args.protocol), "comparison protocol")
        protocol = comparison.parse_protocol(str(args.protocol))
        require_profile_comparison_binding(protocol, prior_selected, proposed_selected)
    except comparison.ComparisonError as exc:
        raise ProfileError(str(exc)) from exc
    command = [
        sys.executable,
        str(Path(comparison.__file__).resolve()),
        "--protocol",
        str(args.protocol),
    ]
    for option, paths in (
        ("--observation", args.observation),
        ("--evidence", args.evidence),
        ("--ordering-evidence", args.ordering_evidence),
    ):
        for path in paths:
            command.extend((option, str(path)))
    command.extend(("--format", "json"))
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ProfileError(detail or "comparison command failed")
    try:
        comparison_report = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError("comparison command returned invalid JSON") from exc
    report_digest = digest(completed.stdout)
    evidence_digests = [digest(read_regular(path, "comparison evidence")) for path in args.evidence]
    ordering_digests = [digest(read_regular(path, "ordering evidence")) for path in args.ordering_evidence]
    expected = (prior_digest, proposed_digest, protocol_digest, report_digest, evidence_digests, ordering_digests)
    actual = (record["prior_profile_digest"], record["proposed_profile_digest"], record["comparison_protocol_digest"], record["comparison_report_digest"], record["comparison_evidence_digests"], record["comparison_ordering_evidence_digests"])
    if actual != expected:
        raise ProfileError("adoption record does not match recomputed comparison evidence")
    revisions = {
        (entry["id"], entry["revision"]): entry
        for entry in catalog["supplemental_revisions"]
    }
    for item in newly_selected:
        review = revisions[(item["id"], item["revision"])]["review_evidence"]
        if (
            review["comparison_protocol_digest"] != protocol_digest
            or review["comparison_report_digest"] != report_digest
            or review["evidence_digests"] != evidence_digests
        ):
            raise ProfileError(
                f"catalog review evidence does not match adoption inputs: "
                f"{item['id']}@{item['revision']}"
            )
    recommendation = comparison_recommendation(comparison_report, "instruction_effect")
    if record["decision"] == "adopt" and recommendation != "adopt_candidate":
        raise ProfileError("comparison does not recommend adopting the candidate")
    return {"schema_version": 1, "report_kind": "harness_profile_adoption_check", "decision": record["decision"], "comparison_report_digest": report_digest, "repository_changed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "render"):
        command = sub.add_parser(name)
        command.add_argument("--catalog", type=Path, required=True)
        command.add_argument("--profile", type=Path, required=True)
    adoption = sub.add_parser("check-adoption")
    adoption.add_argument("--catalog", type=Path, required=True)
    adoption.add_argument("--prior-profile", type=Path, required=True)
    adoption.add_argument("--proposed-profile", type=Path, required=True)
    adoption.add_argument("--record", type=Path, required=True)
    adoption.add_argument("--protocol", type=Path, required=True)
    adoption.add_argument("--observation", type=Path, action="append", default=[])
    adoption.add_argument("--evidence", type=Path, action="append", default=[])
    adoption.add_argument("--ordering-evidence", type=Path, action="append", default=[])
    rollback = sub.add_parser("check-rollback")
    rollback.add_argument("--catalog", type=Path, required=True)
    rollback.add_argument("--current-profile", type=Path, required=True)
    rollback.add_argument("--prior-profile", type=Path, required=True)
    rollback.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    args.repository_root = args.repository_root.resolve()
    try:
        catalog, catalog_digest = parse_catalog(args.catalog, args.repository_root)
        if args.command in {"check", "render"}:
            profile, profile_digest = parse_profile(args.profile)
            selected = resolve(catalog, profile, args.repository_root)
            output = report(f"harness_profile_{args.command}", catalog_digest, profile_digest, selected)
        elif args.command == "check-adoption":
            output = check_adoption(args, catalog)
        else:
            current, current_digest = parse_profile(args.current_profile)
            prior, prior_digest = parse_profile(args.prior_profile)
            resolve(catalog, current, args.repository_root)
            resolve(catalog, prior, args.repository_root)
            record, _ = load_json(args.record, "rollback record")
            exact(record, {"schema_version", "decision", "current_profile_digest", "prior_profile_digest", "governing_sources_digest"}, "rollback record")
            if record["schema_version"] != 1 or record["decision"] != "rollback" or record["current_profile_digest"] != current_digest or record["prior_profile_digest"] != prior_digest:
                raise ProfileError("rollback record does not match the supplied profiles")
            status_value = "rollback_ready" if record["governing_sources_digest"] == governing_digest(catalog) else "reassessment_required"
            output = {"schema_version": 1, "report_kind": "harness_profile_rollback_check", "status": status_value, "repository_changed": False}
    except (OSError, ProfileError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    serialized = json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    if len(serialized) > MAX_REPORT_BYTES:
        print("report exceeds its byte bound", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
