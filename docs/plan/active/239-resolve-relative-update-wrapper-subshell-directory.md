# Resolve a relative update wrapper against its subshell directory

status: in_progress
primary_invariant: a relative installed-workflow command word inside a subshell whose working directory is settled resolves to that directory, and stays unproven whenever the directory is not settled
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
  - docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md
  - docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md
  - docs/plan/checked/2026/08/16-31/235-model-fixture-word-grammar.md
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
  - docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md
successor_plans:
  - docs/plan/active/227-complete-bounded-copier-fixture-runtime.md
integration_gates:
  - do not edit tests/copier-update.sh; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not admit a relative command word whose subshell directory does not settle; the checked Plan 231 decision that an unanchored destination stays unproven holds everywhere else
  - leave the unresolved-dispatch admission unchanged; independent review found relaxing it unsound for a fixture that is not a transition
  - Plan 227 resumes only after this plan is checked and its exact checked archive path replaces the active dependency

## Decisions

- Model the subshell directory, not a general working directory. The committed fixture runs its two wrapper self-update lanes as `(cd "$out" && .project-agent-workflow/scripts/run-copier-update.sh --force)`. The operation model already carries a subshell enclosure, so the directory can be read from the operations inside that one subshell without inventing a whole-script directory state.
- Settle the directory or stay unproven. The relative word resolves only when the subshell contains exactly one directory change, it precedes the command word, and its single operand settles to an anchored path. Anything else keeps the current unproven reading, which still rejects.
- Do not weaken the checked Plan 231 rule. That plan decided a relative installed-workflow command word proves nothing because no working-directory model existed. This plan supplies the missing model for one bounded shape rather than admitting relative words generally.
- Keep the unresolved-dispatch admission unchanged. Independent review found that relaxing it is unsound for a fixture that is not a transition, where the alternate-path rule never runs.

## Tasks

- [ ] Read the enclosing subshell of a reachable operation and collect the directory changes that precede it inside that same subshell.
- [ ] Resolve a relative installed-workflow command word against the settled operand of a single preceding directory change, and keep it unproven when the subshell holds no directory change, more than one, or an operand that does not settle.
- [ ] Add regression tests covering the settled subshell form, a subshell with two directory changes, a directory change whose operand carries an unsettled expansion, and a relative command word with no enclosing subshell.
- [ ] Confirm the two wrapper self-update lanes of the committed fixture no longer report an alternate path when the fixture is read as a transition, without editing the fixture.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 227 stop record and the Plan 237 record hold the reproduction that isolates these two lanes and the independent review ruling that they need a separate classification.
