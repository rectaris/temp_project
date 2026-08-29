# Restore the resolution model as the single update authority

status: in_progress
primary_invariant: no bounded fixture rule rejects an operation the checked resolution model proves is not a Copier update of the sanctioned destination, and every spelling the blanket detector uniquely catches still rejects
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
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md
  - docs/plan/checked/2026/08/16-31/233-collect-fixture-aliases-from-a-modelled-grammar.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md
successor_plans:
  - docs/plan/active/227-complete-bounded-copier-fixture-runtime.md
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not change what a relative installed-workflow command word proves; the checked Plan 231 decision that no working-directory model exists stays unchanged
  - leave the unresolved-dispatch admission unchanged; the relative wrapper self-update lanes are classified separately
  - Plan 227 resumes only after this plan is checked and its exact checked archive path replaces the active dependency
checked_summary_ja: 解決モデルを唯一のupdate判定権とし、旧来の部分文字列検出が証明済み非updateを却下する欠陥を修復する。

## Decisions

- Repair the checker, not the fixture. The only fixture-only way to clear the rejected Copier copy lanes is to remove the substring `update` from the fixture's own directory and variable names, which silences a substring detector without changing behavior. That is the bypass shape Plan 186 is chartered to reject.
- Keep detection and reading one function. Plan 231 made `_update_reading` the single reader; this repair removes the second, independent trigger rather than adding a third.
- Fold before demoting. Every spelling the blanket detector uniquely catches must first read as an unproven update, so the reader returns an empty destination set and the operation still rejects. Demoting the detector without the fold turns over-rejection into silent acceptance, which is the unsafe direction.
- Read the script name of a settled installed-workflow path. A path whose final segment is written entirely as text and is not an update entry point runs no update, so the operation is not an alternate path. A segment that carries an expansion, or a path that does not settle, stays unproven.
- Leave the relative wrapper self-update lanes alone. Their destination is genuinely unanchored, so the resolution model does not prove them safe and this invariant does not cover them. They are classified separately.

## Tasks

- [ ] Fold every spelling `_dispatch_runs_update` uniquely catches into `_update_reading` as an unproven update, covering the interpreter string form, the command-prefix form, the positional-forwarding form, and the expansion-carried form.
- [ ] Make the modelled reader the single alternate-path trigger and remove the blanket substring trigger, so an operation the reader proves runs no Copier update is no longer an alternate path.
- [ ] Read the final segment of a settled installed-workflow path and prove that a command word naming a non-update script runs no update, keeping an unsettled or expansion-carrying segment unproven.
- [ ] Add one regression test per folded spelling asserting the alternate-path rejection still fires, and one test asserting a Copier copy lane whose operands mention the update word is accepted.
- [ ] Confirm the committed tests/copier-update.sh still passes --check without editing it, and record the residual rejections that remain for Plan 227 and for the separate wrapper self-update classification.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 227 stop record holds the reproduction commands and the finding classification this repair is derived from.
