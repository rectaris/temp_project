# Align planning guidance with the current manifest contract

status: in_progress
task_types:
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/active/061-current-plan-manifest-reference.md
  - references/planning.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
context_files:
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The planning reference lists the current required and optional active-plan fields.
  - Removed open-plan fields are identified only as legacy archive compatibility and are not recommended for new plans.
  - Deterministic validation prevents the stale field list from returning.
checked_summary_ja: planning reference の推奨項目を現行 manifest contract と同期し、廃止済み open-plan fields の再導入を検査する。

## Context

The planning reference must document the active manifest fields accepted by the current linter.

The planning reference recommends legacy fields that the current generated linter rejects for active and backlog plans.

## Decisions

- Treat the generated plan manifest contract as the source of truth for reusable planning guidance.
- Mention legacy fields only when explaining checked-archive compatibility.

## Tasks

- [ ] Replace the recommended field list with the current required and optional fields.
- [ ] Add static checks that reject the removed open-plan fields in the recommendation section.
- [ ] Run the required validation commands.

## Validation Notes

- Pending.
