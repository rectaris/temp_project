#!/usr/bin/env python3
"""Tests for the bounded Orca coordinator bridge."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts/orca-coordinator.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("orca_coordinator", BRIDGE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Orca coordinator bridge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIDGE_MODULE = load_bridge()


class FakeAdapter:
    class AdapterError(RuntimeError):
        pass

    def __init__(self, root: Path, *, admitted: bool = True) -> None:
        self.root = root
        self.admitted = admitted
        self.permit = {
            "group_id": "group-1",
            "group_description_digest": "sha256:" + "1" * 64,
            "plan_path": "docs/plan/active/001-member.md",
            "permit_id": "permit-1",
            "baseline_generation": 0,
            "base_commit": subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
            ).strip(),
        }

    def repository_root(self) -> Path:
        return self.root

    def verified_member(self, state, permit, plan, operation):
        del state, permit, operation
        if not self.admitted:
            raise self.AdapterError("plan is not an admitted group member")
        if plan != self.permit["plan_path"]:
            raise self.AdapterError("group member permit names a different plan")
        return {
            "root": self.root,
            "state": {"repository_identity": "sha256:" + "2" * 64},
            "member": {"logical_member_id": "001"},
            "permit": self.permit,
        }

    def require_clean_checkout(self, worktree: Path) -> None:
        if worktree != self.root:
            raise self.AdapterError("unexpected worktree")

    def require_member_worktree(self, worktree: Path, plan: str) -> None:
        if worktree != self.root or plan != self.permit["plan_path"]:
            raise self.AdapterError("worktree binding mismatch")


class OrcaCoordinatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.external = self.base / "external"
        self.repo.mkdir()
        self.external.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.repo,
            check=True,
        )
        (self.repo / "README").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        self.adapter = FakeAdapter(self.repo)
        self.head = self.adapter.permit["base_commit"]
        self.state = self.private_file("bridge.json")
        self.lock = self.private_file("bridge.lock")
        self.group_state = self.private_file("group.json", "{}\n")
        self.permit = self.private_file("permit.json", "{}\n")
        self.output = self.external / "readiness.json"
        self.manifest = self.external / "candidate.json"
        self.log = self.external / "orca-log.jsonl"
        self.orca = self.base / "fake-orca"
        self.orca.write_text(self.fake_orca_source(), encoding="utf-8")
        self.orca.chmod(0o755)
        self.environment = mock.patch.dict(
            os.environ,
            {
                "FAKE_ORCA_LOG": str(self.log),
                "FAKE_ORCA_WORKTREE": str(self.repo),
                "FAKE_ORCA_MODE": "ok",
            },
        )
        self.environment.start()
        self.adapter_patch = mock.patch.object(
            BRIDGE_MODULE, "_ADAPTER", self.adapter
        )
        self.adapter_patch.start()

    def tearDown(self) -> None:
        self.adapter_patch.stop()
        self.environment.stop()
        self.temporary.cleanup()

    def private_file(self, name: str, content: str = "") -> Path:
        path = self.external / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        return path

    def args(self, **overrides):
        values = {
            "state": str(self.state),
            "lock": str(self.lock),
            "group_state": str(self.group_state),
            "permit": str(self.permit),
            "plan": self.adapter.permit["plan_path"],
            "worktree": str(self.repo),
            "source_commit": self.head,
            "output": str(self.output),
            "candidate_manifest": str(self.manifest),
            "worker_bin": None,
            "worker_arg": ["--output-dir", str(self.external / "worker output")],
            "coordinator_terminal": "coord-terminal",
            "orca_bin": str(self.orca),
            "timeout_seconds": 1.0,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def fake_orca_source(self) -> str:
        return """#!/usr/bin/env python3
import json
import os
import shlex
import sys
import subprocess
import time
from pathlib import Path

args = sys.argv[1:]
mode = os.environ.get("FAKE_ORCA_MODE", "ok")
log = Path(os.environ["FAKE_ORCA_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")

if args == ["--version"]:
    print("1.4.196" if mode == "old-version" else "1.4.197")
    raise SystemExit(0)
if args == ["status", "--json"]:
    if mode == "malformed-status":
        print("not-json")
    else:
        print(json.dumps({
            "id": "status-1",
            "ok": True,
            "result": {
                "app": {"running": True},
                "runtime": {
                    "state": "ready",
                    "reachable": True,
                    "connectionState": "connected"
                }
            },
            "_meta": {"runtimeId": "runtime-1"}
        }))
    raise SystemExit(0)
if args[:2] == ["terminal", "show"]:
    terminal = args[args.index("--terminal") + 1]
    incarnation = "coord-incarnation" if terminal == "coord-terminal" else "worker-incarnation"
    print(json.dumps({
        "id": "show-1",
        "ok": True,
        "result": {"terminal": {
            "handle": terminal,
            "incarnationId": incarnation,
            "worktreePath": os.environ["FAKE_ORCA_WORKTREE"],
            "connected": mode != "disconnected"
        }},
        "_meta": {"runtimeId": "runtime-1"}
    }))
    raise SystemExit(0)
if args[:2] == ["terminal", "create"]:
    command = args[args.index("--command") + 1]
    entry = shlex.split(command)
    state_path = Path(entry[entry.index("--state") + 1])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["phase"] = "claimed"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    os.chmod(state_path, 0o600)
    monitor = (
        "import json,os,sys,time;"
        "p=sys.argv[1];"
        "deadline=time.monotonic()+2;"
        "\\nwhile time.monotonic()<deadline:\\n"
        " s=json.loads(open(p,encoding='utf-8').read());"
        "\\n if s['phase']=='bound':\\n"
        "  s['phase']='running';"
        "  open(p,'w',encoding='utf-8').write(json.dumps(s));"
        "  os.chmod(p,0o600);"
        "  break\\n"
        " if s['phase']=='uncertain': break\\n"
        " time.sleep(0.01)"
    )
    if mode != "dead-entry":
        subprocess.Popen(
            [sys.executable, "-c", monitor, str(state_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if mode == "create-fail":
        raise SystemExit(9)
    if mode == "malformed-create":
        print("not-json")
        raise SystemExit(0)
    if mode == "oversized-create":
        print("x" * 300000)
        raise SystemExit(0)
    if mode == "slow-create":
        time.sleep(0.15)
    print(json.dumps({
        "id": "create-1",
        "ok": True,
        "result": {"terminal": {
            "handle": "worker-terminal",
            "incarnationId": "worker-incarnation"
        }},
        "_meta": {"runtimeId": "runtime-1"}
    }))
    raise SystemExit(0)
raise SystemExit(2)
"""

    def state_document(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def orca_calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [
            json.loads(line)
            for line in self.log.read_text(encoding="utf-8").splitlines()
        ]

    def test_ensure_creates_and_binds_one_terminal(self) -> None:
        with mock.patch("builtins.print") as output:
            BRIDGE_MODULE.command_ensure(self.args())
        state = self.state_document()
        self.assertEqual(state["phase"], "running")
        self.assertEqual(state["terminal"]["handle"], "worker-terminal")
        self.assertEqual(
            state["binding"]["coordinator_terminal_incarnation"],
            "coord-incarnation",
        )
        create = [
            call for call in self.orca_calls() if call[:2] == ["terminal", "create"]
        ]
        self.assertEqual(len(create), 1)
        entry = shlex.split(create[0][create[0].index("--command") + 1])
        self.assertEqual(
            entry,
            [
                BRIDGE_MODULE.sys.executable,
                str(BRIDGE.resolve()),
                "worker-entry",
                "--state",
                str(self.state),
                "--start-token",
                state["start_token"],
            ],
        )
        self.assertIn('"outcome": "created"', output.call_args.args[0])
        self.assertIn('"phase": "running"', output.call_args.args[0])

    def test_live_matching_terminal_is_reused_without_create(self) -> None:
        BRIDGE_MODULE.command_ensure(self.args())
        before = len(
            [
                call
                for call in self.orca_calls()
                if call[:2] == ["terminal", "create"]
            ]
        )
        with mock.patch("builtins.print") as output:
            BRIDGE_MODULE.command_ensure(self.args())
        after = len(
            [
                call
                for call in self.orca_calls()
                if call[:2] == ["terminal", "create"]
            ]
        )
        self.assertEqual((before, after), (1, 1))
        self.assertIn('"outcome": "reused"', output.call_args.args[0])

    def test_bound_terminal_must_reach_running_before_reuse(self) -> None:
        BRIDGE_MODULE.command_ensure(self.args())
        state = self.state_document()
        state["phase"] = "bound"
        state["bind_deadline_monotonic_ns"] = time.monotonic_ns() + 50_000_000
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        with self.assertRaisesRegex(
            BRIDGE_MODULE.BridgeError,
            "transition timed out|binding deadline expired",
        ):
            BRIDGE_MODULE.command_ensure(self.args())
        self.assertEqual(self.state_document()["phase"], "uncertain")

    def test_reuse_rejects_runtime_change_and_implausible_deadline(self) -> None:
        BRIDGE_MODULE.command_ensure(self.args())
        state = self.state_document()
        state["runtime"]["runtime_id"] = "old-runtime"
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "runtime incarnation"):
            BRIDGE_MODULE.command_ensure(self.args())
        state["runtime"]["runtime_id"] = "runtime-1"
        state["phase"] = "bound"
        state["bind_deadline_monotonic_ns"] = (
            time.monotonic_ns()
            + int((BRIDGE_MODULE.MAX_TIMEOUT_SECONDS + 10) * 1_000_000_000)
        )
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "allowed horizon"):
            BRIDGE_MODULE.command_ensure(self.args())

    def test_concurrent_calls_create_at_most_one_terminal(self) -> None:
        os.environ["FAKE_ORCA_MODE"] = "slow-create"
        outcomes: list[str] = []

        def invoke() -> None:
            try:
                BRIDGE_MODULE.command_ensure(self.args())
                outcomes.append("ok")
            except BRIDGE_MODULE.BridgeError:
                outcomes.append("refused")

        first = threading.Thread(target=invoke)
        second = threading.Thread(target=invoke)
        first.start()
        time.sleep(0.03)
        second.start()
        first.join()
        second.join()
        creates = [
            call for call in self.orca_calls() if call[:2] == ["terminal", "create"]
        ]
        self.assertEqual(len(creates), 1)
        self.assertIn("ok", outcomes)

    def test_unavailable_incompatible_and_unadmitted_attempts_fail_before_create(
        self,
    ) -> None:
        os.environ["FAKE_ORCA_MODE"] = "old-version"
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "incompatible"):
            BRIDGE_MODULE.command_ensure(self.args())
        self.assertEqual(self.state.stat().st_size, 0)
        self.adapter.admitted = False
        os.environ["FAKE_ORCA_MODE"] = "ok"
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "not an admitted"):
            BRIDGE_MODULE.command_ensure(self.args())
        self.assertFalse(
            any(call[:2] == ["terminal", "create"] for call in self.orca_calls())
        )

    def test_mismatched_worktree_and_source_commit_are_refused(self) -> None:
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "source commit"):
            BRIDGE_MODULE.command_ensure(
                self.args(source_commit="0" * 40)
            )
        other = self.base / "other"
        other.mkdir()
        with self.assertRaises(BRIDGE_MODULE.BridgeError):
            BRIDGE_MODULE.command_ensure(self.args(worktree=str(other)))

    def test_symlink_hard_link_and_non_private_state_are_refused(self) -> None:
        real = self.private_file("real-state")
        symlink = self.external / "state-link"
        symlink.symlink_to(real)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "symlink"):
            BRIDGE_MODULE.command_ensure(self.args(state=str(symlink)))
        hardlink = self.external / "state-hardlink"
        os.link(real, hardlink)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "hard linked"):
            BRIDGE_MODULE.command_ensure(self.args(state=str(hardlink)))
        self.state.chmod(0o644)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "mode 0600"):
            BRIDGE_MODULE.command_ensure(self.args())

    def test_malformed_oversized_and_lost_create_replies_become_uncertain(
        self,
    ) -> None:
        for mode in ("malformed-create", "oversized-create", "create-fail"):
            with self.subTest(mode=mode):
                self.state.write_text("", encoding="utf-8")
                self.state.chmod(0o600)
                if self.log.exists():
                    self.log.unlink()
                os.environ["FAKE_ORCA_MODE"] = mode
                with self.assertRaises(BRIDGE_MODULE.BridgeError):
                    BRIDGE_MODULE.command_ensure(self.args())
                self.assertEqual(self.state_document()["phase"], "uncertain")
                os.environ["FAKE_ORCA_MODE"] = "ok"
                with self.assertRaisesRegex(
                    BRIDGE_MODULE.BridgeError, "uncertain"
                ):
                    BRIDGE_MODULE.command_ensure(self.args())
                creates = [
                    call
                    for call in self.orca_calls()
                    if call[:2] == ["terminal", "create"]
                ]
                self.assertEqual(len(creates), 1)

    def test_claimed_entry_that_never_runs_becomes_uncertain(self) -> None:
        os.environ["FAKE_ORCA_MODE"] = "dead-entry"
        with self.assertRaisesRegex(
            BRIDGE_MODULE.BridgeError,
            "transition timed out|binding deadline expired",
        ):
            BRIDGE_MODULE.command_ensure(self.args(timeout_seconds=0.5))
        self.assertEqual(self.state_document()["phase"], "uncertain")

    def test_mismatched_and_settled_records_are_refused(self) -> None:
        BRIDGE_MODULE.command_ensure(self.args())
        state = self.state_document()
        state["binding"]["permit_id"] = "different"
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "different attempt"):
            BRIDGE_MODULE.command_ensure(self.args())
        state["binding"]["permit_id"] = "permit-1"
        state["phase"] = "completed"
        state["worker_returncode"] = 0
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "already settled"):
            BRIDGE_MODULE.command_ensure(self.args())

    def test_shell_metacharacters_remain_single_worker_arguments(self) -> None:
        value = "literal $(touch should-not-exist); 'quoted value'"
        BRIDGE_MODULE.command_ensure(self.args(worker_arg=[value]))
        state = self.state_document()
        vector = BRIDGE_MODULE.dispatch_vector(state["binding"])
        self.assertEqual(vector[-2:], ["--worker-arg", value])
        create = next(
            call for call in self.orca_calls() if call[:2] == ["terminal", "create"]
        )
        entry = shlex.split(create[create.index("--command") + 1])
        self.assertEqual(entry[-4:-2], ["--state", str(self.state)])
        self.assertFalse((self.repo / "should-not-exist").exists())

    def test_worker_entry_claims_once_and_dispatches_without_shell(self) -> None:
        BRIDGE_MODULE.command_ensure(self.args())
        state = self.state_document()
        state["phase"] = "prepared"
        state["terminal"] = {"handle": "", "incarnation_id": ""}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        expected = BRIDGE_MODULE.dispatch_vector(state["binding"])
        calls: list[tuple[list[str], str]] = []

        def fake_dispatch(command, worktree):
            calls.append((command, worktree))
            return 0

        def bind_after_claim() -> None:
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                current = self.state_document()
                if current["phase"] == "claimed":
                    current["phase"] = "bound"
                    current["terminal"] = {
                        "handle": "worker-terminal",
                        "incarnation_id": "worker-incarnation",
                    }
                    self.state.write_text(json.dumps(current), encoding="utf-8")
                    self.state.chmod(0o600)
                    return
                time.sleep(0.01)
            raise AssertionError("entry never claimed the token")

        binder = threading.Thread(target=bind_after_claim)
        binder.start()
        entry_args = SimpleNamespace(
            state=str(self.state),
            start_token=state["start_token"],
            timeout_seconds=1.0,
        )
        with mock.patch.object(
            BRIDGE_MODULE.subprocess,
            "check_output",
            return_value=str(self.repo) + "\n",
        ), mock.patch.object(BRIDGE_MODULE, "run_dispatch", side_effect=fake_dispatch):
            with self.assertRaises(SystemExit) as exit_status:
                BRIDGE_MODULE.command_worker_entry(entry_args)
        binder.join()
        self.assertEqual(exit_status.exception.code, 0)
        self.assertEqual(calls, [(expected, str(self.repo))])
        self.assertEqual(self.state_document()["phase"], "completed")

    def test_wrong_or_replayed_entry_token_is_refused(self) -> None:
        BRIDGE_MODULE.command_ensure(self.args())
        state = self.state_document()
        state["phase"] = "prepared"
        state["terminal"] = {"handle": "", "incarnation_id": ""}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.state.chmod(0o600)
        with mock.patch.object(
            BRIDGE_MODULE.subprocess,
            "check_output",
            return_value=str(self.repo) + "\n",
        ):
            with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "mismatch"):
                BRIDGE_MODULE.command_worker_entry(
                    SimpleNamespace(
                        state=str(self.state),
                        start_token="f" * 64,
                        timeout_seconds=0.05,
                    )
                )
        self.assertEqual(self.state_document()["phase"], "prepared")

    def test_lock_path_replacement_is_detected_after_acquisition(self) -> None:
        original_flock = BRIDGE_MODULE.fcntl.flock

        def replace_then_lock(descriptor, operation):
            replacement = self.private_file("replacement.lock")
            os.replace(replacement, self.lock)
            original_flock(descriptor, operation)

        with mock.patch.object(
            BRIDGE_MODULE.fcntl, "flock", side_effect=replace_then_lock
        ):
            with self.assertRaisesRegex(BRIDGE_MODULE.BridgeError, "replaced"):
                with BRIDGE_MODULE.lock_file(self.lock, self.repo):
                    pass


if __name__ == "__main__":
    unittest.main()
