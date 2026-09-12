#!/usr/bin/env python3
"""Focused tests for optional harness profile selection."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "scripts/check-harness-profile.py"
IMPLEMENTATION = ROOT / "template/.project-agent-workflow/scripts/check-harness-profile.py"
COMPARISON_FIXTURES = ROOT / "tests/test-harness-comparison.py"
CASES = ROOT / "tests/fixtures/harness-profiles/cases.json"


def load_implementation():
    spec = importlib.util.spec_from_file_location("harness_profiles", IMPLEMENTATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_comparison_fixtures():
    """Reuse the checked comparison fixtures so adoption inputs are real inputs."""

    spec = importlib.util.spec_from_file_location("harness_comparison_fixtures", COMPARISON_FIXTURES)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class HarnessProfileTests(unittest.TestCase):
    def run_cli(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(COMMAND), "--repository-root", str(root), *arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def fixture(self, *, status: str = "active") -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        policy = root / "policy.md"
        policy.write_text("governing\n", encoding="utf-8")
        asset = root / "advice.txt"
        asset.write_text("Use the bounded fixture.\n", encoding="utf-8")
        catalog = root / "catalog.json"
        catalog.write_text(json.dumps({
            "schema_version": 1,
            "governing_sources": [{
                "id": "policy", "revision": "v1", "path": "policy.md",
                "content_digest": digest(policy.read_bytes()), "rationale": "Governing."
            }],
            "supplemental_revisions": [{
                "id": "fixture-advice", "revision": "v1",
                "content_digest": digest(asset.read_bytes()),
                "applicability": {"task_types": ["test"], "model_selector": None},
                "introduction_reason": "Synthetic fixture.",
                "failure_case_references": ["cases.json#fixture"],
                "review_evidence": {
                    "comparison_protocol_digest": "sha256:" + "1" * 64,
                    "comparison_report_digest": "sha256:" + "2" * 64,
                    "evidence_digests": ["sha256:" + "3" * 64]
                },
                "status": status
            }]
        }), encoding="utf-8")
        profile = root / "profile.json"
        profile.write_text(json.dumps({
            "schema_version": 1,
            "selections": [{
                "id": "fixture-advice", "revision": "v1",
                "content_digest": digest(asset.read_bytes()), "asset_path": "advice.txt"
            }]
        }), encoding="utf-8")
        return temporary, root, catalog, profile

    def test_repository_defaults_check_and_render_empty_selection(self) -> None:
        check = self.run_cli(
            ROOT, "check", "--catalog", str(ROOT / "docs/agent/harness-instructions.json"),
            "--profile", str(ROOT / "docs/agent/harness-profile.json"),
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        render = self.run_cli(
            ROOT, "render", "--catalog", str(ROOT / "docs/agent/harness-instructions.json"),
            "--profile", str(ROOT / "docs/agent/harness-profile.json"),
        )
        self.assertEqual(render.returncode, 0, render.stderr)
        output = json.loads(render.stdout)
        self.assertEqual(output["supplemental_instructions"], "")
        self.assertEqual(output["runtime_activation"], "not_observed")

    def test_exact_selection_renders_only_selected_asset(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            result = self.run_cli(root, "render", "--catalog", str(catalog), "--profile", str(profile))
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["supplemental_instructions"], "Use the bounded fixture.")
            self.assertFalse(output["governing_sources_included"])

    def test_unknown_revision_and_digest_drift_fail_without_fallback(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            value = json.loads(profile.read_text())
            value["selections"][0]["revision"] = "v2"
            profile.write_text(json.dumps(value))
            self.assertNotEqual(self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile)).returncode, 0)
            value["selections"][0]["revision"] = "v1"
            value["selections"][0]["content_digest"] = "sha256:" + "9" * 64
            profile.write_text(json.dumps(value))
            self.assertNotEqual(self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile)).returncode, 0)

    def test_governing_source_id_selection_is_rejected(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            value = json.loads(profile.read_text())
            value["selections"][0]["id"] = "policy"
            profile.write_text(json.dumps(value))
            result = self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("governing sources cannot be selected", result.stderr)

    def test_governing_source_path_selection_is_rejected(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            value = json.loads(profile.read_text())
            value["selections"][0].update({
                "id": "fixture-advice",
                "revision": "v1",
                "content_digest": digest((root / "policy.md").read_bytes()),
                "asset_path": "policy.md",
            })
            catalog_value = json.loads(catalog.read_text())
            catalog_value["supplemental_revisions"][0]["content_digest"] = value[
                "selections"
            ][0]["content_digest"]
            catalog.write_text(json.dumps(catalog_value))
            profile.write_text(json.dumps(value))
            result = self.run_cli(root, "render", "--catalog", str(catalog), "--profile", str(profile))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("governing source paths", result.stderr)

    def test_unsafe_asset_path_is_rejected(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            value = json.loads(profile.read_text())
            value["selections"][0].update({
                "asset_path": "../outside.txt",
                "content_digest": digest(b"outside the repository\n"),
            })
            catalog_value = json.loads(catalog.read_text())
            catalog_value["supplemental_revisions"][0]["content_digest"] = value[
                "selections"
            ][0]["content_digest"]
            catalog.write_text(json.dumps(catalog_value))
            profile.write_text(json.dumps(value))
            result = self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("normalized repository-relative path", result.stderr)

    def test_non_regular_and_symlinked_assets_are_rejected(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            value = json.loads(profile.read_text())
            target = root / "advice.txt"
            target.unlink()
            target.mkdir()
            self.assertNotEqual(
                self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile)).returncode,
                0,
            )
            target.rmdir()
            target.symlink_to(root / "policy.md")
            self.assertNotEqual(
                self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile)).returncode,
                0,
            )
            target.unlink()
            os.mkfifo(target)
            self.assertNotEqual(
                self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile)).returncode,
                0,
            )

    def test_catalog_types_path_normalization_and_selection_bound_are_strict(self) -> None:
        implementation = load_implementation()
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            value = json.loads(catalog.read_text())
            value["supplemental_revisions"][0]["applicability"]["model_selector"] = {}
            catalog.write_text(json.dumps(value))
            with self.assertRaises(implementation.ProfileError):
                implementation.parse_catalog(catalog, root)
            with self.assertRaises(implementation.ProfileError):
                implementation.safe_repository_file(root, "./advice.txt", "asset")
            profile.write_text(json.dumps({
                "schema_version": 1,
                "selections": [
                    {
                        "id": f"fixture-{index}",
                        "revision": "v1",
                        "content_digest": "sha256:" + "1" * 64,
                        "asset_path": f"asset-{index}.txt",
                    }
                    for index in range(implementation.MAX_SELECTIONS + 1)
                ],
            }))
            with self.assertRaises(implementation.ProfileError):
                implementation.parse_profile(profile)

    def test_profile_rejects_multiple_revisions_and_noncanonical_order(self) -> None:
        implementation = load_implementation()
        temporary, root, _, profile = self.fixture()
        with temporary:
            base = json.loads(profile.read_text())["selections"][0]
            profile.write_text(json.dumps({
                "schema_version": 1,
                "selections": [
                    base,
                    {**base, "revision": "v2"},
                ],
            }))
            with self.assertRaises(implementation.ProfileError):
                implementation.parse_profile(profile)
            profile.write_text(json.dumps({
                "schema_version": 1,
                "selections": [
                    {**base, "id": "z-advice"},
                    {**base, "id": "a-advice"},
                ],
            }))
            with self.assertRaises(implementation.ProfileError):
                implementation.parse_profile(profile)

    def test_adoption_uses_named_comparison_from_report_list(self) -> None:
        implementation = load_implementation()
        report = {
            "comparisons": [
                {"comparison": "model_effect", "recommendation": "keep_current"},
                {"comparison": "instruction_effect", "recommendation": "adopt_candidate"},
            ]
        }
        self.assertEqual(
            implementation.comparison_recommendation(report, "instruction_effect"),
            "adopt_candidate",
        )
        with self.assertRaises(implementation.ProfileError):
            implementation.comparison_recommendation(
                {"comparisons": [{"comparison": "model_effect", "recommendation": "keep_current"}]},
                "instruction_effect",
            )

    def test_profile_comparison_binding_rejects_unrelated_assets(self) -> None:
        implementation = load_implementation()
        prior = [{
            "asset_path": "advice.txt",
            "content_digest": "sha256:" + "1" * 64,
        }]
        proposed = [{
            "asset_path": "advice.txt",
            "content_digest": "sha256:" + "2" * 64,
        }]
        protocol = {
            "configurations": {
                "new_model_current_instructions": {
                    "instruction_asset_digests": {"advice.txt": "sha256:" + "1" * 64}
                },
                "new_model_candidate_instructions": {
                    "instruction_asset_digests": {"advice.txt": "sha256:" + "2" * 64}
                },
            }
        }
        implementation.require_profile_comparison_binding(protocol, prior, proposed)
        protocol["configurations"]["new_model_current_instructions"][
            "instruction_asset_digests"
        ]["confounder.txt"] = "sha256:" + "3" * 64
        protocol["configurations"]["new_model_candidate_instructions"][
            "instruction_asset_digests"
        ]["confounder.txt"] = "sha256:" + "4" * 64
        with self.assertRaises(implementation.ProfileError):
            implementation.require_profile_comparison_binding(protocol, prior, proposed)
        del protocol["configurations"]["new_model_current_instructions"][
            "instruction_asset_digests"
        ]["confounder.txt"]
        protocol["configurations"]["new_model_candidate_instructions"][
            "instruction_asset_digests"
        ] = {"unrelated.txt": "sha256:" + "2" * 64}
        with self.assertRaises(implementation.ProfileError):
            implementation.require_profile_comparison_binding(protocol, prior, proposed)

    def test_retired_selection_remains_reproducible(self) -> None:
        temporary, root, catalog, profile = self.fixture(status="retired")
        with temporary:
            result = self.run_cli(root, "check", "--catalog", str(catalog), "--profile", str(profile))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["selected_revisions"][0]["availability"], "retired")

    def adoption_fixture(
        self, *, status: str = "active"
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Path], list[str]]:
        """Measure one candidate selection with the real comparison command.

        The prior profile selects nothing and the proposed profile selects the
        fixture asset, so the comparison moves only the profile-selected asset.
        """

        fixtures = load_comparison_fixtures()
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        policy = root / "policy.md"
        policy.write_text("governing\n", encoding="utf-8")
        asset = root / "advice.txt"
        asset.write_text("Use the bounded fixture.\n", encoding="utf-8")
        asset_digest = digest(asset.read_bytes())

        payload = fixtures.protocol()
        shared = {"AGENTS.md": fixtures.sha("instructions-current")}
        configurations = payload["configurations"]
        for slot in ("old_model_current_instructions", "new_model_current_instructions"):
            configurations[slot]["instruction_asset_digests"] = dict(shared)
        configurations["new_model_candidate_instructions"]["instruction_asset_digests"] = {
            **shared,
            "advice.txt": asset_digest,
        }
        observations = fixtures.adoptable_observations()
        for record in observations:
            record["instruction_loading"]["effective_instruction_digests"] = dict(
                configurations[record["slot"]]["instruction_asset_digests"]
            )

        protocol_path = root / "protocol.json"
        protocol_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        arguments = ["--protocol", str(protocol_path)]
        for index, record in enumerate(observations):
            path = root / f"observation-{index:03d}.json"
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            arguments += ["--observation", str(path)]
        evidence_paths: list[Path] = []
        for index, blob in enumerate(fixtures.evidence_payloads(observations)):
            path = root / f"evidence-{index:03d}.bin"
            path.write_bytes(blob)
            evidence_paths.append(path)
            arguments += ["--evidence", str(path)]
        ordering = root / "ordering.txt"
        ordering.write_bytes(fixtures.ORDERING_ATTESTATION)
        arguments += ["--ordering-evidence", str(ordering)]

        completed = subprocess.run(
            ["python3", str(ROOT / "scripts/compare-harness-runs.py"), *arguments, "--format", "json"],
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        report_digest = digest(completed.stdout)
        self.assertEqual(
            json.loads(completed.stdout)["comparisons"][-1]["comparison"],
            "instruction_effect",
        )

        catalog = root / "catalog.json"
        catalog.write_text(json.dumps({
            "schema_version": 1,
            "governing_sources": [{
                "id": "policy", "revision": "v1", "path": "policy.md",
                "content_digest": digest(policy.read_bytes()), "rationale": "Governing."
            }],
            "supplemental_revisions": [{
                "id": "fixture-advice", "revision": "v1",
                "content_digest": asset_digest,
                "applicability": {"task_types": ["test"], "model_selector": None},
                "introduction_reason": "Synthetic fixture.",
                "failure_case_references": ["cases.json#fixture"],
                "review_evidence": {
                    "comparison_protocol_digest": digest(protocol_path.read_bytes()),
                    "comparison_report_digest": report_digest,
                    "evidence_digests": [digest(path.read_bytes()) for path in evidence_paths],
                },
                "status": status
            }]
        }), encoding="utf-8")
        prior = root / "prior.json"
        prior.write_text(json.dumps({"schema_version": 1, "selections": []}), encoding="utf-8")
        proposed = root / "proposed.json"
        proposed.write_text(json.dumps({
            "schema_version": 1,
            "selections": [{
                "id": "fixture-advice", "revision": "v1",
                "content_digest": asset_digest, "asset_path": "advice.txt"
            }]
        }), encoding="utf-8")
        record_path = root / "adoption.json"
        record_path.write_text(json.dumps({
            "schema_version": 1,
            "decision": "adopt",
            "prior_profile_digest": digest(prior.read_bytes()),
            "proposed_profile_digest": digest(proposed.read_bytes()),
            "comparison_protocol_digest": digest(protocol_path.read_bytes()),
            "comparison_report_digest": report_digest,
            "comparison_evidence_digests": [digest(path.read_bytes()) for path in evidence_paths],
            "comparison_ordering_evidence_digests": [digest(ordering.read_bytes())],
        }), encoding="utf-8")
        paths = {
            "catalog": catalog,
            "prior": prior,
            "proposed": proposed,
            "record": record_path,
            "protocol": protocol_path,
            "ordering": ordering,
        }
        return temporary, root, paths, [str(path) for path in evidence_paths]

    def run_adoption(self, root: Path, paths: dict[str, Path], evidence: list[str]):
        arguments = [
            "check-adoption",
            "--catalog", str(paths["catalog"]),
            "--prior-profile", str(paths["prior"]),
            "--proposed-profile", str(paths["proposed"]),
            "--record", str(paths["record"]),
            "--protocol", str(paths["protocol"]),
            "--ordering-evidence", str(paths["ordering"]),
        ]
        for path in evidence:
            arguments += ["--evidence", path]
        for path in sorted(root.glob("observation-*.json")):
            arguments += ["--observation", str(path)]
        return self.run_cli(root, *arguments)

    def test_measured_adoption_is_accepted_and_changes_no_repository_state(self) -> None:
        temporary, root, paths, evidence = self.adoption_fixture()
        with temporary:
            before = sorted(item.name for item in root.iterdir())
            result = self.run_adoption(root, paths, evidence)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["decision"], "adopt")
            self.assertFalse(output["repository_changed"])
            self.assertEqual(sorted(item.name for item in root.iterdir()), before)

    def test_retired_revision_cannot_be_newly_adopted(self) -> None:
        temporary, root, paths, evidence = self.adoption_fixture(status="retired")
        with temporary:
            result = self.run_adoption(root, paths, evidence)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("retired revisions cannot be newly adopted", result.stderr)

    def test_adoption_record_that_misstates_its_comparison_is_rejected(self) -> None:
        temporary, root, paths, evidence = self.adoption_fixture()
        with temporary:
            record = json.loads(paths["record"].read_text())
            record["comparison_report_digest"] = "sha256:" + "4" * 64
            paths["record"].write_text(json.dumps(record), encoding="utf-8")
            result = self.run_adoption(root, paths, evidence)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match recomputed comparison evidence", result.stderr)

    def test_unmeasured_revision_cannot_be_adopted(self) -> None:
        temporary, root, paths, evidence = self.adoption_fixture()
        with temporary:
            catalog = json.loads(paths["catalog"].read_text())
            catalog["supplemental_revisions"][0]["review_evidence"][
                "comparison_report_digest"
            ] = "sha256:" + "5" * 64
            paths["catalog"].write_text(json.dumps(catalog), encoding="utf-8")
            result = self.run_adoption(root, paths, evidence)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("catalog review evidence does not match adoption inputs", result.stderr)

    def test_declared_cases_are_bound_to_executed_tests(self) -> None:
        declared = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(declared["schema_version"], 1)
        for case, method in declared["cases"].items():
            self.assertTrue(
                hasattr(type(self), method),
                f"case {case} names no test: {method}",
            )

    def test_rollback_reports_governing_reassessment(self) -> None:
        temporary, root, catalog, profile = self.fixture()
        with temporary:
            current_digest = digest(profile.read_bytes())
            record = root / "rollback.json"
            record.write_text(json.dumps({
                "schema_version": 1, "decision": "rollback",
                "current_profile_digest": current_digest,
                "prior_profile_digest": current_digest,
                "governing_sources_digest": "sha256:" + "0" * 64
            }))
            result = self.run_cli(
                root, "check-rollback", "--catalog", str(catalog),
                "--current-profile", str(profile), "--prior-profile", str(profile),
                "--record", str(record),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "reassessment_required")


if __name__ == "__main__":
    unittest.main()
