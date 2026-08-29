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

- [x] Fold every spelling `_dispatch_runs_update` uniquely catches into `_update_reading` as an unproven update, covering the interpreter string form, the command-prefix form, the positional-forwarding form, and the expansion-carried form.
- [x] Make the modelled reader the single alternate-path trigger and remove the blanket substring trigger, so an operation the reader proves runs no Copier update is no longer an alternate path.
- [x] Read the final segment of a settled installed-workflow path and prove that a command word naming a non-update script runs no update, keeping an unsettled or expansion-carrying segment unproven.
- [x] Add one regression test per folded spelling asserting the alternate-path rejection still fires, and one test asserting a Copier copy lane whose operands mention the update word is accepted.
- [x] Confirm the committed tests/copier-update.sh still passes --check without editing it, and record the residual rejections that remain for Plan 227 and for the separate wrapper self-update classification.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- The fold now covers every spelling the deleted blanket detector uniquely caught. `_forwards_an_update` and `_forwarded_dispatch_updates` carry the wrapper-marker clauses verbatim and tighten the copier-word clause from a substring anywhere in the dispatch to a non-option word equal to the update word. They are consulted only after the modelled loop is inconclusive, so an unreadable forwarded update returns an empty destination set rather than a proof of no update.
- `_check_alternate_paths` now triggers on `_runs_an_update` alone. `_dispatches_update` and `_dispatch_runs_update` were deleted; they had no other callers.
- `_names_no_update_script` proves no update only when every settled path sits inside the installed workflow, has a segment after it, and ends in written text with no expansion that is not an update script name. An empty or unsettled path set stays unproven.
- `_names_an_update_script` reads a name that says both the Copier word and the update word. Its docstring now records the installed-workflow invariant it depends on, so a future update entry point must keep both words in its name.
- `_names_an_installed_workflow` was extended with the same name reading, closing a bare update-script command word that a self-review parity harness found.
- A parity harness over a 392-sample corpus reported 3 loosened and 0 tightened readings against the previous validator. Two are the intended loosenings. The third is the disclosed Copier copy residual below.
- Independent review round 1 returned no High and no Medium finding and confirmed the fold reproduces the deleted detector on every forwarding shape it tested, that `_names_no_update_script` cannot clear any update-capable installed script, and that deleting the blanket detector removed no coverage. Its one Low finding, recording the name-rule invariant, was applied before the authoritative run.
- Residual, ruled a separate bounded plan by the review: a Copier copy or recopy into the sanctioned destination through a helper the fixture does not define stays accepted. The previous validator also accepted it whenever no update word happened to appear, so the earlier rejection was accidental. Reading copy destinations would block Plan 227, whose lane copy writes an unsettleable path.
- Residual, already held for a separate classification: the two relative installed-workflow self-update lanes still report `alternate_path`.
- Residual, pre-existing and unchanged: a bare Copier update forwarded through an interpreter or command prefix stays accepted, which is the finding already recorded against Plan 227.
- The committed fixture still passes `--check` and was neither edited nor executed. Its reproduction fell from 24 findings to 5, and the 5 remaining are Plan 227 work or the separate classification.
- Authoritative validation run once: 309 tests pass, `--check tests/copier-update.sh` passes, `scripts/lint-project-workflow.sh` exits 0, `tests/smoke.sh` passes, `git diff --check` is clean.
