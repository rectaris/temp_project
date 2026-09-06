"""Plan authoring input tests: what the deterministic check decides, and what it does not."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import PLAN_AUTHORING_MODULES, PLANLIB, ROOT, load_module


FIXTURES = ROOT / "tests/fixtures/plan-authoring"
ROOT_COMMAND = ROOT / "scripts/create-root-plan.py"


class PlanAuthoringTest(unittest.TestCase):
    @staticmethod
    def module():
        return load_module(PLAN_AUTHORING_MODULES[0], "plan_authoring_under_test")

    @staticmethod
    def load_cases(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def make_repository(self, directory: Path) -> Path:
        (directory / "docs/plan/active").mkdir(parents=True)
        (directory / "docs/plan/backlog").mkdir(parents=True)
        (directory / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nNo active development items.\n", encoding="utf-8"
        )
        return directory

    def run_command(self, root: Path, *args: str):
        return subprocess.run(
            [sys.executable, str(ROOT_COMMAND), "--root", str(root), *args],
            capture_output=True,
            text=True,
        )

    def write_input(self, directory: Path, document: dict, name: str = "input.json") -> Path:
        path = directory / name
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_root_and_template_libraries_are_byte_identical(self):
        root_bytes = PLAN_AUTHORING_MODULES[0].read_bytes()
        template_bytes = PLAN_AUTHORING_MODULES[1].read_bytes()
        self.assertEqual(root_bytes, template_bytes)

    def test_fixture_cases_decide_as_recorded(self):
        module = self.module()
        for fixture_name in ("cases.json", "holdout.json"):
            fixture = self.load_cases(fixture_name)
            for outcome in fixture["observed_outcomes"]:
                self.assertTrue(outcome["decision_matched"], outcome)
            for case in fixture["cases"]:
                with self.subTest(fixture=fixture_name, case=case["id"]):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = self.make_repository(Path(tmp))
                        source = self.write_input(root, case["input"])
                        profile = case["input"]["profile"]
                        if case["expect"] == "accept":
                            module.check_authoring_input(root, source, profile=profile)
                            continue
                        with self.assertRaises(module.AuthoringError) as caught:
                            module.check_authoring_input(root, source, profile=profile)
                        self.assertIn(case["expect_error_contains"], str(caught.exception))

    def test_holdout_fixture_is_not_used_for_tuning(self):
        self.assertFalse(self.load_cases("holdout.json")["used_for_tuning"])
        self.assertTrue(self.load_cases("cases.json")["used_for_tuning"])

    def accepted_case(self, profile: str) -> dict:
        for case in self.load_cases("cases.json")["cases"]:
            if case["expect"] == "accept" and case["input"]["profile"] == profile:
                return case["input"]
        raise AssertionError(f"no accepted {profile} case")

    def test_check_writes_nothing_and_write_reproduces_the_checked_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            source = self.write_input(root, self.accepted_case("root"))
            before = sorted(p.name for p in (root / "docs/plan/active").iterdir())
            index_before = (root / "docs/plan/plan.md").read_text(encoding="utf-8")

            checked = self.run_command(root, "check", "--input", str(source), "--print-digest")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            digest = checked.stdout.strip()
            self.assertEqual(
                digest, "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            )
            self.assertEqual(sorted(p.name for p in (root / "docs/plan/active").iterdir()), before)
            self.assertEqual((root / "docs/plan/plan.md").read_text(encoding="utf-8"), index_before)

            written = self.run_command(
                root, "write", "--input", str(source), "--expect-input-sha256", digest
            )
            self.assertEqual(written.returncode, 0, written.stderr)
            plan_path = root / written.stdout.strip()
            self.assertTrue(plan_path.is_file())
            self.assertIn(written.stdout.strip(), (root / "docs/plan/plan.md").read_text(encoding="utf-8"))

    def test_write_refuses_an_input_that_changed_after_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            document = self.accepted_case("root")
            source = self.write_input(root, document)
            digest = self.run_command(
                root, "check", "--input", str(source), "--print-digest"
            ).stdout.strip()

            document["summary"] = "A different summary that was never checked"
            self.write_input(root, document)
            written = self.run_command(
                root, "write", "--input", str(source), "--expect-input-sha256", digest
            )

            self.assertNotEqual(written.returncode, 0)
            self.assertIn("changed since it was checked", written.stderr)
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])
            self.assertEqual(
                (root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                "# Active Plan\n\nNo active development items.\n",
            )

    def test_malformed_active_index_stops_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            malformed = "# Active Plan\n\nid\tpath\tstatus\n001\tdocs/plan/active/a.md\tnot_a_status\n"
            (root / "docs/plan/plan.md").write_text(malformed, encoding="utf-8")
            source = self.write_input(root, self.accepted_case("root"))

            checked = self.run_command(root, "check", "--input", str(source), "--print-digest")
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("active plan index is invalid", checked.stderr)
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])
            self.assertEqual((root / "docs/plan/plan.md").read_text(encoding="utf-8"), malformed)

    def test_backlog_rendering_leaves_the_active_index_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            document = self.accepted_case("root")
            document["lifecycle"] = "backlog"
            source = self.write_input(root, document)
            digest = self.run_command(
                root, "check", "--input", str(source), "--print-digest"
            ).stdout.strip()
            written = self.run_command(
                root, "write", "--input", str(source), "--expect-input-sha256", digest
            )

            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertTrue(written.stdout.strip().startswith("docs/plan/backlog/"))
            self.assertEqual(
                (root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                "# Active Plan\n\nNo active development items.\n",
            )

    def test_rendered_plan_satisfies_the_admission_and_witness_contracts(self):
        planlib = load_module(PLANLIB, "planlib_for_plan_authoring")
        for profile in ("root", "generated"):
            with self.subTest(profile=profile):
                with tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    source = self.write_input(root, self.accepted_case(profile))
                    module = self.module()
                    digest, _ = module.check_authoring_input(root, source, profile=profile)
                    path = module.write_authoring_input(
                        root, source, expected_digest=digest, profile=profile
                    )
                    parsed = planlib.parse_manifest_text(
                        (root / path).read_text(encoding="utf-8")
                    )
                    planlib.validate_admission_record(parsed)
                    self.assertEqual(len(planlib.validate_validation_witness_map(parsed)), 2)

    def test_claim_wording_does_not_change_the_structural_decision(self):
        """The check proves references and digests, never that a witness establishes a condition."""

        module = self.module()
        truthful = self.accepted_case("root")
        misleading = json.loads(json.dumps(truthful))
        for witness in misleading["witnesses"]:
            witness["claim"] = "Proves every property this repository will ever need."

        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            first = self.write_input(root, truthful, "a.json")
            second = self.write_input(root, misleading, "b.json")
            _, truthful_report = module.check_authoring_input(root, first, profile="root")
            _, misleading_report = module.check_authoring_input(root, second, profile="root")

        def structural(report: str) -> list[str]:
            return [
                line
                for line in report.splitlines()
                if not line.strip().startswith(("claimed-witness-behavior:", "authoring-input-sha256:"))
            ]

        self.assertEqual(structural(truthful_report), structural(misleading_report))
        self.assertNotEqual(truthful_report, misleading_report)
        self.assertIn("semantic-review-required:", truthful_report)
        self.assertIn("repository-writes-performed: 0", truthful_report)

    def test_legacy_relaxations_are_not_reachable_from_the_input(self):
        """The interface is a parameter of the conversion, never a field of the input."""

        module = self.module()
        document = self.accepted_case("root")
        document["decisions"] = ["TBD"]
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            source = self.write_input(root, document)
            with self.assertRaises(module.AuthoringError) as caught:
                module.check_authoring_input(root, source, profile="root")
            self.assertIn("placeholder", str(caught.exception))

            forged = dict(document)
            forged["authoring_interface"] = "legacy_arguments"
            forged_path = self.write_input(root, forged, "forged.json")
            with self.assertRaises(module.AuthoringError) as forged_error:
                module.check_authoring_input(root, forged_path, profile="root")
            self.assertIn("unknown key", str(forged_error.exception))

            with self.assertRaises(module.AuthoringError) as root_legacy:
                module.check_authoring_input(
                    root, source, profile="root", interface="legacy_arguments"
                )
            self.assertIn("generated plans only", str(root_legacy.exception))
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])

    def test_declared_paths_may_not_resolve_through_a_symlink(self):
        module = self.module()
        document = self.accepted_case("root")
        document["write_paths"] = [{"id": "wp-lib", "path": "linked/plan_authoring.py"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            (root / "real").mkdir()
            (root / "linked").symlink_to("real", target_is_directory=True)
            source = self.write_input(root, document)
            with self.assertRaises(module.AuthoringError) as caught:
                module.check_authoring_input(root, source, profile="root")
            self.assertIn("resolves through a symlink", str(caught.exception))

    def test_surrogate_escape_is_refused_as_an_authoring_error(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            document = self.accepted_case("root")
            source = root / "surrogate.json"
            source.write_text(
                json.dumps(document, ensure_ascii=False).replace(
                    '"summary": "', '"summary": "\\ud800', 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(module.AuthoringError):
                module.check_authoring_input(root, source, profile="root")

    def test_sequential_plans_allocate_distinct_ids_and_one_index_row_each(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            written = []
            for index in range(3):
                document = self.accepted_case("root")
                document["slug"] = f"sequential-plan-{index}"
                document["summary"] = f"Sequential plan {index}"
                source = self.write_input(root, document, f"input-{index}.json")
                digest, _ = module.check_authoring_input(root, source, profile="root")
                written.append(
                    module.write_authoring_input(root, source, digest, profile="root")
                )

            self.assertEqual(
                written,
                [
                    "docs/plan/active/001-sequential-plan-0.md",
                    "docs/plan/active/002-sequential-plan-1.md",
                    "docs/plan/active/003-sequential-plan-2.md",
                ],
            )
            self.assertEqual(
                (root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                "# Active Plan\n\nid\tpath\tstatus\n"
                + "".join(
                    f"{path.split('/')[-1][:3]}\t{path}\tin_progress\n" for path in written
                ),
            )

    def test_root_entrypoint_is_bound_to_its_profile_and_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            source = self.write_input(root, self.accepted_case("root"))
            for extra in (
                ["--profile", "generated"],
                ["--authoring-interface", "legacy_arguments"],
            ):
                with self.subTest(extra=extra):
                    result = self.run_command(root, "check", "--input", str(source), *extra)
                    self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])

    def test_both_titles_receive_the_same_legacy_treatment(self):
        module = self.module()
        for field in ("summary", "summary_ja"):
            with self.subTest(field=field):
                document = json.loads(json.dumps(self.accepted_case("generated")))
                document[field] = "  " + "a" * 260 + "  "
                with tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    source = self.write_input(root, document)
                    with self.assertRaises(module.AuthoringError):
                        module.check_authoring_input(root, source, profile="generated")
                    digest, _ = module.check_authoring_input(
                        root, source, profile="generated", interface="legacy_arguments"
                    )
                    path = module.write_authoring_input(
                        root,
                        source,
                        digest,
                        profile="generated",
                        interface="legacy_arguments",
                    )
                    rendered = (root / path).read_text(encoding="utf-8")
                    for line in rendered.splitlines():
                        self.assertEqual(line, line.rstrip(), line)
