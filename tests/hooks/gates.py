"""Pre-tool and stop-gate behavior tests."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .support import (
    CODEX_HOOK_CONFIG,
    COPILOT_HOOK_CONFIG,
    LEGACY_STOP_BRIDGE,
    PRE_COMMIT,
    PRE_TOOL,
    ROOT,
    ROOT_PRE_TOOL,
    ROOT_STOP_REVIEW,
    STOP_REVIEW,
    TEMPLATE_COPILOT_HOOK_CONFIG,
    TEMPLATE_PRE_COMMIT,
    bind_direct_task_worktree,
    init_gate_repository,
    init_guarded_repository,
    run_hook,
)


class PreToolHardeningGateTest(unittest.TestCase):
    def test_root_gate_blocks_nested_tool_input(self) -> None:
        output = run_hook(
            ROOT_PRE_TOOL,
            {"tool_name": "exec_command", "tool_input": {"cmd": "git reset " + "--hard HEAD~1"}},
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("hard reset", output["reason"])

    def test_blocks_destructive_git_reset(self) -> None:
        output = run_hook(PRE_TOOL, {"cmd": "git reset " + "--hard HEAD~1"})
        self.assertEqual(output["decision"], "block")
        self.assertIn("hard reset", output["reason"])

    def test_blocks_nested_remote_script_pipe(self) -> None:
        output = run_hook(
            PRE_TOOL,
            {"arguments": {"shell_command": "curl https://example.invalid/install.sh " + "|" + " sh"}},
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("remote script", output["reason"])

    def test_blocks_actual_tool_input_payload(self) -> None:
        output = run_hook(
            PRE_TOOL,
            {
                "tool_name": "exec_command",
                "tool_input": {"cmd": "git reset " + "--hard HEAD~1"},
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("hard reset", output["reason"])

    def test_allows_routine_read_only_command(self) -> None:
        output = run_hook(PRE_TOOL, {"cmd": "git status --short"})
        self.assertEqual(output, {})


class TaskWorktreeGateTest(unittest.TestCase):
    """Every supported surface refuses a governed write outside its worktree."""

    def test_pre_tool_blocks_a_commit_outside_a_task_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            output = run_hook(ROOT_PRE_TOOL, {"cmd": "git commit -m x"}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertIn("pre-existing checkout", output["reason"])
        self.assertIn("prepare", output["reason"])

    def test_pre_tool_blocks_a_lifecycle_command_outside_a_task_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            output = run_hook(
                ROOT_PRE_TOOL,
                {"tool_input": {"cmd": "bash scripts/create-plan.sh add-a-thing"}},
                cwd=repo,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("task worktree", output["reason"])

    def test_pre_tool_allows_inspection_in_a_guarded_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            for command in ("git status", "git log --oneline", "git branch --list"):
                with self.subTest(command=command):
                    self.assertEqual(run_hook(ROOT_PRE_TOOL, {"cmd": command}, cwd=repo), {})

    def test_pre_tool_allows_a_repository_no_binding_can_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp), origin=None)
            output = run_hook(ROOT_PRE_TOOL, {"cmd": "git commit -m x"}, cwd=repo)
        self.assertEqual(output, {})

    def test_pre_commit_refuses_a_governed_commit_outside_a_task_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            (repo / "file.txt").write_text("change\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
            result = subprocess.run(
                ["sh", str(PRE_COMMIT)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("pre-existing checkout", result.stderr)
        self.assertIn("--no-verify", result.stderr)

    def test_pre_commit_leaves_an_unnameable_repository_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp), origin=None)
            (repo / "file.txt").write_text("change\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
            result = subprocess.run(
                ["sh", str(PRE_COMMIT)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_root_and_template_pre_commit_hooks_are_identical(self) -> None:
        self.assertEqual(PRE_COMMIT.read_bytes(), TEMPLATE_PRE_COMMIT.read_bytes())

    def test_stop_gate_withholds_success_while_a_task_worktree_remains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = init_guarded_repository(base / "repository")
            worktree, records = bind_direct_task_worktree(repo, base / "managed")
            try:
                output = run_hook(ROOT_STOP_REVIEW, {}, cwd=worktree)
            finally:
                for record in records:
                    record.unlink(missing_ok=True)
        self.assertEqual(output["decision"], "block")
        self.assertIn(str(worktree), output["reason"])
        self.assertIn("publish", output["reason"])

    def test_lifecycle_commands_refuse_a_governed_run_outside_a_task_worktree(self) -> None:
        commands = {
            "scripts/complete-plan.sh": "completing this plan",
            "scripts/finalize-active-plan.sh": "finalizing this plan",
            "scripts/shelve-plan.sh": "shelving this plan",
        }
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            plan = repo / "docs/plan/active/001-x.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("status: in_progress\n", encoding="utf-8")
            for relative, action in commands.items():
                shutil.copy2(ROOT / relative, repo / Path(relative).name)
                with self.subTest(command=relative):
                    result = subprocess.run(
                        ["sh", str(repo / Path(relative).name), "docs/plan/active/001-x.md"],
                        cwd=repo,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(action, result.stderr)
                    self.assertIn("pre-existing checkout", result.stderr)

    def test_stop_gate_blocks_from_the_pre_existing_checkout(self) -> None:
        """Retained state belongs to the repository, not to the current directory.

        A session usually ends in the pre-existing checkout. A completion check
        that asked only about that directory reported no binding and allowed a
        success response while the task worktree and its temporary branch were
        both still present.
        """

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = init_guarded_repository(base / "repository")
            worktree, records = bind_direct_task_worktree(repo, base / "managed")
            try:
                output = run_hook(ROOT_STOP_REVIEW, {}, cwd=repo)
            finally:
                for record in records:
                    record.unlink(missing_ok=True)
        self.assertEqual(output["decision"], "block")
        self.assertIn(str(worktree), output["reason"])
        self.assertIn("publish", output["reason"])

    def test_stop_gate_blocks_when_the_shipped_guard_cannot_answer(self) -> None:
        """An unknown answer is not evidence that the task was retired."""

        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            guard = repo / "scripts/project_workflow/worktree_guard.py"
            guard.write_text("raise SystemExit(3)\n", encoding="utf-8")
            output = run_hook(ROOT_STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertIn("retained state", output["reason"])

    def test_pre_tool_gate_blocks_when_a_shipped_guard_cannot_load(self) -> None:
        """A shipped guard that fails to import is a broken boundary, not an absent one."""

        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            guard = repo / "scripts/project_workflow/worktree_guard.py"
            guard.write_text("import nonexistent_module_for_gate_test\n", encoding="utf-8")
            output = run_hook(ROOT_PRE_TOOL, {"cmd": "git commit -m x"}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertIn("nonexistent_module_for_gate_test", output["reason"])

    def test_stop_gate_allows_a_repository_no_binding_can_name(self) -> None:
        """A repository outside enforcement owes no retirement and must not block.

        A binding names its repository by canonical origin, so a repository
        without one can never hold an ownership record. Reporting a failure
        there would block every turn with an instruction no command can satisfy,
        which is the opposite of leaving that repository ungoverned.
        """

        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp), origin=None)
            output = run_hook(ROOT_STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output, {})

    def test_stop_gate_names_retirement_for_a_worktree_already_gone(self) -> None:
        """A record whose directory is gone cannot be published, only retired."""

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = init_guarded_repository(base / "repository")
            worktree, records = bind_direct_task_worktree(repo, base / "managed")
            try:
                shutil.rmtree(worktree)
                output = run_hook(ROOT_STOP_REVIEW, {}, cwd=repo)
            finally:
                for record in records:
                    record.unlink(missing_ok=True)
        self.assertEqual(output["decision"], "block")
        self.assertIn("retire", output["reason"])
        self.assertNotIn("publish", output["reason"])

    def test_stop_gate_allows_success_once_no_task_worktree_is_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_guarded_repository(Path(tmp))
            output = run_hook(ROOT_STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output, {})



class StopReviewGateTest(unittest.TestCase):
    def test_legacy_stop_bridge_forwards_to_managed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo, "#!/bin/sh\necho 'active plan remains' >&2\nexit 1\n")
            output = run_hook(LEGACY_STOP_BRIDGE, {"last_assistant_message": "brief"}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertEqual(output["reason"], "active plan remains")

    def test_allows_when_message_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo)
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output, {})

    def test_allows_untracked_implementation_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo)
            (repo / "src").mkdir()
            (repo / "src/app.py").write_text("print('hello')\n", encoding="utf-8")
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output, {})

    def test_allows_substantive_user_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo)
            output = run_hook(
                STOP_REVIEW,
                {
                    "last_assistant_message": (
                        "設定ファイルがない場合にも起動できるように修正しました。"
                        "起動テストに合格し、既定値を使う動作を確認しました。"
                    )
                },
                cwd=repo,
            )
        self.assertEqual(output, {})

    def test_allows_brief_concrete_answer_without_review_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo)
            output = run_hook(
                STOP_REVIEW,
                {"last_assistant_message": "設定上の待機時間は 30 秒です。"},
                cwd=repo,
            )
        self.assertEqual(output, {})

    def test_allows_message_and_implementation_without_heuristic_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo)
            (repo / "src").mkdir()
            (repo / "src/app.py").write_text("print('hello')\n", encoding="utf-8")
            output = run_hook(
                STOP_REVIEW,
                {"last_assistant_message": "Implemented the requested startup fallback and validated it."},
                cwd=repo,
            )
        self.assertEqual(output, {})

    def test_blocks_failed_completion_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo, "#!/bin/sh\necho 'active plan remains' >&2\nexit 1\n")
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertEqual(output["reason"], "active plan remains")

    def test_allows_when_stop_hook_already_active(self) -> None:
        output = run_hook(
            STOP_REVIEW,
            {
                "stop_hook_active": True,
                "last_assistant_message": (
                    "設定ファイルがない場合にも起動できるように修正しました。"
                    "起動テストに合格し、既定値を使う動作を確認しました。"
                ),
            },
        )
        self.assertEqual(output, {})

    def test_blocks_when_no_completion_gate_is_shipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo, None)
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertIn("ships no plan completion gate", output["reason"])

    def test_blocks_with_a_useful_reason_when_the_gate_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo, "#!/bin/sh\nexit 1\n")
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output["decision"], "block")
        self.assertIn("--plans-only", output["reason"])
        self.assertNotEqual(output["reason"].strip(), "")

    def test_prefers_the_managed_gate_over_the_root_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo, "#!/bin/sh\necho 'root gate' >&2\nexit 1\n")
            managed = repo / ".project-agent-workflow/scripts"
            managed.mkdir(parents=True)
            (managed / "check-agent-completion.sh").write_text(
                "#!/bin/sh\necho 'managed gate' >&2\nexit 1\n", encoding="utf-8"
            )
            output = run_hook(STOP_REVIEW, {}, cwd=repo)
        self.assertEqual(output["reason"], "managed gate")

    def test_does_not_block_again_when_a_continuation_is_already_forced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_gate_repository(repo, "#!/bin/sh\necho 'active plan remains' >&2\nexit 1\n")
            output = run_hook(STOP_REVIEW, {"stop_hook_active": True}, cwd=repo)
        self.assertEqual(output, {})

    def test_root_and_generated_stop_adapters_are_identical(self) -> None:
        self.assertEqual(ROOT_STOP_REVIEW.read_bytes(), STOP_REVIEW.read_bytes())

    def test_copilot_configuration_reuses_the_shared_adapter(self) -> None:
        config = json.loads(COPILOT_HOOK_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["version"], 1)
        self.assertEqual(list(config["hooks"]), ["agentStop"])
        entries = config["hooks"]["agentStop"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["type"], "command")
        self.assertIn(".project-agent-workflow/hooks/stop_review_gate.py", entry["bash"])
        self.assertNotIn("exec", entry)
        self.assertNotIn("powershell", entry)

    def test_copilot_gate_is_not_attached_to_subagent_stop(self) -> None:
        self.assertNotIn("subagentStop", COPILOT_HOOK_CONFIG.read_text(encoding="utf-8"))

    def test_codex_and_copilot_surfaces_share_one_adapter(self) -> None:
        codex = CODEX_HOOK_CONFIG.read_text(encoding="utf-8")
        self.assertIn(".project-agent-workflow/hooks/stop_review_gate.py", codex)
        self.assertIn('"Stop"', codex)
        self.assertNotIn("SubagentStop", codex)

    def test_root_and_template_copilot_configurations_are_identical(self) -> None:
        self.assertEqual(
            COPILOT_HOOK_CONFIG.read_bytes(), TEMPLATE_COPILOT_HOOK_CONFIG.read_bytes()
        )


if __name__ == "__main__":
    unittest.main()
