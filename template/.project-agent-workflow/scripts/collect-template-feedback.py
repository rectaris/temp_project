#!/usr/bin/env python3
"""Collect local improvement reports as traceable template requirement candidates."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

MAX_REPORTS = 32
MAX_CRITERIA = 16
MAX_NOTES = 16
REPORT_ROOT = PurePosixPath("docs/improvements/reports")
REQUIREMENT_ROOT = PurePosixPath("docs/improvements/requirements")
CANDIDATE_KEYS = {
    "schema_version",
    "candidate_id",
    "requested_behavior",
    "sources",
    "applicability",
    "fix_status",
    "completion_criteria",
    "priority_suggestion",
    "disagreements",
    "pending_questions",
    "supersedes",
}
APPLICABILITY = {"template_wide", "project_specific", "unknown"}
FIX_STATES = {"open", "already_fixed", "unknown"}
PRIORITY_LEVELS = {"high", "medium", "low"}
NONE = "none"


def load_validator() -> ModuleType:
    """Reuse the checked record validator that ships beside this command."""

    module_path = Path(__file__).resolve().parent / "template-feedback.py"
    spec = importlib.util.spec_from_file_location("template_feedback_validator", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"improvement record validator is missing: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FEEDBACK = load_validator()
FeedbackError = FEEDBACK.FeedbackError
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")


def digest(data: bytes) -> str:
    return FEEDBACK.digest(data)


def json_text(value: Any) -> str:
    return FEEDBACK.json_text(value)


def bounded_text(value: Any, label: str) -> str:
    text = FEEDBACK.bounded_text(value, label)
    # Imported prose is evidence, never an instruction. Refusing credential
    # shapes here keeps a hostile or careless source from persisting one.
    FEEDBACK.reject_suspected_secrets(text, label)
    return text


def bounded_notes(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise FeedbackError(f"{label} must be a list")
    if len(value) > MAX_NOTES:
        raise FeedbackError(f"{label} exceeds its bounded item count")
    notes = [bounded_text(item, f"{label}[{index}]") for index, item in enumerate(value)]
    for index, note in enumerate(notes):
        # Inspection prints one note per line, so a note never spans lines and
        # cannot forge an entry beside it.
        if "\n" in note:
            raise FeedbackError(f"{label}[{index}] must stay on one line")
    return notes


def stored_report_path(alias: str, report_id: str) -> PurePosixPath:
    return REPORT_ROOT / alias / f"{report_id}.json"


def held_directory(root: Path, relative: PurePosixPath) -> Path | None:
    """Resolve one storage directory under the same guard the writes use.

    A read is the receiver's own tree too, so a symlinked component is an
    unsafe repository state rather than a path to quietly follow outside.
    """

    directory = FEEDBACK.safe_repository_path(root, str(relative), f"{relative} storage directory")
    if not directory.is_dir():
        return None
    return directory


def held_entries(
    root: Path, relative: PurePosixPath, name_pattern: re.Pattern[str]
) -> tuple[list[tuple[str, Path]], int]:
    """List the safe, conventionally named JSON files in one storage directory.

    A conforming name keeps a listed entry from carrying its own line breaks or
    separators into a readable listing. The count of everything skipped is
    returned so a reader is told that something is held but not shown.
    """

    directory = held_directory(root, relative)
    if directory is None:
        return [], 0
    entries: list[tuple[str, Path]] = []
    skipped = 0
    for entry in sorted(directory.iterdir()):
        if entry.is_dir() and not entry.is_symlink():
            continue
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json" or not name_pattern.fullmatch(entry.stem):
            skipped += 1
            continue
        entries.append((entry.stem, FEEDBACK.safe_repository_path(root, str(relative / entry.name), "stored entry")))
    return entries, skipped


def held_reports(root: Path) -> tuple[dict[tuple[str, str], str], int]:
    """Return the digest of every report this repository already holds.

    Only the receiver's own tree is read. No source project is discovered.
    """

    directory = held_directory(root, REPORT_ROOT)
    held: dict[tuple[str, str], str] = {}
    unlisted = 0
    if directory is None:
        return held, unlisted
    for alias_directory in sorted(directory.iterdir()):
        # A report lives under its project alias, so anything else at this level
        # is held but unlistable and is counted rather than silently dropped.
        if alias_directory.is_symlink() or not alias_directory.is_dir():
            unlisted += 1
            continue
        if not FEEDBACK.ALIAS_RE.fullmatch(alias_directory.name):
            unlisted += 1
            continue
        entries, skipped = held_entries(root, REPORT_ROOT / alias_directory.name, ID_RE)
        unlisted += skipped
        for report_id, path in entries:
            held[(alias_directory.name, report_id)] = digest(FEEDBACK.read_regular(path, "stored report"))
    return held, unlisted


def read_report(root: Path, value: str) -> tuple[dict[str, Any], str, str, PurePosixPath]:
    path = Path(value)
    if path.is_dir():
        raise FeedbackError(f"a report source must be one explicit file, not a directory: {value}")
    record, _ = FEEDBACK.parse_record(path, root)
    content = json_text(record)
    canonical = content.encode()
    # The stored form is re-serialized, so it can exceed the bound that admitted
    # the input. Refusing here keeps the receiver from writing a report that it
    # would later refuse to read back.
    if len(canonical) > FEEDBACK.MAX_BYTES:
        raise FeedbackError(f"the stored form of this report exceeds its bounded size: {value}")
    return record, content, digest(canonical), stored_report_path(record["project_alias"], record["report_id"])


def import_plan(root: Path, reports: list[str]) -> list[dict[str, Any]]:
    """Validate every supplied report before the receiver writes anything."""

    if not reports:
        raise FeedbackError("import needs at least one explicit report file")
    if len(reports) > MAX_REPORTS:
        raise FeedbackError("import exceeds its bounded report count")
    planned: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], str] = {}
    for value in reports:
        record, content, content_digest, relative = read_report(root, value)
        identity = (record["project_alias"], record["report_id"])
        if identity in seen:
            # Even an identical repeat is refused: a doubled entry would report
            # one stored report as two imported ones.
            if seen[identity] != content_digest:
                raise FeedbackError(f"two supplied reports claim one identity with different bytes: {relative}")
            raise FeedbackError(f"one report identity was supplied twice: {relative}")
        seen[identity] = content_digest
        destination = FEEDBACK.safe_repository_path(root, str(relative), "stored report path")
        outcome = "new"
        if destination.exists():
            if destination.is_symlink() or not destination.is_file():
                raise FeedbackError(f"refusing unsafe existing report: {relative}")
            if digest(FEEDBACK.read_regular(destination, "held report")) != content_digest:
                raise FeedbackError(
                    f"a held report already exists with different bytes: {relative}; "
                    "a correction arrives as a new report id that supersedes the earlier one"
                )
            outcome = "unchanged"
        planned.append(
            {
                "project_alias": record["project_alias"],
                "report_id": record["report_id"],
                "digest": content_digest,
                "stored_path": str(relative),
                "outcome": outcome,
                "source": value,
                "content": content,
            }
        )
    return planned


def parse_candidate_shape(root: Path, path: Path) -> tuple[dict[str, Any], bytes]:
    """Validate one candidate on its own bytes, without reading held reports.

    Shape is a property of the file, so a reader can re-derive it later even
    when the surrounding tree has changed.
    """

    value, raw = FEEDBACK.load_json(path, "candidate")
    FEEDBACK.exact(value, CANDIDATE_KEYS, "candidate")
    if value["schema_version"] != 1:
        raise FeedbackError("unsupported candidate schema")
    if not isinstance(value["candidate_id"], str) or not ID_RE.fullmatch(value["candidate_id"]):
        raise FeedbackError("candidate_id must use 1-64 lowercase letters, digits, or hyphens")
    bounded_text(value["requested_behavior"], "requested_behavior")

    sources = value["sources"]
    if not isinstance(sources, list) or not sources:
        raise FeedbackError("a candidate must cite at least one held report")
    if len(sources) > MAX_REPORTS:
        raise FeedbackError("sources exceeds its bounded item count")
    identities: set[tuple[str, str]] = set()
    for index, raw_source in enumerate(sources):
        label = f"sources[{index}]"
        source = FEEDBACK.exact(raw_source, {"project_alias", "report_id", "digest"}, label)
        if not isinstance(source["project_alias"], str) or not FEEDBACK.ALIAS_RE.fullmatch(source["project_alias"]):
            raise FeedbackError(f"{label}.project_alias must use 1-64 lowercase letters, digits, or hyphens")
        if not isinstance(source["report_id"], str) or not ID_RE.fullmatch(source["report_id"]):
            raise FeedbackError(f"{label}.report_id must use 1-64 lowercase letters, digits, or hyphens")
        identity = (source["project_alias"], source["report_id"])
        if identity in identities:
            raise FeedbackError(f"{label} repeats one report identity")
        identities.add(identity)

    applicability = FEEDBACK.exact(value["applicability"], {"certainty", "explanation"}, "applicability")
    if applicability["certainty"] not in APPLICABILITY:
        raise FeedbackError("applicability.certainty must be template_wide, project_specific, or unknown")
    bounded_text(applicability["explanation"], "applicability.explanation")

    fix_status = FEEDBACK.exact(value["fix_status"], {"state", "reference"}, "fix_status")
    if fix_status["state"] not in FIX_STATES:
        raise FeedbackError("fix_status.state must be open, already_fixed, or unknown")
    reference = bounded_text(fix_status["reference"], "fix_status.reference")
    if fix_status["state"] == "already_fixed" and reference == NONE:
        # An already-fixed claim without a change or verification reference is
        # an assertion, not evidence.
        raise FeedbackError("an already_fixed claim needs a matching change or verification reference")
    if reference != NONE:
        if any(character.isspace() for character in reference):
            raise FeedbackError("fix_status.reference must be a path without whitespace")
        FEEDBACK.safe_repository_path(root, reference, "fix_status.reference")

    criteria = value["completion_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise FeedbackError("a candidate must state at least one completion criterion")
    if len(criteria) > MAX_CRITERIA:
        raise FeedbackError("completion_criteria exceeds its bounded item count")
    for index, item in enumerate(criteria):
        bounded_text(item, f"completion_criteria[{index}]")

    priority = FEEDBACK.exact(
        value["priority_suggestion"],
        {"level", "impact", "recurrence", "evidence", "effort"},
        "priority_suggestion",
    )
    if priority["level"] not in PRIORITY_LEVELS:
        raise FeedbackError("priority_suggestion.level must be high, medium, or low")
    for field in ("impact", "recurrence", "evidence", "effort"):
        bounded_text(priority[field], f"priority_suggestion.{field}")

    value["disagreements"] = bounded_notes(value["disagreements"], "disagreements")
    value["pending_questions"] = bounded_notes(value["pending_questions"], "pending_questions")

    supersedes = value["supersedes"]
    if supersedes != NONE and (not isinstance(supersedes, str) or not ID_RE.fullmatch(supersedes)):
        raise FeedbackError("supersedes must name an existing candidate id or the explicit none value")
    if supersedes == value["candidate_id"]:
        raise FeedbackError("supersedes must not name the candidate itself")
    return value, raw


def verify_candidate_sources(root: Path, value: dict[str, Any]) -> None:
    """Bind a candidate to the exact held report bytes it cites."""

    held, _ = held_reports(root)
    for index, source in enumerate(value["sources"]):
        label = f"sources[{index}]"
        identity = (source["project_alias"], source["report_id"])
        if identity not in held:
            raise FeedbackError(f"{label} cites a report this repository does not hold")
        if held[identity] != source["digest"]:
            raise FeedbackError(f"{label} cites a digest that does not match the held report bytes")


def parse_candidate(root: Path, path: Path) -> tuple[dict[str, Any], bytes]:
    value, raw = parse_candidate_shape(root, path)
    verify_candidate_sources(root, value)
    return value, raw


def held_candidates(root: Path) -> tuple[list[tuple[str, Path]], int]:
    return held_entries(root, REQUIREMENT_ROOT, ID_RE)


def held_candidate_ids(root: Path) -> set[str]:
    entries, _ = held_candidates(root)
    return {candidate_id for candidate_id, _ in entries}


def command_example(args: argparse.Namespace) -> int:
    del args
    sys.stdout.write(
        json_text(
            {
                "schema_version": 1,
                "candidate_id": "report-worktree-removal-in-publish-output",
                "requested_behavior": "Publish should report the worktree removal it performed.",
                "sources": [
                    {
                        "project_alias": "example-project",
                        "report_id": "plan-worktree-publish-confusion",
                        "digest": "sha256:" + "0" * 64,
                    }
                ],
                "applicability": {
                    "certainty": "unknown",
                    "explanation": "One project reported it; local hooks were not ruled out as the cause.",
                },
                "fix_status": {"state": "open", "reference": NONE},
                "completion_criteria": [
                    "Publish output names the removed worktree and branch.",
                    "A test fails when publish reports success without removing them.",
                ],
                "priority_suggestion": {
                    "level": "medium",
                    "impact": "Two tasks shared one checkout before anyone noticed.",
                    "recurrence": "Reported once by one project.",
                    "evidence": "One held report with an agent paraphrase and a change reference.",
                    "effort": "Unestimated; the publish path is small but validated.",
                },
                "disagreements": [],
                "pending_questions": ["Does the same publish output appear when no worktree existed?"],
                "supersedes": NONE,
            }
        )
    )
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    planned = import_plan(root, args.report)
    sys.stdout.write(
        json_text(
            {
                "decision": "import",
                "reports": [
                    {key: entry[key] for key in ("project_alias", "report_id", "digest", "stored_path", "outcome")}
                    for entry in planned
                ],
                "checked_digest": digest("".join(entry["content"] for entry in planned).encode()),
            }
        )
    )
    return 0


def command_import(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    planned = import_plan(root, args.report)
    checked = digest("".join(entry["content"] for entry in planned).encode())
    if args.checked_digest != checked:
        raise FeedbackError("checked digest does not match the supplied report set")
    pending = [entry for entry in planned if entry["outcome"] == "new"]
    if pending:
        FEEDBACK.require_task_binding(root, "importing improvement reports")
        for entry in pending:
            relative = PurePosixPath(entry["stored_path"])
            FEEDBACK.prepare_directory(root, relative.parent)
            FEEDBACK.atomic_write(root / relative, entry["content"])
    sys.stdout.write(
        json_text(
            {
                "decision": "import",
                "checked_digest": checked,
                "written": [entry["stored_path"] for entry in pending],
                "unchanged": [entry["stored_path"] for entry in planned if entry["outcome"] == "unchanged"],
            }
        )
    )
    return 0


def candidate_assessment(record: dict[str, Any], raw: bytes) -> dict[str, Any]:
    return {
        "decision": "record_candidate",
        "candidate_id": record["candidate_id"],
        "checked_digest": digest(raw),
        "candidate_path": str(REQUIREMENT_ROOT / f"{record['candidate_id']}.json"),
        "applicability_certainty": record["applicability"]["certainty"],
        "fix_status": record["fix_status"]["state"],
        "priority_suggestion": record["priority_suggestion"]["level"],
        "sources": [f"{item['project_alias']}/{item['report_id']}" for item in record["sources"]],
        "pending_questions": record["pending_questions"],
    }


def command_check_candidate(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    record, raw = parse_candidate(root, Path(args.candidate))
    sys.stdout.write(json_text(candidate_assessment(record, raw)))
    return 0


def command_record_candidate(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    record, raw = parse_candidate(root, Path(args.candidate))
    result = candidate_assessment(record, raw)
    if args.checked_digest != result["checked_digest"]:
        raise FeedbackError("checked digest does not match the supplied candidate bytes")
    if record["supersedes"] != NONE and record["supersedes"] not in held_candidate_ids(root):
        raise FeedbackError("supersedes names a candidate that this repository does not hold")

    relative = PurePosixPath(result["candidate_path"])
    content = json_text(record)
    destination = FEEDBACK.safe_repository_path(root, str(relative), "candidate_path")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise FeedbackError(f"refusing unsafe existing candidate: {relative}")
        if destination.read_text(encoding="utf-8") == content:
            result["outcome"] = "unchanged"
            sys.stdout.write(json_text(result))
            return 0
        raise FeedbackError(
            f"an earlier candidate revision exists with different bytes: {relative}; "
            "record a revision under a new candidate id that supersedes this one"
        )

    FEEDBACK.require_task_binding(root, "recording a template requirement candidate")
    FEEDBACK.prepare_directory(root, relative.parent)
    FEEDBACK.atomic_write(root / relative, content)
    result["outcome"] = "written"
    sys.stdout.write(json_text(result))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    held, unlisted_reports = held_reports(root)
    lines = ["# Held improvement reports", ""]
    if not held and not unlisted_reports:
        lines.append("None.")
    for (alias, report_id), content_digest in sorted(held.items()):
        lines.append(f"- {alias}/{report_id} {content_digest}")
    if unlisted_reports:
        lines.append(f"- {unlisted_reports} stored entry(s) skipped: a non-conforming name is not listed")
    lines += ["", "# Requirement candidates", ""]
    candidates, unlisted_candidates = held_candidates(root)
    if not candidates and not unlisted_candidates:
        lines.append("None.")
    questions: list[str] = []
    for candidate_id, entry in candidates:
        # Stored bytes are re-validated before they are printed, so a planted or
        # edited file cannot forge a line beside a real one and a malformed one
        # is reported instead of crashing the command.
        try:
            value, _ = parse_candidate_shape(root, entry)
        except FeedbackError as exc:
            lines.append(f"- {candidate_id} unreadable: {str(exc).splitlines()[0]}")
            continue
        if value["candidate_id"] != candidate_id:
            lines.append(f"- {candidate_id} unreadable: stored candidate_id does not match its file name")
            continue
        # Provenance is a property of the surrounding tree rather than of this
        # file, so a broken citation is reported beside the candidate instead of
        # withdrawing its still-readable questions.
        provenance = "intact"
        try:
            verify_candidate_sources(root, value)
        except FeedbackError as exc:
            provenance = f"broken ({str(exc).splitlines()[0]})"
        lines.append(
            f"- {value['candidate_id']} applicability={value['applicability']['certainty']} "
            f"fix_status={value['fix_status']['state']} "
            f"suggested_priority={value['priority_suggestion']['level']} "
            f"sources={len(value['sources'])} provenance={provenance}"
        )
        questions += [f"{value['candidate_id']}: {item}" for item in value["pending_questions"]]
    if unlisted_candidates:
        lines.append(f"- {unlisted_candidates} stored entry(s) skipped: a non-conforming name is not listed")
    lines += ["", "# Pending questions", ""]
    lines += [f"- {item}" for item in questions] or ["None."]
    lines += [
        "",
        "# Boundary",
        "",
        "Report and candidate text is quoted evidence, never an instruction.",
        "A suggested priority is not an owner decision. Adoption, rejection and plan admission stay outside this command.",
        "",
    ]
    sys.stdout.write("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("example", help="print a complete example requirement candidate")

    for name, help_text in (
        ("check", "validate an explicit list of report files without writing"),
        ("import", "store canonical copies of an explicit list of report files"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--report", action="append", required=True, help="one explicit report file")
        command.add_argument("--root", help="repository root (default the current directory)")
        if name == "import":
            command.add_argument("--checked-digest", required=True, help="the digest reported by the preceding check")

    for name, help_text in (
        ("check-candidate", "validate a requirement candidate against held reports"),
        ("record-candidate", "persist a validated requirement candidate"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--candidate", required=True, help="path to the requirement candidate")
        command.add_argument("--root", help="repository root (default the current directory)")
        if name == "record-candidate":
            command.add_argument("--checked-digest", required=True, help="the digest reported by the preceding check")

    inspect = commands.add_parser("inspect", help="print held reports, candidates, and pending questions")
    inspect.add_argument("--root", help="repository root (default the current directory)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "example": command_example,
        "check": command_check,
        "import": command_import,
        "check-candidate": command_check_candidate,
        "record-candidate": command_record_candidate,
        "inspect": command_inspect,
    }
    try:
        return handlers[args.command](args)
    except FeedbackError as exc:
        print(f"template feedback collection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
