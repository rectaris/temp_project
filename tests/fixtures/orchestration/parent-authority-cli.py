#!/usr/bin/env python3
"""Exercise one actual root or installed CLI against an offline Git fixture."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


def main() -> None:
    command = Path(sys.argv[1]).resolve(strict=True)
    git = shutil.which("git", path=os.defpath)
    if git is None:
        raise SystemExit("Git is required for the authority CLI fixture")
    environment = {
        "PATH": os.defpath, "LANG": "C", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_LAZY_FETCH": "1",
    }
    with tempfile.TemporaryDirectory(prefix="parent-authority-cli-") as temporary:
        base = Path(temporary)
        repository = base / "repository"
        repository.mkdir(mode=0o700)

        def git_query(*arguments: str) -> str:
            result = subprocess.run(
                [git, "-c", f"core.hooksPath={os.devnull}", "-C", str(repository), *arguments],
                env=environment, capture_output=True, text=True, check=True, timeout=30)
            return result.stdout.strip()

        git_query("init", "-q", "-b", "accepted")
        git_query("config", "user.name", "Offline authority fixture")
        git_query("config", "user.email", "fixture@example.invalid")
        git_query("remote", "add", "origin", "https://example.invalid/offline.git")
        scripts = repository / "scripts"
        scripts.mkdir()
        marker = base / "entrypoint-was-executed"
        contents = {
            "policy.txt": b"accepted fixture policy\n",
            "scripts/control.py": (
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('unexpected execution')\n"
            ).encode(),
        }
        for relative, data in contents.items():
            (repository / relative).write_bytes(data)
        git_query("add", ".")
        git_query("commit", "-qm", "Accept offline fixture")
        commit = git_query("rev-parse", "HEAD")
        bundle = base / "bundle"
        common = ["--repository", str(repository), "--bundle", str(bundle),
                  "--accepted-commit", commit, "--accepted-ref", "refs/heads/accepted"]

        def invoke(operation: str, *arguments: str, refused: bool = False) -> dict:
            result = subprocess.run(
                [str(command), operation, *arguments], cwd=base, env=environment,
                capture_output=True, text=True, check=False, timeout=60)
            if refused:
                if result.returncode == 0:
                    raise AssertionError(f"{operation} accepted corrupted inputs")
                return {}
            if result.returncode != 0:
                raise AssertionError(f"{operation} failed: {result.stderr}")
            return json.loads(result.stdout)

        materialized = invoke("materialize", *common, "--operation-id", "offline-cli")
        pin = materialized["manifest_digest"]
        manifest_path = bundle / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        expected_pin = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
        if pin != expected_pin or manifest["accepted_commit"] != commit:
            raise AssertionError("manifest did not bind the exact accepted source bytes")
        entries = {entry["path"]: entry for entry in manifest["inventory"]}
        if set(entries) != set(contents):
            raise AssertionError("materialized inventory differs from accepted fixture files")
        for relative, expected in contents.items():
            if (bundle / "tree" / relative).read_bytes() != expected:
                raise AssertionError(f"materialized content differs: {relative}")
            if entries[relative]["sha256"] != "sha256:" + hashlib.sha256(expected).hexdigest():
                raise AssertionError(f"manifest digest differs: {relative}")
        verified = invoke("verify", *common, "--manifest-digest", pin)
        if verified["verified"] is not True or verified["manifest_digest"] != pin:
            raise AssertionError("verification did not retain the parent manifest pin")
        recovered = invoke("materialize", *common, "--operation-id", "offline-cli")
        if recovered != materialized:
            raise AssertionError("same-operation recovery changed bundle identity")
        contract = invoke("launch-contract", "policy.txt", *common,
                          "--manifest-digest", pin, "--entrypoint", "scripts/control.py")
        for result in (materialized, verified, manifest, contract):
            if result["member_write_admitted"] is not False:
                raise AssertionError("an input operation admitted member writes")
        if contract["execution_authorized"] is not False or marker.exists():
            raise AssertionError("the launch contract authorized or performed execution")
        if contract["manifest_digest"] != pin or contract["cwd"] != str(bundle / "tree"):
            raise AssertionError("the launch contract escaped the pinned input root")
        if contract["argv"][-1] != str(bundle / "tree/policy.txt"):
            raise AssertionError("the launch argument did not name a fixed inventory file")
        if any(manifest["runtime"][field] is not False
               for field in ("stdlib_closure_verified", "native_entrypoint_verified")):
            raise AssertionError("unverified execution capabilities became verified")

        damaged = bundle / "tree/policy.txt"
        original_mode = stat.S_IMODE(damaged.stat().st_mode)
        damaged.chmod(0o600)
        damaged.write_bytes(b"retained corrupted fixture bytes\n")
        damaged.chmod(original_mode)
        retained = damaged.read_bytes()
        invoke("verify", *common, "--manifest-digest", pin, refused=True)
        invoke("materialize", *common, "--operation-id", "offline-cli", refused=True)
        if damaged.read_bytes() != retained or manifest_path.read_bytes() != manifest_bytes:
            raise AssertionError("a refused operation repaired or replaced retained evidence")
        if marker.exists():
            raise AssertionError("a refused input operation ran the captured entrypoint")
        print(json.dumps({"cli": str(command), "accepted_commit": commit,
                          "manifest_digest": pin, "corruption_refused_and_retained": True,
                          "execution_authorized": False, "member_write_admitted": False},
                         sort_keys=True))


if __name__ == "__main__":
    main()
