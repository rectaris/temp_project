#!/usr/bin/env python3
"""Resolve abstract worker capabilities to the backend that implements them.

The parent orchestrator asks for a capability, such as `plan_implementation`
or `repository_exploration`, instead of naming a provider. The managed
Capability Registry maps each capability to an ordered list of
implementations, and the first entry is the resolution. Every capability
resolves to Codex today: `plan_implementation` to the sandboxed plan runner and
every other capability to an existing `.codex/agents` profile.

The registry names profiles only. It never stores a model, a reasoning value or
an instruction, and it never writes a profile, because those files stay
project-owned.

`WorkerBackend` is the launch boundary below the runner. The runner keeps its
sandbox, environment, fallback, receipt, manifest and validation code and asks
the resolved backend only for the command of one attempt. `CodexBackend` builds
exactly the Codex command the runner built before this boundary existed.

The module is written for two layouts, so it imports nothing from its siblings
and the root and generated copies stay byte-identical.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


REGISTRY_SCHEMA_VERSION = 1
REGISTRY_MAX_BYTES = 65_536
REGISTRY_RELATIVE_PATH = "docs/agent/capability-registry.json"
READ_ONLY = "read_only"
WRITABLE = "writable"
CAPABILITY_ACCESS = (
    ("repository_exploration", READ_ONLY),
    ("bounded_implementation", WRITABLE),
    ("plan_implementation", WRITABLE),
    ("evidence_synthesis", READ_ONLY),
    ("documentation_research", READ_ONLY),
    ("deep_review", READ_ONLY),
)
PLAN_IMPLEMENTATION = "plan_implementation"
CODEX_BACKEND_ID = "codex"
SANDBOXED_RUNNER = "sandboxed_runner"
NATIVE_PROFILE = "native_profile"
MAX_IMPLEMENTATIONS = 8
MAX_PROFILES = 8
PROFILE_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}")
O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


class RegistryError(ValueError):
    """Raised when the Capability Registry cannot be read, parsed or resolved."""


@dataclass(frozen=True)
class Implementation:
    """One way to perform a capability."""

    backend: str
    kind: str
    profiles: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"backend": self.backend, "kind": self.kind}
        if self.kind == NATIVE_PROFILE:
            record["profiles"] = list(self.profiles)
        return record


# Schema version 1 admits exactly one implementation table. Each read-only
# capability names only read-only profiles and each writable capability only
# its own writers, so a registry edit can never widen what a capability may do.
SCHEMA_V1_IMPLEMENTATIONS = {
    "repository_exploration": (
        Implementation(CODEX_BACKEND_ID, NATIVE_PROFILE, ("repo_explorer",)),
    ),
    "bounded_implementation": (
        Implementation(CODEX_BACKEND_ID, NATIVE_PROFILE, ("fast_scoped_worker", "scoped_worker")),
    ),
    "plan_implementation": (Implementation(CODEX_BACKEND_ID, SANDBOXED_RUNNER),),
    "evidence_synthesis": (
        Implementation(CODEX_BACKEND_ID, NATIVE_PROFILE, ("evidence_synthesizer",)),
    ),
    "documentation_research": (
        Implementation(CODEX_BACKEND_ID, NATIVE_PROFILE, ("docs_researcher",)),
    ),
    "deep_review": (
        Implementation(CODEX_BACKEND_ID, NATIVE_PROFILE, ("change_reviewer",)),
    ),
}


@dataclass(frozen=True)
class Capability:
    """One abstract capability and its ordered implementations."""

    identifier: str
    access: str
    implementations: tuple[Implementation, ...]


def exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"{label} must be a JSON object")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        unknown = sorted(set(value) - keys)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unknown:
            detail.append("unknown " + ", ".join(unknown))
        raise RegistryError(f"{label} has invalid keys: {'; '.join(detail)}")
    return value


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"capability registry repeats the key {key!r}")
        result[key] = value
    return result


def parse_implementation(value: Any, capability: str, index: int) -> Implementation:
    label = f"capability {capability} implementation {index}"
    if not isinstance(value, dict):
        raise RegistryError(f"{label} must be a JSON object")
    kind = value.get("kind")
    if kind == SANDBOXED_RUNNER:
        record = exact_keys(value, {"backend", "kind"}, label)
        profiles: tuple[str, ...] = ()
    elif kind == NATIVE_PROFILE:
        record = exact_keys(value, {"backend", "kind", "profiles"}, label)
        raw_profiles = record["profiles"]
        if (
            not isinstance(raw_profiles, list)
            or not raw_profiles
            or len(raw_profiles) > MAX_PROFILES
        ):
            raise RegistryError(f"{label} profiles must be a non-empty bounded list")
        if any(
            not isinstance(profile, str) or PROFILE_PATTERN.fullmatch(profile) is None
            for profile in raw_profiles
        ):
            raise RegistryError(f"{label} names a malformed profile")
        if len(set(raw_profiles)) != len(raw_profiles):
            raise RegistryError(f"{label} repeats a profile")
        profiles = tuple(raw_profiles)
    else:
        raise RegistryError(f"{label} declares an unknown kind: {kind!r}")
    backend = record["backend"]
    if backend != CODEX_BACKEND_ID:
        raise RegistryError(f"{label} declares an unknown backend: {backend!r}")
    if (kind == SANDBOXED_RUNNER) != (capability == PLAN_IMPLEMENTATION):
        raise RegistryError(
            f"{label}: only {PLAN_IMPLEMENTATION} runs through the sandboxed runner, "
            "and it runs through nothing else"
        )
    return Implementation(backend=backend, kind=kind, profiles=profiles)


def parse_registry(raw: bytes) -> dict[str, Capability]:
    """Return the capabilities of one exact registry document, in registry order."""

    if len(raw) > REGISTRY_MAX_BYTES:
        raise RegistryError(f"capability registry exceeds {REGISTRY_MAX_BYTES} bytes")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"capability registry is not UTF-8 JSON: {exc}") from exc
    document = exact_keys(document, {"schema_version", "capabilities"}, "capability registry")
    version = document["schema_version"]
    if type(version) is not int or version != REGISTRY_SCHEMA_VERSION:
        raise RegistryError(
            f"capability registry schema_version must be {REGISTRY_SCHEMA_VERSION}"
        )
    entries = document["capabilities"]
    if not isinstance(entries, list):
        raise RegistryError("capability registry capabilities must be a list")
    expected = [identifier for identifier, _ in CAPABILITY_ACCESS]
    actual = [entry.get("id") if isinstance(entry, dict) else None for entry in entries]
    if actual != expected:
        raise RegistryError(
            "capability registry must declare exactly these capabilities in order: "
            + ", ".join(expected)
        )
    capabilities: dict[str, Capability] = {}
    for entry, (identifier, access) in zip(entries, CAPABILITY_ACCESS):
        label = f"capability {identifier}"
        record = exact_keys(entry, {"id", "access", "implementations"}, label)
        if record["access"] != access:
            raise RegistryError(f"{label} access must be {access}")
        raw_implementations = record["implementations"]
        if (
            not isinstance(raw_implementations, list)
            or not raw_implementations
            or len(raw_implementations) > MAX_IMPLEMENTATIONS
        ):
            raise RegistryError(f"{label} implementations must be a non-empty bounded list")
        implementations = tuple(
            parse_implementation(item, identifier, index)
            for index, item in enumerate(raw_implementations, start=1)
        )
        if len(set(implementations)) != len(implementations):
            raise RegistryError(f"{label} repeats an implementation")
        if implementations != SCHEMA_V1_IMPLEMENTATIONS[identifier]:
            raise RegistryError(
                f"{label} implementations differ from the schema-version "
                f"{REGISTRY_SCHEMA_VERSION} table"
            )
        capabilities[identifier] = Capability(
            identifier=identifier, access=access, implementations=implementations
        )
    return capabilities


def read_registry_bytes(path: Path) -> bytes:
    """Read one bounded regular registry file through no symlink and no special file.

    Every path component is opened relative to its parent directory without
    following a symlink, and the final component is opened without blocking,
    so a symlinked ancestor, a FIFO or a device refuses instead of redirecting
    or stalling the read.
    """

    parts = Path(os.path.abspath(path)).parts
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | O_CLOEXEC
    try:
        directory = os.open(parts[0], directory_flags)
    except OSError as exc:
        raise RegistryError(f"capability registry cannot be opened safely: {path}: {exc}") from exc
    try:
        for part in parts[1:-1]:
            try:
                child = os.open(part, directory_flags, dir_fd=directory)
            except FileNotFoundError as exc:
                raise RegistryError(f"capability registry is missing: {path}") from exc
            except OSError as exc:
                raise RegistryError(
                    f"capability registry cannot be opened safely: {path}: {exc}"
                ) from exc
            os.close(directory)
            directory = child
        try:
            descriptor = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | O_CLOEXEC,
                dir_fd=directory,
            )
        except FileNotFoundError as exc:
            raise RegistryError(f"capability registry is missing: {path}") from exc
        except OSError as exc:
            raise RegistryError(
                f"capability registry cannot be opened safely: {path}: {exc}"
            ) from exc
    finally:
        os.close(directory)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RegistryError(f"capability registry is not a regular file: {path}")
        if metadata.st_size > REGISTRY_MAX_BYTES:
            raise RegistryError(f"capability registry exceeds {REGISTRY_MAX_BYTES} bytes")
        chunks: list[bytes] = []
        remaining = REGISTRY_MAX_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def load_registry(path: Path) -> dict[str, Capability]:
    return parse_registry(read_registry_bytes(path))


def resolve(registry: dict[str, Capability], capability: str) -> Implementation:
    """Return the implementation that performs one declared capability."""

    entry = registry.get(capability)
    if entry is None:
        raise RegistryError(f"unknown capability: {capability!r}")
    return entry.implementations[0]


class WorkerBackend:
    """The launch boundary for one sandboxed plan-runner attempt."""

    backend_id = ""

    def command(
        self,
        *,
        executable: str,
        clone_dir: Path,
        last_message_path: Path,
        model: str,
        reasoning: str,
    ) -> list[str]:
        raise NotImplementedError


class CodexBackend(WorkerBackend):
    """Build the Codex CLI command the sandboxed runner executes inside Bubblewrap.

    Bubblewrap supplies the isolation, so Codex's own sandbox and approvals
    are bypassed and user configuration is ignored.
    """

    backend_id = CODEX_BACKEND_ID

    def command(
        self,
        *,
        executable: str,
        clone_dir: Path,
        last_message_path: Path,
        model: str,
        reasoning: str,
    ) -> list[str]:
        return [
            executable,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ignore-user-config",
            "--ephemeral",
            "--model",
            model,
            "--skip-git-repo-check",
            "--color",
            "never",
            "--cd",
            str(clone_dir),
            "--config",
            f'model_reasoning_effort="{reasoning}"',
            "--output-last-message",
            str(last_message_path),
            "-",
        ]


RUNNER_BACKENDS: dict[str, type[WorkerBackend]] = {CODEX_BACKEND_ID: CodexBackend}


def runner_backend(implementation: Implementation) -> WorkerBackend:
    """Return the sandboxed-runner backend for one resolved implementation."""

    if implementation.kind != SANDBOXED_RUNNER:
        raise RegistryError(
            f"{PLAN_IMPLEMENTATION} must resolve to the sandboxed runner, not {implementation.kind}"
        )
    backend = RUNNER_BACKENDS.get(implementation.backend)
    if backend is None:
        raise RegistryError(f"no sandboxed-runner backend is available for {implementation.backend!r}")
    return backend()


def resolve_plan_implementation(registry_path: Path) -> WorkerBackend:
    """Resolve plan_implementation from one registry file to its runner backend."""

    return runner_backend(resolve(load_registry(registry_path), PLAN_IMPLEMENTATION))


def default_registry_path() -> Path:
    """Return the registry beside this module in the root or the generated layout."""

    here = Path(__file__).resolve().parent
    if here.name == "project_workflow":
        return here.parent.parent / REGISTRY_RELATIVE_PATH
    return here.parent / REGISTRY_RELATIVE_PATH


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subcommands = parser.add_subparsers(dest="command", required=True)
    resolve_parser = subcommands.add_parser(
        "resolve", help="print the resolution of one capability as JSON"
    )
    resolve_parser.add_argument("capability")
    args = parser.parse_args(argv)
    try:
        registry = load_registry(default_registry_path())
        implementation = resolve(registry, args.capability)
    except RegistryError as exc:
        print(f"capability resolution failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "capability": args.capability,
                "access": registry[args.capability].access,
                "implementation": implementation.as_record(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
