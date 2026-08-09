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
    agents = (root / ".project-agent-workflow/AGENTS.md").read_text(encoding="utf-8")

    profile_answers = (
        ("primary_language", "Primary language"),
        ("human_report_mode", "Human report mode"),
        ("codex_hooks_mode", "Codex hooks mode"),
        ("skillspector_mode", "SkillSpector mode"),
        ("ci_autofix_mode", "CI autofix mode"),
    )
    for key, label in profile_answers:
        require(
            f"- {label}: `{answers[key]}`" in agents,
            f"managed AGENTS.md does not reflect {key}",
        )

    human_report_config = (root / ".project-agent-workflow/human-report.json").read_text(encoding="utf-8")
    require(
        f'"mode": "{answers["human_report_mode"]}"' in human_report_config,
        "managed human report config does not reflect human_report_mode",
    )

    conditional_files = (
        (".codex/hooks.json", answers["codex_hooks_mode"] == "enable_local_logging"),
        (
            ".project-agent-workflow/scripts/skillspector-scan.sh",
            answers["skillspector_mode"] == "document_optional",
        ),
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
        "managed AGENTS.md external-service state summary does not match generated policy",
    )

    config = (root / ".codex/config.toml").read_text(encoding="utf-8")
    require(
        "max_concurrent_threads_per_session = 4" in config,
        "generated Codex config lacks canonical concurrency setting",
    )
    require("max_threads" not in config and "max_depth" not in config, "generated Codex config uses legacy settings")
    expected_profiles = {
        "change_reviewer": ("gpt-5.6-sol", "high"),
        "docs_researcher": ("gpt-5.6-luna", "medium"),
        "evidence_synthesizer": ("gpt-5.6-luna", "xhigh"),
        "fast_scoped_worker": ("gpt-5.3-codex-spark", "medium"),
        "repo_explorer": ("gpt-5.6-luna", "low"),
        "scoped_worker": ("gpt-5.6-terra", "medium"),
        "sequential_plan_worker": ("gpt-5.3-codex-spark", "medium"),
    }
    for name, (model, effort) in expected_profiles.items():
        text = (root / ".codex" / "agents" / f"{name}.toml").read_text(encoding="utf-8")
        require(
            f'model = "{model}"' in text,
            f"{name} does not pin its task-specific model",
        )
        require(
            f'model_reasoning_effort = "{effort}"' in text,
            f"{name} does not pin its task-specific reasoning effort",
        )
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
    fast_worker = (root / ".codex/agents/fast_scoped_worker.toml").read_text(encoding="utf-8")
    require(
        "Require an explicit write scope and predetermined validation" in fast_worker
        and "Do not commit, tag, push, release" in fast_worker,
        "fast_scoped_worker lacks its bounded-work or main-session ownership contract",
    )
    evidence_synthesizer = (root / ".codex/agents/evidence_synthesizer.toml").read_text(encoding="utf-8")
    require(
        'sandbox_mode = "read-only"' in evidence_synthesizer
        and "Do not edit files, execute external writes" in evidence_synthesizer
        and "final high-risk judgment" in evidence_synthesizer,
        "evidence_synthesizer lacks its read-only or parent-judgment boundary",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
