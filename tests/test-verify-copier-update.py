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


def load_helper_module():
    spec = importlib.util.spec_from_file_location("verify_copier_update_helper", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load verification helper")
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


if __name__ == "__main__":
    unittest.main()
