# Freeze worker completion receipt scenarios before implementation

status: checked
task_types:
  - planning_docs
  - referent_first
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
parent_direct_reason: fixture inputs and their executable evaluator are parent-owned validation authority
primary_invariant: commit implementation-independent worker completion receipt scenarios and expected outcomes before production behavior changes and keep their identity unchanged afterward
write_scope:
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/114-validate-structured-worker-completion.md
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - references/orchestration.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Add deterministic median, edge, negative, and untuned holdout cases for successful and failed attempts, partial command execution, stale or replayed receipt, plan and contract mismatch, patch and path mismatch, false success claims, missing out-of-scope declaration, unknown fields, oversized values, traversal and symlink escape, and attempted secret or raw-output inclusion.
replan_source: docs/plan/active/114-validate-structured-worker-completion.md
replan_contract: docs/plan/replanned/contracts/114-validate-structured-worker-completion.json
integration_gates:
  - record the tuned and holdout fixture digests before plan 154 starts and preserve both exact files unchanged through plan 155
  - plan 154 must treat tuned scenarios as read-only context and the holdout as an opaque digest-sealed artifact
  - plan 155 must reject drift in either fixture before evaluation
successor_plans:
  - docs/plan/active/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/active/154-enforce-structured-worker-completion-receipt.md
  - docs/plan/active/155-integrate-structured-worker-completion-receipt.md
inherited_acceptance_digests:
  - sha256:82556513f481a08d6941fd122a8a4e8633391421047d5e7803cd57a89a328fe4
checked_summary_ja: worker完了受領書の通常caseと独立holdoutを実装前に固定し、後続planで同じ入力と期待結果を検証する。

## Context

The concrete implementation boundary is one active plan that adds exact bounded tuned and holdout fixture files for successful, failed, malformed, deceptive, tampered, traversal, symlink, oversized, and prohibited-content worker completion receipt cases without changing production runner behavior.

## Decisions

- Store concrete receipt inputs and expected outcomes in separate tuned and holdout fixture files.
- Use one generic evaluator selected by fixture path; keep the default worker test path tuned-only.
- Record committed fixture digests in validation notes and require exact continuity in plans 154 and 155.
- Do not change production receipt emission or validation behavior in this plan.
- Use bounded parent implementation and independent review because fixtures and their evaluator are validation authority.

## Tasks

- [x] Define exact-shape scenario records for every source-required success, failure, malformed, deceptive, tampering, path, and prohibited-content case.
- [x] Add a generic executable evaluator that reports observed acceptance or rejection for a caller-selected fixture.
- [x] Keep the holdout physically separate from reusable prompts and tuned data.
- [x] Align inventory and Copier-preservation checks for the new fixture files.
- [x] Review the bounded parent diff, run focused validation, obtain independent review, run the authoritative suite once, and archive this plan with the committed fixture digests.

## Validation Notes

- Plan 136 is checked at `docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md`.
- The source Plan 114 acceptance text is preserved exactly.
- Production receipt behavior and explicit holdout execution remain assigned to plans 154 and 155.
- Frozen tuned-scenario digest: `sha256:264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a`.
- Frozen holdout digest: `sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76`.
- Independent review initially found two Medium issues: missing successful-correction coverage and default holdout parsing. Both were corrected; the fresh rereview reported High 0, Medium 0, and Low 0.
- Focused validation passed with 83 runner tests, the Copier-template static check, and `git diff --check`.
- The authoritative validation list ran exactly once and every command passed, including root policy checks, change selection, workflow lint, smoke, and the required real Copier update lane.
- No unresolved risk remains in this fixture-freezing scope.
