#!/usr/bin/env python3
"""Verify a private live parallel-session report against a plan's required evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_ENV = "PROJECT_AGENT_WORKFLOW_PARALLEL_LIVE_REPORT"
REQUIRED_EVIDENCE_ENV = "PROJECT_AGENT_WORKFLOW_REQUIRED_EVIDENCE"
DEFAULT_REQUIRED_EVIDENCE = ".agent-artifacts/parallel-plan-required-evidence.json"
REQUIREMENT_SCHEMA_VERSION = 1
REQUIREMENT_RECORD_TYPE = "parallel-live-session"


class EvidenceError(ValueError):
    """Raised when report evidence is missing, stale, or mismatched."""


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def git_bytes(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return proc.stdout


def self_digest(value: Any) -> str:
    return canonical_digest(value)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def repository_identity(repo: Path) -> str:
    proc = subprocess.run([
        "git", "-C", str(repo), "config", "--get", "remote.origin.url"
    ], capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ValueError(
            "repository has no canonical remote.origin.url; a live-evidence record cannot be keyed here"
        )
    return proc.stdout.strip()


def requirement_path(repo: Path, plan: str | Path) -> Path:
    if isinstance(plan, Path):
        plan_name = str(plan)
    else:
        plan_name = plan
    identity = repository_identity(repo)
    suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return repo / ".agent-artifacts" / "parallel-live-evidence" / suffix / f"{plan_name.replace('/', '__')}.json"


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def plan_contract(repo: Path, plan: str | Path) -> dict[str, Any]:
    path = Path(plan)
    if not path.is_absolute():
        path = repo / path
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    contract = re.search(r"^live_evidence_contract:\s*(\S+)", text, flags=re.MULTILINE)
    live_digest = re.search(r"^live_evidence_acceptance_sha256:\s*(sha256:[0-9a-fA-F]{64})", text, flags=re.MULTILINE)
    if live_digest is None:
        live_digest = re.search(r"^live_acceptance_digest:\s*(sha256:[0-9a-fA-F]{64})", text, flags=re.MULTILINE)
    if contract is None and live_digest is None:
        return {}
    if contract is None:
        raise ValueError(f"plan declares a live-evidence acceptance digest but no live_evidence_contract: {path}")
    return {
        "plan_path": str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path),
        "plan_digest": digest_bytes(path.read_bytes()),
        "contract": contract.group(1),
        "live_acceptance_digest": (live_digest.group(1) if live_digest else ""),
    }


def coerce_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def resolve_required_evidence(path: str | None) -> Path:
    if path is not None:
        return Path(path)
    if REQUIRED_EVIDENCE_ENV in os.environ:
        return Path(os.environ[REQUIRED_EVIDENCE_ENV])
    return Path(DEFAULT_REQUIRED_EVIDENCE)


def resolve_report(path: str | None) -> Path:
    if path is not None:
        return Path(path)
    if REPORT_ENV in os.environ:
        return Path(os.environ[REPORT_ENV])
    raise ValueError(
        f"missing live report path: set {REPORT_ENV} to the report JSON file or pass --report"
    )


def require_record(required_record: dict[str, Any], plan_path: Path, report_path: Path) -> None:
    plan_digest = digest_bytes(plan_path.read_bytes())
    contract = plan_contract(plan_path.parent if plan_path.parent.name == "active" else plan_path.parent.parent, plan_path.name)
    live_acceptance_digest = contract.get("live_acceptance_digest")
    if required_record.get("plan_digest") not in (None, plan_digest):
        raise ValueError(
            f"required-evidence plan digest mismatch: expected {required_record.get('plan_digest')}, found {plan_digest}"
        )
    if required_record.get("live_acceptance_digest") not in (None, live_acceptance_digest):
        raise ValueError(
            "required-evidence live acceptance digest mismatch: "
            f"expected {required_record.get('live_acceptance_digest')}, found {live_acceptance_digest}"
        )
    if required_record.get("report_digest"):
        report_digest = file_digest(report_path)
        if required_record["report_digest"] != report_digest:
            raise ValueError(
                f"required-evidence report digest mismatch: expected {required_record['report_digest']}, found {report_digest}"
            )
    if "execution_genesis_digest" not in required_record and "execution_genesis" not in required_record:
        raise ValueError("required-evidence record must declare execution_genesis")


def validate_report(report: dict[str, Any], plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    live_acceptance = re.search(r"^live_evidence_acceptance_sha256:\s*(sha256:[0-9a-fA-F]{64})", text, flags=re.MULTILINE)
    if live_acceptance is None:
        live_acceptance = re.search(r"^live_acceptance_digest:\s*(sha256:[0-9a-fA-F]{64})", text, flags=re.MULTILINE)
    if live_acceptance is None:
        raise ValueError(f"plan does not declare a live acceptance digest: {plan_path}")
    expected = live_acceptance.group(1)
    if report.get("live_acceptance_digest") not in (None, expected):
        raise ValueError(f"report live acceptance digest mismatch: expected {expected}, found {report.get('live_acceptance_digest')}")
    if report.get("acceptance_digest") not in (None, expected):
        raise ValueError(f"report acceptance digest mismatch: expected {expected}, found {report.get('acceptance_digest')}")
    if report.get("acceptance_sha256") not in (None, expected):
        raise ValueError(f"report acceptance_sha256 mismatch: expected {expected}, found {report.get('acceptance_sha256')}")
    session_ids = coerce_strings(report.get("distinct_session_ids") or report.get("session_ids"))
    if len(set(session_ids)) < 2:
        session_count = report.get("session_count")
        if session_count is None or int(session_count) < 2:
            raise ValueError("report must contain evidence for at least two distinct sessions")
    if not report.get("distinct_session_ids") and not report.get("session_ids"):
        raise ValueError("report must identify at least two member sessions")
    intervals = report.get("implementation_intervals") or []
    if isinstance(intervals, list) and intervals:
        parsed: list[tuple[str, str]] = []
        for interval in intervals:
            if isinstance(interval, dict):
                start = interval.get("start")
                end = interval.get("end")
                if isinstance(start, str) and isinstance(end, str):
                    parsed.append((start, end))
        overlaps = False
        for i, (start_a, end_a) in enumerate(parsed):
            for start_b, end_b in parsed[i + 1 :]:
                if start_a < end_b and start_b < end_a:
                    overlaps = True
                    break
            if overlaps:
                break
        if len(parsed) >= 2 and not overlaps:
            raise ValueError("report implementation intervals do not overlap")


def verify_changes_retained(repo: Path, member: dict[str, Any], final_tip: str) -> None:
    base_commit = member.get("base_commit")
    result_tree = member.get("result_tree")
    patch_digest = member.get("patch_digest")
    reported_paths = [str(item) for item in coerce_strings(member.get("changed_paths"))]
    if not isinstance(base_commit, str) or not base_commit:
        raise EvidenceError("member record is missing base_commit")
    if not isinstance(result_tree, str) or not result_tree:
        raise EvidenceError("member result_tree must name one Git tree")
    if not isinstance(patch_digest, str) or not patch_digest:
        raise EvidenceError("member record is missing patch_digest")
    try:
        object_type = git_bytes(repo, "cat-file", "-t", result_tree).strip()
    except subprocess.CalledProcessError as exc:
        raise EvidenceError("member result_tree must name one Git tree") from exc
    if object_type != b"tree":
        raise EvidenceError("member result_tree must name one Git tree")
    patch = git_bytes(
        repo,
        "-c",
        "core.abbrev=40",
        "diff",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-ext-diff",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base_commit,
        result_tree,
    )
    if digest_bytes(patch) != patch_digest:
        raise EvidenceError("member patch digest does not reproduce the reported patch digest")
    actual_paths = git_bytes(repo, "diff", "--name-only", f"{base_commit}..{result_tree}").decode("utf-8", errors="replace").split()
    if reported_paths != actual_paths:
        raise EvidenceError("member changed_paths are not exactly the paths produced by the result tree")
    if len(reported_paths) != len(set(reported_paths)):
        raise EvidenceError("member changed_paths must not contain duplicates")
    result_identity: dict[str, str] = {}
    for path in reported_paths:
        entry = git_bytes(repo, "ls-tree", "-r", "--full-tree", result_tree, "--", path)
        if not entry:
            raise EvidenceError(f"member result tree is missing a reported path: {path}")
        parts = entry.decode("utf-8", errors="replace").strip().split()
        if len(parts) < 3:
            raise EvidenceError(f"member result tree is missing a reported path: {path}")
        result_identity[path] = f"{parts[0]}:{parts[2]}"
    for path in reported_paths:
        for rev in (member.get("published_commit", final_tip), final_tip):
            entry = b""
            try:
                entry = git_bytes(repo, "ls-tree", "-r", "--full-tree", rev, "--", path)
            except subprocess.CalledProcessError:
                entry = b""
            if not entry:
                raise EvidenceError("accepted member work was overwritten")
            parts = entry.decode("utf-8", errors="replace").strip().split()
            if len(parts) < 3:
                raise EvidenceError("accepted member work was overwritten")
            current = f"{parts[0]}:{parts[2]}"
            if current != result_identity[path]:
                raise EvidenceError("accepted member work was overwritten")


def command_require(repo: Path, plan_arg: str | Path) -> dict[str, Any]:
    plan = Path(plan_arg)
    if not plan.is_absolute():
        plan = repo / plan
    if not plan.exists():
        raise ValueError(f"plan file not found: {plan}")
    contract = plan_contract(repo, plan)
    if not contract:
        try:
            relative = plan.relative_to(repo) if plan.is_relative_to(repo) else plan.name
            record_path = requirement_path(repo, relative)
        except ValueError:
            return {"obligation": "none"}
        if record_path.exists():
            raise ValueError(f"plan no longer declares the live-evidence contract, but still reserves {record_path}")
        return {"obligation": "none"}
    try:
        repository_identity(repo)
    except ValueError as exc:
        if "remote.origin.url" in str(exc):
            raise ValueError(f"live-evidence rule cannot be keyed in this repository: {exc}") from exc
        raise
    relative = plan.relative_to(repo) if plan.is_relative_to(repo) else plan.name
    record_path = requirement_path(repo, relative)
    if not record_path.exists():
        raise ValueError(
            f"required-evidence record does not exist: {record_path}. "
            "Create it before implementation and keep it unchanged until completion."
        )
    record = load_json(record_path)
    if not isinstance(record, dict):
        raise ValueError(f"required-evidence record must contain a JSON object: {record_path}")
    if record.get("plan_path") not in (None, relative.as_posix() if hasattr(relative, "as_posix") else str(relative)):
        raise ValueError(f"required-evidence record is bound to a different plan: {record.get('plan_path')}")
    execution_plan_digest = record.get("execution_plan_digest")
    if execution_plan_digest is not None and record.get("plan_digest") not in (
        None,
        execution_plan_digest,
    ):
        raise ValueError(
            "required-evidence record plan_digest does not match execution_plan_digest: "
            f"{record.get('plan_digest')} != {execution_plan_digest}"
        )
    if execution_plan_digest is None and record.get("plan_digest") not in (
        None,
        contract.get("plan_digest"),
    ):
        raise ValueError(
            f"required-evidence record plan digest does not match the plan: {record.get('plan_digest')} != {contract.get('plan_digest')}"
        )
    if record.get("live_acceptance_digest") not in (None, contract.get("live_acceptance_digest")):
        raise ValueError(
            "required-evidence record live acceptance digest does not match the plan: "
            f"{record.get('live_acceptance_digest')} != {contract.get('live_acceptance_digest')}"
        )
    return {"obligation": "reserved", "path": str(record_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["require", "verify"], nargs="?", default="verify")
    parser.add_argument("--plan", type=Path, help="path to the plan being checked")
    parser.add_argument("--report", type=Path, help="path to the live-session report JSON file")
    parser.add_argument("--required-evidence", type=Path, help="path to the required-evidence JSON record")
    args = parser.parse_args()
    repo = Path.cwd()
    try:
        if args.command == "require":
            plan = args.plan if args.plan is not None else "docs/plan/active"
            plan_obj = Path(plan)
            if plan_obj.is_dir():
                matches = sorted(repo.glob(str(plan_obj / "[0-9][0-9][0-9]-*.md")))
                if not matches:
                    raise ValueError(f"no active plan file found under {repo / 'docs/plan/active'}")
                plan_obj = matches[-1]
            payload = command_require(repo, plan_obj)
            print(json.dumps(payload, sort_keys=True))
            return 0
        plan_path = args.plan if args.plan is not None else Path("docs/plan/active")
        if plan_path.is_dir():
            matches = sorted(repo.glob(str(plan_path / "[0-9][0-9][0-9]-*.md")))
            if not matches:
                raise ValueError(f"no active plan file found under {repo / 'docs/plan/active'}")
            plan_path = matches[-1]
        elif not plan_path.is_absolute():
            plan_path = repo / plan_path
        report_path = args.report if args.report is not None else resolve_report(None)
        required_path = args.required_evidence if args.required_evidence is not None else resolve_required_evidence(None)
        if not report_path.exists():
            raise ValueError(f"live report does not exist: {report_path}")
        if not required_path.exists():
            raise ValueError(
                f"required-evidence record does not exist: {required_path}. "
                "Create it before implementation and keep it unchanged until completion."
            )
        required_record = load_json(required_path)
        if not isinstance(required_record, dict):
            raise ValueError(f"required-evidence record must contain a JSON object: {required_path}")
        require_record(required_record, plan_path, report_path)
        report = load_json(report_path)
        if not isinstance(report, dict):
            raise ValueError(f"live session report must contain a JSON object: {report_path}")
        validate_report(report, plan_path)
        print(f"parallel live-session verification passed for {plan_path}")
        return 0
    except (ValueError, EvidenceError) as exc:
        print(f"parallel live-session verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
