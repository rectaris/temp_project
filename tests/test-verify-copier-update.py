#!/usr/bin/env python3
"""Deterministic tests for the isolated Copier update verification Skill."""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".codex/skills/verify-copier-update/scripts/verify-copier-update.py"
SKILL = HELPER.parent.parent
TRIAGE = SKILL / "scripts/triage-copier-update.py"
COVERAGE = SKILL / "scripts/check-triage-coverage.py"
TABLE = SKILL / "references/update-triage.yaml"
TEMPLATE_SKILL = ROOT / "template/.project-agent-workflow/skills/verify-copier-update"
DOWNSTREAM = ROOT / "scripts/verify-downstream-baselines.py"
BASELINES = ROOT / "docs/downstream-baselines.yaml"


def load_helper_module():
    spec = importlib.util.spec_from_file_location("verify_copier_update_helper", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load verification helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(arguments: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write(path: Path, value: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def initialize_repository(path: Path, message: str) -> str:
    run(["git", "init", "--quiet"], path)
    run(["git", "config", "user.name", "Test"], path)
    run(["git", "config", "user.email", "test@example.invalid"], path)
    run(["git", "add", "-A"], path)
    run(["git", "commit", "--quiet", "-m", message], path)
    return run(["git", "rev-parse", "HEAD"], path).stdout.strip()


def raw_repository_identity(path: Path) -> tuple[object, ...]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"

    def git_output(*arguments: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(path), *arguments],
            env=environment,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout

    def git_path(*arguments: str) -> Path:
        return Path(git_output(*arguments).decode("utf-8").strip())

    def file_identity(file_path: Path) -> tuple[object, ...]:
        metadata = file_path.lstat()
        value = os.readlink(file_path) if file_path.is_symlink() else file_path.read_bytes()
        return (
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
            metadata.st_ino,
            metadata.st_dev,
            value,
        )

    def git_state_file_identity(file_path: Path) -> tuple[object, ...]:
        metadata = file_path.lstat()
        value = os.readlink(file_path) if file_path.is_symlink() else file_path.read_bytes()
        return (metadata.st_mode, value)

    git_directories = {
        git_path("rev-parse", "--absolute-git-dir"),
        git_path("rev-parse", "--path-format=absolute", "--git-common-dir"),
    }
    shared_indexes = tuple(
        (candidate.name, git_state_file_identity(candidate))
        for directory in sorted(git_directories, key=os.fspath)
        for candidate in sorted(directory.glob("sharedindex.*"), key=lambda item: item.name)
    )
    ignored_paths = [
        item
        for item in git_output(
            "ls-files", "--others", "--ignored", "--exclude-standard", "-z"
        ).split(b"\0")
        if item
    ]
    ignored = tuple(
        (raw, file_identity(path / raw.decode("utf-8", errors="surrogateescape")))
        for raw in ignored_paths
    )
    return (
        git_state_file_identity(git_path("rev-parse", "--path-format=absolute", "--git-path", "HEAD")),
        git_state_file_identity(git_path("rev-parse", "--path-format=absolute", "--git-path", "index")),
        shared_indexes,
        git_output("for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)%00"),
        ignored,
    )


class VerifyCopierUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="verify-copier-update-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.target = self.root / "target-repository"
        self.bin = self.root / "bin"
        self.source.mkdir()
        self.target.mkdir()
        self.bin.mkdir()

        write(self.source / "mode.txt", "ok\n")
        self.source_oid = initialize_repository(self.source, "source")
        run(["git", "tag", "v1.1.0"], self.source)

        write(
            self.target / ".copier-answers.yml",
            "# managed answers\n_commit: v1.0.0\n_src_path: ../source\n",
        )
        write(
            self.target / ".project-agent-workflow/scripts/update-from-copier.sh",
            textwrap.dedent(
                """\
                #!/bin/sh
                set -eu
                copier update --trust "$@"
                python3 .project-agent-workflow/scripts/validate-copier-update.py --destination .
                """
            ),
            0o755,
        )
        write(
            self.target / ".project-agent-workflow/scripts/validate-copier-update.py",
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                from pathlib import Path
                import sys
                if Path("unsafe.marker").exists():
                    print("unsafe marker", file=sys.stderr)
                    raise SystemExit(1)
                print("validator passed")
                """
            ),
            0o755,
        )
        write(
            self.target / ".project-agent-workflow/scripts/validate-changes.py",
            "#!/usr/bin/env python3\nprint('change validation passed')\n",
            0o755,
        )
        write(self.target / "product.txt", "preserve me\n")
        self.target_oid = initialize_repository(self.target, "target")

        write(
            self.bin / "copier",
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                from pathlib import Path

                mode = Path("../source/mode.txt").read_text(encoding="utf-8").strip()
                Path(".project-agent-workflow/generated.txt").write_text("updated\\n", encoding="utf-8")
                answers = Path(".copier-answers.yml")
                answers.write_text(
                    answers.read_text(encoding="utf-8").replace("_commit: v1.0.0", "_commit: v1.1.0"),
                    encoding="utf-8",
                )
                if mode == "reject":
                    Path("unsafe.marker").write_text("unsafe\\n", encoding="utf-8")
                """
            ),
            0o755,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(
        self,
        output_name: str,
        *,
        validation: str | None = None,
        trust: bool = True,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        output = self.root / output_name
        command = [
            "python3",
            str(HELPER),
            "--target",
            str(self.target),
            "--source",
            str(self.source),
            "--source-ref",
            "v1.1.0",
            "--output-dir",
            str(output),
        ]
        if trust:
            command.append("--trust-template-tasks")
        if validation is None:
            validation = json.dumps(
                [
                    "python3",
                    "-c",
                    "from pathlib import Path; assert Path('product.txt').read_text() == 'preserve me\\n'; assert Path('.project-agent-workflow/generated.txt').read_text() == 'updated\\n'",
                ]
            )
        command.extend(["--validation-command-json", validation])
        environment = os.environ.copy()
        environment["PATH"] = f"{self.bin}{os.pathsep}{environment.get('PATH', '')}"
        process = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process, output

    def manifest(self, output: Path) -> dict[str, object]:
        return json.loads((output / "verification-manifest.json").read_text(encoding="utf-8"))

    def assert_originals_unchanged(self) -> None:
        self.assertEqual(self.target_oid, run(["git", "rev-parse", "HEAD"], self.target).stdout.strip())
        self.assertEqual(self.source_oid, run(["git", "rev-parse", "HEAD"], self.source).stdout.strip())
        self.assertEqual("", run(["git", "status", "--porcelain"], self.target).stdout)
        self.assertEqual("", run(["git", "status", "--porcelain"], self.source).stdout)
        self.assertEqual("preserve me\n", (self.target / "product.txt").read_text(encoding="utf-8"))

    def test_verified_update_is_isolated_and_idempotent(self) -> None:
        process, output = self.invoke("verified")
        self.assertEqual(0, process.returncode, process.stderr)
        manifest = self.manifest(output)
        self.assertEqual("verified", manifest["result"])
        self.assertEqual("all_checks_passed", manifest["reason_code"])
        self.assertEqual(self.target_oid, manifest["target"]["baseline_oid"])
        self.assertEqual(self.source_oid, manifest["source"]["commit_oid"])
        self.assertEqual("generated_wrapper", manifest["update_path"])
        self.assertTrue(any(item["path"] == ".project-agent-workflow/generated.txt" for item in manifest["changed_paths"]))
        self.assertNotIn(str(self.target), json.dumps(manifest))
        self.assertNotIn(str(self.source), json.dumps(manifest))
        self.assert_originals_unchanged()

    def record_remote_source(self, recorded: str) -> str:
        write(
            self.target / ".copier-answers.yml",
            f"# managed answers\n_commit: v1.0.0\n_src_path: {recorded}\n",
        )
        run(["git", "add", ".copier-answers.yml"], self.target)
        run(["git", "commit", "-qm", "record a remote template path"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        return self.target_oid

    def test_remote_src_path_is_verified_against_the_local_checkout(self) -> None:
        baseline = self.record_remote_source("https://github.com/example/template.git")
        process, output = self.invoke("remote-https")
        self.assertEqual(0, process.returncode, process.stderr)
        manifest = self.manifest(output)
        self.assertEqual("verified", manifest["result"])
        self.assertEqual(baseline, manifest["target"]["baseline_oid"])
        self.assertEqual("https://github.com/example/template.git", manifest["source"]["recorded_src_path"])
        self.assertEqual("../source", manifest["source"]["isolated_src_path"])
        self.assertNotEqual(baseline, manifest["target"]["isolated_baseline_oid"])
        self.assert_originals_unchanged()

    def test_scp_style_src_path_is_verified_against_the_local_checkout(self) -> None:
        self.record_remote_source("git@github.com:example/template.git")
        process, output = self.invoke("remote-scp")
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual("verified", self.manifest(output)["result"])
        self.assert_originals_unchanged()

    def test_a_relative_src_path_keeps_the_original_baseline(self) -> None:
        process, output = self.invoke("relative")
        manifest = self.manifest(output)
        self.assertEqual("../source", manifest["source"]["recorded_src_path"])
        self.assertEqual("../source", manifest["source"]["isolated_src_path"])
        self.assertNotIn("isolated_baseline_oid", manifest["target"])
        self.assertEqual(0, process.returncode, process.stderr)

    def test_snapshot_inspection_does_not_change_original_git_state(self) -> None:
        write(self.target / ".gitignore", "ignored-state.txt\n")
        run(["git", "add", ".gitignore"], self.target)
        run(["git", "commit", "--quiet", "-m", "ignore runtime state"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        write(self.target / "ignored-state.txt", "runtime\n")
        run(["git", "update-index", "--split-index"], self.target)
        product_metadata = (self.target / "product.txt").stat()
        os.utime(
            self.target / "product.txt",
            ns=(product_metadata.st_atime_ns, product_metadata.st_mtime_ns + 2_000_000_000),
        )
        target_before = raw_repository_identity(self.target)
        source_before = raw_repository_identity(self.source)
        process, output = self.invoke("snapshot-preservation")
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual("verified", self.manifest(output)["result"])
        self.assertEqual(target_before, raw_repository_identity(self.target))
        self.assertEqual(source_before, raw_repository_identity(self.source))

    def test_external_clean_filter_is_blocked_without_execution(self) -> None:
        write(self.target / ".gitattributes", "product.txt filter=mutating\n")
        run(["git", "add", ".gitattributes"], self.target)
        run(["git", "commit", "--quiet", "-m", "declare clean filter"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        marker = self.target / "filter-ran.marker"
        filter_script = self.bin / "mutating-filter"
        write(
            filter_script,
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import sys\n"
            f"Path({str(marker)!r}).write_text('ran\\n')\n"
            "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
            0o755,
        )
        run(["git", "config", "filter.mutating.clean", str(filter_script)], self.target)
        product_metadata = (self.target / "product.txt").stat()
        os.utime(
            self.target / "product.txt",
            ns=(product_metadata.st_atime_ns, product_metadata.st_mtime_ns + 2_000_000_000),
        )
        process, output = self.invoke("external-clean-filter")
        self.assertEqual(2, process.returncode)
        self.assertEqual("target_external_filter_unsupported", self.manifest(output)["reason_code"])
        self.assertFalse(marker.exists())

    def test_observed_validator_failure_is_rejected(self) -> None:
        write(self.source / "mode.txt", "reject\n")
        run(["git", "add", "mode.txt"], self.source)
        run(["git", "commit", "--quiet", "-m", "reject mode"], self.source)
        run(["git", "tag", "--force", "v1.1.0"], self.source)
        self.source_oid = run(["git", "rev-parse", "HEAD"], self.source).stdout.strip()
        process, output = self.invoke("rejected")
        self.assertEqual(1, process.returncode)
        manifest = self.manifest(output)
        self.assertEqual("rejected", manifest["result"])
        self.assertEqual("update_failed", manifest["reason_code"])
        self.assert_originals_unchanged()

    def test_dirty_target_is_blocked(self) -> None:
        write(self.target / "untracked.txt", "dirty\n")
        process, output = self.invoke("dirty-target")
        self.assertEqual(2, process.returncode)
        self.assertEqual("target_dirty", self.manifest(output)["reason_code"])

    def test_dirty_source_is_blocked(self) -> None:
        write(self.source / "untracked.txt", "dirty\n")
        process, output = self.invoke("dirty-source")
        self.assertEqual(2, process.returncode)
        self.assertEqual("source_dirty", self.manifest(output)["reason_code"])

    def test_missing_trust_is_blocked(self) -> None:
        process, output = self.invoke("missing-trust", trust=False)
        self.assertEqual(2, process.returncode)
        self.assertEqual("template_trust_missing", self.manifest(output)["reason_code"])

    def test_invalid_validation_argv_is_blocked(self) -> None:
        process, output = self.invoke("invalid-validation", validation='{"command":"npm test"}')
        self.assertEqual(2, process.returncode)
        self.assertEqual("invalid_command_argv", self.manifest(output)["reason_code"])

    def test_unsafe_copier_launcher_is_blocked(self) -> None:
        output = self.root / "unsafe-launcher"
        command = [
            "python3",
            str(HELPER),
            "--target",
            str(self.target),
            "--source",
            str(self.source),
            "--source-ref",
            "v1.1.0",
            "--output-dir",
            str(output),
            "--trust-template-tasks",
            "--copier-command-json",
            '["sh","-c","copier update --force"]',
            "--validation-command-json",
            '["python3","-c","pass"]',
        ]
        process = subprocess.run(command, cwd=ROOT, check=False)
        self.assertEqual(2, process.returncode)
        self.assertEqual("unsafe_copier_launcher", self.manifest(output)["reason_code"])

    def test_validation_cannot_change_the_update_result(self) -> None:
        validation = json.dumps(
            [
                "python3",
                "-c",
                "from pathlib import Path; Path('product.txt').write_text('changed\\n')",
            ]
        )
        process, output = self.invoke("validation-mutates", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("validation_changed_worktree", self.manifest(output)["reason_code"])
        self.assert_originals_unchanged()

    def test_validation_cannot_change_the_isolated_source(self) -> None:
        validation = json.dumps(
            [
                "python3",
                "-c",
                "from pathlib import Path; Path('../source/mode.txt').write_text('changed\\n')",
            ]
        )
        process, output = self.invoke("validation-mutates-source", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("validation_source_changed", self.manifest(output)["reason_code"])
        self.assert_originals_unchanged()

    def test_source_path_cannot_overlap_private_scratch(self) -> None:
        answers = self.target / ".copier-answers.yml"
        answers.write_text(
            answers.read_text(encoding="utf-8").replace("_src_path: ../source", "_src_path: ../home"),
            encoding="utf-8",
        )
        run(["git", "add", ".copier-answers.yml"], self.target)
        run(["git", "commit", "--quiet", "-m", "overlap scratch"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        process, output = self.invoke("scratch-overlap")
        self.assertEqual(2, process.returncode)
        self.assertEqual("source_path_scratch_overlap", self.manifest(output)["reason_code"])
        self.assert_originals_unchanged()

    def test_disposable_commit_does_not_run_project_hook(self) -> None:
        validation = json.dumps(
            [
                "python3",
                "-c",
                "from pathlib import Path; hook=Path('.git/hooks/pre-commit'); hook.write_text(\"#!/bin/sh\\nprintf 'hook ran\\n' > hook-ran.marker\\nprintf 'changed\\n' > product.txt\\ngit add product.txt hook-ran.marker\\n\"); hook.chmod(0o755)",
            ]
        )
        process, output = self.invoke("commit-hook", validation=validation)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual("verified", self.manifest(output)["result"])
        target_clone = output / "workspace/target"
        self.assertFalse((target_clone / "hook-ran.marker").exists())
        self.assertEqual("preserve me\n", (target_clone / "product.txt").read_text(encoding="utf-8"))
        self.assert_originals_unchanged()

    def test_original_mutation_is_rejected_not_blocked(self) -> None:
        original_product = self.target / "product.txt"
        validation = json.dumps(
            [
                "python3",
                "-c",
                f"from pathlib import Path; Path({str(original_product)!r}).write_text('changed\\n')",
            ]
        )
        process, output = self.invoke("original-mutates", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])
        self.assertEqual("changed\n", original_product.read_text(encoding="utf-8"))
        self.assertEqual(self.source_oid, run(["git", "rev-parse", "HEAD"], self.source).stdout.strip())
        self.assertEqual("", run(["git", "status", "--porcelain"], self.source).stdout)

    def test_original_mutation_is_rejected_even_when_validation_fails(self) -> None:
        original_product = self.target / "product.txt"
        validation = json.dumps(
            [
                "python3",
                "-c",
                f"from pathlib import Path; Path({str(original_product)!r}).write_text('changed\\n'); raise SystemExit(7)",
            ]
        )
        process, output = self.invoke("original-mutates-before-failure", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_original_source_mutation_is_rejected_when_validation_fails(self) -> None:
        source_mode = self.source / "mode.txt"
        validation = json.dumps(
            [
                "python3",
                "-c",
                f"from pathlib import Path; Path({str(source_mode)!r}).write_text('changed\\n'); raise SystemExit(7)",
            ]
        )
        process, output = self.invoke("original-source-mutates-before-failure", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_source_changed", self.manifest(output)["reason_code"])

    def test_original_state_unavailable_overrides_prior_result(self) -> None:
        original_git = self.target / ".git"
        moved_git = self.target / ".git.moved"
        validation = json.dumps(
            [
                "python3",
                "-c",
                f"from pathlib import Path; Path({str(original_git)!r}).rename(Path({str(moved_git)!r})); raise SystemExit(7)",
            ]
        )
        process, output = self.invoke("original-state-unavailable", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_state_unavailable", self.manifest(output)["reason_code"])

    def test_tracked_raw_bytes_hidden_by_eol_normalization_are_protected(self) -> None:
        write(self.target / ".gitattributes", "product.txt text\n")
        (self.target / "product.txt").write_bytes(b"line one\r\nline two\n")
        run(["git", "add", ".gitattributes", "product.txt"], self.target)
        run(["git", "commit", "--quiet", "-m", "normalize product text"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        self.assertEqual("", run(["git", "status", "--porcelain"], self.target).stdout)
        original_product = self.target / "product.txt"
        validation = json.dumps(
            [
                "python3",
                "-c",
                f"from pathlib import Path; Path({str(original_product)!r}).write_bytes(b'line one\\nline two\\r\\n')",
            ]
        )
        process, output = self.invoke("original-eol-normalized-mutation", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_actual_mode_change_is_detected_when_core_filemode_is_false(self) -> None:
        run(["git", "config", "core.filemode", "false"], self.target)
        original_product = self.target / "product.txt"
        validation = json.dumps(
            ["python3", "-c", f"from pathlib import Path; Path({str(original_product)!r}).chmod(0o755)"]
        )
        process, output = self.invoke("original-mode-mutates", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_original_ref_mutation_is_rejected(self) -> None:
        validation = json.dumps(
            [
                "git",
                "-C",
                str(self.target),
                "branch",
                "unexpected-ref",
            ]
        )
        process, output = self.invoke("original-ref-mutates", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_original_assume_unchanged_flag_mutation_is_rejected(self) -> None:
        validation = json.dumps(
            ["git", "-C", str(self.target), "update-index", "--assume-unchanged", "product.txt"]
        )
        process, output = self.invoke("original-assume-unchanged", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_existing_assume_unchanged_flag_is_blocked_before_update(self) -> None:
        run(["git", "update-index", "--assume-unchanged", "product.txt"], self.target)
        process, output = self.invoke("existing-assume-unchanged")
        self.assertEqual(2, process.returncode)
        self.assertEqual("target_index_flags_unsupported", self.manifest(output)["reason_code"])
        self.assertEqual("preserve me\n", (self.target / "product.txt").read_text(encoding="utf-8"))

    def test_original_skip_worktree_flag_mutation_is_rejected(self) -> None:
        validation = json.dumps(
            ["git", "-C", str(self.target), "update-index", "--skip-worktree", "product.txt"]
        )
        process, output = self.invoke("original-skip-worktree", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_existing_skip_worktree_flag_is_blocked_before_update(self) -> None:
        run(["git", "update-index", "--skip-worktree", "product.txt"], self.target)
        process, output = self.invoke("existing-skip-worktree")
        self.assertEqual(2, process.returncode)
        self.assertEqual("target_index_flags_unsupported", self.manifest(output)["reason_code"])
        self.assertEqual("preserve me\n", (self.target / "product.txt").read_text(encoding="utf-8"))

    def test_submodule_entry_is_blocked_before_update(self) -> None:
        blob = run(["git", "rev-parse", "HEAD"], self.source).stdout.strip()
        run(["git", "update-index", "--add", "--cacheinfo", "160000", blob, "nested-source"], self.target)
        run(["git", "commit", "--quiet", "-m", "add gitlink"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        process, output = self.invoke("submodule-entry")
        self.assertEqual(2, process.returncode)
        self.assertEqual("target_submodule_unsupported", self.manifest(output)["reason_code"])

    def test_original_symbolic_head_mutation_is_rejected(self) -> None:
        run(["git", "branch", "same-commit"], self.target)
        validation = json.dumps(
            ["git", "-C", str(self.target), "symbolic-ref", "HEAD", "refs/heads/same-commit"]
        )
        process, output = self.invoke("original-symbolic-head", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_original_split_index_creation_is_rejected(self) -> None:
        validation = json.dumps(
            ["git", "-C", str(self.target), "update-index", "--split-index"]
        )
        process, output = self.invoke("original-split-index", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_original_ignored_file_mutation_is_rejected(self) -> None:
        write(self.target / ".gitignore", "ignored-state.txt\n")
        run(["git", "add", ".gitignore"], self.target)
        run(["git", "commit", "--quiet", "-m", "ignore runtime state"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        ignored = self.target / "ignored-state.txt"
        write(ignored, "before\n")
        validation = json.dumps(
            [
                "python3",
                "-c",
                f"from pathlib import Path; Path({str(ignored)!r}).write_text('after value\\n')",
            ]
        )
        process, output = self.invoke("original-ignored-mutates", validation=validation)
        self.assertEqual(1, process.returncode)
        self.assertEqual("original_target_changed", self.manifest(output)["reason_code"])

    def test_ignored_file_error_detail_does_not_expose_repository_path(self) -> None:
        write(self.target / ".gitignore", "ignored-state.txt\n")
        run(["git", "add", ".gitignore"], self.target)
        run(["git", "commit", "--quiet", "-m", "ignore runtime state"], self.target)
        write(self.target / "ignored-state.txt", "runtime\n")
        helper = load_helper_module()
        environment = os.environ.copy()
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        with mock.patch.object(
            helper.Path,
            "lstat",
            side_effect=OSError(f"unavailable: {self.target}/ignored-state.txt"),
        ):
            with self.assertRaises(helper.VerificationStop) as caught:
                helper.ignored_file_identity(self.target, environment, "target")
        self.assertEqual("target_ignored_file_unavailable", caught.exception.reason_code)
        self.assertNotIn(str(self.target), caught.exception.detail)

    def test_ignored_symlink_error_is_bounded(self) -> None:
        write(self.target / ".gitignore", "ignored-link\n")
        run(["git", "add", ".gitignore"], self.target)
        run(["git", "commit", "--quiet", "-m", "ignore runtime link"], self.target)
        (self.target / "ignored-link").symlink_to("runtime-target")
        helper = load_helper_module()
        environment = os.environ.copy()
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        with mock.patch.object(
            helper.os,
            "readlink",
            side_effect=OSError(f"unavailable: {self.target}/ignored-link"),
        ):
            with self.assertRaises(helper.VerificationStop) as caught:
                helper.ignored_file_identity(self.target, environment, "target")
        self.assertEqual("target_ignored_symlink_unavailable", caught.exception.reason_code)
        self.assertNotIn(str(self.target), caught.exception.detail)

    def test_command_start_error_manifest_does_not_expose_repository_path(self) -> None:
        missing = self.target / "missing-command"
        process, output = self.invoke(
            "missing-validation-command",
            validation=json.dumps([str(missing)]),
        )
        self.assertEqual(2, process.returncode)
        manifest = self.manifest(output)
        self.assertEqual("command_unavailable", manifest["reason_code"])
        self.assertNotIn(str(self.target), json.dumps(manifest))

    def test_dangling_wrapper_symlink_is_rejected(self) -> None:
        wrapper = self.target / ".project-agent-workflow/scripts/update-from-copier.sh"
        wrapper.unlink()
        wrapper.symlink_to("missing-wrapper")
        run(["git", "add", "-A"], self.target)
        run(["git", "commit", "--quiet", "-m", "dangling wrapper"], self.target)
        self.target_oid = run(["git", "rev-parse", "HEAD"], self.target).stdout.strip()
        process, output = self.invoke("dangling-wrapper")
        self.assertEqual(1, process.returncode)
        self.assertEqual("update_wrapper_invalid", self.manifest(output)["reason_code"])

    def test_output_inside_target_is_rejected_before_creation(self) -> None:
        output = self.target / "evidence"
        command = [
            "python3",
            str(HELPER),
            "--target",
            str(self.target),
            "--source",
            str(self.source),
            "--source-ref",
            "v1.1.0",
            "--output-dir",
            str(output),
            "--trust-template-tasks",
            "--validation-command-json",
            '["python3","-c","pass"]',
        ]
        process = subprocess.run(command, cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(2, process.returncode)
        self.assertIn("output directory must be outside", process.stderr)
        self.assertFalse(output.exists())


def load_triage_module():
    spec = importlib.util.spec_from_file_location("triage_copier_update_helper", TRIAGE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load triage resolver")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_manifest(directory: Path, result: str, reason_code: str) -> Path:
    path = directory / "verification-manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "result": result,
                "reason_code": reason_code,
                "detail": "recorded detail",
                "unresolved": [],
            }
        ),
        encoding="utf-8",
    )
    return path


class TriageTableTest(unittest.TestCase):
    def setUp(self) -> None:
        self.triage = load_triage_module()
        self.table = self.triage.require_table(TABLE)

    def test_bundled_reader_matches_the_yaml_library(self) -> None:
        import yaml

        expected = yaml.safe_load(TABLE.read_text(encoding="utf-8"))
        self.assertEqual(expected, self.triage.parse_triage_without_yaml(TABLE))

    def test_reader_is_used_when_the_yaml_library_is_absent(self) -> None:
        real_import = __import__

        def without_yaml(name, *arguments):
            if name == "yaml":
                raise ModuleNotFoundError("No module named 'yaml'")
            return real_import(name, *arguments)

        with mock.patch("builtins.__import__", without_yaml):
            loaded = self.triage.load_yaml(TABLE)
        self.assertEqual(self.table["schema_version"], loaded["schema_version"])

    def test_every_emitted_reason_code_is_classified(self) -> None:
        process = run(["python3", str(COVERAGE)], ROOT, check=False)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn("reason codes classified", process.stdout)

    def test_coverage_check_reports_an_unclassified_code(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            table = Path(raw) / "update-triage.yaml"
            text = TABLE.read_text(encoding="utf-8")
            table.write_text(text.replace("  git_unavailable:\n", "  git_absent:\n", 1), encoding="utf-8")
            process = run(
                ["python3", str(COVERAGE), "--triage-table", str(table)], ROOT, check=False
            )
        self.assertEqual(1, process.returncode)
        self.assertIn("git_unavailable", process.stderr)

    def test_longest_subject_wins_over_a_shorter_one(self) -> None:
        entry = self.triage.resolve_code(self.table, "final_target_index_state_short_read")
        self.assertEqual("final_target_index_state", entry["subject"])
        self.assertEqual("short_read", entry["matched"])

    def test_an_exact_code_wins_over_a_subject_split(self) -> None:
        entry = self.triage.resolve_code(self.table, "source_path_escape")
        self.assertEqual("code", entry["match"])
        self.assertIsNone(entry.get("subject"))

    def test_an_unknown_code_is_refused_rather_than_guessed(self) -> None:
        with self.assertRaises(self.triage.TriageError):
            self.triage.resolve_code(self.table, "brand_new_code")

    def test_a_stop_exception_built_without_raising_is_still_classified(self) -> None:
        for code in (
            "original_target_state_unavailable",
            "original_target_changed",
            "original_source_state_unavailable",
            "original_source_changed",
        ):
            with self.subTest(code=code):
                self.assertEqual("environment", self.triage.resolve_code(self.table, code)["owner"])

    def test_recorded_answer_faults_belong_to_the_project(self) -> None:
        for code in (
            "absolute_source_path",
            "source_path_escape",
            "source_path_overlap",
            "source_path_scratch_overlap",
            "update_wrapper_invalid",
        ):
            with self.subTest(code=code):
                self.assertEqual("project", self.triage.resolve_code(self.table, code)["owner"])

    def test_a_shared_suffix_reports_the_repository_that_owns_it(self) -> None:
        for code, owner in (
            ("source_dirty", "template"),
            ("target_dirty", "project"),
            ("source_head_state_short_read", "template"),
            ("target_head_state_short_read", "project"),
            ("update_source_changed", "template"),
            ("final_target_invalid_oid", "project"),
        ):
            with self.subTest(code=code):
                self.assertEqual(owner, self.triage.resolve_code(self.table, code)["owner"])

    def test_a_subject_override_outranks_the_subject_owner(self) -> None:
        for code, owner in (
            ("source_unavailable", "invocation"),
            ("target_unavailable", "invocation"),
            ("source_head_state_unavailable", "template"),
        ):
            with self.subTest(code=code):
                self.assertEqual(owner, self.triage.resolve_code(self.table, code)["owner"])

    def test_a_resolved_entry_does_not_leak_the_override_mapping(self) -> None:
        self.assertNotIn("subject_owners", self.triage.resolve_code(self.table, "source_dirty"))

    def test_every_declared_subject_owner_is_known(self) -> None:
        for subject, owner in self.table["subjects"].items():
            with self.subTest(subject=subject):
                self.assertIn(owner, self.triage.SUBJECT_OWNERS)

    def test_a_table_that_overrides_an_undeclared_subject_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            table = Path(raw) / "update-triage.yaml"
            table.write_text(
                TABLE.read_text(encoding="utf-8").replace(
                    "      source: invocation\n", "      no_such_subject: invocation\n", 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(self.triage.TriageError) as caught:
                self.triage.require_table(table)
        self.assertIn("undeclared subject", str(caught.exception))

    def test_an_exact_code_may_not_take_its_owner_from_a_subject(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            table = Path(raw) / "update-triage.yaml"
            table.write_text(
                TABLE.read_text(encoding="utf-8").replace(
                    "    owner: template\n", "    owner: from_subject\n", 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(self.triage.TriageError) as caught:
                self.triage.require_table(table)
        self.assertIn("owner from a subject", str(caught.exception))

    def test_the_bundled_reader_refuses_syntax_it_cannot_reproduce(self) -> None:
        original = TABLE.read_text(encoding="utf-8")
        for replacement in (
            '    owner: "environment"\n',
            "    owner: environment # inline\n",
        ):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as raw:
                table = Path(raw) / "update-triage.yaml"
                table.write_text(
                    original.replace("    owner: environment\n", replacement, 1), encoding="utf-8"
                )
                with self.assertRaises(self.triage.TriageError):
                    self.triage.parse_triage_without_yaml(table)

    def test_the_template_copy_is_identical(self) -> None:
        for relative in (
            "SKILL.md",
            "references/update-triage.yaml",
            "scripts/triage-copier-update.py",
            "scripts/check-triage-coverage.py",
        ):
            with self.subTest(relative=relative):
                self.assertEqual(
                    (SKILL / relative).read_bytes(), (TEMPLATE_SKILL / relative).read_bytes()
                )


class TriageResolverTest(unittest.TestCase):
    def test_a_passing_manifest_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = write_manifest(Path(raw), "verified", "all_checks_passed")
            process = run(["python3", str(TRIAGE), str(manifest)], ROOT, check=False)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn("owner: none", process.stdout)

    def test_a_failing_manifest_exits_one_with_an_owner(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = write_manifest(Path(raw), "rejected", "not_idempotent")
            process = run(
                ["python3", str(TRIAGE), str(manifest), "--format", "json"], ROOT, check=False
            )
        self.assertEqual(1, process.returncode)
        report = json.loads(process.stdout)
        self.assertEqual("template", report["owner"])
        self.assertEqual("never", report["retry"])

    def test_an_unclassified_code_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = write_manifest(Path(raw), "rejected", "brand_new_code")
            process = run(["python3", str(TRIAGE), str(manifest)], ROOT, check=False)
        self.assertEqual(2, process.returncode)
        self.assertIn("not classified", process.stderr)

    def test_a_manifest_that_contradicts_the_table_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = write_manifest(Path(raw), "verified", "not_idempotent")
            process = run(["python3", str(TRIAGE), str(manifest)], ROOT, check=False)
        self.assertEqual(2, process.returncode)
        self.assertIn("disagree", process.stderr)

    def test_an_unusable_manifest_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = Path(raw) / "verification-manifest.json"
            manifest.write_text("{ not json", encoding="utf-8")
            process = run(["python3", str(TRIAGE), str(manifest)], ROOT, check=False)
        self.assertEqual(2, process.returncode)
        self.assertIn("not valid JSON", process.stderr)


class RemoteSourceDetectionTest(unittest.TestCase):
    """Pin the helper's classification to the one Copier itself performs.

    A value the helper calls remote is verified against the isolated checkout, so a
    disagreement with Copier would either verify against a source the real update
    never uses or refuse a project Copier can update.
    """

    def setUp(self) -> None:
        self.helper = load_helper_module()

    def test_a_source_copier_would_clone_is_recognised(self) -> None:
        for recorded in (
            "https://github.com/rectaris/temp_project.git",
            "https://github.com/rectaris/temp_project",
            "https://gitlab.com/rectaris/temp_project",
            "git@github.com:rectaris/temp_project.git",
            "git://example.invalid/template.git",
            "git+https://example.invalid/template",
            "gh:rectaris/temp_project",
            "gl:rectaris/temp_project",
            "ssh://example.invalid/template.git",
        ):
            with self.subTest(recorded=recorded):
                self.assertTrue(self.helper.is_remote_source(recorded))

    def test_a_source_copier_would_read_as_a_path_is_not(self) -> None:
        for recorded in (
            "../temp_project",
            "./template",
            "template",
            "..",
            "/srv/template",
            "a:b/c",
            "C:/windows/template",
            "https://example.invalid/template",
            "ssh://example.invalid/template",
            "file:///srv/template",
            "user@host:some/path",
            # A repository Copier would clone, but one that lives on this machine and
            # must therefore still face every refusal a path faces.
            "../temp_project.git",
            "/srv/template.git",
            "file:///srv/template.git",
            "git+/srv/template",
        ):
            with self.subTest(recorded=recorded):
                self.assertFalse(self.helper.is_remote_source(recorded))


TEMPLATE_REMOTE = "git@github.com:rectaris/temp_project.git"
# A verification runs inside a fresh clone, so a gate driven by one of these launchers
# cannot run there and must never be recorded.
NEEDS_INSTALLED_DEPENDENCIES = frozenset({"npm", "npx", "pnpm", "yarn", "node", "vitest", "tsc"})
ENTRY = (
    "schema_version: 1\n"
    f"template_remote: {TEMPLATE_REMOTE}\n"
    "baselines:\n"
    "  - id: one\n"
    "    path: one\n"
    "    remote: git@github.com:owner/one.git\n"
    "    baseline_ref: dev\n"
    "    template_commit: v1.0.0\n"
    "    validation_commands:\n"
    '      - ["true"]\n'
)


class DownstreamBaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = load_module("verify_downstream_baselines", DOWNSTREAM)

    def load_record(self, text: str, root: Path | None = None):
        with tempfile.TemporaryDirectory() as raw:
            base = root or Path(raw)
            record = Path(raw) / "downstream-baselines.yaml"
            record.write_text(text, encoding="utf-8")
            return self.runner.load_baselines(record, base)[1]

    def make_checkout(
        self, root: Path, remote: str, commit: str, source: str = TEMPLATE_REMOTE
    ) -> Path:
        checkout = root / "one"
        checkout.mkdir(parents=True)
        run(["git", "init", "-q", "-b", "dev"], checkout)
        run(["git", "remote", "add", "origin", remote], checkout)
        (checkout / ".copier-answers.yml").write_text(
            f"_commit: {commit}\n_src_path: {source}\n", encoding="utf-8"
        )
        run(["git", "add", ".copier-answers.yml"], checkout)
        run(["git", "commit", "-qm", "baseline"], checkout)
        return checkout

    def check(self, baseline, template_remote: str = TEMPLATE_REMOTE):
        return self.runner.check_record(baseline, template_remote)[1]

    def test_the_committed_record_names_every_downstream_project(self) -> None:
        baselines = self.load_record(BASELINES.read_text(encoding="utf-8"))
        self.assertEqual(
            ["curiretas-gakumas-portal", "gakumasu-timeline", "supportcard-status"],
            sorted(baseline.identifier for baseline in baselines),
        )
        for baseline in baselines:
            with self.subTest(baseline=baseline.identifier):
                self.assertTrue(baseline.path.is_absolute())
                self.assertTrue(baseline.remote)
                self.assertTrue(baseline.baseline_ref)
                self.assertTrue(baseline.template_commit)
                for command in baseline.validation_commands:
                    self.assertTrue(all(command))
                    self.assertNotIn(command[0], NEEDS_INSTALLED_DEPENDENCIES)

    def test_a_project_without_a_runnable_gate_is_recorded_without_one(self) -> None:
        text = ENTRY.replace('    validation_commands:\n      - ["true"]\n', "")
        baselines = self.load_record(text)
        self.assertEqual((), baselines[0].validation_commands)

    def test_a_relative_path_resolves_against_the_given_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            baselines = self.load_record(ENTRY, root)
        self.assertEqual(root / "one", baselines[0].path)

    def test_the_same_repository_written_two_ways_compares_equal(self) -> None:
        for left, right in (
            ("git@github.com:owner/one.git", "https://github.com/owner/one"),
            ("https://github.com/owner/one/", "https://github.com/owner/one.git"),
            ("ssh://git@github.com/owner/one.git", "git@github.com:owner/one"),
            ("https://github.com:443/owner/one.git", "https://github.com/owner/one"),
        ):
            with self.subTest(left=left):
                self.assertEqual(
                    self.runner.canonical_remote(left), self.runner.canonical_remote(right)
                )
        for left, right in (
            ("git@github.com:owner/one.git", "git@github.com:owner/two.git"),
            # A path may distinguish two repositories by case, so case is preserved.
            ("git@github.com:owner/One.git", "git@github.com:owner/one.git"),
        ):
            with self.subTest(left=left, right=right):
                self.assertNotEqual(
                    self.runner.canonical_remote(left), self.runner.canonical_remote(right)
                )

    def test_an_unusable_record_is_refused(self) -> None:
        for text, message in (
            (ENTRY.replace("schema_version: 1", "schema_version: 2"), "schema_version"),
            (
                f"schema_version: 1\ntemplate_remote: {TEMPLATE_REMOTE}\nbaselines: []\n",
                "non-empty baselines",
            ),
            (ENTRY.replace(f"template_remote: {TEMPLATE_REMOTE}\n", ""), "non-empty template_remote"),
            (ENTRY.replace('      - ["true"]\n', "      - []\n"), "unusable validation command"),
            (
                ENTRY.replace('    validation_commands:\n      - ["true"]\n', "    validation_commands: true\n"),
                "validation commands as a list",
            ),
            (ENTRY + ENTRY.split("baselines:\n", 1)[1], "recorded more than once"),
            (ENTRY.replace("    path: one\n", '    path: ""\n'), "non-empty path"),
            (ENTRY.replace("    remote: git@github.com:owner/one.git\n", ""), "non-empty remote"),
            (ENTRY.replace("    baseline_ref: dev\n", ""), "non-empty baseline_ref"),
            (ENTRY.replace("    template_commit: v1.0.0\n", ""), "non-empty template_commit"),
            (ENTRY.replace("  - id: one\n", "  - id: ../escape\n"), "safe as a directory"),
            (ENTRY.replace("  - id: one\n", "  - id: /absolute\n"), "safe as a directory"),
        ):
            with self.subTest(message=message):
                with self.assertRaises(self.runner.BaselineError) as caught:
                    self.load_record(text)
                self.assertIn(message, str(caught.exception))

    def test_an_absent_checkout_is_reported_without_running_a_verification(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            baselines = self.load_record(ENTRY, Path(raw))
            report = self.check(baselines[0])
        self.assertEqual("blocked", report["result"])
        self.assertEqual("baseline_checkout_unavailable", report["reason_code"])
        self.assertEqual("environment", report["owner"])

    def test_a_checkout_of_another_repository_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.make_checkout(root, "git@github.com:owner/other.git", "v1.0.0")
            baselines = self.load_record(ENTRY, root)
            report = self.check(baselines[0])
        self.assertEqual("baseline_remote_mismatch", report["reason_code"])
        self.assertEqual("project", report["owner"])

    def test_a_checkout_that_left_the_recorded_template_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.make_checkout(root, "https://github.com/owner/one", "v9.9.9")
            baselines = self.load_record(ENTRY, root)
            report = self.check(baselines[0])
        self.assertEqual("baseline_template_commit_mismatch", report["reason_code"])
        self.assertIn("v9.9.9", report["next_action"])

    def test_an_absent_baseline_ref_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.make_checkout(root, "git@github.com:owner/one.git", "v1.0.0")
            baselines = self.load_record(ENTRY.replace("baseline_ref: dev", "baseline_ref: gone"), root)
            report = self.check(baselines[0])
        self.assertEqual("baseline_ref_unavailable", report["reason_code"])

    def test_a_project_generated_from_another_template_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.make_checkout(
                root,
                "git@github.com:owner/one.git",
                "v1.0.0",
                source="https://github.com/someone-else/temp_project.git",
            )
            baselines = self.load_record(ENTRY, root)
            report = self.check(baselines[0])
        self.assertEqual("baseline_template_source_mismatch", report["reason_code"])

    def test_a_recorded_version_with_a_comment_is_read_as_copier_reads_it(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            checkout = self.make_checkout(root, "git@github.com:owner/one.git", "v1.0.0")
            (checkout / ".copier-answers.yml").write_text(
                f"_commit: v1.0.0 # the current baseline\n_src_path: {TEMPLATE_REMOTE}\n",
                encoding="utf-8",
            )
            run(["git", "commit", "-qam", "comment"], checkout)
            baselines = self.load_record(ENTRY, root)
            self.assertIsNone(self.check(baselines[0]))

    def test_a_moving_ref_is_read_and_verified_at_one_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            checkout = self.make_checkout(root, "git@github.com:owner/one.git", "v1.0.0")
            baselines = self.load_record(ENTRY, root)
            commit, refused = self.runner.check_record(baselines[0], TEMPLATE_REMOTE)
            self.assertIsNone(refused)
            head = run(["git", "rev-parse", "HEAD"], checkout).stdout.strip()
        self.assertEqual(head, commit)

    def test_an_unrecorded_baseline_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            process = run(
                [
                    "python3",
                    str(DOWNSTREAM),
                    "--source-ref",
                    "HEAD",
                    "--output-dir",
                    str(Path(raw) / "out"),
                    "--only",
                    "no-such-project",
                ],
                ROOT,
                check=False,
            )
        self.assertEqual(2, process.returncode)
        self.assertIn("unrecorded baseline", process.stderr)

    def test_an_existing_output_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            process = run(
                ["python3", str(DOWNSTREAM), "--source-ref", "HEAD", "--output-dir", raw],
                ROOT,
                check=False,
            )
        self.assertEqual(2, process.returncode)
        self.assertIn("already exists", process.stderr)


if __name__ == "__main__":
    unittest.main()
