"""Disposable-repository tests for the generated-project smoke source."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT


sys.path.insert(0, str(ROOT / "scripts"))

from project_workflow.shell_functions import derive  # noqa: E402
from project_workflow.shell_lexical import project  # noqa: E402


HELPER = ROOT / "tests/prepare-smoke-source.py"
SMOKE = ROOT / "tests/smoke.sh"
TAG = "v1.2.2"
GUARD = 'if [ -z "$source_ref" ]; then\n'
TRACKED_TEMPLATE_SCRIPT = "template/.project-agent-workflow/scripts/tool_command_context.py"
TRACKED_COPY_TASK_SCRIPT = "scripts/validate-copier-update.py"


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def worktree_snapshot(repository: Path) -> dict[str, tuple[bytes, int]]:
    """Record every non-Git working file with its bytes and permission bits."""

    snapshot: dict[str, tuple[bytes, int]] = {}
    for path in sorted(repository.rglob("*")):
        if ".git" in path.relative_to(repository).parts:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        relative = str(path.relative_to(repository))
        snapshot[relative] = (path.read_bytes(), stat.S_IMODE(path.lstat().st_mode))
    return snapshot


class SmokeSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.destination = self.base / "render-source"
        self.source.mkdir()
        git(self.source, "init", "-q", "-b", "dev")
        git(self.source, "config", "user.name", "Smoke Source Test")
        git(self.source, "config", "user.email", "smoke-source-test@example.invalid")
        self.write("copier.yml", "_subdirectory: template\n")
        self.write(TRACKED_TEMPLATE_SCRIPT, "committed template helper\n")
        self.write(TRACKED_COPY_TASK_SCRIPT, "committed copy task\n")
        self.write("template/README.md.jinja", "committed readme\n")
        self.write("docs/plan/plan.md", "# Active Plan\n")
        self.write(".gitignore", ".agent-logs/\n*.pyc\n")
        git(self.source, "add", "-A")
        git(self.source, "commit", "-qm", "baseline")

    def tearDown(self) -> None:
        for path in sorted(self.base.rglob("*"), reverse=True):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        self.temp.cleanup()

    def write(self, relative: str, content: str, *, mode: int | None = None) -> Path:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if mode is not None:
            path.chmod(mode)
        return path

    def prepare(self, destination: Path | None = None) -> subprocess.CompletedProcess[str]:
        target = self.destination if destination is None else destination
        return subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--source",
                str(self.source),
                "--destination",
                str(target),
                "--tag",
                TAG,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def prepared(self) -> Path:
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.destination

    def committed_bytes(self, relative: str) -> str:
        return git(self.destination, "show", f"{TAG}:{relative}")

    def assert_refused(self, expected: str, *, destination_created: bool = False) -> None:
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected, result.stderr)
        self.assertEqual(self.destination.exists(), destination_created)

    def test_edited_template_script_is_prepared_with_current_bytes(self) -> None:
        self.write(TRACKED_TEMPLATE_SCRIPT, "edited template helper\n")
        self.prepared()
        self.assertEqual(self.committed_bytes(TRACKED_TEMPLATE_SCRIPT), "edited template helper\n")

    def test_edited_copy_task_script_is_prepared_with_current_bytes(self) -> None:
        self.write(TRACKED_COPY_TASK_SCRIPT, "edited copy task\n")
        self.prepared()
        self.assertEqual(self.committed_bytes(TRACKED_COPY_TASK_SCRIPT), "edited copy task\n")

    def test_staged_then_unstaged_change_uses_the_working_bytes(self) -> None:
        self.write("template/README.md.jinja", "staged readme\n")
        git(self.source, "add", "template/README.md.jinja")
        self.write("template/README.md.jinja", "working readme\n")
        self.prepared()
        self.assertEqual(self.committed_bytes("template/README.md.jinja"), "working readme\n")

    def test_new_nonignored_template_file_is_included(self) -> None:
        self.write("template/.project-agent-workflow/scripts/new_helper.py", "new helper\n")
        self.prepared()
        self.assertEqual(
            self.committed_bytes("template/.project-agent-workflow/scripts/new_helper.py"),
            "new helper\n",
        )

    def test_tracked_deletion_is_materialized(self) -> None:
        (self.source / "template/README.md.jinja").unlink()
        self.prepared()
        listing = git(self.destination, "ls-tree", "-r", "--name-only", TAG)
        self.assertNotIn("template/README.md.jinja", listing.splitlines())
        self.assertIn("copier.yml", listing.splitlines())

    def test_staged_removal_is_materialized(self) -> None:
        git(self.source, "rm", "-q", "template/README.md.jinja")
        self.prepared()
        listing = git(self.destination, "ls-tree", "-r", "--name-only", TAG).splitlines()
        self.assertNotIn("template/README.md.jinja", listing)

    def test_path_containing_spaces_is_prepared(self) -> None:
        relative = "template/.project-agent-workflow/docs/agent/spec notes.md"
        self.write(relative, "spaced notes\n")
        self.prepared()
        self.assertEqual(self.committed_bytes(relative), "spaced notes\n")

    def test_executable_bit_change_is_prepared(self) -> None:
        (self.source / TRACKED_COPY_TASK_SCRIPT).chmod(0o755)
        self.prepared()
        entry = git(self.destination, "ls-tree", TAG, "--", TRACKED_COPY_TASK_SCRIPT)
        self.assertTrue(entry.startswith("100755 "), entry)
        prepared_file = self.destination / TRACKED_COPY_TASK_SCRIPT
        self.assertTrue(stat.S_IMODE(prepared_file.lstat().st_mode) & stat.S_IXUSR)

    def test_preparation_leaves_the_source_unchanged(self) -> None:
        self.write(TRACKED_TEMPLATE_SCRIPT, "edited template helper\n")
        self.write("template/new-note.md", "new note\n")
        (self.source / "template/README.md.jinja").unlink()
        head = git(self.source, "rev-parse", "HEAD")
        refs = git(self.source, "show-ref")
        index = git(self.source, "status", "--porcelain=v1")
        snapshot = worktree_snapshot(self.source)
        self.prepared()
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.source, "show-ref"), refs)
        self.assertEqual(git(self.source, "status", "--porcelain=v1"), index)
        self.assertEqual(worktree_snapshot(self.source), snapshot)

    def test_ignored_local_evidence_is_not_overlaid(self) -> None:
        self.write("template/.project-agent-workflow/scripts/cached.pyc", "ignored bytes\n")
        self.write(".agent-logs/run.json", "{}\n")
        self.prepared()
        listing = git(self.destination, "ls-tree", "-r", "--name-only", TAG).splitlines()
        self.assertNotIn("template/.project-agent-workflow/scripts/cached.pyc", listing)
        self.assertNotIn(".agent-logs/run.json", listing)

    def test_new_file_outside_the_input_boundary_is_not_overlaid(self) -> None:
        self.write("docs/plan/backlog/900-example.md", "outside the boundary\n")
        self.prepared()
        listing = git(self.destination, "ls-tree", "-r", "--name-only", TAG).splitlines()
        self.assertNotIn("docs/plan/backlog/900-example.md", listing)

    def test_change_outside_the_input_boundary_is_not_overlaid(self) -> None:
        self.write("docs/plan/plan.md", "# Edited Active Plan\n")
        self.prepared()
        self.assertEqual(self.committed_bytes("docs/plan/plan.md"), "# Active Plan\n")

    @unittest.skipIf(os.geteuid() == 0, "root bypasses read permission")
    def test_unreadable_input_fails_before_the_clone(self) -> None:
        (self.source / TRACKED_TEMPLATE_SCRIPT).chmod(0o000)
        self.assert_refused("unreadable input")

    def test_symlink_input_is_refused(self) -> None:
        link = self.source / "template/link.md"
        link.symlink_to("README.md.jinja")
        git(self.source, "add", "template/link.md")
        self.assert_refused("unsupported tracked input type 120000")

    def test_untracked_symlink_input_is_refused(self) -> None:
        link = self.source / "template/untracked-link.md"
        link.symlink_to("README.md.jinja")
        self.assert_refused("unsupported input file type")

    def test_special_file_input_is_refused(self) -> None:
        os.mkfifo(self.source / "template/pipe")
        self.assert_refused("unsupported input file type")

    def test_existing_destination_is_refused(self) -> None:
        self.destination.mkdir()
        self.assert_refused("destination already exists", destination_created=True)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_non_repository_source_is_refused(self) -> None:
        plain = self.base / "plain"
        plain.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--source",
                str(plain),
                "--destination",
                str(self.destination),
                "--tag",
                TAG,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a Git repository", result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root bypasses write permission")
    def test_unusable_destination_reports_a_diagnostic(self) -> None:
        blocked = self.base / "blocked"
        blocked.mkdir(mode=0o500)
        result = self.prepare(blocked / "render-source")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("smoke source preparation failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class SmokeCopySelectionTest(unittest.TestCase):
    """Argument-capture tests for the copy paths declared in tests/smoke.sh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.smoke_text = SMOKE.read_text(encoding="utf-8")
        cls.smoke_lines = cls.smoke_text.splitlines(keepends=True)
        cls.table = derive(project(cls.smoke_text))

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.capture = self.base / "capture"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def function_text(self, name: str) -> str:
        declaration = self.table[name]
        return "".join(self.smoke_lines[declaration.start.line - 1 : declaration.end.line])

    def selection_block(self) -> str:
        start = self.smoke_lines.index(GUARD)
        end = self.smoke_lines.index("fi\n", start)
        return "".join(self.smoke_lines[start : end + 1])

    def run_shell(self, script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", "-eu", "-c", script],
            check=True,
            text=True,
            cwd=self.base,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def captured_arguments(self) -> list[str]:
        return self.capture.read_text(encoding="utf-8").split("\0")[:-1]

    def copy_preamble(self, source_ref: str, *, copier_status: int) -> str:
        """Replay the smoke variables one copy function reads, capturing argv."""

        return (
            f'root="{self.base}/root"\n'
            f'tmp="{self.base}/tmp"\n'
            f'render_source="{self.base}/render-source"\n'
            f'source_ref="{source_ref}"\n'
            f'run_copier() {{ for argument in "$@"; do printf "%s\\0" "$argument" '
            f'>>"{self.capture}"; done; return {copier_status}; }}\n'
        )

    def test_ordinary_copy_uses_the_prepared_source_and_ref(self) -> None:
        script = (
            self.copy_preamble(TAG, copier_status=0)
            + self.function_text("render_fixture")
            + '\nrender_fixture "$root/tests/fixtures/docs.answers.yml" "$tmp/out"\n'
        )
        self.run_shell(script)
        arguments = self.captured_arguments()
        self.assertIn("--vcs-ref", arguments)
        self.assertEqual(arguments[arguments.index("--vcs-ref") + 1], TAG)
        self.assertEqual(arguments[-2], f"{self.base}/render-source")
        self.assertNotIn(f"{self.base}/root", arguments)

    def test_default_copy_uses_the_prepared_source_and_ref(self) -> None:
        script = (
            self.copy_preamble(TAG, copier_status=0)
            + self.function_text("render_defaults")
            + '\nrender_defaults "$tmp/out"\n'
        )
        self.run_shell(script)
        arguments = self.captured_arguments()
        self.assertEqual(arguments[arguments.index("--vcs-ref") + 1], TAG)
        self.assertEqual(arguments[-2], f"{self.base}/render-source")
        self.assertNotIn(f"{self.base}/root", arguments)

    def test_invalid_answer_copy_uses_the_prepared_source_and_ref(self) -> None:
        script = (
            self.copy_preamble(TAG, copier_status=1)
            + self.function_text("assert_rejected_input")
            + "\nassert_rejected_input empty-name project_name ''\n"
        )
        self.run_shell(script)
        arguments = self.captured_arguments()
        self.assertEqual(arguments[arguments.index("--vcs-ref") + 1], TAG)
        self.assertEqual(arguments[-2], f"{self.base}/render-source")
        self.assertEqual(arguments[-1], f"{self.base}/tmp/invalid-empty-name")
        self.assertNotIn(f"{self.base}/root", arguments)

    def test_every_copy_path_reads_the_same_selected_source(self) -> None:
        sources = set()
        for name, call, status in (
            ("render_fixture", 'render_fixture "$tmp/fixture.yml" "$tmp/out"', 0),
            ("render_defaults", 'render_defaults "$tmp/out"', 0),
            ("assert_rejected_input", "assert_rejected_input label project_name ''", 1),
        ):
            self.capture.unlink(missing_ok=True)
            preamble = self.copy_preamble(TAG, copier_status=status)
            self.run_shell(preamble + self.function_text(name) + f"\n{call}\n")
            arguments = self.captured_arguments()
            sources.add((arguments[arguments.index("--vcs-ref") + 1], arguments[-2]))
        self.assertEqual(sources, {(TAG, f"{self.base}/render-source")})

    def test_absent_smoke_ref_prepares_an_isolated_source(self) -> None:
        stub = self.base / "bin"
        stub.mkdir()
        (stub / "python3").write_text(
            f'#!/bin/sh\nfor argument in "$@"; do printf "%s\\0" "$argument" >>"{self.capture}"; done\n',
            encoding="utf-8",
        )
        (stub / "python3").chmod(0o755)
        script = (
            f'PATH="{stub}:$PATH"\n'
            f'root="{self.base}/root"\n'
            f'tmp="{self.base}/tmp"\n'
            'source_ref=""\n'
            'render_source=$root\n'
            + self.selection_block()
            + '\nprintf "%s\\n%s\\n" "$render_source" "$source_ref"\n'
        )
        result = self.run_shell(script)
        self.assertEqual(
            result.stdout, f"{self.base}/tmp/render-source\n{TAG}\n"
        )
        arguments = self.captured_arguments()
        self.assertIn(f"{self.base}/root/tests/prepare-smoke-source.py", arguments)
        self.assertEqual(arguments[arguments.index("--destination") + 1], f"{self.base}/tmp/render-source")

    def test_explicit_smoke_ref_bypasses_the_current_file_overlay(self) -> None:
        stub = self.base / "bin"
        stub.mkdir()
        (stub / "python3").write_text(
            f'#!/bin/sh\nprintf "called\\0" >>"{self.capture}"\n', encoding="utf-8"
        )
        (stub / "python3").chmod(0o755)
        script = (
            f'PATH="{stub}:$PATH"\n'
            f'root="{self.base}/root"\n'
            f'tmp="{self.base}/tmp"\n'
            'source_ref="v9.9.9"\n'
            'render_source=$root\n'
            + self.selection_block()
            + '\nprintf "%s\\n%s\\n" "$render_source" "$source_ref"\n'
        )
        result = self.run_shell(script)
        self.assertEqual(result.stdout, f"{self.base}/root\nv9.9.9\n")
        self.assertFalse(self.capture.exists())
