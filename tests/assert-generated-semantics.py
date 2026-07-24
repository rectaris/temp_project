#!/usr/bin/env python3
"""Assert that rendered content, not only its inventory, matches Copier answers."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


MODE_TO_STATE = {"disabled": "disabled", "document_optional": "documented"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("generated", type=Path)
    args = parser.parse_args()
    root = args.generated
    answers = yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")

    profile_answers = (
        ("primary_language", "Primary language"),
        ("codex_hooks_mode", "Codex hooks mode"),
        ("skillspector_mode", "SkillSpector mode"),
        ("ci_autofix_mode", "CI autofix mode"),
    )
    for key, label in profile_answers:
        require(f"- {label}: `{answers[key]}`" in agents, f"AGENTS.md does not reflect {key}")

    conditional_files = (
        (".codex/hooks.json", answers["codex_hooks_mode"] == "enable_local_logging"),
        ("scripts/skillspector-scan.sh", answers["skillspector_mode"] == "document_optional"),
        (".github/workflows/codex-ci-autofix.yml", answers["ci_autofix_mode"] != "disabled"),
    )
    for relative, expected in conditional_files:
        require((root / relative).is_file() is expected, f"conditional file mismatch: {relative}")

    policy = yaml.safe_load((root / "docs/agent/external-services.yaml").read_text(encoding="utf-8"))
    services = policy["external_services"]
    service_modes = (
        ("mcp", answers["mcp_policy_mode"]),
        ("linear_sync", answers["linear_sync_mode"]),
        ("graph_memory", answers["graph_memory_mode"]),
    )
    for service_name, mode in service_modes:
        service = services[service_name]
        expected_state = MODE_TO_STATE[mode]
        require(service["state"] == expected_state, f"{service_name} state mismatch")
        require(service["authentication"] == "none", f"{service_name} authentication default mismatch")
        require(service["credential_reference"] == "", f"{service_name} credential reference default mismatch")

    expected_profile = (
        f"MCP=`{services['mcp']['state']}`",
        f"Linear=`{services['linear_sync']['state']}`",
        f"graph memory=`{services['graph_memory']['state']}`",
    )
    require(
        f"- External service policy states: {', '.join(expected_profile)}" in agents,
        "AGENTS.md external-service state summary does not match generated policy",
    )

    config = (root / ".codex/config.toml").read_text(encoding="utf-8")
    require(
        "max_concurrent_threads_per_session = 4" in config,
        "generated Codex config lacks canonical concurrency setting",
    )
    require("max_threads" not in config and "max_depth" not in config, "generated Codex config uses legacy settings")
    for name in ("change_reviewer", "docs_researcher", "repo_explorer", "scoped_worker"):
        text = (root / ".codex" / "agents" / f"{name}.toml").read_text(encoding="utf-8")
        require("\nmodel = " not in text, f"{name} pins a helper model")
    docs_researcher = (root / ".codex/agents/docs_researcher.toml").read_text(encoding="utf-8")
    require(
        "external-service policy authorizes" in docs_researcher
        and "When external research is unavailable" in docs_researcher,
        "docs_researcher lacks an external-policy fallback",
    )
    require(
        "Do not commit changes." in (root / ".codex/agents/scoped_worker.toml").read_text(encoding="utf-8"),
        "scoped_worker does not preserve main-session commit ownership",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
