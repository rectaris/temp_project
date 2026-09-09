#!/usr/bin/env python3
"""Verify a candidate template ref against every recorded downstream baseline.

A release reaches three projects this repository does not control. Running the
verification skill against each recorded baseline before the tag exists moves the
discovery of a broken update from a downstream agent's session into this
repository's release step, where it can still be fixed.

Every baseline is reported. The command exits non-zero unless all of them verify,
so a release cannot proceed on a partially checked ref.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".codex/skills/verify-copier-update"
HELPER = SKILL / "scripts/verify-copier-update.py"
RESOLVER = SKILL / "scripts/triage-copier-update.py"
TABLE = SKILL / "references/update-triage.yaml"
BASELINES = ROOT / "docs/downstream-baselines.yaml"
SCHEMA_VERSION = 1
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SCP_REMOTE_RE = re.compile(r"^(?:[^/\s:@]+@)?([^/\s:@]+):(.+)$")
NETWORK_SCHEMES = ("git", "ssh", "http", "https")
DEFAULT_PORTS = {"ssh": (22,), "git": (9418,), "http": (80,), "https": (443,)}
ANSWERS_PATH = ".copier-answers.yml"


class BaselineError(Exception):
    """One bounded failure that leaves a release check unproven."""


@dataclass(frozen=True)
class Baseline:
    identifier: str
    path: Path
    remote: str
    baseline_ref: str
    template_commit: str
    validation_commands: tuple[tuple[str, ...], ...]


def canonical_remote(remote: str, base: Path | None = None) -> str:
    """Reduce the spellings of one repository address to a single comparable form.

    The same repository is written as an scp address and as an https URL depending on
    who cloned it, and either may carry the .git suffix, so the spelling alone must
    not decide that a checkout is the wrong project. Only the host is case-folded,
    because a path may distinguish two repositories by case. The login name is
    dropped: it authenticates the connection rather than naming the repository.

    An address that is not carried over the network names a directory, so it is
    resolved against the checkout that recorded it and compared as a path.
    """

    value = remote.strip().rstrip("/")
    matched = SCP_REMOTE_RE.match(value) if "://" not in value else None
    if matched:
        host, path = matched.group(1), matched.group(2)
    else:
        parsed = urlsplit(value)
        if parsed.scheme not in NETWORK_SCHEMES or not parsed.netloc:
            resolved = Path(value)
            if not resolved.is_absolute() and base is not None:
                resolved = base / resolved
            return f"path:{os.path.normpath(str(resolved))}"
        host = parsed.hostname or ""
        if parsed.port is not None and parsed.port not in DEFAULT_PORTS.get(parsed.scheme, ()):
            host = f"{host}:{parsed.port}"
        path = parsed.path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return f"repo:{host.lower()}/{path}"


def checkout_root() -> Path:
    """Return the directory the recorded relative paths are resolved against.

    A linked worktree sits outside the directory that holds the downstream checkouts,
    so the root is taken from the main worktree rather than from the directory this
    command happens to run in.
    """

    process = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        raise BaselineError("the main worktree could not be located")
    common = Path(process.stdout.strip())
    if common.name != ".git":
        raise BaselineError(f"the main worktree could not be located: {common}")
    return common.parent.parent


def load_baselines(path: Path, root: Path) -> tuple[str, list[Baseline]]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise BaselineError("reading the baseline record requires the YAML library") from exc
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineError(f"baseline record is unavailable: {exc}") from exc
    except yaml.YAMLError as exc:
        raise BaselineError(f"baseline record is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
        raise BaselineError(f"baseline record must declare schema_version {SCHEMA_VERSION}")
    template_remote = loaded.get("template_remote")
    if not isinstance(template_remote, str) or not template_remote.strip():
        raise BaselineError("baseline record must declare a non-empty template_remote")
    entries = loaded.get("baselines")
    if not isinstance(entries, list) or not entries:
        raise BaselineError("baseline record must declare a non-empty baselines list")
    baselines: list[Baseline] = []
    seen: set[str] = set()
    for entry in entries:
        baselines.append(require_baseline(entry, root, seen))
    return template_remote.strip(), baselines


def require_baseline(entry: object, root: Path, seen: set[str]) -> Baseline:
    if not isinstance(entry, dict):
        raise BaselineError("each baseline must be a mapping")
    identifier = entry.get("id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise BaselineError("each baseline must declare a non-empty id")
    if identifier in seen:
        raise BaselineError(f"baseline {identifier} is recorded more than once")
    seen.add(identifier)
    if not IDENTIFIER_RE.match(identifier):
        raise BaselineError(
            f"baseline id must be a lowercase name that is safe as a directory: {identifier}"
        )
    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise BaselineError(f"baseline {identifier} must declare a non-empty path")
    resolved = Path(raw_path)
    if not resolved.is_absolute():
        resolved = (root / resolved).resolve()
    required = {}
    for field in ("remote", "baseline_ref", "template_commit"):
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            raise BaselineError(f"baseline {identifier} must declare a non-empty {field}")
        required[field] = value.strip()
    commands = entry.get("validation_commands")
    if not isinstance(commands, list):
        raise BaselineError(
            f"baseline {identifier} must declare validation_commands as a list, empty only when"
            " the project has no command the isolated clone can run"
        )
    parsed: list[tuple[str, ...]] = []
    for command in commands:
        if not isinstance(command, list) or not command:
            raise BaselineError(f"baseline {identifier} declares an unusable validation command")
        if not all(isinstance(item, str) and item for item in command):
            raise BaselineError(f"baseline {identifier} declares a validation command with an empty entry")
        parsed.append(tuple(command))
    return Baseline(
        identifier,
        resolved,
        required["remote"],
        required["baseline_ref"],
        required["template_commit"],
        tuple(parsed),
    )


def require_candidate_source(template_remote: str) -> None:
    """Refuse to verify from a checkout that is not the recorded template repository.

    The runner substitutes this checkout for the source each project records, so a
    checkout of some other repository would silently verify every project against a
    template none of them uses.
    """

    process = subprocess.run(
        ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        raise BaselineError("this repository has no origin remote to verify from")
    if canonical_remote(process.stdout, ROOT) != canonical_remote(template_remote, ROOT):
        raise BaselineError(
            f"this repository tracks {process.stdout.strip()}, not the recorded "
            f"template_remote {template_remote}"
        )


def load_resolver():
    try:
        return SourceFileLoader("triage_copier_update", str(RESOLVER)).load_module()
    except Exception as exc:  # noqa: BLE001 - reported as one bounded failure
        raise BaselineError(f"triage resolver is unavailable: {exc}") from exc


def blocked(baseline: Baseline, code: str, owner: str, action: str) -> dict[str, object]:
    return {
        "baseline": baseline.identifier,
        "result": "blocked",
        "reason_code": code,
        "owner": owner,
        "next_action": action,
    }


def git(baseline: Baseline, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(baseline.path), *arguments],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def check_record(baseline: Baseline, template_remote: str) -> tuple[str, dict[str, object] | None]:
    """Resolve the baseline to one immutable commit the record actually describes.

    A record that names the wrong repository, an absent ref or a template the project
    has since left would let a release report itself checked against baselines it
    never touched. The ref is resolved once and every later step uses that commit, so
    a branch that moves during the run cannot separate what was checked from what was
    verified.
    """

    if not baseline.path.is_dir():
        return "", blocked(
            baseline,
            "baseline_checkout_unavailable",
            "environment",
            f"Check out {baseline.identifier} at {baseline.path}, then run this again.",
        )
    origin = git(baseline, "remote", "get-url", "origin")
    if origin.returncode != 0:
        return "", blocked(
            baseline,
            "baseline_remote_unavailable",
            "environment",
            f"Give {baseline.path} an origin remote, or correct its recorded path.",
        )
    if canonical_remote(origin.stdout, baseline.path) != canonical_remote(
        baseline.remote, baseline.path
    ):
        return "", blocked(
            baseline,
            "baseline_remote_mismatch",
            "project",
            f"{baseline.path} tracks {origin.stdout.strip()}, not the recorded "
            f"{baseline.remote}. Correct the record or the checkout.",
        )
    resolved = git(baseline, "rev-parse", "--verify", "--quiet", f"{baseline.baseline_ref}^{{commit}}")
    if resolved.returncode != 0 or not resolved.stdout.strip():
        return "", blocked(
            baseline,
            "baseline_ref_unavailable",
            "project",
            f"{baseline.path} has no commit at {baseline.baseline_ref}. "
            "Fetch that ref or correct the record.",
        )
    commit = resolved.stdout.strip()
    answers = git(baseline, "show", f"{commit}:{ANSWERS_PATH}")
    if answers.returncode != 0:
        return commit, blocked(
            baseline,
            "baseline_answers_unavailable",
            "project",
            f"{baseline.identifier} has no {ANSWERS_PATH} at {commit}. "
            "The project is not Copier-managed at its recorded baseline.",
        )
    try:
        recorded = recorded_answers(answers.stdout)
    except BaselineError as exc:
        return commit, blocked(baseline, "baseline_answers_invalid", "project", str(exc))
    if recorded["_commit"] != baseline.template_commit:
        return commit, blocked(
            baseline,
            "baseline_template_commit_mismatch",
            "project",
            f"{baseline.identifier} records template version {recorded['_commit']!r} at "
            f"{baseline.baseline_ref}, not the recorded {baseline.template_commit!r}. "
            "Update docs/downstream-baselines.yaml to the version it actually holds.",
        )
    if canonical_remote(recorded["_src_path"], baseline.path) != canonical_remote(
        template_remote, baseline.path
    ):
        return commit, blocked(
            baseline,
            "baseline_template_source_mismatch",
            "project",
            f"{baseline.identifier} is generated from {recorded['_src_path']!r}, not from "
            f"{template_remote!r}. Verifying it against this repository would substitute "
            "a template the project does not use.",
        )
    return commit, None


def recorded_answers(blob: str) -> dict[str, str]:
    """Read the two recorded values a baseline check depends on, as Copier reads them."""

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise BaselineError("reading a project's answers requires the YAML library") from exc
    try:
        loaded = yaml.safe_load(blob)
    except yaml.YAMLError as exc:
        raise BaselineError(f"{ANSWERS_PATH} is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise BaselineError(f"{ANSWERS_PATH} must hold a mapping")
    recorded = {}
    for field in ("_commit", "_src_path"):
        value = loaded.get(field)
        if not isinstance(value, str) or not value.strip():
            raise BaselineError(f"{ANSWERS_PATH} must record a non-empty {field}")
        recorded[field] = value.strip()
    return recorded


def verify(
    baseline: Baseline, source_ref: str, output: Path, template_remote: str
) -> dict[str, object]:
    """Run one isolated verification and resolve its outcome, without raising."""

    commit, refused = check_record(baseline, template_remote)
    if refused is not None:
        return refused
    command = [
        sys.executable,
        str(HELPER),
        "--target",
        str(baseline.path),
        "--target-ref",
        commit,
        "--source",
        str(ROOT),
        "--source-ref",
        source_ref,
        "--output-dir",
        str(output),
        "--trust-template-tasks",
    ]
    for validation in baseline.validation_commands:
        command.extend(["--validation-command-json", json.dumps(list(validation))])
    if not baseline.validation_commands:
        command.append("--declare-no-project-validation")
    subprocess.run(command, cwd=ROOT, check=False)
    manifest = output / "verification-manifest.json"
    if not manifest.is_file():
        return blocked(
            baseline,
            "verification_manifest_missing",
            "environment",
            f"Inspect {output} for why the verification helper recorded no manifest.",
        )
    resolved = subprocess.run(
        [sys.executable, str(RESOLVER), str(manifest), "--triage-table", str(TABLE), "--format", "json"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if resolved.returncode == 2:
        return blocked(
            baseline,
            "triage_unresolved",
            "undetermined",
            resolved.stderr.strip() or "The manifest could not be resolved.",
        )
    report = json.loads(resolved.stdout)
    report["baseline"] = baseline.identifier
    return report


def render(reports: list[dict[str, object]]) -> str:
    lines = []
    for report in reports:
        lines.append(
            f"{report['baseline']}: {report['result']} ({report['reason_code']}) "
            f"owner={report['owner']}"
        )
        if report["result"] != "verified" or report.get("residual_obligation"):
            lines.append(f"  next_action: {report['next_action']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source-ref", required=True, help="the candidate template ref to verify")
    parser.add_argument("--output-dir", required=True, type=Path, help="an unused evidence directory")
    parser.add_argument("--baselines", type=Path, default=BASELINES)
    parser.add_argument("--only", action="append", default=[], help="verify one recorded baseline")
    parser.add_argument(
        "--checkout-root",
        type=Path,
        default=None,
        help="the directory recorded relative paths resolve against",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        root = args.checkout_root.resolve() if args.checkout_root else checkout_root()
        template_remote, baselines = load_baselines(args.baselines, root)
        require_candidate_source(template_remote)
        load_resolver()
    except BaselineError as exc:
        print(f"downstream verification failed: {exc}", file=sys.stderr)
        return 2

    if args.only:
        recorded = {baseline.identifier for baseline in baselines}
        unknown = sorted(set(args.only) - recorded)
        if unknown:
            print(f"downstream verification failed: unrecorded baseline: {', '.join(unknown)}", file=sys.stderr)
            return 2
        baselines = [baseline for baseline in baselines if baseline.identifier in set(args.only)]

    output = args.output_dir
    if output.exists():
        print(f"downstream verification failed: output directory already exists: {output}", file=sys.stderr)
        return 2
    try:
        output.mkdir(mode=0o700, parents=True)
    except OSError as exc:
        print(f"downstream verification failed: output directory is unusable: {exc}", file=sys.stderr)
        return 2

    reports = [
        verify(baseline, args.source_ref, output / baseline.identifier, template_remote)
        for baseline in baselines
    ]

    if args.format == "json":
        print(json.dumps(reports, indent=2, sort_keys=True))
    else:
        print(render(reports))
    return 0 if all(report["result"] == "verified" for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
