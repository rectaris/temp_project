"""Accepted-bundle identity, recovery and fixed-import regression tests."""

from __future__ import annotations

import os
import json
import stat
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from .support import ROOT, load_module


GROUP_DRIVER = r'''
import ctypes, importlib.util, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(36, 1, 0, 0, 0):
    raise OSError(ctypes.get_errno(), "isolated fixture subreaper setup")
spec = importlib.util.spec_from_file_location("owned_query_fixture", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
mode = sys.argv[2]
started = []
original = subprocess.Popen
def recording(*args, **kwargs):
    process = original(*args, **kwargs)
    started.append(process)
    return process
subprocess.Popen = recording
with tempfile.TemporaryDirectory() as name:
    trace = Path(name) / "descendant"
    program = """import subprocess,sys
from pathlib import Path
options = {'stdin': subprocess.DEVNULL}
if sys.argv[2] == 'closed':
    options.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
p = subprocess.Popen([sys.executable,'-I','-S','-B','-c','import time; time.sleep(30)'], **options)
Path(sys.argv[1]).write_text(str(p.pid))
print(p.pid, flush=True)
"""
    record = {"deadline_reached": False}
    descendant = None
    reaped = False
    try:
        try:
            result = module.capture(
                [sys.executable, '-I', '-S', '-B', '-c', program, str(trace), mode],
                cwd=name, env={'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C'}, timeout=2)
            record['leader_status'] = result.returncode
        except module.CommandError:
            record['deadline_reached'] = True
        record['leader_reaped_before_fixture_cleanup'] = bool(started) and all(
            process.returncode is not None for process in started)
        descendant = int(trace.read_text())
        deadline = time.monotonic() + 1
        while os.waitid(os.P_PID, descendant, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        state = os.waitid(os.P_PID, descendant, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        record['descendant_running_after_capture'] = state is None
        if state is None:
            os.kill(descendant, signal.SIGKILL)
        waited, status = os.waitpid(descendant, 0)
        reaped = waited == descendant
        record['fixture_reaped_descendant'] = reaped
        record['descendant_exit'] = os.waitstatus_to_exitcode(status)
    finally:
        subprocess.Popen = original
        for process in started:
            if process.returncode is None:
                os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
            for stream in (process.stdout, process.stderr):
                stream.close()
        if descendant is not None and not reaped:
            os.waitid(os.P_PID, descendant, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            os.kill(descendant, signal.SIGKILL)
            os.waitpid(descendant, 0)
    print(json.dumps(record))
'''


class SyntheticPhysicalView:
    """Model declared mount identities without borrowing the host mount layout.

    Host observations supply existence, types and inode equivalence only. Their
    device/inode pairs are interned within the independently declared fixture
    device, so separate host filesystems cannot create false inode aliases.
    """

    def __init__(self, real_class, rows, *, real=True, backing_device=None,
                 fold=False, missing=(), errors=(), equivalents=None):
        self.error_type = real_class.__init__.__globals__["AuthorityError"]
        self.rows, self.nodes, self.missing = rows, {}, set()
        self.real, self.fold = real, fold
        if real and backing_device is None:
            raise ValueError("host-backed fixtures require an independent device")
        self.backing_device = backing_device
        self.absent, self.errors = {Path(p) for p in missing}, {Path(p) for p in errors}
        self.equivalents = equivalents or {}
        self.opened, self.inodes = [], {}
        for name in ["chain", "identity", "row", "attachment", "coordinate", "projected"]:
            setattr(self, name, getattr(real_class, name).__get__(self, type(self)) if name != "identity" else real_class.identity)

    def canonical(self, path):
        parts = [self.equivalents.get(part, part.lower() if self.fold else part) for part in path.parts]
        return Path(*parts)

    def node(self, path):
        from types import SimpleNamespace
        if path in self.nodes:
            return self.nodes[path]
        if path in self.errors:
            raise PermissionError("synthetic inaccessible required suffix")
        if path in self.absent:
            raise FileNotFoundError("synthetic exact missing leaf")
        if path != Path("/"):
            parent = self.node(path.parent)
            if not stat.S_ISDIR(parent["info"].st_mode):
                raise self.error_type("synthetic nondirectory path parent")
        self.opened.append(path)
        canonical = self.canonical(path)
        candidates = [row for row in self.rows if canonical == self.canonical(row["point"])
                      or self.canonical(row["point"]) in canonical.parents]
        if not candidates:
            raise OSError("synthetic missing mount view")
        row = max(candidates, key=lambda r: (len(r["point"].parts), int(r["id"])))
        coordinate = self.canonical(row["root"] / canonical.relative_to(self.canonical(row["point"]))) if row["root"] is not None else Path("/opaque") / row["id"]
        device = os.makedev(*row["device"])
        kind = stat.S_IFDIR
        if row["filesystem"] == "nsfs" or path.name.endswith(".txt"):
            kind = stat.S_IFREG
        if self.real and row["root"] is not None:
            info = coordinate.stat(follow_symlinks=False)
            device = self.backing_device
            inode = self.inodes.setdefault(
                ("host", info.st_dev, info.st_ino), len(self.inodes) + 1)
            kind = stat.S_IFMT(info.st_mode)
            if kind == stat.S_IFLNK:
                raise self.error_type("synthetic symlink path")
        else:
            inode = self.inodes.setdefault((row["device"], str(coordinate)), len(self.inodes) + 1)
        node = {"fd": -1, "info": SimpleNamespace(st_dev=device, st_ino=inode, st_mode=kind | 0o700),
                "mount_id": row["id"], "path": path}
        self.nodes[path] = node
        return node

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # This model pins immutable fixture identities. Separate tests exercise
        # the real descriptor recheck and FD cleanup against changed metadata.
        return False


class ParentAuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module(ROOT / "scripts/project_workflow/parent_authority.py", "authority_test")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="parent-authority-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "dev")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", "https://example.invalid/project.git")
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/control.py").write_text("import helper\nprint(helper.MARKER)\n")
        (self.repo / "scripts/helper.py").write_text("MARKER = 'accepted'\n")
        (self.repo / "policy.txt").write_text("fixed policy\n")
        self.git("add", ".")
        self.git("commit", "-qm", "accepted")
        self.commit = self.git("rev-parse", "HEAD")
        self.bundle = self.base / "bundle"
        self.real_view = self.module.PhysicalView
        def view(rows):
            if any(row.get("source") == "fixture" for row in rows):
                result = SyntheticPhysicalView(
                    self.real_view, rows, backing_device=self.base.stat().st_dev)
                result.error_type = self.module.AuthorityError
                return result
            return self.real_view(rows)
        patcher = patch.object(self.module, "PhysicalView", side_effect=view)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL).decode().strip()

    def materialize(self, *, operation: str = "fixture-1", commit: str | None = None) -> dict:
        return self.module.materialize(self.repo, self.bundle, commit or self.commit, "refs/heads/dev", operation)

    def verify(self, result: dict, *, repo: Path | None = None) -> dict:
        return self.module.verify_bundle(repo or self.repo, self.bundle, self.commit, "refs/heads/dev", result["manifest_digest"])

    def test_exact_full_tree_and_idempotent_recovery(self) -> None:
        result = self.materialize()
        manifest = self.verify(result)
        self.assertEqual({entry["path"] for entry in manifest["inventory"]}, {"policy.txt", "scripts/control.py", "scripts/helper.py"})
        self.assertFalse(result["member_write_admitted"])
        self.assertEqual(self.materialize(), result)
        self.assertEqual((self.bundle / "tree/policy.txt").read_text(), "fixed policy\n")

    def test_immutable_inventory_ignores_replacements_and_unrelated_worktree_executors(self) -> None:
        original = self.git("rev-parse", f"{self.commit}:policy.txt")
        replacement = self.base / "replacement"
        replacement.write_text("not the accepted policy\n")
        replaced = self.git("hash-object", "-w", str(replacement))
        self.git("replace", original, replaced)
        marker = self.base / "worktree-executor-started"
        executor = self.base / "worktree-executor"
        executor.write_text(f"#!/bin/sh\nprintf started > '{marker}'\nexit 23\n")
        executor.chmod(0o700)
        for setting in ("core.fsmonitor", "filter.offline.clean", "filter.offline.process",
                        "diff.offline.textconv", "diff.external"):
            self.git("config", setting, str(executor))
        (self.repo / ".gitattributes").write_text("* filter=offline diff=offline\n")
        inventory = self.module.accepted_inventory(self.repo, self.commit, "refs/heads/dev")
        policy = next(entry for entry in inventory if entry["path"] == "policy.txt")
        self.assertEqual(policy["sha256"], self.module.digest(b"fixed policy\n"))
        self.assertFalse(marker.exists())
        with self.assertRaises(self.module.AuthorityError):
            self.module.git(self.repo, "cat-file", "blob", "0" * 40)

    def test_unaccepted_candidate_and_dirty_product_do_not_supply_authority(self) -> None:
        self.git("switch", "-qc", "candidate")
        (self.repo / "scripts/helper.py").write_text("MARKER = 'candidate'\n")
        self.git("commit", "-qam", "unaccepted")
        candidate = self.git("rev-parse", "HEAD")
        with self.assertRaises(self.module.AuthorityError):
            self.materialize(commit=candidate)
        self.assertFalse(self.bundle.exists())
        result = self.materialize()
        self.verify(result)
        self.assertIn("accepted", (self.bundle / "tree/scripts/helper.py").read_text())

    def test_wrong_repository_and_parent_manifest_pin_refuse(self) -> None:
        result = self.materialize()
        self.git("remote", "set-url", "origin", "https://example.invalid/foreign.git")
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)
        self.git("remote", "set-url", "origin", "https://example.invalid/project.git")
        with self.assertRaises(self.module.AuthorityError):
            self.verify({"manifest_digest": "sha256:" + "0" * 64})

    def test_foreign_destination_and_different_operation_remain_retained(self) -> None:
        self.bundle.mkdir()
        sentinel = self.bundle / "foreign"
        sentinel.write_bytes(b"retain me")
        with self.assertRaises(self.module.AuthorityError):
            self.materialize()
        self.assertEqual(sentinel.read_bytes(), b"retain me")
        sentinel.unlink()
        self.bundle.rmdir()
        result = self.materialize()
        before = (self.bundle / "manifest.json").read_bytes()
        with self.assertRaises(self.module.AuthorityError):
            self.materialize(operation="fixture-2")
        self.assertEqual((self.bundle / "manifest.json").read_bytes(), before)
        self.verify(result)

    def test_blob_mode_missing_and_extra_inventory_refuse(self) -> None:
        result = self.materialize()
        path = self.bundle / "tree/policy.txt"
        path.chmod(0o600)
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)
        path.write_text("changed\n")
        path.chmod(0o400)
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)
        path.chmod(0o600)
        path.write_text("fixed policy\n")
        path.unlink()
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)
        path.write_text("fixed policy\n")
        path.chmod(0o400)
        (self.bundle / "tree/unclassified").write_text("extra")
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)

    def test_symlink_hardlink_and_nonregular_manifest_refuse(self) -> None:
        result = self.materialize()
        manifest = self.bundle / "manifest.json"
        os.link(manifest, self.base / "alias")
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)
        (self.base / "alias").unlink()
        content = manifest.read_bytes()
        manifest.unlink()
        manifest.symlink_to(self.base / "saved")
        (self.base / "saved").write_bytes(content)
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)
        manifest.unlink()
        manifest.mkdir()
        with self.assertRaises(self.module.AuthorityError):
            self.verify(result)

    def test_tracked_symlink_and_gitlink_are_not_materialized(self) -> None:
        (self.repo / "scripts/link.py").symlink_to("helper.py")
        self.git("add", ".")
        self.git("commit", "-qm", "link")
        commit = self.git("rev-parse", "HEAD")
        with self.assertRaises(self.module.AuthorityError):
            self.materialize(commit=commit)
        self.assertFalse(self.bundle.exists())
        self.git("rm", "scripts/link.py")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.commit},submodule")
        self.git("commit", "-qm", "gitlink")
        with self.assertRaises(self.module.AuthorityError):
            self.materialize(commit=self.git("rev-parse", "HEAD"))

    def test_bundle_cannot_be_inside_worktree_or_symlink_parent(self) -> None:
        self.bundle = self.repo / "bundle"
        with self.assertRaises(self.module.AuthorityError):
            self.materialize()
        alias = self.base / "alias"
        alias.symlink_to(self.base, target_is_directory=True)
        self.bundle = alias / "bundle"
        with self.assertRaises(self.module.AuthorityError):
            self.materialize()

    def test_atomic_rename_interruption_recovers_same_operation_only(self) -> None:
        with patch.object(self.module.os, "rename", side_effect=OSError("fixture interruption")):
            with self.assertRaises(OSError):
                self.materialize()
        self.assertFalse(self.bundle.exists())
        result = self.materialize()
        self.verify(result)
        self.assertTrue((self.base / ".bundle.authority-intent.json").exists())

    def test_corrupted_staging_is_never_repaired_or_deleted(self) -> None:
        with patch.object(self.module.os, "rename", side_effect=OSError("fixture interruption")):
            with self.assertRaises(OSError):
                self.materialize()
        retained = self.base / ".bundle.authority-stage/tree/policy.txt"
        retained.chmod(0o600)
        retained.write_bytes(b"retain corrupt evidence")
        with self.assertRaises(self.module.AuthorityError):
            self.materialize()
        self.assertEqual(retained.read_bytes(), b"retain corrupt evidence")
        self.assertFalse(self.bundle.exists())

    def test_completed_stage_missing_inventory_is_retained_without_repair(self) -> None:
        for missing in ("blob", "tree"):
            with self.subTest(missing=missing):
                self.bundle = self.base / ("completed-" + missing)
                with patch.object(self.module.os, "rename", side_effect=OSError("fixture interruption")):
                    with self.assertRaises(OSError):
                        self.materialize()
                stage = self.base / ("." + self.bundle.name + ".authority-stage")
                manifest = stage / "manifest.json"
                original_manifest = manifest.read_bytes()
                original_identity = (stage.stat().st_dev, stage.stat().st_ino)
                absent = stage / "tree/policy.txt" if missing == "blob" else stage / "tree"
                if missing == "blob":
                    absent.unlink()
                else:
                    self.module.shutil.rmtree(absent)
                with self.assertRaises(self.module.AuthorityError):
                    self.materialize()
                self.assertFalse(absent.exists())
                self.assertFalse(self.bundle.exists())
                self.assertEqual(manifest.read_bytes(), original_manifest)
                self.assertEqual((stage.stat().st_dev, stage.stat().st_ino), original_identity)

    def test_fixed_import_contract_ignores_candidate_and_python_environment(self) -> None:
        result = self.materialize()
        contract = self.module.launch_contract(self.repo, self.bundle, self.commit, "refs/heads/dev", result["manifest_digest"], "scripts/control.py", [])
        candidate = self.base / "candidate"
        candidate.mkdir()
        (candidate / "helper.py").write_text("MARKER = 'poisoned'\n")
        env = {**contract["environment"], "PYTHONPATH": str(candidate), "PYTHONHOME": str(candidate)}
        process = subprocess.run(contract["argv"], cwd=candidate, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "accepted\n")
        self.verify(result)
        self.assertFalse(any(self.bundle.rglob("__pycache__")))
        self.assertEqual(contract["cwd"], str(self.bundle / "tree"))
        self.assertFalse(contract["execution_authorized"])
        self.assertFalse(contract["member_write_admitted"])
        self.assertIn("verified member-excluded native entrypoint", contract["blocking_requirements"])
        with self.assertRaises(self.module.AuthorityError):
            self.module.launch_contract(self.repo, self.bundle, self.commit, "refs/heads/dev", result["manifest_digest"], "../candidate/helper.py", [])

    def test_arguments_are_fixed_inventory_paths_and_cwd_is_bound(self) -> None:
        result = self.materialize()
        def contract(arguments):
            return self.module.launch_contract(self.repo, self.bundle, self.commit, "refs/heads/dev", result["manifest_digest"], "scripts/control.py", arguments)
        value = contract(["policy.txt"])
        self.assertEqual(value["argv"][-1], str(self.bundle / "tree/policy.txt"))
        self.assertEqual(value["cwd"], str(self.bundle / "tree"))
        for arguments in [[str(self.repo / "policy.txt")], ["../policy.txt"], ["--config", "policy.txt"], ["--config=policy.txt"], ["missing.json"], ["."]]:
            with self.subTest(arguments=arguments):
                with self.assertRaises(self.module.AuthorityError):
                    contract(arguments)

    def test_worktree_quoted_paths_are_not_external_destinations(self) -> None:
        for name in ["日本語", "quoted\"name", "line\nname"]:
            with self.subTest(name=name):
                worktree = self.base / name
                self.git("worktree", "add", "--detach", str(worktree), self.commit)
                with self.assertRaises(self.module.AuthorityError):
                    self.module.external_destination(self.repo, worktree / "bundle")
        self.assertEqual(self.module.external_destination(self.repo, self.base / "outside"), self.base / "outside")

    def test_manifest_is_parsed_from_the_exact_pinned_read(self) -> None:
        result = self.materialize()
        manifest = self.bundle / "manifest.json"
        original = self.module.read_owned
        reads = []
        def read(path, **kwargs):
            data = original(path, **kwargs)
            if path == manifest:
                reads.append(data)
                if len(reads) > 1:
                    return data.replace(b'"fixture-1"', b'"unverified-change"')
            return data
        with patch.object(self.module, "read_owned", side_effect=read):
            verified = self.verify(result)
        self.assertEqual(len(reads), 1)
        self.assertEqual(verified["operation_id"], "fixture-1")
        for raw in [b'{"a":1,"a":2}', b'[]', b'invalid']:
            with self.subTest(raw=raw):
                with self.assertRaises(self.module.AuthorityError):
                    self.module.parse_record(raw)

    def test_missing_host_capability_and_runtime_drift_refuse(self) -> None:
        result = self.materialize()
        with patch.object(self.module, "runtime_inventory", return_value={"changed": True}):
            with self.assertRaises(self.module.AuthorityError):
                self.verify(result)
        self.assertFalse(self.verify(result)["runtime"]["native_entrypoint_verified"])

    def test_serial_upgrade_preserves_old_bundle_and_run_identity(self) -> None:
        old = self.materialize()
        old_bytes = (self.bundle / "manifest.json").read_bytes()
        old_bundle = self.bundle
        (self.repo / "policy.txt").write_text("new accepted policy\n")
        self.git("commit", "-qam", "serial accepted update")
        self.bundle = self.base / "bundle-new"
        new = self.materialize(operation="upgrade-1", commit=self.git("rev-parse", "HEAD"))
        self.assertNotEqual(new["manifest_digest"], old["manifest_digest"])
        self.assertEqual((old_bundle / "manifest.json").read_bytes(), old_bytes)
        self.module.verify_bundle(self.repo, old_bundle, self.commit, "refs/heads/dev", old["manifest_digest"])

    def test_all_wrapper_entries_ignore_startup_path_and_sibling_poison(self) -> None:
        poison = self.base / "poison"
        poison.mkdir()
        sentinel = self.base / "poison-executed"
        payload = f"open({str(sentinel)!r}, 'w').write('poison')\nraise RuntimeError('poison')\n"
        (poison / "sitecustomize.py").write_text(payload)
        (poison / "usercustomize.py").write_text(payload)
        (poison / "python3").write_text("#!/bin/sh\necho poison > " + str(sentinel) + "\nexit 91\n")
        (poison / "python3").chmod(0o700)
        env = {**os.environ, "PATH": str(poison), "PYTHONPATH": str(poison), "PYTHONHOME": str(poison)}
        for relative in ["scripts/parent-authority.py", "template/.project-agent-workflow/scripts/parent-authority.py"]:
            with self.subTest(entry=relative):
                directory = self.base / ("root-entry" if relative.startswith("scripts/") else "generated-entry")
                directory.mkdir()
                wrapper = directory / "parent-authority.py"
                wrapper.write_bytes((ROOT / relative).read_bytes())
                wrapper.chmod(0o700)
                (directory / "parent_authority.py").write_text("def main():\n    import sys\n    print(sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode)\n    return 0\n")
                (directory / "pathlib.py").write_text(payload)
                (directory / "importlib.py").write_text(payload)
                for command in [[str(wrapper)], ["/bin/sh", str(wrapper)]]:
                    process = subprocess.run(command, cwd=poison, env=env, capture_output=True, text=True, timeout=10)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertEqual(process.stdout.strip(), "1 1 1")
                    self.assertFalse(sentinel.exists())
        for relative in ["scripts/parent-authority.py", "template/.project-agent-workflow/scripts/parent-authority.py"]:
            process = subprocess.run([str(ROOT / relative), "--help"], cwd=poison, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(sentinel.exists())

    def test_physical_worktree_aliases_refuse_every_bundle_entry(self) -> None:
        result = self.materialize()
        # Case-insensitive/bind-alias identity is emulated on this Linux fixture.
        # Path.samefile performs the production inode/device comparison.
        original = Path.samefile
        def samefile(path, other):
            if path == self.base and other == self.repo:
                return True
            return original(path, other)
        with patch.object(Path, "samefile", samefile):
            for operation in [
                lambda: self.module.materialize(self.repo, self.base / "alias-bundle", self.commit, "refs/heads/dev", "alias"),
                lambda: self.verify(result),
                lambda: self.module.launch_contract(self.repo, self.bundle, self.commit, "refs/heads/dev", result["manifest_digest"], "scripts/control.py", []),
            ]:
                with self.subTest(operation=operation):
                    with self.assertRaises(self.module.AuthorityError):
                        operation()
        self.verify(result)

    def test_nonregular_inputs_refuse_without_waiting_in_all_roles(self) -> None:
        # Each subprocess timeout detects the historical FIFO-open hang.
        result = self.materialize()
        paths = [self.bundle / "manifest.json", self.bundle / "tree/policy.txt",
                 self.base / ".bundle.authority-intent.json", self.base / ".bundle.authority-lock"]
        source = ROOT / "scripts/project_workflow/parent_authority.py"
        for path in paths:
            content, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            for kind in ["fifo", "directory", "symlink", "hardlink"]:
                with self.subTest(role=path.name, kind=kind):
                    path.unlink()
                    saved = self.base / "saved-input"
                    saved.write_bytes(content)
                    saved.chmod(mode)
                    if kind == "fifo":
                        os.mkfifo(path, mode)
                    elif kind == "directory":
                        path.mkdir()
                    elif kind == "symlink":
                        path.symlink_to(saved)
                    else:
                        os.link(saved, path)
                    command = [sys.executable, "-I", "-S", "-B", "-c",
                               "import importlib.util;from pathlib import Path;"
                               "s=importlib.util.spec_from_file_location('authority'," + repr(str(source)) + ");"
                               "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                               "m.materialize(Path(" + repr(str(self.repo)) + "),Path(" + repr(str(self.bundle))
                               + ")," + repr(self.commit) + ",'refs/heads/dev','fixture-1')"]
                    process = subprocess.run(command, capture_output=True, timeout=3)
                    self.assertNotEqual(process.returncode, 0)
                    self.assertTrue(path.is_symlink() or path.exists())
                    self.assertEqual(saved.read_bytes(), content)
                    if kind == "directory":
                        path.rmdir()
                    else:
                        path.unlink()
                    saved.unlink()
                    path.write_bytes(content)
                    path.chmod(mode)
        self.verify(result)

    def test_owned_reader_bounds_metadata_parent_walk_and_fd_release(self) -> None:
        path = self.base / "owned"
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        before = len(list(Path("/proc/self/fd").iterdir()))
        for _ in range(10):
            with self.assertRaises(self.module.AuthorityError):
                self.module.read_owned(path, limit=2)
        self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)
        path.chmod(0o622)
        with self.assertRaises(self.module.AuthorityError):
            self.module.read_owned(path)
        path.chmod(0o600)
        original_read = os.read
        def change(fd, size):
            data = original_read(fd, size)
            if data:
                path.write_bytes(b"changed")
            return data
        with patch.object(self.module.os, "read", side_effect=change):
            with self.assertRaises(self.module.AuthorityError):
                self.module.read_owned(path)
        directory = self.base / "parent"
        directory.mkdir()
        (directory / "leaf").write_bytes(b"original")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "leaf").write_bytes(b"foreign")
        original_open = os.open
        def switch(name, flags, *args, **kwargs):
            if name == "parent" and kwargs.get("dir_fd") is not None and directory.is_dir():
                directory.rename(self.base / "retained-parent")
                directory.symlink_to(outside, target_is_directory=True)
            return original_open(name, flags, *args, **kwargs)
        with patch.object(self.module.os, "open", side_effect=switch):
            with self.assertRaises(OSError):
                self.module.read_owned(directory / "leaf")
        self.assertEqual((outside / "leaf").read_bytes(), b"foreign")
        self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)

    def test_subdirectory_and_nested_bind_views_refuse_all_entries(self) -> None:
        result = self.materialize()
        device = f"{os.major(self.base.stat().st_dev)}:{os.minor(self.base.stat().st_dev)}"
        # Synthetic existing kernel mappings; no actual host mount is created.
        root = f"1 0 {device} / / rw - ext4 fixture rw\n"
        for target in [self.repo / "scripts", self.repo / "scripts/nested"]:
            raw = (root + f"2 1 {device} {target} {self.base} rw - ext4 fixture rw\n").encode()
            rows = self.module.parse_mount_view(raw)
            with patch.object(self.module, "mount_view", return_value=rows):
                for entry in [lambda: self.materialize(), lambda: self.verify(result),
                              lambda: self.module.launch_contract(self.repo, self.bundle, self.commit,
                              "refs/heads/dev", result["manifest_digest"], "scripts/control.py", [])]:
                    with self.subTest(target=target, entry=entry):
                        with self.assertRaises(self.module.AuthorityError):
                            entry()
        self.verify(result)

    def test_host_inode_collisions_preserve_synthetic_alias_decisions(self) -> None:
        from types import SimpleNamespace
        rows = self.module.parse_mount_view(b"1 0 0:42 / / rw - ext4 fixture rw\n")
        for alias in (False, True):
            observations = {
                Path("/"): SimpleNamespace(st_dev=1, st_ino=7, st_mode=stat.S_IFDIR),
                Path("/work"): SimpleNamespace(st_dev=2, st_ino=7, st_mode=stat.S_IFDIR),
                Path("/authority"): SimpleNamespace(
                    st_dev=2, st_ino=7 if alias else 8, st_mode=stat.S_IFDIR),
            }
            factory = lambda snapshot: SyntheticPhysicalView(
                self.real_view, snapshot, backing_device=os.makedev(0, 42))
            with self.subTest(alias=alias), \
                    patch.object(Path, "stat", lambda path, **kwargs: observations[path]), \
                    patch.object(self.module, "PhysicalView", side_effect=factory), \
                    patch.object(self.module, "mount_view", return_value=rows):
                if alias:
                    with self.assertRaises(self.module.AuthorityError):
                        self.module.reject_mount_alias(Path("/work"), Path("/authority"), rows)
                else:
                    self.module.reject_mount_alias(Path("/work"), Path("/authority"), rows)

    def test_mount_parser_and_physical_projection_fail_closed(self) -> None:
        device = f"{os.major(self.base.stat().st_dev)}:{os.minor(self.base.stat().st_dev)}"
        root = f"1 0 {device} / / rw - ext4 fixture rw\n"
        bad = [b"", b"malformed", (root + root).encode(),
               root.replace("ext4", "unknownfs").encode(),
               root.replace(device, "0:99999").encode(),
               (root + f"2 1 {device} / {self.base} rw - ext4 fixture rw\n"
                + f"3 1 {device} / {self.base} rw - ext4 fixture rw\n").encode(),
               (root + f"2 1 {device} /wrong {self.base} rw - ext4 fixture rw\n").encode(),
               root.replace(" / / ", " / /bad\\999 ").encode()]
        for raw in bad:
            with self.subTest(raw=raw):
                with self.assertRaises((self.module.AuthorityError, OSError)):
                    rows = self.module.parse_mount_view(raw)
                    with patch.object(self.module, "mount_view", return_value=rows):
                        self.module.external_destination(self.repo, self.bundle)
        rows = self.module.parse_mount_view(root.encode())
        with patch.object(self.module, "mount_view", return_value=rows):
            self.assertEqual(self.module.external_destination(self.repo, self.bundle), self.bundle)
        escaped = self.module.parse_mount_view(
            (root + f"2 1 {device} /root\\040name /point\\134name rw - ext4 fixture rw\n").encode())
        self.assertEqual(str(escaped[1]["root"]), "/root name")
        self.assertEqual(str(escaped[1]["point"]), "/point\\name")
        with patch.object(self.module.sys, "platform", "unsupported"):
            with self.assertRaises(self.module.AuthorityError):
                self.module.mount_view()

    def test_unrelated_nsfs_namespace_root_is_retained_without_projection(self) -> None:
        device = f"{os.major(self.base.stat().st_dev)}:{os.minor(self.base.stat().st_dev)}"
        # N01-N10: real classes, child selectors and a future opaque class.
        names = ["mnt", "cgroup", "ipc", "net", "pid", "time", "user", "uts",
                 "pid_for_children", "time_for_children", "future_ns"]
        result = self.materialize()
        for name in names:
            raw = (f"1 0 {device} / / rw - ext4 fixture rw\n"
                   f"2 1 0:5 {name}:[4026532921] /namespace-fixture rw - nsfs nsfs rw\n")
            rows = self.module.parse_mount_view(raw.encode())
            with self.subTest(namespace=name):
                self.assertEqual(len(rows), 2)
                self.assertIsNone(rows[1]["root"])
                self.assertEqual(rows[1]["point"], Path("/namespace-fixture"))
                self.assertEqual(rows[1]["device"], (0, 5))
                with patch.object(self.module, "mount_view", return_value=rows):
                    self.assertEqual(self.materialize(), result)
                    self.verify(result)
                    self.module.launch_contract(self.repo, self.bundle, self.commit,
                                                "refs/heads/dev", result["manifest_digest"],
                                                "scripts/control.py", [])

    def test_nsfs_namespace_roots_relevant_to_placement_or_alias_refuse(self) -> None:
        device = f"{os.major(self.base.stat().st_dev)}:{os.minor(self.base.stat().st_dev)}"
        root = f"1 0 {device} / / rw - ext4 fixture rw\n"
        cases = [("0:5", self.base), ("0:5", self.repo),
                 ("0:5", self.repo / "subtree"), ("0:5", self.bundle / "tree"),
                 (device, self.repo / "subtree"), (device, Path("/namespace-fixture"))]
        for name in ["mnt", "cgroup", "ipc", "net", "pid", "time", "user", "uts",
                     "pid_for_children", "time_for_children", "future_ns"]:
            for mount_device, point in cases:
                rows = self.module.parse_mount_view(
                    (root + f"2 1 {mount_device} {name}:[4026532921] {point} rw - nsfs nsfs rw\n").encode())
                with self.subTest(namespace=name, device=mount_device, point=point):
                    with patch.object(self.module, "mount_view", return_value=rows):
                        with self.assertRaises(self.module.AuthorityError):
                            self.module.external_destination(self.repo, self.bundle)

    def test_nsfs_exception_does_not_relax_mount_path_validation(self) -> None:
        prefix = "1 0 0:5 "
        bad = ["mnt:[0]", "net:[abc]", "mnt:[x]", "mnt:[18446744073709551616]",
               "net:[2]suffix", "net:[2]\\040", "Upper:[2]", ": [2]",
               "a" * 65 + ":[2]",
               "mnt:[4026532921]/..", "mnt:[4026532921]\\040", "relative", "/../root"]
        for value in bad:
            with self.subTest(root=value):
                with self.assertRaises(self.module.AuthorityError):
                    self.module.parse_mount_view(
                        (prefix + value + " /namespace-fixture rw - nsfs nsfs rw\n").encode())
        for filesystem, point in [("ext4", "/namespace-fixture"),
                                  ("unknownfs", "/namespace-fixture"),
                                  ("nsfs", "relative"), ("nsfs", "/../bad"),
                                  ("nsfs", "/bad\\999")]:
            with self.subTest(filesystem=filesystem, point=point):
                with self.assertRaises(self.module.AuthorityError):
                    self.module.parse_mount_view(
                        (prefix + f"mnt:[4026532921] {point} rw - {filesystem} fixture rw\n").encode())
        row = prefix + "mnt:[4026532921] /namespace-fixture rw - nsfs nsfs rw\n"
        with self.assertRaises(self.module.AuthorityError):
            self.module.parse_mount_view((row + row).encode())

    def test_independent_alias_counterexample_matrix(self) -> None:
        from types import SimpleNamespace
        # A01-A24 use synthetic kernel rows and physical inode identities.
        # No host mount is made; case folding is a synthetic identity model.
        root = "1 0 0:42 / / rw - ext4 fixture rw\n"
        cases = [
            ("A01", "/repo", "/parent/bundle", "", False),
            ("A02", "/repo", "/repo/bundle", "", True),
            ("A03", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree /repo rw - ext4 fixture rw\n", True),
            ("A04", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle /repo/control rw - ext4 fixture rw\n", True),
            ("A05", "/repo", "/parent/bundle", "2 1 0:42 /parent /repo/control rw - ext4 fixture rw\n", True),
            ("A06", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree/deep /repo/control rw - ext4 fixture rw\n", True),
            ("A07", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree /repo rw - ext4 fixture rw\n", True),
            ("A08", "/visible/tree", "/parent/bundle", "2 1 0:42 /parent/bundle /visible rw - ext4 fixture rw\n", True),
            ("A09", "/repo", "/parent/bundle", "2 1 0:42 / /repo/control rw - ext4 fixture rw\n", True),
            ("A10", "/repo", "/parent/bundle", "2 1 0:42 /repo/child /parent/bundle rw - ext4 fixture rw\n", True),
            ("A11", "/repo", "/parent/bundle", "2 1 0:42 /unrelated /repo/control rw - ext4 fixture rw\n", False),
            ("A12", "/repo", "/parent/bundle", "2 1 0:43 / /repo rw - tmpfs fixture rw\n3 2 0:42 /parent /repo/control rw - ext4 fixture rw\n", True),
            ("A13", "/repo", "/parent/bundle", "2 1 0:43 / /repo rw - tmpfs fixture rw\n3 2 0:42 /parent/bundle/tree /repo/control rw - ext4 fixture rw\n", True),
            ("A14", "/repo", "/parent/bundle", "2 1 0:43 /source /parent/bundle/tree rw - tmpfs fixture rw\n3 1 0:43 /source /repo/control rw - tmpfs fixture rw\n", True),
            ("A15", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree/policy.txt /repo/control/file rw - ext4 fixture rw\n", True),
            ("A16", "/repo", "/parent/bundle", "2 1 0:42 / /repo/control rw - ext4 fixture rw\n3 1 0:42 / /repo/control rw - ext4 fixture rw\n", True),
            ("A17", "/repo", "/parent/bundle", "2 1 0:42 /unrelated /repo/control rw - ext4 fixture rw\n3 2 0:42 /hidden /repo/control/nested rw - ext4 fixture rw\n4 1 0:43 / /unrelated rw - tmpfs fixture rw\n", True),
            ("A18", "/repo", "/parent/bundle", "2 1 0:42 / /parent rw - overlay fixture rw\n", True),
            ("A19", "/repo", "/parent/bundle", "2 1 0:5 net:[42] /namespace rw - nsfs nsfs rw\n", False),
            ("A20", "/repo", "/parent/bundle", "2 1 0:5 net:[42] /parent/bundle/tree rw - nsfs nsfs rw\n", True),
            ("A21", "/repo", "/parent/bundle", "1 0 0:42 / / rw - ext4 fixture rw\n", True),
            ("A22", "/repo", "/parent/BUNDLE", "2 1 0:42 /parent/bundle/tree /repo/control rw - ext4 fixture rw\n", True),
            ("A23", "/parent/repo", "/parent/bundle", "", False),
            ("A24", "/repo", "/parent/bundle", "2 1 0:42 /repo/stage /parent/bundle rw - ext4 fixture rw\n", True),
        ]
        for case_id, worktree, authority, extra, refuse in cases:
            with self.subTest(case=case_id):
                if case_id == "A21":
                    with self.assertRaises(self.module.AuthorityError):
                        self.module.parse_mount_view((root + extra).encode())
                    continue
                rows = self.module.parse_mount_view((root + extra).encode())
                factory = lambda rows: SyntheticPhysicalView(self.real_view, rows, real=False,
                                                            fold=case_id == "A22",
                                                            missing=[authority] if case_id == "A23" else [])
                with patch.object(self.module, "PhysicalView", side_effect=factory), patch.object(self.module, "mount_view", return_value=rows):
                    if refuse:
                        with self.assertRaises(self.module.AuthorityError):
                            self.module.reject_mount_alias(Path(worktree), Path(authority), rows)
                    else:
                        self.module.reject_mount_alias(Path(worktree), Path(authority), rows)

    def test_operation_records_are_excluded_before_first_write(self) -> None:
        # A24: all exact operation records are excluded before the first write.
        device = f"{os.major(self.base.stat().st_dev)}:{os.minor(self.base.stat().st_dev)}"
        prefix = ".bundle.authority"
        for suffix in ["-stage", "-intent.json", "-intent.json.next", "-lock"]:
            protected = self.base / (prefix + suffix)
            rows = self.module.parse_mount_view((f"1 0 {device} / / rw - ext4 fixture rw\n"
                    f"2 1 {device} {self.repo} {protected} rw - ext4 fixture rw\n").encode())
            factory = lambda rows: SyntheticPhysicalView(self.real_view, rows, real=False, missing=[self.bundle])
            with self.subTest(record=suffix), patch.object(self.module, "mount_view", return_value=rows), patch.object(self.module, "PhysicalView", side_effect=factory):
                with self.assertRaises(self.module.AuthorityError):
                    self.materialize()
                self.assertFalse(self.bundle.exists())
                self.assertFalse(any(p.name.startswith(prefix) for p in self.base.iterdir()))

    def test_worktree_growth_does_not_enable_native_member_admission(self) -> None:
        # A26: registration changes do not grant the unproven native capability.
        result = self.materialize()
        extra = self.base / "another-member"
        self.git("worktree", "add", "--detach", str(extra), self.commit)
        contract = self.module.launch_contract(self.repo, self.bundle, self.commit,
                                              "refs/heads/dev", result["manifest_digest"],
                                              "scripts/control.py", [])
        self.assertFalse(contract["member_write_admitted"])
        self.assertFalse(contract["execution_authorized"])

    def test_fd_physical_row_counterexample_matrix(self) -> None:
        root = "1 999 0:42 / / rw - ext4 fixture rw\n"
        # Each fixture describes kernel-resolved FD/mount identities. Name
        # equivalences are only the declared fake kernel behavior, never a
        # userspace normalization algorithm in production.
        cases = [
            ("B01", "/repo", "/parent/BUNDLE", "2 1 0:43 /repo/control /parent/bundle/tree rw - tmpfs fixture rw\n", True, True, (), ()),
            ("B02", "/Repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree /repo/control rw - ext4 fixture rw\n", True, True, (), ()),
            ("B03", "/Repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree /repo rw - ext4 fixture rw\n", True, True, (), ()),
            ("B04", "/repo", "/parent/BUNDLE", "2 1 0:42 /parent/bundle/tree /repo/control rw - ext4 fixture rw\n", True, True, (), ()),
            ("B05", "/repo", "/parent/É", "2 1 0:42 /repo/control /parent/e\u0301/tree rw - ext4 fixture rw\n", True, False, (), ()),
            ("B07", "/repo", "/parent/bundle", "2 1 0:43 /source /unrelated/blocked rw - tmpfs fixture rw\n", False, False, (), ("/unrelated/blocked",)),
            ("B08", "/repo", "/parent/bundle", "2 1 0:43 /source /parent/bundle/blocked rw - tmpfs fixture rw\n", True, False, (), ("/parent/bundle/blocked",)),
            ("B09", "/repo", "/parent/bundle", "2 1 0:5 net:[42] /unrelated/ns rw - nsfs nsfs rw\n", False, False, (), ("/unrelated/ns",)),
            ("B10", "/repo", "/parent/BUNDLE", "2 1 0:5 net:[42] /parent/bundle/tree rw - nsfs nsfs rw\n", True, True, (), ()),
            ("B11", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree/policy.txt /repo/control/file.txt rw - ext4 fixture rw\n", True, False, (), ()),
            ("B12", "/repo", "/parent/bundle", "2 1 0:42 /source/policy.txt /parent/bundle/policy.txt ro - ext4 fixture ro\n", True, False, (), ()),
            ("B13", "/repo", "/parent/bundle", "2 1 0:42 /parent/bundle/tree /repo rw - ext4 fixture rw\n", True, False, (), ()),
            ("B14", "/repo", "/parent/bundle", "2 1 0:43 /source /repo/control rw - tmpfs fixture rw\n3 1 0:43 /source /repo/control rw - tmpfs fixture rw\n", True, False, (), ()),
            ("B16", "/repo", "/parent/bundle", "2 1 0:43 /source /parent/bundle/deleted rw - tmpfs fixture rw\n", True, False, (), ("/parent/bundle/deleted",)),
            ("B17", "/parent/repo", "/parent/bundle", "", False, False, ("/parent/bundle",), ()),
            ("B18", "/repo", "/parent/bundle", "", False, False, (), ()),
            ("B19", "/repo", "/parent/bundle", "2 1 0:44 / /unrelated/autofs/blocked rw - autofs fixture rw\n", False, False, (), ("/unrelated/autofs",)),
            ("B20", "/repo", "/parent/bundle", "", False, False, (), ()),
            ("B22", "/repo", "/parent/bundle", "2 1 0:42 / /unrelated/blocked rw - ext4 fixture rw\n", True, False, (), ("/unrelated/blocked",)),
        ]
        for case_id, worktree, authority, extra, refuse, fold, missing, errors in cases:
            rows = self.module.parse_mount_view((root + extra).encode())
            models = []
            def factory(rows):
                model = SyntheticPhysicalView(self.real_view, rows, real=False, fold=fold,
                                              missing=missing, errors=errors,
                                              equivalents={"É": "e\u0301"} if case_id == "B05" else None)
                models.append(model)
                return model
            with self.subTest(case=case_id), patch.object(self.module, "PhysicalView", side_effect=factory), patch.object(self.module, "mount_view", return_value=rows):
                if refuse:
                    with self.assertRaises(self.module.AuthorityError):
                        self.module.reject_mount_alias(Path(worktree), Path(authority), rows)
                else:
                    self.module.reject_mount_alias(Path(worktree), Path(authority), rows)
                if case_id in {"B07", "B09", "B19"}:
                    self.assertTrue(all(Path(error) not in model.opened for error in errors for model in models))
        # B18: an external namespace-root parent is legal, a missing required
        # full-filesystem projection is not. No global parent-ID closure rule.
        rows = self.module.parse_mount_view(root.replace(" / / ", " /hidden / ").encode())
        factory = lambda rows: SyntheticPhysicalView(self.real_view, rows, real=False)
        with patch.object(self.module, "PhysicalView", side_effect=factory), patch.object(self.module, "mount_view", return_value=rows):
            with self.assertRaises(self.module.AuthorityError):
                self.module.reject_mount_alias(Path("/repo"), Path("/parent/bundle"), rows)
        for filesystem in ["ext4", "xfs", "tmpfs"]:
            rows = self.module.parse_mount_view(root.replace("ext4", filesystem).encode())
            with patch.object(self.module, "PhysicalView", side_effect=factory), patch.object(self.module, "mount_view", return_value=rows):
                self.module.reject_mount_alias(Path("/repo"), Path("/parent/bundle"), rows)

    def test_fd_capability_and_recheck_fail_closed(self) -> None:
        # B15/B16/B21: real metadata descriptors, injected identity drift or
        # unavailable proc metadata; no mount or global security setting changes.
        rows = self.module.mount_view()
        before = len(list(Path("/proc/self/fd").iterdir()))
        with self.assertRaises(self.module.AuthorityError):
            with self.real_view(rows) as view:
                chain = view.chain(self.repo)
                chain[-1]["mount_id"] += "0"
        self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)
        with patch("builtins.open", side_effect=PermissionError("synthetic fdinfo denial")):
            with self.assertRaises(self.module.AuthorityError):
                with self.real_view(rows) as view:
                    view.chain(self.repo)
        self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)
        # Exact future absence is separately rechecked without creating a file.
        future = self.base / "fd-future"
        with self.real_view(rows) as view:
            view.chain(future, missing=True)
            view.missing.add(self.repo)  # Inject contradiction to absence claim.
            with self.assertRaises(self.module.AuthorityError):
                view.recheck()
            view.missing.remove(self.repo)
        self.assertFalse(future.exists())

    def test_fd_preserves_byte_names_and_actual_mount_ids(self) -> None:
        # B03/B06: permitted ordinary read observation on private fixture data.
        raw = self.base / os.fsdecode(b"byte-\xff")
        raw.mkdir()
        rows = self.module.mount_view()
        with self.real_view(rows) as view:
            chain = view.chain(raw)
            self.assertEqual(os.fsencode(chain[-1]["path"].name), b"byte-\xff")
            row = view.row(chain[-1])
            self.assertEqual(row["id"], chain[-1]["mount_id"])
            self.assertEqual(row["device"], (os.major(raw.stat().st_dev), os.minor(raw.stat().st_dev)))
            self.assertEqual(view.identity(chain[-1], namespace=False)[:2], (raw.stat().st_dev, raw.stat().st_ino))

    def test_cli_rejects_operation_specific_extras_before_effects(self) -> None:
        common = ["--repository", str(self.repo), "--bundle", str(self.bundle),
                  "--accepted-commit", self.commit, "--accepted-ref", "refs/heads/dev"]
        matrices = {
            "materialize": (["--operation-id", "fixture"], [["--manifest-digest", ""], ["--entrypoint", ""], ["ignored"]]),
            "verify": (["--manifest-digest", "sha256:" + "0" * 64], [["--operation-id", ""], ["--entrypoint", ""], ["ignored"]]),
            "launch-contract": (["--manifest-digest", "sha256:" + "0" * 64, "--entrypoint", "scripts/control.py"], [["--operation-id", ""]]),
        }
        for operation, (required, extras) in matrices.items():
            for extra in extras:
                with self.subTest(operation=operation, extra=extra):
                    with patch.object(self.module, "materialize") as materialize, patch.object(self.module, "verify_bundle") as verify, patch.object(self.module, "launch_contract") as launch:
                        self.assertEqual(self.module.main([operation, *common, *required, *extra]), 1)
                        materialize.assert_not_called()
                        verify.assert_not_called()
                        launch.assert_not_called()
        self.assertFalse(self.bundle.exists())

    def test_persistence_dependency_order_and_recovered_bytes_resync(self) -> None:
        events = []
        original_sync, original_rename, original_fsync = self.module.sync_directory, os.rename, os.fsync
        def sync(path):
            events.append(("directory", str(path)))
            return original_sync(path)
        def fsync(fd):
            events.append(("file" if stat.S_ISREG(os.fstat(fd).st_mode) else "directory-fd",
                           os.readlink(f"/proc/self/fd/{fd}")))
            return original_fsync(fd)
        def rename(source, destination):
            events.append(("rename", str(source)))
            return original_rename(source, destination)
        with patch.object(self.module, "sync_directory", side_effect=sync), patch.object(self.module.os, "rename", side_effect=rename), patch.object(self.module.os, "fsync", side_effect=fsync):
            self.materialize()
        stage = self.base / ".bundle.authority-stage"
        rename_index = events.index(("rename", str(stage)))
        def last_before(kind, path):
            return max(i for i, event in enumerate(events[:rename_index]) if event == (kind, str(path)))
        self.assertLess(last_before("file", stage / "manifest.json"), last_before("directory", stage))
        self.assertLess(last_before("directory", stage / "tree/scripts"), last_before("directory", stage / "tree"))
        self.assertLess(last_before("directory", stage / "tree"), last_before("directory", stage))
        self.assertLess(last_before("directory", stage), last_before("directory", self.base))
        self.assertIn(("directory", str(self.base)), events[rename_index + 1:])
        events.clear()
        with patch.object(self.module.os, "fsync", side_effect=fsync):
            self.materialize()
        for path in [self.bundle / "manifest.json", self.bundle / "tree/policy.txt"]:
            self.assertIn(("file", str(path)), events)

    def test_each_durability_barrier_refuses_and_recognized_stage_resumes(self) -> None:
        original_sync = self.module.sync_directory
        for phase in ["nested", "tree", "stage", "pre-rename-parent", "post-rename-parent"]:
            with self.subTest(phase=phase):
                directory = self.base / phase
                directory.mkdir(mode=0o700)
                self.bundle = directory / "bundle"
                stage = directory / ".bundle.authority-stage"
                failed = False
                def sync(path):
                    nonlocal failed
                    trigger = ((phase == "nested" and path == stage / "tree/scripts")
                               or (phase == "tree" and path == stage / "tree")
                               or (phase == "stage" and path == stage)
                               or (phase == "pre-rename-parent" and path == directory and (stage / "manifest.json").exists())
                               or (phase == "post-rename-parent" and path == directory and self.bundle.exists()))
                    if trigger and not failed:
                        failed = True
                        raise OSError("injected durability barrier")
                    return original_sync(path)
                with patch.object(self.module, "sync_directory", side_effect=sync):
                    with self.assertRaises(OSError):
                        self.materialize()
                self.assertTrue(failed)
                self.assertEqual(self.bundle.exists(), phase == "post-rename-parent")
                if phase != "post-rename-parent":
                    self.assertTrue(stage.exists())
                result = self.materialize()
                self.verify(result)

    def test_file_fsync_and_intent_replace_failures_retain_unknown_bytes(self) -> None:
        original = os.fsync
        def fsync(fd):
            path = os.readlink(f"/proc/self/fd/{fd}")
            if path.endswith("/tree/policy.txt"):
                raise OSError("injected file sync")
            return original(fd)
        with patch.object(self.module.os, "fsync", side_effect=fsync):
            with self.assertRaises(OSError):
                self.materialize()
        self.assertFalse(self.bundle.exists())
        result = self.materialize()
        self.verify(result)
        original_replace = os.replace
        def replace(source, destination):
            if str(source).endswith("-intent.json.next"):
                raise OSError("injected intent replace")
            return original_replace(source, destination)
        with patch.object(self.module.os, "replace", side_effect=replace):
            with self.assertRaises(OSError):
                self.materialize()
        retained = self.base / ".bundle.authority-intent.json.next"
        before = retained.read_bytes()
        with self.assertRaises(OSError):
            self.materialize()
        self.assertEqual(retained.read_bytes(), before)
        self.verify(result)

    def test_unsafe_recovery_states_are_retained_without_recreation(self) -> None:
        result = self.materialize()
        manifest = self.bundle / "manifest.json"
        data = manifest.read_bytes()
        manifest.unlink()
        with self.assertRaises((self.module.AuthorityError, OSError)):
            self.materialize()
        self.assertFalse(manifest.exists())
        manifest.write_bytes(data)
        manifest.chmod(0o400)
        stage = self.base / ".bundle.authority-stage"
        stage.mkdir(mode=0o700)
        sentinel = stage / "unclassified"
        sentinel.write_bytes(b"retain")
        with self.assertRaises(self.module.AuthorityError):
            self.materialize()
        self.assertEqual(sentinel.read_bytes(), b"retain")
        sentinel.unlink()
        stage.rmdir()
        self.verify(result)
        intent_path = self.base / ".bundle.authority-intent.json"
        intent = json.loads(intent_path.read_bytes())
        intent["stage_identity"]["inode"] += 1
        intent_path.write_bytes(self.module.canonical(intent))
        with self.assertRaises(self.module.AuthorityError):
            self.materialize()
        self.assertEqual(manifest.read_bytes(), data)

    def test_socket_and_foreign_owner_metadata_refuse_every_role(self) -> None:
        # Synthetic fstat inputs keep this test independent of socket-bind permission.
        result = self.materialize()
        paths = [self.bundle / "manifest.json", self.bundle / "tree/policy.txt",
                 self.base / ".bundle.authority-intent.json", self.base / ".bundle.authority-lock"]
        original = os.fstat
        for path in paths:
            before = path.read_bytes()
            for field, replacement in [(0, stat.S_IFSOCK | 0o600), (4, os.getuid() + 1)]:
                def observe(fd):
                    info = original(fd)
                    if os.readlink(f"/proc/self/fd/{fd}") == str(path):
                        values = list(info)
                        values[field] = replacement
                        return os.stat_result(values)
                    return info
                with self.subTest(path=path, field=field):
                    with patch.object(self.module.os, "fstat", side_effect=observe):
                        with self.assertRaises(self.module.AuthorityError):
                            self.materialize()
                    self.assertEqual(path.read_bytes(), before)
        self.verify(result)

    def test_intent_record_types_and_manifest_schema_refuse(self) -> None:
        result = self.materialize()
        intent_path = self.base / ".bundle.authority-intent.json"
        original = intent_path.read_bytes()
        for mutation in [lambda value: value.update(state=[]),
                         lambda value: value.update(state="unknown"),
                         lambda value: value["request"].update(schema_version=True),
                         lambda value: value.update(stage_identity={"device": True, "inode": 1})]:
            value = json.loads(original)
            mutation(value)
            intent_path.write_bytes(self.module.canonical(value))
            before = intent_path.read_bytes()
            with self.assertRaises(self.module.AuthorityError):
                self.materialize()
            self.assertEqual(intent_path.read_bytes(), before)
        intent_path.write_bytes(original)
        manifest_path = self.bundle / "manifest.json"
        raw = manifest_path.read_bytes()
        for schema in [True, 2]:
            value = json.loads(raw)
            value["schema_version"] = schema
            changed = self.module.canonical(value)
            manifest_path.chmod(0o600)
            manifest_path.write_bytes(changed)
            manifest_path.chmod(0o400)
            with self.assertRaises(self.module.AuthorityError):
                self.verify({"manifest_digest": self.module.digest(changed)})
        manifest_path.chmod(0o600)
        manifest_path.write_bytes(raw)
        manifest_path.chmod(0o400)
        self.verify(result)

    def test_mount_view_change_refuses_before_publication(self) -> None:
        original = self.module.sync_bundle
        rows = self.module.mount_view()
        changed = [{**row, "id": row["id"] + "0"} for row in rows]
        view = rows
        def sync(bundle, entries):
            nonlocal view
            original(bundle, entries)
            view = changed
        with patch.object(self.module, "mount_view", side_effect=lambda: view), patch.object(self.module, "sync_bundle", side_effect=sync):
            with self.assertRaises(self.module.AuthorityError):
                self.materialize()
        self.assertFalse(self.bundle.exists())
        self.assertTrue((self.base / ".bundle.authority-stage/manifest.json").exists())
        self.verify(self.materialize())

    def test_worktree_submount_on_different_device_remains_excluded(self) -> None:
        rows = self.module.parse_mount_view((
            "1 0 0:42 / / rw - ext4 fixture rw\n"
            "2 1 0:999 / /internal rw - tmpfs fixture rw\n"
            "3 1 0:999 / /external rw - tmpfs fixture rw\n").encode())
        factory = lambda rows: SyntheticPhysicalView(self.real_view, rows, real=False)
        with patch.object(self.module, "PhysicalView", side_effect=factory):
            with self.assertRaises(self.module.AuthorityError):
                self.module.reject_mount_alias(Path("/internal"), Path("/external"), rows)
            rows[1]["point"] = Path("/worktree/internal")
            with self.assertRaises(self.module.AuthorityError):
                self.module.reject_mount_alias(Path("/worktree"), Path("/external"), rows)

    def test_git_both_stream_bounds_and_cleanup(self) -> None:
        executable = self.base / "fake-git"
        baseline = len(list(Path('/proc/self/fd').iterdir()))
        cases = [
            ("os.write(1,b'x'*128)", True),
            ("os.write(1,b'x'*129)", False),
            ("os.write(2,b'x'*128)", True),
            ("os.write(2,b'x'*129)", False),
            ("os.write(1,b'x'*128);os.write(2,b'y'*128)", True),
            ("os.write(1,b'x'*129);os.write(2,b'y'*129)", False),
            ("os.write(1,b'x');sys.exit(2)", False),
        ]
        for body, accepted in cases:
            executable.write_text(f"#!{sys.executable}\nimport os,sys\n{body}\n")
            executable.chmod(0o700)
            with self.subTest(body=body), patch.object(self.module.shutil, "which", return_value=str(executable)), patch.object(self.module, "MAX_FILE", 128):
                if accepted:
                    self.assertLessEqual(len(self.module.git(self.repo, "status")), 128)
                else:
                    with self.assertRaises(self.module.AuthorityError):
                        self.module.git(self.repo, "status")
            self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), baseline)

    def test_runtime_regular_sparse_growth_and_fifo_bounds(self) -> None:
        executable = self.base / "executable"
        executable.write_bytes(b'x' * 128)
        with patch.object(self.module, "MAX_FILE", 128):
            self.assertEqual(self.module.runtime_digest(executable), self.module.digest(b'x' * 128))
            with executable.open('r+b') as stream:
                stream.truncate(129)
            with self.assertRaises(self.module.AuthorityError), patch.object(self.module.os, "read", side_effect=AssertionError('oversized sparse file must not be read')):
                self.module.runtime_digest(executable)
            executable.write_bytes(b'x')
            original = os.read
            def grow(fd, size):
                executable.write_bytes(b'y' * 129)
                return original(fd, size)
            with patch.object(self.module.os, "read", side_effect=grow):
                with self.assertRaises(self.module.AuthorityError):
                    self.module.runtime_digest(executable)
            executable.unlink()
            os.mkfifo(executable)
            with self.assertRaises(self.module.AuthorityError), patch.object(self.module.os, "read", side_effect=AssertionError('FIFO must not be read')):
                self.module.runtime_digest(executable)
            executable.unlink()
            executable.write_bytes(b'x')
            with patch.object(self.module.os, "read", side_effect=OSError('injected read failure')):
                with self.assertRaises(OSError):
                    self.module.runtime_digest(executable)
            self.assertEqual(self.module.runtime_digest(executable), self.module.digest(b'x'))

    @unittest.skipUnless(sys.platform == "linux", "isolated Linux subreaper fixture")
    def test_query_success_and_deadline_terminate_owned_descendants(self) -> None:
        runtime = ROOT / "scripts/project_workflow/process_runtime.py"
        for mode in ("closed", "inherited"):
            with self.subTest(mode=mode):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", "-B", "-c", GROUP_DRIVER, str(runtime), mode],
                    cwd=self.base, env={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads(result.stdout)
                self.assertEqual(record["deadline_reached"], mode == "inherited")
                if mode == "closed":
                    self.assertEqual(record["leader_status"], 0)
                self.assertTrue(record["leader_reaped_before_fixture_cleanup"])
                self.assertFalse(record["descendant_running_after_capture"])
                self.assertLess(record["descendant_exit"], 0)
                self.assertTrue(record["fixture_reaped_descendant"])

    def test_missing_query_custody_refuses_before_child_start(self) -> None:
        runtime = self.module._local_processes()
        marker = self.base / "unsupported-query-started"
        with patch.object(os, "waitid", None, create=True):
            with self.assertRaises(runtime.CommandError):
                runtime.capture(
                    [sys.executable, "-I", "-S", "-B", "-c",
                     f"from pathlib import Path; Path({str(marker)!r}).write_text('started')"],
                    cwd=self.base, env=runtime.local_environment())
        self.assertFalse(marker.exists())
