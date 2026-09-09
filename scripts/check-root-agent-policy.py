#!/usr/bin/env python3
"""Check root-level agent workflow policy for this template repository."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ROOT_ADMISSION_BOUNDARY_PLAN_ID = 264
ADMISSION_FIELDS = (
    "plan_purpose",
    "feasibility_evidence",
    "completion_conditions",
    "completion_witness_map",
)
PLAN_PURPOSE_VALUES = {"implementation"}
FEASIBILITY_EVIDENCE_KINDS = {
    "reproduced_defect",
    "existing_mechanism",
    "bounded_prototype",
    "mechanical_transformation",
}
MAX_FEASIBILITY_EVIDENCE = 8
MAX_COMPLETION_CONDITIONS = 8
FEASIBILITY_EVIDENCE_MAX_BYTES = 400
COMPLETION_CONDITION_MAX_BYTES = 400
ADMISSION_PLACEHOLDER_VALUES = {
    "-",
    "?",
    "n/a",
    "na",
    "none",
    "pending",
    "placeholder",
    "t.b.d.",
    "tbd",
    "todo",
    "unknown",
    "xxx",
}
ADMISSION_LIFECYCLE_PREFIXES = (
    "docs/plan/",
    ".agent-logs/",
    ".agent-artifacts/",
)
ADMISSION_SCALAR_KEYS = {"status", "plan_purpose", "execution_group", "implementation_tier"}
ADMISSION_LIST_KEYS = {
    "acceptance",
    "write_scope",
    "focused_validation",
    "feasibility_evidence",
    "completion_conditions",
    "completion_witness_map",
}
TIER_ONE_VALUE = "1"
PLAN_FILE_RE = re.compile(r"([0-9]{3})-[a-z0-9][a-z0-9-]*\.md")
MATRIX_MARKER_RE = re.compile(r"^\s*(A|B|C|推奨|理由|Recommended|Reason)\s*[:：]")
APPROACH_MARKERS = {"A", "B", "C"}
RATIONALE_MARKERS = {"推奨", "理由", "Recommended", "Reason"}
MATRIX_WINDOW_LINES = 20
REVIEW_FINDING_BUDGETS_HEADING = "### Review-Finding Budgets"
REVIEW_CONTINUATION_CLAUSE_PREFIX = (
    "- A review-budget-exhausted `descope_pending` run with reason "
    "`parent_remediation_budget_exhausted`"
)
REVIEW_CONTINUATION_CLAUSE = (
    REVIEW_CONTINUATION_CLAUSE_PREFIX
    + ", no open writable attempt, and exactly one or two prior formal reviews may "
    "receive one owner-authorized same-plan continuation. Never reopen or modify "
    "the stopped ledger. Create a fresh ledger with `plan-execution-state.py "
    "continue`, bind the complete predecessor-ledger digest and event-chain leaf, "
    "exact unchanged plan path and digest, source HEAD, primary invariant, "
    "implementation mode, and a mode-0600 authorization record."
)
MCP_SCENARIO_IDS = {
    "same-context-success",
    "sandbox-credential-failure-host-success",
    "authenticated-provider-permission-denial",
    "provider-change-after-preflight",
    "command-boundary-change-after-preflight",
    "account-change-after-preflight",
    "credential-source-change-after-preflight",
    "saved-prefix-without-task-authorization",
    "host-preflight-without-project-authorization",
    "identity-read-with-authenticated-premise",
    "identity-read-prerequisite-write-reuse",
    "identity-read-exact-source-mismatch",
    "unavailable-fallback",
    "duplicate-write-prevention",
    "credential-persistence-attempt",
}

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
    ".codex/skills/mcp-ops/references/provider-call-execution-context.md",
    ".codex/skills/plan-archive/SKILL.md",
    ".codex/skills/plan-archive/agents/openai.yaml",
    ".codex/skills/sequential-plan-orchestrator/SKILL.md",
    ".codex/skills/sequential-plan-orchestrator/agents/openai.yaml",
    ".codex/skills/write-for-reader/SKILL.md",
    ".codex/skills/write-for-reader/agents/openai.yaml",
    ".codex/skills/browser-ops/SKILL.md",
    ".codex/skills/browser-ops/agents/openai.yaml",
    ".codex/skills/browser-ops/references/browser-run-policy.md",
    ".codex/skills/natural-japanese/SKILL.md",
    ".codex/skills/natural-japanese/agents/openai.yaml",
    ".codex/skills/natural-japanese/references/workflow.md",
    ".codex/skills/natural-japanese/references/upstream-adaptation.md",
    ".codex/skills/natural-japanese/scripts/check-japanese-prose.py",
    ".codex/skills/natural-japanese/LICENSE",
    ".agents/skills/natural-japanese/SKILL.md",
    ".codex/agents/sequential_plan_worker.toml",
    "docs/agent/spec-index.yaml",
    "docs/agent/SPEC_GIT_RETIREMENT.md",
    "docs/agent/git-retirement.yaml",
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
    "scripts/migrate-sequential-plan-worker.py",
    "scripts/plan_validation_commands.py",
    "scripts/referent-contract.py",
    "scripts/run-sandboxed-plan-worker.py",
    "scripts/plan-execution-state.py",
    "scripts/restructure-plan.py",
    "scripts/sync-plan-to-linear.sh",
    "scripts/validate-changes.py",
    "scripts/update_agent_model_profiles.py",
    "tests/root-plan-lifecycle.sh",
    "tests/test-plan-restructure.py",
    "tests/test-plan-execution-state.py",
    "tests/test-agent-model-profiles.py",
    "tests/fixtures/write-for-reader/scenarios.json",
    "tests/fixtures/mcp-ops/scenarios.json",
    "tests/fixtures/natural-japanese/scenarios.json",
    "tests/fixtures/natural-japanese/evaluator-prompt.md",
    "tests/fixtures/natural-japanese/evaluation-results.json",
    "scripts/natural-japanese-evaluation.py",
    "tests/test-natural-japanese.py",
]

REUSABLE_SKILLS = (
    "decision-audit",
    "define-referents-first",
    "graph-memory",
    "implementation-guidelines",
    "linear-ops",
    "mcp-ops",
    "natural-japanese",
    "plan-archive",
    "sequential-plan-orchestrator",
    "write-for-reader",
)

# --- decision-reuse routing: expectations are owned here, never by the fixture ---
DECISION_REUSE_FIXTURE = "tests/fixtures/agent-policy-routing/scenarios.json"
DECISION_REUSE_REFERENCE = ".codex/skills/decision-audit/references/implementation-preflight.md"
DECISION_REUSE_GENERATED_REFERENCE = (
    ".project-agent-workflow/skills/decision-audit/references/implementation-preflight.md"
)
DECISION_REUSE_AUTHORIZATIONS = (
    "reuse_accepted_decision",
    "require_explicit_authorization",
    "stop_before_repair_classification",
    "stop_for_owner_decision",
)
DECISION_REUSE_SECTIONS = (
    "## Accepted Decision Reuse",
    "## Requirement, Scope, Condition, And Witness Preflight",
    "## Exact Failure Reproduction",
)
# Each required case binds one fixed authorization expectation and the policy
# file that decides it. Neither may be renegotiated by editing the fixture.
DECISION_REUSE_REQUIRED_CASES = {
    "reuse-unchanged-authorized-work": (
        "reuse_accepted_decision",
        ("docs/agent/SPEC_DECISION_AUDIT.md",),
    ),
    "reauthorize-changed-requirements": (
        "require_explicit_authorization",
        ("docs/agent/SPEC_PLAN_WORKFLOW.md",),
    ),
    "reauthorize-changed-safety-conditions": (
        "require_explicit_authorization",
        ("docs/agent/SPEC_SECURITY.md",),
    ),
    "reauthorize-expanded-external-effects": (
        "require_explicit_authorization",
        ("docs/agent/SPEC_SECURITY.md",),
    ),
    "reproduce-before-formal-diagnosis": (
        "stop_before_repair_classification",
        ("docs/agent/SPEC_PLAN_WORKFLOW.md",),
    ),
    "stop-on-exhausted-review-budget": (
        "stop_for_owner_decision",
        ("docs/agent/SPEC_PLAN_WORKFLOW.md",),
    ),
}
DECISION_REUSE_REQUIRED_POLICY_REFERENCES = (
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "docs/agent/SPEC_SECURITY.md",
    "docs/agent/SPEC_DECISION_AUDIT.md",
)
# The routed instruction itself, not just the path. Each entry must appear as a
# whole line, including its exact leading indentation, so neither a negated
# instruction nor a re-indented one that Markdown reads as a code block or as
# foreign list content can satisfy it.
DECISION_REUSE_SKILL_INSTRUCTIONS = {
    ".codex/skills/decision-audit/SKILL.md": (
        "Read `references/implementation-preflight.md` when the audit is about to become"
        " work: when a settled decision would be reopened, before writing long plan prose,"
        " or after a formal validation failure.",
    ),
    ".codex/skills/implementation-guidelines/SKILL.md": (
        "- Read `{reference}` before reopening an already accepted decision and before"
        " writing long plan prose.",
        "- After a formal validation failure, reproduce the exact failure as described in"
        " `{reference}` before proposing a repair.",
    ),
    ".codex/skills/sequential-plan-orchestrator/SKILL.md": (
        "   Read `{reference}` before classifying a repair, before reopening a settled"
        " decision, and before asking for approval that the unchanged authorization"
        " already covers.",
    ),
}

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
    "docs/agent/SPEC_GIT_RETIREMENT.md",
    "docs/agent/git-retirement.yaml",
    "*.backup",
    "decision audit",
    "docs/plan/active",
]

VALIDATION_WITNESS_MIGRATION_MARKER = (
    "validation-witness-migration-provenance-schema: 1"
)
VALIDATION_WITNESS_MIGRATION_POLICY_MARKERS = (
    "original live guardian",
    "256-bit capability",
    "capability commitment",
    "challenge-response",
    "`prepared`",
    "`pending`",
    "`consumed`",
    "`recovering`",
    "same live guardian",
    "one-hour",
    "pre-boundary",
    "socket pathname is not identity evidence",
    "expiry rejects after-stage authorization",
    "verified pre-boundary recovery",
    "product acceptance evidence",
    "validation witness by itself",
    "copying repository and git-local files without the original live guardian fails",
    "unrestricted same-user actor",
)

# The always-loaded entrypoints route to the guardian rule instead of repeating
# it. The route is what an agent reads first, so it must name its destination,
# require the read before the migration step, and refuse a summary substitute.
VALIDATION_WITNESS_MIGRATION_ROUTE_MARKER = (
    "validation-witness migration guardian rule"
)
VALIDATION_WITNESS_MIGRATION_ROUTE_MARKERS = (
    "before any copier v1.4.5 before-update or after-update migration step",
    "read the whole",
    "follow it there",
    "no summary of it authorizes an update",
)
VALIDATION_WITNESS_MIGRATION_ROUTE_DESTINATIONS = {
    "AGENTS.md": "references/orchestration.md",
    "template/.project-agent-workflow/AGENTS.md.jinja": (
        ".project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
    ),
}
# A route long enough to restate the rule would reintroduce the duplicate the
# relocation removed, so the entrypoint route is capped.
VALIDATION_WITNESS_MIGRATION_ROUTE_MAX_BYTES = 300

# Markers and root/generated equality accept a weakening that is applied to
# both sides at once, so the reviewed route and the reviewed guardian statement
# are pinned by digest. Changing either text is intended to fail here and be
# re-reviewed before the digest is re-pinned.
VALIDATION_WITNESS_MIGRATION_ROUTE_SHA256 = (
    "f74585e0aeeecec3ef344bc6867f72f8d565fa808e055b59b53292351c5cdacd"
)
VALIDATION_WITNESS_MIGRATION_POLICY_SHA256 = (
    "9d4234176cb97bd911ceea0f5795524fac81f6c4128d68a5d9d1b1ab17cceb51"
)

# The activation baseline of plan 275. The entrypoints are always loaded, so
# each one is held at or below its reduced size rather than allowed to drift
# back toward the duplicated form.
AGENTS_BASELINE_BYTES = {
    "AGENTS.md": 23719,
    "template/.project-agent-workflow/AGENTS.md.jinja": 21072,
}
AGENTS_MINIMUM_BYTE_REDUCTION = 1000

VALIDATION_WITNESS_MAP_MARKER = "validation_witness_map"

# Markers every witness-map policy statement must carry, whatever depth the
# owning document states the policy at.
VALIDATION_WITNESS_MAP_SHARED_MARKERS = (
    "validation_witness_schema: 1",
    "a new or materially updated",
    "earliest parent-owned",
    "pre-schema project-owned integration plan",
    "replan contract",
    "`replanned`",
    "narrower safe preflight",
)

# The AGENTS statement is the short rule an agent reads first, so it must keep
# the three witness stages and the refusals that make the map fail closed.
VALIDATION_WITNESS_MAP_AGENTS_MARKERS = (
    "static, focused, or authoritative witness",
    "static witness only for its named enforced predicate",
    "reject missing coverage",
    "a focused command labeled authoritative",
    "authoritative-only witness without one bounded reason",
    "never remove or weaken the authoritative `validation` suite",
)

# The orchestration statement is the detailed contract, so it must keep the
# exact witness names and fields the plan command enforces.
VALIDATION_WITNESS_MAP_ORCHESTRATION_MARKERS = (
    "field absence alone never proves legacy provenance",
    "`resolved-context-files`",
    "`focused_validation`",
    "`authoritative_only_reason`",
    "reject missing, duplicate, reordered, stale, unknown, unrelated-static, "
    "or late mappings before candidate execution",
    "never removes, reorders, or weakens the authoritative suite",
)

TIER_ZERO_PAIR_SPECS = (
    "docs/agent/SPEC_PLAN_WORKFLOW.md",
    "template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md",
)

# The mirrored-pair exception counts two physical files as one Tier 0 change,
# so the base Tier 0 conditions must survive it unchanged.
TIER_ZERO_BASE_CONDITIONS = (
    "- tier 0: one file, reversible, already covered by an existing validation "
    "command, with no new external effect and an unchanged security boundary."
)

TIER_ZERO_PAIR_MARKERS = (
    "count one exact mirrored pair as one tier 0 file",
    "every remaining tier 0 condition holds for both files",
    "already exists and is already checked mechanically",
    "is not evidence",
    "require both files to stay covered by an existing validation command",
    "unchanged validation authority, and unchanged meaning",
)

# Each exclusion names one way a mirrored edit stops being mechanical. Dropping
# any of them would silently widen the exception, so all are required.
TIER_ZERO_PAIR_EXCLUSION_MARKERS = (
    "a behavior change",
    "two independent edits carried in one change",
    "reaches only one side or differs in shape between the sides",
    "a counterpart-only branch",
    "a change to a validation definition",
    "a change to what a rule means",
    "escalate every excluded case to the tier it already takes",
    "lowers no review, validation, or security requirement",
)

# The markers above are fragments, so a reworded or inverted sentence could keep
# every one of them while permitting what it must forbid. The whole exception is
# therefore pinned as exact contiguous text, including the escalation bullet that
# closes it, so an inserted, inverted, or qualified sentence fails the check.
TIER_ZERO_PAIR_BLOCK_LINES = (
    "count one exact mirrored pair as one tier 0 file. a single mechanical edit "
    "and the same edit in that file's established counterpart, such as a source "
    "document and its generated copy, stay tier 0 together when every remaining "
    "tier 0 condition holds for both files.",
    "",
    "- admit the pair only on a counterpart relation that already exists and is "
    "already checked mechanically. a correspondence asserted for this change, or "
    "a human claim that two files are the same, is not evidence.",
    "- require both files to stay covered by an existing validation command, with "
    "an unchanged security boundary, unchanged validation authority, and "
    "unchanged meaning. a typo fix, a comment fix, and a formatting fix that "
    "leaves meaning unchanged are the qualifying examples.",
    "- exclude a behavior change, two independent edits carried in one change, an "
    "edit that reaches only one side or differs in shape between the sides, a "
    "change to a counterpart-only branch, a change to a validation definition, "
    "and a change to what a rule means.",
    "- escalate every excluded case to the tier it already takes. the pair "
    "exception widens no other tier 0 condition and lowers no review, validation, "
    "or security requirement.",
    "",
    "- escalate a tier as soon as new evidence crosses its boundary, and treat "
    "the escalation as a plan update rather than a stop.",
)
TIER_ZERO_PAIR_BLOCK = "\n".join(TIER_ZERO_PAIR_BLOCK_LINES)

# Every Tier 0 statement the section may make is accounted for above: the base
# bullet, the three mentions in the exception paragraph, the exception's own
# no-widening clause, and the restructuring-contract bullet. The two remaining
# whole-file mentions are the plan-file exemption and the descope routing rule
# in the Rules section, so a new Tier 0 sentence anywhere in either tier policy
# must be reviewed against this exception before these budgets move.
TIER_ZERO_SECTION_MENTIONS = 6
TIER_ZERO_FILE_MENTIONS = 8

# Substring pinning bounds only the text it names, so prose placed after the
# exception could still qualify it. The exact section bytes are therefore
# digest-bound: any addition, reordering, or rewording inside the tier policy
# fails until it is re-reviewed here. Both specs share one digest because this
# section carries no command path for the generated rewrite to change.
TIER_ZERO_SECTION_DIGEST = (
    "sha256:734d9a1632c0c54710229919359dfc5baf9430f243b07da489ca975501572779"
)


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


def validation_witness_migration_policy_statement(relative: str) -> str:
    # Only the line ending is removed. Leading indentation stays inside the
    # digest so that nesting a top-level mandatory bullet under other content
    # cannot keep the pin green.
    matches = [
        line.rstrip()
        for line in read(relative).splitlines()
        if VALIDATION_WITNESS_MIGRATION_MARKER in line
    ]
    if len(matches) != 1:
        fail(
            f"{relative} must contain exactly one validation-witness migration "
            "policy statement"
        )
    statement = matches[0]
    lowered = statement.lower()
    for marker in VALIDATION_WITNESS_MIGRATION_POLICY_MARKERS:
        if marker not in lowered:
            fail(f"{relative} missing validation-witness migration marker: {marker}")
    # The digest covers the exact reviewed bytes; lowercasing before hashing
    # would accept a synchronized change to a case-sensitive lifecycle token.
    digest = hashlib.sha256(statement.encode("utf-8")).hexdigest()
    if digest != VALIDATION_WITNESS_MIGRATION_POLICY_SHA256:
        fail(
            f"{relative} validation-witness migration policy changed without "
            f"re-reviewing the pinned statement: {digest}"
        )
    return statement


def validation_witness_migration_route(relative: str) -> str:
    text = read(relative)
    if VALIDATION_WITNESS_MIGRATION_MARKER in text:
        fail(
            f"{relative} must route to the validation-witness migration policy "
            "instead of restating it"
        )
    matches = [
        line.rstrip()
        for line in text.splitlines()
        if VALIDATION_WITNESS_MIGRATION_ROUTE_MARKER in line.lower()
    ]
    if len(matches) != 1:
        fail(
            f"{relative} must contain exactly one validation-witness migration "
            "route"
        )
    route = matches[0]
    size = len(route.encode("utf-8"))
    if size > VALIDATION_WITNESS_MIGRATION_ROUTE_MAX_BYTES:
        fail(
            f"{relative} validation-witness migration route is {size} bytes, "
            f"over {VALIDATION_WITNESS_MIGRATION_ROUTE_MAX_BYTES}"
        )
    destination = VALIDATION_WITNESS_MIGRATION_ROUTE_DESTINATIONS[relative]
    if destination not in route:
        fail(
            f"{relative} validation-witness migration route does not name "
            f"{destination}"
        )
    lowered = route.lower()
    for marker in VALIDATION_WITNESS_MIGRATION_ROUTE_MARKERS:
        if marker not in lowered:
            fail(
                f"{relative} missing validation-witness migration route marker: "
                f"{marker}"
            )
    # Only the exact case-sensitive destination is substituted, so a route that
    # names an unreachable variant of the path fails instead of normalizing away.
    normalized = route.replace(destination, "<destination>")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if digest != VALIDATION_WITNESS_MIGRATION_ROUTE_SHA256:
        fail(
            f"{relative} validation-witness migration route changed without "
            f"re-reviewing the pinned route: {digest}"
        )
    return normalized


def check_agents_entrypoint_size() -> None:
    for relative, baseline in AGENTS_BASELINE_BYTES.items():
        size = len(read(relative).encode("utf-8"))
        allowed = baseline - AGENTS_MINIMUM_BYTE_REDUCTION
        if size > allowed:
            fail(
                f"{relative} is {size} bytes; the routed entrypoint must stay at "
                f"or below {allowed}"
            )


def check_validation_witness_migration_policy() -> None:
    root_agents = validation_witness_migration_route("AGENTS.md")
    template_agents = validation_witness_migration_route(
        "template/.project-agent-workflow/AGENTS.md.jinja"
    )
    if root_agents != template_agents:
        fail("root/generated AGENTS validation-witness migration route differs")

    root_orchestration = validation_witness_migration_policy_statement(
        "references/orchestration.md"
    )
    template_orchestration = validation_witness_migration_policy_statement(
        "template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
    )
    if root_orchestration != template_orchestration:
        fail("root/generated orchestration validation-witness migration policy differs")


def validation_witness_map_policy_statement(
    relative: str, markers: tuple[str, ...]
) -> str:
    matches = [
        line.strip().lower()
        for line in read(relative).splitlines()
        if VALIDATION_WITNESS_MAP_MARKER in line
    ]
    if len(matches) != 1:
        fail(
            f"{relative} must contain exactly one validation-witness map policy statement"
        )
    statement = matches[0]
    for marker in (*VALIDATION_WITNESS_MAP_SHARED_MARKERS, *markers):
        if marker not in statement:
            fail(f"{relative} missing validation-witness map marker: {marker}")
    return statement


def check_validation_witness_map_policy() -> None:
    """Keep the root and generated witness-map policy one statement.

    The generated policy is already bound by `check-copier-template.py`, and
    the root policy is only searched for a few loose markers. Nothing compared
    the two, so either side could drop the refusals that make the map fail
    closed while every check still passed. Isolating the single statement in
    each document and comparing it makes that drift a validation failure.
    """

    root_agents = validation_witness_map_policy_statement(
        "AGENTS.md", VALIDATION_WITNESS_MAP_AGENTS_MARKERS
    )
    template_agents = validation_witness_map_policy_statement(
        "template/.project-agent-workflow/AGENTS.md.jinja",
        VALIDATION_WITNESS_MAP_AGENTS_MARKERS,
    )
    if root_agents != template_agents:
        fail("root/generated AGENTS validation-witness map policy differs")

    root_orchestration = validation_witness_map_policy_statement(
        "references/orchestration.md",
        VALIDATION_WITNESS_MAP_ORCHESTRATION_MARKERS,
    )
    template_orchestration = validation_witness_map_policy_statement(
        "template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md",
        VALIDATION_WITNESS_MAP_ORCHESTRATION_MARKERS,
    )
    if root_orchestration != template_orchestration:
        fail("root/generated orchestration validation-witness map policy differs")


def implementation_tiers_section(relative: str) -> str:
    matches = re.findall(
        r"^#{2,3} Implementation Tiers\n(.*?)(?=^#{2,3} |\Z)",
        read(relative),
        re.MULTILINE | re.DOTALL,
    )
    if len(matches) != 1:
        fail(f"{relative} must contain exactly one Implementation Tiers section")
    return matches[0]


def check_tier_zero_pair_policy() -> None:
    """Keep the mirrored Tier 0 exception bounded in both tier policies.

    Root policy requires every root change to be mirrored into its template
    counterpart, so a one-file Tier 0 bound would push a typo fix into a full
    plan. The exception counts one exact mirrored pair as one file, which only
    stays safe while its eligibility conditions and its exclusions both hold.
    Marker presence alone would accept an inverted or qualified restatement, and
    pinned prose alone would accept a widening sentence placed after it, so the
    whole section is digest-bound and Tier 0 mentions are budgeted. The named
    markers stay because they report which condition or exclusion was lost.

    A paraphrase that never writes "Tier 0" is outside what any text check can
    decide; the budget bounds literal restatements, not prose in general.
    """

    for relative in TIER_ZERO_PAIR_SPECS:
        raw = implementation_tiers_section(relative)
        section = raw.lower()
        if section.count(TIER_ZERO_BASE_CONDITIONS) != 1:
            fail(f"{relative} lost the unchanged Tier 0 base conditions")
        for marker in TIER_ZERO_PAIR_MARKERS:
            if section.count(marker) != 1:
                fail(f"{relative} missing Tier 0 mirrored-pair condition: {marker}")
        for marker in TIER_ZERO_PAIR_EXCLUSION_MARKERS:
            if section.count(marker) != 1:
                fail(f"{relative} missing Tier 0 mirrored-pair exclusion: {marker}")
        if section.count(TIER_ZERO_PAIR_BLOCK) != 1:
            fail(f"{relative} must state the Tier 0 mirrored-pair exception exactly")
        mentions = section.count("tier 0")
        if mentions != TIER_ZERO_SECTION_MENTIONS:
            fail(
                f"{relative} states {mentions} Tier 0 rules in its tier policy, "
                f"not the reviewed {TIER_ZERO_SECTION_MENTIONS}"
            )
        file_mentions = read(relative).lower().count("tier 0")
        if file_mentions != TIER_ZERO_FILE_MENTIONS:
            fail(
                f"{relative} states {file_mentions} Tier 0 rules in total, "
                f"not the reviewed {TIER_ZERO_FILE_MENTIONS}"
            )
        digest = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if digest != TIER_ZERO_SECTION_DIGEST:
            fail(f"{relative} tier policy changed without re-reviewing the Tier 0 pair")


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
        "def validation_failure_identity",
        '"failure": failure',
        "network_enabled=False",
        '"prepare-dependencies"',
        '"--dependency-snapshot"',
        "def verify_dependency_snapshot",
        "read_only_shadows",
        "WORKER_CONTRACT_SCHEMA_VERSION",
        "def derive_worker_contract",
        "def verify_worker_contract",
        "def derive_repository_identity",
        "worker_attempt_label",
        "require_safe_delegated_write_scope",
        "NEW_FILE_ROOT",
        "SANDBOXED_PLAN_WORKER_CONTRACT first",
    )
    for marker in runner_markers:
        if marker not in runner:
            fail(f"sandboxed plan worker missing model fallback marker: {marker}")

    execution_state = read("scripts/plan-execution-state.py")
    for marker in (
        '"diagnosis_required"', "MAX_DIAGNOSIS_ATTEMPTS",
        '"authoritative_failure"', '"failure_diagnosis"',
        "def load_authoritative_failure", "def load_diagnosis_evidence",
        '"diagnosis_read"', '"repair_plan"',
        "def review_candidate_identity_digest", "def candidate_review_identity",
        '"--candidate-manifest"',
        "checked parent-direct diff differs from the reviewed target",
        "def initialize_reviewer_registry", "def admit_reviewer_session",
        '"registry-init"', '"--reviewer-registry"',
        '"reviewer_registry"', '"event_chain_digest"',
        '"execution_genesis_digest"', '"predecessor_checkpoint_bound"',
        '"migrate-checkpoint"', '"session_checkpoint_migrated"',
        "MAX_MIGRATION_COMPATIBILITY_EVENTS", "reserved event capacity",
    ):
        if marker not in execution_state:
            fail(f"plan execution state missing confirmed-diagnosis marker: {marker}")

    for relative in (
        "AGENTS.md",
        "references/orchestration.md",
        ".codex/skills/sequential-plan-orchestrator/SKILL.md",
    ):
        text = read(relative).lower()
        for marker in ("gpt-5.3-codex-spark", "gpt-5.6-luna", "max", "usage limit", "rate limit"):
            if marker not in text:
                fail(f"{relative} missing sandboxed model fallback policy marker: {marker}")
        for marker in (
            "admitted patch digest", "mutable lifecycle",
            "reviewer session registry", "event-chain digest", "execution genesis",
            "schema-1 checkpoint",
        ):
            if marker not in text:
                fail(f"{relative} missing candidate review identity marker: {marker}")
    for relative in (
        "references/orchestration.md",
        ".codex/skills/sequential-plan-orchestrator/SKILL.md",
    ):
        text = read(relative).lower()
        for marker in (
            "active-plan index",
            "index/file status mismatch",
            "duplicate ids or paths",
            "immutable identities and archive ordering",
            "lower-numbered deferred plan does not block",
        ):
            if marker not in text:
                fail(f"{relative} missing runnable-plan selection marker: {marker}")


def check_reusable_skill_parity() -> None:
    for skill in REUSABLE_SKILLS:
        relative_files = ["SKILL.md", "agents/openai.yaml"]
        if skill == "mcp-ops":
            relative_files.append("references/provider-call-execution-context.md")
        if skill == "decision-audit":
            relative_files.append("references/implementation-preflight.md")
        if skill == "natural-japanese":
            relative_files.extend(
                [
                    "references/workflow.md",
                    "references/upstream-adaptation.md",
                    "scripts/check-japanese-prose.py",
                    "LICENSE",
                ]
            )
        for relative in relative_files:
            root_path = ROOT / ".codex" / "skills" / skill / relative
            template_path = ROOT / "template" / ".project-agent-workflow" / "skills" / skill / relative
            if not root_path.is_file() or not template_path.is_file():
                fail(f"missing reusable skill file for parity: {skill}/{relative}")
            template_text = template_path.read_text(encoding="utf-8")
            if skill == "natural-japanese":
                template_text = template_text.replace(
                    ".project-agent-workflow/skills/natural-japanese/",
                    ".codex/skills/natural-japanese/",
                )
            template_text = template_text.replace(
                ".project-agent-workflow/skills/", ".codex/skills/"
            ).replace(
                ".project-agent-workflow/", ""
            ).replace(".agents/skills/", ".codex/skills/")
            if root_path.read_text(encoding="utf-8") != template_text:
                fail(f"root/template reusable skill drift: {skill}/{relative}")


def decision_reuse_instruction_lines(relative: str, reference: str) -> tuple[str, ...]:
    return tuple(
        instruction.format(reference=reference)
        for instruction in DECISION_REUSE_SKILL_INSTRUCTIONS[relative]
    )


# A routed instruction only counts when Markdown renders it as an instruction,
# and the constructs that can swallow a line depend on container context that
# spans several lines. Approximating that context failed repeatedly: a fence
# indented past the margin, a tab-indented fence inside a list item, and a raw
# HTML block opened as list content each hid a byte-identical route. Rather than
# keep enumerating hiding places, a file that carries a routed instruction is
# required to be plain prose, so the tokens that could open such a context are
# refused wherever they appear.
MARKDOWN_FENCE_TOKEN_RE = re.compile(r"`{3,}|~{3,}")
MARKDOWN_CONTAINER_PREFIX_RE = re.compile(r"^ *(?:> ?|(?:[-*+]|\d{1,9}[.)])(?: +|$))")


def markdown_block_content(line: str) -> str:
    """Return the line with its blockquote and list markers removed."""

    current = line
    while True:
        match = MARKDOWN_CONTAINER_PREFIX_RE.match(current)
        if match is None:
            return current.lstrip(" ")
        current = current[match.end():]


def markdown_prose_defects(text: str) -> list[str]:
    """Report the constructs that stop this text from being plain prose.

    Without any code fence token there is no fenced block in any container,
    without a tab there is no ambiguous indentation, and without a comment
    marker or a block that opens with a raw HTML tag there is no HTML block.
    What remains renders every line as text, so a line that matches an expected
    instruction is that instruction.
    """

    defects: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if "\t" in raw:
            defects.append(f"line {number} contains a tab, which shifts block indentation")
        if MARKDOWN_FENCE_TOKEN_RE.search(line):
            defects.append(f"line {number} contains a code fence token")
        if "<!--" in line:
            defects.append(f"line {number} contains an HTML comment marker")
        elif markdown_block_content(line).startswith("<"):
            defects.append(f"line {number} opens a raw HTML block")
    return defects


def markdown_prose_lines(text: str) -> set[str]:
    """Return the lines of a text already proven to be plain prose.

    Only trailing whitespace is normalized. Leading indentation stays part of
    the line because Markdown gives it meaning.
    """

    return {line.rstrip() for line in text.splitlines()}


def require_markdown_prose(relative: str, text: str) -> None:
    for defect in markdown_prose_defects(text):
        fail(f"{relative} must stay plain Markdown prose to carry a routed instruction: {defect}")


def require_decision_reuse_instructions(relative: str, reference: str) -> None:
    text = read(relative)
    require_markdown_prose(relative, text)
    lines = markdown_prose_lines(text)
    for instruction in decision_reuse_instruction_lines(relative, reference):
        if instruction not in lines:
            fail(f"{relative} does not carry the routed preflight instruction: {instruction}")


def check_decision_reuse_scenarios() -> None:
    """Check the fixed decision-reuse fixture against checker-owned expectations.

    The fixture supplies cases; it never supplies the expectations those cases
    are judged against. These are structural predicates about the fixture and
    the routed instructions. They do not measure how an agent behaves.
    """

    relative = DECISION_REUSE_FIXTURE
    path = ROOT / relative
    if not path.is_file():
        fail(f"missing decision-reuse scenario fixture: {relative}")
    try:
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{relative} is not readable JSON: {error}")
    if not isinstance(fixture, dict):
        fail(f"{relative} must be a JSON object")
    scenarios = fixture.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        fail(f"{relative} must declare a non-empty scenarios list")
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            fail(f"{relative} scenario {index} is not an object")
        if not isinstance(scenario.get("id"), str) or not scenario["id"].strip():
            fail(f"{relative} scenario {index} needs a non-empty string id")

    block = fixture.get("decision_reuse")
    if not isinstance(block, dict):
        fail(f"{relative} must declare a decision_reuse block")

    declared = {
        "reference": DECISION_REUSE_REFERENCE,
        "generated_reference": DECISION_REUSE_GENERATED_REFERENCE,
    }
    for key, expected in declared.items():
        if block.get(key) != expected:
            fail(f"{relative} decision_reuse {key} must be {expected}")
    declared_sets = {
        "authorization_values": set(DECISION_REUSE_AUTHORIZATIONS),
        "required_case_ids": set(DECISION_REUSE_REQUIRED_CASES),
        "required_policy_references": set(DECISION_REUSE_REQUIRED_POLICY_REFERENCES),
        "linking_skills": set(DECISION_REUSE_SKILL_INSTRUCTIONS),
    }
    for key, expected_set in declared_sets.items():
        value = block.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            fail(f"{relative} decision_reuse {key} must be a list of strings")
        if set(value) != expected_set:
            fail(
                f"{relative} decision_reuse {key} must be exactly "
                f"{sorted(expected_set)}"
            )

    cases: dict[str, dict] = {}
    for scenario in scenarios:
        if scenario.get("kind") != "decision-reuse":
            continue
        case_id = scenario["id"]
        if case_id in cases:
            fail(f"{relative} declares duplicate decision-reuse case: {case_id}")
        cases[case_id] = scenario
    missing = sorted(set(DECISION_REUSE_REQUIRED_CASES) - set(cases))
    if missing:
        fail(f"{relative} missing required decision-reuse cases: {', '.join(missing)}")

    for case_id, scenario in sorted(cases.items()):
        authorization = scenario.get("authorization")
        if authorization not in DECISION_REUSE_AUTHORIZATIONS:
            fail(
                f"{relative} case {case_id} has an unknown authorization expectation: "
                f"{authorization!r}"
            )
        for key in ("task", "expected"):
            if not isinstance(scenario.get(key), str) or not scenario[key].strip():
                fail(f"{relative} case {case_id} missing {key}")
        for key in ("required_before_action", "critical_failures", "policy_references"):
            value = scenario.get(key)
            if not isinstance(value, list) or not value:
                fail(f"{relative} case {case_id} missing {key}")
            if not all(isinstance(item, str) and item.strip() for item in value):
                fail(f"{relative} case {case_id} has a malformed {key} entry")
        for policy in scenario["policy_references"]:
            if not (ROOT / policy).is_file():
                fail(f"{relative} case {case_id} names an unresolved policy reference: {policy}")

    for case_id, (authorization, policies) in sorted(DECISION_REUSE_REQUIRED_CASES.items()):
        scenario = cases[case_id]
        if scenario["authorization"] != authorization:
            fail(
                f"{relative} case {case_id} must expect {authorization}, "
                f"not {scenario['authorization']}"
            )
        absent = [policy for policy in policies if policy not in scenario["policy_references"]]
        if absent:
            fail(
                f"{relative} case {case_id} must cite {', '.join(absent)} as its "
                "deciding policy"
            )

    for target in (DECISION_REUSE_REFERENCE, "template/" + DECISION_REUSE_GENERATED_REFERENCE):
        if not (ROOT / target).is_file():
            fail(f"missing implementation preflight reference: {target}")
    preflight = read(DECISION_REUSE_REFERENCE)
    require_markdown_prose(DECISION_REUSE_REFERENCE, preflight)
    preflight_lines = markdown_prose_lines(preflight)
    for section in DECISION_REUSE_SECTIONS:
        if section not in preflight_lines:
            fail(f"{DECISION_REUSE_REFERENCE} missing section: {section}")

    for skill in sorted(DECISION_REUSE_SKILL_INSTRUCTIONS):
        if not (ROOT / skill).is_file():
            fail(f"missing decision-reuse linking skill: {skill}")
        require_decision_reuse_instructions(skill, DECISION_REUSE_REFERENCE)


def check_natural_japanese_contract() -> None:
    agents = read("AGENTS.md")
    for marker in (
        ".codex/skills/natural-japanese/SKILL.md",
        "Japanese replies",
        "facts, quotations, uncertainty",
        "requested form",
        "document purpose",
    ):
        if marker not in agents:
            fail(f"AGENTS.md missing natural-japanese routing marker: {marker}")

    bridge = read(".agents/skills/natural-japanese/SKILL.md")
    if ".codex/skills/natural-japanese/SKILL.md" not in bridge:
        fail("root natural-japanese discovery bridge does not point at the managed skill")

    workflow = read(".codex/skills/natural-japanese/references/workflow.md")
    for marker in (
        "## Short Reply",
        "Do not run a subprocess.",
        "## Japanese File Work",
        "at most once per draft",
        "## Important Long-Form Prose",
        "independent reader review",
        "## Protected Content",
        "Never invent experience",
        "## Non-Use Boundary",
        "code-only changes",
    ):
        if marker not in workflow:
            fail(f"natural-japanese workflow missing marker: {marker}")

    provenance = read(".codex/skills/natural-japanese/references/upstream-adaptation.md")
    for marker in (
        "https://github.com/coji/natural-japanese",
        "v1.5.0",
        "21e632661a910bf97289c501089ad11eb8b4d85f",
        "License: MIT",
        "runtime downloads",
        "future upstream update requires an explicit review",
    ):
        if marker not in provenance:
            fail(f"natural-japanese provenance missing marker: {marker}")

    if "Copyright (c) 2026 coji" not in read(".codex/skills/natural-japanese/LICENSE"):
        fail("natural-japanese upstream MIT notice is missing")
    helper = ROOT / ".codex/skills/natural-japanese/scripts/check-japanese-prose.py"
    if helper.stat().st_mode & 0o111 == 0:
        fail("natural-japanese lint helper must be executable")
    helper_text = helper.read_text(encoding="utf-8").lower()
    for forbidden in ("subprocess", "urllib", "requests", "sudachi"):
        if forbidden in helper_text:
            fail(f"natural-japanese lint helper must remain dependency-free: {forbidden}")


def _mcp_exact_mapping(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _mcp_nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _mcp_identity_project_authorized(value: object) -> tuple[bool, dict]:
    authorization = _mcp_exact_mapping(
        value,
        {
            "provider", "access", "operation", "target", "payload", "effects",
            "current_task_requires", "authenticated_result_required", "prerequisite_scope",
        },
        "identity_read_project_authorization",
    )
    authorized = (
        _mcp_nonblank(authorization["provider"])
        and authorization["access"] == "read"
        and authorization["operation"] == "identity.read"
        and _mcp_nonblank(authorization["target"])
        and _mcp_nonblank(authorization["payload"])
        and authorization["effects"] == ["ordinary"]
        and authorization["current_task_requires"] is True
        and authorization["authenticated_result_required"] is False
        and authorization["prerequisite_scope"] == "identity-read-only"
    )
    return authorized, authorization


def _mcp_host_execution_approved(value: object) -> bool:
    approval = _mcp_exact_mapping(
        value,
        {"required", "approved", "authorizes_provider_effects"},
        "identity_read_host_execution_approval",
    )
    return (
        approval["authorizes_provider_effects"] is False
        and (approval["required"] is False or approval["approved"] is True)
    )


def _evaluate_mcp_identity_read(conditions: dict) -> str:
    host_variant = "sandbox_local_credential_source" in conditions
    expected_keys = {
        "identity_read_project_authorization",
        "identity_read_host_execution_approval",
        "identity_read_result",
        "intended_call_authorization_request",
    }
    if host_variant:
        expected_keys.update({
            "sandbox_local_credential_source", "user_reports_login_elsewhere",
            "host_credential_source",
        })
    else:
        expected_keys.add("local_credential_source")
    _mcp_exact_mapping(conditions, expected_keys, "identity-read scenario conditions")

    project_authorized, authorization = _mcp_identity_project_authorized(
        conditions["identity_read_project_authorization"]
    )
    if not project_authorized or not _mcp_host_execution_approved(
        conditions["identity_read_host_execution_approval"]
    ):
        return "deny_provider_preflight"

    source_keys = {"exact_binding", "class", "available", "credential_material_read"}
    if host_variant:
        sandbox_source = _mcp_exact_mapping(
            conditions["sandbox_local_credential_source"], source_keys, "sandbox credential source"
        )
        if (
            sandbox_source["available"] is not False
            or sandbox_source["credential_material_read"] is not False
            or conditions["user_reports_login_elsewhere"] is not True
        ):
            return "fail_closed_report_credential_unavailable"
        selected_source = _mcp_exact_mapping(
            conditions["host_credential_source"], source_keys, "host credential source"
        )
    else:
        selected_source = _mcp_exact_mapping(
            conditions["local_credential_source"], source_keys, "local credential source"
        )
    if selected_source["credential_material_read"] is not False:
        return "deny_credential_persistence"
    if selected_source["available"] is not True:
        return "fail_closed_report_credential_unavailable"
    if not _mcp_nonblank(selected_source["exact_binding"]) or not _mcp_nonblank(selected_source["class"]):
        return "fail_closed_report_context_binding_missing"

    result = _mcp_exact_mapping(
        conditions["identity_read_result"],
        {"provider_authenticated", "account", "evidence_context"},
        "identity_read_result",
    )
    if result["provider_authenticated"] is not True:
        return "fail_closed_report_authentication_inconclusive"
    if not _mcp_nonblank(result["account"]):
        return "fail_closed_report_context_binding_missing"
    evidence = _mcp_exact_mapping(
        result["evidence_context"],
        {"provider", "command_boundary", "exact_credential_source", "credential_source_class"},
        "identity read evidence context",
    )
    intended = _mcp_exact_mapping(
        conditions["intended_call_authorization_request"],
        {
            "provider", "operation", "target", "payload", "effects", "current_task_requires",
            "command_boundary", "exact_credential_source",
        },
        "intended_call_authorization_request",
    )
    concrete_bindings = (
        evidence["provider"],
        evidence["command_boundary"],
        evidence["exact_credential_source"],
        evidence["credential_source_class"],
        intended["provider"],
        intended["command_boundary"],
        intended["exact_credential_source"],
    )
    if any(not _mcp_nonblank(value) for value in concrete_bindings):
        return "fail_closed_report_context_binding_missing"
    context_matches = (
        evidence["provider"] == authorization["provider"] == intended["provider"]
        and evidence["command_boundary"] == intended["command_boundary"]
        and evidence["exact_credential_source"]
        == selected_source["exact_binding"]
        == intended["exact_credential_source"]
        and evidence["credential_source_class"] == selected_source["class"]
    )
    if not context_matches:
        return "repeat_preflight_and_fresh_authorization"
    if (
        not _mcp_nonblank(intended["operation"])
        or not _mcp_nonblank(intended["target"])
        or not _mcp_nonblank(intended["payload"])
        or intended["effects"] != ["ordinary"]
        or intended["current_task_requires"] is not True
    ):
        return "deny_intended_call"
    return "run_fresh_authorization_then_call"


def evaluate_mcp_scenario(scenario: object) -> str:
    item = _mcp_exact_mapping(
        scenario,
        {"id", "class", "used_for_tuning", "conditions", "expected"},
        "mcp scenario",
    )
    scenario_id = item["id"]
    conditions = item["conditions"]
    if not isinstance(conditions, dict):
        raise ValueError("mcp scenario conditions must be a mapping")
    if scenario_id in {
        "same-context-success",
        "sandbox-credential-failure-host-success",
        "identity-read-exact-source-mismatch",
    }:
        return _evaluate_mcp_identity_read(conditions)
    if scenario_id in {
        "host-preflight-without-project-authorization",
        "identity-read-with-authenticated-premise",
        "identity-read-prerequisite-write-reuse",
    }:
        _mcp_exact_mapping(
            conditions,
            {"identity_read_project_authorization", "identity_read_host_execution_approval"},
            f"{scenario_id} conditions",
        )
        authorized, _ = _mcp_identity_project_authorized(
            conditions["identity_read_project_authorization"]
        )
        host_approved = _mcp_host_execution_approved(
            conditions["identity_read_host_execution_approval"]
        )
        return "run_provider_identity_read" if authorized and host_approved else "deny_provider_preflight"
    if scenario_id == "authenticated-provider-permission-denial":
        _mcp_exact_mapping(
            conditions,
            {"credential_available", "provider_authenticated", "provider_permission", "fallback_evidence_available"},
            f"{scenario_id} conditions",
        )
        return (
            "report_provider_permission_denial"
            if conditions["credential_available"] is True
            and conditions["provider_authenticated"] is True
            and conditions["provider_permission"] == "denied"
            else "classify_authentication_failure"
        )
    if scenario_id == "provider-change-after-preflight":
        _mcp_exact_mapping(
            conditions,
            {"preflight_provider", "call_provider", "account_changed", "exact_credential_source_changed", "command_boundary_changed"},
            f"{scenario_id} conditions",
        )
        return (
            "repeat_preflight_and_fresh_authorization"
            if conditions.get("preflight_provider") != conditions.get("call_provider")
            else "continue_context_check"
        )
    if scenario_id == "command-boundary-change-after-preflight":
        _mcp_exact_mapping(
            conditions,
            {"provider_changed", "account_changed", "exact_credential_source_changed", "preflight_command_boundary", "call_command_boundary"},
            f"{scenario_id} conditions",
        )
        return (
            "repeat_preflight_and_fresh_authorization"
            if conditions.get("preflight_command_boundary") != conditions.get("call_command_boundary")
            else "continue_context_check"
        )
    if scenario_id == "account-change-after-preflight":
        _mcp_exact_mapping(
            conditions,
            {"provider_changed", "preflight_account", "call_account", "exact_credential_source_changed", "command_boundary_changed"},
            f"{scenario_id} conditions",
        )
        return (
            "repeat_preflight_and_fresh_authorization"
            if conditions.get("preflight_account") != conditions.get("call_account")
            else "continue_context_check"
        )
    if scenario_id == "credential-source-change-after-preflight":
        _mcp_exact_mapping(
            conditions,
            {"provider_changed", "account_changed", "preflight_exact_credential_source", "call_exact_credential_source", "credential_source_class", "command_boundary_changed"},
            f"{scenario_id} conditions",
        )
        return (
            "repeat_preflight_and_fresh_authorization"
            if conditions.get("preflight_exact_credential_source")
            != conditions.get("call_exact_credential_source")
            else "continue_context_check"
        )
    if scenario_id == "saved-prefix-without-task-authorization":
        _mcp_exact_mapping(
            conditions,
            {"host_execution_approved", "saved_command_prefix_approved", "task_authorized", "access"},
            f"{scenario_id} conditions",
        )
        return (
            "deny_external_write"
            if conditions == {
                "host_execution_approved": True,
                "saved_command_prefix_approved": True,
                "task_authorized": False,
                "access": "write",
            }
            else "evaluate_exact_external_call"
        )
    if scenario_id == "unavailable-fallback":
        _mcp_exact_mapping(
            conditions,
            {"provider_backend_configured", "configured_fallback_available"},
            f"{scenario_id} conditions",
        )
        return (
            "fail_closed_report_backend_unavailable"
            if conditions.get("provider_backend_configured") is False
            and conditions.get("configured_fallback_available") is False
            else "use_configured_fallback"
        )
    if scenario_id == "duplicate-write-prevention":
        _mcp_exact_mapping(
            conditions,
            {"prior_write_result", "exact_remote_state_read_supported", "intended_state_already_exists"},
            f"{scenario_id} conditions",
        )
        return (
            "skip_duplicate_write"
            if conditions.get("prior_write_result") == "uncertain"
            and conditions.get("exact_remote_state_read_supported") is True
            and conditions.get("intended_state_already_exists") is True
            else "do_not_retry_write"
        )
    if scenario_id == "credential-persistence-attempt":
        _mcp_exact_mapping(
            conditions,
            {"diagnostic_contains_credential_material", "persist_to_fixture_or_log", "task_authorized"},
            f"{scenario_id} conditions",
        )
        return (
            "deny_credential_persistence"
            if conditions.get("diagnostic_contains_credential_material") is True
            or conditions.get("persist_to_fixture_or_log") is True
            else "continue_sanitized_diagnostic"
        )
    raise ValueError(f"unknown mcp scenario: {scenario_id}")


def validate_mcp_blank_binding_mutations(scenarios: list[object]) -> None:
    median = next(
        (item for item in scenarios if isinstance(item, dict) and item.get("id") == "same-context-success"),
        None,
    )
    if median is None:
        raise ValueError("same-context-success is required for blank-binding mutations")
    paths = (
        ("local_credential_source", "exact_binding"),
        ("local_credential_source", "class"),
        ("identity_read_result", "account"),
        ("identity_read_result", "evidence_context", "provider"),
        ("identity_read_result", "evidence_context", "command_boundary"),
        ("identity_read_result", "evidence_context", "exact_credential_source"),
        ("identity_read_result", "evidence_context", "credential_source_class"),
        ("intended_call_authorization_request", "provider"),
        ("intended_call_authorization_request", "command_boundary"),
        ("intended_call_authorization_request", "exact_credential_source"),
    )
    for path in paths:
        mutated = copy.deepcopy(median)
        cursor = mutated["conditions"]
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = ""
        action = evaluate_mcp_scenario(mutated)
        if action != "fail_closed_report_context_binding_missing":
            raise ValueError(f"blank binding did not fail closed: {'.'.join(path)} -> {action}")


def check_mcp_execution_context() -> None:
    skill = read(".codex/skills/mcp-ops/SKILL.md")
    reference = read(".codex/skills/mcp-ops/references/provider-call-execution-context.md")
    specification = read("docs/agent/SPEC_EXTERNAL_SERVICES.md")
    for marker in (
        "references/provider-call-execution-context.md",
        "Do not claim `runtime_configured`",
        "exact provider, account, command boundary, and credential source",
    ):
        if marker not in skill:
            fail(f"root mcp-ops Skill missing execution-context marker: {marker}")
    for marker in (
        "provider, command execution boundary, and credential source",
        "This decision excludes host execution approval",
        "cannot pass the normal `authorize` command",
        "exact selected credential source",
        "saved command-prefix approval",
        "credential-source unavailability",
        "provider-permission denial",
        "provider unavailability",
        "read the exact remote state",
        "Never read, print, persist, fixture, log, or send token values",
    ):
        if marker not in reference:
            fail(f"root mcp-ops execution-context reference missing marker: {marker}")
    for marker in (
        "provider-call execution context",
        "would make that check circular",
        "this approval grants no provider operation, target, payload, or effect",
        "must not expose the exact credential-source binding",
        "saved command-prefix approval is never external-write authorization",
        "Distinguish a process that cannot obtain credentials",
        "read the exact remote state before retrying",
        "Schema version 2 and project-owned schema version 1 policies remain unchanged",
    ):
        if marker not in specification:
            fail(f"root external-service specification missing execution-context marker: {marker}")

    fixture = json.loads(read("tests/fixtures/mcp-ops/scenarios.json"))
    requirements = fixture.get("requirements", [])
    scenarios = fixture.get("scenarios", [])
    if not requirements or any(item.get("critical") is not True for item in requirements):
        fail("mcp-ops scenarios must keep every declared requirement critical")
    try:
        observed_ids = [item["id"] for item in scenarios]
        if len(observed_ids) != len(set(observed_ids)) or set(observed_ids) != MCP_SCENARIO_IDS:
            raise ValueError("mcp scenario identifiers differ from the accepted set")
        for item in scenarios:
            if evaluate_mcp_scenario(item) != item["expected"]:
                raise ValueError(f"incorrect condition-to-action mapping: {item['id']}")
        validate_mcp_blank_binding_mutations(scenarios)
    except (KeyError, TypeError, ValueError) as exc:
        fail(f"mcp-ops scenario evaluation failed: {exc}")
    if {item.get("class") for item in scenarios} != {"median", "edge", "negative", "holdout"}:
        fail("mcp-ops scenarios must cover median, edge, negative, and holdout classes")
    holdouts = [item for item in scenarios if item.get("class") == "holdout"]
    if len(holdouts) != 1 or holdouts[0].get("used_for_tuning") is not False:
        fail("mcp-ops holdout scenario must remain outside tuning")
    if any(item.get("used_for_tuning") is not True for item in scenarios if item.get("class") != "holdout"):
        fail("mcp-ops non-holdout scenarios must remain tuned inputs")


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


def check_git_retirement_policy() -> None:
    index = read("docs/agent/spec-index.yaml")
    for marker in (
        "  git_retirement:",
        "docs/agent/SPEC_GIT_RETIREMENT.md",
        "docs/agent/SPEC_SECURITY.md",
    ):
        if marker not in index:
            fail(f"root Git-retirement route missing: {marker}")

    root_spec = read("docs/agent/SPEC_GIT_RETIREMENT.md")
    generated_spec = read("template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md")
    normalized_generated_spec = generated_spec.replace(
        "`.project-agent-workflow/scripts/retire-merged-worktrees.py",
        "`scripts/retire-merged-worktrees.py",
    ).replace(
        "`.project-agent-workflow/scripts/manage-plan-worktrees.py",
        "`scripts/manage-plan-worktrees.py",
    )
    if root_spec != normalized_generated_spec:
        fail("root/generated Git-retirement specifications differ beyond the command path")
    for marker in (
        "docs/agent/git-retirement.yaml",
        "`scan` enumerates registered worktrees with Git plumbing.",
        "Every `apply-local` invocation requires a current explicit operator action.",
        "`git worktree remove`",
        "`git branch -d`",
        "must not run `apply-local`",
        "remote branch deletion",
    ):
        if marker not in root_spec:
            fail(f"Git-retirement specification missing marker: {marker}")
    if "`.project-agent-workflow/scripts/retire-merged-worktrees.py scan`" not in generated_spec:
        fail("generated Git-retirement specification names the wrong command path")

    try:
        root_config = yaml.safe_load(read("docs/agent/git-retirement.yaml"))
        generated_config = yaml.safe_load(read("template/docs/agent/git-retirement.yaml.jinja"))
    except yaml.YAMLError as exc:
        fail(f"invalid Git-retirement configuration YAML: {exc}")
    expected_root_config = {
        "version": 1,
        "enabled": True,
        "merge_target_refs": ["refs/heads/dev"],
        "protected_local_branch_refs": ["refs/heads/main", "refs/heads/dev"],
    }
    expected_generated_config = {
        "version": 1,
        "enabled": False,
        "merge_target_refs": [],
        "protected_local_branch_refs": [],
    }
    if root_config != expected_root_config:
        fail("root Git-retirement configuration differs from the exact enabled profile")
    if generated_config != expected_generated_config:
        fail("generated Git-retirement configuration differs from the exact safe-disabled profile")

    root_agents = read("AGENTS.md")
    generated_agents = read("template/.project-agent-workflow/AGENTS.md.jinja")
    if "docs/agent/SPEC_GIT_RETIREMENT.md" not in root_agents:
        fail("root AGENTS.md does not route local Git retirement")
    if ".project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md" not in generated_agents:
        fail("generated AGENTS.md does not route local Git retirement")

    ownership = read("template/.project-agent-workflow/ownership.yaml")
    if "  - .project-agent-workflow/**" not in ownership:
        fail("generated Git-retirement specification lacks managed ownership")
    if "  - docs/agent/**" not in ownership:
        fail("generated Git-retirement configuration lacks project-owned classification")


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


def check_review_turn_zero_contract() -> None:
    required = {
        "docs/agent/SPEC_AGENT_LOGGING.md": (
            "ReviewPacketStart",
            "SessionStart` alone",
            "inherited turn count",
        ),
        "docs/agent/SPEC_CONTEXT_COMPRESSION.md": (
            "cannot establish staged-review turn zero",
            "ReviewPacketStart",
        ),
        ".project-agent-workflow/hooks/agent_log_event.py": (
            '"review_packet_digest"',
            '"inherited_turns"',
            '"ReviewPacketStart"',
        ),
        "template/.project-agent-workflow/scripts/import-codex-transcript.py": (
            '"review_packet_start"',
            '"review_packet_digest"',
            '"inherited_turns"',
        ),
        "scripts/plan-execution-state.py": (
            "review_turn_zero_from_manifest",
            "--review-resource-manifest",
        ),
    }
    for relative, markers in required.items():
        text = read(relative)
        for marker in markers:
            if marker not in text:
                fail(f"{relative} missing review turn-zero marker: {marker}")


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
    optional_fields = (
        "target_json",
        "acceptance_focus",
        "completion_deferred_reason",
        "implementation_tier",
        "primary_invariant",
        "integration_gates",
        "replan_source",
        "replan_contract",
        "successor_plans",
        "inherited_acceptance_digests",
        "replan_reason_codes",
    )
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
                contract_fields = {
                    "worker_contract_path", "worker_contract_digest", "worker_attempt_label",
                }
                receipt_fields = {
                    "worker_completion_receipt_path", "worker_completion_receipt_digest",
                    "worker_process_result_path", "worker_process_result_digest",
                    "worker_attempt_id",
                }
                accepted_manifest_shapes = {
                    frozenset(manifest_fields),
                    frozenset(manifest_fields | {"correction_lineage"}),
                    frozenset(manifest_fields | contract_fields),
                    frozenset(manifest_fields | contract_fields | {"correction_lineage"}),
                    frozenset(manifest_fields | contract_fields | receipt_fields),
                    frozenset(
                        manifest_fields | contract_fields | receipt_fields | {"correction_lineage"}
                    ),
                }
                if not isinstance(manifest, dict) or frozenset(manifest) not in accepted_manifest_shapes:
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


def check_plan_restructuring_scenarios() -> None:
    fixture_path = ROOT / "tests/fixtures/orchestration/plan-restructuring-scenarios.json"
    holdout_path = ROOT / "tests/fixtures/orchestration/plan-restructuring-holdout.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid plan restructuring fixture: {exc}")
    if set(fixture) != {"schema_version", "requirements", "holdout_file", "scenarios"}:
        fail("plan restructuring fixture has an invalid exact shape")
    if fixture["schema_version"] != 1 or fixture["holdout_file"] != holdout_path.name:
        fail("plan restructuring fixture has an unsupported schema or holdout")
    requirements = fixture["requirements"]
    if not isinstance(requirements, list) or len(requirements) != 5:
        fail("plan restructuring fixture must preserve five critical requirements")
    requirement_markers = {
        "P1": ("hard trigger", "stops", "implementation", "validation", "apply", "finalize"),
        "P2": ("atomic restructuring", "every source acceptance", "integration plan"),
        "P3": ("requirement replacement", "explicit user authorization", "clarification", "acceptance mapping"),
        "P4": ("elapsed time is telemetry only", "scope", "specification", "security", "correction", "review"),
        "P5": ("independently repairable defect", "source-plan scope", "validation authority", "invariant boundaries", "current execution run", "source plan as deferred", "without rewriting acceptance", "separate bounded repair plan", "fresh execution run"),
    }
    observed_requirements: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict) or set(requirement) != {"id", "critical", "text"}:
            fail("plan restructuring requirement has an invalid exact shape")
        requirement_id = requirement["id"]
        if requirement_id not in requirement_markers or requirement_id in observed_requirements:
            fail("plan restructuring requirement identifiers differ from the accepted contract")
        if requirement["critical"] is not True or not isinstance(requirement["text"], str):
            fail("plan restructuring requirements must be critical text")
        lowered = requirement["text"].lower()
        if any(marker not in lowered for marker in requirement_markers[requirement_id]):
            fail(f"plan restructuring requirement {requirement_id} lost a critical referent")
        observed_requirements.add(requirement_id)
    if observed_requirements != set(requirement_markers):
        fail("plan restructuring requirement set is incomplete")

    expected_cases = {
        "median-multiple-independent-invariants": ("median", ["P1", "P2", "P4"], {"event": "parent_review", "independent_invariant_count": 2}, "multiple_independent_invariants", "atomic_restructure", "replan_required"),
        "edge-delegated-correction-budget-exhausted": ("edge", ["P1", "P2", "P4"], {"initial_generation_count": 1, "rejected_correction_count": 2}, "candidate_correction_budget_exhausted", "atomic_restructure", "replan_required"),
        "edge-parent-direct-review-budget-exhausted": ("edge", ["P1", "P2", "P4"], {"independently_reviewed_parent_remediation_count": 2, "remaining_finding_severity": "Medium"}, "parent_remediation_budget_exhausted", "atomic_restructure", "replan_required"),
        "negative-scope-drift": ("negative", ["P1", "P2", "P4"], {"event": "scope_drift"}, "scope_drift", "atomic_restructure", "replan_required"),
        "negative-specification-drift": ("negative", ["P1", "P2", "P4"], {"event": "spec_drift"}, "spec_drift", "atomic_restructure", "replan_required"),
        "negative-security-boundary-drift": ("negative", ["P1", "P2", "P4"], {"event": "security_boundary_drift"}, "security_boundary_drift", "atomic_restructure", "replan_required"),
        "negative-post-authoritative-design-change": ("negative", ["P1", "P2", "P4"], {"event": "post_authoritative_design_change", "authoritative_validation_count": 1}, "post_authoritative_design_change", "atomic_restructure", "replan_required"),
        "median-plan119-independent-validation-authorization-repair": ("median", ["P1", "P4", "P5"], {"event": "repair_classification", "affected_invariant_count": 1, "bounded_write_and_validation_scope": True, "source_scope_changed": False, "validation_authority_changed": False, "invariant_boundaries_changed": False, "source_acceptance_changed": False, "safety_boundary_changed": False, "external_authority_changed": False}, "independent_repair_required", "defer_source_and_create_bounded_repair_plan", "repair_required"),
        "edge-repair-required-run-cannot-continue": ("edge", ["P1", "P5"], {"operation": "continue_same_execution_run", "execution_state": "repair_required"}, "independent_repair_required", "reject_transition", "repair_required"),
        "edge-checked-repair-resumes-source-with-fresh-run": ("edge", ["P5"], {"repair_plan_status": "checked", "source_plan_status": "deferred", "source_scope_changed": False, "validation_authority_changed": False, "invariant_boundaries_changed": False, "requirements_changed": False, "safety_boundary_changed": False, "external_authority_changed": False, "execution_run": "fresh"}, "repair_prerequisite_satisfied", "resume_source_with_fresh_execution", "in_progress"),
        "negative-independent-repair-with-source-scope-drift": ("negative", ["P1", "P2", "P5"], {"event": "repair_classification", "source_scope_changed": True}, "scope_drift", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-independent-repair-with-validation-authority-drift": ("negative", ["P1", "P2", "P5"], {"event": "repair_classification", "validation_authority_changed": True}, "spec_drift", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-independent-repair-with-invariant-boundary-drift": ("negative", ["P1", "P2", "P5"], {"event": "repair_classification", "invariant_boundaries_changed": True}, "multiple_independent_invariants", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-independent-repair-with-altered-authority": ("negative", ["P1", "P2", "P3", "P5"], {"event": "repair_classification", "external_authority_changed": True}, "security_boundary_drift", "reject_repair_and_atomic_restructure", "replan_required"),
        "negative-unauthorized-requirement-replacement": ("negative", ["P3"], {"operation": "replace_source_acceptance_text", "explicit_user_authorization": False}, "requirement_change_not_authorized", "reject_transition", "pending_user_authorization"),
    }
    scenarios = fixture["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != len(expected_cases):
        fail("plan restructuring scenario set is incomplete")
    observed_cases: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "class", "used_for_tuning", "requirements", "input", "expected"}:
            fail("plan restructuring scenario has an invalid exact shape")
        scenario_id = scenario["id"]
        if scenario_id not in expected_cases or scenario_id in observed_cases:
            fail("plan restructuring scenario identifiers differ from the accepted contract")
        scenario_class, covered, inputs, reason, action, state = expected_cases[scenario_id]
        expected = {"state": state, "reason_code": reason, "next_action": action}
        if scenario["class"] != scenario_class or scenario["used_for_tuning"] is not True:
            fail(f"plan restructuring scenario class/tuning differs: {scenario_id}")
        if scenario["requirements"] != covered or scenario["input"] != inputs or scenario["expected"] != expected:
            fail(f"plan restructuring scenario input/result differs: {scenario_id}")
        observed_cases.add(scenario_id)
    if observed_cases != set(expected_cases):
        fail("plan restructuring scenario set differs from the accepted contract")

    expected_holdout = [{
        "id": "holdout-security-drift-with-dirty-product-path",
        "class": "holdout",
        "used_for_tuning": False,
        "requirements": ["P1", "P2", "P4"],
        "input": {"event": "security_boundary_drift", "dirty_product_path": "config/project-owned.yaml"},
        "expected": {"state": "replan_required", "reason_code": "security_boundary_drift", "next_action": "atomic_restructure_preserving_dirty_path"},
    }, {
        "id": "holdout-independent-repair-rejects-stopped-run-reuse",
        "class": "holdout",
        "used_for_tuning": False,
        "requirements": ["P1", "P5"],
        "input": {"source_plan_status": "deferred", "repair_plan_status": "checked", "execution_run": "stopped_repair_required_run"},
        "expected": {"state": "repair_required", "reason_code": "independent_repair_required", "next_action": "reject_transition_and_initialize_fresh_run"},
    }]
    if set(holdout) != {"schema_version", "scenarios"} or holdout.get("schema_version") != 1:
        fail("plan restructuring holdout has an invalid exact shape")
    if holdout.get("scenarios") != expected_holdout:
        fail("plan restructuring holdout must remain fixed and outside tuning scenarios")


def check_review_sequencing_scenarios(*, include_holdout: bool) -> None:
    fixture_path = ROOT / "tests/fixtures/orchestration/review-sequencing-scenarios.json"
    holdout_path = ROOT / "tests/fixtures/orchestration/review-sequencing-holdout.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid review sequencing fixture: {exc}")
    if not isinstance(fixture, dict) or set(fixture) != {
        "schema_version", "used_for_tuning", "requirements", "scenarios"
    }:
        fail("review sequencing fixture has an invalid exact shape")
    if fixture["schema_version"] != 1 or fixture["used_for_tuning"] is not True:
        fail("review sequencing fixture has an invalid identity")
    requirements = fixture["requirements"]
    if not isinstance(requirements, list) or len(requirements) != 4 or any(
        not isinstance(item, str) or not item for item in requirements
    ):
        fail("review sequencing requirements are incomplete")
    expected = {
        "median-accepted-two-plan-chain": ("median", "dependent_start_admitted"),
        "edge-independent-read-only-helper": ("edge", "ledger_unchanged"),
        "negative-rejected-predecessor": ("negative", "dependent_start_rejected"),
        "negative-overlapping-starts": ("negative", "second_start_rejected"),
        "negative-repeated-reason": ("negative", "replan_required"),
        "edge-changed-reason": ("edge", "next_correction_admitted"),
        "negative-unknown-reason": ("negative", "closure_rejected"),
        "negative-worker-authored-reason": ("negative", "closure_rejected"),
        "negative-missing-review-evidence": ("negative", "closure_rejected"),
        "negative-replay-and-history-rewrite": ("negative", "ledger_rejected"),
        "edge-crash-recovery": ("edge", "failed_attempt_closed"),
        "negative-stale-predecessor-digest": ("negative", "dependent_start_rejected"),
        "negative-correction-budget-exhausted": ("negative", "replan_required"),
        "negative-multiple-invariants-coupled": ("negative", "replan_required"),
        "negative-global-lock-or-shared-write": ("negative", "policy_rejected"),
    }
    scenarios = fixture["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != len(expected):
        fail("review sequencing scenario count differs from the accepted set")
    observed: dict[str, tuple[str, str]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "class", "expected"}:
            fail("review sequencing scenario has an invalid exact shape")
        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or scenario_id in observed:
            fail("review sequencing scenario identifier is invalid")
        observed[scenario_id] = (scenario["class"], scenario["expected"])
    if observed != expected:
        fail("review sequencing scenarios differ from the accepted outcomes")
    if not include_holdout:
        return
    if not isinstance(holdout, dict) or set(holdout) != {
        "schema_version", "used_for_tuning", "scenarios"
    }:
        fail("review sequencing holdout has an invalid exact shape")
    if holdout["schema_version"] != 1 or holdout["used_for_tuning"] is not False:
        fail("review sequencing holdout must remain untuned")
    if holdout["scenarios"] != [{
        "id": "holdout-accepted-predecessor-proof-substitution",
        "input": "a different accepted predecessor ledger is supplied after the dependent ledger is bound",
        "expected": "dependent_start_rejected",
    }]:
        fail("review sequencing holdout differs from its sealed outcome")


def check_worker_contract_scenarios(*, include_holdout: bool) -> None:
    scenario_path = ROOT / "tests/fixtures/orchestration/worker-contract-scenarios.json"
    holdout_path = ROOT / "tests/fixtures/orchestration/worker-contract-holdout.json"
    evidence_path = ROOT / "tests/fixtures/orchestration/worker-contract-evidence.json"
    try:
        scenario_bytes = scenario_path.read_bytes()
        scenarios = json.loads(scenario_bytes.decode("utf-8"))
        holdout_bytes = holdout_path.read_bytes()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid worker-contract fixture: {exc}")
    if hashlib.sha256(scenario_bytes).hexdigest() != "ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf":
        fail("worker-contract tuned scenario bytes differ from the preimplementation seal")
    if set(scenarios) != {"schema_version", "suite", "used_for_tuning", "holdout_file", "base", "cases"}:
        fail("worker-contract scenarios have an invalid exact shape")
    if (
        scenarios["schema_version"] != 1
        or scenarios["suite"] != "worker-execution-contract"
        or scenarios["used_for_tuning"] is not True
        or scenarios["holdout_file"] != holdout_path.name
    ):
        fail("worker-contract scenarios have an unsupported identity or holdout link")
    cases = scenarios["cases"]
    if not isinstance(cases, list) or not cases:
        fail("worker-contract scenarios must not be empty")
    if {case.get("class") for case in cases if isinstance(case, dict)} != {"median", "edge", "negative"}:
        fail("worker-contract scenarios must preserve median, edge, and negative classes")
    if any(not isinstance(case, dict) or case.get("used_for_tuning") is not True for case in cases):
        fail("worker-contract scenarios must remain tuned inputs")
    expected_coverage = {
        "exact_derivation", "lineage_binding", "explicit_new_non_authority_path",
        "source_plan_mutation", "digest_mismatch", "lineage_mismatch",
        "missing_primary_invariant", "duplicate_field", "unknown_field",
        "path_traversal", "symlink_escape", "oversized_input", "contract_mutation",
        "read_only_mount", "authority_widening", "directory_prefix_scope",
    }
    observed_coverage = {
        marker
        for case in cases
        for marker in (case.get("covers", []) if isinstance(case, dict) else [])
    }
    if observed_coverage != expected_coverage:
        fail("worker-contract scenarios do not cover the accepted preimplementation boundary")
    if hashlib.sha256(holdout_bytes).hexdigest() != "a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27":
        fail("worker-contract holdout bytes differ from the preimplementation seal")
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid worker-contract integration evidence: {exc}")
    evidence_fields = {
        "schema_version", "suite", "implementation_commit", "tuned_fixture",
        "holdout_fixture", "runner_sha256", "template_runner_sha256",
        "observations", "source_acceptance",
    }
    if not isinstance(evidence, dict) or set(evidence) != evidence_fields:
        fail("worker-contract evidence has an invalid exact shape")
    if evidence["schema_version"] != 1 or evidence["suite"] != "worker-execution-contract-integration":
        fail("worker-contract evidence has an unsupported identity")
    expected_fixture_records = (
        evidence.get("tuned_fixture") == {
            "path": "tests/fixtures/orchestration/worker-contract-scenarios.json",
            "sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        }
        and evidence.get("holdout_fixture") == {
            "path": "tests/fixtures/orchestration/worker-contract-holdout.json",
            "sha256": hashlib.sha256(holdout_bytes).hexdigest(),
        }
    )
    if not expected_fixture_records:
        fail("worker-contract evidence fixture bindings differ")
    implementation_commit = evidence.get("implementation_commit")
    if not isinstance(implementation_commit, str) or re.fullmatch(r"[0-9a-f]{40}", implementation_commit) is None:
        fail("worker-contract evidence implementation commit is invalid")
    committed_runner = subprocess.run(
        ["git", "show", f"{implementation_commit}:scripts/run-sandboxed-plan-worker.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if committed_runner.returncode != 0:
        fail("worker-contract evidence implementation commit is unavailable")
    committed_template_runner = subprocess.run(
        [
            "git", "show",
            f"{implementation_commit}:template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if committed_template_runner.returncode != 0:
        fail("worker-contract evidence template implementation commit is unavailable")
    root_runner_digest = hashlib.sha256((ROOT / "scripts/run-sandboxed-plan-worker.py").read_bytes()).hexdigest()
    template_runner_digest = hashlib.sha256(
        (ROOT / "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py").read_bytes()
    ).hexdigest()
    if (
        hashlib.sha256(committed_runner.stdout).hexdigest() != evidence.get("runner_sha256")
        or hashlib.sha256(committed_template_runner.stdout).hexdigest()
        != evidence.get("template_runner_sha256")
        or evidence.get("runner_sha256") != evidence.get("template_runner_sha256")
        or root_runner_digest != template_runner_digest
    ):
        fail("worker-contract evidence runner bindings differ")
    expected_observations = [
        {
            "id": case["id"],
            "class": case["class"],
            "used_for_tuning": case["used_for_tuning"],
            **case["expected"],
        }
        for fixture in (scenarios, json.loads(holdout_bytes.decode("utf-8")))
        for case in fixture["cases"]
    ]
    if evidence.get("observations") != expected_observations:
        fail("worker-contract evidence observations differ from the sealed expectations")
    replan_contract = json.loads(
        (ROOT / "docs/plan/replanned/contracts/113-generate-plan-bound-worker-contract.json").read_text(
            encoding="utf-8"
        )
    )
    expected_acceptance = [
        {"digest": item["digest"].removeprefix("sha256:"), "result": "passed"}
        for item in replan_contract["source"]["acceptance"]
    ]
    if evidence.get("source_acceptance") != expected_acceptance:
        fail("worker-contract evidence source acceptance bindings differ")
    if not include_holdout:
        return
    try:
        holdout = json.loads(holdout_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid worker-contract holdout fixture: {exc}")
    if set(holdout) != {"schema_version", "suite", "used_for_tuning", "base", "cases"}:
        fail("worker-contract holdout has an invalid exact shape")
    if holdout["schema_version"] != 1 or holdout["suite"] != "worker-execution-contract" or holdout["used_for_tuning"] is not False:
        fail("worker-contract holdout has an unsupported identity")
    holdout_cases = holdout["cases"]
    if not isinstance(holdout_cases, list) or len(holdout_cases) != 1:
        fail("worker-contract holdout must contain one independent case")
    holdout_case = holdout_cases[0]
    if (
        not isinstance(holdout_case, dict)
        or holdout_case.get("class") != "holdout"
        or holdout_case.get("used_for_tuning") is not False
        or holdout_case.get("id") != "holdout-missing-parent-new-package-manifest"
    ):
        fail("worker-contract holdout identity differs from the sealed case")
    test_path = ROOT / "tests/test-sandboxed-plan-worker.py"
    spec = importlib.util.spec_from_file_location("worker_contract_behavior_evaluator", test_path)
    if spec is None or spec.loader is None:
        fail("could not load the generic worker-contract evaluator")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        tuned_observations = module.evaluate_selected_worker_contract_fixture(
            scenario_path, used_for_tuning=True
        )
        holdout_observations = module.evaluate_selected_worker_contract_fixture(
            holdout_path, used_for_tuning=False
        )
    except Exception as exc:
        fail(f"worker-contract behavior evaluation failed: {exc}")
    if len(tuned_observations) != len(cases) or holdout_observations != [{
        "id": "holdout-missing-parent-new-package-manifest",
        "observed": {"result": "rejected", "error_code": "validation_authority_write"},
    }]:
        fail("worker-contract behavior observations differ from the sealed scenarios")
    actual_observations = []
    for fixture, observations in (
        (scenarios, tuned_observations),
        (holdout, holdout_observations),
    ):
        observed_by_id = {item["id"]: item["observed"] for item in observations}
        actual_observations.extend(
            {
                "id": case["id"],
                "class": case["class"],
                "used_for_tuning": case["used_for_tuning"],
                **observed_by_id[case["id"]],
            }
            for case in fixture["cases"]
        )
    if actual_observations != evidence["observations"]:
        fail("worker-contract execution differs from the recorded integration evidence")


def check_worker_completion_receipt_scenarios(*, include_holdout: bool) -> None:
    scenario_path = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-scenarios.json"
    holdout_path = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-holdout.json"
    replacement_holdout_path = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-holdout-v2.json"
    try:
        scenario_bytes = scenario_path.read_bytes()
        scenarios = json.loads(scenario_bytes.decode("utf-8"))
        holdout_bytes = holdout_path.read_bytes()
        replacement_holdout_bytes = replacement_holdout_path.read_bytes()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid worker-completion-receipt fixture: {exc}")
    if hashlib.sha256(scenario_bytes).hexdigest() != "264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a":
        fail("worker-completion-receipt tuned scenario bytes differ from the preimplementation seal")
    if set(scenarios) != {"schema_version", "suite", "used_for_tuning", "holdout_file", "base", "cases"}:
        fail("worker-completion-receipt scenarios have an invalid exact shape")
    if (
        scenarios.get("schema_version") != 1
        or scenarios.get("suite") != "worker-completion-receipt"
        or scenarios.get("used_for_tuning") is not True
        or scenarios.get("holdout_file") != holdout_path.name
    ):
        fail("worker-completion-receipt scenarios have an unsupported identity or holdout link")
    cases = scenarios.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("worker-completion-receipt scenarios must not be empty")
    if {case.get("class") for case in cases if isinstance(case, dict)} != {"median", "edge", "negative"}:
        fail("worker-completion-receipt scenarios must preserve median, edge, and negative classes")
    if any(not isinstance(case, dict) or case.get("used_for_tuning") is not True for case in cases):
        fail("worker-completion-receipt scenarios must remain tuned inputs")
    expected_coverage = {
        "successful_attempt", "failed_attempt", "initial_attempt", "correction_attempt",
        "failure_before_candidate", "partial_command_execution", "stale_receipt",
        "replayed_receipt", "plan_mismatch", "contract_mismatch", "patch_mismatch",
        "changed_path_mismatch", "false_success_claim", "missing_out_of_scope_declaration",
        "unknown_field", "duplicate_field", "oversized_receipt", "oversized_value",
        "path_traversal", "symlink_escape", "secret_inclusion", "raw_output_inclusion",
    }
    observed_coverage = {
        marker
        for case in cases
        for marker in (case.get("covers", []) if isinstance(case, dict) else [])
    }
    if observed_coverage != expected_coverage:
        fail("worker-completion-receipt scenarios do not cover the accepted preimplementation boundary")
    if hashlib.sha256(holdout_bytes).hexdigest() != "4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76":
        fail("worker-completion-receipt holdout bytes differ from the preimplementation seal")
    if hashlib.sha256(replacement_holdout_bytes).hexdigest() != "ddbbedb5c65cfe16ae48763b403c1beb16c241b7a77ab9379a88f98c8dd0f8de":
        fail("worker-completion-receipt replacement holdout bytes differ from the independent seal")
    test_path = ROOT / "tests/test-sandboxed-plan-worker.py"
    spec = importlib.util.spec_from_file_location("worker_completion_receipt_fixture_evaluator", test_path)
    if spec is None or spec.loader is None:
        fail("could not load the generic worker-completion-receipt evaluator")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        evaluator = module.SandboxedPlanWorkerTests(
            methodName="test_tuned_worker_completion_receipt_fixture_is_frozen_and_evaluator_is_generic"
        ).evaluate_worker_completion_receipt_case
        observations = module.evaluate_worker_completion_receipt_fixture(
            scenario_path,
            evaluator,
            used_for_tuning=True,
        )
    except Exception as exc:
        fail(f"worker-completion-receipt fixture evaluation failed: {exc}")
    if len(observations) != len(cases):
        fail("worker-completion-receipt tuned observations are incomplete")
    try:
        exposed_holdout = json.loads(holdout_bytes.decode("utf-8"))
        exposed_observations = module.evaluate_worker_completion_receipt_fixture(
            holdout_path,
            evaluator,
            used_for_tuning=False,
        )
    except Exception as exc:
        fail(f"worker-completion-receipt exposed holdout regression failed: {exc}")
    if (
        exposed_holdout.get("used_for_tuning") is not False
        or exposed_observations
        != [
            {
                "id": "holdout-host-path-raw-output-in-residual-risk",
                "observed": {
                    "result": "rejected",
                    "error_code": "prohibited_receipt_content",
                },
            }
        ]
    ):
        fail("worker-completion-receipt exposed holdout observations differ")
    evidence_path = ROOT / "tests/fixtures/orchestration/worker-completion-receipt-evidence.json"
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid worker-completion-receipt integration evidence: {exc}")
    if set(evidence) != {
        "schema_version", "suite", "implementation_commit", "tuned_fixture",
        "exposed_holdout_fixture", "replacement_holdout_fixture", "runner_sha256",
        "template_runner_sha256", "observations", "source_acceptance",
    }:
        fail("worker-completion-receipt integration evidence has an invalid exact shape")
    if (
        evidence.get("schema_version") != 1
        or evidence.get("suite") != "worker-completion-receipt-integration"
        or evidence.get("tuned_fixture") != {
            "path": str(scenario_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        }
        or evidence.get("exposed_holdout_fixture") != {
            "path": str(holdout_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(holdout_bytes).hexdigest(),
            "evidence_status": "known_regression_after_initial_failure",
        }
        or evidence.get("replacement_holdout_fixture") != {
            "path": str(replacement_holdout_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(replacement_holdout_bytes).hexdigest(),
            "evidence_status": "untuned_holdout",
        }
    ):
        fail("worker-completion-receipt evidence fixture bindings differ")
    implementation_commit = evidence.get("implementation_commit")
    if not isinstance(implementation_commit, str) or re.fullmatch(r"[0-9a-f]{40}", implementation_commit) is None:
        fail("worker-completion-receipt evidence implementation commit is invalid")
    committed_runner_digests = []
    for relative in (
        "scripts/run-sandboxed-plan-worker.py",
        "template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py",
    ):
        result = subprocess.run(
            ["git", "show", f"{implementation_commit}:{relative}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            fail("worker-completion-receipt evidence implementation commit is unavailable")
        committed_runner_digests.append(hashlib.sha256(result.stdout).hexdigest())
    if (
        evidence.get("runner_sha256") != committed_runner_digests[0]
        or evidence.get("template_runner_sha256") != committed_runner_digests[1]
        or committed_runner_digests[0] != committed_runner_digests[1]
    ):
        fail("worker-completion-receipt evidence runner bindings differ")
    source_contract = json.loads(
        (ROOT / "docs/plan/replanned/contracts/114-validate-structured-worker-completion.json").read_text(
            encoding="utf-8"
        )
    )
    expected_acceptance = [
        {"digest": item["digest"].removeprefix("sha256:"), "result": "passed"}
        for item in source_contract["source"]["acceptance"]
    ]
    if evidence.get("source_acceptance") != expected_acceptance:
        fail("worker-completion-receipt evidence acceptance bindings differ")
    expected_known_observations = [
        {
            "id": case["id"],
            "class": case["class"],
            "used_for_tuning": case["used_for_tuning"],
            **case["expected"],
        }
        for fixture in (scenarios, exposed_holdout)
        for case in fixture["cases"]
    ]
    observations = evidence.get("observations")
    if (
        not isinstance(observations, list)
        or observations[:-1] != expected_known_observations
        or observations[-1:] != [{
            "id": "holdout-host-path-in-completion-risk",
            "class": "holdout",
            "used_for_tuning": False,
            "result": "rejected",
            "error_code": "prohibited_receipt_content",
        }]
    ):
        fail("worker-completion-receipt recorded observations differ")
    if not include_holdout:
        return
    try:
        replacement_holdout = json.loads(replacement_holdout_bytes.decode("utf-8"))
        replacement_observations = module.evaluate_worker_completion_receipt_fixture(
            replacement_holdout_path,
            evaluator,
            used_for_tuning=False,
        )
    except Exception as exc:
        fail(f"worker-completion-receipt replacement holdout evaluation failed: {exc}")
    actual_observations = []
    for fixture, fixture_observations in (
        (scenarios, observations[:len(cases)]),
        (exposed_holdout, exposed_observations),
        (replacement_holdout, replacement_observations),
    ):
        observed_by_id = {item["id"]: item.get("observed", item) for item in fixture_observations}
        actual_observations.extend(
            {
                "id": case["id"],
                "class": case["class"],
                "used_for_tuning": case["used_for_tuning"],
                **observed_by_id[case["id"]],
            }
            for case in fixture["cases"]
        )
    if actual_observations != evidence["observations"]:
        fail("worker-completion-receipt execution differs from integration evidence")


def has_exact_review_continuation_clause(policy: str) -> bool:
    lines = policy.splitlines()
    headings = [
        index
        for index, line in enumerate(lines)
        if line == REVIEW_FINDING_BUDGETS_HEADING.lower()
    ]
    if len(headings) != 1:
        return False
    start = headings[0] + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    candidates = [
        line
        for line in lines[start:end]
        if line.startswith(REVIEW_CONTINUATION_CLAUSE_PREFIX.lower())
    ]
    return candidates == [REVIEW_CONTINUATION_CLAUSE.lower()]


def check_review_continuation_clause(policy: str) -> None:
    if not has_exact_review_continuation_clause(policy):
        fail(
            "SPEC_PLAN_WORKFLOW.md review-finding budget section does not contain "
            "the exact one-or-two-review continuation clause"
        )
    old_clause = REVIEW_CONTINUATION_CLAUSE.replace(
        "exactly one or two prior formal reviews",
        "exactly two prior formal reviews",
    )
    decoy = "<!-- exactly one or two prior formal reviews -->"
    mutated = policy.replace(
        REVIEW_CONTINUATION_CLAUSE.lower(),
        f"{old_clause.lower()}\n{decoy}",
        1,
    )
    if has_exact_review_continuation_clause(mutated):
        fail("review-continuation clause self-test accepted detached decoy wording")


def check_orchestration_policy(*, include_holdout: bool = False) -> None:
    check_plan_restructuring_scenarios()
    check_review_sequencing_scenarios(include_holdout=include_holdout)
    check_worker_contract_scenarios(include_holdout=include_holdout)
    check_worker_completion_receipt_scenarios(include_holdout=include_holdout)
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
        "select the runnable active plan",
        "index/file status mismatch",
        "zero runnable rows",
        "multiple runnable rows",
        "duplicate ids or paths",
        "immutable identities and archive ordering only",
        "lower-numbered deferred plan does not block",
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
        "worker completion receipt",
        "consumed-attempt replay rejection",
        "receipt claims are advisory only",
        "run-sandboxed-plan-worker.py correct",
        "aggregate patch",
        "at most one correction round",
        "independent_review_limit` is two",
        "third review request is refused",
        "rejected patch never touches the source",
        "candidate generation and correction do not run plan validation",
        "parent diff review",
        "critical-invariant review",
        "focused_validation",
        "validation_authority_scope",
        "validation_witness_map",
        "validation_witness_schema: 1",
        "resolved-context-files",
        "authoritative_only_reason",
        "earliest parent-owned witness",
        "network-isolated review clone",
        "authoritative",
        "bounded parent implementation",
        "independent change review",
        "diagnosis_required",
        "failed-operation digest",
        "observed exit status",
        "inconclusive",
        "disputed",
        "repair_required",
        "repair-evidence",
        "fresh plan digest",
        "replan_required",
        "requirement change needs separate explicit user authorization",
        "elapsed time is telemetry",
        "plan-execution-state.py",
        "independent-review receipt",
        "--plan-execution-state",
        "--predecessor-plan-execution-state",
        "predecessor_acceptance",
        "writable_attempt_started",
        "attempt_closed",
        "successor_claimed",
        "review_evidence_digest",
        "acceptance_unmet",
        "multiple_invariants_coupled",
        "global task lock",
        "plan_execution_attempt_id",
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
        "worker completion receipt",
        "validation_witness_map",
        "authoritative-only witness",
        "diagnosis_required",
        "confirmed",
        "inconclusive",
        "disputed",
        "repair_required",
        "source-plan scope",
        "validation authority",
        "invariant boundaries",
        "source plan `deferred`",
        "fresh run",
        "never reopen a stopped ledger run",
        "never relabel requirement, authority, or security-boundary drift",
        "implementation-start authorization",
        "plan_purpose: implementation",
        "feasibility_evidence",
        "completion_conditions",
        "completion_witness_map",
        "outside plan-lifecycle records",
        "identifier is 264 or higher",
        "run-wide independent review budget is exhausted",
        "owner_continuation_authorization",
        "schema 4",
        "a third review is refused",
    ):
        if marker not in agents:
            fail(f"AGENTS.md missing orchestration ownership marker: {marker}")

    plan_workflow = read("docs/agent/SPEC_PLAN_WORKFLOW.md").lower()
    for marker in (
        "plan admission contract",
        "plan_purpose",
        "feasibility_evidence",
        "completion_conditions",
        "completion_witness_map",
        "reproduced_defect",
        "existing_mechanism",
        "bounded_prototype",
        "mechanical_transformation",
        "independent_review_limit` is two",
        "owner_continuation_authorization",
        "identifier is 264 or higher",
        "independent repair prerequisite",
        "diagnosis_required",
        "failed-operation digest",
        "observed exit status",
        "confirmed",
        "inconclusive",
        "disputed",
        "repair_required",
        "one observed defect",
        "source-plan scope",
        "validation authority",
        "invariant boundaries",
        "unchanged source acceptance",
        "external-effect authority",
        "separate numbered active repair plan",
        "do not create a replan contract",
        "fresh source-plan digest",
        "security-boundary change is not an independent repair",
    ):
        if marker not in plan_workflow:
            fail(f"SPEC_PLAN_WORKFLOW.md missing independent-repair marker: {marker}")
    check_review_continuation_clause(plan_workflow)

    diagnosis_fixture = json.loads(
        read("tests/fixtures/orchestration/failure-diagnosis-scenarios.json")
    )
    expected_diagnosis_ids = {
        "confirmed-single-invariant",
        "inconclusive-read-only-stop",
        "disputed-read-only-stop",
        "receipt-replay-rejected",
        "failure-identity-mutation-rejected",
        "validation-authority-drift-rejected",
    }
    if diagnosis_fixture.get("schema_version") != 1 or {
        item.get("id") for item in diagnosis_fixture.get("scenarios", [])
        if isinstance(item, dict)
    } != expected_diagnosis_ids:
        fail("failure-diagnosis scenarios do not preserve the exact confirmation boundary")

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


def parse_plan_manifest(text: str) -> dict[str, str | list[str]]:
    """Read the bounded leading manifest of a root plan file."""

    values: dict[str, str | list[str]] = {key: [] for key in ADMISSION_LIST_KEYS}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        if ":" in line and not line.startswith(" "):
            key, rest = line.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            current = None
            if key in ADMISSION_SCALAR_KEYS:
                values[key] = rest
            elif key in ADMISSION_LIST_KEYS:
                current = key
                if rest:
                    values[key].append(rest)  # type: ignore[union-attr]
            continue
        if current and line.lstrip().startswith("- "):
            values[current].append(line.lstrip()[2:].strip())  # type: ignore[union-attr]
    return values


def admission_placeholder(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return stripped.lower().strip(" .") in ADMISSION_PLACEHOLDER_VALUES


def bounded_admission_text(value: object, maximum_bytes: int) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and not admission_placeholder(value)
        and len(value.encode("utf-8")) <= maximum_bytes
        and all(ord(char) >= 0x20 for char in value)
    )


def admission_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_plan_admission(relative: str, values: dict[str, str | list[str]]) -> None:
    """Require one bounded implementation-start authorization for a numbered plan."""

    purpose = values.get("plan_purpose", "")
    if purpose not in PLAN_PURPOSE_VALUES:
        fail(f"{relative} must declare plan_purpose: implementation")
    evidence_items = values["feasibility_evidence"]
    conditions = values["completion_conditions"]
    raw_map = values["completion_witness_map"]
    focused = values["focused_validation"]
    write_scope = values["write_scope"]
    assert isinstance(evidence_items, list) and isinstance(conditions, list)
    assert isinstance(raw_map, list) and isinstance(focused, list)
    assert isinstance(write_scope, list)

    if (
        not evidence_items
        or len(evidence_items) > MAX_FEASIBILITY_EVIDENCE
        or len(evidence_items) != len(set(evidence_items))
    ):
        fail(f"{relative} feasibility_evidence must be a bounded unique non-empty list")
    for index, raw in enumerate(evidence_items, start=1):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            fail(f"{relative} feasibility_evidence entry {index} is not valid JSON")
        if not isinstance(record, dict) or set(record) != {"kind", "evidence"}:
            fail(
                f"{relative} feasibility_evidence entry {index} must declare exactly "
                "kind and evidence"
            )
        if record["kind"] not in FEASIBILITY_EVIDENCE_KINDS:
            fail(f"{relative} feasibility_evidence entry {index} has an unsupported kind")
        if not bounded_admission_text(record["evidence"], FEASIBILITY_EVIDENCE_MAX_BYTES):
            fail(
                f"{relative} feasibility_evidence entry {index} must be bounded "
                "non-placeholder text"
            )

    if (
        not conditions
        or len(conditions) > MAX_COMPLETION_CONDITIONS
        or len(conditions) != len(set(conditions))
    ):
        fail(f"{relative} completion_conditions must be a bounded unique non-empty list")
    for index, condition in enumerate(conditions, start=1):
        if not bounded_admission_text(condition, COMPLETION_CONDITION_MAX_BYTES):
            fail(
                f"{relative} completion_conditions entry {index} must be bounded "
                "non-placeholder text"
            )

    mapped: list[str] = []
    for index, raw in enumerate(raw_map, start=1):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            fail(f"{relative} completion_witness_map entry {index} is not valid JSON")
        if (
            not isinstance(record, dict)
            or set(record) != {"condition_sha256", "witness"}
            or not all(isinstance(value, str) for value in record.values())
        ):
            fail(
                f"{relative} completion_witness_map entry {index} must declare exactly "
                "condition_sha256 and witness"
            )
        witness = record["witness"]
        if not witness or witness != witness.strip() or witness not in focused:
            fail(
                f"{relative} completion_witness_map entry {index} witness is not a "
                "declared focused_validation command"
            )
        mapped.append(record["condition_sha256"])
    if mapped != [admission_digest(condition) for condition in conditions]:
        fail(
            f"{relative} completion_witness_map must cover completion_conditions "
            "exactly once and in source order"
        )

    if not [
        path
        for path in write_scope
        if not admission_placeholder(path)
        and not path.startswith(ADMISSION_LIFECYCLE_PREFIXES)
    ]:
        fail(
            f"{relative} plan_purpose: implementation requires a write_scope path "
            "outside plan-lifecycle records"
        )

    if values.get("implementation_tier", "") == TIER_ONE_VALUE:
        acceptance = values["acceptance"]
        assert isinstance(acceptance, list)
        if len(acceptance) != 1:
            fail(
                f"{relative} implementation_tier: 1 requires exactly one acceptance "
                f"item, not {len(acceptance)}; a plan that needs several acceptance "
                "items is Tier 2"
            )


def check_plan_admission_boundary() -> None:
    """Admit new root plans only as bounded implementation authorizations."""

    for directory in ("docs/plan/active", "docs/plan/backlog"):
        plan_dir = ROOT / directory
        if not plan_dir.is_dir():
            continue
        for path in sorted(plan_dir.glob("[0-9][0-9][0-9]-*.md")):
            match = PLAN_FILE_RE.fullmatch(path.name)
            if match is None:
                fail(f"{directory}/{path.name} is not a normalized plan filename")
            if int(match.group(1)) < ROOT_ADMISSION_BOUNDARY_PLAN_ID:
                continue
            relative = str(path.relative_to(ROOT))
            check_plan_admission(relative, parse_plan_manifest(path.read_text(encoding="utf-8")))


def load_parallel_group_module():
    """Load the shared group-description authority used by root and generated lint."""

    path = ROOT / "scripts/parallel-plan-state.py"
    if not path.is_file():
        fail("scripts/parallel-plan-state.py is required for execution group policy")
    spec = importlib.util.spec_from_file_location("root_parallel_group", path)
    if spec is None or spec.loader is None:
        fail("could not load the parallel plan group authority")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execution_group_members() -> dict[str, str]:
    """Return every enrolled member plan path mapped to its group description."""

    module = load_parallel_group_module()
    try:
        groups = module.load_group_descriptions(ROOT)
    except module.GroupError as exc:
        fail(f"invalid execution group description: {exc}")
    enrolled: dict[str, str] = {}
    for label, group in groups.items():
        for plan_path in group["members"]:
            enrolled[plan_path] = label
    return enrolled


def check_execution_groups() -> None:
    directory = ROOT / "docs/plan/execution-groups"
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            if path.is_dir() or path.suffix != ".json":
                fail(
                    "docs/plan/execution-groups may contain only group description "
                    f"JSON files: {path.relative_to(ROOT)}"
                )
    enrolled = execution_group_members()
    active_dir = ROOT / "docs/plan/active"
    if active_dir.is_dir():
        for path in sorted(active_dir.glob("[0-9][0-9][0-9]-*.md")):
            relative = str(path.relative_to(ROOT))
            values = parse_plan_manifest(path.read_text(encoding="utf-8"))
            declared = values.get("execution_group", "")
            assert isinstance(declared, str)
            if not declared:
                continue
            if enrolled.get(relative) != declared:
                fail(
                    f"{relative} declares execution_group {declared!r}, which does "
                    "not name a validated group description enrolling this plan"
                )
    for plan_path in sorted(enrolled):
        if not (ROOT / plan_path).is_file():
            fail(f"execution group enrolls a missing plan: {plan_path}")


# --- active plan index grammar: keep byte-identical across enforcing commands ---
ACTIVE_INDEX_TITLE = "# Active Plan"
ACTIVE_INDEX_EMPTY_BODY = "No active development items."
ACTIVE_INDEX_HEADER = "id\tpath\tstatus"
ACTIVE_INDEX_STATUSES = ("in_progress", "ready_to_archive", "deferred", "replan_required")
ACTIVE_INDEX_ID_RE = re.compile(r"[0-9]{3}")
ACTIVE_INDEX_ROW_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-[a-z0-9][a-z0-9-]*\.md")


class ActiveIndexError(ValueError):
    """Raised when the active plan index is not one accepted representation."""


def read_active_index(path: Path) -> str:
    """Read one active plan index without newline translation."""

    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ActiveIndexError(f"active plan index is not UTF-8 text: {exc}") from exc


def parse_active_index(text: str) -> list[tuple[str, str, str]]:
    """Return the rows of one exact accepted active plan index document.

    The empty representation is the title, one blank line, and the empty
    marker. The populated representation is the title, one blank line, the
    actual-tab header, and one or more actual-tab rows. Every other nonempty
    document is rejected whole instead of being partially parsed.
    """

    if "\r" in text or not text.endswith("\n") or text.endswith("\n\n"):
        raise ActiveIndexError("active plan index must end with exactly one trailing newline")
    lines = text.split("\n")[:-1]
    if lines[:2] != [ACTIVE_INDEX_TITLE, ""]:
        raise ActiveIndexError("active plan index must start with its title and one blank line")
    body = lines[2:]
    if not body:
        raise ActiveIndexError("active plan index must hold the empty marker or the header")
    if body[0] == ACTIVE_INDEX_EMPTY_BODY:
        if len(body) > 1:
            raise ActiveIndexError("empty active plan index must hold no other content")
        return []
    if body[0] != ACTIVE_INDEX_HEADER:
        raise ActiveIndexError(f"active plan index needs the exact tab header: {body[0]!r}")
    if len(body) == 1:
        raise ActiveIndexError("active plan index header must be followed by at least one row")
    rows: list[tuple[str, str, str]] = []
    for line in body[1:]:
        columns = line.split("\t")
        if len(columns) != 3:
            raise ActiveIndexError(f"active plan index row needs three tab columns: {line!r}")
        plan_id, path, status = columns
        if ACTIVE_INDEX_ID_RE.fullmatch(plan_id) is None:
            raise ActiveIndexError(f"active plan index row needs a three-digit id: {line!r}")
        match = ACTIVE_INDEX_ROW_PATH_RE.fullmatch(path)
        if match is None:
            raise ActiveIndexError(f"active plan index row needs a normalized path: {line!r}")
        if match.group(1) != plan_id:
            raise ActiveIndexError(f"active plan index row id does not match its file: {line!r}")
        if status not in ACTIVE_INDEX_STATUSES:
            raise ActiveIndexError(f"active plan index row status is not allowed: {line!r}")
        if any(plan_id == row[0] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index id: {plan_id}")
        if any(path == row[1] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index path: {path}")
        rows.append((plan_id, path, status))
    return rows


def render_active_index(rows: list[tuple[str, str, str]]) -> str:
    """Serialize fully parsed rows as the single canonical representation."""

    if rows:
        body = "\n".join("\t".join(row) for row in rows)
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_HEADER}\n{body}\n"
    else:
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_EMPTY_BODY}\n"
    if parse_active_index(text) != rows:
        raise ActiveIndexError("canonical active plan index serialization failed")
    return text
# --- end active plan index grammar ---


def check_active_plans() -> None:
    active_dir = ROOT / "docs/plan/active"
    if not active_dir.exists():
        return
    for path in sorted(active_dir.glob("[0-9][0-9][0-9]-*.md")):
        if contains_option_matrix(path.read_text(encoding="utf-8")):
            fail(f"{path.relative_to(ROOT)} contains an option-analysis matrix")

    index_path = ROOT / "docs/plan/plan.md"
    if not index_path.exists():
        return
    try:
        rows = parse_active_index(read_active_index(index_path))
    except ActiveIndexError as exc:
        fail(str(exc))
    runnable_rows: list[str] = []
    runnable_paths: list[str] = []
    for row_id, row_path, row_status in rows:
        plan_file = ROOT / row_path
        if not plan_file.exists():
            fail(f"active index references missing plan file: {row_path}")
        plan_text = plan_file.read_text(encoding="utf-8")
        file_status = None
        for plan_line in plan_text.splitlines():
            if plan_line.startswith("status:"):
                file_status = plan_line.split(":", 1)[1].strip()
                break
        if file_status is not None and file_status != row_status:
            fail(f"active index status '{row_status}' does not match plan file status '{file_status}' for {row_path}")
        if row_status == "in_progress":
            runnable_rows.append(row_id)
            runnable_paths.append(row_path)
    if len(runnable_rows) > 1:
        enrolled = execution_group_members()
        groups = {enrolled.get(path) for path in runnable_paths}
        if None in groups or len(groups) != 1:
            fail(
                "multiple runnable plans in active index: "
                + ", ".join(runnable_rows)
            )
        label = groups.pop()
        members = {path for path, group in enrolled.items() if group == label}
        if set(runnable_paths) != members:
            fail(
                "runnable plans do not match the exact membership of "
                f"{label}: {', '.join(runnable_rows)}"
            )


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
    parser.add_argument(
        "--check-plan-admission",
        metavar="PLAN",
        help="check one root plan file against the numbered-plan admission boundary",
    )
    args = parser.parse_args()

    if args.check_plan_admission:
        path = Path(args.check_plan_admission)
        if not path.is_file():
            fail(f"{args.check_plan_admission} is not a readable plan file")
        match = PLAN_FILE_RE.fullmatch(path.name)
        if match is None:
            fail(f"{path.name} is not a normalized plan filename")
        if int(match.group(1)) < ROOT_ADMISSION_BOUNDARY_PLAN_ID:
            print(f"{args.check_plan_admission} predates the admission boundary")
            return 0
        check_plan_admission(
            args.check_plan_admission,
            parse_plan_manifest(path.read_text(encoding="utf-8")),
        )
        print(f"{args.check_plan_admission} admission check passed")
        return 0

    if args.self_test:
        self_test()
    check_required_files()
    check_gitignore()
    check_agents_rules()
    check_agents_entrypoint_size()
    check_validation_witness_migration_policy()
    check_validation_witness_map_policy()
    check_tier_zero_pair_policy()
    check_agent_model_profiles()
    check_sandboxed_worker_fallback()
    check_reusable_skill_parity()
    check_decision_reuse_scenarios()
    check_natural_japanese_contract()
    check_mcp_execution_context()
    check_browser_routing()
    check_external_service_policy()
    check_git_retirement_policy()
    check_user_communication_contract()
    check_review_turn_zero_contract()
    check_namespaced_documentation_targets()
    check_orchestration_policy(include_holdout=args.include_holdout)
    check_plan_admission_boundary()
    check_execution_groups()
    check_active_plans()
    print("root agent policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
