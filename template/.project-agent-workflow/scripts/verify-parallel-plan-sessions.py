#!/usr/bin/env python3
"""Verify a private live parallel-session report against a plan's required evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPORT_ENV = "PROJECT_AGENT_WORKFLOW_PARALLEL_LIVE_REPORT"
REQUIRED_EVIDENCE_ENV = "PROJECT_AGENT_WORKFLOW_REQUIRED_EVIDENCE"
DEFAULT_REQUIRED_EVIDENCE = ".agent-artifacts/parallel-plan-required-evidence.json"


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def parse_plan_digest(plan_path: Path) -> str:
    return file_digest(plan_path)


def parse_live_acceptance_digest(plan_path: Path) -> str:
    text = plan_path.read_text(encoding="utf-8")
    explicit = re.search(r"live acceptance digest[^\n]*?(sha256:[0-9a-f]{64})", text, flags=re.IGNORECASE)
    if explicit:
        return explicit.group(1)
    matches = re.findall(r"sha256:[0-9a-f]{64}", text)
    if not matches:
        raise ValueError(f"plan does not contain a live acceptance digest: {plan_path}")
    return matches[-1]


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
    plan_digest = parse_plan_digest(plan_path)
    live_acceptance_digest = parse_live_acceptance_digest(plan_path)
    expected = required_record.get("plan_digest")
    if expected is not None and expected != plan_digest:
        raise ValueError(
            f"required-evidence plan digest mismatch: expected {expected}, found {plan_digest}"
        )
    required_live = required_record.get("live_acceptance_digest")
    if required_live is not None and required_live != live_acceptance_digest:
        raise ValueError(
            f"required-evidence live acceptance digest mismatch: expected {required_live}, "
            f"found {live_acceptance_digest}"
        )
    if required_record.get("report_digest"):
        expected_report = required_record["report_digest"]
        actual_report = file_digest(report_path)
        if expected_report != actual_report:
            raise ValueError(
                f"required-evidence report digest mismatch: expected {expected_report}, "
                f"found {actual_report}"
            )
    if "execution_genesis" not in required_record:
        raise ValueError("required-evidence record must declare execution_genesis")


def validate_report(report: dict[str, Any], plan_path: Path) -> None:
    plan_digest = parse_plan_digest(plan_path)
    live_acceptance_digest = parse_live_acceptance_digest(plan_path)
    if report.get("plan_digest") not in (None, plan_digest):
        raise ValueError(f"report plan digest mismatch: expected {plan_digest}, found {report.get('plan_digest')}")
    if report.get("live_acceptance_digest") not in (None, live_acceptance_digest):
        raise ValueError(
            "report live acceptance digest mismatch: "
            f"expected {live_acceptance_digest}, found {report.get('live_acceptance_digest')}"
        )
    if report.get("acceptance_digest") not in (None, live_acceptance_digest):
        raise ValueError(
            "report acceptance digest mismatch: "
            f"expected {live_acceptance_digest}, found {report.get('acceptance_digest')}"
        )
    if report.get("acceptance_sha256") not in (None, live_acceptance_digest):
        raise ValueError(
            "report acceptance_sha256 mismatch: "
            f"expected {live_acceptance_digest}, found {report.get('acceptance_sha256')}"
        )
    session_ids = coerce_strings(report.get("distinct_session_ids") or report.get("session_ids"))
    if len(session_ids) < 2:
        session_count = report.get("session_count")
        if session_count is None or int(session_count) < 2:
            raise ValueError("report must contain evidence for at least two distinct sessions")
    if "distinct_session_ids" in report and len(set(session_ids)) < 2:
        raise ValueError("report distinct_session_ids must include at least two unique sessions")
    intervals = report.get("implementation_intervals")
    if isinstance(intervals, list) and intervals:
        parsed = []
        for interval in intervals:
            if isinstance(interval, dict):
                start = interval.get("start")
                end = interval.get("end")
                if start is not None and end is not None:
                    parsed.append((start, end))
        if len(parsed) >= 2:
            overlaps = False
            for i, (start_a, end_a) in enumerate(parsed):
                for _, (start_b, end_b) in enumerate(parsed[i + 1 :], start=i + 1):
                    if start_a < end_b and start_b < end_a:
                        overlaps = True
                        break
                if overlaps:
                    break
            if not overlaps:
                raise ValueError("report implementation intervals do not overlap")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="path to the active plan being verified")
    parser.add_argument("--report", type=Path, help="path to the live-session JSON report")
    parser.add_argument(
        "--required-evidence",
        type=Path,
        help="path to the required-evidence JSON record; defaults to .agent-artifacts/parallel-plan-required-evidence.json",
    )
    args = parser.parse_args()

    try:
        plan_path = args.plan if args.plan is not None else Path("docs/plan/active").resolve()
        if plan_path.is_dir():
            matches = sorted(plan_path.glob("[0-9][0-9][0-9]-*.md"))
            if not matches:
                raise ValueError(f"no active plan file found under {plan_path}")
            plan_path = matches[-1]
        if not plan_path.is_file():
            raise ValueError(f"plan file not found: {plan_path}")

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
    except ValueError as exc:
        print(f"parallel live-session verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"parallel live-session verification passed for {plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
