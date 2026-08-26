# Restore terminal checked archive status

status: checked
implementation_tier: 1
primary_invariant: every plan file indexed by docs/plan/checked.md carries the terminal status: checked and no other archive byte changes
task_types:
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: low
implementation_ambiguity: low
write_scope:
  - docs/plan/checked/2026/07/01-15/028-completion-lifecycle-gate.md
  - docs/plan/checked/2026/07/16-31/029-referent-first-semantic-guard.md
  - docs/plan/checked/2026/07/16-31/030-chat-visible-referent-staging.md
  - docs/plan/checked/2026/07/16-31/031-template-review-remediation.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/plan/checked.md
  - scripts/restructure-plan.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Set status: checked in every partitioned archive indexed by docs/plan/checked.md that still carries a nonterminal status, and change no other byte of those archives.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7d85fee6d1628b08cbf1049f9ae7d5f286adeb98bc59505881f6d17d2d79e80f","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans: []
checked_summary_ja: checked索引に載る保管済みplanの終端statusをcheckedへ統一する。

## Decisions

- A terminal checked archive is a plan file that `docs/plan/checked.md` indexes under a `YYYY/MM/01-15` or `YYYY/MM/16-31` partition and that records `status: checked`.
- Archives `028`, `029`, `030`, and `031` still record `status: ready_to_archive`, which the finalizer used before the current two-step completion lifecycle existed.
- `activation_checked_pairs` in `scripts/restructure-plan.py` is fail-closed over every partitioned checked row, so one nonterminal archive blocks every future activation record in the repository.
- Change only the `status` line of each affected archive. Preserve every other manifest field, body byte, and index row.
- Leave the twenty-three unpartitioned `docs/plan/checked.md` rows for plans `001` through `023` unchanged; `CHECKED_PATH_RE` skips them and they are a separate index invariant.
- Use direct parent implementation because the change is bounded, reversible, and fully covered by the existing repository verification command.

## Tasks

- [x] Set `status: checked` in the four affected partitioned archives.
- [x] Confirm no other byte of those archives changed.
- [x] Confirm that repository verification accepts the result and that an activation record can resolve every partitioned checked row.
- [x] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- Each affected archive changed exactly one line from `status: ready_to_archive` to `status: checked`; `git diff` shows four insertions and four deletions in total.
- `activation_checked_pairs` now resolves 131 partitioned checked rows, including the Plan 213 archive, instead of failing on archive `028`.
- Focused validation passed `python3 scripts/restructure-plan.py --verify` and `git diff --check`.
