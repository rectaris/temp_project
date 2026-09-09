# Admit v1.4.5 Copier wiring and source inventory

status: checked
primary_invariant: the v1.4.5 before and after migration commands and every required source path are admitted through the existing single Copier update inventory
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - copier.yml
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/177-align-validation-witness-provenance-policy.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/181-verify-plan176-successor-acceptance.md
  - docs/plan/replanned/2026/08/16-31/178-wire-validation-witness-copier-transition.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
replan_source: docs/plan/active/178-wire-validation-witness-copier-transition.md
replan_contract: docs/plan/replanned/contracts/178-wire-validation-witness-copier-transition.json
integration_gates:
  - preserve the dirty tests/copier-update.sh candidate without editing, staging, committing, or validating it in this slice
  - Plan 183 must start only after this plan is checked and its exact checked archive path replaces the active dependency
successor_plans:
  - docs/plan/active/182-admit-v145-copier-wiring.md
  - docs/plan/active/183-build-bounded-copier-transition-fixture.md
  - docs/plan/active/184-verify-plan178-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: v1.4.5のbefore/after migrationと必要source pathを既存の単一inventoryへ接続する。

## Decisions

- v1.4.5 Copier wiring slice means the successor that admits the exact before/after migration commands and the one-inventory source membership before runtime fixture work begins.
- Match the checked Plan 180 CLI exactly: `--destination . --stage before|after` at version v1.4.5.
- Keep the existing inventory loop and Plan 166 general inventory ownership unchanged.
- Remove runtime-process assertions, the assertion that provenance is `pending` before the fixture release event, fixture ready/release synchronization checks, and guardian capability challenge-response checks from this slice's checker candidate; Plan 183 owns those connected checks.
- Use bounded parent implementation because `copier.yml` and the checker define a security-sensitive migration and validation boundary.

## Tasks

- [x] Re-admit only the preserved v1.4.5 migration and inventory hunks against checked Plans 177, 180, and 181.
- [x] Make the checker parse the exact v1.4.5 YAML entries and prove unique `copier.yml` and snapshot-script inventory membership without claiming runtime fixture behavior.
- [x] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [x] Archive and commit only this plan's four implementation paths plus parent-owned lifecycle files.

## Validation Notes

- All prior Plan 178 reviews and diagnostic checks are advisory history only; initialize a fresh execution ledger.
- The preserved tests/copier-update.sh bytes remain unaccepted input owned by Plan 183.
- Do not run tests/copier-update.sh in this slice.
- Parent-direct execution ledger `/tmp/plan182-execution-state.json` records one independent review, one focused validation event, and exactly one authoritative validation event without a stop reason.
- Independent review `.agent-artifacts/reviews/182-wiring-review.md` reported Accept with High 0, Medium 0, and Low 0 for the exact four-path implementation diff.
- Focused and authoritative validation each passed `python3 scripts/check-copier-template.py` and `git diff --check`.
- Repository completion validation passed `scripts/lint-project-workflow.sh` and `tests/smoke.sh`; actionlint was unavailable and the smoke script reported its configured skip.
- `tests/copier-update.sh` was not executed, staged, edited, or accepted in this slice and remains reserved for Plan 183.
