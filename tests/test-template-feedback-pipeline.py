#!/usr/bin/env python3
"""Drive one improvement from a generated project to an adopted direction.

The whole path runs against real Copier output: a generated project records an
improvement, a second generated project receives it, derives a requirement
candidate, adopts it by explicit decision and renders a direction, and a Copier
update then has to leave every one of those project-owned bytes alone.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TAG = "v1.2.2"
MANUAL_PROSE = "Our own standing note that Copier must not touch.\n"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def copier_command() -> list[str] | None:
    if shutil.which("copier"):
        return ["copier"]
    if shutil.which("uv") and (ROOT / "pyproject.toml").is_file():
        return ["uv", "run", "--project", str(ROOT), "copier"]
    return None


COPIER = copier_command()


def run(command: list[str], cwd: Path, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=environment or os.environ.copy(),
    )


def git(repository: Path, *arguments: str) -> None:
    result = run(["git", "-C", str(repository), *arguments], ROOT)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")


@unittest.skipIf(
    COPIER is None and os.environ.get("REQUIRE_COPIER", "0") != "1",
    "copier CLI not found; skipped generated-project pipeline",
)
class PipelineTest(unittest.TestCase):
    """One improvement, two generated projects, one Copier update."""

    @classmethod
    def setUpClass(cls) -> None:
        if COPIER is None:
            raise AssertionError("copier CLI not found and REQUIRE_COPIER=1")
        cls._temporary = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._temporary.name)
        cls.environment = os.environ.copy()
        cls.environment["UV_CACHE_DIR"] = str(cls.tmp / "uv-cache")
        cls.source = cls.tmp / "source"
        prepared = run(
            [
                sys.executable,
                str(ROOT / "tests/prepare-smoke-source.py"),
                "--source",
                str(ROOT),
                "--destination",
                str(cls.source),
                "--tag",
                SOURCE_TAG,
            ],
            ROOT,
        )
        if prepared.returncode != 0:
            raise AssertionError(f"could not prepare a disposable Copier source: {prepared.stderr.strip()}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def copier(self, *arguments: str) -> None:
        result = run([*COPIER, *arguments], ROOT, self.environment)
        if result.returncode != 0:
            raise AssertionError(f"copier {' '.join(arguments)} failed: {result.stderr.strip()}")

    def render(self, name: str) -> Path:
        out = self.tmp / name
        self.copier(
            "copy", "-q", "-f", "--trust", "--defaults", "--vcs-ref", SOURCE_TAG, str(self.source), str(out)
        )
        git(out, "init", "-b", "main")
        git(out, "config", "user.name", "CI")
        git(out, "config", "user.email", "ci@example.invalid")
        git(out, "add", "-A")
        git(out, "-c", "user.name=CI", "-c", "user.email=ci@example.invalid", "commit", "-qm", "Generate project")
        return out

    def project_cli(self, project: Path, name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = self.environment.copy()
        environment["PYTHONPYCACHEPREFIX"] = str(self.tmp / "pycache")
        return run(
            [sys.executable, f".project-agent-workflow/scripts/{name}", *arguments],
            project,
            environment,
        )

    def checked(self, project: Path, name: str, *arguments: str) -> dict:
        result = self.project_cli(project, name, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_an_improvement_reaches_an_adopted_direction_and_survives_update(self) -> None:
        reporter = self.render("reporter")
        receiver = self.render("receiver")

        # 1. The reporting project records its own improvement evidence.
        report = self.checked(reporter, "template-feedback.py", "example")
        alias = json.loads((reporter / "docs/agent/template-feedback.json").read_text(encoding="utf-8"))[
            "project_alias"
        ]
        report["project_alias"] = alias
        (reporter / "report.json").write_bytes(json_bytes(report))
        assessed = self.checked(reporter, "template-feedback.py", "check", "--record", "report.json")
        recorded = self.checked(
            reporter,
            "template-feedback.py",
            "record",
            "--record",
            "report.json",
            "--checked-digest",
            assessed["checked_digest"],
        )
        reported = reporter / recorded["record_path"]
        self.assertTrue(reported.is_file())

        # 2. The receiving project imports that exact file and nothing else.
        transferred = receiver / "incoming-report.json"
        transferred.write_bytes(reported.read_bytes())
        planned = self.checked(
            receiver, "collect-template-feedback.py", "check", "--report", "incoming-report.json"
        )
        imported = self.checked(
            receiver,
            "collect-template-feedback.py",
            "import",
            "--report",
            "incoming-report.json",
            "--checked-digest",
            planned["checked_digest"],
        )
        held_report = receiver / imported["written"][0]
        self.assertTrue(held_report.is_file())

        # 3. The receiver derives a requirement candidate from held bytes.
        candidate = self.checked(receiver, "collect-template-feedback.py", "example")
        candidate["sources"] = [
            {
                "project_alias": alias,
                "report_id": report["report_id"],
                "digest": "sha256:" + digest(held_report),
            }
        ]
        (receiver / "candidate.json").write_bytes(json_bytes(candidate))
        candidate_check = self.checked(
            receiver, "collect-template-feedback.py", "check-candidate", "--candidate", "candidate.json"
        )
        candidate_record = self.checked(
            receiver,
            "collect-template-feedback.py",
            "record-candidate",
            "--candidate",
            "candidate.json",
            "--checked-digest",
            candidate_check["checked_digest"],
        )
        held_candidate = receiver / candidate_record["candidate_path"]

        # 4. The owner adopts it explicitly, and only then does it appear.
        decision = self.checked(receiver, "development-direction.py", "example")
        decision["candidate_id"] = candidate["candidate_id"]
        decision["candidate_digest"] = "sha256:" + digest(held_candidate)
        (receiver / "decision.json").write_bytes(json_bytes(decision))
        decision_check = self.checked(
            receiver, "development-direction.py", "check-decision", "--decision", "decision.json"
        )
        decision_record = self.checked(
            receiver,
            "development-direction.py",
            "record-decision",
            "--decision",
            "decision.json",
            "--checked-digest",
            decision_check["checked_digest"],
        )
        held_decision = receiver / decision_record["decision_path"]
        self.checked(receiver, "development-direction.py", "render")

        direction = receiver / "docs/development-direction.md"
        self.assertIn(candidate["requested_behavior"], direction.read_text(encoding="utf-8"))
        # Manual prose sits outside the generated section on purpose.
        direction.write_text(direction.read_text(encoding="utf-8") + "\n" + MANUAL_PROSE, encoding="utf-8")

        plan_input = self.checked(receiver, "development-direction.py", "plan-input")
        self.assertEqual(plan_input["requirements"][0]["candidate_id"], candidate["candidate_id"])
        # Adoption is not admission: no numbered plan appeared anywhere.
        self.assertEqual(sorted(path.name for path in (receiver / "docs/plan/active").glob("[0-9]*.md")), [])

        before = {
            path: digest(path)
            for path in (
                held_report,
                held_candidate,
                held_decision,
                direction,
                receiver / "docs/agent/template-feedback.json",
                receiver / "AGENTS.md",
            )
        }
        local_policy = receiver / "docs/agent/local-project-rule.md"
        local_policy.write_text("A project-owned rule the template never wrote.\n", encoding="utf-8")
        before[local_policy] = digest(local_policy)

        # 5. A Copier update must leave every project-owned byte alone.
        update_source = self.tmp / "update-source"
        git(ROOT, "clone", "-q", str(self.source), str(update_source))
        git(update_source, "checkout", "-q", SOURCE_TAG)
        git(
            update_source,
            "-c",
            "user.name=CI",
            "-c",
            "user.email=ci@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "Exercise a template update over held improvement data",
        )
        head = run(["git", "-C", str(update_source), "rev-parse", "HEAD"], ROOT).stdout.strip()

        answers = receiver / ".copier-answers.yml"
        answers.write_text(
            "\n".join(
                f"_src_path: {update_source}" if line.startswith("_src_path:") else line
                for line in answers.read_text(encoding="utf-8").splitlines()
            )
            + "\n",
            encoding="utf-8",
        )
        git(receiver, "add", "-A")
        git(
            receiver,
            "-c",
            "user.name=CI",
            "-c",
            "user.email=ci@example.invalid",
            "commit",
            "-qm",
            "Hold improvement evidence, a requirement, a decision and a direction",
        )
        self.copier("update", "-q", "--trust", "--defaults", "--vcs-ref", head, str(receiver))

        for path, expected in before.items():
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"update removed {path}")
                self.assertEqual(digest(path), expected, f"update rewrote {path}")
        self.assertIn(MANUAL_PROSE.strip(), direction.read_text(encoding="utf-8"))
        rejected = sorted(str(path.relative_to(receiver)) for path in receiver.rglob("*.rej"))
        self.assertEqual(rejected, [], "a Copier update left unresolved conflicts")

        # 6. Validation behaviour still holds after the update.
        after = self.checked(receiver, "development-direction.py", "render", "--check")
        self.assertEqual(after["outcome"], "unchanged")
        listing = self.project_cli(receiver, "development-direction.py", "inspect")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn(decision["decision_id"], listing.stdout)
        self.assertIn("authenticates nobody", listing.stdout)

        # 7. The reporting project never received the receiver's records.
        self.assertFalse((reporter / "docs/improvements").exists())
        self.assertFalse((reporter / "docs/development-direction.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=0)
