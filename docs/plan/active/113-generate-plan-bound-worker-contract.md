# Generate a plan-bound worker execution contract

status: in_progress
task_types:
  - planning_docs
  - referent_first
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
primary_invariant: derive one immutable worker execution contract from one unchanged accepted active plan without replacing or widening the source plan
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
  - tests/test-validation-tools.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/01-15/074-isolated-candidate-correction.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - references/orchestration.md
  - references/validation.md
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/planlib.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - git diff --check
acceptance:
  - Generate one versioned worker execution contract deterministically from the exact committed active-plan bytes admitted for one initial or correction attempt; bind it to the repository identity, source HEAD, plan path, plan digest, orchestration run identifier, and attempt lineage.
  - Include only the plan's primary invariant, normalized write scope, context files, required specifications, acceptance items, focused-validation commands, explicit exclusions, and hard stop conditions needed by that attempt.
  - Require every writable delegated plan to declare exactly one nonblank `primary_invariant`, reject a missing or ambiguous invariant before worker start, and preserve compatibility for plans that are parsed or archived without writable delegation.
  - Keep the active plan and directly read normative specifications as the implementation source of truth; require the worker to read them, and treat the generated record as a supplemental bounded projection that cannot override, omit as satisfied, or amend source requirements.
  - Validate the record schema, size, normalized repository-relative paths, digests, identity, lineage, and exact equality to a fresh derivation immediately before worker invocation; fail closed on any mismatch, unknown field, duplicate item, symlink escape, or plan change.
  - Mount or copy the record into the isolated worker boundary as read-only input and prevent the worker from changing the active plan, generated record, runner, validation authority, source worktree, or parent-owned execution state.
  - Do not include prompts, worker output, environment values, credentials, host-specific absolute paths, raw logs, or undeclared repository files in the record.
  - Build the worker prompt from fixed repository policy plus the verified structured record instead of a separately maintained restatement of plan details; do not create a second manual source that can drift from the plan.
  - Preserve existing isolated-clone, no-hardlink, clean-source, object-database, model-routing, correction-budget, candidate-admission, validation-order, and external-effect boundaries.
  - Add deterministic median, edge, negative, and untuned holdout cases for exact derivation, source-plan mutation, digest and lineage mismatch, missing primary invariant, duplicate and unknown fields, path traversal and symlink escape, oversized input, attempted contract mutation, and attempted authority widening.
  - Keep root and generated runner behavior byte-identical, keep root and generated orchestration policy and Skill semantics aligned after path normalization, and preserve project-owned files through supported Copier copy and update paths.
  - Record the behavior under Unreleased, run focused validation only after parent diff and critical-invariant review, run the authoritative suite exactly once for an otherwise acceptable candidate, and finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 承認済みactive planから一つの読み取り専用worker実行契約を生成し、元planを置換または拡張せずに一回の隔離実装へ渡す。

## Context

The current runner constructs a prose worker prompt from selected plan sections but does not expose one schema-validated input record bound to the exact plan bytes and attempt lineage.

The worker execution contract is the versioned read-only structured projection generated from one unchanged accepted active plan for one isolated writable worker attempt. It supplements rather than replaces the plan and normative specifications.

Reducing worker context is useful only when the omitted material is irrelevant. Normative instructions, scope, the primary invariant, acceptance items, and stop conditions must remain directly reachable and cannot be summarized away.

## Decisions

- Derive the worker execution contract from the accepted active plan for every attempt; do not maintain a second hand-written task contract.
- Use one primary invariant as the writable delegation boundary and fail before invocation when that boundary is absent or ambiguous.
- Keep the source plan and normative specifications authoritative and require direct worker reads.
- Keep the generated record read-only, bounded, schema-validated, digest-bound, and free of secrets and raw interaction content.
- Preserve all existing runner isolation, authorization, correction, review, and validation gates.

## Tasks

- [ ] Define and validate the versioned worker execution contract and exact plan-to-record derivation.
- [ ] Integrate the verified read-only record into initial and correction worker invocation without broadening worker authority.
- [ ] Align root and generated policy, Skill, runner, plan parsing, inventories, and non-destructive Copier behavior.
- [ ] Add deterministic accepted, rejected, tampering, isolation, compatibility, and holdout coverage.
- [ ] Review the candidate diff and primary invariant, run focused validation, complete independent review, run the authoritative suite once, and archive the accepted plan before plan 114 starts.

## Validation Notes

- Decision audit selected a plan-derived record instead of a manually duplicated contract and retained the source plan as authority.
- The advisory referent contract sealed the worker execution contract as a supplemental record for one worker attempt, not as a replacement plan or a new authorization source.
- Plan 114 must not start until this plan is accepted and archived.
