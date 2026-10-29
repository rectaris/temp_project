"""Materialize accepted Git controls without admitting member execution.

The parent supplies the accepted publication ref and pins the returned manifest
digest. Filesystem ownership and modes are identity checks, not a sandbox against
the same OS user. Native registration and member admission belong to integration.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from types import ModuleType
from urllib.parse import urlsplit, urlunsplit


SCHEMA = 1
MAX_FILE = 32 * 1024 * 1024
LOCAL_PROCESSES: ModuleType | None = None
MAX_TOTAL = 256 * 1024 * 1024
OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
OPERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class AuthorityError(ValueError):
    """An authority input is absent, divergent or unsafe."""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def plain_path(path: Path, *, exists: bool = True) -> Path:
    path = path.absolute()
    if any(part in {".", ".."} for part in path.parts):
        raise AuthorityError("path traversal is not an authority identity")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise AuthorityError("authority path contains a symlink")
    if exists and not path.exists():
        raise AuthorityError("authority path is missing")
    return path


def open_regular(path: Path) -> int:
    """Walk exact components without following a substituted parent or FIFO."""
    path = plain_path(path)
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for component in path.parts[1:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=directory)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise AuthorityError("authority input must be a regular file")
            if not os.path.samestat(info, path.stat(follow_symlinks=False)):
                raise AuthorityError("authority path changed during opening")
            return fd
        except BaseException:
            os.close(fd)
            raise
    finally:
        os.close(directory)


def open_owned(path: Path) -> int:
    fd = open_regular(path)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o022:
            raise AuthorityError("authority file must be owned, single-link and regular")
        return fd
    except BaseException:
        os.close(fd)
        raise


def runtime_digest(path: Path) -> str:
    fd = open_regular(path)
    try:
        before = os.fstat(fd)
        if before.st_size > MAX_FILE:
            raise AuthorityError("runtime executable exceeds its byte bound")
        hasher = hashlib.sha256()
        total = 0
        while chunk := os.read(fd, min(65536, MAX_FILE + 1 - total)):
            total += len(chunk)
            if total > MAX_FILE:
                raise AuthorityError("runtime executable exceeds its byte bound")
            hasher.update(chunk)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns
        ) or not os.path.samestat(after, path.stat(follow_symlinks=False)):
            raise AuthorityError("runtime executable changed during reading")
        return "sha256:" + hasher.hexdigest()
    finally:
        os.close(fd)


def read_owned(path: Path, *, limit: int = MAX_FILE) -> bytes:
    fd = open_owned(path)
    try:
        before = os.fstat(fd)
        if before.st_size > limit:
            raise AuthorityError("authority input exceeds its byte bound")
        data = bytearray()
        while chunk := os.read(fd, min(65536, limit + 1 - len(data))):
            data.extend(chunk)
            if len(data) > limit:
                raise AuthorityError("authority input exceeds its byte bound")
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns
        ) or not os.path.samestat(after, path.stat(follow_symlinks=False)):
            raise AuthorityError("authority file changed during reading")
        return bytes(data)
    finally:
        os.close(fd)


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise AuthorityError("duplicate authority JSON key")
        value[key] = item
    return value


def parse_record(data: bytes) -> dict:
    try:
        value = json.loads(data, object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuthorityError("invalid authority JSON") from error
    if not isinstance(value, dict):
        raise AuthorityError("authority record must be an object")
    return value


def read_record(path: Path) -> dict:
    return parse_record(read_owned(path))


def relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value or path.is_absolute() or path.as_posix() != value
        or ".." in path.parts or "\\" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise AuthorityError("invalid exact authority inventory path")
    return value


def _local_processes() -> ModuleType:
    global LOCAL_PROCESSES
    if LOCAL_PROCESSES is None:
        path = Path(__file__).resolve().with_name("process_runtime.py")
        if path.is_symlink() or not path.is_file():
            raise AuthorityError("required local process support is unavailable")
        with path.open("rb") as stream:
            source = stream.read(2 * 1024 * 1024 + 1)
        if len(source) > 2 * 1024 * 1024:
            raise AuthorityError("local process support exceeds its resource bound")
        module = ModuleType(__name__ + "_local_processes")
        module.__file__ = str(path)
        sys.modules[module.__name__] = module
        exec(compile(source, str(path), "exec"), module.__dict__)
        LOCAL_PROCESSES = module
    return LOCAL_PROCESSES


def git(repo: Path, *args: str) -> bytes:
    runtime = _local_processes()
    try:
        completed = runtime.immutable_git_capture(
            repo, *args, timeout=60, limit=MAX_FILE, keep_stderr=False)
    except runtime.GitCapabilityError as error:
        raise AuthorityError(str(error)) from error
    except (OSError, RuntimeError) as error:
        raise AuthorityError("accepted repository Git query refused") from error
    if completed.returncode:
        raise AuthorityError("accepted repository Git query refused")
    return completed.stdout


def repository_identity(repo: Path) -> dict:
    repo = plain_path(repo)
    common = plain_path(Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()))
    origin = git(repo, "remote", "get-url", "origin").decode().strip()
    if re.fullmatch(r"[^/@:\s]+@[^/:\s]+:[^:\s]+", origin):
        host, path = origin.split("@", 1)[1].split(":", 1)
        origin = f"ssh://{host.lower()}/{path.removesuffix('.git')}"
    else:
        url = urlsplit(origin)
        if (
            url.scheme not in {"https", "ssh", "git"} or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or url.path in {"", "/"}
        ):
            raise AuthorityError("repository requires a credential-free canonical origin")
        port = f":{url.port}" if url.port is not None else ""
        origin = urlunsplit((url.scheme, url.hostname.lower() + port, url.path.removesuffix(".git"), "", ""))
    info = common.stat()
    return {
        "common_git_dir": str(common), "device": info.st_dev, "inode": info.st_ino,
        "origin_digest": digest(origin.encode()),
    }


def accepted_inventory(repo: Path, commit: str, accepted_ref: str) -> list[dict]:
    if not OID.fullmatch(commit) or not re.fullmatch(r"refs/heads/[A-Za-z0-9._/-]+", accepted_ref):
        raise AuthorityError("accepted source must name an exact commit and local publication ref")
    if git(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise AuthorityError("accepted source is not a Git commit")
    # The parent owns this ref selector; no member-supplied selector is admitted.
    git(repo, "merge-base", "--is-ancestor", commit, accepted_ref)
    entries = []
    total = 0
    for raw in git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not raw:
            continue
        header, raw_path = raw.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        path = relative_path(raw_path.decode("utf-8"))
        if kind != "blob" or mode not in {"100644", "100755"} or not OID.fullmatch(oid):
            raise AuthorityError("tracked symlink, gitlink or unsupported authority object")
        content = git(repo, "cat-file", "blob", oid)
        total += len(content)
        if total > MAX_TOTAL:
            raise AuthorityError("accepted authority tree exceeds its byte bound")
        entries.append({"path": path, "oid": oid, "mode": mode, "sha256": digest(content), "size": len(content)})
    if not entries:
        raise AuthorityError("accepted authority inventory is empty")
    return sorted(entries, key=lambda entry: entry["path"])


def runtime_inventory() -> dict:
    """Pin executable inputs; native/host confinement remains a separate gate.

    Python runs with -I -S. The caller must also pin its standard-library inputs;
    this inventory deliberately does not claim their closure is proven.
    """
    result = {}
    for name, path in (("python", Path(sys.executable).resolve()), ("git", Path(shutil.which("git", path=os.defpath) or ""))):
        if not path.is_absolute() or not path.is_file():
            raise AuthorityError("runtime executable is unavailable")
        path = plain_path(path.resolve())
        result[name] = {"path": str(path), "sha256": runtime_digest(path)}
    return {"executables": result, "stdlib_closure_verified": False, "native_entrypoint_verified": False}


def verify_runtime(value: dict) -> None:
    if value != runtime_inventory():
        raise AuthorityError("runtime capability inventory changed")


def owned_directory(path: Path) -> None:
    plain_path(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise AuthorityError("parent authority directory must be owned and private")


def mount_view() -> list[dict]:
    """Read only the current Linux kernel view; callers cannot supply a table."""
    if not sys.platform.startswith("linux"):
        raise AuthorityError("physical authority placement requires Linux mountinfo")
    with open(f"/proc/{os.getpid()}/mountinfo", "rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    if not raw or len(raw) > MAX_FILE:
        raise AuthorityError("mount view is missing or exceeds its byte bound")
    return parse_mount_view(raw)


def parse_mount_view(raw: bytes) -> list[dict]:
    def decode(value: str) -> PurePosixPath:
        if re.search(r"\\(?!040|011|012|134)", value):
            raise AuthorityError("unsupported mount path escape")
        value = re.sub(r"\\(040|011|012|134)", lambda match: chr(int(match[1], 8)), value)
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts:
            raise AuthorityError("invalid mount path")
        return path

    rows, identities = [], set()
    if not raw or len(raw) > MAX_FILE:
        raise AuthorityError("mount view is missing or exceeds its byte bound")
    for line in os.fsdecode(raw).splitlines():
        fields = line.split(" ")
        if fields.count("-") != 1:
            raise AuthorityError("invalid mount view")
        separator = fields.index("-")
        if (separator < 6 or len(fields) != separator + 4
                or not fields[0].isdigit() or not fields[1].isdigit() or fields[0] in identities
                or not re.fullmatch(r"[0-9]+:[0-9]+", fields[2])):
            raise AuthorityError("invalid mount identity")
        identities.add(fields[0])
        filesystem = fields[separator + 1]
        # nsfs names a mounted namespace object rather than a filesystem path.
        # Retain the row, but never use that name as a physical projection.
        handle = re.fullmatch(r"[a-z][a-z0-9_]{0,63}:\[([1-9][0-9]{0,19})\]", fields[3])
        opaque = (filesystem == "nsfs" and handle is not None
                  and int(handle[1]) <= 2**64 - 1)
        rows.append({"id": fields[0], "device": tuple(map(int, fields[2].split(":"))),
                     "root": None if opaque else decode(fields[3]),
                     "point": decode(fields[4]), "filesystem": filesystem,
                     "parent": fields[1], "source": fields[separator + 2]})
    return rows


class PhysicalView:
    """Pinned nofollow namespace paths, interpreted in one mount snapshot."""

    def __init__(self, rows: list[dict]):
        if not hasattr(os, "O_PATH"):
            raise AuthorityError("physical placement requires O_PATH")
        self.rows = rows
        self.nodes: dict[Path, dict] = {}
        self.missing: set[Path] = set()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.recheck()
        finally:
            for node in self.nodes.values():
                os.close(node["fd"])

    @staticmethod
    def descriptor(fd: int) -> tuple:
        info = os.fstat(fd)
        try:
            with open(f"/proc/{os.getpid()}/fdinfo/{fd}", "rb") as stream:
                raw = stream.read(65537)
        except OSError as exc:
            raise AuthorityError("mount descriptor metadata is unavailable") from exc
        matches = re.findall(rb"^mnt_id:\s+([0-9]+)$", raw, re.MULTILINE)
        if len(raw) > 65536 or len(matches) != 1:
            raise AuthorityError("mount descriptor identity is missing or ambiguous")
        return info, matches[0].decode("ascii")

    def node(self, path: Path) -> dict:
        if path in self.nodes:
            return self.nodes[path]
        if len(self.nodes) >= 512:
            raise AuthorityError("physical observation exceeds descriptor bound")
        parent = None if path == Path("/") else self.node(path.parent)
        if parent is not None and not stat.S_ISDIR(parent["info"].st_mode):
            raise AuthorityError("physical path parent is not a directory")
        fd = -1
        try:
            fd = os.open("/" if parent is None else path.name,
                         os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                         **({} if parent is None else {"dir_fd": parent["fd"]}))
            info, mount_id = self.descriptor(fd)
            if stat.S_ISLNK(info.st_mode):
                raise AuthorityError("physical path contains a symlink")
            node = {"fd": fd, "info": info, "mount_id": mount_id, "path": path}
            self.nodes[path] = node
            return node
        except BaseException:
            if fd >= 0:
                os.close(fd)
            raise

    def chain(self, path: Path, *, missing: bool = False) -> list[dict]:
        if not path.is_absolute() or ".." in path.parts or len(path.parts) > 256:
            raise AuthorityError("physical path is not bounded and absolute")
        result = []
        current = Path("/")
        for name in ("/", *path.parts[1:]):
            if name != "/":
                current /= name
            try:
                result.append(self.node(current))
            except FileNotFoundError:
                if missing and current == path:
                    self.missing.add(path)
                    return result
                raise AuthorityError("required physical path is missing") from None
            except OSError as exc:
                raise AuthorityError("required physical path cannot be observed") from exc
        return result

    @staticmethod
    def identity(node: dict, *, namespace: bool = True) -> tuple:
        info = node["info"]
        return (info.st_dev, info.st_ino, node["mount_id"] if namespace else None)

    def row(self, node: dict, *, physical: bool = True) -> dict:
        rows = [row for row in self.rows if row["id"] == node["mount_id"]]
        info = node["info"]
        if len(rows) != 1 or rows[0]["device"] != (os.major(info.st_dev), os.minor(info.st_dev)):
            raise AuthorityError("descriptor mount and snapshot identity differ")
        row = rows[0]
        if physical and (row["filesystem"] not in {"ext4", "xfs", "tmpfs"} or row["root"] is None):
            raise AuthorityError("unsupported physical filesystem view")
        return row

    def attachment(self, point: Path, anchors: list[list[dict]]) -> list[dict] | None:
        ancestor_ids = {self.identity(node) for chain in anchors for node in chain}
        endpoint_ids = {self.identity(chain[-1]) for chain in anchors}
        chain = []
        current = Path("/")
        for name in ("/", *point.parts[1:]):
            if len(chain) >= 256:
                raise AuthorityError("mount attachment exceeds ancestry bound")
            if name != "/":
                current /= name
            try:
                chain.append(self.node(current))
            except OSError as exc:
                raise AuthorityError("mount attachment relation is unknown") from exc
            identities = {self.identity(node) for node in chain}
            if self.identity(chain[-1]) not in ancestor_ids and not identities & endpoint_ids:
                # Kernel-resolved namespace branches have diverged. Do not open
                # an inaccessible/autofs suffix merely to prove this target role.
                return None
        return chain

    def coordinate(self, chain: list[dict], row: dict) -> PurePosixPath:
        point = self.chain(Path(row["point"]))
        if point[-1]["mount_id"] != row["id"]:
            raise AuthorityError("mount attachment is shadowed or ambiguous")
        identity = self.identity(point[-1])
        indexes = [i for i, node in enumerate(chain) if self.identity(node) == identity]
        if len(indexes) != 1:
            raise AuthorityError("covering mount ancestry is unknown")
        return row["root"].joinpath(*(node["path"].name for node in chain[indexes[0] + 1:]))

    def projected(self, chain: list[dict]) -> list[list[dict]]:
        row = self.row(chain[-1])
        coordinate = self.coordinate(chain, row)
        # A full visible filesystem root proves source genealogy without using
        # a lexical mismatch to discard possibly equivalent root spellings.
        roots = [r for r in self.rows if r["device"] == row["device"] and r["root"] == PurePosixPath("/")
                 and r["filesystem"] in {"ext4", "xfs", "tmpfs"}]
        if not roots:
            raise AuthorityError("widest physical source projection is unavailable")
        result = []
        for root in roots:
            point = self.chain(Path(root["point"]))
            if self.row(point[-1]) != root:
                raise AuthorityError("widest projection is shadowed")
            projected = self.chain(Path(root["point"] / coordinate.relative_to("/")))
            if self.row(projected[-1])["device"] != row["device"] or self.identity(projected[-1], namespace=False) != self.identity(chain[-1], namespace=False):
                raise AuthorityError("physical source projection identity differs")
            result.append(projected[len(point) - 1:])
        return result

    def recheck(self) -> None:
        for path, node in self.nodes.items():
            parent = None if path == Path("/") else self.nodes[path.parent]
            fd = -1
            try:
                fd = os.open("/" if parent is None else path.name,
                             os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                             **({} if parent is None else {"dir_fd": parent["fd"]}))
                info, mount_id = self.descriptor(fd)
                if (info.st_dev, info.st_ino, mount_id) != self.identity(node):
                    raise AuthorityError("physical path binding changed")
            except OSError as exc:
                raise AuthorityError("physical path binding cannot be rechecked") from exc
            finally:
                if fd >= 0:
                    os.close(fd)
        for path in self.missing:
            parent = self.nodes[path.parent]
            fd = -1
            try:
                fd = os.open(path.name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent["fd"])
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise AuthorityError("future path absence cannot be rechecked") from exc
            finally:
                if fd >= 0:
                    os.close(fd)
            raise AuthorityError("future physical target changed")


def covering_mount(path: Path, rows: list[dict]) -> dict:
    with PhysicalView(rows) as view:
        return view.row(view.chain(path)[-1])


def reject_mount_alias(worktree: Path, protected: Path, rows: list[dict]) -> None:
    with PhysicalView(rows) as view:
        work = view.chain(worktree)
        authority = view.chain(protected, missing=True)
        future = authority[-1]["path"] != protected
        wm, am = view.row(work[-1]), view.row(authority[-1])
        if any(row["root"] is None and row["device"] == am["device"] for row in rows):
            raise AuthorityError("opaque mount root prevents physical source proof")
        regions = [work]
        for row in rows:
            attachment = view.attachment(Path(row["point"]), [work, authority])
            if attachment is None:
                continue  # Retained in view.rows for its separate source role.
            if attachment[-1]["mount_id"] != row["id"]:
                raise AuthorityError("relevant attachment is stacked or shadowed")
            ids = [view.identity(node) for node in attachment]
            protected_id = view.identity(authority[-1])
            work_id = view.identity(work[-1])
            if not future and protected_id in ids and ids[-1] != protected_id:
                raise AuthorityError("mounted authority descendants prevent exclusion proof")
            if work_id in ids:
                view.row(attachment[-1])
                regions.append(attachment)
        for region in regions:
            if view.row(region[-1])["device"] != am["device"]:
                continue
            authorities = view.projected(authority)
            reachable = view.projected(region)
            for source in authorities:
                for member in reachable:
                    authority_ids = [view.identity(node, namespace=False) for node in source]
                    member_ids = [view.identity(node, namespace=False) for node in member]
                    if member_ids[-1] in authority_ids or (not future and authority_ids[-1] in member_ids):
                        raise AuthorityError("physical authority and worktree source regions overlap")
        # Pinned namespace paths are rechecked on context exit. Mountview changes
        # also refuse before this placement proof can be used for an effect.
        if mount_view() != rows:
            raise AuthorityError("mount snapshot changed during physical observation")


def external_destination(repo: Path, destination: Path) -> Path:
    destination = plain_path(destination, exists=False)
    owned_directory(destination.parent)
    worktrees = [
        Path(os.fsdecode(record.removeprefix(b"worktree "))).absolute()
        for record in git(repo, "worktree", "list", "--porcelain", "-z").split(b"\0")
        if record.startswith(b"worktree ")
    ]
    rows = mount_view()
    for worktree in worktrees:
        reject_mount_alias(worktree, destination, rows)
    for ancestor in (destination, *destination.parents):
        if not ancestor.exists():
            continue
        for worktree in worktrees:
            # Physical identity also covers case folding and alternate spellings.
            if ancestor.samefile(worktree):
                raise AuthorityError("parent authority must be outside every repository worktree")
    return destination


def write_new(path: Path, data: bytes, mode: int = 0o600) -> None:
    plain_path(path, exists=False)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Retain incomplete bytes. Recovery may not substitute a fresh record.
        raise


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_bundle(bundle: Path, entries: list[dict]) -> None:
    """Persist verified recovered bytes and child names before publication."""
    for path in [bundle / "manifest.json", *[bundle / "tree" / entry["path"] for entry in entries]]:
        fd = open_owned(path)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    tree = bundle / "tree"
    for relative in sorted(expected_directories(entries), key=lambda value: len(PurePosixPath(value).parts), reverse=True):
        sync_directory(tree / relative)
    sync_directory(tree)
    sync_directory(bundle)
    sync_directory(bundle.parent)


def replace_owned(path: Path, value: dict) -> None:
    read_owned(path)
    temp = path.with_name(path.name + ".next")
    write_new(temp, canonical(value))
    os.replace(temp, path)
    sync_directory(path.parent)


def tree_paths(root: Path) -> tuple[set[str], set[str]]:
    files, directories = set(), set()
    for base, names, leaves in os.walk(root, followlinks=False):
        for name in names:
            path = Path(base) / name
            owned_directory(path)
            directories.add(path.relative_to(root).as_posix())
        for name in leaves:
            path = Path(base) / name
            plain_path(path)
            files.add(path.relative_to(root).as_posix())
    return files, directories


def expected_directories(entries: list[dict]) -> set[str]:
    return {
        parent.as_posix() for entry in entries
        for parent in PurePosixPath(entry["path"]).parents if parent != PurePosixPath(".")
    }


def verify_files(root: Path, entries: list[dict], *, complete: bool) -> None:
    files, directories = tree_paths(root)
    expected = {entry["path"] for entry in entries}
    if files - expected or directories - expected_directories(entries) or (complete and files != expected):
        raise AuthorityError("authority tree inventory diverges")
    for entry in entries:
        path = root / entry["path"]
        if not path.exists():
            if complete:
                raise AuthorityError("authority blob is missing")
            continue
        content = read_owned(path)
        mode = 0o500 if entry["mode"] == "100755" else 0o400
        if len(content) != entry["size"] or digest(content) != entry["sha256"] or stat.S_IMODE(path.stat().st_mode) != mode:
            raise AuthorityError("authority blob bytes or mode diverge")


def verify_bundle(repo: Path, bundle: Path, commit: str, accepted_ref: str, expected_digest: str) -> dict:
    if not DIGEST.fullmatch(expected_digest):
        raise AuthorityError("parent-pinned manifest digest is required")
    bundle = external_destination(repo, bundle)
    owned_directory(bundle)
    raw = read_owned(bundle / "manifest.json")
    if stat.S_IMODE((bundle / "manifest.json").stat().st_mode) != 0o400 or digest(raw) != expected_digest:
        raise AuthorityError("authority manifest differs from the parent pin")
    manifest = parse_record(raw)
    keys = {"schema_version", "repository", "accepted_commit", "accepted_ref", "operation_id", "inventory", "runtime", "member_write_admitted"}
    if set(manifest) != keys or type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA:
        raise AuthorityError("unsupported authority manifest schema")
    if (
        manifest["repository"] != repository_identity(repo)
        or manifest["accepted_commit"] != commit or manifest["accepted_ref"] != accepted_ref
        or not isinstance(manifest["operation_id"], str) or not OPERATION.fullmatch(manifest["operation_id"])
        or manifest["member_write_admitted"] is not False
        or canonical(manifest["inventory"]) != canonical(accepted_inventory(repo, commit, accepted_ref))
    ):
        raise AuthorityError("authority manifest source or repository binding diverges")
    verify_runtime(manifest["runtime"])
    files, directories = tree_paths(bundle)
    if (
        files != {"manifest.json"} | {"tree/" + entry["path"] for entry in manifest["inventory"]}
        or directories != {"tree"} | {"tree/" + path for path in expected_directories(manifest["inventory"])}
    ):
        raise AuthorityError("authority bundle contains unclassified files")
    owned_directory(bundle / "tree")
    verify_files(bundle / "tree", manifest["inventory"], complete=True)
    return manifest


def materialize(repo: Path, destination: Path, commit: str, accepted_ref: str, operation_id: str) -> dict:
    if not OPERATION.fullmatch(operation_id):
        raise AuthorityError("invalid bounded operation identity")
    destination = external_destination(repo, destination)
    placement_view = mount_view()
    identity = repository_identity(repo)
    entries = accepted_inventory(repo, commit, accepted_ref)
    manifest = {
        "schema_version": SCHEMA, "repository": identity, "accepted_commit": commit,
        "accepted_ref": accepted_ref, "operation_id": operation_id, "inventory": entries,
        "runtime": runtime_inventory(), "member_write_admitted": False,
    }
    raw_manifest = canonical(manifest)
    manifest_digest = digest(raw_manifest)
    result = {"bundle": str(destination), "manifest_digest": manifest_digest, "member_write_admitted": False}
    prefix = "." + destination.name + ".authority"
    intent_path = destination.with_name(prefix + "-intent.json")
    stage = destination.with_name(prefix + "-stage")
    lock_path = destination.with_name(prefix + "-lock")
    # Staging and sibling recovery records are protected before the first write.
    for path in (stage, intent_path, intent_path.with_name(intent_path.name + ".next"), lock_path):
        external_destination(repo, path)
    # A retained lock is inert but must keep its identity; never unlink it.
    plain_path(lock_path, exists=False)
    created_lock = False
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    except FileNotFoundError:
        if any(path.exists() for path in (
                intent_path, stage, destination, intent_path.with_name(intent_path.name + ".next"))):
            raise AuthorityError("bound authority operation lock is missing; recreation is closed")
        try:
            lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            created_lock = True
        except FileExistsError:
            lock_fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(lock_fd, "r+") as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise AuthorityError("invalid parent authority operation lock")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        path_info = lock_path.lstat()
        if (not stat.S_ISREG(path_info.st_mode) or path_info.st_uid != os.getuid()
                or path_info.st_nlink != 1 or stat.S_IMODE(path_info.st_mode) != 0o600
                or (path_info.st_dev, path_info.st_ino) != (info.st_dev, info.st_ino)):
            raise AuthorityError("authority operation lock identity or custody changed")
        next_path = intent_path.with_name(intent_path.name + ".next")
        if next_path.exists():
            raise FileExistsError(errno.EEXIST, "retained authority intent update is ambiguous", str(next_path))
        request = {
            "schema_version": SCHEMA, "destination": str(destination), "stage": str(stage),
            "manifest_digest": manifest_digest, "operation_id": operation_id, "repository": identity,
            "lock_identity": {"device": info.st_dev, "inode": info.st_ino},
        }
        if intent_path.exists():
            intent = read_record(intent_path)
            if (set(intent) != {"request", "stage_identity", "state"}
                    or canonical(intent["request"]) != canonical(request)
                    or not isinstance(intent["state"], str)
                    or intent["state"] not in {"prepared", "published"}):
                raise AuthorityError("foreign or different-operation authority intent is retained")
        else:
            if not created_lock or destination.exists() or stage.exists():
                raise AuthorityError("unbound or unclassified authority operation state is retained")
            intent = {"request": request, "stage_identity": None, "state": "prepared"}
            write_new(intent_path, canonical(intent))
            sync_directory(destination.parent)
        stage_identity = intent["stage_identity"]
        if stage_identity is not None and (
            not isinstance(stage_identity, dict) or set(stage_identity) != {"device", "inode"}
            or any(type(stage_identity[key]) is not int or stage_identity[key] < 0
                   for key in ("device", "inode"))
        ):
            raise AuthorityError("invalid bound stage identity")
        if destination.exists():
            if stage.exists():
                raise AuthorityError("authority publication has ambiguous stage and destination")
            verify_bundle(repo, destination, commit, accepted_ref, manifest_digest)
            info = destination.stat()
            if intent["stage_identity"] != {"device": info.st_dev, "inode": info.st_ino}:
                raise AuthorityError("published authority directory identity changed")
            sync_bundle(destination, entries)
            intent["state"] = "published"
            replace_owned(intent_path, intent)
            return result
        if intent["state"] != "prepared":
            raise AuthorityError("published authority is missing; recreation is closed")
        if not stage.exists():
            if intent["stage_identity"] is not None:
                raise AuthorityError("bound authority stage is missing; recreation is closed")
            stage.mkdir(mode=0o700)
            info = stage.stat()
            intent["stage_identity"] = {"device": info.st_dev, "inode": info.st_ino}
            replace_owned(intent_path, intent)
        owned_directory(stage)
        info = stage.stat()
        if intent["stage_identity"] != {"device": info.st_dev, "inode": info.st_ino}:
            raise AuthorityError("authority stage identity differs from its intent")
        manifest_path = stage / "manifest.json"
        if manifest_path.exists() or manifest_path.is_symlink():
            verify_bundle(repo, stage, commit, accepted_ref, manifest_digest)
        tree = stage / "tree"
        if not tree.exists():
            tree.mkdir(mode=0o700)
        owned_directory(tree)
        verify_files(tree, entries, complete=False)
        for entry in entries:
            path = tree / entry["path"]
            if path.exists():
                continue
            for parent in reversed(path.parents):
                if parent == tree or tree in parent.parents:
                    if not parent.exists():
                        parent.mkdir(mode=0o700)
                    owned_directory(parent)
            content = git(repo, "cat-file", "blob", entry["oid"])
            if digest(content) != entry["sha256"]:
                raise AuthorityError("Git blob changed during materialization")
            write_new(path, content, 0o500 if entry["mode"] == "100755" else 0o400)
            sync_directory(path.parent)
        if manifest_path.exists():
            if read_owned(manifest_path) != raw_manifest:
                raise AuthorityError("retained staged manifest diverges")
        else:
            write_new(manifest_path, raw_manifest, 0o400)
        verify_bundle(repo, stage, commit, accepted_ref, manifest_digest)
        if repository_identity(repo) != identity:
            raise AuthorityError("repository changed before authority publication")
        sync_bundle(stage, entries)
        external_destination(repo, destination)
        if mount_view() != placement_view:
            raise AuthorityError("physical mount view changed before publication")
        os.rename(stage, destination)
        sync_directory(destination.parent)
        intent["state"] = "published"
        replace_owned(intent_path, intent)
        return result


def launch_contract(repo: Path, bundle: Path, commit: str, accepted_ref: str, expected_digest: str, entrypoint: str, arguments: list[str]) -> dict:
    manifest = verify_bundle(repo, bundle, commit, accepted_ref, expected_digest)
    relative_path(entrypoint)
    entries = {entry["path"]: entry for entry in manifest["inventory"]}
    if entrypoint not in entries or not entrypoint.endswith(".py"):
        raise AuthorityError("entrypoint is outside the fixed Python inventory")
    # Until a typed flag contract is admitted, arguments select only fixed files.
    fixed_arguments = []
    for argument in arguments:
        relative_path(argument)
        if argument not in entries:
            raise AuthorityError("argument is outside the fixed authority inventory")
        fixed_arguments.append(str(bundle.absolute() / "tree" / argument))
    script = bundle.absolute() / "tree" / entrypoint
    root = script.parent
    bootstrap = "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_path(sys.argv.pop(1),run_name='__main__')"
    return {
        "schema_version": SCHEMA, "manifest_digest": expected_digest,
        "argv": [manifest["runtime"]["executables"]["python"]["path"], "-I", "-S", "-B", "-c", bootstrap, str(root), str(script), *fixed_arguments],
        "environment": {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
        "cwd": str(bundle.absolute() / "tree"),
        "code_root": str(bundle.absolute() / "tree"), "member_write_admitted": False,
        "blocking_requirements": ["verified standard-library closure", "verified member-excluded native entrypoint"],
        "execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["materialize", "verify", "launch-contract"])
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--accepted-commit", required=True)
    parser.add_argument("--accepted-ref", required=True)
    parser.add_argument("--operation-id")
    parser.add_argument("--manifest-digest")
    parser.add_argument("--entrypoint")
    parser.add_argument("arguments", nargs="*")
    args = parser.parse_args(argv)
    try:
        if args.operation == "materialize":
            if args.manifest_digest is not None or args.entrypoint is not None or args.arguments:
                raise AuthorityError("materialize received arguments for another operation")
        elif args.operation == "verify":
            if args.operation_id is not None or args.entrypoint is not None or args.arguments:
                raise AuthorityError("verify received arguments for another operation")
        elif args.operation_id is not None:
            raise AuthorityError("launch-contract received arguments for another operation")
        if args.operation == "materialize":
            if args.operation_id is None:
                raise AuthorityError("materialization requires an operation identity")
            value = materialize(args.repository, args.bundle, args.accepted_commit, args.accepted_ref, args.operation_id)
        else:
            if args.manifest_digest is None:
                raise AuthorityError("verification requires the parent's manifest pin")
            if args.operation == "verify":
                verify_bundle(args.repository, args.bundle, args.accepted_commit, args.accepted_ref, args.manifest_digest)
                value = {"verified": True, "manifest_digest": args.manifest_digest, "member_write_admitted": False}
            else:
                if args.entrypoint is None:
                    raise AuthorityError("launch contract requires an exact entrypoint")
                value = launch_contract(args.repository, args.bundle, args.accepted_commit, args.accepted_ref, args.manifest_digest, args.entrypoint, args.arguments)
        print(json.dumps(value, sort_keys=True))
        return 0
    except (AuthorityError, OSError, subprocess.SubprocessError, UnicodeError) as error:
        print(f"parent authority refused: {error}", file=sys.stderr)
        return 1
