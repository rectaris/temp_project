#!/usr/bin/env python3
"""Render a development direction from explicitly adopted requirement decisions."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

MAX_DECISIONS = 256
DECISION_ROOT = PurePosixPath("docs/improvements/decisions")
DIRECTION_PATH = PurePosixPath("docs/development-direction.md")
BEGIN_MARKER = "<!-- development-direction:generated:begin -->"
END_MARKER = "<!-- development-direction:generated:end -->"
DECISION_KEYS = {
    "schema_version",
    "decision_id",
    "candidate_id",
    "candidate_digest",
    "action",
    "reason",
    "priority",
    "authority",
    "implementation_evidence",
    "downstream_verification",
    "supersedes",
}
ACTIONS = {"accept", "defer", "reject"}
PRIORITIES = {"high", "medium", "low", "none"}
AUTHORITY_KINDS = {"owner_instruction", "prior_authorization"}
EVIDENCE_STATES = {"pending", "recorded"}
NONE = "none"


def load_collector() -> ModuleType:
    """Reuse the checked collection command that ships beside this one."""

    module_path = Path(__file__).resolve().parent / "collect-template-feedback.py"
    spec = importlib.util.spec_from_file_location("template_feedback_collector", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"improvement collection command is missing: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COLLECT = load_collector()
FEEDBACK = COLLECT.FEEDBACK
FeedbackError = COLLECT.FeedbackError
ID_RE = COLLECT.ID_RE
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


def digest(data: bytes) -> str:
    return COLLECT.digest(data)


def json_text(value: Any) -> str:
    return COLLECT.json_text(value)


def bounded_text(value: Any, label: str) -> str:
    return COLLECT.bounded_text(value, label)


def one_line(value: Any, label: str) -> str:
    text = bounded_text(value, label)
    # A rendered document and a readable listing place one record per line, so a
    # recorded value never spans lines and cannot forge an entry, a heading, or
    # a section boundary beside it.
    if "\n" in text:
        raise FeedbackError(f"{label} must stay on one line")
    if BEGIN_MARKER in text or END_MARKER in text:
        raise FeedbackError(f"{label} must not contain a generated section marker")
    return text


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise FeedbackError(f"{label} must use 1-64 lowercase letters, digits, or hyphens")
    return value


def parse_decision(root: Path, path: Path) -> tuple[dict[str, Any], bytes]:
    """Validate one decision on its own bytes, without reading held candidates."""

    value, raw = FEEDBACK.load_json(path, "decision")
    FEEDBACK.exact(value, DECISION_KEYS, "decision")
    if value["schema_version"] != 1:
        raise FeedbackError("unsupported decision schema")
    identifier(value["decision_id"], "decision_id")
    identifier(value["candidate_id"], "candidate_id")
    if not isinstance(value["candidate_digest"], str) or not DIGEST_RE.fullmatch(value["candidate_digest"]):
        raise FeedbackError("candidate_digest must be a sha256 digest of the exact candidate bytes")
    if value["action"] not in ACTIONS:
        raise FeedbackError("action must be accept, defer, or reject")
    one_line(value["reason"], "reason")
    if value["priority"] not in PRIORITIES:
        raise FeedbackError("priority must be high, medium, low, or the explicit none value")
    if value["action"] == "accept" and value["priority"] == NONE:
        raise FeedbackError("an accepted requirement needs an explicit ordering priority")
    if value["action"] != "accept" and value["priority"] != NONE:
        raise FeedbackError("only an accepted requirement carries an ordering priority")

    authority = FEEDBACK.exact(value["authority"], {"kind", "reference", "quotation"}, "authority")
    if authority["kind"] not in AUTHORITY_KINDS:
        raise FeedbackError("authority.kind must be owner_instruction or prior_authorization")
    quotation = one_line(authority["quotation"], "authority.quotation")
    reference = one_line(authority["reference"], "authority.reference")
    # The command checks the shape of the supplied authority. It cannot
    # authenticate a person from free-form text, so the recorder must have
    # verified the real instruction before invoking this write.
    if quotation == NONE:
        raise FeedbackError("authority.quotation must quote the instruction this decision rests on")
    if authority["kind"] == "prior_authorization" and reference == NONE:
        raise FeedbackError("a prior authorization must reference the exact earlier decision it relies on")
    if reference != NONE:
        if any(character.isspace() for character in reference):
            raise FeedbackError("authority.reference must be a path or identifier without whitespace")
        if not ID_RE.fullmatch(reference):
            FEEDBACK.safe_repository_path(root, reference, "authority.reference")

    for field, keys in (
        ("implementation_evidence", {"status", "reference"}),
        ("downstream_verification", {"status", "reference"}),
    ):
        entry = FEEDBACK.exact(value[field], keys, field)
        if entry["status"] not in EVIDENCE_STATES:
            raise FeedbackError(f"{field}.status must be pending or recorded")
        entry_reference = one_line(entry["reference"], f"{field}.reference")
        # A recorded claim without a reference is an assertion. Unverified
        # closure stays visibly pending instead.
        if entry["status"] == "recorded" and entry_reference == NONE:
            raise FeedbackError(f"a recorded {field} needs an exact reference")
        if entry["status"] == "pending" and entry_reference != NONE:
            raise FeedbackError(f"a pending {field} carries no reference")
        if entry_reference != NONE:
            if any(character.isspace() for character in entry_reference):
                raise FeedbackError(f"{field}.reference must be a path or identifier without whitespace")
            FEEDBACK.safe_repository_path(root, entry_reference, f"{field}.reference")

    supersedes = value["supersedes"]
    if supersedes != NONE:
        identifier(supersedes, "supersedes")
        if supersedes == value["decision_id"]:
            raise FeedbackError("supersedes must not name the decision itself")
    return value, raw


def held_decisions(root: Path) -> tuple[list[tuple[str, dict[str, Any]]], int]:
    entries, skipped = COLLECT.held_entries(root, DECISION_ROOT, ID_RE)
    decisions: list[tuple[str, dict[str, Any]]] = []
    for decision_id, path in entries:
        value, _ = parse_decision(root, path)
        if value["decision_id"] != decision_id:
            raise FeedbackError(f"stored decision_id does not match its file name: {decision_id}")
        decisions.append((decision_id, value))
    return decisions, skipped


def held_candidate_bytes(root: Path) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map each held candidate id to its exact digest and its parsed content."""

    entries, _ = COLLECT.held_candidates(root)
    held: dict[str, tuple[str, dict[str, Any]]] = {}
    for candidate_id, path in entries:
        raw = FEEDBACK.read_regular(path, "held candidate")
        value, _ = COLLECT.parse_candidate_shape(root, path)
        held[candidate_id] = (digest(raw), value)
    return held


def verify_decision_candidate(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    """Bind a decision to the exact candidate revision it decides."""

    held = held_candidate_bytes(root)
    candidate_id = value["candidate_id"]
    if candidate_id not in held:
        raise FeedbackError("a decision must name a requirement candidate this repository holds")
    content_digest, candidate = held[candidate_id]
    if content_digest != value["candidate_digest"]:
        # A later revision of the same candidate is different bytes. Carrying an
        # earlier approval onto them would transfer a decision nobody made.
        raise FeedbackError(
            "candidate_digest does not match the held candidate bytes; "
            "a changed candidate revision needs its own explicit decision"
        )
    return candidate


def verify_supersession(value: dict[str, Any], existing: list[tuple[str, dict[str, Any]]]) -> None:
    """Keep one supersession inside the requirement it supersedes."""

    target = value["supersedes"]
    if target == NONE:
        return
    held = dict(existing)
    if target not in held:
        raise FeedbackError("supersedes names a decision that this repository does not hold")
    if held[target]["candidate_id"] != value["candidate_id"]:
        # Superseding across requirements would retire a decision about
        # something else, which nobody decided.
        raise FeedbackError(
            f"supersedes names decision {target}, which decides a different requirement; "
            "a supersession replaces an earlier decision about the same requirement"
        )


def decision_conflict(root: Path, value: dict[str, Any], existing: list[tuple[str, dict[str, Any]]]) -> None:
    superseded = {item["supersedes"] for _, item in existing if item["supersedes"] != NONE}
    superseded |= {value["supersedes"]} - {NONE}
    for decision_id, item in existing:
        if decision_id == value["decision_id"] or decision_id in superseded:
            continue
        if item["candidate_digest"] != value["candidate_digest"]:
            continue
        # Two live decisions about one requirement revision are two answers to
        # one question, even when they agree. The later one has to say which
        # earlier decision it replaces.
        raise FeedbackError(
            f"decision {decision_id} already decided this candidate revision as {item['action']}; "
            "record a decision that explicitly supersedes it"
        )


def decision_assessment(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    return {
        "decision": "record_decision",
        "decision_id": value["decision_id"],
        "checked_digest": digest(raw),
        "decision_path": str(DECISION_ROOT / f"{value['decision_id']}.json"),
        "candidate_id": value["candidate_id"],
        "action": value["action"],
        "priority": value["priority"],
        "authority_kind": value["authority"]["kind"],
        "implementation_evidence": value["implementation_evidence"]["status"],
        "downstream_verification": value["downstream_verification"]["status"],
    }


def command_example(args: argparse.Namespace) -> int:
    del args
    sys.stdout.write(
        json_text(
            {
                "schema_version": 1,
                "decision_id": "accept-publish-reports-worktree-removal",
                "candidate_id": "report-worktree-removal-in-publish-output",
                "candidate_digest": "sha256:" + "0" * 64,
                "action": "accept",
                "reason": "Two projects lost an afternoon to a stale checkout that publish claimed to have removed.",
                "priority": "medium",
                "authority": {
                    "kind": "owner_instruction",
                    "reference": NONE,
                    "quotation": "Adopt the publish output change; leave the rest deferred for now.",
                },
                "implementation_evidence": {"status": "pending", "reference": NONE},
                "downstream_verification": {"status": "pending", "reference": NONE},
                "supersedes": NONE,
            }
        )
    )
    return 0


def command_check_decision(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    value, raw = parse_decision(root, Path(args.decision))
    verify_decision_candidate(root, value)
    existing, _ = held_decisions(root)
    verify_supersession(value, existing)
    decision_conflict(root, value, existing)
    sys.stdout.write(json_text(decision_assessment(value, raw)))
    return 0


def command_record_decision(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    value, raw = parse_decision(root, Path(args.decision))
    verify_decision_candidate(root, value)
    existing, _ = held_decisions(root)
    result = decision_assessment(value, raw)
    if args.checked_digest != result["checked_digest"]:
        raise FeedbackError("checked digest does not match the supplied decision bytes")
    if len(existing) >= MAX_DECISIONS:
        raise FeedbackError("the decision history has reached its bounded size")
    verify_supersession(value, existing)

    relative = PurePosixPath(result["decision_path"])
    content = json_text(value)
    destination = FEEDBACK.safe_repository_path(root, str(relative), "decision_path")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise FeedbackError(f"refusing unsafe existing decision: {relative}")
        if destination.read_text(encoding="utf-8") == content:
            # Repeating one recorded decision changes nothing.
            result["outcome"] = "unchanged"
            sys.stdout.write(json_text(result))
            return 0
        raise FeedbackError(
            f"a decision already exists under this id with different bytes: {relative}; "
            "a changed decision is a new decision id that supersedes the earlier one"
        )
    decision_conflict(root, value, existing)

    FEEDBACK.require_task_binding(root, "recording an owner requirement decision")
    FEEDBACK.prepare_directory(root, relative.parent)
    FEEDBACK.atomic_write(root / relative, content)
    result["outcome"] = "written"
    sys.stdout.write(json_text(result))
    return 0


def current_decisions(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Separate decisions that still bind held candidate bytes from history."""

    decisions, skipped = held_decisions(root)
    held = held_candidate_bytes(root)
    superseded = {item["supersedes"] for _, item in decisions if item["supersedes"] != NONE}
    current: list[dict[str, Any]] = []
    historical: list[dict[str, Any]] = []
    for decision_id, value in decisions:
        entry = dict(value)
        candidate = held.get(value["candidate_id"])
        if decision_id in superseded:
            entry["state"] = "superseded by a later decision"
            historical.append(entry)
            continue
        if candidate is None:
            entry["state"] = "the decided candidate is no longer held"
            historical.append(entry)
            continue
        if candidate[0] != value["candidate_digest"]:
            # The candidate changed after the decision, so the decision stays in
            # history rather than silently applying to bytes nobody approved.
            entry["state"] = "the candidate changed after this decision"
            historical.append(entry)
            continue
        entry["state"] = "current"
        entry["candidate"] = candidate[1]
        current.append(entry)
    return current, historical, skipped


def priority_order(entry: dict[str, Any]) -> tuple[int, str]:
    return ({"high": 0, "medium": 1, "low": 2}[entry["priority"]], entry["decision_id"])


def candidate_lines(entry: dict[str, Any]) -> list[str]:
    """Render one adopted requirement, refusing any text that is not one line.

    Candidate prose is imported evidence. The collection command keeps it inert
    as stored data, and this rule keeps it inert as rendered text too.
    """

    candidate = entry["candidate"]
    sources = ", ".join(f"{item['project_alias']}/{item['report_id']}" for item in candidate["sources"])
    lines = [
        f"- {one_line(candidate['requested_behavior'], 'requested_behavior')}",
        f"  - priority: {entry['priority']}",
        f"  - reason: {one_line(entry['reason'], 'reason')}",
        f"  - requirement: {entry['candidate_id']} {entry['candidate_digest']}",
        f"  - sources: {sources}",
        f"  - applicability: {candidate['applicability']['certainty']}",
    ]
    for index, criterion in enumerate(candidate["completion_criteria"]):
        lines.append(f"  - done when: {one_line(criterion, f'completion_criteria[{index}]')}")
    for index, question in enumerate(candidate["pending_questions"]):
        lines.append(f"  - unresolved: {one_line(question, f'pending_questions[{index}]')}")
    for index, note in enumerate(candidate["disagreements"]):
        lines.append(f"  - disagreement: {one_line(note, f'disagreements[{index}]')}")
    lines.append(f"  - implementation: {evidence_line(entry['implementation_evidence'])}")
    lines.append(f"  - downstream verification: {evidence_line(entry['downstream_verification'])}")
    return lines


def unrenderable(identifier_text: str, exc: FeedbackError) -> list[str]:
    """Report a requirement that cannot be rendered without forging a line."""

    return [f"- {identifier_text} not rendered: {str(exc).splitlines()[0]}"]


def render_lines(root: Path) -> list[str]:
    current, historical, skipped = current_decisions(root)
    accepted = sorted((item for item in current if item["action"] == "accept"), key=priority_order)
    deferred = sorted((item for item in current if item["action"] == "defer"), key=lambda item: item["decision_id"])
    rejected = sorted((item for item in current if item["action"] == "reject"), key=lambda item: item["decision_id"])
    decided = {item["candidate_id"] for item in current}
    undecided = sorted(
        (value for candidate_id, (_, value) in held_candidate_bytes(root).items() if candidate_id not in decided),
        key=lambda value: value["candidate_id"],
    )

    lines = [
        "## Development Direction",
        "",
        "Every entry below rests on an explicit decision bound to the exact requirement bytes it decided.",
        "This section is generated. Edit the decisions, not these lines.",
        "",
        "### Adopted, in order",
        "",
    ]
    if not accepted:
        lines.append("None adopted yet.")
    for entry in accepted:
        try:
            lines += candidate_lines(entry)
        except FeedbackError as exc:
            lines += unrenderable(entry["candidate_id"], exc)

    for title, group in (("Deferred", deferred), ("Rejected", rejected)):
        lines += ["", f"### {title}", ""]
        if not group:
            lines.append("None.")
        for entry in group:
            try:
                lines.append(f"- {one_line(entry['candidate']['requested_behavior'], 'requested_behavior')}")
                lines.append(f"  - reason: {one_line(entry['reason'], 'reason')}")
                lines.append(f"  - requirement: {entry['candidate_id']} {entry['candidate_digest']}")
            except FeedbackError as exc:
                lines += unrenderable(entry["candidate_id"], exc)

    lines += ["", "### Suggested, not decided", ""]
    if not undecided:
        lines.append("None.")
    for candidate in undecided:
        try:
            behavior = one_line(candidate["requested_behavior"], "requested_behavior")
        except FeedbackError as exc:
            lines += unrenderable(candidate["candidate_id"], exc)
            continue
        lines.append(
            f"- {behavior} "
            f"(suggested priority {candidate['priority_suggestion']['level']}, no decision recorded)"
        )

    lines += ["", "### Historical decisions", ""]
    if not historical:
        lines.append("None.")
    for entry in sorted(historical, key=lambda item: item["decision_id"]):
        lines.append(f"- {entry['decision_id']} {entry['action']} {entry['candidate_id']}: {entry['state']}")
    if skipped:
        lines.append(f"- {skipped} stored entry(s) skipped: a non-conforming name is not listed")
    lines.append("")
    return lines


def evidence_line(entry: dict[str, Any]) -> str:
    if entry["status"] == "pending":
        return "pending"
    return f"recorded at {entry['reference']}"


def managed_document(existing: str | None, generated: list[str]) -> str:
    block = "\n".join([BEGIN_MARKER, *generated, END_MARKER])
    if existing is None:
        return "\n".join(["# Development Direction", "", block, ""])
    if existing.count(BEGIN_MARKER) != 1 or existing.count(END_MARKER) != 1:
        # Ambiguous markers make the managed region undecidable, so the command
        # refuses rather than guessing which prose is owned by whom.
        raise FeedbackError("the development direction must contain exactly one generated section")
    start = existing.index(BEGIN_MARKER)
    end = existing.index(END_MARKER)
    if end < start:
        raise FeedbackError("the generated section markers are out of order")
    return existing[:start] + block + existing[end + len(END_MARKER) :]


def command_render(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    destination = FEEDBACK.safe_repository_path(root, str(DIRECTION_PATH), "development direction")
    existing = None
    if destination.is_file():
        raw = FEEDBACK.read_regular(destination, "development direction")
        try:
            existing = raw.decode()
        except UnicodeDecodeError as exc:
            raise FeedbackError("the development direction must be UTF-8 text") from exc
    content = managed_document(existing, render_lines(root))
    if existing == content:
        sys.stdout.write(json_text({"decision": "render", "path": str(DIRECTION_PATH), "outcome": "unchanged"}))
        return 0
    if args.check:
        sys.stdout.write(json_text({"decision": "render", "path": str(DIRECTION_PATH), "outcome": "would_change"}))
        return 0
    FEEDBACK.require_task_binding(root, "rendering the development direction")
    FEEDBACK.prepare_directory(root, DIRECTION_PATH.parent)
    FEEDBACK.atomic_write(destination, content)
    sys.stdout.write(json_text({"decision": "render", "path": str(DIRECTION_PATH), "outcome": "written"}))
    return 0


def command_plan_input(args: argparse.Namespace) -> int:
    """Emit adopted requirement references without admitting any numbered plan."""

    root = FEEDBACK.resolve_root(args.root)
    current, _, _ = current_decisions(root)
    accepted = sorted((item for item in current if item["action"] == "accept"), key=priority_order)
    sys.stdout.write(
        json_text(
            {
                "decision": "plan_input",
                "requirements": [
                    {
                        "candidate_id": entry["candidate_id"],
                        "candidate_digest": entry["candidate_digest"],
                        "decision_id": entry["decision_id"],
                        "priority": entry["priority"],
                        "requested_behavior": entry["candidate"]["requested_behavior"],
                        "completion_criteria": entry["candidate"]["completion_criteria"],
                        "pending_questions": entry["candidate"]["pending_questions"],
                        "implementation_evidence": entry["implementation_evidence"]["status"],
                    }
                    for entry in accepted
                ],
                "boundary": (
                    "These are adopted requirements, not an admitted plan. "
                    "Numbered plan admission still needs bounded feasibility, an exact write scope, "
                    "completion witnesses and published plan bytes."
                ),
            }
        )
    )
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    root = FEEDBACK.resolve_root(args.root)
    current, historical, skipped = current_decisions(root)
    lines = ["# Requirement decisions", ""]
    if not current and not historical and not skipped:
        lines.append("None.")
    for entry in sorted(current, key=lambda item: item["decision_id"]):
        lines.append(
            f"- {entry['decision_id']} {entry['action']} {entry['candidate_id']} "
            f"priority={entry['priority']} authority={entry['authority']['kind']} "
            f"implementation={entry['implementation_evidence']['status']} "
            f"downstream={entry['downstream_verification']['status']}"
        )
    for entry in sorted(historical, key=lambda item: item["decision_id"]):
        lines.append(f"- {entry['decision_id']} {entry['action']} {entry['candidate_id']} historical: {entry['state']}")
    if skipped:
        lines.append(f"- {skipped} stored entry(s) skipped: a non-conforming name is not listed")
    lines += [
        "",
        "# Boundary",
        "",
        "A recorded decision is the owner's, and this command only checks the shape of the authority it was given.",
        "It authenticates nobody, and it admits no numbered plan.",
        "",
    ]
    sys.stdout.write("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("example", help="print a complete example decision")

    for name, help_text in (
        ("check-decision", "validate one decision against the held requirement candidate"),
        ("record-decision", "append one validated decision to the decision history"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--decision", required=True, help="path to the decision record")
        command.add_argument("--root", help="repository root (default the current directory)")
        if name == "record-decision":
            command.add_argument("--checked-digest", required=True, help="the digest reported by the preceding check")

    render = commands.add_parser("render", help="render the development direction from current decisions")
    render.add_argument("--check", action="store_true", help="report whether rendering would change the document")
    render.add_argument("--root", help="repository root (default the current directory)")

    for name, help_text in (
        ("plan-input", "print adopted requirement references for later plan authoring"),
        ("inspect", "print current and historical decisions"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--root", help="repository root (default the current directory)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "example": command_example,
        "check-decision": command_check_decision,
        "record-decision": command_record_decision,
        "render": command_render,
        "plan-input": command_plan_input,
        "inspect": command_inspect,
    }
    try:
        return handlers[args.command](args)
    except FeedbackError as exc:
        print(f"development direction failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
