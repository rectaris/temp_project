"""Hook context-compression behavior tests."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .support import CONTEXT_COMPRESS, MANIFEST_CHECKER, MANIFEST_HELPER


class ContextCompressionBoundaryTest(unittest.TestCase):
    def prepare_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=root, stdout=subprocess.DEVNULL, check=True)
        scripts = root / ".project-agent-workflow/scripts"
        scripts.mkdir(parents=True)
        shutil.copyfile(CONTEXT_COMPRESS, scripts / "context-compress.sh")
        shutil.copyfile(MANIFEST_HELPER, scripts / "agent_log_manifest.py")
        shutil.copyfile(MANIFEST_CHECKER, scripts / "check-agent-log-manifest.py")

    def compress(self, repo: Path, source: str, run_id: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HEADROOM_DISABLED"] = "1"
        return subprocess.run(
            ["sh", ".project-agent-workflow/scripts/context-compress.sh", source, run_id],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_rejects_symlink_alias_for_normative_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            policy = repo / "docs/agent/POLICY.md"
            policy.parent.mkdir(parents=True)
            policy.write_text("normative\n", encoding="utf-8")
            (repo / "innocent.txt").symlink_to(policy)
            result = self.compress(repo, "innocent.txt", "symlink-run")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing normative agent instruction", result.stderr)

    def test_rejects_namespaced_normative_policy_before_writing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            policy = repo / ".project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md"
            policy.parent.mkdir(parents=True)
            policy.write_text("normative plan policy\n", encoding="utf-8")

            result = self.compress(
                repo,
                ".project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md",
                "namespaced-policy",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing normative agent instruction", result.stderr)
            self.assertFalse((repo / ".agent-logs/namespaced-policy").exists())

    def test_same_basename_sources_have_distinct_validated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            for directory, content in (("a", "first\n"), ("b", "second\n")):
                source = repo / "logs" / directory / "same.log"
                source.parent.mkdir(parents=True)
                source.write_text(content, encoding="utf-8")
                result = self.compress(repo, str(source.relative_to(repo)), "same-run")
                self.assertEqual(result.returncode, 0, result.stderr)

            run_dir = repo / ".agent-logs/same-run"
            outputs = sorted((run_dir / "compressed").glob("same.log.*.compressed.md"))
            self.assertEqual(len(outputs), 2)
            self.assertIn("first", outputs[0].read_text(encoding="utf-8") + outputs[1].read_text(encoding="utf-8"))
            self.assertIn("second", outputs[0].read_text(encoding="utf-8") + outputs[1].read_text(encoding="utf-8"))
            check = subprocess.run(
                [
                    "python3",
                    ".project-agent-workflow/scripts/check-agent-log-manifest.py",
                    ".agent-logs/same-run/manifest.json",
                ],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_manifest_rejects_escaping_declared_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            source = repo / "sample.log"
            source.write_text("sample\n", encoding="utf-8")
            result = self.compress(repo, "sample.log", "escape-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest_path = repo / ".agent-logs/escape-run/manifest.json"
            base_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cases = {
                "raw_logs": ["../outside.log"],
                "transcript_log": "../outside.jsonl",
                "hook_event_log": "../outside.jsonl",
                "plans": ["../outside.md"],
                "artifacts": ["../outside.bin"],
                "compressed_outputs": ["../outside.md"],
                "redaction_report": "../outside.md",
            }
            for field, value in cases.items():
                with self.subTest(field=field):
                    manifest = dict(base_manifest)
                    manifest[field] = value
                    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
                    check = subprocess.run(
                        ["python3", ".project-agent-workflow/scripts/check-agent-log-manifest.py", str(manifest_path)],
                        cwd=repo,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertNotEqual(check.returncode, 0)
                    self.assertIn("safe", check.stderr)

    def test_concurrent_manifest_updates_preserve_both_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.prepare_repo(repo)
            sources = []
            for name in ("first.log", "second.log"):
                source = repo / "logs" / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(name + "\n", encoding="utf-8")
                sources.append(str(source.relative_to(repo)))
            env = os.environ.copy()
            env["HEADROOM_DISABLED"] = "1"
            processes = [
                subprocess.Popen(
                    ["sh", ".project-agent-workflow/scripts/context-compress.sh", source, "parallel-run"],
                    cwd=repo,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for source in sources
            ]
            for process in processes:
                _, stderr = process.communicate()
                self.assertEqual(process.returncode, 0, stderr)
            manifest = json.loads((repo / ".agent-logs/parallel-run/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["artifacts"]), 2)
            self.assertEqual(len(manifest["compressed_outputs"]), 2)



if __name__ == "__main__":
    unittest.main()
