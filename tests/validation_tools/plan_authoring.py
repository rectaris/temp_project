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

    def test_standing_authorization_renders_one_line_that_the_ledger_reads(self):
        words = "4回目のレビューまで、この計画の続行を承認する。"
        ledger = load_module(ROOT / "scripts/plan-execution-state.py", "ledger_for_plan_authoring")
        planlib = load_module(PLANLIB, "planlib_for_standing_authoring")
        module = self.module()
        self.assertEqual(
            set(module.ADMISSION_PLACEHOLDER_VALUES), set(ledger.STANDING_PLACEHOLDER_VALUES)
        )
        for profile in ("root", "generated"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                root = self.make_repository(Path(tmp))
                document = json.loads(json.dumps(self.accepted_case(profile)))
                document["standing_continuation_authorization"] = words
                source = self.write_input(root, document)
                if profile == "root":
                    checked = self.run_command(root, "check", "--input", str(source), "--print-digest")
                    self.assertEqual(checked.returncode, 0, checked.stderr)
                    written = self.run_command(
                        root, "write", "--input", str(source),
                        "--expect-input-sha256", checked.stdout.strip(),
                    )
                    self.assertEqual(written.returncode, 0, written.stderr)
                    path = written.stdout.strip()
                else:
                    digest, _ = module.check_authoring_input(root, source, profile=profile)
                    path = module.write_authoring_input(root, source, digest, profile=profile)
                rendered = (root / path).read_text(encoding="utf-8")
                self.assertEqual(
                    [line for line in rendered.splitlines()
                     if line.startswith("standing_continuation_authorization")],
                    [f"standing_continuation_authorization: {words}"],
                )
                self.assertEqual(ledger.plan_standing_quotation(rendered), words)
                self.assertEqual(
                    planlib.parse_manifest_text(rendered)["standing_continuation_authorization"], words
                )
                del document["standing_continuation_authorization"]
                absent = self.write_input(root, document, "absent.json")
                module.check_authoring_input(root, absent, profile=profile)
                self.assertNotIn(
                    "standing_continuation_authorization",
                    module.render_plan(
                        module.build_document(
                            module.parse_input(absent.read_bytes()), profile=profile
                        ),
                        "002",
                    ),
                )

    def test_standing_authorization_refuses_unbounded_values(self):
        module = self.module()
        for profile in ("root", "generated"):
            for value, message in (
                ("", "must not be empty"),
                ("TODO", "placeholder"),
                ("t.b.d.", "placeholder"),
                ("Pending", "placeholder"),
                ("first line\u2028second line", "one line"),
                ("first line\nsecond line", "control character"),
                ("x" * 401, "at most 400 bytes"),
                (" padded words", "leading or trailing whitespace"),
                (["list"], "must be text"),
            ):
                with self.subTest(profile=profile, value=value), tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    document = json.loads(json.dumps(self.accepted_case(profile)))
                    document["standing_continuation_authorization"] = value
                    source = self.write_input(root, document)
                    with self.assertRaises(module.AuthoringError) as caught:
                        module.check_authoring_input(root, source, profile=profile)
                    self.assertIn(message, str(caught.exception))
                    self.assertEqual(list((root / "docs/plan/active").iterdir()), [])

    def test_unassigned_backlog_roundtrip_and_mixed_coverage(self):
        module = self.module()
        planlib = load_module(PLANLIB, "planlib_unassigned_authoring")
        for profile in ("root", "generated"):
            data = self.accepted_case(profile)
            data["lifecycle"] = "backlog"
            texts = [item["text"] for item in data["acceptance_items"]]
            for item in data["acceptance_items"]:
                for key in ("witness", "stage", "authoritative_only_reason"):
                    item.pop(key, None)
                item["unassigned_reason"] = "Live approval acquisition has no complete verification method yet."
            for mixed in (False, True):
                with self.subTest(profile=profile, mixed=mixed):
                    if mixed:
                        item = dict(data["acceptance_items"][0])
                        item["id"] = "another-acceptance"
                        item["text"] = "Preserve the independently assigned fixture predicate."
                        item.pop("unassigned_reason")
                        item["witness"] = data["completion_conditions"][0]["witness"]
                        item["stage"] = "focused"
                        data["acceptance_items"].append(item)
                        data["requirements"][0]["acceptance_items"].append(item["id"])
                    document = module.build_document(data, profile=profile)
                    rendered = module.render_plan(document, "991")
                    values = planlib.parse_manifest_text(rendered)
                    records = planlib.validate_validation_witness_map(values)
                    self.assertEqual(len(records), int(mixed))
                    self.assertEqual(document["acceptance"][:len(texts)], texts)
                    self.assertEqual([r["acceptance_sha256"] for r in document["validation_witness_unassigned"]],
                                     [module.text_digest(text) for text in texts])
                    data["lifecycle"] = "active"
                    with self.assertRaises(module.AuthoringError):
                        module.build_document(data, profile=profile)
                    data["lifecycle"] = "backlog"

    def test_unassigned_report_preserves_reasons_and_marks_draft_completion(self):
        module = self.module()
        for profile in ("root", "generated"):
            for mixed in (False, True):
                with self.subTest(profile=profile, mixed=mixed):
                    data = self.accepted_case(profile)
                    data["lifecycle"] = "backlog"
                    selected = data["acceptance_items"][:1] if mixed else data["acceptance_items"]
                    reasons = []
                    for index, item in enumerate(selected, 1):
                        for key in ("stage", "witness", "authoritative_only_reason"):
                            item.pop(key, None)
                        reason = f"Live target {index} lacks an assigned independent verification method."
                        item["unassigned_reason"] = reason
                        reasons.append(reason)
                    document = module.build_document(data, profile=profile)
                    report = module.render_report(document, "sha256:" + "0" * 64,
                                                  next_plan_id="991", plan_path="docs/plan/backlog/991-example.md")
                    self.assertIn("implementation-admission: blocked (unassigned verification)", report)
                    for reason in reasons:
                        self.assertIn("unassigned-reason: " + reason, report)
                    self.assertNotIn("legacy authoring placeholder", report)
                    self.assertIn("completion-witness-status: unfulfilled draft", report)
                    self.assertEqual(report.count("verification-status: unassigned"), len(reasons))
                    self.assertIn("repository-writes-performed: 0", report)
                    if mixed:
                        self.assertIn("stage: " + data["acceptance_items"][1]["stage"], report)
            assigned = module.build_document(self.accepted_case(profile), profile=profile)
            report = module.render_report(assigned, "sha256:" + "0" * 64,
                                          next_plan_id="991", plan_path="docs/plan/active/991-example.md")
            self.assertNotIn("unassigned", report)
            self.assertNotIn("unfulfilled draft", report)

    def test_plan387_partial_command_is_never_whole_acceptance_evidence(self):
        source = ROOT / "docs/plan/authoring/387-implement-issue18-limited-implementation-resume.json"
        data = json.loads(source.read_text())
        module = self.module()
        document = module.build_document(data, profile="root")
        report = module.render_report(document, "sha256:" + "0" * 64,
                                      next_plan_id="387", plan_path="docs/plan/backlog/387-implement-issue18-limited-implementation-resume.md")
        self.assertEqual(report.count("completion-witness-status: unfulfilled draft"), 5)
        self.assertEqual(report.count("verification-status: unassigned"), 5)
        self.assertIn("implementation-admission: blocked", report)
        self.assertNotIn("legacy authoring placeholder", report)
        self.assertEqual(document["validation_witness_map"], [])
        # A syntactically complete partial-test map and a success note do not
        # authorize activation of these original whole E1-E5 conditions.
        root_policy = load_module(ROOT / "scripts/check-root-agent-policy.py", "plan387_root_pending")
        rendered = module.render_plan(document, "387")
        values = root_policy.parse_plan_manifest(rendered.replace("status: backlog", "status: in_progress"))
        with self.assertRaises(SystemExit):
            root_policy.check_plan_admission("docs/plan/active/387-implement-issue18-limited-implementation-resume.md", values)
        data["lifecycle"] = "active"
        with self.assertRaises(module.AuthoringError):
            module.build_document(data, profile="root")

    def test_unassigned_authoring_rejects_missing_invalid_or_conflicting_reason(self):
        module = self.module()
        for profile in ("root", "generated"):
            for reason in (None, "", " ", "TBD", "t.b.d.", "x" * 241, "語" * 81, "\ud800",
                           *(f"reason{separator}continued" for separator in ("\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"))):
                data = self.accepted_case(profile)
                data["lifecycle"] = "backlog"
                item = data["acceptance_items"][0]
                for key in ("witness", "stage", "authoritative_only_reason"):
                    item.pop(key, None)
                if reason is not None:
                    item["unassigned_reason"] = reason
                with self.subTest(profile=profile, reason=reason):
                    with self.assertRaises(module.AuthoringError):
                        module.build_document(data, profile=profile)
            data = self.accepted_case(profile)
            data["lifecycle"] = "backlog"
            data["acceptance_items"][0]["unassigned_reason"] = "A concrete method remains unassigned."
            with self.assertRaises(module.AuthoringError):
                module.build_document(data, profile=profile)

    def test_safe_unicode_and_literal_escapes_in_reasons_roundtrip_without_loss(self):
        module = self.module()
        planlib = load_module(PLANLIB, "planlib_reason_roundtrip")
        for profile in ("root", "generated"):
            for reason in (
                'Live "approval" verification remains unassigned; \\u0085 stays literal.',
                "実環境の取得検証は未設計です。",
                "Café approval verification remains undefined.",
            ):
                with self.subTest(profile=profile, reason=reason):
                    data = self.accepted_case(profile)
                    data["lifecycle"] = "backlog"
                    for item in data["acceptance_items"]:
                        for key in ("witness", "stage", "authoritative_only_reason"):
                            item.pop(key, None)
                        item["unassigned_reason"] = reason
                    document = module.build_document(data, profile=profile)
                    rendered = module.render_plan(document, "991")
                    values = planlib.parse_manifest_text(rendered.encode("utf-8").decode("utf-8"))
                    planlib.validate_validation_witness_map(values)
                    pending = [json.loads(entry) for entry in values["validation_witness_unassigned"]]
                    self.assertEqual([entry["reason"] for entry in pending],
                                     [reason] * len(data["acceptance_items"]))
                    self.assertEqual(pending, document["validation_witness_unassigned"])

    def test_splitline_reasons_refuse_check_and_write_before_effects(self):
        module = self.module()
        for profile in ("root", "generated"):
            for separator in ("\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
                with self.subTest(profile=profile, separator=separator), tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    data = self.accepted_case(profile)
                    data["lifecycle"] = "backlog"
                    item = data["acceptance_items"][0]
                    for key in ("witness", "stage", "authoritative_only_reason"):
                        item.pop(key, None)
                    item["unassigned_reason"] = f"Live method{separator}remains unassigned."
                    source = self.write_input(root, data)
                    before = {path.relative_to(root): path.read_bytes()
                              for path in root.rglob("*") if path.is_file()}
                    digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
                    with self.assertRaises(module.AuthoringError):
                        module.check_authoring_input(root, source, profile=profile)
                    with self.assertRaises(module.AuthoringError):
                        module.write_authoring_input(root, source, digest, profile=profile)
                    self.assertEqual({path.relative_to(root): path.read_bytes()
                                      for path in root.rglob("*") if path.is_file()}, before)

    def test_plan387_complete_checked_input_regenerates_without_requirement_loss(self):
        source = ROOT / "docs/plan/authoring/387-implement-issue18-limited-implementation-resume.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        document = self.module().build_document(data, profile="root")
        rendered = self.module().render_plan(document, "387")
        self.assertEqual(rendered, (ROOT / "docs/plan/backlog/387-implement-issue18-limited-implementation-resume.md").read_text(encoding="utf-8"))
        expected = ['sha256:0d7cabf5a1694a41432b61ad27875ee0c6b69fef2a86b37203c80bee57a323a2', 'sha256:2c84a36e2a222baad191de2332f4cb878a91510ec817db4737c9c521b5a41baa', 'sha256:2c30a0e1bd02f136f1741cda177f803e112048e5bdc61f37305b54b6f94ef372', 'sha256:47022777607a1553215cd75384af833bc3a754eac19a993823a82fa64e959cd2', 'sha256:edad9cbda2cc4ed9975bb1af205b31e2f7a1dd9b3f4242f7c8fb4add73b44e24']
        self.assertEqual([self.module().text_digest(item) for item in document["acceptance"]], expected)
        self.assertEqual([self.module().text_digest(document["completion_conditions"][i]["text"]) for i in document["condition_order"]], expected)
        self.assertEqual(len(document["validation_witness_unassigned"]), 5)
        self.assertEqual(document["validation_witness_map"], [])
        self.assertEqual(document["status"], "backlog")
        for field in ("decisions", "tasks", "validation_notes", "integration_gates"):
            for clause in data[field]:
                self.assertIn(clause, rendered)


class PlanAuthoringInRepositoryTest(unittest.TestCase):
    """Authoring inside a real repository, where the shared lifecycle lock applies."""

    @staticmethod
    def module():
        return load_module(PLAN_AUTHORING_MODULES[0], "plan_authoring_in_repository")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repository"
        (self.root / "docs/plan/active").mkdir(parents=True)
        (self.root / "docs/plan/backlog").mkdir(parents=True)
        (self.root / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nNo active development items.\n", encoding="utf-8"
        )
        self.git("init", "-q", "-b", "dev")
        self.git("config", "user.name", "Authoring Test")
        self.git("config", "user.email", "authoring@example.invalid")
        self.git("add", "-A")
        self.git("commit", "-qm", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    def accepted_input(self, profile: str = "root") -> dict:
        cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            if case["expect"] == "accept" and case["input"]["profile"] == profile:
                return case["input"]
        raise AssertionError(f"no accepted {profile} case")

    def run_command(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT_COMMAND), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_check_and_write_complete_inside_a_repository(self) -> None:
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        checked = self.run_command("check", "--input", str(source), "--print-digest")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        digest = checked.stdout.strip()
        written = self.run_command(
            "write", "--input", str(source), "--expect-input-sha256", digest
        )
        self.assertEqual(written.returncode, 0, written.stderr)
        created = sorted(path.name for path in (self.root / "docs/plan/active").iterdir())
        self.assertEqual(len(created), 1, created)
        self.assertTrue(created[0].startswith("001-"), created)

    def test_a_governed_repository_refuses_authoring_outside_a_task_worktree(self) -> None:
        """A repository a binding can name must author its plan in that worktree."""

        self.git("remote", "add", "origin", "git@github.com:example/authoring.git")
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        checked = self.run_command("check", "--input", str(source), "--print-digest")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        written = self.run_command(
            "write", "--input", str(source), "--expect-input-sha256", checked.stdout.strip()
        )
        self.assertEqual(written.returncode, 1)
        self.assertIn("pre-existing checkout", written.stderr)
        self.assertEqual(list((self.root / "docs/plan/active").iterdir()), [])

    def test_rechecking_a_written_input_moves_past_the_plan_it_created(self) -> None:
        module = self.module()
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        digest, _ = module.check_authoring_input(self.root, source, profile="root")
        first = module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertTrue(first.startswith("docs/plan/active/001-"), first)
        _, report = module.check_authoring_input(self.root, source, profile="root")
        self.assertIn("next-plan-id: 002", report)

    def test_a_written_identifier_stays_reserved_until_publication(self) -> None:
        module = self.module()
        guard = module.locate_worktree_guard()
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        digest, _ = module.check_authoring_input(self.root, source, profile="root")
        module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertEqual(guard.reserved_plan_ids(self.root), {1})

    def test_the_reported_identifier_is_the_written_identifier(self) -> None:
        module = self.module()
        source = self.root / "input.json"
        document = self.accepted_input()
        source.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        digest, report = module.check_authoring_input(self.root, source, profile="root")
        reported = [line for line in report.splitlines() if line.startswith("next-plan-id: ")]
        relative = module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertEqual(reported, [f"next-plan-id: {relative[len('docs/plan/active/'):][:3]}"])

    def test_revised_recheck_keeps_id_and_refuses_superseded_write_in_both_copies(self) -> None:
        for index, module_path in enumerate(PLAN_AUTHORING_MODULES):
            with self.subTest(module=module_path):
                module = load_module(module_path, f"revised_authoring_{index}")
                profile = "root" if index == 0 else "generated"
                document = self.accepted_input(profile)
                document["slug"] = f"revised-{index}"
                source_a = self.root / f"input-a-{index}.json"
                source_b = self.root / f"input-b-{index}.json"
                source_a.write_text(json.dumps(document), encoding="utf-8")
                document["summary"] += " after revision"
                source_b.write_text(json.dumps(document, indent=2), encoding="utf-8")
                digest_a, report_a = module.check_authoring_input(
                    self.root, source_a, profile=profile
                )
                digest_b, report_b = module.check_authoring_input(
                    self.root, source_b, profile=profile
                )
                identifier = f"{index + 1:03d}"
                self.assertIn(f"next-plan-id: {identifier}", report_a)
                self.assertIn(f"next-plan-id: {identifier}", report_b)
                guard = module.locate_worktree_guard()
                ledger = guard.reservation_ledger_path(self.root)
                ledger_before = ledger.read_bytes()
                files_before = {
                    path.relative_to(self.root): path.read_bytes()
                    for path in (self.root / "docs/plan").rglob("*.md")
                }
                with self.assertRaises(module.AuthoringError):
                    module.write_authoring_input(
                        self.root, source_a, digest_a, profile=profile
                    )
                self.assertEqual(ledger.read_bytes(), ledger_before)
                self.assertEqual(
                    {
                        path.relative_to(self.root): path.read_bytes()
                        for path in (self.root / "docs/plan").rglob("*.md")
                    },
                    files_before,
                )
                written = module.write_authoring_input(
                    self.root, source_b, digest_b, profile=profile
                )
                self.assertEqual(written, f"docs/plan/active/{identifier}-revised-{index}.md")
                self.assertIn(
                    f"{identifier}\t{written}\t",
                    (self.root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                )

    def test_write_without_check_cannot_allocate_an_identifier(self) -> None:
        module = self.module()
        source = self.root / "unchecked.json"
        source.write_text(json.dumps(self.accepted_input()), encoding="utf-8")
        digest = module.byte_digest(source.read_bytes())
        with self.assertRaises(module.AuthoringError):
            module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertEqual(list((self.root / "docs/plan/active").iterdir()), [])
