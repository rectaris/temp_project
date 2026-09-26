"""Behavior checks for the offline weighted feature scoring command."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .question_set import AFTER_CUTOFF, CUTOFF, JANUARY, HistoryRepository, git_environment, plan_text
from .support import ROOT, load_module


SCRIPT = ROOT / "scripts/score-plan-features.py"
QUESTION_SET_SCRIPT = ROOT / "scripts/build-plan-question-set.py"
PROTOCOL = ROOT / "tests/fixtures/feature-scoring/evaluation-protocol.md"
CASES = ROOT / "tests/fixtures/feature-scoring/cases.json"
MIN_CLASS_COUNT = 2
# Synthetic holdout questions built by the test only; no holdout is committed as a fixture.
HOLDOUT = (
    ("901-synthetic-holdout-high-a.md", "high", {"change_breadth": 0.88, "authority_surface": 0.85}),
    ("902-synthetic-holdout-high-b.md", "high", {"change_breadth": 0.82, "authority_surface": 0.9}),
    ("903-synthetic-holdout-high-c.md", "high", {"change_breadth": 0.2, "authority_surface": 0.2}),
    ("904-synthetic-holdout-ordinary-a.md", "ordinary", {"change_breadth": 0.5, "authority_surface": 0.5}),
    ("905-synthetic-holdout-ordinary-b.md", "ordinary", {"change_breadth": 0.6, "authority_surface": 0.45}),
    ("906-synthetic-holdout-low-a.md", "low", {"change_breadth": 0.1, "authority_surface": 0.1}),
)
OFFLINE_BOOTSTRAP = """\
import runpy
import socket
import sys


def refuse(*args, **kwargs):
    raise OSError("socket creation disabled")


socket.socket = refuse
socket.create_connection = refuse
socket.socketpair = refuse
socket.fromfd = refuse
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
"""


def question_id(plan_file: str) -> str:
    return plan_file[: -len(".md")]


def tree_digest(root: Path) -> str:
    """Digest every path, mode, and byte below root, including the Git directory."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        info = path.lstat()
        digest.update(relative + b"\0" + oct(info.st_mode).encode() + b"\0")
        if path.is_symlink():
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class FeatureScoringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="feature-scoring-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.module = load_module(SCRIPT, "score_plan_features")
        self.question_module = load_module(QUESTION_SET_SCRIPT, "build_plan_question_set_feature_scoring")
        self.cases = json.loads(CASES.read_text(encoding="utf-8"))
        self.repo = HistoryRepository(self.base / "repo")
        tuning = {
            f"docs/plan/backlog/{case['plan_file']}": plan_text(case["case_id"], label=case["label"])
            for case in self.cases["tuning_cases"]
        }
        tuning[self.module.PROTOCOL_PATH] = PROTOCOL.read_text(encoding="utf-8")
        self.repo.commit(JANUARY, tuning)
        self.repo.commit(
            AFTER_CUTOFF,
            {f"docs/plan/backlog/{name}": plan_text(name, label=label) for name, label, _ in HOLDOUT},
        )
        self.question_set = self.question_module.build_report(self.repo.root, "HEAD", CUTOFF, MIN_CLASS_COUNT)
        self.questions = {item["question_id"]: item for item in self.question_set["questions"]}
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.question_set_path = self.write("question-set.json", self.question_set)
        self.dimensions_path = self.write("dimensions.json", self.cases["dimensions"])
        self.dimensions_sha256 = self.module.digest(self.cases["dimensions"])
        self.tuning_scores = self.scores(
            [(question_id(case["plan_file"]), case["values"]) for case in self.cases["tuning_cases"]]
        )
        self.holdout_scores = self.scores([(question_id(name), values) for name, _, values in HOLDOUT])
        self.ledger = self.outside / "holdout.ledger"

    def write(self, name: str, value: object) -> Path:
        path = self.outside / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def scores(self, entries: list[tuple[str, dict]]) -> dict:
        return {
            "schema_version": 1,
            "kind": "feature_scores",
            "dimensions_sha256": self.dimensions_sha256,
            "recorder": {"identity": "synthetic-fixture", "model_id": "none"},
            "scores": [
                {
                    "question_id": identifier,
                    "input_sha256": self.questions[identifier]["input_sha256"],
                    "values": dict(values),
                }
                for identifier, values in entries
            ],
        }

    def fit(self, scores: dict | None = None) -> dict:
        path = self.write("tuning-scores.json", self.tuning_scores if scores is None else scores)
        return self.module.fit(self.repo.root, self.question_set_path, self.dimensions_path, path)

    def score(self, weights: dict, scores: dict | None = None, ledger: Path | None = None) -> dict:
        weights_path = self.write("weights.json", weights)
        scores_path = self.write("holdout-scores.json", self.holdout_scores if scores is None else scores)
        return self.module.score_holdout(
            self.repo.root, self.question_set_path, self.dimensions_path, scores_path, weights_path,
            self.ledger if ledger is None else ledger,
        )

    def report(self, scoring: dict) -> dict:
        return self.module.report(self.repo.root, self.write("scoring.json", scoring), self.ledger)

    def run_offline(self, script: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-I", "-c", OFFLINE_BOOTSTRAP, str(script), *args],
            cwd=self.repo.root, env=git_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def test_fit_accepts_only_a_question_set_that_passes_verify(self) -> None:
        tampered = copy.deepcopy(self.question_set)
        first = next(item for item in tampered["questions"] if item["partition"] == "tuning")
        first["label"] = "low" if first["label"] != "low" else "high"
        self.question_set_path = self.write("question-set.json", tampered)
        with mock.patch.object(self.module, "fit_weights", side_effect=AssertionError("fitted")):
            with self.assertRaisesRegex(self.module.FeatureScoringError, "does not pass verify.*" + first["question_id"]):
                self.fit()

    def test_fit_refuses_holdout_unjoined_mismatched_and_out_of_range_records_before_fitting(self) -> None:
        holdout = question_id(HOLDOUT[0][0])
        tuning = self.tuning_scores["scores"][0]["question_id"]

        def edited(change) -> dict:
            scores = copy.deepcopy(self.tuning_scores)
            change(scores["scores"])
            return scores

        cases = {
            "is a holdout question; fit accepts only tuning": edited(
                lambda records: records.append(copy.deepcopy(self.holdout_scores["scores"][0]))
            ),
            "names no question": edited(lambda records: records[0].update(question_id="999-absent")),
            "input_sha256 does not match": edited(lambda records: records[0].update(input_sha256="sha256:" + "0" * 64)),
            "must lie from 0 to 1, got 1.5": edited(lambda records: records[0]["values"].update(change_breadth=1.5)),
            "must lie from 0 to 1, got -0.1": edited(lambda records: records[0]["values"].update(change_breadth=-0.1)),
            "must score exactly the dimensions": edited(lambda records: records[0]["values"].pop("change_breadth")),
            "unexpected \\['partition'\\]": edited(lambda records: records[0].update(partition="tuning")),
            f"score record {tuning} is repeated": edited(lambda records: records.append(copy.deepcopy(records[0]))),
        }
        for message, scores in cases.items():
            with self.subTest(message=message):
                with mock.patch.object(self.module, "fit_weights", side_effect=AssertionError("fitted")):
                    with self.assertRaisesRegex(self.module.FeatureScoringError, message):
                        self.fit(scores)
        self.assertIn(holdout, self.questions)
        text = self.write("nan.json", self.tuning_scores).read_text(encoding="utf-8").replace("0.15", "NaN", 1)
        (self.outside / "nan.json").write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(self.module.FeatureScoringError, "non-finite number NaN"):
            self.module.fit(self.repo.root, self.question_set_path, self.dimensions_path, self.outside / "nan.json")

    def test_fit_is_deterministic_order_independent_and_uses_protocol_parameters(self) -> None:
        weights = self.fit()
        reordered = copy.deepcopy(self.tuning_scores)
        reordered["scores"].reverse()
        again = self.fit(reordered)
        self.assertNotEqual(again.pop("scores_sha256"), weights["scores_sha256"])
        self.assertEqual(again, {key: value for key, value in weights.items() if key != "scores_sha256"})
        self.assertEqual(self.module.encode(self.fit()), self.module.encode(self.fit()))
        self.assertEqual(weights["fit"], {"learning_rate": 0.1, "iterations": 2000, "l2_weight": 0.01})
        self.assertEqual(weights["question_set"]["tuning_fitted"], len(self.cases["tuning_cases"]))
        self.assertEqual(weights["question_set"]["tuning_missing"], [])
        protocol = PROTOCOL.read_text(encoding="utf-8").replace('"iterations": 2000', '"iterations": 10')
        self.repo.commit(AFTER_CUTOFF + 60, {self.module.PROTOCOL_PATH: protocol})
        short = self.fit()
        self.assertEqual(short["fit"]["iterations"], 10)
        self.assertNotEqual(short["weights"], weights["weights"])

    def test_score_holdout_ledger_must_lie_outside_the_worktree(self) -> None:
        weights = self.fit()
        inside_repo = self.repo.root / "holdout.ledger"
        inside_tool = ROOT / f"{self.base.name}.ledger"
        self.repo.git("worktree", "add", "-q", "--detach", str(self.base / "linked"))
        linked = self.base / "linked" / "holdout.ledger"
        for location in (inside_repo, inside_tool, self.repo.root / ".git" / "holdout.ledger", linked):
            with self.subTest(location=str(location)):
                with self.assertRaisesRegex(self.module.FeatureScoringError, "outside the repository worktree"):
                    self.score(weights, ledger=location)
                self.assertFalse(location.exists())
        internal = self.repo.root / "hardlinked.ledger"
        internal.write_bytes(b"")
        internal.chmod(0o600)
        alias = self.outside / "alias.ledger"
        os.link(internal, alias)
        with self.assertRaisesRegex(self.module.FeatureScoringError, "exactly one link"):
            self.score(weights, ledger=alias)
        self.assertEqual(internal.read_bytes(), b"")
        target = self.outside / "target.ledger"
        target.write_bytes(b"")
        target.chmod(0o600)
        link = self.outside / "link.ledger"
        link.symlink_to(target)
        with self.assertRaisesRegex(self.module.FeatureScoringError, "without following a link"):
            self.score(weights, ledger=link)
        target.chmod(0o644)
        with self.assertRaisesRegex(self.module.FeatureScoringError, "mode 0600"):
            self.score(weights, ledger=target)
        self.assertEqual(target.read_bytes(), b"")

    def test_score_holdout_refuses_a_second_scoring_for_a_recorded_key(self) -> None:
        weights = self.fit()
        scoring = self.score(weights)
        self.assertEqual(self.ledger.stat().st_mode & 0o777, 0o600)
        material = scoring["key_material"]
        holdout_digests = sorted(self.questions[question_id(name)]["input_sha256"] for name, _, _ in HOLDOUT)
        self.assertEqual(
            material,
            {
                "source_commit": self.question_set["revision"]["commit"],
                "holdout_input_sha256s": holdout_digests,
                "dimensions_sha256": self.dimensions_sha256,
                "weights_sha256": self.module.digest(weights),
                "band_thresholds_sha256": self.module.digest(self.module.parse_protocol(PROTOCOL.read_text())["bands"]),
            },
        )
        self.assertEqual(scoring["key"], self.module.digest(material))
        [entry] = [json.loads(line) for line in self.ledger.read_text().splitlines()]
        self.assertEqual(entry["key"], scoring["key"])
        self.assertEqual(entry["scoring_sha256"], self.module.digest(scoring))
        before = self.ledger.read_bytes()
        with mock.patch.object(self.module, "predict", side_effect=AssertionError("scored")):
            with self.assertRaisesRegex(self.module.FeatureScoringError, "already scored for key"):
                self.score(weights)
            reordered = copy.deepcopy(self.holdout_scores)
            reordered["scores"].reverse()
            with self.assertRaisesRegex(self.module.FeatureScoringError, "already scored for key"):
                self.score(weights, reordered)
        self.assertEqual(self.ledger.read_bytes(), before)
        refit = copy.deepcopy(self.tuning_scores)
        refit["scores"].pop()
        other = self.score(self.fit(refit))
        self.assertNotEqual(other["key"], scoring["key"])
        self.assertEqual(len(self.ledger.read_text().splitlines()), 2)

    def test_score_holdout_refuses_tuning_records_and_rebound_inputs_before_recording(self) -> None:
        weights = self.fit()
        with_tuning = copy.deepcopy(self.holdout_scores)
        with_tuning["scores"].append(copy.deepcopy(self.tuning_scores["scores"][0]))
        with self.assertRaisesRegex(self.module.FeatureScoringError, "score-holdout accepts only holdout"):
            self.score(weights, with_tuning)
        rebound = copy.deepcopy(weights)
        rebound["dimensions_sha256"] = "sha256:" + "1" * 64
        with self.assertRaisesRegex(self.module.FeatureScoringError, "different dimensions"):
            self.score(rebound)
        protocol = PROTOCOL.read_text(encoding="utf-8").replace('"lower_inclusive": 0.7', '"lower_inclusive": 0.8')
        self.repo.commit(AFTER_CUTOFF + 60, {self.module.PROTOCOL_PATH: protocol})
        with self.assertRaisesRegex(self.module.FeatureScoringError, "different committed protocol"):
            self.score(weights)
        self.assertFalse(self.ledger.exists())

    def test_report_pairs_every_accuracy_with_its_baseline_and_names_thin_classes(self) -> None:
        scoring = self.score(self.fit())
        self.assertEqual(scoring["baseline_class"], "high")
        result = self.report(scoring)
        self.assertEqual(result["coverage"]["holdout_expected"], len(HOLDOUT))
        self.assertEqual(result["coverage"]["holdout_missing"], [])
        overall = result["overall"]
        self.assertEqual(overall["count"], len(HOLDOUT))
        self.assertEqual(overall["baseline"], {"majority_class": "high", "count": 6, "correct": 3, "accuracy": 0.5})
        self.assertEqual(result["classes"]["low"], {
            "count": 1, "status": "not_measurable", "correct": None, "accuracy": None, "baseline": None,
        })
        self.assertEqual(result["not_measurable_classes"], ["low"])
        self.assertEqual(result["classes"]["ordinary"]["baseline"]["count"], 2)
        self.assertEqual(result["classes"]["ordinary"]["baseline"]["accuracy"], 0.0)
        self.assertEqual(result["classes"]["high"]["baseline"]["accuracy"], 1.0)
        self.assertEqual(sum(band["count"] for band in result["bands"].values()), len(HOLDOUT))
        for name, band in result["bands"].items():
            with self.subTest(band=name):
                if band["status"] == "measured":
                    self.assertEqual(band["baseline"]["count"], band["count"])
                else:
                    self.assertIsNone(band["accuracy"])
                    self.assertIn(f"band_not_measurable:{name}", result["blockers"])
        self.assertEqual(result["blockers"], ["band_not_measurable:middle", "band_not_measurable:low"])
        self.assertEqual(result["outcome"], "insufficient_evidence")
        self.assertEqual(self.module.encode_report(result), self.module.encode_report(self.report(scoring)))

    def test_report_writer_refuses_an_accuracy_without_a_paired_baseline(self) -> None:
        result = self.report(self.score(self.fit()))
        self.module.encode_report(result)
        edits = {
            "overall lacks a paired baseline": lambda value: value["overall"].update(baseline=None),
            "class high lacks a paired baseline": lambda value: value["classes"]["high"]["baseline"].update(count=99),
            "class ordinary lacks a paired baseline": lambda value: value["classes"]["ordinary"]["baseline"].pop(
                "accuracy"
            ),
            "class low is not measurable but carries an accuracy": lambda value: value["classes"]["low"].update(
                accuracy=1.0
            ),
        }
        for message, edit in edits.items():
            with self.subTest(message=message):
                broken = copy.deepcopy(result)
                edit(broken)
                with self.assertRaisesRegex(self.module.FeatureScoringError, message):
                    self.module.encode_report(broken)

    def test_bands_follow_protocol_thresholds_and_outcomes_follow_limits(self) -> None:
        protocol = self.module.parse_protocol(PROTOCOL.read_text(encoding="utf-8"))

        def record(label: str, predicted: str | None, confidence: float | None) -> dict:
            return {
                "question_id": f"q-{label}-{confidence}", "input_sha256": "sha256:" + "2" * 64, "label": label,
                "scored": predicted is not None, "predicted": predicted, "confidence": confidence,
                "probabilities": None,
            }

        records = [
            record("high", "high", 0.7), record("ordinary", "ordinary", 0.95),
            record("high", "high", 0.6999), record("ordinary", "ordinary", 0.5),
            record("low", "low", 0.4999), record("ordinary", "low", 0.34),
        ]
        scoring = {
            "key": "sha256:" + "3" * 64, "key_material": {"weights_sha256": "sha256:" + "4" * 64},
            "question_set_sha256": "sha256:" + "5" * 64, "protocol_sha256": self.module.digest(protocol),
            "scores_sha256": "sha256:" + "6" * 64, "recorder": {"identity": "synthetic", "model_id": "none"},
            "min_class_count": 2, "baseline_class": "ordinary", "bands": protocol["bands"],
            "decision_limits": protocol["decision_limits"],
            "tuning_coverage": {"expected": 3, "fitted": 3, "missing": []}, "holdout_missing": [], "records": records,
        }
        result = self.module.evaluate(scoring)
        self.assertEqual({name: band["count"] for name, band in result["bands"].items()}, {"high": 2, "middle": 2, "low": 2})
        self.assertEqual(result["bands"]["low"]["accuracy"], 0.5)
        self.assertEqual(result["bands"]["low"]["baseline"]["accuracy"], 0.5)
        self.assertEqual(result["bands"]["middle"]["upper_exclusive"], 0.7)
        self.assertEqual(result["overall"]["accuracy"], round(5 / 6, 6))
        self.assertEqual(result["overall"]["baseline"]["accuracy"], 0.5)
        self.assertEqual(result["not_measurable_classes"], ["low"])
        self.assertEqual((result["outcome"], result["blockers"]), ("meets_limits", []))
        self.module.encode_report(result)
        below = copy.deepcopy(scoring)
        below["decision_limits"] = {"min_overall_accuracy_gain_over_baseline": 0.5}
        self.assertEqual(self.module.evaluate(below)["outcome"], "below_limits")
        thin = copy.deepcopy(scoring)
        thin["records"] = records[:4] + [record("low", None, None), record("ordinary", None, None)]
        thin["holdout_missing"] = ["q-low-None", "q-ordinary-None"]
        thin_result = self.module.evaluate(thin)
        self.assertEqual(thin_result["overall"]["count"], 6)
        self.assertEqual(thin_result["overall"]["correct"], 4)
        self.assertEqual(thin_result["unbanded_unscored"], 2)
        self.assertEqual(thin_result["bands"]["low"]["status"], "not_measurable")
        self.assertEqual(thin_result["outcome"], "insufficient_evidence")
        self.assertEqual(thin_result["blockers"], ["holdout_coverage_incomplete", "band_not_measurable:low"])
        untuned = copy.deepcopy(scoring)
        untuned["tuning_coverage"]["missing"] = ["q-missing"]
        self.assertEqual(self.module.evaluate(untuned)["blockers"], ["tuning_coverage_incomplete"])

    def test_report_accepts_only_the_scoring_recorded_in_the_ledger(self) -> None:
        scoring = self.score(self.fit())
        tampered = copy.deepcopy(scoring)
        tampered["records"][0]["predicted"] = "low" if tampered["records"][0]["predicted"] != "low" else "high"
        with self.assertRaisesRegex(self.module.FeatureScoringError, "not the one recorded in the ledger"):
            self.report(tampered)
        rekeyed = copy.deepcopy(scoring)
        rekeyed["key_material"]["weights_sha256"] = "sha256:" + "7" * 64
        with self.assertRaisesRegex(self.module.FeatureScoringError, "key does not match its key material"):
            self.report(rekeyed)
        self.ledger = self.outside / "other.ledger"
        with self.assertRaisesRegex(self.module.FeatureScoringError, "ledger does not exist"):
            self.report(scoring)

    def test_commands_run_offline_and_leave_the_repository_unchanged(self) -> None:
        probe_script = self.outside / "probe.py"
        probe_script.write_text("import socket\nsocket.socket()\n", encoding="utf-8")
        probe = subprocess.run(
            [sys.executable, "-I", "-c", OFFLINE_BOOTSTRAP, str(probe_script)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertNotEqual(probe.returncode, 0)
        self.assertIn(b"socket creation disabled", probe.stderr)
        # Run committed copies of the tool from inside the history repository, so the tree
        # digest also covers the tool checkout, including any bytecode cache an import writes.
        self.repo.commit(
            AFTER_CUTOFF + 60,
            {f"scripts/{path.name}": path.read_text(encoding="utf-8") for path in (SCRIPT, QUESTION_SET_SCRIPT)},
        )
        script = self.repo.root / "scripts" / SCRIPT.name
        tuning_path = self.write("tuning-scores.json", self.tuning_scores)
        holdout_path = self.write("holdout-scores.json", self.holdout_scores)
        before = tree_digest(self.repo.root)
        common = ("--question-set", str(self.question_set_path), "--dimensions", str(self.dimensions_path))
        fitted = self.run_offline(script, "fit", *common, "--scores", str(tuning_path))
        self.assertEqual(fitted.returncode, 0, fitted.stderr.decode())
        self.assertEqual(self.run_offline(script, "fit", *common, "--scores", str(tuning_path)).stdout, fitted.stdout)
        weights_path = self.outside / "weights.json"
        weights_path.write_bytes(fitted.stdout)
        holdout = ("--scores", str(holdout_path), "--weights", str(weights_path), "--ledger", str(self.ledger))
        scored = self.run_offline(script, "score-holdout", *common, *holdout)
        self.assertEqual(scored.returncode, 0, scored.stderr.decode())
        again = self.run_offline(script, "score-holdout", *common, *holdout)
        self.assertEqual(again.returncode, 2)
        self.assertIn(b"already scored", again.stderr)
        self.assertEqual(again.stdout, b"")
        scoring_path = self.outside / "scoring.json"
        scoring_path.write_bytes(scored.stdout)
        reported = self.run_offline(script, "report", "--scoring", str(scoring_path), "--ledger", str(self.ledger))
        self.assertEqual(reported.returncode, 0, reported.stderr.decode())
        self.assertEqual(json.loads(reported.stdout)["kind"], "feature_scoring_report")
        inside = self.run_offline(script, "report", "--scoring", str(scoring_path), "--ledger", "holdout.ledger")
        self.assertEqual(inside.returncode, 2)
        self.assertFalse((self.repo.root / "scripts" / "__pycache__").exists())
        self.assertEqual(tree_digest(self.repo.root), before)


class CommittedFeatureScoringCasesTest(unittest.TestCase):
    def test_committed_protocol_and_cases_are_synthetic_tuning_inputs(self) -> None:
        module = load_module(SCRIPT, "score_plan_features_cases")
        protocol = module.parse_protocol(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(protocol["classes"], list(module.CLASSES))
        fixture = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(fixture["fixture_kind"], "synthetic")
        self.assertIs(fixture["holdout"]["present"], False)
        path = Path(tempfile.mkdtemp(prefix="feature-scoring-cases-")) / "dimensions.json"
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        path.write_text(json.dumps(fixture["dimensions"]), encoding="utf-8")
        identifiers, _ = module.load_dimensions(path)
        self.assertTrue(fixture["tuning_cases"])
        for case in fixture["tuning_cases"]:
            with self.subTest(case=case["case_id"]):
                self.assertIs(case["used_for_tuning"], True)
                self.assertIn(case["label"], module.CLASSES)
                self.assertEqual(sorted(case["values"]), sorted(identifiers))
