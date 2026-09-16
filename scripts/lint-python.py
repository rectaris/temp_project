#!/usr/bin/env python3
"""Run pinned Python correctness checks, with explicitly bounded safe fixes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import sysconfig
import tomllib


RUFF_VERSION = "0.15.7"
RULES = ["E9", "F541", "F631", "F634", "F821", "F822", "F823"]
EXCLUDED_DIRECTORIES = {
    ".git", ".venv", ".uv-cache", ".ruff_cache", "__pycache__", "node_modules",
}


class LintError(ValueError):
    pass


def layout() -> tuple[Path, Path, tuple[str, ...]]:
    workflow = Path(__file__).resolve().parents[1]
    if (workflow / "scripts/project_workflow/worktree_guard.py").is_file():
        return workflow, workflow, (
            "scripts", "tests", "template/.project-agent-workflow/scripts",
        )
    if (
        workflow.name == ".project-agent-workflow"
        and (workflow / "scripts/worktree_guard.py").is_file()
    ):
        return workflow.parent, workflow, (".project-agent-workflow/scripts",)
    raise LintError("unrecognized root or managed Python lint distribution")


def regular_path(root: Path, relative: str, *, directory: bool = False) -> Path:
    path = PurePosixPath(relative)
    if (
        not relative or path.is_absolute() or path.as_posix() != relative
        or ".." in path.parts or "\\" in relative
    ):
        raise LintError(f"expected a normalized repository-relative path: {relative!r}")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise LintError(f"symlink is not a lint target: {relative}")
    if not (target.is_dir() if directory else target.is_file()):
        raise LintError(f"missing or non-regular lint path: {relative}")
    return target


def read_configuration(root: Path, workflow: Path) -> Path:
    relative = (workflow / "tools/python-quality/ruff.toml").relative_to(root).as_posix()
    config = regular_path(root, relative)
    expected = {
        "required-version": f"=={RUFF_VERSION}",
        "preview": False,
        "respect-gitignore": False,
        "force-exclude": False,
        "lint": {"select": RULES, "ignore": [], "fixable": ["F541"], "unfixable": []},
    }
    with config.open("rb") as stream:
        actual = tomllib.load(stream)
    if actual != expected:
        raise LintError("managed Ruff configuration differs from the pinned rule/fix policy")
    requirements = regular_path(
        root,
        (workflow / "tools/python-quality/requirements.txt").relative_to(root).as_posix(),
    )
    if requirements.read_text(encoding="utf-8") != f"ruff=={RUFF_VERSION}\n":
        raise LintError("managed Ruff requirement differs from the pinned version")
    return config


def ruff_environment() -> dict[str, str]:
    return {
        key: value for key, value in os.environ.items() if not key.startswith("RUFF_")
    }


def ruff_executable() -> Path:
    """Resolve the pinned Ruff installed in this interpreter's environment.

    Running the installed executable keeps an importable `ruff` module in the
    working directory or on `PYTHONPATH`, and any earlier `ruff` on `PATH`,
    from being selected in place of the pinned tool.
    """
    scripts = sysconfig.get_path("scripts")
    executable = Path(scripts or "") / ("ruff.exe" if os.name == "nt" else "ruff")
    if not scripts or not executable.is_absolute() or not executable.is_file():
        raise LintError(
            "Ruff is unavailable; install tools/python-quality/requirements.txt "
            "from the root or managed workflow directory into this Python environment"
        )
    return executable


def check_version(executable: Path) -> None:
    result = subprocess.run(
        [str(executable), "--version"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        env=ruff_environment(),
    )
    if result.returncode:
        raise LintError(
            "the installed Ruff did not report its version: " + result.stderr.strip()
        )
    if result.stdout.strip() != f"ruff {RUFF_VERSION}":
        raise LintError(
            f"Ruff version mismatch: expected {RUFF_VERSION}, got {result.stdout.strip()!r}"
        )


def target_paths(root: Path, scopes: tuple[str, ...], operands: list[str]) -> list[str]:
    if len(operands) != len(set(operands)):
        raise LintError("duplicate lint targets are not allowed")
    if operands:
        for relative in operands:
            path = regular_path(root, relative)
            if (
                path.suffix != ".py"
                or not any(relative.startswith(scope + "/") for scope in scopes)
                or set(PurePosixPath(relative).parts) & EXCLUDED_DIRECTORIES
            ):
                raise LintError(f"target is outside the Python lint scope: {relative}")
        return sorted(operands)
    paths: list[str] = []

    def traversal_error(error: OSError) -> None:
        raise error

    for scope in scopes:
        directory = regular_path(root, scope, directory=True)
        for current, directories, files in os.walk(
            directory, followlinks=False, onerror=traversal_error,
        ):
            directories[:] = sorted(
                name for name in directories if name not in EXCLUDED_DIRECTORIES
            )
            for name in directories:
                relative = (Path(current) / name).relative_to(root).as_posix()
                regular_path(root, relative, directory=True)
            for name in sorted(files):
                if name.endswith(".py"):
                    relative = (Path(current) / name).relative_to(root).as_posix()
                    regular_path(root, relative)
                    paths.append(relative)
    if not paths:
        raise LintError("the declared Python lint scope contains no Python files")
    return sorted(paths)


def require_fix_worktree(root: Path, workflow: Path) -> None:
    relative = (
        ".project-agent-workflow/scripts/worktree_guard.py"
        if workflow != root else "scripts/project_workflow/worktree_guard.py"
    )
    guard = regular_path(root, relative)
    # The guard's verdict authorizes writes, so its interpreter is isolated too.
    # Inherited startup code could otherwise print a forged enforced result and
    # exit 0 before the guard reproduces the binding. The guard is stdlib-only.
    result = subprocess.run(
        [sys.executable, "-I", str(guard), "require", "--action", "applying Python lint fixes"],
        cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise LintError(result.stderr.strip() or "task worktree guard refused lint fixes")
    observation = json.loads(result.stdout)
    if not isinstance(observation, dict) or observation.get("enforced") is not True:
        raise LintError("Python lint fixes require a live task-bound worktree")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="apply only safe F541 fixes")
    parser.add_argument("files", nargs="*", help="explicit repository-relative Python files")
    args = parser.parse_args(argv)
    try:
        if args.fix and not args.files:
            raise LintError("--fix requires explicit Python file operands")
        root, workflow, scopes = layout()
        config = read_configuration(root, workflow)
        targets = target_paths(root, scopes, args.files)
        executable = ruff_executable()
        check_version(executable)
        if args.fix:
            for relative in targets:
                if regular_path(root, relative).stat().st_nlink != 1:
                    raise LintError(f"hard-linked files cannot receive lint fixes: {relative}")
            require_fix_worktree(root, workflow)
        command = [
            str(executable), "check", "--config", str(config),
            "--no-cache", "--no-unsafe-fixes", "--fix" if args.fix else "--no-fix",
            "--", *targets,
        ]
        return subprocess.run(command, cwd=root, env=ruff_environment(), check=False).returncode
    except (LintError, OSError, UnicodeError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"Python lint failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
