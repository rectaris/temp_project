#!/usr/bin/env python3
"""Assess and render ignored local-only developer reports."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any

import security_rules


CONFIG_PATH = Path(".project-agent-workflow/human-report.json")
OUTPUT_ROOT = Path(".agent-artifacts/human-reports")
REPORT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
THRESHOLD = 3
MAX_ITEMS = 100
MAX_TEXT = 10_000
MAX_JSON_BYTES = 1_048_576
MAX_SOURCE_BYTES = 10_485_760
SECRET_PATTERNS = (
    (security_rules.PRIVATE_KEY_MATERIAL, "private key material"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "GitHub token-like material"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access-key-like material"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "API-key-like material"),
)


class ReportError(ValueError):
    """Raised when the report contract or output boundary is invalid."""


def require_object(value: Any, context: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{context} must be an object")
    unknown = set(value) - keys
    missing = keys - set(value)
    if unknown or missing:
        raise ReportError(f"{context} keys differ: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value


def require_string(value: Any, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ReportError(f"{context} must be a string")
    if "\x00" in value:
        raise ReportError(f"{context} must not contain NUL")
    if len(value) > MAX_TEXT:
        raise ReportError(f"{context} exceeds {MAX_TEXT} characters")
    if not allow_empty and not value.strip():
        raise ReportError(f"{context} must not be empty")
    return value


def require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise ReportError(f"{context} must be a boolean")
    return value


def require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReportError(f"{context} must be an array")
    if len(value) > MAX_ITEMS:
        raise ReportError(f"{context} exceeds {MAX_ITEMS} items")
    return value


def require_enum(value: Any, context: str, allowed: set[str]) -> str:
    text = require_string(value, context)
    if text not in allowed:
        raise ReportError(f"{context} must be one of {sorted(allowed)}")
    return text


def string_list(value: Any, context: str) -> list[str]:
    return [require_string(item, f"{context}[{index}]") for index, item in enumerate(require_list(value, context))]


def validate_report(raw: Any) -> dict[str, Any]:
    report = require_object(
        raw,
        "report",
        {
            "version",
            "title",
            "language",
            "audience",
            "purpose",
            "summary",
            "facts",
            "decisions",
            "relations",
            "risks",
            "next_actions",
            "presentation",
            "content_safety",
            "sources",
        },
    )
    if report["version"] != 1:
        raise ReportError("report.version must equal 1")
    require_string(report["title"], "report.title")
    language = require_string(report["language"], "report.language")
    if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", language):
        raise ReportError("report.language must be a BCP 47-like language tag")
    require_enum(report["audience"], "report.audience", {"developer"})
    require_enum(report["purpose"], "report.purpose", {"decision", "progress"})
    require_string(report["summary"], "report.summary")

    source_values = string_list(report["sources"], "report.sources")
    if not source_values:
        raise ReportError("report.sources must contain at least one repository-relative path")
    if len(set(source_values)) != len(source_values):
        raise ReportError("report.sources must not contain duplicates")

    facts = require_list(report["facts"], "report.facts")
    for index, item in enumerate(facts):
        fact = require_object(item, f"report.facts[{index}]", {"label", "value", "certainty", "source"})
        require_string(fact["label"], f"report.facts[{index}].label")
        require_string(fact["value"], f"report.facts[{index}].value")
        require_enum(
            fact["certainty"],
            f"report.facts[{index}].certainty",
            {"confirmed", "disputed", "inferred", "unknown"},
        )
        source = require_string(fact["source"], f"report.facts[{index}].source")
        if source not in source_values:
            raise ReportError(f"report.facts[{index}].source must appear in report.sources")

    decisions = require_list(report["decisions"], "report.decisions")
    for index, item in enumerate(decisions):
        decision = require_object(
            item,
            f"report.decisions[{index}]",
            {"question", "options", "recommendation", "reason"},
        )
        require_string(decision["question"], f"report.decisions[{index}].question")
        options = require_list(decision["options"], f"report.decisions[{index}].options")
        for option_index, raw_option in enumerate(options):
            option = require_object(
                raw_option,
                f"report.decisions[{index}].options[{option_index}]",
                {"label", "summary", "advantages", "disadvantages"},
            )
            require_string(option["label"], f"report.decisions[{index}].options[{option_index}].label")
            require_string(option["summary"], f"report.decisions[{index}].options[{option_index}].summary")
            string_list(option["advantages"], f"report.decisions[{index}].options[{option_index}].advantages")
            string_list(option["disadvantages"], f"report.decisions[{index}].options[{option_index}].disadvantages")
        require_string(decision["recommendation"], f"report.decisions[{index}].recommendation", allow_empty=True)
        require_string(decision["reason"], f"report.decisions[{index}].reason", allow_empty=True)

    relations = require_list(report["relations"], "report.relations")
    for index, item in enumerate(relations):
        relation = require_object(item, f"report.relations[{index}]", {"from", "to", "kind"})
        require_string(relation["from"], f"report.relations[{index}].from")
        require_string(relation["to"], f"report.relations[{index}].to")
        require_enum(
            relation["kind"],
            f"report.relations[{index}].kind",
            {"affects", "depends_on", "sequence"},
        )

    risks = require_list(report["risks"], "report.risks")
    for index, item in enumerate(risks):
        risk = require_object(item, f"report.risks[{index}]", {"description", "impact", "mitigation", "certainty"})
        require_string(risk["description"], f"report.risks[{index}].description")
        require_string(risk["impact"], f"report.risks[{index}].impact")
        require_string(risk["mitigation"], f"report.risks[{index}].mitigation")
        require_enum(
            risk["certainty"],
            f"report.risks[{index}].certainty",
            {"confirmed", "disputed", "inferred", "unknown"},
        )

    actions = require_list(report["next_actions"], "report.next_actions")
    for index, item in enumerate(actions):
        action = require_object(item, f"report.next_actions[{index}]", {"action", "owner", "status"})
        require_string(action["action"], f"report.next_actions[{index}].action")
        require_string(action["owner"], f"report.next_actions[{index}].owner")
        require_enum(action["status"], f"report.next_actions[{index}].status", {"blocked", "pending", "ready"})

    presentation = require_object(
        report["presentation"],
        "report.presentation",
        {"explicit_html", "needs_cross_comparison", "needs_filtering"},
    )
    for key in presentation:
        require_bool(presentation[key], f"report.presentation.{key}")

    safety = require_object(
        report["content_safety"],
        "report.content_safety",
        {"reviewed", "contains_raw_logs", "contains_unredacted_sensitive_data"},
    )
    for key in safety:
        require_bool(safety[key], f"report.content_safety.{key}")
    return report


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise ReportError(f"missing JSON file: {path}")
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            raise ReportError(f"JSON file exceeds {MAX_JSON_BYTES} bytes: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"could not read JSON file {path}: {exc}") from exc


def load_mode() -> str:
    config = require_object(load_json(CONFIG_PATH), "human report config", {"version", "mode"})
    if config["version"] != 1:
        raise ReportError("human report config version must equal 1")
    return require_enum(config["mode"], "human report config mode", {"agent_select_local", "disabled"})


def source_path(path_text: str, root: Path) -> Path:
    if "\\" in path_text:
        raise ReportError(f"source path must use forward slashes: {path_text}")
    pure = PurePosixPath(path_text)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ReportError(f"source path must stay repository-relative: {path_text}")
    if pure.parts[0] in {".agent-artifacts", ".agent-logs", ".git"}:
        raise ReportError(f"source path is outside the allowed evidence boundary: {path_text}")
    if any(part == ".env" or part.startswith(".env.") for part in pure.parts) or pure.suffix in {".key", ".pem"}:
        raise ReportError(f"source path looks secret-bearing and is not accepted: {path_text}")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ReportError(f"source path cannot be resolved: {path_text}") from exc
    if root not in resolved.parents or not resolved.is_file():
        raise ReportError(f"source path must resolve to a repository file: {path_text}")
    return resolved


def source_records(report: dict[str, Any], root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path_text in report["sources"]:
        resolved = source_path(path_text, root)
        if resolved.stat().st_size > MAX_SOURCE_BYTES:
            raise ReportError(f"source file exceeds {MAX_SOURCE_BYTES} bytes: {path_text}")
        records.append({"path": path_text, "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()})
    return records


def assess(report: dict[str, Any], mode: str) -> dict[str, Any]:
    max_options = max((len(item["options"]) for item in report["decisions"]), default=0)
    status_items = len(report["facts"]) + len(report["next_actions"])
    metrics = {
        "max_options_in_decision": max_options,
        "relation_count": len(report["relations"]),
        "status_item_count": status_items,
    }
    reasons: list[str] = []
    blocking: list[str] = []
    score = 0
    safety = report["content_safety"]
    if not safety["reviewed"]:
        blocking.append("content safety review is not recorded")
    if safety["contains_raw_logs"]:
        blocking.append("raw logs are not accepted as report input")
    if safety["contains_unredacted_sensitive_data"]:
        blocking.append("unredacted sensitive data is present")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for pattern, description in SECRET_PATTERNS:
        if pattern.search(serialized):
            blocking.append(f"{description} was detected")
    if mode == "disabled":
        return {
            "version": 1,
            "decision": "skip",
            "score": 0,
            "threshold": THRESHOLD,
            "reasons": ["human report generation is disabled by project configuration"],
            "blocking_reasons": [],
            "metrics": metrics,
        }
    if blocking:
        return {
            "version": 1,
            "decision": "blocked",
            "score": 0,
            "threshold": THRESHOLD,
            "reasons": [],
            "blocking_reasons": blocking,
            "metrics": metrics,
        }
    if max_options >= 3:
        score += 2
        reasons.append("a decision compares at least three options")
    if report["presentation"]["needs_cross_comparison"]:
        score += 2
        reasons.append("the report requires cross-field comparison")
    if len(report["relations"]) >= 3:
        score += 2
        reasons.append("the report contains at least three dependency, sequence, or impact relations")
    if status_items >= 8:
        score += 1
        reasons.append("the report contains at least eight status or action items")
    if report["presentation"]["needs_filtering"]:
        score += 2
        reasons.append("the report requires filtering or repeated scanning")
    explicit = report["presentation"]["explicit_html"]
    if explicit:
        reasons.insert(0, "HTML was explicitly requested")
    decision = "generate" if explicit or score >= THRESHOLD else "skip"
    if decision == "skip":
        reasons.append("the report does not meet the local HTML generation threshold")
    return {
        "version": 1,
        "decision": decision,
        "score": score,
        "threshold": THRESHOLD,
        "reasons": reasons,
        "blocking_reasons": [],
        "metrics": metrics,
    }


def git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unavailable"


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_list(items: list[str]) -> str:
    if not items:
        return '<p class="empty">None recorded.</p>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def render_html(
    report: dict[str, Any], assessment: dict[str, Any], sources: list[dict[str, str]], commit: str
) -> str:
    fact_rows = "".join(
        "<tr>"
        f'<td><span class="certainty {escape(item["certainty"])}">{escape(item["certainty"])}</span></td>'
        f'<th scope="row">{escape(item["label"])}</th>'
        f"<td>{escape(item['value'])}</td>"
        f"<td><code>{escape(item['source'])}</code></td>"
        "</tr>"
        for item in report["facts"]
    ) or '<tr><td colspan="4" class="empty">No facts recorded.</td></tr>'

    decision_blocks: list[str] = []
    for decision in report["decisions"]:
        option_blocks = []
        for option in decision["options"]:
            option_blocks.append(
                '<article class="option">'
                f"<h3>{escape(option['label'])}</h3>"
                f"<p>{escape(option['summary'])}</p>"
                "<h4>Advantages</h4>"
                f"{render_list(option['advantages'])}"
                "<h4>Disadvantages</h4>"
                f"{render_list(option['disadvantages'])}"
                "</article>"
            )
        recommendation = ""
        if decision["recommendation"] or decision["reason"]:
            recommendation = (
                '<div class="recommendation"><strong>Recommendation:</strong> '
                f"{escape(decision['recommendation'])}<br><strong>Reason:</strong> {escape(decision['reason'])}</div>"
            )
        decision_blocks.append(
            '<section class="decision">'
            f"<h2>{escape(decision['question'])}</h2>"
            f'<div class="option-grid">{"".join(option_blocks)}</div>'
            f"{recommendation}</section>"
        )
    decisions_html = "".join(decision_blocks) or '<p class="empty">No decisions recorded.</p>'

    relation_rows = "".join(
        f"<tr><td>{escape(item['from'])}</td><td>{escape(item['kind'])}</td><td>{escape(item['to'])}</td></tr>"
        for item in report["relations"]
    ) or '<tr><td colspan="3" class="empty">No relations recorded.</td></tr>'
    risk_rows = "".join(
        "<tr>"
        f'<td><span class="certainty {escape(item["certainty"])}">{escape(item["certainty"])}</span></td>'
        f"<td>{escape(item['description'])}</td><td>{escape(item['impact'])}</td><td>{escape(item['mitigation'])}</td>"
        "</tr>"
        for item in report["risks"]
    ) or '<tr><td colspan="4" class="empty">No risks recorded.</td></tr>'
    action_rows = "".join(
        f"<tr><td>{escape(item['status'])}</td><td>{escape(item['action'])}</td><td>{escape(item['owner'])}</td></tr>"
        for item in report["next_actions"]
    ) or '<tr><td colspan="3" class="empty">No next actions recorded.</td></tr>'
    source_rows = "".join(
        f"<tr><th scope=\"row\"><code>{escape(item['path'])}</code></th><td><code>{escape(item['sha256'])}</code></td></tr>"
        for item in sources
    )
    reason_items = render_list(assessment["reasons"])
    return f"""<!doctype html>
<html lang="{escape(report['language'])}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
  <title>{escape(report['title'])}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.5; }}
    body {{ margin: 0 auto; max-width: 1120px; padding: 2rem; }}
    header, section {{ margin-bottom: 2rem; }}
    .summary, .recommendation {{ border-left: .35rem solid #3973b9; padding: .8rem 1rem; background: color-mix(in srgb, Canvas 94%, #3973b9); }}
    .meta {{ display: flex; flex-wrap: wrap; gap: .75rem; padding: 0; list-style: none; }}
    .meta li, .certainty {{ border: 1px solid GrayText; border-radius: .35rem; padding: .15rem .45rem; }}
    .confirmed {{ border-color: #16803a; }} .inferred {{ border-color: #8a6300; }}
    .unknown {{ border-color: #646464; }} .disputed {{ border-color: #b3261e; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid GrayText; padding: .55rem; text-align: left; vertical-align: top; }}
    .option-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 1rem; }}
    .option {{ border: 1px solid GrayText; border-radius: .5rem; padding: 1rem; }}
    code {{ overflow-wrap: anywhere; }} .empty {{ color: GrayText; }}
    @media print {{ body {{ max-width: none; padding: 0; }} .option {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(report['title'])}</h1>
    <p class="summary">{escape(report['summary'])}</p>
    <ul class="meta">
      <li>Purpose: {escape(report['purpose'])}</li>
      <li>Git commit: <code>{escape(commit)}</code></li>
      <li>Assessment score: {escape(assessment['score'])}/{escape(assessment['threshold'])}</li>
    </ul>
    <p>This local HTML view is derived. The repository sources listed below remain authoritative.</p>
  </header>
  <main>
    <section><h2>Generation reasons</h2>{reason_items}</section>
    <section><h2>Facts and status</h2><table><thead><tr><th>Certainty</th><th>Item</th><th>Value</th><th>Source</th></tr></thead><tbody>{fact_rows}</tbody></table></section>
    <section><h2>Decisions</h2>{decisions_html}</section>
    <section><h2>Relations</h2><table><thead><tr><th>From</th><th>Relation</th><th>To</th></tr></thead><tbody>{relation_rows}</tbody></table></section>
    <section><h2>Risks</h2><table><thead><tr><th>Certainty</th><th>Risk</th><th>Impact</th><th>Mitigation</th></tr></thead><tbody>{risk_rows}</tbody></table></section>
    <section><h2>Next actions</h2><table><thead><tr><th>Status</th><th>Action</th><th>Owner</th></tr></thead><tbody>{action_rows}</tbody></table></section>
    <section><h2>Source provenance</h2><table><thead><tr><th>Repository path</th><th>SHA-256</th></tr></thead><tbody>{source_rows}</tbody></table></section>
  </main>
</body>
</html>
"""


def atomic_write(path: Path, content: str) -> None:
    if path.is_symlink():
        raise ReportError(f"refusing symlink output: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def output_directory(report_id: str, root: Path) -> Path:
    if not REPORT_ID_RE.fullmatch(report_id):
        raise ReportError("report id must use 1-64 lowercase letters, digits, or hyphens")
    artifact_root = root / ".agent-artifacts"
    artifact_root.mkdir(exist_ok=True)
    if artifact_root.is_symlink():
        raise ReportError("refusing symlink artifact root: .agent-artifacts")
    output_root = root / OUTPUT_ROOT
    output_root.mkdir(exist_ok=True)
    if output_root.is_symlink():
        raise ReportError(f"refusing symlink output root: {OUTPUT_ROOT}")
    if root not in output_root.resolve().parents:
        raise ReportError("local artifact root escaped the repository")
    destination = output_root / report_id
    destination.mkdir(exist_ok=True)
    if destination.is_symlink():
        raise ReportError(f"refusing symlink report directory: {destination.relative_to(root)}")
    if output_root.resolve() not in destination.resolve().parents:
        raise ReportError("report output escaped the local artifact root")
    return destination


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def command_example(args: argparse.Namespace) -> int:
    del args
    print(
        json_text(
            {
                "version": 1,
                "title": "Report title",
                "language": "en",
                "audience": "developer",
                "purpose": "progress",
                "summary": "Concrete outcome or decision needed.",
                "facts": [
                    {
                        "label": "Current state",
                        "value": "Describe the confirmed, inferred, unknown, or disputed fact.",
                        "certainty": "confirmed",
                        "source": "docs/plan/plan.md",
                    }
                ],
                "decisions": [],
                "relations": [],
                "risks": [],
                "next_actions": [],
                "presentation": {
                    "explicit_html": False,
                    "needs_cross_comparison": False,
                    "needs_filtering": False,
                },
                "content_safety": {
                    "reviewed": False,
                    "contains_raw_logs": False,
                    "contains_unredacted_sensitive_data": False,
                },
                "sources": ["docs/plan/plan.md"],
            }
        ),
        end="",
    )
    return 0


def command_assess(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    report = validate_report(load_json(Path(args.report)))
    source_records(report, root)
    print(json_text(assess(report, load_mode())), end="")
    return 0


def command_render(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    report = validate_report(load_json(Path(args.report)))
    sources = source_records(report, root)
    assessment = assess(report, load_mode())
    if assessment["decision"] != "generate":
        print(json_text(assessment), file=sys.stderr, end="")
        return 3
    destination = output_directory(args.report_id, root)
    rendered = render_html(report, assessment, sources, git_commit(root))
    atomic_write(destination / "assessment.json", json_text(assessment))
    atomic_write(destination / "index.html", rendered)
    print((destination / "index.html").relative_to(root).as_posix())
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    example_parser = commands.add_parser("example", help="print a complete example report contract")
    example_parser.set_defaults(handler=command_example)
    assess_parser = commands.add_parser("assess", help="validate and assess a structured human report")
    assess_parser.add_argument("report", help="path to the structured report JSON")
    assess_parser.set_defaults(handler=command_assess)
    render_parser = commands.add_parser("render", help="render an assessed report below .agent-artifacts")
    render_parser.add_argument("report", help="path to the structured report JSON")
    render_parser.add_argument("--report-id", required=True, help="lowercase stable identifier for the local output directory")
    render_parser.set_defaults(handler=command_render)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        return args.handler(args)
    except (OSError, ReportError) as exc:
        print(f"human report error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
