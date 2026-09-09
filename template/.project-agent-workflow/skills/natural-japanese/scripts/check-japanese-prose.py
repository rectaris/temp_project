#!/usr/bin/env python3
"""Report bounded advisory findings for Japanese prose without rewriting it."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MAX_BYTES = 1024 * 1024
EMPTY_PHRASES = (
    "重要なのは",
    "ここでは見ていく",
    "正面から扱う",
    "多角的に分析する",
    "包括的に",
    "深掘りする",
    "言語化する",
)
CONNECTORS = ("さらに", "また", "加えて")
CONTRAST_PATTERNS = ("ではなく", "だけでなく")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？])")


def markdown_indentation(line: str) -> tuple[int, str]:
    columns = 0
    index = 0
    while index < len(line) and line[index] in {" ", "\t"}:
        columns = (
            columns + 1
            if line[index] == " "
            else columns + (4 - columns % 4)
        )
        index += 1
    return columns, line[index:]


def visible_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fence_character = ""
    fence_length = 0
    for number, line in enumerate(text.splitlines(), start=1):
        indentation, content = markdown_indentation(line)
        if fence_character:
            closing = (
                re.fullmatch(
                    rf"{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                    content,
                )
                if indentation < 4
                else None
            )
            if closing is not None:
                fence_character = ""
                fence_length = 0
            continue
        if indentation >= 4:
            continue
        opening = re.match(r"^(`{3,}|~{3,})(.*)$", content)
        if opening is not None:
            marker = opening.group(1)
            if marker[0] == "`" and "`" in opening.group(2):
                lines.append((number, line))
                continue
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        lines.append((number, line))
    return lines


def finding(rule: str, line: int, message: str, excerpt: str) -> dict[str, object]:
    return {
        "rule": rule,
        "line": line,
        "message": message,
        "excerpt": excerpt[:160],
        "advisory": True,
    }


def inspect(text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    lines = visible_lines(text)
    visible = "\n".join(line for _, line in lines)

    for number, line in lines:
        for phrase in EMPTY_PHRASES:
            if phrase in line:
                findings.append(
                    finding(
                        "empty-phrase",
                        number,
                        f"`{phrase}` が具体的な情報を加えているか確認してください。",
                        line.strip(),
                    )
                )
        for sentence in SENTENCE_SPLIT.split(line):
            stripped = sentence.strip()
            if len(stripped) > 120:
                findings.append(
                    finding(
                        "reading-load",
                        number,
                        "一文が長いため、事実関係を保ったまま分割できるか確認してください。",
                        stripped,
                    )
                )

    for connector in CONNECTORS:
        count = visible.count(connector)
        if count >= 3:
            findings.append(
                finding(
                    "repeated-connector",
                    0,
                    f"`{connector}` が {count} 回あります。論理関係に必要か確認してください。",
                    connector,
                )
            )

    contrast_count = sum(visible.count(pattern) for pattern in CONTRAST_PATTERNS)
    if contrast_count >= 3:
        findings.append(
            finding(
                "repeated-contrast",
                0,
                f"否定から肯定へ転じる構文が {contrast_count} 回あります。必要な対比だけか確認してください。",
                " / ".join(CONTRAST_PATTERNS),
            )
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    try:
        raw = args.path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError(f"input exceeds {MAX_BYTES} bytes")
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"Japanese prose check failed: {exc}", file=sys.stderr)
        return 1

    findings = inspect(text)
    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "path": args.path.as_posix(),
                    "advisory": True,
                    "modified": False,
                    "finding_count": len(findings),
                    "findings": findings,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        for item in findings:
            location = f"line {item['line']}" if item["line"] else "document"
            print(f"{location}: {item['rule']}: {item['message']}")
        print(f"{len(findings)} advisory finding(s); no text was changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
