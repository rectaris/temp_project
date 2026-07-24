#!/usr/bin/env python3
"""Validate the constrained external-service policy and authorize one operation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys


POLICY = Path("docs/agent/external-services.yaml")
STATES = {"disabled", "documented", "configured_read_only", "configured_write_capable"}
AUTHENTICATION = {"none", "environment", "platform"}
FIELDS = {
    "state",
    "connection",
    "authentication",
    "credential_reference",
    "allowed_reads",
    "allowed_writes",
    "write_authorization_rule",
    "dry_run_or_local_validation",
    "unavailable_fallback",
}
ENVIRONMENT_REFERENCE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PLATFORM_REFERENCE = re.compile(r"^(?:binding|secret|vault):[A-Za-z0-9][A-Za-z0-9._/-]*$")


class PolicyError(ValueError):
    pass


def scalar(raw: str) -> str:
    value = raw.strip()
    if value == '""' or value == "''":
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def load_policy(path: Path) -> dict[str, dict[str, str | list[str]]]:
    services: dict[str, dict[str, str | list[str]]] = {}
    current_service: str | None = None
    current_list: str | None = None
    in_services = False
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw == "external_services:":
            in_services = True
            current_service = None
            current_list = None
            continue
        if not in_services:
            continue
        service_match = re.fullmatch(r"  ([a-z][a-z0-9_]*):", raw)
        if service_match:
            current_service = service_match.group(1)
            if current_service in services:
                raise PolicyError(f"line {lineno}: duplicate service: {current_service}")
            services[current_service] = {}
            current_list = None
            continue
        field_match = re.fullmatch(r"    ([a-z][a-z0-9_]*):(.*)", raw)
        if field_match and current_service:
            key, raw_value = field_match.groups()
            if key in services[current_service]:
                raise PolicyError(f"line {lineno}: duplicate field: {current_service}.{key}")
            value = raw_value.strip()
            if value == "[]":
                services[current_service][key] = []
                current_list = None
            elif value:
                services[current_service][key] = scalar(value)
                current_list = None
            else:
                services[current_service][key] = []
                current_list = key
            continue
        item_match = re.fullmatch(r"      - (.+)", raw)
        if item_match and current_service and current_list:
            value = services[current_service][current_list]
            assert isinstance(value, list)
            value.append(scalar(item_match.group(1)))
            continue
        raise PolicyError(f"line {lineno}: unsupported external-services YAML structure")
    if not services:
        raise PolicyError("external_services mapping is empty")
    return services


def text_field(service: dict[str, str | list[str]], key: str) -> str:
    value = service[key]
    if not isinstance(value, str):
        raise PolicyError(f"{key} must be a scalar")
    return value


def list_field(service: dict[str, str | list[str]], key: str) -> list[str]:
    value = service[key]
    if not isinstance(value, list) or any(not item for item in value):
        raise PolicyError(f"{key} must be a list of non-empty operation names")
    return value


def validate_service(name: str, service: dict[str, str | list[str]]) -> None:
    missing = FIELDS - set(service)
    unknown = set(service) - FIELDS
    if missing or unknown:
        raise PolicyError(f"{name} field mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")
    state = text_field(service, "state")
    authentication = text_field(service, "authentication")
    reference = text_field(service, "credential_reference")
    if state not in STATES:
        raise PolicyError(f"{name}.state must be one of: {', '.join(sorted(STATES))}")
    if authentication not in AUTHENTICATION:
        raise PolicyError(
            f"{name}.authentication must be one of: {', '.join(sorted(AUTHENTICATION))}"
        )
    if authentication == "none" and reference:
        raise PolicyError(f"{name}.credential_reference must be empty for authentication: none")
    if authentication == "environment" and not ENVIRONMENT_REFERENCE.fullmatch(reference):
        raise PolicyError(f"{name}.credential_reference must be an environment-variable name")
    if authentication == "platform" and not PLATFORM_REFERENCE.fullmatch(reference):
        raise PolicyError(
            f"{name}.credential_reference must use binding:, secret:, or vault: followed by an identifier"
        )
    allowed_reads = list_field(service, "allowed_reads")
    allowed_writes = list_field(service, "allowed_writes")
    if len(allowed_reads) != len(set(allowed_reads)) or len(allowed_writes) != len(set(allowed_writes)):
        raise PolicyError(f"{name} operation lists must not contain duplicates")
    if state in {"configured_read_only", "configured_write_capable"}:
        if not text_field(service, "connection") or not allowed_reads:
            raise PolicyError(f"{name} configured state requires connection and allowed_reads")
    if state == "configured_read_only" and allowed_writes:
        raise PolicyError(f"{name} configured_read_only must not declare allowed_writes")
    if state == "configured_write_capable":
        if not allowed_writes:
            raise PolicyError(f"{name} configured_write_capable requires allowed_writes")
        if not text_field(service, "write_authorization_rule"):
            raise PolicyError(f"{name} configured_write_capable requires write_authorization_rule")
        if not text_field(service, "dry_run_or_local_validation"):
            raise PolicyError(f"{name} configured_write_capable requires dry_run_or_local_validation")


def validate_policy(path: Path) -> dict[str, dict[str, str | list[str]]]:
    services = load_policy(path)
    for name, service in services.items():
        validate_service(name, service)
    return services


def authorize(
    services: dict[str, dict[str, str | list[str]]],
    service_name: str,
    access: str,
    operation: str,
    authorization_rule: str | None,
) -> None:
    if service_name not in services:
        raise PolicyError(f"unknown service: {service_name}")
    service = services[service_name]
    state = text_field(service, "state")
    if access == "read":
        if state not in {"configured_read_only", "configured_write_capable"}:
            raise PolicyError(f"{service_name} state does not authorize reads: {state}")
        if operation not in list_field(service, "allowed_reads"):
            raise PolicyError(f"{service_name} read operation is not allowlisted: {operation}")
        return
    if state != "configured_write_capable":
        raise PolicyError(f"{service_name} state does not authorize writes: {state}")
    if operation not in list_field(service, "allowed_writes"):
        raise PolicyError(f"{service_name} write operation is not allowlisted: {operation}")
    expected = text_field(service, "write_authorization_rule")
    if authorization_rule != expected:
        raise PolicyError("provided authorization rule does not match write_authorization_rule")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=POLICY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    authorize_parser = subparsers.add_parser("authorize")
    authorize_parser.add_argument("service")
    authorize_parser.add_argument("access", choices=("read", "write"))
    authorize_parser.add_argument("operation")
    authorize_parser.add_argument("--authorization-rule")
    args = parser.parse_args(argv)
    try:
        services = validate_policy(args.policy)
        if args.command == "authorize":
            authorize(
                services,
                args.service,
                args.access,
                args.operation,
                args.authorization_rule,
            )
    except (OSError, PolicyError) as exc:
        print(f"external-service policy error: {exc}", file=sys.stderr)
        return 1
    print("external-service policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
