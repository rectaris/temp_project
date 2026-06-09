#!/usr/bin/env python3
"""Lightweight static security checks for generated repositories."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path.cwd()
SKIP_DIRS = {".git", "node_modules", "dist", "coverage", ".venv", ".uv-cache", ".uv-tools", ".uv-home"}
TEXT_SUFFIXES = {".sh", ".py", ".js", ".mjs", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".md", ".json"}
RULES = [
    (re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"), "private key material"),
    (re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sh|bash|zsh)\b"), "remote script piped to shell"),
    (re.compile(r"^\s*sudo\b", re.MULTILINE), "sudo command in repository script"),
    (re.compile(r"\bpull_request_target\b"), "pull_request_target workflow requires careful review"),
]


def iter_files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
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
