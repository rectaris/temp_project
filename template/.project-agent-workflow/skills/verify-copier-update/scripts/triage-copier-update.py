#!/usr/bin/env python3
"""Resolve one verify-copier-update manifest into a single owner and next action.

The verifier decides whether a template ref can be adopted. This command decides
what the reporting agent does about that answer, so the decision comes from the
committed triage table rather than from prose judgment.

Exit status:
  0  the manifest resolved and the verification passed
  1  the manifest resolved and the verification did not pass
  2  the manifest could not be resolved
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TRIAGE_NAME = "update-triage.yaml"
SCHEMA_VERSION = 1
RESULTS = ("verified", "rejected", "blocked")
OWNERS = ("none", "invocation", "environment", "project", "template", "undetermined")
RETRIES = ("after_fix", "never")


class TriageError(Exception):
    """One bounded failure that leaves the manifest unresolved."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        return parse_triage_without_yaml(path)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TriageError(f"triage table is unavailable: {exc}") from exc
    except yaml.YAMLError as exc:
        raise TriageError(f"triage table is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise TriageError("triage table must be a mapping")
    return loaded


def parse_triage_without_yaml(path: Path) -> dict[str, Any]:
    """Read the bounded subset of YAML this table uses.

    The skill must resolve a manifest on a downstream machine that installs no
    Python packages, so the reader accepts exactly the shapes the table declares:
    two nesting levels of mappings, one plain scalar per leaf, folded ``>-``
    blocks, and one list of plain scalars. Any other YAML syntax is refused rather
    than read differently from the library, so the two readers can never disagree
    about a committed instruction.
    """

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TriageError(f"triage table is unavailable: {exc}") from exc

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending: tuple[dict[str, Any], str] | None = None
    folded: list[str] = []
    folded_indent = 0

    for number, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if pending is not None:
            if stripped and indent > folded_indent:
                require_plain_scalar(stripped, number)
                folded.append(stripped)
                continue
            container, key = pending
            container[key] = " ".join(folded)
            pending = None
            folded = []
        if not stripped or stripped.startswith("#"):
            continue
        if raw.lstrip(" ") != raw.lstrip():
            raise TriageError(f"triage table line {number} is indented with something other than spaces")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise TriageError(f"triage table line {number} is indented below the document")
        container = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(container, list):
                raise TriageError(f"triage table line {number} has an unexpected list entry")
            value = stripped[2:].strip()
            require_plain_scalar(value, number)
            container.append(value)
            continue
        if ":" not in stripped:
            raise TriageError(f"triage table line {number} is not a mapping entry")
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not isinstance(container, dict):
            raise TriageError(f"triage table line {number} has an unexpected mapping entry")
        if key in container:
            raise TriageError(f"triage table line {number} repeats the key {key!r}")
        if value == ">-":
            pending = (container, key)
            folded_indent = indent
            continue
        if value == "":
            child: Any = [] if peek_is_list(lines, number) else {}
            container[key] = child
            stack.append((indent, child))
            continue
        require_plain_scalar(value, number)
        container[key] = int(value) if value.isdigit() else value

    if pending is not None:
        container, key = pending
        container[key] = " ".join(folded)
    return root


# YAML syntax whose meaning this reader does not reproduce. A scalar that opens
# with one of these, or that carries an inline comment, is refused so a machine
# without the YAML library never reads a different instruction than one with it.
UNSUPPORTED_SCALAR_OPENERS = ("\"", "'", "&", "*", "!", "|", ">", "{", "[", "?", "%", "@", "`")


def require_plain_scalar(value: str, number: int) -> None:
    if not value:
        return
    if value.startswith(UNSUPPORTED_SCALAR_OPENERS):
        raise TriageError(
            f"triage table line {number} uses YAML scalar syntax this reader does not support"
        )
    if " #" in value:
        raise TriageError(f"triage table line {number} carries an inline comment")


def peek_is_list(lines: list[str], number: int) -> bool:
    for raw in lines[number:]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped.startswith("- ")
    return False


def require_table(path: Path) -> dict[str, Any]:
    table = load_yaml(path)
    if table.get("schema_version") != SCHEMA_VERSION:
        raise TriageError(f"triage table must declare schema_version {SCHEMA_VERSION}")
    for section in ("results", "codes", "suffixes"):
        if not isinstance(table.get(section), dict) or not table[section]:
            raise TriageError(f"triage table must declare a non-empty {section} mapping")
    if not isinstance(table.get("subjects"), list) or not table["subjects"]:
        raise TriageError("triage table must declare a non-empty subjects list")
    for result in RESULTS:
        if result not in table["results"]:
            raise TriageError(f"triage table must describe the {result} result")
    for section in ("codes", "suffixes"):
        for name, entry in table[section].items():
            require_entry(section, name, entry)
    return table


def require_entry(section: str, name: str, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise TriageError(f"{section} entry {name} must be a mapping")
    owner = entry.get("owner")
    if owner not in OWNERS:
        raise TriageError(f"{section} entry {name} declares an unknown owner: {owner!r}")
    if entry.get("retry") not in RETRIES:
        raise TriageError(f"{section} entry {name} declares an unknown retry: {entry.get('retry')!r}")
    action = entry.get("next_action")
    if not isinstance(action, str) or not action.strip():
        raise TriageError(f"{section} entry {name} must declare a non-empty next_action")


def resolve_code(table: dict[str, Any], code: str) -> dict[str, Any]:
    if code in table["codes"]:
        return {"match": "code", "matched": code, **table["codes"][code]}
    subjects = sorted((str(subject) for subject in table["subjects"]), key=len, reverse=True)
    for subject in subjects:
        prefix = f"{subject}_"
        if code.startswith(prefix):
            suffix = code[len(prefix) :]
            if suffix in table["suffixes"]:
                return {
                    "match": "subject_suffix",
                    "matched": suffix,
                    "subject": subject,
                    **table["suffixes"][suffix],
                }
    raise TriageError(
        f"reason code is not classified: {code}. Report it upstream so the triage "
        "table gains an entry; do not guess an owner."
    )


def require_manifest(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TriageError(f"verification manifest is unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TriageError(f"verification manifest is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise TriageError("verification manifest must be a JSON object")
    result = loaded.get("result")
    if result not in RESULTS:
        raise TriageError(f"verification manifest declares an unknown result: {result!r}")
    code = loaded.get("reason_code")
    if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]+", code):
        raise TriageError(f"verification manifest declares an unusable reason code: {code!r}")
    return loaded


def build_report(table: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    result = str(manifest["result"])
    code = str(manifest["reason_code"])
    entry = resolve_code(table, code)
    if result == "verified" and entry["owner"] != "none":
        raise TriageError(
            f"verification manifest reports {result} with reason code {code}, which the "
            "triage table assigns an owner; the manifest and the table disagree"
        )
    if result != "verified" and entry["owner"] == "none":
        raise TriageError(
            f"verification manifest reports {result} with reason code {code}, which the "
            "triage table records as a passing code; the manifest and the table disagree"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "result": result,
        "reason_code": code,
        "owner": entry["owner"],
        "retry": entry["retry"],
        "match": entry["match"],
        "matched": entry["matched"],
        "subject": entry.get("subject"),
        "result_action": str(table["results"][result]["next_action"]).strip(),
        "next_action": str(entry["next_action"]).strip(),
        "detail": manifest.get("detail"),
        "unresolved": manifest.get("unresolved", []),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"result: {report['result']}",
        f"reason_code: {report['reason_code']}",
        f"owner: {report['owner']}",
        f"retry: {report['retry']}",
    ]
    if report.get("subject"):
        lines.append(f"subject: {report['subject']}")
    lines.append(f"result_action: {report['result_action']}")
    lines.append(f"next_action: {report['next_action']}")
    if report.get("detail"):
        lines.append(f"detail: {report['detail']}")
    for item in report.get("unresolved") or []:
        lines.append(f"unresolved: {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path, help="path to verification-manifest.json")
    parser.add_argument(
        "--triage-table",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / TRIAGE_NAME,
        help="path to the triage table",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        table = require_table(args.triage_table)
        manifest = require_manifest(args.manifest)
        report = build_report(table, manifest)
    except TriageError as exc:
        print(f"triage failed: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0 if report["result"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
