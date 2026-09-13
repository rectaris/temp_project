#!/usr/bin/env python3
"""Check the improvement record command in its root and generated layouts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_COMMAND = ROOT / "template/.project-agent-workflow/scripts/template-feedback.py"
ROOT_COMMAND = ROOT / "scripts/template-feedback.py"
GENERATED_COMMAND = Path(".project-agent-workflow/scripts/template-feedback.py")


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("template_feedback_under_test", TEMPLATE_COMMAND)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FEEDBACK = load_module()


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def example_record() -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(TEMPLATE_COMMAND), "example"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


class FeedbackCase(unittest.TestCase):
    """Drive the command through both installed layouts against real files."""

    layouts = ("root", "generated")

    def fixture(self, *, mode: str = "agent_select_local", layout: str = "root"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "docs/agent").mkdir(parents=True)
        (root / "docs/agent/template-feedback.json").write_text(
            json.dumps({"schema_version": 1, "project_alias": "example-project", "mode": mode}) + "\n",
            encoding="utf-8",
        )
        (root / "docs/agent/SPEC_PLAN_WORKFLOW.md").write_text("referenced evidence location\n", encoding="utf-8")
        if layout == "generated":
            # The generated project ships the implementation itself; the root
            # repository reaches it through a wrapper. Both must behave alike.
            destination = root / GENERATED_COMMAND
            destination.parent.mkdir(parents=True)
            destination.write_bytes(TEMPLATE_COMMAND.read_bytes())
            command = [sys.executable, str(destination)]
        else:
            command = [sys.executable, str(ROOT_COMMAND)]
        return temporary, root, command

    def run_cli(self, command: list[str], root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["PYTHONPYCACHEPREFIX"] = str(root / ".pycache")
        return subprocess.run(
            [*command, *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    def write_record(self, root: Path, record: dict[str, object]) -> tuple[Path, str]:
        path = root / "candidate.json"
        raw = (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        return path, digest(raw)

    def record_arguments(self, path: Path, checked: str) -> list[str]:
        return ["record", "--record", str(path), "--checked-digest", checked]


class RecordShapeTest(FeedbackCase):
    def test_example_record_is_accepted_in_both_layouts(self) -> None:
        for layout in self.layouts:
            with self.subTest(layout=layout):
                temporary, root, command = self.fixture(layout=layout)
                with temporary:
                    path, checked = self.write_record(root, example_record())
                    result = self.run_cli(command, root, "check", "--record", str(path))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    assessed = json.loads(result.stdout)
                    self.assertEqual(assessed["decision"], "record")
                    self.assertEqual(assessed["checked_digest"], checked)
                    self.assertEqual(
                        assessed["record_path"],
                        "docs/template-feedback/example-project/plan-worktree-publish-confusion.json",
                    )

    def test_unknown_revision_and_attribution_are_preserved(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            assessed = json.loads(result.stdout)
            # An absent upstream revision and an unresolved cause survive as
            # explicit unknowns instead of being inferred from the task.
            self.assertEqual(assessed["template_revision"], "unknown")
            self.assertEqual(assessed["attribution_certainty"], "unknown")

    def test_missing_field_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            del record["impact"]
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid exact field shape", result.stderr)

    def test_empty_field_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["observed_behavior"] = "   "
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("state an explicit unknown instead", result.stderr)

    def test_guessed_revision_shape_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["template_source"] = {"alias": "project-agent-workflow", "revision": "probably v1.4.5"}
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exact revision or the explicit unknown value", result.stderr)

    def test_oversized_record_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["impact"] = "x" * (FEEDBACK.MAX_FIELD_BYTES + 1)
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds its byte bound", result.stderr)

    def test_evidence_reference_escaping_the_repository_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["evidence"][1]["reference"] = "../outside.md"
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("normalized repository-relative path", result.stderr)

    def test_evidence_reference_through_a_symlink_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            (root / "linked").symlink_to("docs")
            record = example_record()
            record["evidence"][1]["reference"] = "linked/agent/SPEC_PLAN_WORKFLOW.md"
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not contain a symlink", result.stderr)

    def test_alias_mismatch_with_the_project_configuration_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["project_alias"] = "other-project"
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match the configured project alias", result.stderr)


class SecretRejectionTest(FeedbackCase):
    suspected = (
        ("private_key", "-----BEGIN RSA PRIVATE KEY-----"),
        ("aws_key", "The log printed AKIAIOSFODNN7EXAMPLE during setup."),
        ("github_token", "It used ghp_abcdefghijklmnopqrstuvwxyz0123456789."),
        ("assignment", "The fixture set api_key = 0123456789abcdef in the shell."),
    )

    def test_suspected_credentials_are_rejected_in_every_text_field(self) -> None:
        for name, text in self.suspected:
            for field in ("impact", "workaround"):
                with self.subTest(pattern=name, field=field):
                    temporary, root, command = self.fixture()
                    with temporary:
                        record = example_record()
                        record[field] = text
                        path, _ = self.write_record(root, record)
                        result = self.run_cli(command, root, "check", "--record", str(path))
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("suspected credential", result.stderr)

    def test_suspected_credentials_are_rejected_in_evidence_summaries(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["evidence"][0]["summary"] = "The token ghp_abcdefghijklmnopqrstuvwxyz0123456789 appeared."
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("suspected credential", result.stderr)

    def test_suspected_credentials_are_rejected_in_evidence_references(self) -> None:
        # A reference names a location. Without this scan it would be a second
        # free-text field that never met the evidence review.
        for name, text in self.suspected:
            with self.subTest(pattern=name):
                temporary, root, command = self.fixture()
                with temporary:
                    record = example_record()
                    record["evidence"][1]["reference"] = text
                    path, _ = self.write_record(root, record)
                    result = self.run_cli(command, root, "check", "--record", str(path))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("suspected credential", result.stderr)

    def test_a_reference_carrying_prose_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["evidence"][1]["reference"] = "docs/plan/README.md and the note beside it"
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("path without whitespace", result.stderr)


class RoutingModeTest(FeedbackCase):
    def test_local_mode_prepares_an_ignored_draft_and_no_tracked_file(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "draft", "--record", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            drafted = json.loads(result.stdout)
            self.assertEqual(
                drafted["draft_path"],
                ".agent-artifacts/template-feedback/plan-worktree-publish-confusion.json",
            )
            self.assertTrue((root / drafted["draft_path"]).is_file())
            self.assertFalse((root / "docs/template-feedback").exists())

    def test_disabled_mode_is_a_no_op_for_check_and_draft(self) -> None:
        temporary, root, command = self.fixture(mode="disabled")
        with temporary:
            record = example_record()
            path, _ = self.write_record(root, record)
            for verb in ("check", "draft"):
                with self.subTest(verb=verb):
                    result = self.run_cli(command, root, verb, "--record", str(path))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["decision"], "no_op")
            self.assertFalse((root / ".agent-artifacts").exists())
            self.assertFalse((root / "docs/template-feedback").exists())

    def test_disabled_mode_refuses_to_record(self) -> None:
        temporary, root, command = self.fixture(mode="disabled")
        with temporary:
            record = example_record()
            path, checked = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("recording is disabled", result.stderr)
            self.assertFalse((root / "docs/template-feedback").exists())

    def test_unsupported_mode_is_rejected(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            (root / "docs/agent/template-feedback.json").write_text(
                json.dumps({"schema_version": 1, "project_alias": "example-project", "mode": "send_upstream"}) + "\n",
                encoding="utf-8",
            )
            record = example_record()
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "check", "--record", str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent_select_local or disabled", result.stderr)


class PersistenceTest(FeedbackCase):
    def test_recording_writes_one_project_owned_file_in_both_layouts(self) -> None:
        for layout in self.layouts:
            with self.subTest(layout=layout):
                temporary, root, command = self.fixture(layout=layout)
                with temporary:
                    record = example_record()
                    path, checked = self.write_record(root, record)
                    result = self.run_cli(command, root, *self.record_arguments(path, checked))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    written = json.loads(result.stdout)
                    self.assertEqual(written["outcome"], "written")
                    stored = root / written["record_path"]
                    self.assertTrue(stored.is_file())
                    self.assertEqual(json.loads(stored.read_text(encoding="utf-8")), record)

    def test_identical_retry_changes_nothing(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            path, checked = self.write_record(root, record)
            first = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertEqual(first.returncode, 0, first.stderr)
            stored = root / json.loads(first.stdout)["record_path"]
            before = stored.read_bytes()
            second = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["outcome"], "unchanged")
            self.assertEqual(stored.read_bytes(), before)

    def test_conflicting_bytes_under_one_identity_are_refused(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            path, checked = self.write_record(root, record)
            self.assertEqual(self.run_cli(command, root, *self.record_arguments(path, checked)).returncode, 0)
            stored = root / "docs/template-feedback/example-project/plan-worktree-publish-confusion.json"
            before = stored.read_bytes()
            record["impact"] = "A different account of the same report id."
            path, checked = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("an immutable record already exists with different bytes", result.stderr)
            self.assertEqual(stored.read_bytes(), before)

    def test_correction_uses_a_new_id_that_supersedes_the_original(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            path, checked = self.write_record(root, record)
            self.assertEqual(self.run_cli(command, root, *self.record_arguments(path, checked)).returncode, 0)
            correction = example_record()
            correction["report_id"] = "plan-worktree-publish-confusion-corrected"
            correction["supersedes"] = record["report_id"]
            path, checked = self.write_record(root, correction)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (root / "docs/template-feedback/example-project/plan-worktree-publish-confusion.json").is_file()
            )
            self.assertTrue(
                (
                    root
                    / "docs/template-feedback/example-project/plan-worktree-publish-confusion-corrected.json"
                ).is_file()
            )

    def test_supersedes_without_a_held_report_is_refused(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            record["report_id"] = "later-report"
            record["supersedes"] = "never-recorded"
            path, checked = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not hold", result.stderr)
            self.assertFalse((root / "docs/template-feedback").exists())

    def test_digest_of_other_bytes_is_refused(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            record = example_record()
            path, checked = self.write_record(root, record)
            record["impact"] = "Rewritten after the check and before the record."
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checked digest does not match", result.stderr)
            self.assertFalse((root / "docs/template-feedback").exists())


    def test_a_leading_digit_alias_records_end_to_end(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            (root / "docs/agent/template-feedback.json").write_text(
                json.dumps({"schema_version": 1, "project_alias": "3d-engine", "mode": "agent_select_local"}) + "\n",
                encoding="utf-8",
            )
            record = example_record()
            record["project_alias"] = "3d-engine"
            path, checked = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / json.loads(result.stdout)["record_path"]).is_file())


class TaskBoundaryTest(FeedbackCase):
    def install_guard(self, root: Path, *, refuse: bool) -> Path:
        guard = root / ".project-agent-workflow/scripts/worktree_guard.py"
        guard.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "import sys\n"
            "sys.stderr.write('task worktree guard refused: prepare the bound checkout first\\n')\n"
            "raise SystemExit(1)\n"
            if refuse
            else "raise SystemExit(0)\n"
        )
        guard.write_text(body, encoding="utf-8")
        return guard

    def test_a_refusing_task_guard_blocks_the_record_write(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            self.install_guard(root, refuse=True)
            record = example_record()
            path, checked = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("task worktree guard refused", result.stderr)
            self.assertFalse((root / "docs/template-feedback").exists())

    def test_a_permitting_task_guard_allows_the_record_write(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            self.install_guard(root, refuse=False)
            record = example_record()
            path, checked = self.write_record(root, record)
            result = self.run_cli(command, root, *self.record_arguments(path, checked))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / json.loads(result.stdout)["record_path"]).is_file())

    def test_a_nested_root_still_meets_the_repository_task_guard(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            self.install_guard(root, refuse=True)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            nested = root / "sub/nested"
            nested.mkdir(parents=True)
            record = example_record()
            path, checked = self.write_record(root, record)
            result = self.run_cli(
                command,
                root,
                *self.record_arguments(path, checked),
                "--root",
                str(nested),
                "--config",
                str(root / "docs/agent/template-feedback.json"),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("task worktree guard refused", result.stderr)
            self.assertFalse((nested / "docs/template-feedback").exists())

    def test_a_refusing_task_guard_does_not_block_a_local_draft(self) -> None:
        temporary, root, command = self.fixture()
        with temporary:
            self.install_guard(root, refuse=True)
            record = example_record()
            path, _ = self.write_record(root, record)
            result = self.run_cli(command, root, "draft", "--record", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / json.loads(result.stdout)["draft_path"]).is_file())


class BoundaryTest(unittest.TestCase):
    def test_no_command_performs_network_side_effects(self) -> None:
        source = TEMPLATE_COMMAND.read_text(encoding="utf-8")
        for forbidden in ("urllib", "http.client", "socket", "requests", "ftplib", "smtplib"):
            self.assertNotIn(forbidden, source)
        # The only processes the command starts are the shared task guard and
        # the working-tree lookup that locates it.
        self.assertEqual(source.count("subprocess.run("), 2)
        self.assertEqual(source.count('"git", "rev-parse", "--show-toplevel"'), 1)

    def test_the_copier_slug_domain_stays_inside_the_accepted_alias_domain(self) -> None:
        # The generated configuration copies project_slug into project_alias.
        # A slug Copier accepts but the command rejects would leave that project
        # permanently unable to record anything.
        validator = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))["project_slug"]["validator"]
        self.assertIn("^[a-z0-9][a-z0-9-]*$", validator)
        self.assertIn("project_slug | length > 64", validator)
        for slug in ("3d-engine", "example-project", "a" * 64):
            with self.subTest(slug=slug):
                self.assertRegex(slug, "^[a-z0-9][a-z0-9-]*$")
                self.assertLessEqual(len(slug), 64)
                self.assertTrue(FEEDBACK.ALIAS_RE.fullmatch(slug))
        self.assertIsNone(FEEDBACK.ALIAS_RE.fullmatch("a" * 65))

    def test_root_wrapper_delegates_to_the_shipped_implementation(self) -> None:
        wrapper = ROOT_COMMAND.read_text(encoding="utf-8")
        self.assertIn("template-feedback.py", wrapper)
        self.assertIn(".project-agent-workflow", wrapper)

    def test_no_improvement_record_ships_in_the_template(self) -> None:
        self.assertFalse((ROOT / "template/docs/template-feedback").exists())

    def test_the_specification_states_the_local_boundary(self) -> None:
        specification = (ROOT / "docs/agent/SPEC_TEMPLATE_FEEDBACK.md").read_text(encoding="utf-8")
        for required in (
            "no external effect",
            "never blocks the product conversation",
            "task worktree guard",
        ):
            self.assertIn(required, specification)


if __name__ == "__main__":
    unittest.main(verbosity=0)
