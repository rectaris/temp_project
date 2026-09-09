# Freeze worker-contract scenarios before implementation

status: checked
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: commit executable worker-contract scenario inputs and expected outcomes before implementation and keep their identity unchanged afterward
write_scope:
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/worker-contract-scenarios.json
  - tests/fixtures/orchestration/worker-contract-holdout.json
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/113-generate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - references/orchestration.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
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
  - Add deterministic median, edge, negative, and untuned holdout cases for exact derivation, source-plan mutation, digest and lineage mismatch, missing primary invariant, duplicate and unknown fields, path traversal and symlink escape, oversized input, attempted contract mutation, and attempted authority widening.
replan_source: docs/plan/active/113-generate-plan-bound-worker-contract.md
replan_contract: docs/plan/replanned/contracts/113-generate-plan-bound-worker-contract.json
integration_gates:
  - preserve tuned scenarios at sha256:ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf and holdout at sha256:a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27 before plan 135 starts
  - plan 135 must treat the tuned scenarios as read-only context and the holdout as an opaque digest-sealed artifact; plan 136 must reject drift in both files
successor_plans:
  - docs/plan/active/134-freeze-worker-contract-scenarios.md
  - docs/plan/active/135-enforce-plan-bound-worker-contract.md
  - docs/plan/active/136-integrate-plan-bound-worker-contract.md
inherited_acceptance_digests:
  - sha256:ba6dde8e1485e27de30d5dafbf57d39b619e63557aea73ef8fe29d65700515a7
checked_summary_ja: worker実装より前に通常caseと独立holdoutの入力と期待結果を固定し、後続planから変更できない証拠にする。

## Decisions

- Store concrete inputs and expected outcomes, not coverage labels, in separate tuned-scenario and holdout files.
- Make one generic evaluator accept one caller-selected fixture file without duplicating its inputs in test code; the default test path selects only tuned scenarios.
- Record the committed file digests in validation notes and require exact digest continuity in plans 135 and 136.
- Do not implement or modify worker-contract production behavior in this plan.
- Use bounded parent implementation and independent review because fixtures and checks are validation authority.

## Tasks

- [x] Define versioned exact-shape scenario records for median, edge, negative, and holdout classes.
- [x] Add a generic executable evaluator that reports observed rejection or acceptance for a caller-selected fixture; keep holdout behavior reachable only through the explicit Plan 136 holdout selector.
- [x] Keep the holdout physically separate from reusable prompts and non-holdout tuning data.
- [x] Align static inventory and Copier preservation checks for the new fixtures.
- [x] Review the bounded parent diff, run focused validation, obtain independent review, run the authoritative suite once, and archive this plan with the committed fixture digests.

## Validation Notes

- The user authorized continuation from the Plan 113 replan stop on 2026-08-21.
- Exact scenario bytes are intentionally created here rather than in the restructuring contract.
- Frozen tuned-scenario digest: `sha256:ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf`.
- Frozen holdout digest: `sha256:a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27`.
- Focused validation passed: `python3 tests/test-sandboxed-plan-worker.py` (80 tests), `python3 scripts/check-copier-template.py`, and `git diff --check`.
- Independent review closed after two bounded parent remediation rounds; the final fresh review reported zero unresolved High or Medium findings.
- The authoritative validation list completed once with all commands passing, including project lint, smoke, and the required real Copier update lane.
- No unresolved risk remains in this fixture-freezing scope. Production worker-contract behavior and explicit holdout execution remain assigned to Plans 135 and 136.
