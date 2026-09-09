# Separate synthetic Copier version tags

status: checked
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: low
implementation_ambiguity: low
primary_invariant: each synthetic Copier version used by the update fixture resolves to a unique ordered commit identity
write_scope:
  - tests/copier-update.sh
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/138-integrate-provider-auth-call-context.md
required_specs:
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - sh -n tests/copier-update.sh
  - git diff --check
validation:
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Create the synthetic `v1.3.1` tag on a commit after the synthetic `v1.2.2` tag so Copier resolves the requested update version uniquely.
  - Keep the candidate template tree, Plan 138 acceptance, validation authority, policy-preservation assertions, safety conditions, and external-effect authority unchanged.
  - Validate the isolated Copier update fixture and finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: Copier更新fixtureのv1.2.2とv1.3.1を別commitへ結合し、更新先versionを一意に解決できるようにする。

## Context

Plan 138 authoritative validation stopped because the temporary template repository assigned `v1.2.2` and `v1.3.1` to the same candidate commit.
Copier resolved that tree as version 1.2.2 and rejected the intended v1.3.0 to v1.3.1 update as a downgrade.
Independent classification found one bounded fixture defect with unchanged source scope, acceptance, validation authority, invariant boundaries, safety conditions, and external-effect authority.

## Tasks

- [x] Add one empty synthetic commit between the v1.2.2 and v1.3.1 tags without changing candidate template bytes.
- [x] Run the bounded Copier update validation and independent review.
- [x] Archive this repair and leave Plan 138 ready for a fresh execution run.

## Validation Notes

- Source execution ledger `/tmp/plan138-ledger.3Y8tmg/execution.json` stopped in `repair_required` after the first authoritative run.
- Repair execution ledger `/tmp/plan141-ledger.Jbc7nW/execution.json` records the initial stale v1.2.2 provenance assertion, the bounded exact-v1.3.1 remediation, and the successful authoritative rerun.
- `tests/copier-update.sh` and `git diff --check` passed after independent review reported High 0, Medium 0, and Low 0.
