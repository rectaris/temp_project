#!/usr/bin/env python3
"""Check root-level agent workflow policy for this template repository."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_MARKER_RE = re.compile(r"^\s*(A|B|C|推奨|理由|Recommended|Reason)\s*[:：]")
APPROACH_MARKERS = {"A", "B", "C"}
RATIONALE_MARKERS = {"推奨", "理由", "Recommended", "Reason"}
MATRIX_WINDOW_LINES = 20

REQUIRED_ROOT_FILES = [
    ".codex/config.toml",
    ".codex/hooks.json",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/evidence_synthesizer.toml",
    ".codex/agents/fast_scoped_worker.toml",
    ".codex/hooks/agent_log_event.py",
    ".codex/hooks/semantic_guard_advisory.py",
    ".codex/hooks/stop_review_gate.py",
    ".project-agent-workflow/hooks/agent_log_event.py",
    ".project-agent-workflow/hooks/pre_tool_hardening_gate.py",
    ".project-agent-workflow/hooks/semantic_guard_advisory.py",
    ".project-agent-workflow/hooks/stop_review_gate.py",
    ".codex/skills/decision-audit/SKILL.md",
    ".codex/skills/decision-audit/agents/openai.yaml",
    ".codex/skills/graph-memory/SKILL.md",
    ".codex/skills/graph-memory/agents/openai.yaml",
    ".codex/skills/implementation-guidelines/SKILL.md",
    ".codex/skills/implementation-guidelines/agents/openai.yaml",
    ".codex/skills/define-referents-first/SKILL.md",
    ".codex/skills/define-referents-first/agents/openai.yaml",
    ".codex/skills/define-referents-first/references/workflow.md",
    ".codex/skills/linear-ops/SKILL.md",
    ".codex/skills/linear-ops/agents/openai.yaml",
    ".codex/skills/mcp-ops/SKILL.md",
    ".codex/skills/mcp-ops/agents/openai.yaml",
    ".codex/skills/plan-archive/SKILL.md",
    ".codex/skills/plan-archive/agents/openai.yaml",
    ".codex/skills/sequential-plan-orchestrator/SKILL.md",
    ".codex/skills/sequential-plan-orchestrator/agents/openai.yaml",
    ".codex/skills/write-for-reader/SKILL.md",
    ".codex/skills/write-for-reader/agents/openai.yaml",
    ".codex/skills/browser-ops/SKILL.md",
    ".codex/skills/browser-ops/agents/openai.yaml",
    ".codex/skills/browser-ops/references/browser-run-policy.md",
    ".codex/agents/sequential_plan_worker.toml",
    "docs/agent/spec-index.yaml",
    "docs/agent/SPEC_EXTERNAL_SERVICES.md",
    "docs/agent/external-services.yaml",
    "docs/agent/SPEC_AGENT_LOGGING.md",
    "docs/agent/SPEC_CONTEXT_COMPRESSION.md",
    "docs/agent/SPEC_DECISION_AUDIT.md",
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "docs/agent/SPEC_REFERENT_FIRST.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_USER_COMMUNICATION.md",
    "scripts/agent-log-event.py",
    "scripts/check-agent-log-manifest.py",
    "scripts/check-external-service-policy.py",
    "scripts/check-codex-toml.py",
    "scripts/complete-plan.sh",
    "scripts/context-compress.sh",
    "scripts/plan_validation_commands.py",
    "scripts/referent-contract.py",
    "scripts/run-sandboxed-plan-worker.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
    "scripts/update_agent_model_profiles.py",
    "tests/root-plan-lifecycle.sh",
    "tests/test-agent-model-profiles.py",
    "tests/fixtures/write-for-reader/scenarios.json",
]

REUSABLE_SKILLS = (
    "decision-audit",
    "define-referents-first",
    "graph-memory",
    "implementation-guidelines",
    "linear-ops",
    "mcp-ops",
    "plan-archive",
    "sequential-plan-orchestrator",
    "write-for-reader",
)

REQUIRED_AGENT_RULES = [
    "docs/agent/spec-index.yaml",
    ".agent-logs/",
    ".agent-artifacts/",
    ".codex/hooks/agent_log_event.py",
    ".codex/skills/decision-audit",
    ".codex/skills/implementation-guidelines",
    ".codex/skills/define-referents-first",
    ".codex/skills/write-for-reader",
    "docs/agent/SPEC_REFERENT_FIRST.md",
    "docs/agent/SPEC_SKILL_AUTHORING.md",
    "docs/agent/SPEC_USER_COMMUNICATION.md",
    "*.backup",
    "decision audit",
    "docs/plan/active",
]


def fail(message: str) -> None:
    print(f"root agent policy check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def option_matrix_lines(text: str) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = MATRIX_MARKER_RE.match(line)
        if match:
            markers.append((lineno, match.group(1)))
    return markers


def contains_option_matrix(text: str) -> bool:
    markers = option_matrix_lines(text)
    for index, (lineno, marker) in enumerate(markers):
        if marker not in APPROACH_MARKERS:
            continue
        window = [
            candidate
            for candidate_lineno, candidate in markers[index:]
            if candidate_lineno - lineno <= MATRIX_WINDOW_LINES
        ]
        approach_count = len({candidate for candidate in window if candidate in APPROACH_MARKERS})
        has_rationale = any(candidate in RATIONALE_MARKERS for candidate in window)
        if approach_count >= 2 and has_rationale:
            return True
    return False


def check_required_files() -> None:
    for rel in REQUIRED_ROOT_FILES:
        if not (ROOT / rel).is_file():
            fail(f"missing required root policy file: {rel}")


def check_gitignore() -> None:
    text = read(".gitignore")
    for pattern in (".agent-logs/", ".agent-artifacts/"):
        if pattern not in text:
            fail(f".gitignore missing {pattern}")


def check_agents_rules() -> None:
    text = read("AGENTS.md")
    for required in REQUIRED_AGENT_RULES:
        if required not in text:
            fail(f"AGENTS.md missing root policy reference: {required}")


def check_agent_model_profiles() -> None:
    contracts = {
        ".codex/agents/change_reviewer.toml": (
            "gpt-5.6-sol",
            "high",
            'name = "change_reviewer"',
        ),
        ".codex/agents/docs_researcher.toml": (
            "gpt-5.6-luna",
            "medium",
            'name = "docs_researcher"',
        ),
        ".codex/agents/evidence_synthesizer.toml": (
            "gpt-5.6-luna",
            "xhigh",
            'name = "evidence_synthesizer"',
            'sandbox_mode = "read-only"',
            "Do not edit files, execute external writes",
            "final high-risk judgment",
        ),
        ".codex/agents/fast_scoped_worker.toml": (
            "gpt-5.3-codex-spark",
            "medium",
            'name = "fast_scoped_worker"',
            "Require an explicit write scope and predetermined validation",
            "Do not commit, tag, push, release",
        ),
        ".codex/agents/repo_explorer.toml": (
            "gpt-5.6-luna",
            "low",
            'name = "repo_explorer"',
        ),
        ".codex/agents/scoped_worker.toml": (
            "gpt-5.6-terra",
            "medium",
            'name = "scoped_worker"',
            "Do not commit changes",
        ),
        ".codex/agents/sequential_plan_worker.toml": (
            "gpt-5.3-codex-spark",
            "medium",
            'name = "sequential_plan_worker"',
            "Do not process the next active plan",
            "Do not commit changes",
        ),
    }
    for relative, (model, effort, *role_markers) in contracts.items():
        text = read(relative)
        markers = (
            f'model = "{model}"',
            f'model_reasoning_effort = "{effort}"',
            *role_markers,
        )
        for marker in markers:
            if marker not in text:
                fail(f"{relative} missing fixed agent contract: {marker}")


def check_sandboxed_worker_fallback() -> None:
    runner = read("scripts/run-sandboxed-plan-worker.py")
    runner_markers = (
        'DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"',
        'DEFAULT_CODEX_REASONING = "medium"',
        'DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"',
        'DEFAULT_FALLBACK_CODEX_REASONING = "max"',
        "def classify_codex_unavailability",
        'label="fallback"',
        '"attempts"',
        '"selected_attempt"',
        '"fallback_reason"',
        '"--fallback-codex-model"',
        '"--fallback-codex-reasoning-effort"',
        '"--no-model-fallback"',
        "def select_plan_writable_profile",
        "implementation_risk",
        "implementation_ambiguity",
        "WRITABLE_SOL_MODEL",
        "AVAILABILITY_STATE_MAX_BYTES",
        "def open_availability_state",
        '"--availability-state"',
        '"--orchestration-run-id"',
        '"telemetry"',
        '"skipped_known_unavailable_starts"',
        "def correct_worker",
        "def verify_candidate_manifest",
        '"correct"',
        "MAX_CORRECTION_ROUNDS",
        '"correction_lineage"',
        "def validate_candidate",
        "def open_lifecycle_state",
        '"--lifecycle-state"',
        "VALIDATION_AUTHORITY_SCOPE",
        '"authoritative_passed"',
        '"apply requires exactly one successful authoritative validation"',
        "load_plan_validation_commands",
        '"focused_validation_count"',
        '"authoritative_validation_count"',
        "network_enabled=False",
    )
    for marker in runner_markers:
        if marker not in runner:
            fail(f"sandboxed plan worker missing model fallback marker: {marker}")

    for relative in (
        "AGENTS.md",
        "references/orchestration.md",
        ".codex/skills/sequential-plan-orchestrator/SKILL.md",
    ):
        text = read(relative).lower()
        for marker in ("gpt-5.3-codex-spark", "gpt-5.6-luna", "max", "usage limit", "rate limit"):
            if marker not in text:
                fail(f"{relative} missing sandboxed model fallback policy marker: {marker}")


def check_reusable_skill_parity() -> None:
    for skill in REUSABLE_SKILLS:
        for relative in ("SKILL.md", "agents/openai.yaml"):
            root_path = ROOT / ".codex" / "skills" / skill / relative
            template_path = ROOT / "template" / ".project-agent-workflow" / "skills" / skill / relative
            if not root_path.is_file() or not template_path.is_file():
                fail(f"missing reusable skill file for parity: {skill}/{relative}")
            template_text = (
                template_path.read_text(encoding="utf-8")
                .replace(".project-agent-workflow/", "")
                .replace(".agents/skills/", ".codex/skills/")
            )
            if root_path.read_text(encoding="utf-8") != template_text:
                fail(f"root/template reusable skill drift: {skill}/{relative}")


def check_browser_routing() -> None:
    index = read("docs/agent/spec-index.yaml")
    for marker in (
        "  browser_automation:",
        ".codex/skills/browser-ops/SKILL.md",
        ".codex/skills/browser-ops/references/browser-run-policy.md",
        "docs/agent/SPEC_SECURITY.md",
    ):
        if marker not in index:
            fail(f"root browser route missing: {marker}")
    skill = read(".codex/skills/browser-ops/SKILL.md")
    for marker in (
        "references/browser-run-policy.md",
        "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
        "template/docs/agent/external-services.yaml.jinja",
    ):
        if marker not in skill:
            fail(f"root browser skill missing: {marker}")
    root_skill = skill.replace(
        "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
    ).replace(
        "template/docs/agent/external-services.yaml.jinja",
        "docs/agent/external-services.yaml",
    )
    generated_skill = read("template/.project-agent-workflow/skills/browser-ops/SKILL.md")
    if root_skill != generated_skill:
        fail("root/template browser SKILL.md drift")

    root_reference = read(".codex/skills/browser-ops/references/browser-run-policy.md").replace(
        "template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja",
        ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md",
    ).replace(
        "template/docs/agent/external-services.yaml.jinja",
        "docs/agent/external-services.yaml",
    )
    generated_reference = read(
        "template/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md"
    )
    if root_reference != generated_reference:
        fail("root/template browser backend-reference drift")
    if read(".codex/skills/browser-ops/agents/openai.yaml") != read(
        "template/.project-agent-workflow/skills/browser-ops/agents/openai.yaml"
    ):
        fail("root/template browser agents/openai.yaml drift")

    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .agents/skills/browser-ops/SKILL.md" not in ownership:
        fail("browser discovery bridge is not reserved by Copier ownership")


def check_external_service_policy() -> None:
    index = read("docs/agent/spec-index.yaml")
    for marker in (
        "  external_services:",
        "docs/agent/SPEC_EXTERNAL_SERVICES.md",
        "docs/agent/SPEC_SECURITY.md",
    ):
        if marker not in index:
            fail(f"root external-service route missing: {marker}")

    policy = read("docs/agent/external-services.yaml")
    policy_markers = (
        "version: 2",
        "access_profile: task_scoped_default_allow",
        "provider_requirement: runtime_configured",
        "task_scope_rule: current_user_request",
        "  - remote_delete",
        "  - public_communication",
        "  - financial_commitment",
        "  - production_change",
        "  - access_control_change",
        "  - credential_material_transfer",
        "  - secret_persistence",
        "  - write_credentials_to_untrusted_code",
        "unclassified_write_effect: require_confirmation",
        "external_services:",
        "  github:",
        "unavailable_fallback:",
    )
    for marker in policy_markers:
        if marker not in policy:
            fail(f"root external-service policy missing marker: {marker}")
    for forbidden in ("credential_reference:", "access_token:", "private_key:"):
        if forbidden in policy:
            fail(f"root external-service policy contains credential material field: {forbidden}")

    specification = read("docs/agent/SPEC_EXTERNAL_SERVICES.md")
    specification_markers = (
        "docs/agent/external-services.yaml",
        "Provider configuration and authorization are separate facts.",
        "exact provider, operation, target, complete effect set, payload",
        "immediately before the call",
        "git.push",
        "pull_request.publish",
        "release.publish",
        "rectaris/temp_project",
        "git check-ref-format --branch",
    )
    for marker in specification_markers:
        if marker not in specification:
            fail(f"root external-service specification missing marker: {marker}")

    entrypoint = read("scripts/check-external-service-policy.py")
    entrypoint_markers = (
        "template/.project-agent-workflow/scripts/check-external-service-policy.py",
        '"--policy"',
        "allow_abbrev=False",
        "git.push",
        "pull_request.publish",
        "release.publish",
        "rectaris/temp_project",
        "check-ref-format",
        "subprocess.run",
    )
    for marker in entrypoint_markers:
        if marker not in entrypoint:
            fail(f"root external-service entrypoint missing marker: {marker}")
    if "str(POLICY)" not in entrypoint or "str(MAINTAINED_CHECKER)" not in entrypoint:
        fail("root external-service entrypoint must delegate with the fixed root policy")


def check_user_communication_contract() -> None:
    root_spec = read("docs/agent/SPEC_USER_COMMUNICATION.md")
    template_spec = read("template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md")
    if root_spec != template_spec:
        fail("root/template user-communication specifications differ")
    if root_spec.count("write-for-reader") != 1:
        fail("user-communication specification must name the operational skill exactly once")

    fixture_path = ROOT / "tests/fixtures/write-for-reader/scenarios.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid write-for-reader scenario fixture: {exc}")
    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not requirements or not any(item.get("critical") is True for item in requirements):
        fail("write-for-reader scenarios need at least one critical requirement")
    classes = {item.get("class") for item in scenarios}
    if not {"median", "edge", "holdout"}.issubset(classes):
        fail("write-for-reader scenarios need median, edge, and holdout cases")
    if any(item.get("used_for_tuning") is not False for item in scenarios if item.get("class") == "holdout"):
        fail("write-for-reader holdout scenarios must remain outside tuning")


def check_namespaced_documentation_targets() -> None:
    required_target = "template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    stale_target = "template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md"
    for path in ("AGENTS.md", "docs/agent/SPEC_JAPANESE_TECH_WRITING.md"):
        text = read(path)
        if required_target not in text:
            fail(f"{path} missing generated documentation sync target: {required_target}")
        if stale_target in text:
            fail(f"{path} still references removed generated documentation sync target: {stale_target}")

    skill = read("SKILL.md")
    if ".project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md" not in skill:
        fail("SKILL.md missing reusable external-services spec path: .project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md")
    if "`SPEC_EXTERNAL_SERVICES.md`" in skill:
        fail("SKILL.md still references stale external-services spec path: `SPEC_EXTERNAL_SERVICES.md`")

    planning = read("references/planning.md")
    planning_required = (
        "`.project-agent-workflow/scripts/check-agent-completion.sh`",
        "`.project-agent-workflow/scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`",
        "`.project-agent-workflow/scripts/search-plan-archive.py --text <term>`",
    )
    for marker in planning_required:
        if marker not in planning:
            fail(f"references/planning.md missing managed path marker: {marker}")

    require_current_plan_manifest_reference(planning)

    validation = read("references/validation.md")
    validation_required = (
        "`.project-agent-workflow/scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.",
        "`.project-agent-workflow/scripts/security-static-check.py`: scans common high-signal static risks.",
        "`.project-agent-workflow/scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.",
    )
    for marker in validation_required:
        if marker not in validation:
            fail(f"references/validation.md missing managed path marker: {marker}")

    stale_validation = "`scripts/validate-changes.py`: selects validation commands from staged or unstaged paths."
    if stale_validation in validation:
        fail(f"references/validation.md still references stale managed path: {stale_validation}")


def require_current_plan_manifest_reference(planning: str) -> None:
    required_fields = (
        "status",
        "task_types",
        "review_class",
        "human_design_required",
        "human_approval_status",
        "write_scope",
        "context_files",
        "required_specs",
        "validation",
        "acceptance",
        "checked_summary_ja",
    )
    optional_fields = ("target_json", "acceptance_focus", "completion_deferred_reason")
    legacy_fields = ("task_type", "target_files", "expected_output")
    try:
        manifest_reference, _ = planning.split("## Lifecycle Scripts", 1)
        required_section, optional_section = manifest_reference.split(
            "Optional fields for new active and backlog plans:", 1
        )
    except ValueError:
        fail("references/planning.md missing current active-plan manifest sections")
    for field in required_fields:
        if f"- `{field}`" not in required_section:
            fail(f"references/planning.md missing required active-plan field: {field}")
    for field in optional_fields:
        if f"- `{field}`" not in optional_section:
            fail(f"references/planning.md missing optional active-plan field: {field}")
    for field in legacy_fields:
        if f"- `{field}`" in manifest_reference:
            fail(f"references/planning.md recommends removed active-plan field: {field}")
        if f"`{field}`" not in optional_section:
            fail(f"references/planning.md missing legacy archive note for: {field}")


def validate_paired_runner_evidence(
    measured_path: Path,
    *,
    claim_status: str,
    repository_root: Path = ROOT,
) -> list[dict[str, dict[str, float]]]:
    try:
        measured = json.loads(measured_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid paired runner evidence: {exc}") from exc
    if measured.get("schema_version") != 1 or set(measured) != {
        "schema_version", "evidence_status", "capture_commit", "pairs"
    }:
        raise ValueError("paired runner evidence has an invalid exact schema")
    evidence_status = measured["evidence_status"]
    if evidence_status not in {"schema_example", "captured_runner_evidence"}:
        raise ValueError("paired runner evidence status is invalid")
    if claim_status == "measured_pass" and evidence_status != "captured_runner_evidence":
        raise ValueError("measured performance claims require captured runner evidence")
    capture_commit = measured["capture_commit"]
    if evidence_status == "schema_example":
        if capture_commit is not None:
            raise ValueError("schema-example evidence cannot claim a capture commit")
    else:
        if not isinstance(capture_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", capture_commit):
            raise ValueError("captured runner evidence requires a full capture commit")
        commit_check = subprocess.run(
            ["git", "cat-file", "-e", f"{capture_commit}^{{commit}}"],
            cwd=repository_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if commit_check.returncode != 0:
            raise ValueError("paired runner capture commit is unavailable")
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", capture_commit, "HEAD"],
            cwd=repository_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if ancestry.returncode != 0:
            raise ValueError("paired runner capture commit must be an ancestor of current HEAD")
        try:
            measured_rel = measured_path.resolve(strict=True).relative_to(
                repository_root.resolve(strict=True)
            ).as_posix()
        except (OSError, ValueError) as exc:
            raise ValueError("captured runner evidence index must be inside the repository") from exc
        committed_index = subprocess.run(
            ["git", "show", f"HEAD:{measured_rel}"],
            cwd=repository_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if committed_index.returncode != 0 or committed_index.stdout != measured_path.read_bytes():
            raise ValueError("captured runner evidence index must match the current HEAD blob")
    pairs = measured.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 4:
        raise ValueError("paired runner evidence must contain four fixed scenarios")

    expected_classes = {"median", "edge", "negative", "holdout"}
    pair_ids: set[str] = set()
    classes: set[str] = set()
    artifact_paths: set[Path] = set()
    paired_metrics: list[dict[str, dict[str, float]]] = []

    def load_artifact(name: object, digest: object) -> tuple[Path, dict[str, object]]:
        if not isinstance(name, str) or name != f"paired-artifacts/{Path(name).name}":
            raise ValueError("paired evidence artifact must be a direct paired-artifacts child")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("paired evidence artifact digest must be lowercase SHA-256")
        path = measured_path.parent / name
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(measured_path.parent.resolve(strict=True))
            payload = path.read_bytes()
            parsed = json.loads(payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid paired evidence artifact {name}: {exc}") from exc
        if path.is_symlink() or resolved in artifact_paths:
            raise ValueError("paired evidence artifacts must be unique regular files")
        artifact_paths.add(resolved)
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f"paired evidence artifact digest mismatch: {name}")
        if evidence_status == "captured_runner_evidence":
            try:
                repo_rel = resolved.relative_to(repository_root.resolve(strict=True)).as_posix()
            except ValueError as exc:
                raise ValueError("captured runner artifacts must be inside the evidence repository") from exc
            committed = subprocess.run(
                ["git", "show", f"{capture_commit}:{repo_rel}"],
                cwd=repository_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if committed.returncode != 0 or committed.stdout != payload:
                raise ValueError(f"captured runner artifact differs from its capture commit: {name}")
        if not isinstance(parsed, dict):
            raise ValueError(f"paired evidence artifact must contain an object: {name}")
        return resolved, parsed

    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {
            "paired_run_id", "class", "used_for_tuning", "workload_artifact",
            "paired_workload_digest", "baseline", "staged",
        }:
            raise ValueError("paired runner evidence record has an invalid exact shape")
        pair_id = pair["paired_run_id"]
        scenario_class = pair["class"]
        used_for_tuning = pair["used_for_tuning"]
        if not isinstance(pair_id, str) or not pair_id.strip() or pair_id in pair_ids:
            raise ValueError("paired runner identifiers must be unique nonblank strings")
        if scenario_class not in expected_classes or scenario_class in classes:
            raise ValueError("paired runner evidence must contain each fixed class exactly once")
        if used_for_tuning is not (scenario_class != "holdout"):
            raise ValueError("paired holdout and tuning classifications are inconsistent")
        pair_ids.add(pair_id)
        classes.add(scenario_class)

        workload_digest = pair["paired_workload_digest"]
        _, workload = load_artifact(pair["workload_artifact"], workload_digest)
        if workload != {
            "schema_version": 1,
            "scenario_id": pair_id,
            "class": scenario_class,
            "used_for_tuning": used_for_tuning,
        }:
            raise ValueError("paired workload artifact does not match its scenario record")

        parsed_sides: dict[str, dict[str, float]] = {}
        runner_identities: set[tuple[str, str]] = set()
        for side in ("baseline", "staged"):
            record = pair[side]
            example_fields = {
                "manifest_artifact", "manifest_digest", "lifecycle_artifact",
                "lifecycle_digest", "model_starts", "time_to_accepted_patch_seconds",
            }
            captured_fields = {
                "manifest_artifact", "manifest_digest", "lifecycle_artifact",
                "lifecycle_digest", "event_artifact", "event_digest",
            }
            expected_fields = example_fields if evidence_status == "schema_example" else captured_fields
            if not isinstance(record, dict) or set(record) != expected_fields:
                raise ValueError("paired runner side has an invalid exact telemetry shape")
            _, manifest = load_artifact(record["manifest_artifact"], record["manifest_digest"])
            _, lifecycle = load_artifact(record["lifecycle_artifact"], record["lifecycle_digest"])
            if evidence_status == "captured_runner_evidence":
                _, event = load_artifact(record["event_artifact"], record["event_digest"])
                manifest_fields = {
                    "schema_version", "source_head", "plan_path", "plan_digest",
                    "allowed_write_scope", "changed_paths", "patch_path", "patch_digest",
                    "orchestration_run_id", "lifecycle_state_path", "worker_result", "telemetry",
                }
                if not isinstance(manifest, dict) or frozenset(manifest) not in {
                    frozenset(manifest_fields), frozenset(manifest_fields | {"correction_lineage"})
                }:
                    raise ValueError("captured manifest is not an exact runner candidate manifest")
                run_id = manifest.get("orchestration_run_id")
                telemetry = manifest.get("telemetry")
                if not isinstance(run_id, str) or not run_id.strip() or not isinstance(telemetry, dict):
                    raise ValueError("captured runner manifest lacks bounded run telemetry")
                telemetry_fields = {
                    "schema_version", "attempt_durations_seconds", "runner_duration_seconds",
                    "model_starts", "availability_failures", "skipped_known_unavailable_starts",
                    "candidate_generations", "full_validation_count",
                    "authoritative_validation_count", "focused_validation_count",
                    "parent_review_rejections", "correction_round", "implementation_risk",
                    "implementation_ambiguity",
                }
                if set(telemetry) != telemetry_fields:
                    raise ValueError("captured runner telemetry has an invalid exact schema")
                model_starts = telemetry.get("model_starts")
                if not isinstance(model_starts, int) or isinstance(model_starts, bool) or not 0 <= model_starts <= 3:
                    raise ValueError("captured runner model_starts must be a bounded integer")
                lifecycle_fields = {
                    "schema_version", "orchestration_run_id", "current_manifest_digest",
                    "current_patch_digest", "correction_round", "candidate_generations", "phase",
                    "focused_required", "focused_validation_count", "authoritative_validation_count",
                    "parent_review_rejections",
                }
                if not isinstance(lifecycle, dict) or set(lifecycle) != lifecycle_fields:
                    raise ValueError("captured lifecycle is not an exact runner lifecycle ledger")
                if (
                    lifecycle.get("orchestration_run_id") != run_id
                    or lifecycle.get("current_manifest_digest") != record["manifest_digest"]
                    or lifecycle.get("current_patch_digest") != manifest.get("patch_digest")
                    or lifecycle.get("phase") != "applied"
                    or lifecycle.get("authoritative_validation_count") != 1
                ):
                    raise ValueError("captured lifecycle does not authorize the paired manifest")
                event_fields = {
                    "schema_version", "artifact_kind", "paired_run_id", "paired_workload_digest",
                    "orchestration_run_id", "manifest_digest", "lifecycle_digest",
                    "comparison_side", "runner_revision", "runner_digest",
                    "started_at_unix_ns", "accepted_at_unix_ns",
                }
                if not isinstance(event, dict) or set(event) != event_fields:
                    raise ValueError("captured parent event has an invalid exact schema")
                if (
                    event.get("schema_version") != 1
                    or event.get("artifact_kind") != "parent_acceptance_event"
                    or event.get("paired_run_id") != pair_id
                    or event.get("paired_workload_digest") != workload_digest
                    or event.get("orchestration_run_id") != run_id
                    or event.get("manifest_digest") != record["manifest_digest"]
                    or event.get("lifecycle_digest") != record["lifecycle_digest"]
                    or event.get("comparison_side") != side
                ):
                    raise ValueError("captured parent event does not cross-link runner artifacts")
                runner_revision = event.get("runner_revision")
                runner_digest = event.get("runner_digest")
                if (
                    not isinstance(runner_revision, str)
                    or not re.fullmatch(r"[0-9a-f]{40}", runner_revision)
                    or not isinstance(runner_digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", runner_digest)
                ):
                    raise ValueError("captured parent event has invalid runner provenance")
                runner_blob = subprocess.run(
                    ["git", "show", f"{runner_revision}:scripts/run-sandboxed-plan-worker.py"],
                    cwd=repository_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                )
                runner_ancestry = subprocess.run(
                    ["git", "merge-base", "--is-ancestor", runner_revision, capture_commit],
                    cwd=repository_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                )
                if (
                    runner_blob.returncode != 0
                    or hashlib.sha256(runner_blob.stdout).hexdigest() != runner_digest
                    or runner_ancestry.returncode != 0
                ):
                    raise ValueError("captured runner revision or digest is not repository evidence")
                runner_identities.add((runner_revision, runner_digest))
                started = event.get("started_at_unix_ns")
                accepted = event.get("accepted_at_unix_ns")
                if (
                    not isinstance(started, int) or isinstance(started, bool)
                    or not isinstance(accepted, int) or isinstance(accepted, bool)
                    or started < 0 or accepted < started
                ):
                    raise ValueError("captured parent event timestamps are invalid")
                parsed_sides[side] = {
                    "model_starts": float(model_starts),
                    "time_to_accepted_patch_seconds": (accepted - started) / 1_000_000_000,
                }
                continue
            expected_prefix = {
                "schema_version": 1,
                "paired_run_id": pair_id,
                "paired_workload_digest": workload_digest,
            }
            if manifest != {
                **expected_prefix,
                "artifact_kind": "runner_manifest",
                "telemetry": {"model_starts": record["model_starts"]},
            }:
                raise ValueError("runner manifest does not match paired metrics or provenance")
            if lifecycle != {
                **expected_prefix,
                "artifact_kind": "runner_lifecycle",
                "time_to_accepted_patch_seconds": record["time_to_accepted_patch_seconds"],
            }:
                raise ValueError("runner lifecycle does not match paired metrics or provenance")
            for key in ("model_starts", "time_to_accepted_patch_seconds"):
                value = record[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValueError("paired runner metrics must be finite nonnegative numbers")
            parsed_sides[side] = {
                "model_starts": float(record["model_starts"]),
                "time_to_accepted_patch_seconds": float(record["time_to_accepted_patch_seconds"]),
            }
        if evidence_status == "captured_runner_evidence" and len(runner_identities) != 2:
            raise ValueError("baseline and staged evidence must identify distinct runner revisions")
        paired_metrics.append(parsed_sides)
    if classes != expected_classes:
        raise ValueError("paired runner evidence is missing a fixed scenario class")
    return paired_metrics


def check_orchestration_policy(*, include_holdout: bool = False) -> None:
    policy = read("references/orchestration.md").lower()
    shared_markers = (
        "per-task user instruction",
        "without waiting for a per-task user instruction",
        "repository-wide",
        "independent helper work",
        "main agent owns",
        "expected context reduction",
        "parallelism",
        "review value",
        "repository breadth alone",
        "proactively",
        "short deterministic",
        "cost",
        "external writes",
        "context files read-only",
        "advisory",
        "authorization decisions",
        "secrets",
        "destructive",
        "do not delegate",
        "separate explicit policy",
        "final high-risk",
        "final report",
        "role",
        "write scope",
        "admissible implementation slice",
        "implementation_risk",
        "implementation_ambiguity",
        "spark medium",
        "terra medium",
        "state path outside the repository",
        "orchestration run identifier",
        "symlinked targets or ancestors",
        "skipped known-unavailable starts",
        "finite and nonnegative",
        "prompts, raw output, environment values, or credentials",
        "run-sandboxed-plan-worker.py correct",
        "aggregate patch",
        "at most two correction rounds",
        "rejected patch never touches the source",
        "candidate generation and correction do not run plan validation",
        "parent diff review",
        "critical-invariant review",
        "focused_validation",
        "validation_authority_scope",
        "network-isolated review clone",
        "authoritative",
        "bounded parent implementation",
        "independent change review",
        "at least 30 percent lower median",
        "p95 time no more than 10 percent worse",
    )
    for marker in shared_markers:
        if marker not in policy:
            fail(f"references/orchestration.md missing orchestration marker: {marker}")

    agents = read("AGENTS.md").lower()
    if "references/orchestration.md" not in agents:
        fail("AGENTS.md must reference references/orchestration.md")
    for marker in (
        "references/orchestration.md",
        "completion reporting",
        "final integration",
        "validation acceptance",
        "final ownership",
        "short deterministic commands",
        "external writes",
        "destructive",
        "authorization decisions",
        "per-task user instruction",
        "main session",
        "advisory",
    ):
        if marker not in agents:
            fail(f"AGENTS.md missing orchestration ownership marker: {marker}")

    try:
        fixture = json.loads((ROOT / "tests/fixtures/orchestration/proactive-bounded-subagents.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid orchestration fixture: {exc}")

    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not isinstance(requirements, list) or not isinstance(scenarios, list):
        fail("orchestration fixture must contain requirements and scenarios arrays")
    if not requirements or not any(item.get("critical") is True for item in requirements):
        fail("orchestration requirements need at least one critical requirement")
    requirement_ids: set[str] = set()
    requirement_markers = {
        "R1": ("independently useful", "coordination cost", "repository breadth alone"),
        "R2": ("short deterministic", "direct user clarification", "main session"),
        "R3": ("authorization", "secrets", "external writes", "destructive"),
        "R4": ("helpers were used", "role", "write scope", "acceptance path"),
        "R5": ("write scope", "read-only context"),
        "R6": ("independently reviewable", "validatable", "integration gate"),
        "R7": ("risk", "ambiguity", "spark", "terra", "sol"),
    }
    for requirement in requirements:
        if not isinstance(requirement, dict) or requirement.get("id") is None:
            fail("orchestration requirements must each be an object with an id")
        requirement_id = requirement["id"]
        if not isinstance(requirement_id, str) or not requirement_id or requirement_id in requirement_ids:
            fail("orchestration requirement identifiers must be unique nonblank strings")
        requirement_ids.add(requirement_id)
        if "threshold" not in requirement:
            fail(f"orchestration requirement missing threshold: {requirement.get('id')}")
        requirement_text = f"{requirement.get('threshold', '')} {requirement.get('text', '')}".lower()
        for marker in requirement_markers[requirement_id]:
            if marker not in requirement_text:
                fail(f"orchestration requirement {requirement_id} missing preserved marker: {marker}")
    if requirement_ids != {"R1", "R2", "R3", "R4", "R5", "R6", "R7"}:
        fail("orchestration fixture must preserve R1-R5 and add slice and routing requirements")

    required_classes = {"median", "edge", "negative", "holdout"}
    observed = {item.get("class") for item in scenarios if isinstance(item, dict) and "class" in item}
    if not required_classes.issubset(observed):
        fail(f"orchestration fixture missing scenario classes: {sorted(required_classes - observed)}")

    expected_value_cases = {
        "median-repository-wide-reconciliation": (
            {"independently_useful": True, "expected_benefit": "parallelism", "benefit_exceeds_coordination": True},
            "delegate",
        ),
        "edge-cross-spec-security-review": (
            {"independently_useful": True, "expected_benefit": "review", "benefit_exceeds_coordination": True},
            "delegate-read-only",
        ),
        "negative-deterministic-update": (
            {"independently_useful": False, "expected_benefit": "none", "benefit_exceeds_coordination": False},
            "keep-local",
        ),
        "negative-broad-but-coupled": (
            {"independently_useful": False, "expected_benefit": "repository-breadth-only", "benefit_exceeds_coordination": False},
            "keep-local",
        ),
        "holdout-randomized-boundary-check": (
            {"independently_useful": True, "expected_benefit": "context-reduction", "benefit_exceeds_coordination": True},
            "delegate-read-only",
        ),
    }
    expected_routing_cases = {
        "routing-spark-low-low": (
            {"implementation_risk": "low", "implementation_ambiguity": "low", "preferred_model_override": None, "preferred_reasoning_override": None, "fallback_model_override": None, "fallback_reasoning_override": None},
            {"decision": "run", "preferred_model": "gpt-5.3-codex-spark", "preferred_reasoning": "medium"},
        ),
        "routing-terra-ordinary-low": (
            {"implementation_risk": "ordinary", "implementation_ambiguity": "low", "preferred_model_override": None, "preferred_reasoning_override": None, "fallback_model_override": None, "fallback_reasoning_override": None},
            {"decision": "run", "preferred_model": "gpt-5.6-terra", "preferred_reasoning": "medium"},
        ),
        "routing-absent-defaults": (
            {"implementation_risk": None, "implementation_ambiguity": None, "preferred_model_override": None, "preferred_reasoning_override": None, "fallback_model_override": None, "fallback_reasoning_override": None},
            {"decision": "run", "preferred_model": "gpt-5.6-terra", "preferred_reasoning": "medium"},
        ),
        "routing-risk-high-refusal": (
            {"implementation_risk": "high", "implementation_ambiguity": "low", "preferred_model_override": None, "preferred_reasoning_override": None, "fallback_model_override": None, "fallback_reasoning_override": None},
            {"decision": "refuse", "reason": "implementation-risk-high"},
        ),
        "routing-ambiguity-high-refusal": (
            {"implementation_risk": "low", "implementation_ambiguity": "high", "preferred_model_override": None, "preferred_reasoning_override": None, "fallback_model_override": None, "fallback_reasoning_override": None},
            {"decision": "refuse", "reason": "implementation-ambiguity-high"},
        ),
        "routing-explicit-override": (
            {"implementation_risk": "low", "implementation_ambiguity": "low", "preferred_model_override": "custom-writable", "preferred_reasoning_override": "high", "fallback_model_override": "custom-fallback", "fallback_reasoning_override": "xhigh"},
            {"decision": "run", "preferred_model": "custom-writable", "preferred_reasoning": "high", "fallback_model": "custom-fallback", "fallback_reasoning": "xhigh"},
        ),
        "routing-preferred-sol-refusal": (
            {"implementation_risk": "low", "implementation_ambiguity": "low", "preferred_model_override": "gpt-5.6-sol", "preferred_reasoning_override": "high", "fallback_model_override": None, "fallback_reasoning_override": None},
            {"decision": "refuse", "reason": "preferred-sol-reserved"},
        ),
        "routing-fallback-sol-refusal": (
            {"implementation_risk": "low", "implementation_ambiguity": "low", "preferred_model_override": None, "preferred_reasoning_override": None, "fallback_model_override": "gpt-5.6-sol", "fallback_reasoning_override": "high"},
            {"decision": "refuse", "reason": "fallback-sol-reserved"},
        ),
    }
    expected_ids = set(expected_value_cases) | set(expected_routing_cases)
    scenario_ids: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            fail("orchestration scenario must be an object")
        for key in ("id", "class", "task", "source", "expected"):
            if key not in scenario:
                fail(f"orchestration scenario missing {key}: {scenario}")
        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in scenario_ids:
            fail("orchestration scenario identifiers must be unique nonblank strings")
        scenario_ids.add(scenario_id)
        if scenario_id in expected_value_cases:
            expected_input, expected_result = expected_value_cases[scenario_id]
            if scenario.get("value_gate") != expected_input or scenario.get("expected") != expected_result:
                fail(f"orchestration value-gate scenario has incorrect exact input/result: {scenario_id}")
        elif scenario_id in expected_routing_cases:
            expected_input, expected_result = expected_routing_cases[scenario_id]
            if scenario.get("routing_input") != expected_input or scenario.get("expected") != expected_result:
                fail(f"orchestration routing scenario has incorrect exact input/result: {scenario_id}")
        else:
            fail(f"unexpected orchestration scenario identifier: {scenario_id}")
        if scenario.get("class") == "holdout" and scenario.get("used_for_tuning") is not False:
            fail("orchestration holdout scenario must set used_for_tuning=false")
    if scenario_ids != expected_ids:
        fail(f"orchestration fixture scenario set differs: {sorted(expected_ids - scenario_ids)}")

    staged_path = ROOT / "tests/fixtures/orchestration/staged-acceptance.json"
    try:
        staged = json.loads(staged_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid staged orchestration fixture: {exc}")
    if staged.get("schema_version") != 2 or set(staged) != {
        "schema_version", "requirements", "evidence_file", "holdout_file",
        "performance_claim_status", "measured_evidence_file", "thresholds"
    }:
        fail("staged orchestration fixture has an unsupported schema version")
    staged_requirements = staged.get("requirements")
    thresholds = staged.get("thresholds")
    if not isinstance(staged_requirements, list) or not isinstance(thresholds, dict):
        fail("staged orchestration fixture has an invalid exact top-level shape")
    evidence_scenarios = []
    fixture_keys = ["evidence_file"]
    if include_holdout:
        fixture_keys.append("holdout_file")
    for fixture_key in fixture_keys:
        fixture_name = staged.get(fixture_key)
        if not isinstance(fixture_name, str) or Path(fixture_name).name != fixture_name:
            fail("staged orchestration evidence must name a sibling fixture")
        evidence_path = staged_path.parent / fixture_name
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"invalid staged orchestration event evidence: {exc}")
        if evidence.get("schema_version") != 2 or not isinstance(evidence.get("scenarios"), list):
            fail("staged orchestration event evidence has an invalid schema")
        evidence_scenarios.extend(evidence["scenarios"])
    derived_scenarios = []
    for scenario in evidence_scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {
            "id", "class", "used_for_tuning", "baseline", "rollout_observation"
        }:
            fail("staged orchestration event scenario has an invalid exact shape")
        metrics = []
        for side in ("baseline", "rollout_observation"):
            record = scenario[side]
            required_record = {"source_plan", "start_commit", "accept_commit"}
            required_record |= {"model_start_evidence"} if side == "baseline" else {"events", "unresolved_high_medium_findings"}
            if not isinstance(record, dict) or set(record) != required_record:
                fail("staged orchestration event record is invalid")
            source_plan = record["source_plan"]
            source_path = ROOT / source_plan if isinstance(source_plan, str) else ROOT
            if not source_path.is_file():
                fail("staged orchestration event evidence must cite an existing checked plan")
            commits = []
            for key in ("start_commit", "accept_commit"):
                commit = record[key]
                if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                    fail("staged orchestration evidence commit must be a full object identifier")
                result = subprocess.run(
                    ["git", "show", "-s", "--format=%ct", commit],
                    cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                )
                if result.returncode != 0 or not result.stdout.strip().isdigit():
                    fail("staged orchestration evidence commit is unavailable")
                commits.append(int(result.stdout.strip()))
            started, accepted = commits
            accepted_blob = subprocess.run(
                ["git", "show", f"{record['accept_commit']}:{source_plan}"],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if accepted_blob.returncode != 0 or hashlib.sha256(accepted_blob.stdout).digest() != hashlib.sha256(source_path.read_bytes()).digest():
                fail("staged orchestration checked-plan evidence differs from its accepted commit blob")
            try:
                source_text = accepted_blob.stdout.decode("utf-8")
            except UnicodeDecodeError:
                fail("staged orchestration checked-plan evidence is not UTF-8")
            if accepted < started:
                fail("staged orchestration accepted timestamp precedes start")
            if side == "baseline":
                evidence_kind = record["model_start_evidence"]
                if evidence_kind == "candidate_digests":
                    model_starts = len(set(re.findall(r"[0-9a-f]{64}", source_text)))
                elif evidence_kind == "named_model_starts":
                    model_starts = source_text.count("GPT-5.3-Codex-Spark") + source_text.count("GPT-5.6-Luna")
                else:
                    fail("staged orchestration model-start evidence kind is unknown")
                events = []
            else:
                events = record["events"]
                if events != ["parent_implementation", "authoritative_validation"]:
                    fail("proposed rollout events must match checked parent implementation evidence")
                if "Parent-session" not in source_text or "validation passed" not in source_text.lower():
                    fail("proposed rollout checked plan lacks parent implementation or validation evidence")
                model_starts = 0
            metrics.append({
                "model_starts": model_starts,
                "time_to_accepted_patch_seconds": accepted - started,
                "implementation_generations": events.count("parent_implementation"),
                "known_unavailable_primary_starts": events.count("known_unavailable_primary_start"),
                "authoritative_full_suite_runs": events.count("authoritative_validation"),
                "unresolved_high_medium_findings": record.get("unresolved_high_medium_findings", 0),
            })
        derived_scenarios.append({
            "id": scenario["id"], "class": scenario["class"],
            "used_for_tuning": scenario["used_for_tuning"],
            "baseline": metrics[0], "rollout_observation": metrics[1],
        })
    baseline = {"version": "2026-08-13-plans-062-064-070-v3", "scenarios": derived_scenarios}
    requirement_ids = {item.get("id") for item in staged_requirements if isinstance(item, dict)}
    if len(staged_requirements) != 6 or requirement_ids != {"S1", "S2", "S3", "S4", "S5", "S6"}:
        fail("staged orchestration fixture must preserve all critical requirements")
    if any(
        set(item) != {"id", "critical", "text"}
        or item.get("critical") is not True
        or not isinstance(item.get("text"), str)
        or not item["text"].strip()
        for item in staged_requirements
        if isinstance(item, dict)
    ):
        fail("staged orchestration requirements must have exact critical records")
    staged_scenarios = baseline.get("scenarios")
    if baseline.get("version") != "2026-08-13-plans-062-064-070-v3" or not isinstance(staged_scenarios, list):
        fail("staged orchestration fixture must use the versioned representative baseline")
    expected_staged_ids = {
        "plan-062-equivalent",
        "plan-064-equivalent",
        "plan-070-equivalent",
    }
    if include_holdout:
        expected_staged_ids.add("holdout-coupled-security-slice")
    observed_staged_ids = {item.get("id") for item in staged_scenarios if isinstance(item, dict)}
    observed_staged_classes = {item.get("class") for item in staged_scenarios if isinstance(item, dict)}
    expected_classes = {"median", "edge", "negative"} | ({"holdout"} if include_holdout else set())
    if observed_staged_ids != expected_staged_ids or observed_staged_classes != expected_classes:
        fail("staged orchestration scenarios must preserve exact historical and class coverage")
    tuning = []
    for scenario in staged_scenarios:
        if not isinstance(scenario, dict):
            fail("staged orchestration scenario must be an object")
        if scenario.get("class") == "holdout":
            if scenario.get("used_for_tuning") is not False:
                fail("staged orchestration holdout must remain outside reusable tuning prompts")
        elif scenario.get("used_for_tuning") is not True:
            fail("non-holdout staged orchestration scenarios must be marked for tuning")
        original = scenario.get("baseline")
        rollout = scenario.get("rollout_observation")
        if not isinstance(original, dict) or not isinstance(rollout, dict):
            fail("staged orchestration scenario is missing baseline or rollout metrics")
        for key in ("model_starts", "time_to_accepted_patch_seconds"):
            if not isinstance(original.get(key), (int, float)) or original[key] <= 0:
                fail(f"staged orchestration baseline metric must be positive: {key}")
            if not isinstance(rollout.get(key), (int, float)) or rollout[key] < 0:
                fail(f"staged orchestration rollout metric must be nonnegative: {key}")
        if rollout.get("implementation_generations", 99) > thresholds.get("maximum_implementation_generations"):
            fail("staged orchestration exceeds the implementation-generation budget")
        if rollout.get("known_unavailable_primary_starts", 99) > thresholds.get("maximum_known_unavailable_primary_starts"):
            fail("staged orchestration repeats a known-unavailable primary start")
        if rollout.get("authoritative_full_suite_runs") != thresholds.get("authoritative_full_suite_runs_per_accepted_candidate"):
            fail("staged orchestration must run one authoritative full suite per accepted candidate")
        if rollout.get("unresolved_high_medium_findings") != thresholds.get("maximum_unresolved_high_medium_findings"):
            fail("staged orchestration has unresolved High or Medium findings")
        if scenario.get("used_for_tuning") is True:
            tuning.append(scenario)
    if not tuning:
        fail("staged orchestration fixture has no tuning scenarios")

    def median(values: list[float]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2

    def p95(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]

    minimum_reduction = thresholds.get("minimum_median_reduction_fraction")
    maximum_p95_regression = thresholds.get("maximum_p95_regression_fraction")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in thresholds.values()
    ):
        fail("staged orchestration thresholds must be finite numeric values, not booleans")
    claim_status = staged.get("performance_claim_status")
    if claim_status not in {"measurement_pending", "measured_pass"}:
        fail("staged orchestration performance claim status is invalid")
    if minimum_reduction != 0.3 or maximum_p95_regression != 0.1:
        fail("staged orchestration prospective performance thresholds changed")
    measured_name = staged.get("measured_evidence_file")
    if not isinstance(measured_name, str) or Path(measured_name).name != measured_name:
        fail("measured evidence must name one sibling fixture")
    try:
        paired_metrics = validate_paired_runner_evidence(
            staged_path.parent / measured_name,
            claim_status=claim_status,
        )
    except ValueError as exc:
        fail(str(exc))
    if claim_status == "measured_pass":
        for metric in ("model_starts", "time_to_accepted_patch_seconds"):
            before = [float(item["baseline"][metric]) for item in paired_metrics]
            after = [float(item["staged"][metric]) for item in paired_metrics]
            if median(after) > median(before) * (1 - minimum_reduction):
                fail(f"staged orchestration misses the median reduction threshold: {metric}")
            if p95(after) > p95(before) * (1 + maximum_p95_regression):
                fail(f"staged orchestration exceeds the p95 regression threshold: {metric}")


def check_active_plans() -> None:
    active_dir = ROOT / "docs/plan/active"
    if not active_dir.exists():
        return
    for path in sorted(active_dir.glob("[0-9][0-9][0-9]-*.md")):
        if contains_option_matrix(path.read_text(encoding="utf-8")):
            fail(f"{path.relative_to(ROOT)} contains an option-analysis matrix")


def self_test() -> None:
    good = "review_class: B\n\n## Decisions\n\n1. Use final decisions only.\n"
    bad = """## Decision Audit

1. Storage location
   A: Store the full audit in the active plan.
   B: Store the full audit outside the active plan.

   推奨: B
   理由: Keep active plans executable.
"""
    if contains_option_matrix(good):
        fail("self-test rejected a compact final-decision plan")
    if not contains_option_matrix(bad):
        fail("self-test accepted an option-analysis matrix")

    paired_path = ROOT / "tests/fixtures/orchestration/staged-paired-measured-example.json"
    paired = json.loads(paired_path.read_text(encoding="utf-8"))
    try:
        validate_paired_runner_evidence(paired_path, claim_status="measurement_pending")
    except ValueError as exc:
        fail(f"self-test rejected the repository paired-evidence example: {exc}")

    def write_self_test_fixture(directory: Path, value: dict[str, object]) -> Path:
        shutil.copytree(paired_path.parent / "paired-artifacts", directory / "paired-artifacts")
        candidate = directory / paired_path.name
        candidate.write_text(json.dumps(value), encoding="utf-8")
        return candidate

    with tempfile.TemporaryDirectory(prefix="captured-runner-evidence-") as raw_temp:
        temp_repo = Path(raw_temp)
        fixture_dir = temp_repo / "tests/fixtures/orchestration"
        artifact_dir = fixture_dir / "paired-artifacts"
        artifact_dir.mkdir(parents=True)
        for command in (
            ["git", "init", "-q"],
            ["git", "config", "user.name", "policy-self-test"],
            ["git", "config", "user.email", "policy-self-test@example.invalid"],
        ):
            result = subprocess.run(command, cwd=temp_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode != 0:
                fail(f"self-test could not initialize evidence repository: {result.stderr.decode()}")
        runner_path = temp_repo / "scripts/run-sandboxed-plan-worker.py"
        runner_path.parent.mkdir()
        runner_revisions: dict[str, tuple[str, str]] = {}
        for side, runner_body in (
            ("baseline", "#!/usr/bin/env python3\n# baseline runner\n"),
            ("staged", "#!/usr/bin/env python3\n# staged runner\n"),
        ):
            runner_path.write_text(runner_body, encoding="utf-8")
            for command in (
                ["git", "add", "scripts/run-sandboxed-plan-worker.py"],
                ["git", "commit", "-q", "-m", f"record {side} runner"],
            ):
                result = subprocess.run(command, cwd=temp_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                if result.returncode != 0:
                    fail(f"self-test could not record runner revision: {result.stderr.decode()}")
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=temp_repo, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            ).stdout.strip()
            runner_revisions[side] = (revision, hashlib.sha256(runner_body.encode()).hexdigest())

        def write_capture_artifact(name: str, value: dict[str, object]) -> tuple[str, str]:
            path = artifact_dir / name
            path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
            return f"paired-artifacts/{name}", hashlib.sha256(path.read_bytes()).hexdigest()

        captured_pairs = []
        for scenario_class in ("median", "edge", "negative", "holdout"):
            pair_id = f"captured-{scenario_class}"
            used_for_tuning = scenario_class != "holdout"
            workload_name, workload_digest = write_capture_artifact(
                f"{scenario_class}-workload.json",
                {
                    "schema_version": 1,
                    "scenario_id": pair_id,
                    "class": scenario_class,
                    "used_for_tuning": used_for_tuning,
                },
            )
            sides: dict[str, dict[str, object]] = {}
            for side, model_starts, seconds in (("baseline", 2, 100), ("staged", 1, 70)):
                run_id = f"{pair_id}-{side}"
                patch_digest = hashlib.sha256(run_id.encode()).hexdigest()
                telemetry = {
                    "schema_version": 1,
                    "attempt_durations_seconds": [1.0] * model_starts,
                    "runner_duration_seconds": 2.0,
                    "model_starts": model_starts,
                    "availability_failures": 0,
                    "skipped_known_unavailable_starts": 0,
                    "candidate_generations": 1,
                    "full_validation_count": 0,
                    "authoritative_validation_count": 0,
                    "focused_validation_count": 0,
                    "parent_review_rejections": 0,
                    "correction_round": 0,
                    "implementation_risk": "ordinary",
                    "implementation_ambiguity": "ordinary",
                }
                manifest_name, manifest_digest = write_capture_artifact(
                    f"{scenario_class}-{side}-manifest.json",
                    {
                        "schema_version": 1,
                        "source_head": "0" * 40,
                        "plan_path": "docs/plan/active/example.md",
                        "plan_digest": "1" * 64,
                        "allowed_write_scope": ["scripts/"],
                        "changed_paths": ["scripts/example.py"],
                        "patch_path": "/parent/artifacts/candidate.patch",
                        "patch_digest": patch_digest,
                        "orchestration_run_id": run_id,
                        "lifecycle_state_path": "/parent/state/lifecycle.json",
                        "worker_result": {},
                        "telemetry": telemetry,
                    },
                )
                lifecycle_name, lifecycle_digest = write_capture_artifact(
                    f"{scenario_class}-{side}-lifecycle.json",
                    {
                        "schema_version": 1,
                        "orchestration_run_id": run_id,
                        "current_manifest_digest": manifest_digest,
                        "current_patch_digest": patch_digest,
                        "correction_round": 0,
                        "candidate_generations": 1,
                        "phase": "applied",
                        "focused_required": False,
                        "focused_validation_count": 0,
                        "authoritative_validation_count": 1,
                        "parent_review_rejections": 0,
                    },
                )
                event_name, event_digest = write_capture_artifact(
                    f"{scenario_class}-{side}-event.json",
                    {
                        "schema_version": 1,
                        "artifact_kind": "parent_acceptance_event",
                        "paired_run_id": pair_id,
                        "paired_workload_digest": workload_digest,
                        "orchestration_run_id": run_id,
                        "manifest_digest": manifest_digest,
                        "lifecycle_digest": lifecycle_digest,
                        "comparison_side": side,
                        "runner_revision": runner_revisions[side][0],
                        "runner_digest": runner_revisions[side][1],
                        "started_at_unix_ns": 1_000_000_000,
                        "accepted_at_unix_ns": (seconds + 1) * 1_000_000_000,
                    },
                )
                sides[side] = {
                    "manifest_artifact": manifest_name,
                    "manifest_digest": manifest_digest,
                    "lifecycle_artifact": lifecycle_name,
                    "lifecycle_digest": lifecycle_digest,
                    "event_artifact": event_name,
                    "event_digest": event_digest,
                }
            captured_pairs.append({
                "paired_run_id": pair_id,
                "class": scenario_class,
                "used_for_tuning": used_for_tuning,
                "workload_artifact": workload_name,
                "paired_workload_digest": workload_digest,
                **sides,
            })
        for command in (
            ["git", "add", "tests/fixtures/orchestration/paired-artifacts"],
            ["git", "commit", "-q", "-m", "capture paired runner evidence"],
        ):
            result = subprocess.run(command, cwd=temp_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode != 0:
                fail(f"self-test could not construct captured evidence: {result.stderr.decode()}")
        capture_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=temp_repo, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout.strip()
        captured_path = fixture_dir / "captured.json"
        captured_path.write_text(json.dumps({
            "schema_version": 1,
            "evidence_status": "captured_runner_evidence",
            "capture_commit": capture_commit,
            "pairs": captured_pairs,
        }), encoding="utf-8")
        for command in (
            ["git", "add", "tests/fixtures/orchestration/captured.json"],
            ["git", "commit", "-q", "-m", "index paired runner evidence"],
        ):
            result = subprocess.run(command, cwd=temp_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode != 0:
                fail(f"self-test could not record evidence index: {result.stderr.decode()}")
        try:
            validate_paired_runner_evidence(
                captured_path,
                claim_status="measured_pass",
                repository_root=temp_repo,
            )
        except ValueError as exc:
            fail(f"self-test rejected captured raw runner evidence: {exc}")
        swapped = json.loads(captured_path.read_text(encoding="utf-8"))
        swapped["pairs"][0]["baseline"], swapped["pairs"][0]["staged"] = (
            swapped["pairs"][0]["staged"], swapped["pairs"][0]["baseline"]
        )
        captured_path.write_text(json.dumps(swapped), encoding="utf-8")
        for command in (
            ["git", "add", "tests/fixtures/orchestration/captured.json"],
            ["git", "commit", "-q", "-m", "attempt side swap"],
        ):
            result = subprocess.run(command, cwd=temp_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if result.returncode != 0:
                fail(f"self-test could not record side-swap negative: {result.stderr.decode()}")
        try:
            validate_paired_runner_evidence(
                captured_path,
                claim_status="measured_pass",
                repository_root=temp_repo,
            )
        except ValueError:
            pass
        else:
            fail("self-test accepted baseline/staged artifact swapping")

    invalid_variants = []
    example_claim = copy.deepcopy(paired)
    example_claim["evidence_status"] = "captured_runner_evidence"
    invalid_variants.append(example_claim)
    missing_class = copy.deepcopy(paired)
    missing_class["evidence_status"] = "captured_runner_evidence"
    missing_class["pairs"].pop()
    invalid_variants.append(missing_class)
    bad_digest = copy.deepcopy(paired)
    bad_digest["evidence_status"] = "captured_runner_evidence"
    bad_digest["pairs"][0]["baseline"]["manifest_digest"] = "0" * 64
    invalid_variants.append(bad_digest)
    bad_holdout = copy.deepcopy(paired)
    bad_holdout["evidence_status"] = "captured_runner_evidence"
    bad_holdout["pairs"][-1]["used_for_tuning"] = True
    invalid_variants.append(bad_holdout)
    for index, invalid in enumerate(invalid_variants):
        with tempfile.TemporaryDirectory(prefix="paired-evidence-negative-") as raw_temp:
            candidate = write_self_test_fixture(Path(raw_temp), invalid)
            try:
                validate_paired_runner_evidence(candidate, claim_status="measured_pass")
            except ValueError:
                pass
            else:
                fail(f"self-test accepted invalid paired evidence variant {index}")
    before = [100.0, 100.0, 100.0]
    passing = [70.0, 70.0, 70.0]
    failing = [71.0, 71.0, 71.0]
    if median_for_self_test(passing) > median_for_self_test(before) * 0.7:
        fail("self-test rejected passing paired threshold")
    if median_for_self_test(failing) <= median_for_self_test(before) * 0.7:
        fail("self-test accepted failing paired threshold")


def median_for_self_test(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--include-holdout", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
    check_required_files()
    check_gitignore()
    check_agents_rules()
    check_agent_model_profiles()
    check_sandboxed_worker_fallback()
    check_reusable_skill_parity()
    check_browser_routing()
    check_external_service_policy()
    check_user_communication_contract()
    check_namespaced_documentation_targets()
    check_orchestration_policy(include_holdout=args.include_holdout)
    check_active_plans()
    print("root agent policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
