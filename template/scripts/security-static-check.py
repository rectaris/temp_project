#!/usr/bin/env python3
"""Lightweight static security checks for generated repositories."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import security_rules


ROOT = Path.cwd()
SKIP_DIRS = {".git", "node_modules", "dist", "coverage", ".venv", ".uv-cache", ".uv-tools", ".uv-home"}
TEXT_SUFFIXES = {".sh", ".py", ".js", ".mjs", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".md", ".json"}
RULES = [
    (security_rules.PRIVATE_KEY_MATERIAL, "private key material"),
    (security_rules.REMOTE_SCRIPT_PIPE, "remote script piped to shell"),
    (security_rules.SUDO_COMMAND, "sudo command in repository script"),
    (re.compile(r"\bpull_request_target\b"), "pull_request_target workflow requires careful review"),
]


def iter_files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"}:
            out.append(path)
    return out


def main() -> int:
    findings: list[str] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, message in RULES:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {message}")
    if findings:
        print("static security check failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("static security check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
