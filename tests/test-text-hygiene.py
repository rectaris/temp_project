#!/usr/bin/env python3
"""Prove the tracked-text rule refuses each defect and is reachable locally."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "scripts/check-text-hygiene.py"


def isolated_environment(**extra: str) -> dict[str, str]:
    """Let no configuration outside the fixture reach the verdict.

    A temporary directory must not answer for an enclosing repository, and the
    account's own Git configuration must not decide whether required
    validation passes.
    """

    environment = dict(os.environ)
    environment["GIT_CEILING_DIRECTORIES"] = str(Path(tempfile.gettempdir()).resolve())
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_SYSTEM"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    for name in ("GIT_EXTERNAL_DIFF", "GIT_DIFF_OPTS"):
        environment.pop(name, None)
    environment.update(extra)
    return environment


class RepositoryCase(unittest.TestCase):
    def repository(
        self, files: dict[str, bytes], config: dict[str, str] | None = None
    ) -> tuple[tempfile.TemporaryDirectory, Path]:
        """A repository whose Git configuration is stated, never inherited."""

        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        self.git(root.parent, ["init", "-q", "-b", "main", str(root)])
        settings = {
            "core.autocrlf": "false",
            "commit.gpgSign": "false",
            "user.email": "t@example.com",
            "user.name": "t",
        }
        settings.update(config or {})
        for key, value in settings.items():
            self.git(root, ["config", key, value])
        for name, data in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.git(root, ["add", "-A"])
        return temporary, root

    def git(self, cwd: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, check=True, env=isolated_environment(),
            capture_output=True,
        )

    def run_command(self, root: Path, **environment: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(COMMAND), "--root", str(root)],
            capture_output=True,
            text=True,
            check=False,
            env=isolated_environment(**environment),
        )

    def git_verdict(self, root: Path) -> int:
        """What the release boundary says about the same staged content."""

        return subprocess.run(
            ["git", "diff", "--cached", "--check"],
            cwd=root,
            capture_output=True,
            check=False,
            env=isolated_environment(),
        ).returncode


class RuleTest(RepositoryCase):
    """Each rule refuses a file that breaks only that rule."""

    DEFECTS = {
        "trailing whitespace": b"a line with a trailing space \nand a clean line\n",
        "new blank line at EOF": b"one line\n\n",
        "missing final newline": b"one line without its newline",
    }

    def test_each_defect_is_refused_and_named(self) -> None:
        for label, data in self.DEFECTS.items():
            with self.subTest(rule=label):
                temporary, root = self.repository({"sample.txt": data})
                with temporary:
                    result = self.run_command(root)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn("sample.txt", result.stderr)
                    self.assertIn(label, result.stderr)

    def test_a_carriage_return_is_refused_as_trailing_whitespace(self) -> None:
        temporary, root = self.repository({"sample.txt": b"one line\r\n"})
        with temporary:
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("sample.txt:1", result.stderr)

    def test_a_refusal_names_what_to_do_next(self) -> None:
        temporary, root = self.repository({"sample.txt": b"one line\n\n"})
        with temporary:
            self.assertIn("Next:", self.run_command(root).stderr)

    def test_clean_text_is_accepted(self) -> None:
        temporary, root = self.repository({"sample.txt": b"one line\nanother line\n"})
        with temporary:
            result = self.run_command(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("passed", result.stdout)

    def test_an_empty_tracked_file_is_accepted(self) -> None:
        temporary, root = self.repository({"empty.txt": b""})
        with temporary:
            self.assertEqual(self.run_command(root).returncode, 0)

    def test_a_file_holding_only_a_newline_is_accepted(self) -> None:
        temporary, root = self.repository({"newline.txt": b"\n"})
        with temporary:
            self.assertEqual(self.run_command(root).returncode, 0)
            self.assertEqual(self.git_verdict(root), 0)

    def test_untracked_text_is_not_the_subject(self) -> None:
        temporary, root = self.repository({"sample.txt": b"clean\n"})
        with temporary:
            (root / "untracked.txt").write_bytes(b"trailing space \n")
            self.assertEqual(self.run_command(root).returncode, 0)

    def test_every_violation_is_reported_not_only_the_first_file(self) -> None:
        temporary, root = self.repository(
            {"first.txt": b"one line\n\n", "second.txt": b"trailing space \n"}
        )
        with temporary:
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("first.txt", result.stderr)
            self.assertIn("second.txt", result.stderr)

    def test_a_defect_in_an_unstaged_edit_is_reported(self) -> None:
        temporary, root = self.repository({"sample.txt": b"clean\n"})
        with temporary:
            (root / "sample.txt").write_bytes(b"trailing space \n")
            self.assertEqual(self.run_command(root).returncode, 1)

    def test_a_defect_the_index_still_holds_is_reported_and_marked(self) -> None:
        """A commit records the index, so an unstaged repair is not enough."""

        temporary, root = self.repository({"sample.txt": b"trailing space \n"})
        with temporary:
            (root / "sample.txt").write_bytes(b"clean\n")
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("(staged) sample.txt", result.stderr)

    def test_a_repair_present_in_both_places_is_accepted(self) -> None:
        temporary, root = self.repository({"sample.txt": b"trailing space \n"})
        with temporary:
            (root / "sample.txt").write_bytes(b"clean\n")
            self.git(root, ["add", "-A"])
            self.assertEqual(self.run_command(root).returncode, 0)

    def test_one_defect_in_both_places_is_reported_once_without_the_mark(self) -> None:
        temporary, root = self.repository({"sample.txt": b"trailing space \n"})
        with temporary:
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1)
            reports = [line for line in result.stderr.splitlines() if "sample.txt" in line]
            self.assertEqual(reports, ["sample.txt:1: trailing whitespace."])


class BoundaryAgreementTest(RepositoryCase):
    """The local verdict has to be the one the release boundary will give."""

    def test_the_release_boundary_agrees_on_the_rules_it_shares(self) -> None:
        shared = ("trailing whitespace", "new blank line at EOF")
        for label in shared:
            with self.subTest(rule=label):
                temporary, root = self.repository({"sample.txt": RuleTest.DEFECTS[label]})
                with temporary:
                    self.assertNotEqual(self.git_verdict(root), 0)
                    self.assertEqual(self.run_command(root).returncode, 1)

    def test_a_missing_final_newline_is_the_one_rule_the_boundary_lacks(self) -> None:
        """Record the single added rule, so the difference stays known."""

        temporary, root = self.repository({"sample.txt": b"no newline"})
        with temporary:
            self.assertEqual(self.git_verdict(root), 0)
            self.assertEqual(self.run_command(root).returncode, 1)

    def test_binary_content_is_left_to_the_same_judgement_as_the_boundary(self) -> None:
        body = bytearray(b"a" * 9000 + b"trailing space \n")
        for offset in (7999, 8000, 8191):
            with self.subTest(offset=offset):
                content = bytearray(body)
                content[offset] = 0
                temporary, root = self.repository({"blob.bin": bytes(content)})
                with temporary:
                    expected = {0: 0, 2: 1}[self.git_verdict(root)]
                    self.assertEqual(self.run_command(root).returncode, expected)

    def test_a_refusal_this_command_cannot_read_still_refuses(self) -> None:
        """Git's exit status is the verdict, not the wording of its message."""

        marker = b"<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> other\n"
        temporary, root = self.repository({"conflict.txt": marker})
        with temporary:
            self.assertEqual(self.git_verdict(root), 2)
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("conflict.txt", result.stderr)


class LineEndingTest(RepositoryCase):
    """Line endings follow Git's own conversion, not a second opinion."""

    def test_line_endings_added_by_the_checkout_are_not_reported(self) -> None:
        temporary, root = self.repository(
            {"sample.txt": b"one line\nanother line\n"}, config={"core.autocrlf": "true"}
        )
        with temporary:
            self.git(root, ["commit", "-qm", "initial"])
            # Only a fresh checkout applies the conversion, so remove the file
            # Git already wrote and let Git write it again.
            (root / "sample.txt").unlink()
            self.git(root, ["checkout", "-q", "--", "sample.txt"])
            self.assertEqual(
                self.git(root, ["ls-files", "--eol", "sample.txt"]).stdout.decode().split()[1],
                "w/crlf",
            )
            result = self.run_command(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_carriage_returns_an_edit_introduced_are_reported(self) -> None:
        temporary, root = self.repository({"sample.txt": b"one line\n"})
        with temporary:
            (root / "sample.txt").write_bytes(b"one line\r\n")
            self.assertEqual(self.run_command(root).returncode, 1)

    def test_a_file_mixing_both_line_endings_is_reported(self) -> None:
        temporary, root = self.repository({"sample.txt": b"one line\r\nanother line\n"})
        with temporary:
            self.assertEqual(self.run_command(root).returncode, 1)

    def test_carriage_returns_a_binary_attribute_preserves_are_reported(self) -> None:
        temporary, root = self.repository(
            {"sample.txt": b"one line\r\n", ".gitattributes": b"sample.txt -text\n"}
        )
        with temporary:
            self.assertEqual(self.run_command(root).returncode, 1)


class ConfigurationTest(RepositoryCase):
    """No configuration outside this command may change the verdict."""

    def test_a_relaxed_whitespace_setting_does_not_excuse_a_defect(self) -> None:
        temporary, root = self.repository(
            {"sample.txt": b"one line\n\n"}, config={"core.whitespace": "-blank-at-eof"}
        )
        with temporary:
            self.assertEqual(self.run_command(root).returncode, 1)

    def test_a_patch_format_setting_does_not_hide_a_missing_newline(self) -> None:
        for key, value in (("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true")):
            with self.subTest(setting=key):
                temporary, root = self.repository({"sample.txt": b"no newline"}, config={key: value})
                with temporary:
                    self.assertEqual(self.run_command(root).returncode, 1)

    def test_an_external_diff_program_does_not_replace_the_verdict(self) -> None:
        temporary, root = self.repository({"sample.txt": b"no newline"})
        with temporary:
            program = root.parent / "external-diff.sh"
            program.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            program.chmod(0o755)
            try:
                result = self.run_command(root, GIT_EXTERNAL_DIFF=str(program))
                self.assertEqual(result.returncode, 1, result.stdout)
            finally:
                program.unlink()

    def test_an_external_diff_setting_does_not_replace_the_verdict(self) -> None:
        temporary, root = self.repository({"sample.txt": b"no newline"}, config={"diff.external": "true"})
        with temporary:
            self.assertEqual(self.run_command(root).returncode, 1)


class PathTest(RepositoryCase):
    """Unusual tracked paths are read, not lost."""

    def test_a_path_holding_a_tab_is_still_read(self) -> None:
        try:
            temporary, root = self.repository({"odd\tname.txt": b"no newline"})
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("this filesystem refuses a tab in a name")
        with temporary:
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("missing final newline", result.stderr)

    def test_a_path_holding_a_space_is_reported_by_its_own_name(self) -> None:
        temporary, root = self.repository({"a name.txt": b"no newline"})
        with temporary:
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("a name.txt: missing final newline", result.stderr)

    def test_a_path_outside_utf_8_does_not_crash_the_check(self) -> None:
        temporary, root = self.repository({"clean.txt": b"clean\n"})
        with temporary:
            try:
                (root / os.fsdecode(b"odd-\xff.txt")).write_bytes(b"no newline")
            except (OSError, UnicodeError):
                self.skipTest("this filesystem refuses a non-UTF-8 name")
            self.git(root, ["add", "-A"])
            result = self.run_command(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_a_tracked_symlink_is_not_read_as_its_target(self) -> None:
        temporary, root = self.repository({"clean.txt": b"clean\n"})
        with temporary:
            outside = Path(temporary.name).parent / "outside-target.txt"
            outside.write_bytes(b"trailing space \n")
            try:
                (root / "link.txt").symlink_to(outside)
            except OSError:
                self.skipTest("this filesystem refuses symlinks")
            self.git(root, ["add", "-A"])
            try:
                self.assertEqual(self.run_command(root).returncode, 0)
            finally:
                outside.unlink()


class RootTest(RepositoryCase):
    """The command answers for one whole working tree or for none."""

    def test_a_directory_that_holds_no_repository_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as plain:
            result = self.run_command(Path(plain))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("text hygiene check failed", result.stderr)

    def test_a_subdirectory_cannot_answer_for_the_repository(self) -> None:
        temporary, root = self.repository({"nested/sample.txt": b"clean\n"})
        with temporary:
            result = self.run_command(root / "nested")
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("not the root", result.stderr)


class RegistrationTest(unittest.TestCase):
    """A rule nobody runs is not a rule."""

    def test_required_lint_runs_the_checker_and_this_suite(self) -> None:
        lint = (ROOT / "scripts/lint-project-workflow.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/check-text-hygiene.py", lint)
        self.assertIn("tests/test-text-hygiene.py", lint)

    def test_the_checker_is_in_the_deterministic_source_inventory(self) -> None:
        inventory = (ROOT / "scripts/project_workflow/copier_inventory.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"scripts/check-text-hygiene.py"', inventory)

    def test_this_repository_satisfies_its_own_rule(self) -> None:
        result = subprocess.run(
            [sys.executable, str(COMMAND), "--root", str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
