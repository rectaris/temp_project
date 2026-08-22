# Freeze replacement receipt holdout evidence

status: in_progress
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
parent_direct_reason: independent holdout creation and sealing are parent-owned validation authority and must remain opaque to later implementation work
primary_invariant: freeze one new independent completion-receipt holdout artifact by path and digest without exposing its contents to the evaluator-repair implementation boundary
write_scope:
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/worker-completion-receipt-holdout-v2.json
  - tests/smoke.sh
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/155-integrate-structured-worker-completion-receipt.md
  - docs/plan/checked/2026/08/16-31/157-integrate-structured-worker-completion-enforcement.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Add deterministic median, edge, negative, and untuned holdout cases for successful and failed attempts, partial command execution, stale or replayed receipt, plan and contract mismatch, patch and path mismatch, false success claims, missing out-of-scope declaration, unknown fields, oversized values, traversal and symlink escape, and attempted secret or raw-output inclusion.
  - Keep root and generated runner behavior byte-identical, keep root and generated policy and Skill semantics aligned after path normalization, and preserve supported non-destructive Copier updates.
replan_source: docs/plan/active/155-integrate-structured-worker-completion-receipt.md
replan_contract: docs/plan/replanned/contracts/155-integrate-structured-worker-completion-receipt.json
integration_gates:
  - an independent read-only reviewer designs one schema-valid replacement holdout case without changing production or evaluator code
  - the main implementation boundary records only the new file path digest and preservation markers and does not inspect or execute its contents
  - Plans 161 and 162 must preserve the exposed original holdout bytes and record its initial failure separately
successor_plans:
  - docs/plan/active/160-freeze-replacement-receipt-holdout-evidence.md
  - docs/plan/active/161-repair-receipt-fixture-projection.md
  - docs/plan/active/162-integrate-structured-worker-completion-receipt.md
inherited_acceptance_digests:
  - sha256:82556513f481a08d6941fd122a8a4e8633391421047d5e7803cd57a89a328fe4
  - sha256:5906dbdbacb32377ea164fff882c5cb1f5b10878410be01b008e50d93015212e
checked_summary_ja: evaluator修復から内容を隔離した新しいworker完了受領書holdoutをpathとdigestで固定する。

## Context

The original sealed holdout was exposed by its first execution and revealed a baseline command identifier that predates the accepted positional identifier rule. It remains unchanged but can no longer serve as untuned post-repair evidence.

## Decisions

- Delegate only the new holdout file to an independent helper with no production or evaluator writes.
- Record its path and digest without parsing or executing it in the main session.
- Preserve both old and new holdout files through Copier and smoke checks.

## Tasks

- [ ] Create one independent replacement holdout file with exact ownership and no other writes.
- [ ] Seal its path and digest without inspecting or executing its contents in the main session.
- [ ] Add existence, inventory, smoke, and Copier preservation checks that do not parse the new holdout.
- [ ] Obtain independent review, run validation once, and archive the plan.

## Validation Notes

- The original holdout remains unchanged at `sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76`.
