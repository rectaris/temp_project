#!/usr/bin/env python3
"""Validate external-service policy versions and authorize one operation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys
from typing import Any


POLICY = Path("docs/agent/external-services.yaml")
V1_STATES = {"disabled", "documented", "configured_read_only", "configured_write_capable"}
AUTHENTICATION = {"none", "environment", "platform"}
V1_FIELDS = {
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
V2_FIELDS = {
    "version",
    "access_profile",
    "provider_requirement",
    "task_scope_rule",
    "confirmation_required_effects",
    "denied_effects",
    "unclassified_write_effect",
    "unavailable_fallback",
}
V2_CONFIRMATION_EFFECTS = {
    "remote_delete",
    "public_communication",
    "financial_commitment",
    "production_change",
    "access_control_change",
}
V2_DENIED_EFFECTS = {
    "credential_material_transfer",
    "secret_persistence",
    "write_credentials_to_untrusted_code",
}
ENVIRONMENT_REFERENCE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PLATFORM_REFERENCE = re.compile(r"^(?:binding|secret|vault):[A-Za-z0-9][A-Za-z0-9._/-]*$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class PolicyError(ValueError):
    pass


def scalar(raw: str) -> str:
    value = raw.strip()
    if value == '""' or value == "''":
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def policy_version(path: Path) -> int:
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"version:\s*([0-9]+)\s*", raw)
        if not match:
            raise PolicyError(f"line {lineno}: first policy field must be an integer version")
        return int(match.group(1))
    raise PolicyError("external-service policy is empty")


def load_v1_services(path: Path) -> dict[str, dict[str, str | list[str]]]:
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
        raise PolicyError(f"line {lineno}: unsupported version 1 YAML structure")
    if not services:
        raise PolicyError("external_services mapping is empty")
    return services


def load_v2(path: Path) -> tuple[dict[str, str | list[str]], dict[str, dict[str, str]]]:
    policy: dict[str, str | list[str]] = {}
    services: dict[str, dict[str, str]] = {}
    current_list: str | None = None
    current_service: str | None = None
    in_services = False
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw == "external_services:":
            in_services = True
            current_list = None
            current_service = None
            continue
        if in_services:
            service_match = re.fullmatch(r"  ([a-z][a-z0-9_]*):", raw)
            if service_match:
                current_service = service_match.group(1)
                if current_service in services:
                    raise PolicyError(f"line {lineno}: duplicate service: {current_service}")
                services[current_service] = {}
                continue
            fallback_match = re.fullmatch(r"    unavailable_fallback:\s*(.+)", raw)
            if fallback_match and current_service:
                if services[current_service]:
                    raise PolicyError(f"line {lineno}: duplicate service fallback: {current_service}")
                services[current_service]["unavailable_fallback"] = scalar(fallback_match.group(1))
                continue
            raise PolicyError(f"line {lineno}: unsupported version 2 service structure")
        item_match = re.fullmatch(r"  - (.+)", raw)
        if item_match and current_list:
            value = policy[current_list]
            assert isinstance(value, list)
            value.append(scalar(item_match.group(1)))
            continue
        field_match = re.fullmatch(r"([a-z][a-z0-9_]*):(.*)", raw)
        if field_match:
            key, raw_value = field_match.groups()
            if key in policy:
                raise PolicyError(f"line {lineno}: duplicate field: {key}")
            value = raw_value.strip()
            if not value:
                policy[key] = []
                current_list = key
            else:
                policy[key] = scalar(value)
                current_list = None
            continue
        raise PolicyError(f"line {lineno}: unsupported version 2 YAML structure")
    return policy, services


def text_field(mapping: dict[str, Any], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str):
        raise PolicyError(f"{key} must be a scalar")
    return value


def list_field(mapping: dict[str, Any], key: str) -> list[str]:
    value = mapping[key]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise PolicyError(f"{key} must be a list of non-empty identifiers")
    return value


def validate_v1_service(name: str, service: dict[str, str | list[str]]) -> None:
    missing = V1_FIELDS - set(service)
    unknown = set(service) - V1_FIELDS
    if missing or unknown:
        raise PolicyError(f"{name} field mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")
    state = text_field(service, "state")
    authentication = text_field(service, "authentication")
    reference = text_field(service, "credential_reference")
    if state not in V1_STATES:
        raise PolicyError(f"{name}.state must be one of: {', '.join(sorted(V1_STATES))}")
    if authentication not in AUTHENTICATION:
        raise PolicyError(f"{name}.authentication must be one of: {', '.join(sorted(AUTHENTICATION))}")
    if authentication == "none" and reference:
        raise PolicyError(f"{name}.credential_reference must be empty for authentication: none")
    if authentication == "environment" and not ENVIRONMENT_REFERENCE.fullmatch(reference):
        raise PolicyError(f"{name}.credential_reference must be an environment-variable name")
    if authentication == "platform" and not PLATFORM_REFERENCE.fullmatch(reference):
        raise PolicyError(f"{name}.credential_reference must use binding:, secret:, or vault: followed by an identifier")
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


def validate_v2(policy: dict[str, str | list[str]], services: dict[str, dict[str, str]]) -> None:
    missing = V2_FIELDS - set(policy)
    unknown = set(policy) - V2_FIELDS
    if missing or unknown:
        raise PolicyError(f"version 2 field mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")
    if text_field(policy, "version") != "2":
        raise PolicyError("version 2 policy must declare version: 2")
    if text_field(policy, "access_profile") != "task_scoped_default_allow":
        raise PolicyError("version 2 access_profile must be task_scoped_default_allow")
    if text_field(policy, "provider_requirement") != "runtime_configured":
        raise PolicyError("version 2 provider_requirement must be runtime_configured")
    if text_field(policy, "task_scope_rule") != "current_user_request":
        raise PolicyError("version 2 task_scope_rule must be current_user_request")
    if text_field(policy, "unclassified_write_effect") != "require_confirmation":
        raise PolicyError("version 2 unclassified writes must require confirmation")
    if not text_field(policy, "unavailable_fallback"):
        raise PolicyError("version 2 unavailable_fallback must be non-empty")
    confirmation = list_field(policy, "confirmation_required_effects")
    denied = list_field(policy, "denied_effects")
    if len(confirmation) != len(set(confirmation)) or len(denied) != len(set(denied)):
        raise PolicyError("version 2 effect lists must not contain duplicates")
    if not all(IDENTIFIER.fullmatch(item) for item in confirmation + denied):
        raise PolicyError("version 2 effects must be lowercase identifiers")
    if not V2_CONFIRMATION_EFFECTS.issubset(confirmation):
        raise PolicyError("version 2 policy is missing a required confirmation effect")
    if not V2_DENIED_EFFECTS.issubset(denied):
        raise PolicyError("version 2 policy is missing a required denied effect")
    if set(confirmation) & set(denied):
        raise PolicyError("version 2 confirmation and denied effects must not overlap")
    if "ordinary" in confirmation or "ordinary" in denied:
        raise PolicyError("ordinary must not appear in version 2 protected-effect lists")
    if not services:
        raise PolicyError("external_services mapping is empty")
    for name, service in services.items():
        if set(service) != {"unavailable_fallback"} or not service["unavailable_fallback"]:
            raise PolicyError(f"{name} must define one non-empty unavailable_fallback")


def validate_policy(path: Path) -> tuple[int, dict[str, Any], dict[str, Any]]:
    version = policy_version(path)
    if version == 1:
        services = load_v1_services(path)
        for name, service in services.items():
            validate_v1_service(name, service)
        return version, {}, services
    if version == 2:
        policy, services = load_v2(path)
        validate_v2(policy, services)
        return version, policy, services
    raise PolicyError(f"unsupported external-service policy version: {version}")


def authorize_v1(
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


def authorize_v2(policy: dict[str, Any], args: argparse.Namespace) -> None:
    if not IDENTIFIER.fullmatch(args.service):
        raise PolicyError("service must be a lowercase identifier")
    if not args.provider_configured:
        raise PolicyError("version 2 authorization requires a configured and authenticated provider")
    if not args.task_authorized:
        raise PolicyError("version 2 authorization requires the current user request to authorize the exact operation")
    if not args.target or not args.effect:
        raise PolicyError("version 2 provider calls require exact target and effect")
    if not all(IDENTIFIER.fullmatch(effect) for effect in args.effect):
        raise PolicyError("version 2 provider-call effect must be a lowercase identifier")
    effects = set(args.effect)
    denied = set(list_field(policy, "denied_effects"))
    denied_matches = effects & denied
    if denied_matches:
        raise PolicyError(
            "version 2 policy denies provider-call effect: "
            + ", ".join(sorted(denied_matches))
        )
    if "ordinary" in effects and len(effects) != 1:
        raise PolicyError("ordinary cannot be combined with another provider-call effect")
    if args.access == "read":
        if effects != {"ordinary"}:
            raise PolicyError("version 2 reads must have the ordinary effect classification")
        return
    confirmation = set(list_field(policy, "confirmation_required_effects"))
    requires_confirmation = bool(effects & confirmation) or effects != {"ordinary"}
    if requires_confirmation:
        if args.confirmed_target != args.target or set(args.confirmed_effect or []) != effects:
            raise PolicyError("write effect requires exact current-user confirmation for target and effect")


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
    authorize_parser.add_argument("--provider-configured", action="store_true")
    authorize_parser.add_argument("--task-authorized", action="store_true")
    authorize_parser.add_argument("--target")
    authorize_parser.add_argument("--effect", action="append")
    authorize_parser.add_argument("--confirmed-target")
    authorize_parser.add_argument("--confirmed-effect", action="append")
    args = parser.parse_args(argv)
    try:
        version, policy, services = validate_policy(args.policy)
        if args.command == "authorize":
            if version == 1:
                authorize_v1(services, args.service, args.access, args.operation, args.authorization_rule)
            else:
                authorize_v2(policy, args)
    except (OSError, PolicyError) as exc:
        print(f"external-service policy error: {exc}", file=sys.stderr)
        return 1
    print("external-service policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
