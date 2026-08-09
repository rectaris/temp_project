#!/usr/bin/env python3
"""Validate plan manifest validation commands without invoking a shell."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile


class ValidationCommandError(ValueError):
    pass


SHELL_METACHARS = frozenset(";|&<>`$\\\n\r")
UNSUPPORTED_CHARS = frozenset("\"'~*?[]{}()")
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

PYTHON_SCRIPT_ARGUMENTS = {
    ".project-agent-workflow/scripts/check-external-service-policy.py": {("check",)},
    ".project-agent-workflow/scripts/check-codex-toml.py": {()},
    ".project-agent-workflow/scripts/lint-plan-docs.py": {()},
    ".project-agent-workflow/scripts/format-plan-docs.py": {("--check",)},
    ".project-agent-workflow/scripts/security-static-check.py": {(), ("--changed",), ("--managed",)},
    ".project-agent-workflow/scripts/structure-map.py": {("--check",)},
    ".project-agent-workflow/scripts/plan_validation_commands.py": {("--self-test",)},
}
VALIDATE_CHANGES_FLAGS = frozenset({"--all", "--staged", "--print-only", "--json"})
SHELL_SCRIPT_ARGUMENTS = {
    ".project-agent-workflow/scripts/lint-plan-docs.sh": {()},
    ".project-agent-workflow/scripts/format-plan-docs.sh": {("--check",)},
    ".project-agent-workflow/scripts/check-agent-completion.sh": {()},
}
DIRECT_SCRIPT_ARGUMENTS = {
    ".project-agent-workflow/scripts/lint-plan-docs.sh": {()},
    ".project-agent-workflow/scripts/format-plan-docs.sh": {("--check",)},
    ".project-agent-workflow/scripts/check-agent-completion.sh": {()},
}
NPM_VALIDATION_SCRIPTS = frozenset({"build", "test", "test:unit", "lint", "typecheck", "verify"})
PYTEST_PREFIXES = (("pytest",), ("python3", "-m", "pytest"), ("uv", "run", "pytest"))

# These are the bridgeable v0.5.0 managed CLI aliases that can remain in an open plan
# after pre-v1 adoption. They are accepted by plan lint only when the root
# script is the exact compatibility bridge installed by the adoption helper.
LEGACY_PYTHON_SCRIPT_ARGUMENTS = {
    "scripts/check-external-service-policy.py": {("check",)},
    "scripts/check-codex-toml.py": {()},
    "scripts/lint-plan-docs.py": {()},
    "scripts/format-plan-docs.py": {("--check",)},
    "scripts/security-static-check.py": {()},
    "scripts/structure-map.py": {("--check",)},
}
LEGACY_SHELL_SCRIPT_ARGUMENTS = {
    "scripts/lint-plan-docs.sh": {()},
    "scripts/format-plan-docs.sh": {("--check",)},
    "scripts/check-agent-completion.sh": {()},
}
LEGACY_DIRECT_SCRIPT_ARGUMENTS = {
    "scripts/lint-plan-docs.sh": {()},
    "scripts/format-plan-docs.sh": {("--check",)},
    "scripts/check-agent-completion.sh": {()},
}


@dataclass(frozen=True)
class ValidationCommand:
    raw: str
    argv: tuple[str, ...]


def extract_validation_commands(plan_path: Path) -> list[str]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    commands: list[str] = []
    in_validation = False
    for line in lines:
        if line.startswith("## "):
            break
        if line == "validation:":
            in_validation = True
            continue
        if in_validation:
            if line.startswith("  - "):
                commands.append(line[4:])
                continue
            if line and not line.startswith(" "):
                break
    if not commands:
        raise ValidationCommandError(f"validation list is empty in {plan_path}")
    return commands


def parse_validation_command(
    command: str,
    *,
    legacy_bridge_root: Path | None = None,
) -> ValidationCommand:
    if not command.strip():
        raise ValidationCommandError("validation command must not be empty")
    if command != command.strip():
        raise ValidationCommandError(f"validation command has surrounding whitespace: {command!r}")

    bad_shell = sorted({char for char in command if char in SHELL_METACHARS})
    if bad_shell:
        raise ValidationCommandError(
            f"shell metacharacter is not allowed in validation command: {''.join(bad_shell)!r}"
        )

    bad_unsupported = sorted({char for char in command if char in UNSUPPORTED_CHARS})
    if bad_unsupported:
        raise ValidationCommandError(
            f"unsupported character is not allowed in validation command: {''.join(bad_unsupported)!r}"
        )

    try:
        argv = tuple(shlex.split(command, posix=True))
    except ValueError as exc:
        raise ValidationCommandError(f"could not parse validation command: {exc}") from exc

    if not argv:
        raise ValidationCommandError("validation command must not be empty")
    if ENV_ASSIGNMENT_RE.match(argv[0]):
        raise ValidationCommandError("environment assignment is not allowed in validation command")

    validate_argv(argv, command, legacy_bridge_root=legacy_bridge_root)
    return ValidationCommand(raw=command, argv=argv)


def validate_argv(
    argv: tuple[str, ...],
    command: str,
    *,
    legacy_bridge_root: Path | None = None,
) -> None:
    if any(
        checker(argv)
        for checker in (
            is_git_diff_check,
            is_python_script_check,
            is_validate_changes,
            is_shell_script_check,
            is_direct_script_check,
            is_npm_script_check,
            is_script_syntax_check,
            is_python_compile,
            is_pytest_check,
        )
    ):
        return
    if legacy_bridge_root is not None and is_verified_legacy_bridge_check(argv, legacy_bridge_root):
        return
    raise ValidationCommandError(f"validation command is not allowlisted: {command}")


def has_allowed_suffix(
    argv: tuple[str, ...],
    prefix: tuple[str, ...],
    suffixes: set[tuple[str, ...]],
) -> bool:
    return argv[: len(prefix)] == prefix and argv[len(prefix) :] in suffixes


def is_git_diff_check(argv: tuple[str, ...]) -> bool:
    return has_allowed_suffix(argv, ("git", "diff"), {("--check",), ("--cached", "--check")})


def is_python_script_check(argv: tuple[str, ...]) -> bool:
    if len(argv) < 2 or argv[0] != "python3":
        return False
    script = argv[1]
    suffixes = PYTHON_SCRIPT_ARGUMENTS.get(script)
    return suffixes is not None and tuple(argv[2:]) in suffixes


def is_validate_changes(argv: tuple[str, ...]) -> bool:
    if argv[:2] != ("python3", ".project-agent-workflow/scripts/validate-changes.py"):
        return False
    flags = argv[2:]
    if len(flags) != len(set(flags)) or any(flag not in VALIDATE_CHANGES_FLAGS for flag in flags):
        return False
    return not ({"--all", "--staged"} <= set(flags))


def is_shell_script_check(argv: tuple[str, ...]) -> bool:
    if len(argv) < 2 or argv[0] != "sh":
        return False
    suffixes = SHELL_SCRIPT_ARGUMENTS.get(argv[1])
    return suffixes is not None and tuple(argv[2:]) in suffixes


def is_direct_script_check(argv: tuple[str, ...]) -> bool:
    suffixes = DIRECT_SCRIPT_ARGUMENTS.get(argv[0])
    return suffixes is not None and tuple(argv[1:]) in suffixes


def is_npm_script_check(argv: tuple[str, ...]) -> bool:
    return len(argv) == 3 and argv[:2] == ("npm", "run") and argv[2] in NPM_VALIDATION_SCRIPTS


def is_script_syntax_check(argv: tuple[str, ...]) -> bool:
    if len(argv) != 3 or argv[:2] not in {("sh", "-n"), ("bash", "-n")}:
        return False
    script = Path(argv[2])
    if script.is_absolute() or ".." in script.parts or script.suffix != ".sh":
        return False
    return (
        script.parts[0] in {"scripts", "tests"}
        or script.parts[:2] == ("template", "scripts")
        or script.parts[:2] == (".project-agent-workflow", "scripts")
    )


def is_python_compile(argv: tuple[str, ...]) -> bool:
    if len(argv) < 4 or argv[:3] != ("python3", "-m", "py_compile"):
        return False
    for raw_path in argv[3:]:
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            return False
        if (
            path.parts[0] not in {"scripts", "tests", ".codex"}
            and path.parts[:2] != ("template", "scripts")
            and path.parts[:2] not in {
                (".project-agent-workflow", "scripts"),
                (".project-agent-workflow", "hooks"),
            }
        ):
            return False
    return True


def is_pytest_check(argv: tuple[str, ...]) -> bool:
    prefix = next((candidate for candidate in PYTEST_PREFIXES if argv[: len(candidate)] == candidate), None)
    if prefix is None:
        return False
    paths = argv[len(prefix) :]
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "tests":
            return False
    return True


def python_bridge_content(script_name: str) -> str:
    return f'''#!/usr/bin/env python3
"""Compatibility bridge to Copier-managed workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path


managed = Path(__file__).resolve().parents[1] / ".project-agent-workflow/scripts/{script_name}"
os.execv(sys.executable, [sys.executable, str(managed), *sys.argv[1:]])
'''


def shell_bridge_content(script_name: str) -> str:
    return f'''#!/bin/sh
# Compatibility bridge to Copier-managed workflow.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$script_dir/../.project-agent-workflow/scripts/{script_name}" "$@"
'''


def legacy_bridge_script(argv: tuple[str, ...]) -> str | None:
    if len(argv) >= 2 and argv[0] == "python3":
        script = argv[1]
        suffixes = LEGACY_PYTHON_SCRIPT_ARGUMENTS.get(script)
        if suffixes is not None and tuple(argv[2:]) in suffixes:
            return script
        if script == "scripts/validate-changes.py":
            flags = argv[2:]
            if (
                len(flags) == len(set(flags))
                and all(flag in VALIDATE_CHANGES_FLAGS for flag in flags)
                and not ({"--all", "--staged"} <= set(flags))
            ):
                return script
        return None
    if len(argv) >= 2 and argv[0] == "sh":
        script = argv[1]
        suffixes = LEGACY_SHELL_SCRIPT_ARGUMENTS.get(script)
        if suffixes is not None and tuple(argv[2:]) in suffixes:
            return script
        return None
    script = argv[0]
    suffixes = LEGACY_DIRECT_SCRIPT_ARGUMENTS.get(script)
    if suffixes is not None and tuple(argv[1:]) in suffixes:
        return script
    return None


def is_verified_legacy_bridge_check(argv: tuple[str, ...], repository_root: Path) -> bool:
    script = legacy_bridge_script(argv)
    if script is None:
        return False
    manifest_path = (
        repository_root / ".project-agent-workflow-migration/v1-pre-namespace/manifest.json"
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    previous_ref = manifest.get("previous_ref")
    bridged = manifest.get("bridged_legacy_cli_paths")
    if not (
        manifest.get("operation") == "recopy_adoption"
        and isinstance(previous_ref, str)
        and re.fullmatch(r"v0\.[0-9]+\.[0-9]+", previous_ref)
        and isinstance(bridged, list)
        and script in bridged
    ):
        return False
    bridge = repository_root / script
    if bridge.is_symlink() or not bridge.is_file():
        return False
    managed = repository_root / ".project-agent-workflow/scripts" / bridge.name
    if managed.is_symlink() or not managed.is_file():
        return False
    expected = (
        python_bridge_content(bridge.name)
        if bridge.suffix == ".py"
        else shell_bridge_content(bridge.name)
    )
    try:
        return bool(
            stat.S_IMODE(bridge.stat().st_mode) == 0o755
            and managed.stat().st_mode & stat.S_IXUSR
            and bridge.read_text(encoding="utf-8") == expected
        )
    except (OSError, UnicodeDecodeError):
        return False


def parse_validation_commands(
    commands: list[str],
    *,
    legacy_bridge_root: Path | None = None,
) -> list[ValidationCommand]:
    return [
        parse_validation_command(command, legacy_bridge_root=legacy_bridge_root)
        for command in commands
    ]


def check_plan(path: Path) -> list[ValidationCommand]:
    return parse_validation_commands(extract_validation_commands(path))


def check_legacy_plan_for_lint(path: Path, repository_root: Path) -> list[ValidationCommand]:
    return parse_validation_commands(
        extract_validation_commands(path),
        legacy_bridge_root=repository_root,
    )


def run_plan(path: Path) -> None:
    active_directory = (Path.cwd() / "docs/plan/active").resolve()
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValidationCommandError(f"could not resolve active plan: {path}") from exc
    if resolved.parent != active_directory or not re.fullmatch(r"[0-9]{3}-.+\.md", resolved.name):
        raise ValidationCommandError(f"run-plan requires a numbered active plan path: {path}")
    for command in check_plan(path):
        print(f"+ {shlex.join(command.argv)}", flush=True)
        subprocess.run(command.argv, check=True)


def self_test() -> None:
    parse_validation_command("git diff --check")
    parse_validation_command("python3 -m py_compile .project-agent-workflow/scripts/example.py tests/example.py")
    parse_validation_command("python3 -m pytest")
    parse_validation_command("npm run typecheck")
    parse_validation_command("python3 .project-agent-workflow/scripts/check-external-service-policy.py check")
    parse_validation_command("sh -n .project-agent-workflow/scripts/example.sh")
    parse_validation_command(".project-agent-workflow/scripts/check-agent-completion.sh")
    for bad in (
        "git diff --check; rm -rf .",
        "FOO=1 pytest",
        "python3 - <<EOF",
        "npm run prepublish",
        "python3 -m pytest -q",
    ):
        try:
            parse_validation_command(bad)
        except ValidationCommandError:
            continue
        raise ValidationCommandError(f"self-test accepted unsafe command: {bad}")
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp) / "plan.md"
        plan.write_text(
            "# Plan title\n\nvalidation:\n  - git diff --check\n\n## Tasks\n\n- [ ] example\n",
            encoding="utf-8",
        )
        if [item.raw for item in check_plan(plan)] != ["git diff --check"]:
            raise ValidationCommandError("self-test did not parse validation after the plan title")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check-plan")
    check_parser.add_argument("plan_path", type=Path)

    run_parser = subparsers.add_parser("run-plan")
    run_parser.add_argument("plan_path", type=Path)

    commands_parser = subparsers.add_parser("check-commands")
    commands_parser.add_argument("commands", nargs="+")

    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.self_test:
            self_test()
        elif args.command == "check-plan":
            check_plan(args.plan_path)
        elif args.command == "run-plan":
            run_plan(args.plan_path)
        elif args.command == "check-commands":
            parse_validation_commands(args.commands)
        else:
            parser.print_help()
            return 2
    except ValidationCommandError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "Next: keep validation entries as single allowlisted commands, then rerun "
            "`python3 .project-agent-workflow/scripts/plan_validation_commands.py check-plan <plan>`.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
