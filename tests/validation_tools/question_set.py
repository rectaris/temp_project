"""Behavior checks for the plan-record question set builder."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT, load_module


SCRIPT = ROOT / "scripts/build-plan-question-set.py"
CASES = ROOT / "tests/fixtures/question-set/cases.json"
JANUARY = 1767225600  # 2026-01-01T00:00:00Z
CUTOFF = "2026-02-01T00:00:00Z"
AFTER_CUTOFF = 1769904000 + 3600
REMOVED = ("status", "successor_plans", "replan_contract", "replan_sources", "human_approval_status", "implementation_risk")


def plan_text(
    title: str,
    *,
    status: str = "backlog",
    label: str | None = "high",
    manifest: str = "",
    body: str = "",
    tasks: str = "- [ ] Do the work.\n",
) -> str:
    label_line = "" if label is None else f"implementation_risk: {label}\n"
    return (
        f"# {title}\n\n"
        f"status: {status}\n"
        "task_types:\n  - planning_docs\n"
        "human_approval_status: pending\n"
        f"{label_line}"
        "implementation_ambiguity: ordinary\n"
        f"{manifest}"
        "write_scope:\n  - scripts/example.py\n\n"
        "## Decisions\n\n- Keep it small.\n\n"
        f"## Tasks\n\n{tasks}{body}"
    )


def git_environment(when: int | None = None) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    if when is not None:
        stamp = f"@{when} +0000"
        environment.update({"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
    return environment


class HistoryRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)

    def git(self, *args: str, when: int | None = None) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, env=git_environment(when), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout

    def commit(self, when: int, files: dict[str, str | None]) -> str:
        for relative, text in files.items():
            path = self.root / relative
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"change at {when}", when=when)
        return self.git("rev-parse", "HEAD").strip()


class QuestionSetBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="question-set-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.module = load_module(SCRIPT, "build_plan_question_set")
        self.repo = HistoryRepository(self.base / "repo")

    def build(self, min_class_count: int = 1) -> dict:
        return self.module.build_report(self.repo.root, "HEAD", CUTOFF, min_class_count)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=self.repo.root, env=git_environment(),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    @staticmethod
    def by_file(report: dict) -> tuple[dict, dict]:
        return (
            {item["plan_file"]: item for item in report["questions"]},
            {item["plan_file"]: item for item in report["exclusions"]["plans"]},
        )

    def test_question_reads_the_revision_that_first_added_the_plan(self) -> None:
        authored = plan_text("Point in time", label="high")
        first = self.repo.commit(JANUARY, {"docs/plan/backlog/001-point.md": authored})
        self.repo.commit(
            JANUARY + 600,
            {
                "docs/plan/backlog/001-point.md": None,
                "docs/plan/checked/2026/01/01-15/001-point.md": plan_text(
                    "Point in time", status="checked", label="low", tasks="- [x] Do the work.\n",
                    body="\n## Validation Notes\n\n- Done.\n",
                ),
            },
        )
        report = self.build()
        self.assertEqual(report["exclusions"]["count"], 0)
        [question] = report["questions"]
        expected_input = authored.replace("status: backlog\n", "").replace(
            "human_approval_status: pending\n", ""
        ).replace("implementation_risk: high\n", "")
        self.assertEqual(question["source_commit"], first)
        self.assertEqual(question["source_path"], "docs/plan/backlog/001-point.md")
        self.assertEqual(question["current_path"], "docs/plan/checked/2026/01/01-15/001-point.md")
        self.assertEqual(question["label"], "high")
        self.assertEqual(question["input"], expected_input)
        self.assertEqual(
            question["input_sha256"], "sha256:" + hashlib.sha256(expected_input.encode()).hexdigest()
        )
        self.assertNotIn("Validation Notes", question["input"])

    def test_removed_fields_never_reach_an_emitted_question_input(self) -> None:
        lineage = (
            "successor_plans:\n  - docs/plan/active/002-lineage.md\n"
            "replan_contract: docs/plan/replanned/contracts/009-source.json\n"
            "replan_sources:\n  - docs/plan/active/009-source.md\n"
            "replan_source: docs/plan/active/008-older.md\n"
        )
        self.repo.commit(
            JANUARY,
            {
                "docs/plan/active/002-lineage.md": plan_text("Lineage", status="in_progress", manifest=lineage),
                "docs/plan/active/003-prose.md": plan_text(
                    "Prose", body="\n## Validation Notes\n\n- Keep the source at `status: deferred` for now.\n"
                ),
                "docs/plan/active/004-label-prose.md": plan_text(
                    "Label prose", body="\nUse bounded parent-direct work because implementation_risk is high.\n"
                ),
                "docs/plan/active/005-status-word.md": plan_text(
                    "Status word", body="\nReport the status of each run in one line.\n"
                ),
            },
        )
        questions, exclusions = self.by_file(self.build())
        self.assertEqual(sorted(questions), ["002-lineage.md", "005-status-word.md"])
        emitted = questions["002-lineage.md"]["input"]
        for name in (*REMOVED, "replan_source"):
            self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){name}\s*:", emitted), name)
        self.assertNotIn("docs/plan/active/009-source.md", emitted)
        self.assertNotIn("docs/plan/active/008-older.md", emitted)
        self.assertIn("implementation_ambiguity: ordinary\n", emitted)
        self.assertIn("write_scope:\n  - scripts/example.py\n", emitted)
        self.assertEqual(exclusions["003-prose.md"]["reasons"], ["leaked_field:status"])
        self.assertEqual(exclusions["004-label-prose.md"]["reasons"], ["leaked_field:implementation_risk"])

    def test_concurrent_additions_resolve_to_the_earliest_or_are_rejected(self) -> None:
        base = self.repo.commit(JANUARY, {"docs/plan/backlog/070-seed.md": plan_text("Seed")})
        self.repo.git("switch", "-q", "-c", "side")
        side = self.repo.commit(JANUARY + 100, {"docs/plan/backlog/071-shared.md": plan_text("Shared", label="high")})
        self.repo.commit(JANUARY + 300, {"docs/plan/backlog/072-tie.md": plan_text("Tie", label="high")})
        self.repo.git("switch", "-q", "main")
        self.repo.commit(
            JANUARY + 200,
            {"docs/plan/checked/2026/01/01-15/071-shared.md": plan_text("Shared", status="checked", label="low")},
        )
        self.repo.commit(JANUARY + 300, {"docs/plan/backlog/072-tie.md": plan_text("Tie", label="low")})
        self.repo.git("merge", "-q", "-X", "ours", "--no-edit", "side", when=JANUARY + 400)
        self.repo.git("rm", "-q", "docs/plan/backlog/071-shared.md")
        self.repo.git("commit", "-q", "-m", "drop duplicate", when=JANUARY + 500)
        questions, exclusions = self.by_file(self.build())
        self.assertEqual(sorted(questions), ["070-seed.md", "071-shared.md"])
        self.assertEqual(questions["070-seed.md"]["source_commit"], base)
        self.assertEqual(questions["071-shared.md"]["source_commit"], side)
        self.assertEqual(questions["071-shared.md"]["label"], "high")
        self.assertEqual(exclusions["072-tie.md"]["reasons"], ["source_revision_ambiguous"])

    def test_labels_outside_policy_are_excluded_by_name_not_normalized(self) -> None:
        duplicate = plan_text("Duplicate", label="high").replace(
            "implementation_risk: high\n", "implementation_risk: high\nimplementation_risk: low\n"
        )
        self.repo.commit(
            JANUARY,
            {
                "docs/plan/backlog/005-medium.md": plan_text("Medium", label="medium"),
                "docs/plan/backlog/006-capital.md": plan_text("Capital", label="High"),
                "docs/plan/backlog/007-missing.md": plan_text("Missing", label=None),
                "docs/plan/backlog/008-duplicate.md": duplicate,
                "docs/plan/backlog/009-valid.md": plan_text("Valid", label="ordinary"),
            },
        )
        report = self.build()
        questions, exclusions = self.by_file(report)
        self.assertEqual(sorted(questions), ["009-valid.md"])
        self.assertEqual(report["exclusions"]["count"], 4)
        self.assertEqual(
            {name: (entry["raw_label"], entry["reasons"]) for name, entry in exclusions.items()},
            {
                "005-medium.md": ("medium", ["label_out_of_policy"]),
                "006-capital.md": ("High", ["label_out_of_policy"]),
                "007-missing.md": (None, ["label_missing"]),
                "008-duplicate.md": (["high", "low"], ["label_ambiguous"]),
            },
        )
        self.assertEqual(exclusions["005-medium.md"]["source_path"], "docs/plan/backlog/005-medium.md")

    def test_plans_first_committed_after_execution_are_rejected(self) -> None:
        self.repo.commit(
            JANUARY,
            {
                "docs/plan/checked/2026/01/01-15/010-archived.md": plan_text("Archived", status="checked"),
                "docs/plan/active/011-done-task.md": plan_text(
                    "Done task", status="in_progress", tasks="- [x] Do the work.\n"
                ),
                "docs/plan/active/012-fresh.md": plan_text("Fresh", status="in_progress"),
            },
        )
        questions, exclusions = self.by_file(self.build())
        self.assertEqual(sorted(questions), ["012-fresh.md"])
        self.assertEqual(exclusions["010-archived.md"]["reasons"], ["recorded_after_execution"])
        self.assertEqual(exclusions["011-done-task.md"]["reasons"], ["completed_task_recorded"])

    def test_class_counts_report_majority_share_and_unmeasurable_classes(self) -> None:
        labels = ["high", "high", "high", "ordinary", "ordinary", "low"]
        self.repo.commit(
            JANUARY,
            {f"docs/plan/backlog/{20 + index:03d}-q.md": plan_text("Q", label=value) for index, value in enumerate(labels)},
        )
        statistics = self.build(min_class_count=2)["statistics"]["all"]
        self.assertEqual(statistics["total"], 6)
        self.assertEqual(statistics["classes"]["high"], {"count": 3, "measurable": True, "share": 0.5})
        self.assertEqual(statistics["classes"]["ordinary"]["share"], round(2 / 6, 6))
        self.assertEqual(statistics["classes"]["low"], {"count": 1, "measurable": False, "share": None})
        self.assertEqual(statistics["majority_class"], {"labels": ["high"], "count": 3, "share": 0.5})

    def test_partitions_split_by_time_and_keep_lineage_on_one_side(self) -> None:
        early = {
            "docs/plan/active/030-source.md": plan_text("Source"),
            "docs/plan/active/031-early.md": plan_text("Early", label="low"),
            "docs/plan/active/032-contract-early.md": plan_text(
                "Contract early", manifest="replan_contract: docs/plan/replanned/contracts/099-gone.json\n"
            ),
        }
        self.repo.commit(JANUARY, early)
        self.repo.commit(
            AFTER_CUTOFF,
            {
                "docs/plan/active/030-source.md": plan_text(
                    "Source", manifest="successor_plans:\n  - docs/plan/active/033-successor.md\n"
                ),
                "docs/plan/active/033-successor.md": plan_text("Successor", status="deferred"),
                "docs/plan/active/034-contract-late.md": plan_text(
                    "Contract late", manifest="replan_contract: docs/plan/replanned/contracts/099-gone.json\n"
                ),
                "docs/plan/active/035-late.md": plan_text("Late", label="ordinary"),
            },
        )
        report = self.build()
        questions, _ = self.by_file(report)
        self.assertEqual(
            {name: item["partition"] for name, item in questions.items()},
            {
                "030-source.md": "tuning",
                "031-early.md": "tuning",
                "032-contract-early.md": "tuning",
                "033-successor.md": "tuning",
                "034-contract-late.md": "tuning",
                "035-late.md": "holdout",
            },
        )
        self.assertEqual(questions["033-successor.md"]["lineage_group"], "030-source")
        self.assertEqual(questions["034-contract-late.md"]["lineage_group"], "032-contract-early")
        self.assertNotIn("successor_plans", questions["030-source.md"]["input"])
        self.assertEqual(report["partitions"]["tuning_questions_committed_at_or_after_holdout_from"], 2)
        tuning = report["statistics"]["tuning"]
        self.assertEqual({key: value["count"] for key, value in tuning["classes"].items()}, {"low": 1, "ordinary": 0, "high": 4})
        self.assertEqual(report["statistics"]["holdout"]["total"], 1)

    def test_command_prints_to_stdout_and_writes_nothing_into_the_repository(self) -> None:
        self.repo.commit(JANUARY, {"docs/plan/backlog/040-one.md": plan_text("One")})
        self.repo.commit(AFTER_CUTOFF, {"docs/plan/backlog/041-two.md": plan_text("Two", label="low")})

        def snapshot() -> dict[str, bytes]:
            return {
                path.relative_to(self.repo.root).as_posix(): path.read_bytes()
                for path in sorted(self.repo.root.rglob("*")) if path.is_file()
            }

        before = snapshot()
        result = self.run_cli("build", "--holdout-from", CUTOFF, "--min-class-count", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot(), before)
        report = json.loads(result.stdout)
        self.assertEqual({item["question_id"]: item["partition"] for item in report["questions"]}, {"040-one": "tuning", "041-two": "holdout"})

    def test_verify_regenerates_a_saved_report_and_names_tampered_questions(self) -> None:
        first = self.repo.commit(JANUARY, {"docs/plan/backlog/050-one.md": plan_text("One")})
        self.repo.commit(JANUARY + 60, {"docs/plan/backlog/051-two.md": plan_text("Two", label="low")})
        built = self.run_cli("build", "--holdout-from", CUTOFF)
        self.assertEqual(built.returncode, 0, built.stderr)
        saved = self.base / "saved.json"
        saved.write_text(built.stdout, encoding="utf-8")
        verified = self.run_cli("verify", str(saved))
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertTrue(json.loads(verified.stdout)["verified"])

        report = json.loads(built.stdout)
        for field, value in (("source_commit", first), ("label", "high"), ("input", "# Two\n")):
            tampered = json.loads(built.stdout)
            question = next(item for item in tampered["questions"] if item["question_id"] == "051-two")
            self.assertNotEqual(question[field], value)
            question[field] = value
            saved.write_text(json.dumps(tampered), encoding="utf-8")
            result = self.run_cli("verify", str(saved))
            self.assertEqual(result.returncode, 1, field)
            self.assertEqual(json.loads(result.stdout)["mismatched_questions"], ["051-two"], field)
        self.assertEqual(len(report["questions"]), 2)

    def test_enumeration_and_source_size_are_bounded(self) -> None:
        self.repo.commit(
            JANUARY,
            {
                "docs/plan/backlog/060-small.md": plan_text("Small"),
                "docs/plan/backlog/061-large.md": plan_text("Large", body="x" * 4096 + "\n"),
            },
        )
        with mock.patch.object(self.module, "MAX_PLAN_BYTES", 2048):
            with self.assertRaisesRegex(self.module.QuestionSetError, "lineage record exceeds .*061-large.md"):
                self.build()
        self.repo.commit(JANUARY + 60, {"docs/plan/backlog/061-large.md": plan_text("Large")})
        with mock.patch.object(self.module, "MAX_PLAN_BYTES", 2048):
            questions, exclusions = self.by_file(self.build())
        self.assertEqual(sorted(questions), ["060-small.md"])
        self.assertEqual(exclusions["061-large.md"]["reasons"], ["oversized_source"])
        with mock.patch.object(self.module, "MAX_PLANS", 1):
            with self.assertRaisesRegex(self.module.QuestionSetError, "exceed the bound"):
                self.build()


class CommittedQuestionCasesTest(unittest.TestCase):
    def test_committed_tuning_cases_regenerate_from_repository_history(self) -> None:
        module = load_module(SCRIPT, "build_plan_question_set_cases")
        fixture = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(fixture["label_field"], module.LABEL_FIELD)
        report = module.build_report(ROOT, "HEAD", module.DEFAULT_HOLDOUT_FROM, module.DEFAULT_MIN_CLASS_COUNT)
        questions = {item["plan_file"]: item for item in report["questions"]}
        self.assertTrue(fixture["cases"])
        for case in fixture["cases"]:
            with self.subTest(case=case["plan_file"]):
                self.assertIs(case["used_for_tuning"], True)
                self.assertEqual(case["partition"], "tuning")
                question = questions[case["plan_file"]]
                for key in ("source_path", "source_commit", "label", "input_sha256", "partition"):
                    self.assertEqual(question[key], case[key], key)
