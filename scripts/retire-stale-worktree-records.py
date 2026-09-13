#!/usr/bin/env python3
"""Remove ownership records that no repository can ever reach again.

`manage-plan-worktrees.py publish` and `retire` both unlink the record they
own, and both need the repository the record names. When that repository is
gone the record outlives every command that could reach it. Enough of them
push the shared directory past the count at which the guard refuses to read
it, and every guarded command stops.

Death is proved, not assumed. An absent path cannot by itself tell a deleted
repository from an unmounted disk, so this command accepts absence only when
the nearest existing ancestor of that path sits on the device the record
itself names: the filesystem is mounted, and the path on it is really gone.

The shape follows `retire-merged-worktrees.py`: a read-only `scan` that
writes one digest-bearing manifest, and an `apply-local` that consumes one
exact manifest and revalidates every fact immediately before each unlink.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# The lease is the record's own statement of how long it claims anything, and
# the guard caps it at MAX_LEASE_SECONDS. The extra hour is a clock-skew
# allowance, not a retention period: a task that outlives its lease is held
# back by its worktree still being present, not by waiting longer here.
CLOCK_SKEW_SECONDS = 3_600

KEY_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 4_194_304
MANIFEST_KEYS = {
    "schema_version",
    "state_directory",
    "generated_at",
    "candidates",
    "content_digest",
}
CANDIDATE_KEYS = {
    "key",
    "task",
    "worktree_path",
    "repository_git_dir",
    "lease_expires_at",
    "eligibility_results",
    "eligible",
    "retirable_paths",
}
ELIGIBILITY_KEYS = {
    "record_readable",
    "record_at_canonical_name",
    "lease_expired",
    "worktree_absent",
    "worktree_filesystem_present",
    "repository_absent",
    "repository_filesystem_present",
}
# One key owns exactly these three retirable files. Leaving any of them behind
# keeps the key half present for the next reader to judge. The lock is not in
# this set on purpose: it is the mutual-exclusion primitive itself, and moving
# it while holding it would let a second process lock a fresh file of the same
# name and believe it holds the key.
KEY_SUFFIXES = (".json", ".journal.json", ".publish.journal.json")
# Retirement moves a key here instead of unlinking it. Absence of a path is
# evidence that a repository is gone, never proof: it is read in one mount
# namespace, and device numbers are reused across reboots. Keeping the bytes
# makes a wrong verdict a recoverable inconvenience rather than a loss, and
# lets the guard keep failing closed while an operator checks the claim.
RETIRED_DIRECTORY_NAME = "retired"


class RecordRetirementError(ValueError):
    """A fail-closed local record retirement error."""


def load_worktree_guard():
    """Load the shared guard from either supported layout."""

    cached = sys.modules.get("worktree_guard")
    if cached is not None:
        return cached
    base = Path(__file__).resolve().parent
    for candidate in ("worktree_guard.py", "project_workflow/worktree_guard.py"):
        path = base / candidate
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("worktree_guard", path)
        if spec is None or spec.loader is None:
            break
        module = importlib.util.module_from_spec(spec)
        sys.modules["worktree_guard"] = module
        spec.loader.exec_module(module)
        return module
    raise SystemExit("retire stale worktree records failed: the shared worktree guard is missing")


guard = load_worktree_guard()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def add_content_digest(manifest: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(manifest)
    unsigned.pop("content_digest", None)
    digest = hashlib.sha256(canonical_json(unsigned)).hexdigest()
    return {**unsigned, "content_digest": f"sha256:{digest}"}


def validate_state_directory(raw: str) -> Path:
    """Resolve the record directory, refusing anything the guard would not own.

    The directory is named at runtime rather than assumed, so a test can work
    in isolation and an operator has to say out loud which directory is about
    to be changed. The guard's own ownership and privacy checks decide whether
    the named directory is one it could have written.
    """

    path = guard.canonical_directory(raw, label="ownership-record directory")
    if path == Path(path.root) or path == guard.account_home():
        raise RecordRetirementError("ownership-record directory must not be the root or the home directory")
    guard.require_owned_directory(path, label="ownership-record directory", private=True)
    return path


def mount_devices() -> list[tuple[Path, int]]:
    """Every current mount point and the device it carries.

    A device number on its own says nothing about where a filesystem is
    attached, and it is not stable across a reboot. Reading the mount table
    lets the absence test ask the question that actually matters: is a mount
    covering this path right now, and does it carry the device the record
    named.
    """

    try:
        data = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    except OSError as exc:
        raise RecordRetirementError(
            "the mount table is unavailable, so an absent path cannot be told from an unmounted one"
        ) from exc
    mounts: list[tuple[Path, int]] = []
    for line in data.splitlines():
        fields = line.split(" ")
        if len(fields) < 5:
            continue
        major, _, minor = fields[2].partition(":")
        try:
            device = os.makedev(int(major), int(minor))
        except ValueError:
            continue
        mounts.append((Path(fields[4].replace("\\040", " ")), device))
    return mounts


def covering_mount_device(path: Path, mounts: list[tuple[Path, int]]) -> int | None:
    """The device of the deepest mount whose mount point contains this path.

    Later entries win at the same mount point, because a mount stacked on an
    earlier one is what a reader of that path sees.
    """

    best: tuple[int, int] | None = None
    device: int | None = None
    for index, (mountpoint, candidate) in enumerate(mounts):
        if mountpoint == path or mountpoint in path.parents:
            key = (len(mountpoint.parts), index)
            if best is None or key > best:
                best, device = key, candidate
    return device


def has_symlink_component(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def nearest_existing_ancestor(path: Path) -> Path | None:
    """The closest ancestor that exists, refusing a symlink on the way."""

    current = path
    while True:
        try:
            metadata = os.lstat(current)
        except OSError:
            parent = current.parent
            if parent == current:
                return None
            current = parent
            continue
        if stat.S_ISLNK(metadata.st_mode):
            # A symlink can point anywhere, so it proves nothing about the
            # filesystem the recorded path lived on.
            return None
        return current


def absent_and_proved(path: Path, device: int, mounts: list[tuple[Path, int]]) -> tuple[bool, bool]:
    """Report whether a recorded path is absent, and whether that is proved.

    A path that still exists is never treated as unreachable, whatever its
    device and inode now say. Device numbers are not stable across a reboot,
    so reading a mismatch as "a different object" would delete the record of
    a task that is still there.

    Absence is accepted only when nothing on the way to the path is a symlink,
    the nearest existing ancestor sits on the recorded device, and a mount
    covering the path carries that same device. Together those say the
    filesystem is attached here now and the path on it is genuinely gone.
    """

    if has_symlink_component(path):
        return False, False
    try:
        os.lstat(path)
    except OSError:
        pass
    else:
        return False, True
    ancestor = nearest_existing_ancestor(path)
    if ancestor is None:
        return True, False
    try:
        if ancestor.stat().st_dev != device:
            return True, False
    except OSError:
        return True, False
    return True, covering_mount_device(path, mounts) == device


def expected_key(record: dict[str, Any]) -> str:
    """The key the guard itself would derive for this record's own contents."""

    identity = record["repository_identity"]
    return hashlib.sha256(
        guard.canonical_json(
            {
                "common_git_dir": identity["common_git_dir"],
                "common_git_dir_device": identity["common_git_dir_device"],
                "common_git_dir_inode": identity["common_git_dir_inode"],
                **guard.task_selector(record["task"]),
            }
        )
    ).hexdigest()


def record_paths(directory: Path) -> list[Path]:
    """Every file in the directory that is named like an ownership record."""

    if guard.has_symlink_component(directory):
        raise RecordRetirementError("ownership-record directory contains a symlink component")
    return sorted(
        path
        for path in directory.iterdir()
        if path.name.endswith(".json")
        and not path.name.endswith(".journal.json")
        and KEY_RE.fullmatch(path.name[: -len(".json")]) is not None
    )


def evaluate_record(path: Path, *, now: int, mounts: list[tuple[Path, int]]) -> dict[str, Any]:
    """Decide, from one record alone, whether anything could still reach it."""

    key = path.name[: -len(".json")]
    results = {name: False for name in ELIGIBILITY_KEYS}
    candidate: dict[str, Any] = {
        "key": key,
        "task": None,
        "worktree_path": None,
        "repository_git_dir": None,
        "lease_expires_at": None,
        "eligibility_results": results,
        "eligible": False,
        "retirable_paths": [],
    }
    try:
        record = guard.read_record(path)
    except (OSError, guard.WorktreeError):
        # An unreadable record is reported and left alone. This command removes
        # what it can account for, and cannot account for a file it cannot read.
        return candidate
    results["record_readable"] = True
    candidate["task"] = guard.task_label(record["task"])
    candidate["worktree_path"] = record["worktree_path"]
    candidate["repository_git_dir"] = record["repository_identity"]["common_git_dir"]
    candidate["lease_expires_at"] = record["owner"]["lease_expires_at"]

    results["record_at_canonical_name"] = expected_key(record) == key
    results["lease_expired"] = record["owner"]["lease_expires_at"] + CLOCK_SKEW_SECONDS <= now

    gone, proved = absent_and_proved(
        Path(record["worktree_path"]),
        record["worktree_identity"]["worktree_device"],
        mounts,
    )
    results["worktree_absent"] = gone
    results["worktree_filesystem_present"] = proved

    identity = record["repository_identity"]
    gone, proved = absent_and_proved(
        Path(identity["common_git_dir"]), identity["common_git_dir_device"], mounts
    )
    results["repository_absent"] = gone
    results["repository_filesystem_present"] = proved

    candidate["eligible"] = all(results.values())
    if candidate["eligible"]:
        candidate["retirable_paths"] = [
            path.parent.joinpath(key + suffix).name for suffix in KEY_SUFFIXES
        ]
    return candidate


def scan_directory(directory: Path, *, now: int) -> dict[str, Any]:
    paths = record_paths(directory)
    if len(paths) > guard.MAX_RECORDS_SCANNED * 4:
        raise RecordRetirementError("ownership-record directory holds an implausible record count")
    mounts = mount_devices()
    candidates = [evaluate_record(path, now=now, mounts=mounts) for path in paths]
    candidates.sort(key=lambda candidate: candidate["key"])
    return add_content_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "state_directory": str(directory),
            "generated_at": now,
            "candidates": candidates,
        }
    )


def validate_manifest_output(raw: str, project_root: Path) -> Path:
    requested = Path(raw)
    if not requested.is_absolute():
        requested = project_root / requested
    artifact_root = project_root / ".agent-artifacts/git-retirement"
    if guard.has_symlink_component(requested) or guard.has_symlink_component(artifact_root):
        raise RecordRetirementError("manifest output path contains a symlink component")
    if requested.suffix != ".json" or requested.parent.absolute() != artifact_root.absolute():
        raise RecordRetirementError(
            "manifest output must be one JSON file directly below .agent-artifacts/git-retirement"
        )
    if requested.exists() and (requested.is_symlink() or not requested.is_file()):
        raise RecordRetirementError("manifest output target must be a regular non-symlink file")
    artifact_root.mkdir(parents=True, exist_ok=True)
    return requested


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    data = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def open_exact_regular_file(path: Path) -> int:
    """Open one exact path without following a symlink at any component."""

    if not path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts[1:]):
        raise RecordRetirementError("manifest input path must remain absolute and normalized")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    directory = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = following
        descriptor = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
    finally:
        os.close(directory)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RecordRetirementError("manifest must remain a regular non-symlink file")
    return descriptor


def read_bounded_file(descriptor: int) -> bytes:
    """Read at most the bound, so an oversized file is refused rather than held."""

    chunks: list[bytes] = []
    remaining = MAX_MANIFEST_BYTES + 1
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > MAX_MANIFEST_BYTES:
        raise RecordRetirementError("manifest exceeds the size limit")
    return data


def validate_manifest_input(path: Path, project_root: Path) -> None:
    artifact_root = (project_root / ".agent-artifacts/git-retirement").absolute()
    if path.suffix != ".json" or path.parent.absolute() != artifact_root:
        raise RecordRetirementError(
            "manifest must be one JSON file directly below .agent-artifacts/git-retirement"
        )


def require_type(value: Any, kind: type, label: str) -> Any:
    if not isinstance(value, kind) or isinstance(value, bool) is not (kind is bool):
        raise RecordRetirementError(f"manifest {label} has the wrong type")
    return value


def validate_candidate(candidate: Any) -> None:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_KEYS:
        raise RecordRetirementError("manifest candidate does not carry the expected fields")
    key = candidate["key"]
    if not isinstance(key, str) or KEY_RE.fullmatch(key) is None:
        raise RecordRetirementError("manifest candidate key is not a record key")
    results = candidate["eligibility_results"]
    if not isinstance(results, dict) or set(results) != ELIGIBILITY_KEYS:
        raise RecordRetirementError("manifest candidate eligibility is incomplete")
    for name, value in results.items():
        require_type(value, bool, f"eligibility result {name}")
    require_type(candidate["eligible"], bool, "candidate eligible")
    if candidate["eligible"] != all(results.values()):
        raise RecordRetirementError("manifest candidate verdict disagrees with its own evidence")
    for name in ("task", "worktree_path", "repository_git_dir"):
        if candidate[name] is not None:
            require_type(candidate[name], str, f"candidate {name}")
    if candidate["lease_expires_at"] is not None:
        require_type(candidate["lease_expires_at"], int, "candidate lease_expires_at")
    paths = candidate["retirable_paths"]
    if not isinstance(paths, list):
        raise RecordRetirementError("manifest candidate retirable_paths must be a list")
    expected = [key + suffix for suffix in KEY_SUFFIXES] if candidate["eligible"] else []
    if paths != expected:
        raise RecordRetirementError("manifest candidate retirable_paths do not match its key")


def read_manifest(path: Path, project_root: Path) -> dict[str, Any]:
    validate_manifest_input(path, project_root)
    descriptor = open_exact_regular_file(path)
    try:
        data = read_bounded_file(descriptor)
    finally:
        os.close(descriptor)
    try:
        manifest = json.loads(
            data.decode("utf-8"), object_pairs_hook=guard.reject_duplicate_json_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordRetirementError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise RecordRetirementError("manifest does not carry the expected fields")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise RecordRetirementError(f"manifest schema_version must be {SCHEMA_VERSION}")
    if add_content_digest(manifest)["content_digest"] != manifest["content_digest"]:
        raise RecordRetirementError("manifest content digest does not match its contents")
    require_type(manifest["state_directory"], str, "state_directory")
    require_type(manifest["generated_at"], int, "generated_at")
    candidates = manifest["candidates"]
    if not isinstance(candidates, list):
        raise RecordRetirementError("manifest candidates must be a list")
    seen: set[str] = set()
    for candidate in candidates:
        validate_candidate(candidate)
        if candidate["key"] in seen:
            raise RecordRetirementError("manifest repeats a candidate key")
        seen.add(candidate["key"])
    return manifest


def retire_key(directory: Path, key: str, candidate: dict[str, Any], *, now: int) -> str:
    """Move one key aside under its own lock, or leave every file it owns alone.

    The manager takes this lock for prepare, resume, publish and retire, so
    taking it here keeps retirement on the same protocol rather than beside it.
    The lock file is never moved or unlinked: a second process would create and
    lock a new file of the same name and the two would both believe they hold
    the key.

    Every file the key owns is checked before any of them moves, because a
    refusal partway through would leave the key half present with no record
    left to account for it. The record moves last for the same reason.
    """

    record = directory / f"{key}.json"
    if not record.exists():
        # Checked before the lock so that a key with nothing left to retire
        # does not leave a fresh lock file behind on every run.
        return "already_absent"
    destination = directory / RETIRED_DIRECTORY_NAME
    moves: list[tuple[Path, Path]] = []
    with guard.locked_file(directory / f"{key}.lock"):
        if not record.exists():
            return "already_absent"
        if evaluate_record(record, now=now, mounts=mount_devices()) != candidate:
            return "changed_since_scan"
        guard.ensure_metadata_directory(destination)
        for suffix in KEY_SUFFIXES:
            source = directory / f"{key}{suffix}"
            target = destination / f"{key}{suffix}"
            if source.is_symlink():
                raise RecordRetirementError("ownership-record path is a symlink")
            if source.exists() and not source.is_file():
                raise RecordRetirementError("ownership-record path is not a regular file")
            if target.exists() or target.is_symlink():
                raise RecordRetirementError("a retired ownership record already holds that name")
            if source.exists():
                moves.append((source, target))
        for source, target in moves:
            if source != record:
                os.replace(source, target)
        if record.exists():
            os.replace(record, destination / f"{key}.json")
    return "retired"


def apply_manifest(manifest: dict[str, Any], directory: Path, *, now: int) -> dict[str, Any]:
    """Retire exactly what the manifest named, and only while it still holds.

    Every fact is derived again here rather than trusted from the manifest.
    The manifest chooses the target set; it never supplies the evidence.
    """

    if Path(manifest["state_directory"]) != directory:
        raise RecordRetirementError("manifest was produced for another ownership-record directory")
    outcomes: dict[str, list[str]] = {
        "retired": [],
        "already_absent": [],
        "changed_since_scan": [],
    }
    for candidate in manifest["candidates"]:
        if not candidate["eligible"]:
            continue
        outcomes[retire_key(directory, candidate["key"], candidate, now=now)].append(
            candidate["key"]
        )
    return {
        "operation": "apply-local",
        "state_directory": str(directory),
        "retired": sorted(outcomes["retired"]),
        "retired_directory": str(directory / RETIRED_DIRECTORY_NAME),
        "already_absent": sorted(outcomes["already_absent"]),
        "changed_since_scan": sorted(outcomes["changed_since_scan"]),
    }


def project_root_from_script() -> Path:
    base = Path(__file__).resolve().parent.parent
    return base


def command_scan(arguments: argparse.Namespace) -> int:
    directory = validate_state_directory(arguments.state_directory)
    manifest = scan_directory(directory, now=int(time.time()))
    output = validate_manifest_output(arguments.manifest_output, project_root_from_script())
    write_manifest(output, manifest)
    eligible = [item["key"] for item in manifest["candidates"] if item["eligible"]]
    print(
        json.dumps(
            {
                "operation": "scan",
                "manifest": str(output),
                "scanned": len(manifest["candidates"]),
                "eligible": len(eligible),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def command_apply_local(arguments: argparse.Namespace) -> int:
    directory = validate_state_directory(arguments.state_directory)
    manifest = read_manifest(Path(arguments.manifest).absolute(), project_root_from_script())
    report = apply_manifest(manifest, directory, now=int(time.time()))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="report retirable records without changing anything")
    scan.add_argument("--state-directory", required=True)
    scan.add_argument("--manifest-output", required=True)
    scan.set_defaults(handler=command_scan)

    apply_local = subparsers.add_parser(
        "apply-local", help="retire the records one unchanged manifest names"
    )
    apply_local.add_argument("--state-directory", required=True)
    apply_local.add_argument("--manifest", required=True)
    apply_local.set_defaults(handler=command_apply_local)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        return arguments.handler(arguments)
    except (RecordRetirementError, guard.WorktreeError) as error:
        print(f"retire stale worktree records failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
