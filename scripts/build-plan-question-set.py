#!/usr/bin/env python3
"""Build a labeled implementation-risk question set from committed plan records.

The command reads committed plan files and Git history only. It calls no
provider, needs no network, and writes no file: the report goes to stdout.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REPORT_KIND = "plan_record_question_set"
PLAN_ROOT = "docs/plan"
PLAN_FILE_NAME = re.compile(r"^[0-9]{3}-[A-Za-z0-9._-]+\.md$")
LABEL_FIELD = "implementation_risk"
LABEL_VALUES = ("low", "ordinary", "high")
REMOVED_FIELDS = (
    "status",
    "successor_plans",
    "replan_contract",
    "replan_sources",
    "replan_source",
    "human_approval_status",
    LABEL_FIELD,
)
PRE_EXECUTION_STATUSES = ("backlog", "deferred", "in_progress", "active")
LINEAGE_PLAN_FIELDS = ("successor_plans", "replan_sources", "replan_source")
LINEAGE_CONTRACT_FIELD = "replan_contract"
PARTITIONS = ("tuning", "holdout")
DEFAULT_HOLDOUT_FROM = "2026-09-14T00:00:00Z"
DEFAULT_MIN_CLASS_COUNT = 10
MAX_PLANS = 4096
MAX_PLAN_BYTES = 256 * 1024
MAX_REPORT_BYTES = 64 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 300
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

MANIFEST_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")
COMPLETED_TASK = re.compile(r"(?m)^[ \t]*[-*+][ \t]+\[[xX]\]")
# `status` is an ordinary English word, so it leaks only as a field-like `status:`.
# Every other removed name is a distinctive identifier and leaks as any whole token.
LEAKED_STATUS_FIELD = re.compile(r"(?<![A-Za-z0-9_])(status)(?![A-Za-z0-9_])[`'\"*]*[ \t]*:")
LEAKED_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(re.escape(name) for name in REMOVED_FIELDS if name != "status")
    + r")(?![A-Za-z0-9_])"
)


class QuestionSetError(RuntimeError):
    """The question set cannot be built or verified from the supplied history."""


@dataclass(frozen=True)
class SourceRevision:
    commit: str
    committed_at: int
    path: str


@dataclass(frozen=True)
class ManifestField:
    key: str
    value: str
    start: int
    end: int


def git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment


def git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotePath=true", *args],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_environment(),
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QuestionSetError(f"git {args[0]} failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        raise QuestionSetError(f"git {args[0]} failed: {detail[-1] if detail else completed.returncode}")
    return completed.stdout


def resolve_revision(repo: Path, revision: str) -> str:
    if revision.startswith("-"):
        raise QuestionSetError("revision must not start with '-'")
    return git(repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()


def plan_files_at(repo: Path, commit: str) -> dict[str, list[str]]:
    listing = git(repo, "ls-tree", "-r", "-z", "--name-only", commit, "--", PLAN_ROOT)
    by_name: dict[str, list[str]] = {}
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8", "surrogateescape")
        name = path.rsplit("/", 1)[-1]
        if PLAN_FILE_NAME.fullmatch(name):
            by_name.setdefault(name, []).append(path)
    if len(by_name) > MAX_PLANS:
        raise QuestionSetError(f"{len(by_name)} plan files exceed the bound of {MAX_PLANS}")
    return by_name


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=git_environment(),
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QuestionSetError(f"git merge-base failed: {exc}") from exc
    if completed.returncode not in (0, 1):
        raise QuestionSetError(f"git merge-base failed: {completed.stderr.decode('utf-8', 'replace').strip()}")
    return completed.returncode == 0


def first_additions(repo: Path, commit: str) -> tuple[dict[str, SourceRevision], set[str]]:
    """Map each plan file name to the earliest revision that added it under docs/plan.

    Additions that do not descend from the topologically first one are
    concurrent, for example an authored file and a later squash of it on
    another branch. The earliest committed of them is the source. When several
    share that earliest commit time with different bytes, the name has no
    single first revision and is returned in the ambiguous set instead.
    """

    log = git(
        repo,
        "log",
        "--reverse",
        "--topo-order",
        "--full-history",
        "-m",
        "--no-renames",
        "--diff-filter=A",
        "--name-only",
        "--format=commit %H %ct",
        commit,
        "--",
        PLAN_ROOT,
    ).decode("utf-8", "surrogateescape")
    additions: dict[str, SourceRevision] = {}
    later: dict[str, list[SourceRevision]] = {}
    current: tuple[str, int] | None = None
    for line in log.splitlines():
        if line.startswith("commit "):
            _, sha, stamp = line.split(" ")
            current = (sha, int(stamp))
            continue
        if not line or current is None or not line.startswith(PLAN_ROOT + "/"):
            continue
        name = line.rsplit("/", 1)[-1]
        if not PLAN_FILE_NAME.fullmatch(name):
            continue
        if name not in additions:
            additions[name] = SourceRevision(current[0], current[1], line)
        elif current[0] != additions[name].commit:
            later.setdefault(name, []).append(SourceRevision(current[0], current[1], line))
    known: dict[tuple[str, str], bool] = {}
    concurrent: dict[str, list[SourceRevision]] = {}
    for name, revisions in later.items():
        first = additions[name]
        for other in revisions:
            key = (first.commit, other.commit)
            if key not in known:
                known[key] = is_ancestor(repo, first.commit, other.commit)
            if not known[key]:
                concurrent.setdefault(name, [first]).append(other)
    earliest: dict[str, list[SourceRevision]] = {}
    for name, revisions in concurrent.items():
        first_time = min(item.committed_at for item in revisions)
        earliest[name] = [item for item in revisions if item.committed_at == first_time]
    specs = sorted({f"{item.commit}:{item.path}" for items in earliest.values() for item in items})
    objects = blob_ids(repo, specs)
    ambiguous: set[str] = set()
    for name, revisions in earliest.items():
        if len({objects[f"{item.commit}:{item.path}"] for item in revisions}) != 1:
            ambiguous.add(name)
            continue
        additions[name] = revisions[0]
    return additions, ambiguous


def blob_ids(repo: Path, specs: list[str]) -> dict[str, str]:
    if not specs:
        return {}
    request = "".join(spec + "\n" for spec in specs).encode("utf-8", "surrogateescape")
    lines = git(repo, "cat-file", "--batch-check", stdin=request).decode("utf-8", "surrogateescape").splitlines()
    if len(lines) != len(specs):
        raise QuestionSetError("git cat-file returned an unexpected number of records")
    identifiers: dict[str, str] = {}
    for spec, line in zip(specs, lines):
        fields = line.split(" ")
        if len(fields) != 3 or fields[1] != "blob":
            raise QuestionSetError(f"committed plan record is not a readable blob: {spec}")
        identifiers[spec] = fields[0]
    return identifiers


def read_blobs(repo: Path, specs: list[str]) -> dict[str, bytes | None]:
    """Read `<commit>:<path>` blobs in one batch; oversized blobs map to None."""

    if not specs:
        return {}
    request = "".join(spec + "\n" for spec in specs).encode("utf-8", "surrogateescape")
    output = git(repo, "cat-file", "--batch", stdin=request)
    blobs: dict[str, bytes | None] = {}
    offset = 0
    for spec in specs:
        header_end = output.index(b"\n", offset)
        header = output[offset:header_end].decode("utf-8", "surrogateescape").split(" ")
        offset = header_end + 1
        if len(header) != 3 or header[1] != "blob":
            raise QuestionSetError(f"committed plan record is not a readable blob: {spec}")
        size = int(header[2])
        data = output[offset : offset + size]
        offset += size + 1
        blobs[spec] = data if size <= MAX_PLAN_BYTES else None
    return blobs


def manifest_fields(text: str) -> list[ManifestField]:
    """Return the leading manifest fields with their line spans."""

    lines = text.splitlines(keepends=True)
    fields: list[ManifestField] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        if line.startswith("## "):
            break
        match = MANIFEST_KEY.match(line)
        if not match:
            index += 1
            continue
        end = index + 1
        while end < len(lines):
            follower = lines[end].rstrip("\r\n")
            if not follower.strip() or follower.startswith("## "):
                break
            if not (follower[:1].isspace() or follower.startswith("- ")):
                break
            end += 1
        fields.append(ManifestField(match.group(1), match.group(2).strip(), index, end))
        index = end
    return fields


def scalar_values(fields: list[ManifestField], key: str) -> list[str]:
    return [field.value for field in fields if field.key == key]


def list_values(text: str, fields: list[ManifestField], key: str) -> list[str]:
    lines = text.splitlines()
    values: list[str] = []
    for field in fields:
        if field.key != key:
            continue
        if field.value:
            values.append(field.value)
        for line in lines[field.start + 1 : field.end]:
            item = line.strip()
            if item.startswith("- "):
                values.append(item[2:].strip())
    return values


def question_input(text: str, fields: list[ManifestField]) -> str:
    removed: set[int] = set()
    for field in fields:
        if field.key in REMOVED_FIELDS:
            removed.update(range(field.start, field.end))
    lines = text.splitlines(keepends=True)
    return "".join(line for index, line in enumerate(lines) if index not in removed)


def leaked_fields(value: str) -> list[str]:
    found = {match.group(1) for match in LEAKED_STATUS_FIELD.finditer(value)}
    found.update(match.group(1) for match in LEAKED_TOKEN.finditer(value))
    return sorted(found)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def timestamp(value: int) -> str:
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).strftime(TIMESTAMP_FORMAT)


def parse_timestamp(value: str) -> int:
    try:
        parsed = datetime.datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise QuestionSetError(f"timestamp must use {TIMESTAMP_FORMAT}: {value!r}") from exc
    return int(parsed.replace(tzinfo=datetime.timezone.utc).timestamp())


def evaluate_source(data: bytes | None) -> tuple[list[str], dict[str, Any]]:
    """Return rejection reasons and the derived question fields for one source blob."""

    if data is None:
        return ["oversized_source"], {"raw_label": None}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["undecodable_source"], {"raw_label": None}
    fields = manifest_fields(text)
    reasons: list[str] = []
    labels = scalar_values(fields, LABEL_FIELD)
    raw_label = labels[0] if len(labels) == 1 else (labels or None)
    if not labels or labels == [""]:
        reasons.append("label_missing")
        raw_label = None
    elif len(labels) > 1:
        reasons.append("label_ambiguous")
    elif labels[0] not in LABEL_VALUES:
        reasons.append("label_out_of_policy")
    statuses = scalar_values(fields, "status")
    raw_status = statuses[0] if len(statuses) == 1 else (statuses or None)
    if not statuses or statuses == [""]:
        reasons.append("status_missing")
    elif len(statuses) > 1:
        reasons.append("status_ambiguous")
    elif statuses[0] not in PRE_EXECUTION_STATUSES:
        reasons.append("recorded_after_execution")
    if COMPLETED_TASK.search(text):
        reasons.append("completed_task_recorded")
    value = question_input(text, fields)
    reasons.extend(f"leaked_field:{name}" for name in leaked_fields(value))
    return reasons, {"raw_label": raw_label, "raw_status": raw_status, "input": value}


def lineage_groups(
    repo: Path, commit: str, current: dict[str, str], members: list[str]
) -> dict[str, str]:
    """Union plan files linked by replan lineage recorded at the scanned revision."""

    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        parent[find(left)] = find(right)

    specs = {name: f"{commit}:{path}" for name, path in current.items()}
    blobs = read_blobs(repo, list(specs.values()))
    for name, spec in specs.items():
        data = blobs[spec]
        if data is None:
            raise QuestionSetError(f"lineage record exceeds {MAX_PLAN_BYTES} bytes: {current[name]}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QuestionSetError(f"lineage record is not UTF-8: {current[name]}") from exc
        fields = manifest_fields(text)
        find(name)
        for key in LINEAGE_PLAN_FIELDS:
            for reference in list_values(text, fields, key):
                linked = reference.rsplit("/", 1)[-1]
                if PLAN_FILE_NAME.fullmatch(linked):
                    union(name, linked)
        for reference in list_values(text, fields, LINEAGE_CONTRACT_FIELD):
            if reference and reference != "none":
                union(name, "contract:" + reference)
    return {name: find(name) for name in members}


def class_statistics(labels: list[str], minimum: int) -> dict[str, Any]:
    total = len(labels)
    classes: dict[str, Any] = {}
    for value in LABEL_VALUES:
        count = labels.count(value)
        measurable = count >= minimum
        classes[value] = {
            "count": count,
            "measurable": measurable,
            "share": round(count / total, 6) if measurable and total else None,
        }
    majority: dict[str, Any] = {"labels": [], "count": 0, "share": None}
    if total:
        top = max(labels.count(value) for value in LABEL_VALUES)
        majority = {
            "labels": [value for value in LABEL_VALUES if labels.count(value) == top],
            "count": top,
            "share": round(top / total, 6),
        }
    return {"total": total, "min_class_count": minimum, "classes": classes, "majority_class": majority}


def build_report(repo: Path, revision: str, holdout_from: str, min_class_count: int) -> dict[str, Any]:
    if min_class_count < 1:
        raise QuestionSetError("min class count must be at least 1")
    cutoff = parse_timestamp(holdout_from)
    commit = resolve_revision(repo, revision)
    located = plan_files_at(repo, commit)
    additions, ambiguous = first_additions(repo, commit)

    exclusions: list[dict[str, Any]] = []
    pending: dict[str, tuple[SourceRevision, str]] = {}
    for name in sorted(located):
        paths = located[name]
        source = additions.get(name)
        if len(paths) != 1 or source is None or name in ambiguous:
            if len(paths) != 1:
                reason = "duplicate_plan_file"
            elif source is None:
                reason = "source_revision_not_found"
            else:
                reason = "source_revision_ambiguous"
            exclusions.append(
                {
                    "plan_file": name,
                    "current_paths": sorted(paths),
                    "source_path": source.path if source else None,
                    "source_commit": source.commit if source else None,
                    "raw_label": None,
                    "reasons": [reason],
                }
            )
            continue
        pending[name] = (source, paths[0])

    blobs = read_blobs(repo, [f"{source.commit}:{source.path}" for source, _ in pending.values()])
    candidates: list[dict[str, Any]] = []
    for name, (source, current_path) in pending.items():
        reasons, derived = evaluate_source(blobs[f"{source.commit}:{source.path}"])
        if reasons:
            exclusions.append(
                {
                    "plan_file": name,
                    "current_paths": [current_path],
                    "source_path": source.path,
                    "source_commit": source.commit,
                    "raw_label": derived["raw_label"],
                    "reasons": reasons,
                }
            )
            continue
        value = derived["input"]
        candidates.append(
            {
                "question_id": name[: -len(".md")],
                "plan_file": name,
                "current_path": current_path,
                "source_path": source.path,
                "source_commit": source.commit,
                "source_committed_at": timestamp(source.committed_at),
                "label": derived["raw_label"],
                "input_sha256": sha256_text(value),
                "input": value,
                "_time": source.committed_at,
            }
        )

    current = {name: paths[0] for name, paths in located.items() if len(paths) == 1}
    roots = lineage_groups(repo, commit, current, [item["plan_file"] for item in candidates])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        grouped.setdefault(roots[item["plan_file"]], []).append(item)
    for members in grouped.values():
        members.sort(key=lambda item: (item["_time"], item["plan_file"]))
        key_time = members[0]["_time"]
        partition = "holdout" if key_time >= cutoff else "tuning"
        for item in members:
            item["lineage_group"] = members[0]["question_id"]
            item["partition"] = partition
    candidates.sort(key=lambda item: (item["_time"], item["plan_file"]))
    late_tuning = sum(1 for item in candidates if item["partition"] == "tuning" and item["_time"] >= cutoff)
    for item in candidates:
        del item["_time"]

    exclusions.sort(key=lambda item: item["plan_file"])
    by_reason: dict[str, int] = {}
    for entry in exclusions:
        for reason in entry["reasons"]:
            code = reason.split(":", 1)[0]
            by_reason[code] = by_reason.get(code, 0) + 1

    statistics = {"all": class_statistics([item["label"] for item in candidates], min_class_count)}
    partition_summary: dict[str, Any] = {
        "holdout_from": holdout_from,
        "rule": "lineage_group_earliest_question_time",
        "tuning_questions_committed_at_or_after_holdout_from": late_tuning,
    }
    for partition in PARTITIONS:
        members = [item for item in candidates if item["partition"] == partition]
        statistics[partition] = class_statistics([item["label"] for item in members], min_class_count)
        partition_summary[f"{partition}_lineage_groups"] = len({item["lineage_group"] for item in members})

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "revision": {"requested": revision, "commit": commit},
        "protocol": {
            "label_field": LABEL_FIELD,
            "label_values": list(LABEL_VALUES),
            "removed_fields": list(REMOVED_FIELDS),
            "pre_execution_statuses": list(PRE_EXECUTION_STATUSES),
            "source_rule": "first_commit_adding_plan_file_name_under_docs_plan",
            "holdout_from": holdout_from,
            "min_class_count": min_class_count,
        },
        "enumerated_plan_files": len(located),
        "questions": candidates,
        "exclusions": {"count": len(exclusions), "by_reason": dict(sorted(by_reason.items())), "plans": exclusions},
        "statistics": statistics,
        "partitions": partition_summary,
    }


def encode_report(report: dict[str, Any]) -> bytes:
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_REPORT_BYTES:
        raise QuestionSetError(f"report exceeds {MAX_REPORT_BYTES} bytes")
    return encoded


def load_report(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise QuestionSetError(f"report must be a regular file: {path}")
        if path.stat().st_size > MAX_REPORT_BYTES:
            raise QuestionSetError(f"report exceeds {MAX_REPORT_BYTES} bytes: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuestionSetError(f"report is unreadable: {exc}") from exc
    if not isinstance(report, dict) or report.get("kind") != REPORT_KIND or report.get("schema_version") != SCHEMA_VERSION:
        raise QuestionSetError("report is not a schema-1 plan record question set")
    return report


def verify_report(repo: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Regenerate the question set from committed history and compare it with a saved report."""

    try:
        commit = report["revision"]["commit"]
        protocol = report["protocol"]
        questions = report["questions"]
        holdout_from = protocol["holdout_from"]
        min_class_count = protocol["min_class_count"]
    except (KeyError, TypeError) as exc:
        raise QuestionSetError(f"report is missing field: {exc}") from exc
    if not isinstance(questions, list) or not all(isinstance(item, dict) for item in questions):
        raise QuestionSetError("report questions must be a list of objects")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise QuestionSetError("report revision commit must be a full object name")
    if not isinstance(min_class_count, int) or not isinstance(holdout_from, str):
        raise QuestionSetError("report protocol parameters are malformed")
    regenerated = build_report(repo, commit, holdout_from, min_class_count)
    expected = {item["question_id"]: item for item in regenerated["questions"]}
    supplied: dict[str, dict[str, Any]] = {}
    mismatched: list[str] = []
    for item in questions:
        identifier = str(item.get("question_id"))
        if identifier in supplied:
            mismatched.append(identifier)
        supplied[identifier] = item
    for identifier, item in supplied.items():
        if identifier in expected and item != expected[identifier]:
            mismatched.append(identifier)
        elif identifier in expected and item.get("input_sha256") != sha256_text(str(item.get("input"))):
            mismatched.append(identifier)
    missing = sorted(set(expected) - set(supplied))
    unexpected = sorted(set(supplied) - set(expected))
    other = sorted(
        key
        for key in ("protocol", "exclusions", "statistics", "partitions", "enumerated_plan_files")
        if report.get(key) != regenerated[key]
    )
    return {
        "verified": not (mismatched or missing or unexpected or other),
        "revision": commit,
        "question_count": len(expected),
        "mismatched_questions": sorted(set(mismatched)),
        "missing_questions": missing,
        "unexpected_questions": unexpected,
        "mismatched_sections": other,
    }


def repository_root(value: str | None) -> Path:
    start = Path(value) if value else Path.cwd()
    return Path(git(start, "rev-parse", "--show-toplevel").decode().strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="print the question set report to stdout")
    build.add_argument("--repo", help="repository to read; defaults to the current directory")
    build.add_argument("--revision", default="HEAD", help="revision whose plan files are enumerated")
    build.add_argument("--holdout-from", default=DEFAULT_HOLDOUT_FROM, help="UTC cutoff, " + TIMESTAMP_FORMAT)
    build.add_argument("--min-class-count", type=int, default=DEFAULT_MIN_CLASS_COUNT)
    verify = commands.add_parser("verify", help="regenerate a saved report from committed history")
    verify.add_argument("report", type=Path)
    verify.add_argument("--repo", help="repository to read; defaults to the current directory")
    args = parser.parse_args(argv)
    try:
        repo = repository_root(args.repo)
        if args.command == "build":
            output = encode_report(build_report(repo, args.revision, args.holdout_from, args.min_class_count))
            sys.stdout.buffer.write(output)
            return 0
        result = verify_report(repo, load_report(args.report))
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["verified"] else 1
    except QuestionSetError as exc:
        sys.stderr.write(f"build-plan-question-set: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
