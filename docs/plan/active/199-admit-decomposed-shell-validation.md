# Admit decomposed shell parser validation

status: in_progress
primary_invariant: each reconstructed shell parser layer has one exact focused command and one layer-local compile command before any implementation candidate can use those commands as acceptance evidence
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
  - scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
preservation_scope:
  - scripts/project_workflow/copier_fixture.py
  - tests/test-copier-fixture.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/active/198-integrate-bounded-copier-fixture-validator.md
  - docs/plan/checked/2026/08/16-31/105-admit-reconstructed-plan-validation-commands.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Admit exact focused and compile validation commands for the decomposed shell parser and validator paths without broadening any existing command grammar or generated-project policy.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:81f5c9a17f69ba98b9e9dfd9efc421f3706c77e30889fa375af4a022948a23e8","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
integration_gates:
  - preserve the rejected Plan 197 candidate paths without editing, staging, committing, importing, or accepting them
  - Plan 200 remains deferred until this plan is checked and its exact checked archive path replaces the active predecessor
checked_summary_ja: 分割後のshell parserとCopier validatorに限定した検証commandを実装前に受理する。

## Decisions

- decomposed_validation_admission means the checked validation-command policy entries required before independently executable parser-layer plans are created.
- Admit exact direct commands for `tests/test-shell-lexical.py`, `tests/test-shell-functions.py`, `tests/test-shell-execution.py`, and `tests/test-copier-fixture-validator.py`.
- Admit four exact layer-local compile commands, each covering only the module and test created by its owning plan.
- Admit one optional aggregate compile command over all four modules and tests for Plan 205 after every path exists.
- Admit the exact `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh` CLI command.
- Keep the current `copier_fixture.py` commands admitted for historical plan verification, but do not use them as witnesses for the reconstructed lineage.
- Do not change generated-project validation policy because these commands are root repository planning authorities only.
- Use bounded parent implementation and independent review because this plan changes validation-authority code and the writable runner must not write `scripts/` or `tests/` authority paths.

## Tasks

- [ ] Add the exact root-only focused, four layer-local compile, aggregate compile, and validator CLI command forms.
- [ ] Add positive and near-match rejection tests for path order, omitted files, extra files, alternate Python executables, alternate fixture paths, and extra CLI arguments.
- [ ] Confirm existing historical reconstructed commands remain byte-for-byte accepted and generated policy still rejects every root-only command.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 200 with this plan's exact checked archive as predecessor.

## Validation Notes

- This plan changes validation admission only and creates no parser or validator implementation.
- The two rejected Plan 197 candidate paths remain read-only preservation evidence.
