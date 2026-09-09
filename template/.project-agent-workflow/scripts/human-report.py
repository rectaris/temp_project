#!/usr/bin/env python3
"""Assess and render ignored local reports and Git-tracked shared reports."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tempfile
from typing import Any, TextIO

import security_rules


CONFIG_PATH = Path(".project-agent-workflow/human-report.json")
OUTPUT_ROOT = Path(".agent-artifacts/human-reports")
SHARED_ROOT = Path("docs/human-report")
SHARED_SOURCE_NAME = "report.json"
SHARED_HTML_NAME = "index.html"
GENERATOR_VERSION = 1
CONFLICT_OPEN = "<<<<<<< "
CONFLICT_CLOSE = ">>>>>>> "
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


def load_config() -> dict[str, str]:
    raw = load_json(CONFIG_PATH)
    if not isinstance(raw, dict):
        raise ReportError("human report config must be an object")
    unknown = set(raw) - {"version", "mode", "shared_mode"}
    missing = {"version", "mode"} - set(raw)
    if unknown or missing:
        raise ReportError(
            f"human report config keys differ: missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    if raw["version"] != 1:
        raise ReportError("human report config version must equal 1")
    return {
        "mode": require_enum(raw["mode"], "human report config mode", {"agent_select_local", "disabled"}),
        "shared_mode": require_enum(
            raw.get("shared_mode", "disabled"),
            "human report config shared_mode",
            {"disabled", "explicit_publish"},
        ),
    }


def load_mode() -> str:
    return load_config()["mode"]


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
    report: dict[str, Any],
    assessment: dict[str, Any],
    sources: list[dict[str, str]],
    commit: str,
    provenance: dict[str, Any] | None = None,
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
    if provenance is None:
        provenance_meta = ""
        derivation = (
            "This local HTML view is derived. The repository sources listed below remain authoritative."
        )
    else:
        provenance_meta = (
            f"<li>Report id: <code>{escape(provenance['report_id'])}</code></li>"
            f"<li>Generator version: {escape(provenance['generator_version'])}</li>"
            f"<li>Generated at: <time datetime=\"{escape(provenance['generated_at'])}\">"
            f"{escape(provenance['generated_at'])}</time></li>"
        )
        derivation = (
            "This shared HTML view is derived from the reviewed structured source "
            f"<code>{escape((SHARED_ROOT / provenance['report_id'] / SHARED_SOURCE_NAME).as_posix())}</code>. "
            "The repository sources listed below remain authoritative, and the freshness validator "
            "fails once their recorded hashes no longer match the current repository bytes."
        )
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
      {provenance_meta}
    </ul>
    <p>{derivation}</p>
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


class HtmlSafetyParser(HTMLParser):
    """Collect the publication-relevant shape of a rendered report."""

    FORBIDDEN_TAGS = frozenset(
        {
            "applet",
            "audio",
            "base",
            "embed",
            "form",
            "frame",
            "frameset",
            "iframe",
            "img",
            "link",
            "meta_refresh",
            "object",
            "script",
            "source",
            "track",
            "video",
        }
    )
    REFERENCE_ATTRIBUTES = frozenset(
        {"action", "background", "cite", "data", "formaction", "href", "poster", "src", "srcset"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.failures: list[str] = []
        self.tags: set[str] = set()
        self.document_language = ""
        self.scoped_header_count = 0
        self.style_text: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        attributes = {name.lower(): (value or "") for name, value in attrs}
        if tag in self.FORBIDDEN_TAGS:
            self.failures.append(f"rendered HTML contains a forbidden <{tag}> element")
        if tag == "style":
            self._in_style = True
        if tag == "html":
            self.document_language = attributes.get("lang", "").strip()
        if tag == "th" and attributes.get("scope", "").strip():
            self.scoped_header_count += 1
        if tag == "meta" and attributes.get("http-equiv", "").strip().lower() == "refresh":
            self.failures.append("rendered HTML contains a meta refresh redirect")
        for name, value in attributes.items():
            if name.startswith("on"):
                self.failures.append(f"rendered HTML contains the event-handler attribute {name}")
            if name == "style" and "url(" in value.lower():
                self.failures.append("rendered HTML contains an inline style that loads a resource")
            if name in self.REFERENCE_ATTRIBUTES:
                self.failures.append(f"rendered HTML contains the external reference attribute {name}")

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.style_text.append(data)


def html_publication_failures(rendered: str) -> list[str]:
    parser = HtmlSafetyParser()
    parser.feed(rendered)
    parser.close()
    failures = list(parser.failures)
    style = "".join(parser.style_text)
    if "script" in parser.tags or "javascript:" in rendered.lower():
        failures.append("rendered HTML must not carry executable script")
    if not parser.document_language:
        failures.append("rendered HTML must declare a document language on the root element")
    if "h1" not in parser.tags:
        failures.append("rendered HTML must declare a top-level heading")
    if not parser.style_text:
        failures.append("rendered HTML must embed its own stylesheet")
    if parser.scoped_header_count < 1:
        failures.append("rendered HTML must mark row headers with a scope attribute")
    if "thead" not in parser.tags:
        failures.append("rendered HTML must declare table column headers")
    if "@media print" not in style:
        failures.append("rendered HTML must carry a print layout")
    if "url(" in style.lower() or "@import" in style.lower():
        failures.append("embedded stylesheet must not load an external resource")
    return sorted(set(failures))


def secret_failures(text: str, context: str) -> list[str]:
    return [f"{description} was detected in the {context}" for pattern, description in SECRET_PATTERNS if pattern.search(text)]


def conflict_failures(text: str, context: str) -> list[str]:
    lines = text.splitlines()
    opened = any(line.startswith(CONFLICT_OPEN) for line in lines)
    closed = any(line.startswith(CONFLICT_CLOSE) for line in lines)
    if opened and closed:
        return [f"an unresolved Git merge conflict marker is present in the {context}"]
    return []


def publication_failures(document: dict[str, Any], rendered: str) -> list[str]:
    report = document["report"]
    safety = report["content_safety"]
    failures: list[str] = []
    if not safety["reviewed"]:
        failures.append("content safety review is not recorded")
    if safety["contains_raw_logs"]:
        failures.append("raw logs are not accepted as shared report input")
    if safety["contains_unredacted_sensitive_data"]:
        failures.append("unredacted sensitive data is present")
    failures.extend(secret_failures(json_text(document), "structured source"))
    failures.extend(secret_failures(rendered, "rendered HTML"))
    failures.extend(html_publication_failures(rendered))
    return sorted(set(failures))


def shared_document(report_id: str, report: dict[str, Any], sources: list[dict[str, str]], root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_id": report_id,
        "generator_version": GENERATOR_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_commit": git_commit(root),
        "sources": sources,
        "report": report,
    }


def validate_shared_document(raw: Any) -> dict[str, Any]:
    document = require_object(
        raw,
        "shared report document",
        {
            "schema_version",
            "report_id",
            "generator_version",
            "generated_at",
            "source_commit",
            "sources",
            "report",
        },
    )
    if document["schema_version"] != 1:
        raise ReportError("shared report schema_version must equal 1")
    if document["generator_version"] != GENERATOR_VERSION:
        raise ReportError(f"shared report generator_version must equal {GENERATOR_VERSION}")
    report_id = require_string(document["report_id"], "shared report report_id")
    if not REPORT_ID_RE.fullmatch(report_id):
        raise ReportError("shared report report_id must use 1-64 lowercase letters, digits, or hyphens")
    generated_at = require_string(document["generated_at"], "shared report generated_at")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", generated_at):
        raise ReportError("shared report generated_at must be a UTC timestamp such as 2026-01-01T00:00:00Z")
    require_string(document["source_commit"], "shared report source_commit")
    sources = require_list(document["sources"], "shared report sources")
    if not sources:
        raise ReportError("shared report sources must record at least one repository file")
    for index, item in enumerate(sources):
        record = require_object(item, f"shared report sources[{index}]", {"path", "sha256"})
        require_string(record["path"], f"shared report sources[{index}].path")
        digest = require_string(record["sha256"], f"shared report sources[{index}].sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ReportError(f"shared report sources[{index}].sha256 must be a SHA-256 hex digest")
    document["report"] = validate_report(document["report"])
    if [item["path"] for item in document["sources"]] != list(document["report"]["sources"]):
        raise ReportError("shared report sources must match the report sources in order")
    return document


def render_shared_html(document: dict[str, Any]) -> str:
    assessment = assess(document["report"], "agent_select_local")
    return render_html(
        document["report"],
        assessment,
        document["sources"],
        document["source_commit"],
        {
            "report_id": document["report_id"],
            "generator_version": document["generator_version"],
            "generated_at": document["generated_at"],
        },
    )


def freshness_failures(document: dict[str, Any], root: Path) -> list[str]:
    failures: list[str] = []
    for record in document["sources"]:
        try:
            resolved = source_path(record["path"], root)
        except ReportError as exc:
            failures.append(f"recorded source is no longer publishable: {exc}")
            continue
        current = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if current != record["sha256"]:
            failures.append(
                f"recorded source {record['path']} changed: published {record['sha256']}, current {current}"
            )
    return failures


@contextmanager
def shared_directory_access(
    report_id: str, root: Path, *, create: bool
) -> Iterator[tuple[int, Callable[[], None], bool]]:
    """Retain no-follow directory descriptors through verification and publication."""
    if not REPORT_ID_RE.fullmatch(report_id):
        raise ReportError("report id must use 1-64 lowercase letters, digits, or hyphens")
    descriptors = []
    links = []
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(root, flags)
        descriptors.append(descriptor)
        links.append((None, root, os.fstat(descriptor)))
        created = False
        for part in (*SHARED_ROOT.parts, report_id):
            created = False
            if create:
                try:
                    os.mkdir(part, dir_fd=descriptor)
                    created = True
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=descriptor)
            descriptors.append(child)
            links.append((descriptor, part, os.fstat(child)))
            descriptor = child

        def check() -> None:
            for parent, name, original in links:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISDIR(current.st_mode) or (
                    current.st_dev, current.st_ino
                ) != (original.st_dev, original.st_ino):
                    raise ReportError("shared report directory changed during publication")

        check()
        yield descriptor, check, created
        check()
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def published_report_ids(root: Path) -> list[str]:
    shared_root = root / SHARED_ROOT
    if not shared_root.is_dir():
        return []
    return sorted(
        entry.name
        for entry in shared_root.iterdir()
        if entry.is_dir() and not entry.is_symlink() and REPORT_ID_RE.fullmatch(entry.name)
    )


def atomic_write(path: Path, content: str, *, directory_fd: int | None = None) -> None:
    if directory_fd is not None:
        try:
            existing = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and (not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1):
            raise ReportError(f"refusing unsafe output: {path.name}")
        temporary = f".{path.name}.{secrets.token_hex(16)}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(temporary, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        return
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


def command_publish(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    config = load_config()
    if config["shared_mode"] != "explicit_publish":
        print(
            "shared human report publication is disabled by project configuration "
            "(set human_report_shared_mode to explicit_publish)",
            file=sys.stderr,
        )
        return 4
    report = validate_report(load_json(Path(args.report)))
    sources = source_records(report, root)
    assessment = assess(report, "agent_select_local")
    if assessment["decision"] != "generate":
        print(json_text(assessment), file=sys.stderr, end="")
        return 3
    document = shared_document(args.report_id, report, sources, root)
    rendered = render_shared_html(document)
    failures = publication_failures(document, rendered)
    if failures:
        print("shared human report publication is blocked:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 4
    destination = root / SHARED_ROOT / args.report_id
    with (
        ExitStack() as handles,
        shared_directory_access(args.report_id, root, create=True) as (directory_fd, check, created),
    ):
        if not created and not args.supersede:
            print(
                f"shared human report already exists: {(SHARED_ROOT / args.report_id).as_posix()}; "
                "pass --supersede to replace it in an explicit supersede commit, or remove it in an explicit removal commit",
                file=sys.stderr,
            )
            return 4
        unchanged = False
        snapshots: dict[str, tuple[TextIO, os.stat_result]] = {}
        if not created:
            previous, existing_failures = stored_pair_integrity(
                args.report_id, root, directory_fd=directory_fd, snapshots=snapshots, handles=handles
            )
            if existing_failures:
                print("existing shared human report supersede is blocked:", file=sys.stderr)
                for failure in existing_failures:
                    print(f"- {failure}", file=sys.stderr)
                return 4
            assert previous is not None
            previous_without_time = {
                key: value for key, value in previous.items() if key != "generated_at"
            }
            document_without_time = {
                key: value for key, value in document.items() if key != "generated_at"
            }
            unchanged = json_text(document_without_time) == json_text(previous_without_time)
        check()
        for name, (handle, original) in snapshots.items():
            for current in (os.fstat(handle.fileno()), os.stat(name, dir_fd=directory_fd, follow_symlinks=False)):
                if any(getattr(current, field) != getattr(original, field) for field in (
                    "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"
                )):
                    raise ReportError("published file changed during supersede validation")
        if not unchanged:
            atomic_write(destination / SHARED_SOURCE_NAME, json_text(document), directory_fd=directory_fd)
            check()
            atomic_write(destination / SHARED_HTML_NAME, rendered, directory_fd=directory_fd)
    for name in (SHARED_SOURCE_NAME, SHARED_HTML_NAME):
        print((destination / name).relative_to(root).as_posix())
    print(
        "review, stage, and commit these files yourself; publication never stages or commits",
        file=sys.stderr,
    )
    return 0


def stored_pair_integrity(
    report_id: str,
    root: Path,
    *,
    directory_fd: int | None = None,
    snapshots: dict[str, tuple[TextIO, os.stat_result]] | None = None,
    handles: ExitStack | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if handles is None:
        with ExitStack() as opened:
            return stored_pair_integrity(report_id, root, directory_fd=directory_fd, snapshots=snapshots, handles=opened)
    if directory_fd is None:
        with shared_directory_access(report_id, root, create=False) as (descriptor, _check, _created):
            return stored_pair_integrity(report_id, root, directory_fd=descriptor, snapshots=snapshots, handles=handles)
    failures: list[str] = []
    texts: dict[str, str] = {}
    for name, context in ((SHARED_SOURCE_NAME, "structured source"), (SHARED_HTML_NAME, "rendered HTML")):
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            handle = handles.enter_context(os.fdopen(descriptor, "r", encoding="utf-8"))
            original = os.fstat(handle.fileno())
            if not stat.S_ISREG(original.st_mode) or original.st_nlink != 1:
                raise ReportError(f"missing published {context}: unsafe file type or links")
            texts[name] = handle.read()
            current = os.fstat(handle.fileno())
            if any(getattr(current, field) != getattr(original, field) for field in (
                "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"
            )):
                raise ReportError(f"published {context} changed while reading")
            if snapshots is not None:
                snapshots[name] = (handle, original)
        except (OSError, UnicodeError, ReportError) as exc:
            failures.append(f"missing published {context}: {exc}")
            continue
        failures.extend(conflict_failures(texts[name], f"published {context}"))
    if failures:
        return None, failures
    try:
        document = validate_shared_document(json.loads(texts[SHARED_SOURCE_NAME]))
    except (ReportError, json.JSONDecodeError) as exc:
        return None, [f"published structured source is invalid: {exc}"]
    if document["report_id"] != report_id:
        return None, [f"published structured source records report id {document['report_id']}, not {report_id}"]
    for record in document["sources"]:
        try:
            source_path(record["path"], root)
        except ReportError as exc:
            failures.append(f"recorded source is no longer publishable: {exc}")
    rendered = render_shared_html(document)
    if texts[SHARED_HTML_NAME] != rendered:
        failures.append("published HTML is not the deterministic rendering of its structured source")
    failures.extend(publication_failures(document, rendered))
    failures.extend(secret_failures(texts[SHARED_HTML_NAME], "published rendered HTML"))
    failures.extend(html_publication_failures(texts[SHARED_HTML_NAME]))
    return document, sorted(set(failures))


def verify_shared_report(report_id: str, root: Path) -> list[str]:
    document, failures = stored_pair_integrity(report_id, root)
    if document is not None:
        failures.extend(freshness_failures(document, root))
    return sorted(set(failures))


def command_verify_shared(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    report_ids = [args.report_id] if args.report_id else published_report_ids(root)
    if not report_ids:
        print(f"no shared human report is published below {SHARED_ROOT.as_posix()}")
        return 0
    stale = 0
    for report_id in report_ids:
        failures = verify_shared_report(report_id, root)
        if failures:
            stale += 1
            print(f"stale or blocked shared human report: {(SHARED_ROOT / report_id).as_posix()}", file=sys.stderr)
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            continue
        print(f"fresh shared human report: {(SHARED_ROOT / report_id).as_posix()}")
    return 4 if stale else 0


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
    publish_parser = commands.add_parser("publish", help="publish a shared report below docs/human-report")
    publish_parser.add_argument("report", help="path to the structured report JSON")
    publish_parser.add_argument("--report-id", required=True, help="lowercase stable identifier for the shared report")
    publish_parser.add_argument(
        "--supersede",
        action="store_true",
        help="replace an already published shared report in an explicit supersede commit",
    )
    publish_parser.set_defaults(handler=command_publish)
    verify_parser = commands.add_parser("verify-shared", help="check published shared reports against current sources")
    verify_parser.add_argument("--report-id", help="verify only this shared report instead of every published report")
    verify_parser.set_defaults(handler=command_verify_shared)
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
