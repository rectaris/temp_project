# Verify Plan 187 successor acceptance

status: shelved
shelved_reason: 製品ファイルを一切変えない検証専用プランであり、過去プランの受け入れを形式的に再確認するだけの費用に見合わないとオーナーが指示した
shelved_at: 2026-08-30
primary_invariant: checked Plan 182, the checked runtime and checker replacements, and the three checked enforcement repairs jointly satisfy the unchanged Plan 187 acceptance before Plan 184 performs its own verification
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/backlog/184-verify-plan178-successor-acceptance.md
  - docs/plan/plan.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
successor_plans:
  - docs/plan/active/244-reject-fixture-command-redefinition.md
  - docs/plan/active/245-bind-fixture-inputs-to-one-inventory.md
  - docs/plan/active/246-bind-pre-schema-fixture-contents.md
  - docs/plan/active/247-verify-plan187-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
replan_contract: docs/plan/replanned/contracts/187-verify-plan183-successor-acceptance.json
integration_source_ids:
  - 187
integration_gates:
  - Plans 244, 245, and 246 must be checked and their exact checked archive paths must replace these active context paths before focused validation
  - do not edit, stage, or commit scripts/check-copier-template.py, scripts/project_workflow/copier_fixture_validator.py, or tests/copier-update.sh in this plan
  - rebind the Plan 184 lineage reference from the archived Plan 187 to this plan's checked archive
  - Plan 184 must not start until this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: checked Plan 182、runtime・checker後継、三つのenforcement修理を統合確認し、Plan 187の受入条件を維持する。

## Decisions

- Retain the complete Plan 187 acceptance here so no requirement is lost by the split.
- Plan 187 stopped because its independent review found three separately reproducible enforcement gaps that it had no authority to repair. This plan re-runs that verification only after all three repairs are checked.
- Reject a repeat of the Plan 187 outcome. The mutation evidence must cover command redefinition, inventory-external inputs, and pre-schema content omission, not only removal and duplication of bound operations.
- Verify rather than reimplement. No checker, validator, or fixture file may be edited here.
- Plan 184 resides in docs/plan/backlog after Successor Backlog Deferral, so its rebinding writes that backlog path rather than the former active path.

## Tasks

- [ ] Replace the Plans 244, 245, and 246 active context paths with their exact checked archives and verify each implementation commit and its review evidence.
- [ ] Confirm the final checker retains Plan 182's parsed migration and one-inventory checks and every operation, region, and ordering rule checked Plan 186 bound.
- [ ] Reproduce all three Plan 187 High findings read-only and confirm each is now rejected.
- [ ] Run the original Plan 183 focused validation and a fresh independent read-only review with zero unresolved High or Medium findings.
- [ ] Archive and commit only lifecycle files, then rebind Plan 184 to this checked archive.

## Validation Notes

- Pending. This plan starts only after Plans 244, 245, and 246 are checked.
- The stopped Plan 183 and Plan 187 ledgers and reviews are advisory history and cannot authorize this successor acceptance.
- This plan does not execute the complete Copier transition and does not change product files.
- The run reproduced all three Plan 187 High findings read-only and confirmed the exact reproductions are now rejected: `command_shadowing` for no-op `grep`, `test`, and `touch` declarations, `inventory_region` for a staging the inventory loop does not carry, and the pre-schema content refusal for emptied heredoc bodies. `tests/copier-update.sh` stayed byte-identical at sha256 174ea284.
- The final checker retains every Plan 182 and Plan 186 binding: 45 bound operations with 45 unique names, two named regions plus the transition anchor, 43 ordering pairs, the inventory "exactly one" assertions, the snapshot-marker refusal, and the validator delegation. A 90-case removal and duplication sweep over the bound operations left no survivors.
- All four declared focused validation commands exited zero: `sh -n tests/copier-update.sh`, `python3 scripts/check-copier-template.py`, `python3 scripts/restructure-plan.py --verify`, and `git diff --check`.
- One read-only advisory `code-review` sub-agent was used for the fresh independent review. It held no write scope, and acceptance was retained in the main session.
- That review returned two High and one Medium finding, and the main session reproduced all three against the committed gate with the fixture left byte-identical. First, a staging outside the inventory region is accepted whenever any reachable editing command names a path under the update-source roots, without the inventory being consulted, so `sed -i "1r $root/AGENTS.md" "$update_source/NOTICE"` buys acceptance for `fixture_git "$update_source" add -- NOTICE`. Second, the gate reads only the fixture bytes, so a redefinition in the sourced `tests/lib-copier.sh`, or a no-op `run_copier` in the fixture itself, still makes bound observations vacuous. Third, the bound pre-schema constructions are accepted inside a never-taken branch or an uncalled function.
- Task 4 requires zero unresolved High or Medium findings and this plan may not edit the checker, the validator, or the fixture, so the run stopped before completion. The three findings are independently repairable with bounded write and validation scope and leave this plan's requirements, acceptance, and safety conditions unchanged, so they were recorded as bounded repair plans 248, 249, and 250 rather than as a restructuring of this plan.
- The Plan 184 lineage rebinding was not performed, because this plan has no checked archive to rebind to. This plan returns to the backlog unchanged and resumes through a fresh run after Plans 248, 249, and 250 are checked.
