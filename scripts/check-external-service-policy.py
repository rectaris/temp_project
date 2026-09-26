#!/usr/bin/env python3
"""Apply the root external-service policy before delegating to the maintained checker."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import stringprep
import sys
from typing import NoReturn
import unicodedata
from urllib.parse import unquote


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
TYPESAFE_SERVICE = "typesafe"
TYPESAFE_OPERATION = "decision.evaluate"
TYPESAFE_HOST = "typesafe.ai"
TYPESAFE_TARGET_FORM = "https://api.typesafe.ai/v1/systemone#model=jev-<MAJOR>.<MINOR>.<PATCH>"
TYPESAFE_TARGET = re.compile(
    r"https://api\.typesafe\.ai/v1/systemone#model=jev-"
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
)
IDEOGRAPHIC_DOTS = str.maketrans({"\u3002": "."})
IGNORED_CATEGORIES = frozenset(
    {"Cc", "Cf", "Cn", "Co", "Cs", "Mc", "Me", "Mn", "Zl", "Zp", "Zs"}
)
HANGUL_FILLERS = frozenset({"\u115f", "\u1160", "\u3164", "\uffa0"})
SPECIAL_NETWORK_SCHEMES = frozenset({"ftp", "http", "https", "ws", "wss"})
LIBCURL_SLASH_TOLERANT_SCHEMES = frozenset(
    {
        "dict", "ftps", "gopher", "gophers", "imap", "imaps", "ldap", "ldaps",
        "mqtt", "pop3", "pop3s", "rtmp", "rtmpe", "rtmps", "rtmpt", "rtmpte",
        "rtmpts", "rtsp", "scp", "sftp", "smb", "smbs", "smtp", "smtps",
        "telnet", "tftp",
    }
)
URL_SLASHES = "/\\"
URL_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
AUTHORITY_END = re.compile(r"[/?#]")
HOST_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
CANONICAL_HOST = re.compile(rf"{HOST_LABEL}(?:\.{HOST_LABEL})*")
CANONICAL_AUTHORITY = re.compile(
    r"(?:[A-Za-z0-9._~!$&'()*+,;=:-]*@)?"
    rf"(?:(?P<host>(?:{CANONICAL_HOST.pattern})?)|\[(?P<ipv6>[0-9A-Fa-f:.]+)\])"
    r"(?::[0-9]{1,5})?"
)
URL_STRIPPED_WHITESPACE = frozenset({"\t", "\n", "\r"})
CREDENTIAL_ENVIRONMENT_PREFIX = "TYPESAFE_"
PARSE_ERROR = "root external-service policy error: invalid arguments\n"


class RootPolicyError(ValueError):
    pass


class RootArgumentParser(argparse.ArgumentParser):
    """Report parse failures with fixed wording instead of echoing arguments."""

    def error(self, message: str) -> NoReturn:
        self.exit(2, PARSE_ERROR)


class SingleValueAction(argparse.Action):
    """Refuse a repeated option instead of silently keeping its last value."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        if getattr(namespace, self.dest) is not None:
            parser.error("repeated single-value option")
        setattr(namespace, self.dest, values)


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


def routing_form(value: str) -> str:
    """Fold every spelling of a service or operation name to one routing form.

    The fold percent-decodes until the text is stable, applies compatibility
    normalization, case folding, and compatibility normalization again, maps
    the ideographic full stop to a dot, and drops control, format, surrogate,
    private-use, unassigned, mark, separator, and Hangul filler
    characters together with every character that IDNA2003 nameprep maps to
    nothing (RFC 3454 table B.1). A wider fold can only route more requests
    into the fixed TypeSafe tuple check, never fewer.
    """

    # Each decoding round that changes the text shortens it, so the loop ends.
    decoded = value
    while (next_value := unquote(decoded)) != decoded:
        decoded = next_value
    folded = unicodedata.normalize("NFKC", decoded).casefold()
    folded = unicodedata.normalize("NFKC", folded).translate(IDEOGRAPHIC_DOTS)
    return "".join(
        character
        for character in folded
        if unicodedata.category(character) not in IGNORED_CATEGORIES
        and character not in HANGUL_FILLERS
        and not stringprep.in_table_b1(character)
    )


def target_authority(target: str) -> tuple[str, bool] | None:
    """Return the URL authority a client would connect to and whether it needs a host.

    A scheme follows the RFC 3986 grammar. The special network schemes and a
    scheme-relative target, one that begins with two slashes or backslashes,
    skip every leading slash and backslash and need a host, as the WHATWG URL
    parser does. A file target has an authority after two leading slashes or
    backslashes. Another libcurl protocol scheme followed by at least one
    slash or backslash skips all of them, because libcurl reads
    `gopher:/host` and `gopher:///host` as `gopher://host`; every other
    scheme has an authority only after `//`, as RFC 3986 and the WHATWG URL
    parser read it. The authority ends at the first slash, question mark, or
    number sign, so a backslash stays inside it and fails the canonical
    check. Return None when the target has no URL authority.
    """

    scheme = URL_SCHEME.match(target)
    if scheme is not None:
        name = scheme.group()[:-1].lower()
        rest = target[scheme.end() :]
        if name in SPECIAL_NETWORK_SCHEMES:
            return AUTHORITY_END.split(rest.lstrip(URL_SLASHES), maxsplit=1)[0], True
        if name == "file":
            if len(rest) < 2 or rest[0] not in URL_SLASHES or rest[1] not in URL_SLASHES:
                return None
            return AUTHORITY_END.split(rest[2:], maxsplit=1)[0], False
        if name in LIBCURL_SLASH_TOLERANT_SCHEMES:
            if not rest or rest[0] not in URL_SLASHES:
                return None
            return AUTHORITY_END.split(rest.lstrip(URL_SLASHES), maxsplit=1)[0], False
        if not rest.startswith("//"):
            return None
        return AUTHORITY_END.split(rest[2:], maxsplit=1)[0], False
    if len(target) >= 2 and target[0] in URL_SLASHES and target[1] in URL_SLASHES:
        return AUTHORITY_END.split(target.lstrip(URL_SLASHES), maxsplit=1)[0], True
    return None


def command_line_host(target: str) -> str | None:
    """Return the host a command-line client would guess from a target's leading token.

    A client such as curl reads a target without `scheme://` as
    `[userinfo@]host[:port]` in its leading token, so `x:secret@host` and
    `host:443/v1` both name `host`. Take the text after the last `@` and
    before the first `:` of the leading token. Return it only when the token
    contains no whitespace and the name fold of that text contains a dot, so
    an ideographic, full-width, or percent-encoded dot still yields a guessed
    host that the canonical check then refuses. For a URL with an authority
    the leading token is only the scheme, so the guess adds nothing there.
    """

    token = AUTHORITY_END.split(target, maxsplit=1)[0]
    if any(character.isspace() for character in token):
        return None
    host = token.rpartition("@")[2].partition(":")[0]
    return host if "." in routing_form(host) else None


def names_typesafe_host(target: str) -> bool:
    """Require canonical ASCII hosts and report whether either reading names TypeSafe.

    A target is read both as a URL and as a command-line client would read
    it, because `api.example.com:/v1` is a URL with a dotted scheme to one
    parser and a host with an empty port to another. Every host either
    reading finds must be canonical, and the target names TypeSafe when
    either host does.
    """

    if (
        URL_STRIPPED_WHITESPACE & set(target)
        or target[0] <= " "
        or target[-1] <= " "
    ):
        raise RootPolicyError(
            "external-service target must not contain tab or line-break characters "
            "or begin or end with a control or space character"
        )
    hosts: list[str] = []
    found = target_authority(target)
    if found is not None:
        authority, host_required = found
        canonical = CANONICAL_AUTHORITY.fullmatch(authority)
        if canonical is None or not canonical_host(canonical, host_required):
            raise RootPolicyError("external-service target authority must use a canonical ASCII host")
        hosts.append((canonical.group("host") or "").lower())
    guessed = command_line_host(target)
    if guessed is not None:
        if CANONICAL_HOST.fullmatch(guessed) is None:
            raise RootPolicyError("external-service target authority must use a canonical ASCII host")
        hosts.append(guessed.lower())
    return any(host == TYPESAFE_HOST or host.endswith("." + TYPESAFE_HOST) for host in hosts)


def canonical_host(canonical: re.Match[str], host_required: bool) -> bool:
    literal = canonical.group("ipv6")
    if literal is not None:
        try:
            ipaddress.IPv6Address(literal)
        except ValueError:
            return False
        return True
    return bool(canonical.group("host")) or not host_required


def is_typesafe_request(args: argparse.Namespace) -> bool:
    typesafe_host = names_typesafe_host(args.target)
    return (
        typesafe_host
        or routing_form(args.service) == TYPESAFE_SERVICE
        or routing_form(args.operation) == TYPESAFE_OPERATION
    )


def validate_typesafe_request(args: argparse.Namespace) -> None:
    """Admit only the fixed TypeSafe read tuple.

    Diagnostics use fixed wording and never echo a caller-supplied value, so a
    credential placed in a target or operation cannot reach an error message.
    """

    if args.service != TYPESAFE_SERVICE:
        raise RootPolicyError("TypeSafe decisions require provider typesafe")
    if args.operation != TYPESAFE_OPERATION:
        raise RootPolicyError("typesafe admits only operation decision.evaluate")
    if args.access != "read":
        raise RootPolicyError("typesafe decision.evaluate is a read operation")
    if args.effect != ["ordinary"]:
        raise RootPolicyError("typesafe decision.evaluate requires the exact effect classification: ordinary")
    if not args.provider_configured:
        raise RootPolicyError("typesafe authorization requires a configured and authenticated provider")
    if not args.task_authorized:
        raise RootPolicyError(
            "typesafe authorization requires the current user request to authorize the exact operation"
        )
    if (
        args.authorization_rule is not None
        or args.confirmed_target is not None
        or args.confirmed_effect
    ):
        raise RootPolicyError("typesafe reads take no authorization rule or confirmation")
    if not TYPESAFE_TARGET.fullmatch(args.target):
        raise RootPolicyError(f"typesafe target must be exactly {TYPESAFE_TARGET_FORM}")


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

    if is_typesafe_request(args):
        validate_typesafe_request(args)
        return

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
    parser = RootArgumentParser(add_help=False, allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", add_help=False, allow_abbrev=False)
    authorize_parser = subparsers.add_parser("authorize", add_help=False, allow_abbrev=False)
    authorize_parser.add_argument("service")
    authorize_parser.add_argument("access", choices=("read", "write"))
    authorize_parser.add_argument("operation")
    authorize_parser.add_argument("--authorization-rule", action=SingleValueAction)
    authorize_parser.add_argument("--provider-configured", action="store_true")
    authorize_parser.add_argument("--task-authorized", action="store_true")
    authorize_parser.add_argument("--target", action=SingleValueAction)
    authorize_parser.add_argument("--effect", action="append")
    authorize_parser.add_argument("--confirmed-target", action=SingleValueAction)
    authorize_parser.add_argument("--confirmed-effect", action="append")
    return parser


def maintained_checker_environment() -> dict[str, str]:
    """Pass the parent environment without any TypeSafe credential variable."""

    return {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(CREDENTIAL_ENVIRONMENT_PREFIX)
    }


def delegate(argv: list[str]) -> int:
    delegated = [
        sys.executable,
        str(MAINTAINED_CHECKER),
        "--policy",
        str(POLICY),
        *argv,
    ]
    result = subprocess.run(
        delegated, cwd=ROOT, env=maintained_checker_environment(), check=False
    )
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
