#!/usr/bin/env python3
"""Apply the root external-service policy before delegating to the maintained checker."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs/agent/external-services.yaml"
MAINTAINED_CHECKER = ROOT / "template/.project-agent-workflow/scripts/check-external-service-policy.py"
GITHUB_REPOSITORY = "rectaris/temp_project"
GITHUB_WRITE_EFFECTS = {
    "git.push": "ordinary",
    "pull_request.publish": "public_communication",
    "release.publish": "public_communication",
}
BRANCH_PREFIX = "refs/heads/"
TAG_PREFIX = "refs/tags/"


class RootPolicyError(ValueError):
    pass


def require_nonblank(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise RootPolicyError(f"{label} must not be empty or whitespace-only")
    return value


def reject_option_like(value: str, label: str) -> None:
    if value.lstrip().startswith("-"):
        raise RootPolicyError(f"{label} must not be option-like")


def validate_git_ref_component(component: str, *, ref_kind: str, label: str) -> None:
    if not component:
        raise RootPolicyError(f"{label} must not be empty")
    if ref_kind == "branch":
        command = ["git", "check-ref-format", "--branch", component]
    elif ref_kind == "tag":
        command = ["git", "check-ref-format", f"{TAG_PREFIX}{component}"]
    else:
        raise RootPolicyError(f"unsupported Git ref kind: {ref_kind}")
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        raise RootPolicyError(f"could not run Git ref validation for {label}: {exc}") from exc
    if result.returncode != 0:
        raise RootPolicyError(f"invalid {label} Git ref component: {component}")


def validate_branch_endpoint(endpoint: str, *, label: str) -> None:
    if not endpoint.startswith(BRANCH_PREFIX):
        raise RootPolicyError(f"{label} must use the refs/heads/ form")
    validate_git_ref_component(
        endpoint[len(BRANCH_PREFIX) :],
        ref_kind="branch",
        label=label,
    )


def validate_github_target(operation: str, target: str) -> None:
    repository, delimiter, descriptor = target.partition(":")
    if delimiter != ":" or repository != GITHUB_REPOSITORY:
        raise RootPolicyError(
            f"{operation} target must use repository {GITHUB_REPOSITORY} and one delimiter after owner/repository"
        )

    if operation == "git.push":
        if descriptor.startswith(BRANCH_PREFIX):
            validate_git_ref_component(
                descriptor[len(BRANCH_PREFIX) :],
                ref_kind="branch",
                label="git.push branch",
            )
            return
        if descriptor.startswith(TAG_PREFIX):
            validate_git_ref_component(
                descriptor[len(TAG_PREFIX) :],
                ref_kind="tag",
                label="git.push tag",
            )
            return
        raise RootPolicyError("git.push target must use refs/heads/<branch> or refs/tags/<tag>")

    if operation == "pull_request.publish":
        endpoints = descriptor.split("->")
        if len(endpoints) != 2:
            raise RootPolicyError("pull_request.publish target must have one head-to-base separator")
        validate_branch_endpoint(endpoints[0], label="pull-request head")
        validate_branch_endpoint(endpoints[1], label="pull-request base")
        return

    if operation == "release.publish":
        release_prefix = "release:"
        if not descriptor.startswith(release_prefix):
            raise RootPolicyError("release.publish target must use release:<tag>")
        validate_git_ref_component(
            descriptor[len(release_prefix) :],
            ref_kind="tag",
            label="release tag",
        )
        return

    raise RootPolicyError(f"unsupported GitHub release operation: {operation}")


def validate_authorize_request(args: argparse.Namespace) -> None:
    require_nonblank(args.service, "service")
    require_nonblank(args.operation, "operation")
    reject_option_like(args.service, "service")
    reject_option_like(args.operation, "operation")
    target = require_nonblank(args.target, "target")
    if not args.effect:
        raise RootPolicyError("authorize requires at least one effect")
    if len(args.effect) != len(set(args.effect)):
        raise RootPolicyError("authorize effects must not be duplicated")
    if args.confirmed_effect and len(args.confirmed_effect) != len(set(args.confirmed_effect)):
        raise RootPolicyError("confirmed effects must not be duplicated")

    expected_effect = GITHUB_WRITE_EFFECTS.get(args.operation)
    if expected_effect is None:
        return
    if args.access != "write":
        raise RootPolicyError(f"{args.operation} is a write operation")
    if args.service != "github":
        raise RootPolicyError(f"{args.operation} requires provider github")
    if args.effect != [expected_effect]:
        raise RootPolicyError(
            f"{args.operation} requires the exact effect classification: {expected_effect}"
        )
    validate_github_target(args.operation, target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", add_help=False, allow_abbrev=False)
    authorize_parser = subparsers.add_parser("authorize", add_help=False, allow_abbrev=False)
    authorize_parser.add_argument("service")
    authorize_parser.add_argument("access", choices=("read", "write"))
    authorize_parser.add_argument("operation")
    authorize_parser.add_argument("--authorization-rule")
    authorize_parser.add_argument("--provider-configured", action="store_true")
    authorize_parser.add_argument("--task-authorized", action="store_true")
    authorize_parser.add_argument("--target")
    authorize_parser.add_argument("--effect", action="append")
    authorize_parser.add_argument("--confirmed-target")
    authorize_parser.add_argument("--confirmed-effect", action="append")
    return parser


def delegate(argv: list[str]) -> int:
    delegated = [
        sys.executable,
        str(MAINTAINED_CHECKER),
        "--policy",
        str(POLICY),
        *argv,
    ]
    result = subprocess.run(delegated, cwd=ROOT, check=False)
    return result.returncode


def reconstruct(args: argparse.Namespace) -> list[str]:
    delegated = ["check"] if args.command == "check" else [
        "authorize",
        args.service,
        args.access,
        args.operation,
    ]
    if args.command != "authorize":
        return delegated
    if args.authorization_rule is not None:
        delegated.extend(["--authorization-rule", args.authorization_rule])
    if args.provider_configured:
        delegated.append("--provider-configured")
    if args.task_authorized:
        delegated.append("--task-authorized")
    delegated.extend(["--target", args.target])
    for effect in args.effect:
        delegated.extend(["--effect", effect])
    if args.confirmed_target is not None:
        delegated.extend(["--confirmed-target", args.confirmed_target])
    for effect in args.confirmed_effect or []:
        delegated.extend(["--confirmed-effect", effect])
    return delegated


def main(argv: list[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "authorize":
            validate_authorize_request(args)
        return delegate(reconstruct(args))
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return code if code != 0 else 2
    except (OSError, RootPolicyError) as exc:
        print(f"root external-service policy error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
