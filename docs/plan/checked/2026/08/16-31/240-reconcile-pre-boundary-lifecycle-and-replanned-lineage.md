# Reconcile pre-boundary lifecycle archives and replanned lineage references

status: checked
primary_invariant: repository lineage verification accepts a frozen pre-boundary archive and moves an unstarted plan's replanned reference only through bounded, digest-bound, write-once evidence, and rejects every other drift
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
implementation_tier: 2
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/test-plan-restructure.py
  - scripts/lint-project-workflow.sh
  - docs/plan/replanned/baselines/pre-boundary-lifecycle-reconciliations-v1.json
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/224-admit-legacy-contract-successor-rebinding.md
  - docs/plan/replanned/baselines/live-successor-rebinds-v1.json
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Lineage verification admits a plan that reached a checked archive without an activation record only through a write-once registry that binds one boundary commit, the chain-final baseline digest, and the exact archive bytes, and rejects drifted, uncommitted, unarchived, or rewritten evidence.
  - An unstarted plan may move a reference that names a replanned source only to a checked successor of that same replan contract, only in predecessor, context, integration-gate, and body positions, and never with a change to plan status, acceptance, scope, or contract identity.
  - The workflow lint fails when repository lineage verification fails, so a broken plan lineage cannot stay undetected between restructuring operations.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:be4a5ee2d41020f63294102d01f5358ee640f4f8423759b0356087f1c21d1e40","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:4927c19a59cf1aacb3764d6d09019b101f88ffa3f23541be69c12726d07f0bc2","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:4343edcd22fb93e007e580b3b8c7da8ebaca9caed7d978df103bcb53aff899e8","stage":"focused","witness":"scripts/lint-project-workflow.sh"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/224-admit-legacy-contract-successor-rebinding.md
integration_gates:
  - do not rewrite Git history; the reconciliation registry replaces the rewrite route the user rejected
  - do not weaken any existing lifecycle, rebinding, or activation rule; both capabilities only add bounded evidence-backed routes
  - do not use the reconciliation registry for work after its boundary commit
checked_summary_ja: activation記録を欠いたままcheckedになったplanと、replanned元を参照する未着手planの参照を、限定された証拠付きの経路だけで解決できるようにする。

## Decisions

- Repair the frozen lineage without rewriting history. The user rejected the history rewrite route, so the registry admits only the four already-archived plans and binds each one to a boundary commit, an archive digest, and its chain-final baseline digest.
- Make the registry write-once. Once committed it can never grow, so a defect introduced after the boundary can never be admitted through it.
- Add `rebind_lineage` instead of restructuring Plans 186 and 187. Their lineage references are stale, but their requirements are unchanged, so restructuring would rewrite requirements that no evidence disputes.
- Bound the new rebinding to `predecessor_plans`, `context_files`, `integration_gates`, and body tokens, and to plans that have not started. Contract identity fields stay immutable.
- Run lineage verification inside the workflow lint. The breakage stayed hidden for many commits because no routine check ran it.

## Tasks

- [x] Add the write-once pre-boundary lifecycle reconciliation registry and consult it during lineage verification.
- [x] Record the four plans that left `deferred` without an activation record before the boundary commit.
- [x] Add the `lineage_rebind` record kind and the `rebind_lineage` operation.
- [x] Mirror the tool into the Copier template and document both routes in the root and template plan workflow specifications.
- [x] Add regression tests for registry admission, registry rejection, lineage-reference admission, and lineage-reference rejection.
- [x] Run repository lineage verification from the workflow lint.

## Validation Notes

- Focused validation passed: `python3 tests/test-plan-restructure.py` with 153 tests, `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-copier-template.py`, `scripts/lint-project-workflow.sh`, and `git diff --check`.
- The authoritative suite passed once: `python3 tests/test-plan-restructure.py`, `python3 scripts/restructure-plan.py --verify`, `python3 scripts/check-copier-template.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check`.
- Lineage verification failed from commit `6ddfde5` until this plan. The four reconciled plans are 227, 231, 233, and 235; each one left `deferred` by direct edit and is now frozen in a checked archive.
- The registry admits nothing new. Its boundary commit is `6fcc959f4908b38ef2846f6d3e4abff67c3639dd`, and every entry must already exist with the same archive bytes at that commit.
- No helper agents were used.
