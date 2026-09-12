#!/usr/bin/env python3
"""Render a plan overview from the repository's lifecycle files."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

MAX_REQUESTED_IDS = 128
PLAN_ID_RE = re.compile(r"^([0-9]{3})-[a-z0-9][a-z0-9-]*\.md$")


class OverviewError(ValueError):
    """Raised for unsafe, ambiguous, or missing lifecycle overview inputs."""


_PLANLIB: ModuleType | None = None


def planlib_module() -> ModuleType:
    """Load the canonical plan library that sits beside this implementation.

    The overview is reached through two entrypoints and may be loaded from any
    working directory, so the library is resolved from this file's own
    directory rather than from the import path.
    """

    global _PLANLIB
    if _PLANLIB is not None:
        return _PLANLIB
    module_path = Path(__file__).resolve().with_name("planlib.py")
    if not module_path.is_file():
        raise OverviewError(f"canonical plan index parser is missing: {module_path}")
    spec = importlib.util.spec_from_file_location("plan_overview_planlib", module_path)
    if spec is None or spec.loader is None:
        raise OverviewError(f"canonical plan index parser is unloadable: {module_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise OverviewError(
            f"canonical plan index parser could not be loaded: {module_path}: {exc}"
        ) from exc
    sys.modules[spec.name] = module
    _PLANLIB = module
    return module


def markdown_escape(value: Any) -> str:
    """Escape a markdown table cell while preserving human-readable text."""

    text = "" if value is None else str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", " ")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def parse_requested_ids(raw_values: Iterable[str | int]) -> list[str]:
    ids: list[str] = []
    for raw in raw_values:
        if raw is None or raw == "":
            continue
        for piece in re.split(r"[\s,]+", str(raw).strip()):
            if piece:
                ids.append(piece)
    return ids


def normalize_repo_root(raw_root: str | None) -> Path:
    root = (Path.cwd() if raw_root in (None, "") else Path(raw_root)).resolve()
    if not root.exists():
        raise OverviewError(f"repository root does not exist: {raw_root or '.'}")
    if not root.is_dir():
        raise OverviewError(f"repository root is not a directory: {root}")
    return root


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - exercised by invalid-fixture tests.
        raise OverviewError(f"{path} is not valid UTF-8 text") from exc


def parse_manifest_status(path: Path) -> str:
    text = read_utf8(path)
    match = re.search(r"(?m)^status:\s*([A-Za-z0-9_]+)\s*$", text)
    if match is None:
        raise OverviewError(f"{path} is missing a status declaration")
    return match.group(1)


def parse_title(path: Path) -> str:
    text = read_utf8(path)
    match = re.search(r"(?m)^#\s*(.+?)\s*$", text)
    if match is None:
        return path.stem
    return match.group(1).strip()


def normalize_report_path(root: Path, relative_to: str | None) -> Path | None:
    if relative_to is None:
        return None
    candidate = Path(relative_to)
    if candidate.is_absolute():
        raise OverviewError(f"report path must be relative to the repository root: {relative_to}")
    if ".." in candidate.parts:
        raise OverviewError(f"report path cannot escape the repository root: {relative_to}")
    report_path = (root / candidate).resolve()
    try:
        report_path.relative_to(root)
    except ValueError as exc:
        raise OverviewError(f"report path must stay under the repository root: {relative_to}") from exc
    return report_path


def relative_markdown_link(root: Path, target_path: Path, report_path: Path | None) -> str:
    if report_path is None:
        return str(target_path.relative_to(root)).replace(os.sep, "/")
    relative = os.path.relpath(target_path, start=report_path.parent)
    return relative.replace(os.sep, "/")


def plan_id_from_path(path: Path) -> str | None:
    name = path.name
    match = PLAN_ID_RE.fullmatch(name)
    if match is None:
        return None
    return match.group(1)


def is_project_plan_path(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root)
    except ValueError:
        raise OverviewError(f"unsafe lifecycle path: {path}")
    relative_text = str(relative).replace(os.sep, "/")
    if relative_text.startswith("docs/plan/active/"):
        return bool(PLAN_ID_RE.fullmatch(path.name))
    if relative_text.startswith("docs/plan/backlog/"):
        return bool(PLAN_ID_RE.fullmatch(path.name))
    if relative_text.startswith("docs/plan/shelved/"):
        return bool(PLAN_ID_RE.fullmatch(path.name))
    if relative_text.startswith("docs/plan/checked/"):
        return bool(re.match(r"^docs/plan/checked/.+/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md$", relative_text))
    if relative_text.startswith("docs/plan/replanned/"):
        return bool(re.match(r"^docs/plan/replanned/.+/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md$", relative_text))
    return False


def iter_lifecycle_plan_files(root: Path) -> list[Path]:
    directories = [
        root / "docs/plan/active",
        root / "docs/plan/backlog",
        root / "docs/plan/shelved",
        root / "docs/plan/checked",
        root / "docs/plan/replanned",
    ]
    files: list[Path] = []
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md")):
            if not path.is_file():
                continue
            if path.name in {"README.md", "plan.md"}:
                continue
            if is_project_plan_path(path, root):
                files.append(path)
    return files


def parse_active_index(index_path: Path) -> list[dict[str, str]]:
    """Read one present active index through the canonical shared parser.

    A repository that has no active index at all stays supported and reports no
    active rows. Once the document exists, its whole text is judged by the same
    parser the enforcing lifecycle commands use, so a read-only overview can no
    longer report a malformed index as a successful empty result.
    """

    if not index_path.exists():
        return []
    planlib = planlib_module()
    try:
        rows = planlib.parse_active_index(planlib.read_active_index(index_path))
    except planlib.ActiveIndexError as exc:
        raise OverviewError(f"{index_path}: {exc}") from exc
    return [{"id": plan_id, "path": path, "status": status} for plan_id, path, status in rows]


def build_rows_by_id(root: Path) -> dict[str, list[Path]]:
    rows_by_id: dict[str, list[Path]] = {}
    for path in iter_lifecycle_plan_files(root):
        plan_id = plan_id_from_path(path)
        if plan_id is None:
            continue
        rows_by_id.setdefault(plan_id, []).append(path)
    for row in parse_active_index(root / "docs/plan/plan.md"):
        plan_id = row["id"]
        target = (root / row["path"]).resolve(strict=False)
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise OverviewError(f"active index row escapes the repository root: {row['path']}") from exc
        if not target.exists():
            raise OverviewError(f"active index references a missing file for {plan_id}: {row['path']}")
        if not target.is_file():
            raise OverviewError(f"active index path is not a file for {plan_id}: {row['path']}")
        if plan_id_from_path(target) != plan_id:
            raise OverviewError(f"active index row id does not match its file name: {row['path']}")
        file_status = parse_manifest_status(target)
        if file_status != row["status"]:
            raise OverviewError(
                f"active index status disagreement for {plan_id}: index says {row['status']}, file says {file_status}"
            )
        rows_by_id.setdefault(plan_id, []).append(target)
    return rows_by_id


def make_row(root: Path, path: Path, report_path: Path | None) -> dict[str, str]:
    plan_id = plan_id_from_path(path)
    if plan_id is None:
        raise OverviewError(f"unsupported lifecycle path: {path}")
    relative_path = str(path.resolve().relative_to(root)).replace(os.sep, "/")
    status = parse_manifest_status(path)
    title = parse_title(path)
    return {
        "id": plan_id,
        "status": status,
        "path": relative_path,
        "title": title,
        "link": relative_markdown_link(root, path.resolve(), report_path),
    }


def resolve_rows(root: Path, requested_ids: list[str], report_path: Path | None) -> list[dict[str, str]]:
    if len(requested_ids) > MAX_REQUESTED_IDS:
        raise OverviewError(f"at most {MAX_REQUESTED_IDS} plan ids can be resolved per report")
    if len(requested_ids) != len(set(requested_ids)):
        raise OverviewError(f"duplicate plan ids are not allowed: {requested_ids}")

    rows_by_id = build_rows_by_id(root)

    if not requested_ids:
        backlog_paths: list[Path] = []
        backlog_dir = root / "docs/plan/backlog"
        if backlog_dir.exists():
            for path in sorted(backlog_dir.rglob("*.md")):
                if path.is_file() and plan_id_from_path(path) is not None:
                    backlog_paths.append(path)
        return [make_row(root, item, report_path) for item in backlog_paths]

    resolved: list[dict[str, str]] = []
    for plan_id in requested_ids:
        candidates = rows_by_id.get(plan_id, [])
        if not candidates:
            raise OverviewError(f"request for plan id {plan_id} did not resolve to any lifecycle document")
        unique_candidates: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            rel = str(candidate.resolve().relative_to(root)).replace(os.sep, "/")
            if rel in seen:
                continue
            seen.add(rel)
            unique_candidates.append(candidate)
        if len(unique_candidates) > 1:
            details = ", ".join(
                str(candidate.resolve().relative_to(root)).replace(os.sep, "/")
                for candidate in sorted(unique_candidates)
            )
            raise OverviewError(f"plan id {plan_id} resolves to multiple lifecycle records: {details}")
        resolved.append(make_row(root, unique_candidates[0], report_path))
    return resolved


def render_markdown(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "| id | status | title | path |\n| --- | --- | --- | --- |\n"
    lines = ["| id | status | title | path |", "| --- | --- | --- | --- |"]
    for row in rows:
        line = (
            f"| [{markdown_escape(row['id'])}]({markdown_escape(row['link'])}) "
            f"| {markdown_escape(row['status'])} "
            f"| {markdown_escape(row['title'])} "
            f"| {markdown_escape(row['path'])} |"
        )
        lines.append(line)
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to inspect; defaults to the current directory.")
    parser.add_argument("--relative-to", dest="relative_to", help="Report path used to resolve markdown links.")
    parser.add_argument("--report-path", dest="relative_to", help=argparse.SUPPRESS)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="Report format.")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON instead of markdown.")
    parser.add_argument("--id", dest="id_values", action="append", default=[], help="Plan id to resolve; repeatable.")
    parser.add_argument("--ids", nargs="*", action="append", default=[], help="Comma- or whitespace-separated plan ids.")
    parser.add_argument("plans", nargs="*", help="Plan ids to resolve as positional arguments.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = normalize_repo_root(args.root)
        explicit_values = [
            *args.id_values,
            *[item for group in args.ids for item in group],
            *args.plans,
        ]
        provided_ids = bool(args.id_values or args.ids or args.plans)
        requested_ids = parse_requested_ids(explicit_values)

        if args.json_output:
            output_format = "json"
        else:
            output_format = args.format

        if output_format == "markdown" and args.relative_to is None:
            raise OverviewError("--relative-to is required when rendering markdown output")

        report_path = normalize_report_path(root, args.relative_to)
        if provided_ids:
            rows = resolve_rows(root, requested_ids, report_path)
        else:
            rows = resolve_rows(root, [], report_path)

        if output_format == "json":
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(render_markdown(rows), end="")
        return 0
    except OverviewError as exc:
        print(f"plan overview failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
