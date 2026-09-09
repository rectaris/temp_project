# Resolve fixture destinations and aliases fail-closed

status: replanned
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/230-resolve-fixture-destinations-fail-closed.md
replan_contract: docs/plan/replanned/contracts/230-resolve-fixture-destinations-fail-closed.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/232-settle-fixture-words-from-a-modelled-grammar.md
  - docs/plan/active/233-collect-fixture-aliases-from-a-modelled-grammar.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: fixture checkerに送り先と別名の解決模型を追加し、決まらない場合は未証明として扱う。

## Decisions

- Separate the resolution model from the rule that consumes it. Plan 226 coupled them, and seven independent review rounds showed that each rule change exposed a new resolution gap, so the two invariants must be validated apart.
- Resolve fail-closed on both sides. An update destination this checker cannot settle stays unproven, and an alias this checker cannot place makes the destinations it may reach unproven as well.
- Read the operation as written in addition to every projected dispatch, because the execution graph drops the arguments of a launched command and scripts/project_workflow/shell_execution.py is outside this write scope.
- Settle a value against the environment the operation runs in, not the offset it is written at. A function body reassigned between its definition and its call must not settle to the definition value.
- Bound the settlement. The fixture reassigns a name from its own value, so expand each name at most once per text lineage under a fixed text budget instead of seeking a fixed point.
- Keep every existing rule unchanged in this plan. The model is proven by its own unit coverage, so the fixture check and the full suite must report exactly what they report today.

## Tasks

- [ ] Add a bounded settlement that expands a written path into comparable canonical texts and reports unproven when a name, a positional parameter, or an unmodelled word mark leaves it undetermined.
- [ ] Settle a value against the environment its operation runs in, and report unproven when a name the destination reads is reassigned between a function definition and any reachable call of it.
- [ ] Locate the effective command behind launcher prefixes, launcher options, and assignments, and read an unresolved effective command written in the link form as a link.
- [ ] Collect aliases from every reachable link operation, follow a tracked alias through a move or a symlink-preserving copy, and report unproven when an alias cannot be placed.
- [ ] Prove with unit coverage that each resolution helper reports unproven for every undetermined spelling, and that the committed tests/copier-update.sh check and the full test suite report exactly what they report before this plan.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 226 archive records the seven review rounds and the resolution gaps that motivated this split.
- The resolution model was implemented and carried through three independent review rounds. The full suite ran at 157 tests passing, `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh` passed, `scripts/lint-project-workflow.sh` passed, and `_check_alternate_paths`, `_dispatches_update`, and `_dispatch_runs_update` stayed byte-identical to the committed rule, so no existing rule changed what it reports.
- Round one reported seven High findings and one Low finding: a function body settled against its definition environment rather than every reachable call environment, a quote removal that performed an expansion the shell reads as text, prefix assignments applied to link operands, two spellings called separate across an expansion boundary, ordinary move options that dropped a tracked alias, a target-directory link recorded under its source, an unmodelled special parameter settled as literal text, and a test that discarded the alias set it claimed to prove.
- Round two reported three High findings and one Medium finding after every round-one finding was remediated: an expansion written after a differing segment that removes the difference, assignments written through commands such as `export` and `read`, reversed long-option prefix tests that missed accepted abbreviations, and a two-operand relocation into a directory.
- Round three reported two High findings and one Medium finding after every round-two finding was remediated: an expansion token that itself contains separators, an assigning command reached through a projected dispatch rather than the written command word, and repeated separators compared as a difference.
- Two parent-direct remediation rounds therefore left High findings open, which exhausts the remediation budget this repository sets. Each round's findings fell in a different part of the model, so the work is stopped for restructuring rather than iterated further. The candidate is preserved on the local branch `plan-230-candidate` and is not committed to `dev`.
