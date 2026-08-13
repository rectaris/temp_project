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
        ("external_access_profile", "External access profile"),
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
    if answers["external_access_profile"] == "restricted":
        require(policy["version"] == 1, "restricted profile must render policy version 1")
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

        browser_run = services["browser_run"]
        require(browser_run["state"] == "disabled", "browser_run must be disabled by default")
        require(browser_run["connection"] == "", "browser_run fresh default must not contain connection data")
        require(browser_run["authentication"] == "none", "browser_run authentication default mismatch")
        require(browser_run["credential_reference"] == "", "browser_run must not contain credentials")
        require(
            not browser_run["allowed_reads"] and not browser_run["allowed_writes"],
            "browser_run must not authorize operations by default",
        )
    else:
        require(policy["version"] == 2, "task-scoped profile must render policy version 2")
        require(policy["access_profile"] == "task_scoped_default_allow", "version 2 profile mismatch")
        require(policy["provider_requirement"] == "runtime_configured", "version 2 provider requirement mismatch")
        require(policy["task_scope_rule"] == "current_user_request", "version 2 task scope mismatch")
        require(
            {
                "remote_delete",
                "public_communication",
                "financial_commitment",
                "production_change",
                "access_control_change",
            }.issubset(policy["confirmation_required_effects"]),
            "version 2 confirmation effects incomplete",
        )
        require(
            {
                "credential_material_transfer",
                "secret_persistence",
                "write_credentials_to_untrusted_code",
            }.issubset(policy["denied_effects"]),
            "version 2 denied effects incomplete",
        )
        for service_name in ("mcp", "linear_sync", "graph_memory", "browser_run"):
            require(services[service_name]["unavailable_fallback"], f"{service_name} fallback missing")
        external_spec = (
            root / ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
        ).read_text(encoding="utf-8")
        require(
            "under version 2, confirm the current user request itself requires it"
            in external_spec,
            "version 2 documentation permits lifecycle commands to replace active-request authority",
        )
        require(
            "Any denied effect takes precedence, and `ordinary` applies only when no denied effect applies."
            in external_spec,
            "version 2 documentation lets ordinary overlap a denied effect",
        )
        mcp_skill = (
            root / ".project-agent-workflow/skills/mcp-ops/SKILL.md"
        ).read_text(encoding="utf-8")
        require(
            "version 2 requires the current user request itself" in mcp_skill,
            "generated MCP gate permits lifecycle commands to replace version 2 task authority",
        )

    browser_route = (root / ".project-agent-workflow/docs/agent/spec-index.yaml").read_text(encoding="utf-8")
    require("browser_automation:" in browser_route, "generated spec index lacks browser route")
    require(".agents/skills/browser-ops/SKILL.md" in browser_route, "generated browser route lacks discovery bridge")
    require((root / ".agents/skills/browser-ops/SKILL.md").is_file(), "generated browser bridge missing")
    require(
        (root / ".project-agent-workflow/skills/browser-ops/references/browser-run-policy.md").is_file(),
        "generated browser backend policy missing",
    )
    browser_policy = (
        root / ".project-agent-workflow/skills/browser-ops/references/browser-run-policy.md"
    ).read_text(encoding="utf-8")
    require(
        "Cloudflare Browser Run as one service" in browser_policy,
        "generated browser policy does not keep Browser Run engine authority together",
    )
    require(
        "distinct project-owned external-service record" in browser_policy,
        "generated browser policy permits Browser Run authority to leak to another Chromium provider",
    )

    if answers["external_access_profile"] == "restricted":
        expected_profile = (
            f"MCP=`{services['mcp']['state']}`",
            f"Linear=`{services['linear_sync']['state']}`",
            f"graph memory=`{services['graph_memory']['state']}`",
        )
        require(
            f"- External service policy states: {', '.join(expected_profile)}" in agents,
            "managed AGENTS.md external-service state summary does not match generated policy",
        )
    else:
        require(
            "- External service policy schema: version 2" in agents,
            "managed AGENTS.md does not report the task-scoped version 2 profile",
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
