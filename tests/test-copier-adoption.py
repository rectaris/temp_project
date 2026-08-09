#!/usr/bin/env python3
"""Focused tests for non-destructive namespaced-layout adoption."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/adopt-to-namespaced-layout.py"
SPEC = importlib.util.spec_from_file_location("copier_adoption", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CopierAdoptionTest(unittest.TestCase):
    def test_adoption_backs_up_and_preserves_legacy_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            self.write(repo / ".copier-answers.yml", "_commit: v0.4.5\n_src_path: local-template\n")
            self.write(repo / "AGENTS.md", "# Project Rules\n\nPreserve local routing.\n")
            self.write(repo / "docs/agent/SPEC_ENVIRONMENT.md", "project environment\n")
            self.write(
                repo / "docs/agent/external-services.yaml",
                "external_services:\n  mcp:\n    credential_env: provider-specific credentials\n",
            )
            self.write(repo / "scripts/create-plan.sh", "project plan helper\n")
            self.write(repo / ".codex/skills/decision-audit/SKILL.md", "project skill changes\n")
            self.write(repo / ".codex/agents/docs_researcher.toml", "project agent changes\n")
            self.write(repo / ".codex/hooks/stop_review_gate.py", "legacy stop hook\n")
            self.write(
                repo / ".codex/hooks.json",
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 .codex/hooks/agent_log_event.py --event Stop",
                                        }
                                    ]
                                }
                            ],
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 scripts/project-hook.py",
                                        }
                                    ]
                                }
                            ],
                        }
                    },
                    indent=2,
                )
                + "\n",
            )
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)

            def fake_recopy(
                destination: Path,
                copier_executable: str | None,
                target_ref: str,
                data: tuple[str, ...],
            ) -> None:
                self.assertIsNone(copier_executable)
                self.assertEqual(target_ref, "v1.1.2")
                self.assertEqual(data, ())
                self.write(destination / ".copier-answers.yml", "_commit: v1.1.2\n_src_path: local-template\n")
                self.write(destination / ".project-agent-workflow/AGENTS.md", "managed policy\n")
                self.write(destination / ".project-agent-workflow/ownership.yaml", "version: 1\n")
                self.write(destination / ".codex/hooks/stop_review_gate.py", "stable bridge\n")

            with patch.object(MODULE, "run_recopy", side_effect=fake_recopy):
                MODULE.adopt(repo, "v1.1.2", None, ())

            self.assertEqual(
                (repo / "docs/agent/SPEC_ENVIRONMENT.md").read_text(encoding="utf-8"),
                "project environment\n",
            )
            self.assertIn(
                "credential_env: provider-specific credentials",
                (repo / "docs/agent/external-services.yaml").read_text(encoding="utf-8"),
            )
            self.assertEqual((repo / "scripts/create-plan.sh").read_text(encoding="utf-8"), "project plan helper\n")
            self.assertEqual(
                (repo / ".codex/skills/decision-audit/SKILL.md").read_text(encoding="utf-8"),
                "project skill changes\n",
            )
            self.assertEqual(
                (repo / ".codex/agents/docs_researcher.toml").read_text(encoding="utf-8"),
                "project agent changes\n",
            )
            self.assertIn("project-agent-workflow:managed-core:start", (repo / "AGENTS.md").read_text(encoding="utf-8"))
            backup = repo / ".project-agent-workflow-migration/v1-pre-namespace"
            self.assertEqual((backup / ".codex/hooks/stop_review_gate.py").read_text(encoding="utf-8"), "legacy stop hook\n")
            manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["operation"], "recopy_adoption")
            self.assertEqual(manifest["previous_ref"], "v0.4.5")
            self.assertEqual(manifest["target_ref"], "v1.1.2")
            self.assertEqual(manifest["hook_configuration"], "added")
            self.assertEqual(
                manifest["legacy_schema_review_paths"],
                ["docs/agent/external-services.yaml"],
            )
            self.assertIn(
                "credential_env: provider-specific credentials",
                (backup / "docs/agent/external-services.yaml").read_text(encoding="utf-8"),
            )
            hooks = json.loads((repo / ".codex/hooks.json").read_text(encoding="utf-8"))
            serialized_hooks = json.dumps(hooks)
            self.assertIn("scripts/project-hook.py", serialized_hooks)
            self.assertIn(".project-agent-workflow/hooks/stop_review_gate.py", serialized_hooks)
            self.assertEqual(serialized_hooks.count("stop_review_gate.py"), 1)

    def test_adoption_rejects_the_published_unsafe_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self.write(repo / ".copier-answers.yml", "_commit: v0.4.5\n_src_path: local-template\n")
            with self.assertRaisesRegex(SystemExit, "v1.0.0 contains the unsafe"):
                MODULE.adopt(repo, "v1.0.0", None, ())

    def test_adoption_rejects_an_unversioned_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            with self.assertRaisesRegex(SystemExit, "stable release tag"):
                MODULE.adopt(repo, "main", None, ())

    def test_adoption_rejects_the_incomplete_v110_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            with self.assertRaisesRegex(SystemExit, "v1.1.0 contains incomplete"):
                MODULE.adopt(repo, "v1.1.0", None, ())

    def test_adoption_rejects_the_incomplete_v111_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            with self.assertRaisesRegex(SystemExit, "v1.1.1 contains an incomplete"):
                MODULE.adopt(repo, "v1.1.1", None, ())

    def test_conflict_scan_uses_git_visible_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self.write(repo / ".gitignore", ".venv/\nlegacy/**/.venv/\n")
            self.write(repo / "tracked-conflict.txt", "<<<<<<< tracked\n")
            subprocess.run(["git", "add", ".gitignore", "tracked-conflict.txt"], cwd=repo, check=True)
            self.write(repo / ".venv/LICENSE", "=======\n")
            self.write(repo / "legacy/app/.venv/METADATA", ">>>>>>> package\n")
            self.write(repo / ".project-agent-workflow-migration/v1-pre-namespace/old.py", "=======\n")
            self.write(repo / "src/untracked-conflict.txt", ">>>>>>> current\n")
            self.write(repo / "src/update.rej", "rejected patch\n")

            self.assertEqual(
                MODULE.conflict_paths(repo),
                ["src/untracked-conflict.txt", "src/update.rej", "tracked-conflict.txt"],
            )

    def test_unchanged_enabled_legacy_skillspector_becomes_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            content = b"legacy generated helper\n"
            self.write(
                repo / ".copier-answers.yml",
                "skillspector_mode: document_optional\n",
            )
            helper = repo / "scripts/skillspector-scan.sh"
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_bytes(content)
            manifest: dict[str, object] = {}
            digests = {"scripts/skillspector-scan.sh": hashlib.sha256(content).hexdigest()}

            with patch.object(MODULE, "LEGACY_OPTIONAL_DIGESTS", digests):
                retired, review = MODULE.reconcile_unchanged_optional_paths(repo, manifest)

            self.assertEqual(retired, [])
            self.assertEqual(review, [])
            self.assertEqual(helper.read_text(encoding="utf-8"), MODULE.SKILLSPECTOR_BRIDGE)
            self.assertEqual(
                manifest["bridged_legacy_optional_paths"],
                ["scripts/skillspector-scan.sh"],
            )

    def test_exact_legacy_cli_becomes_executable_bridge_after_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            destination = root / "destination"
            relative = "scripts/validate-changes.py"
            legacy = b"#!/usr/bin/env python3\nprint('legacy validator')\n"
            self.init_source(source, "v0.9.0", {relative: legacy})
            path = destination / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(legacy)
            manifest: dict[str, object] = {}
            backup = destination / MODULE.BACKUP_RELATIVE
            with patch.object(MODULE, "LEGACY_FILES", (relative,)), patch.object(
                MODULE, "LEGACY_SKILLS", ()
            ):
                MODULE.backup_legacy_paths(destination, backup, manifest)
            with patch.object(MODULE, "LEGACY_BRIDGEABLE_CLI_PATHS", (relative,)):
                bridged, modified, unverified = MODULE.reconcile_unchanged_legacy_cli_paths(
                    destination,
                    source,
                    "v0.9.0",
                    manifest,
                )

            self.assertEqual(bridged, [relative])
            self.assertEqual(modified, [])
            self.assertEqual(unverified, [])
            self.assertEqual((backup / relative).read_bytes(), legacy)
            self.assertEqual(path.read_bytes(), MODULE.legacy_cli_bridge(relative))
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_modified_legacy_cli_is_preserved_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            destination = root / "destination"
            relative = "scripts/validate-changes.py"
            generated = b"#!/usr/bin/env python3\nprint('generated')\n"
            modified_content = b"#!/usr/bin/env python3\nprint('project behavior')\n"
            self.init_source(source, "v0.9.0", {relative: generated})
            path = destination / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(modified_content)
            manifest: dict[str, object] = {}

            with patch.object(MODULE, "LEGACY_BRIDGEABLE_CLI_PATHS", (relative,)):
                bridged, modified, unverified = MODULE.reconcile_unchanged_legacy_cli_paths(
                    destination,
                    source,
                    "v0.9.0",
                    manifest,
                )

            self.assertEqual(bridged, [])
            self.assertEqual(modified, [relative])
            self.assertEqual(unverified, [])
            self.assertEqual(path.read_bytes(), modified_content)
            self.assertEqual(manifest["modified_legacy_cli_paths"], [relative])

    def test_missing_previous_object_and_symlink_are_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            destination = root / "destination"
            missing_object = "scripts/validate-changes.py"
            linked = "scripts/workflow-status.sh"
            self.init_source(source, "v1.0.0", {})
            self.write(destination / missing_object, "legacy validator\n")
            link_target = destination / "project-validator.sh"
            self.write(link_target, "project validator\n")
            link = destination / linked
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(link_target)
            manifest: dict[str, object] = {}

            with patch.object(
                MODULE,
                "LEGACY_BRIDGEABLE_CLI_PATHS",
                (missing_object, linked),
            ):
                _, modified, unverified = MODULE.reconcile_unchanged_legacy_cli_paths(
                    destination,
                    source,
                    "v1.0.0",
                    manifest,
                )

            self.assertEqual(modified, [])
            self.assertEqual(unverified, [missing_object, linked])
            self.assertTrue(link.is_symlink())
            self.assertEqual(
                manifest["unverified_legacy_cli_reasons"],
                {
                    missing_object: "previous_template_object_unavailable",
                    linked: "symbolic_link",
                },
            )

    def test_legacy_cli_bridge_reconciliation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            destination = root / "destination"
            relative = "scripts/workflow-status.sh"
            legacy = b"#!/bin/sh\necho legacy\n"
            self.init_source(source, "v0.9.0", {relative: legacy})
            path = destination / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(legacy)
            manifest: dict[str, object] = {}

            with patch.object(MODULE, "LEGACY_BRIDGEABLE_CLI_PATHS", (relative,)):
                first = MODULE.reconcile_unchanged_legacy_cli_paths(
                    destination,
                    source,
                    "v0.9.0",
                    manifest,
                )
                first_content = path.read_bytes()
                first_manifest = json.dumps(manifest, sort_keys=True)
                second = MODULE.reconcile_unchanged_legacy_cli_paths(
                    destination,
                    source,
                    "v0.9.0",
                    manifest,
                )

            self.assertEqual(second, first)
            self.assertEqual(path.read_bytes(), first_content)
            self.assertEqual(json.dumps(manifest, sort_keys=True), first_manifest)
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_root_validate_bridge_executes_managed_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            relative = "scripts/validate-changes.py"
            root_validator = repo / relative
            root_validator.parent.mkdir(parents=True)
            root_validator.write_bytes(MODULE.legacy_cli_bridge(relative))
            root_validator.chmod(0o755)
            self.write(
                repo / ".project-agent-workflow/scripts/validate-changes.py",
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "print(json.dumps({'validator': 'managed', 'args': sys.argv[1:]}))\n",
            )
            self.write(
                repo
                / ".project-agent-workflow-migration/v1-pre-namespace/scripts/validate-changes.py",
                "raise SystemExit('migration backup must not run')\n",
            )

            result = subprocess.run(
                [sys.executable, str(root_validator), "--all"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            self.assertEqual(
                json.loads(result.stdout),
                {"validator": "managed", "args": ["--all"]},
            )

    def test_importable_legacy_modules_are_not_execution_bridges(self) -> None:
        importable_modules = {
            "scripts/agent_log_manifest.py",
            "scripts/plan_validation_commands.py",
            "scripts/planlib.py",
            "scripts/security_rules.py",
        }

        self.assertTrue(importable_modules.isdisjoint(MODULE.LEGACY_BRIDGEABLE_CLI_PATHS))

    def init_source(self, repo: Path, tag: str, files: dict[str, bytes]) -> None:
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        if files:
            for relative, content in files.items():
                path = repo / "template" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        else:
            self.write(repo / "template/.keep", "\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "template source"], cwd=repo, check=True)
        subprocess.run(["git", "tag", tag], cwd=repo, check=True)

    @staticmethod
    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
