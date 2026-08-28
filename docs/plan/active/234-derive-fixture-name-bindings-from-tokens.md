# Derive fixture name bindings from lexical tokens

status: in_progress
primary_invariant: the bounded fixture checker decides which names a fixture may bind only from the lexical tokens the fixture is parsed into, reports a name unsettled whenever any binding surface may set it and whenever the surface itself is written in a form the checker does not enumerate, and leaves every existing rule rejecting and accepting exactly the operations it rejects and accepts today
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
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
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/replanned/2026/08/16-31/226-scope-fixture-alternate-path-rule.md
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
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
successor_plans:
  - docs/plan/active/234-derive-fixture-name-bindings-from-tokens.md
  - docs/plan/active/235-settle-fixture-words-from-a-modelled-grammar.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/232-settle-fixture-words-from-a-modelled-grammar.md
replan_contract: docs/plan/replanned/contracts/232-settle-fixture-words-from-a-modelled-grammar.json
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not change which operations any existing rule reports in this plan; the model is added, not applied
  - Plan 235 must start only after this plan is checked and its exact checked archive path replaces the active dependency
checked_summary_ja: 名前を束縛しうる面を字句トークンから導き、読めない綴りは未解決として扱う。

## Decisions

- Enumerate what the model reads and report everything else unproven. Thirteen independent review rounds across the stopped plans each found another written spelling that a modelled-then-corrected reader settled, so the reader must accept only the forms it enumerates and must never fall through to a literal reading of a form it does not enumerate.
- Read every binding surface from the lexical tokens the fixture is already parsed into, never from the raw fixture text. Each round of the stopped plan found another spelling in which a quoted span, a command substitution, or a line continuation hid a separator from a pattern matched over raw text, and the tokens the checker already holds carry those boundaries exactly.
- Settle a name only when the checker proves no surface binds it. The default answer is unsettled, so a surface written in a form the checker does not enumerate leaves the name unsettled instead of leaving it settled by what is written above the reader.
- Treat a command word the checker cannot resolve to one name as a command that may bind every bare operand it is written with, because a fixture may reach an assigning command through a name, through another name, or through a launcher.
- Leave the value a fixture inherits unproven. A first binding written under a condition, in a subshell, in a pipeline, or in the background leaves the surrounding shell's own value on the path the fixture does not take, and no written text carries it.
- Withdraw a modelled command wherever the fixture may shadow it. A declared function may carry the name of any command the checker reads, including the launcher names, so a declaration of such a name removes the reading rather than narrowing it.
- Reuse the preserved candidate as coverage. The local branch plan-232-candidate holds the reader that three independent review rounds were run against, and the stopped plan records every finding those rounds reported, so each recorded spelling becomes a unit case rather than a later finding.
- Keep every existing rule unchanged. The model is proven by its own unit coverage, so the committed fixture check and the full test suite must report exactly what they report before the plan.

## Tasks

- [ ] Derive from the lexical tokens every assignment a fixture writes, including each assignment written after the first one of a command, and report unsettled every name the checker holds no recorded binding for.
- [ ] Decide from the tokens whether each recorded assignment runs in front of a command, report unsettled every name that may, and prove that a standalone assignment written on its own line is not one.
- [ ] Enumerate the commands that bind a name, read each operand through complete quote removal, and report unsettled every bare operand of a command word the checker cannot resolve to one enumerated name.
- [ ] Enumerate the remaining binding surfaces the fixture may write, including a loop head, the names a shell keeps itself, and a first binding whose inherited value the fixture does not overwrite.
- [ ] Cover every spelling the stopped plan recorded, including a second assignment written as one command, a quoted value inside a prefix run, a quoted name given to an assigning command, a command substitution written inside a prefix run, a continued loop head, and a command name reached through two names.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 232 archive records the three review rounds and the binding surfaces each round found.
