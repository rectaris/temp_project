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

- [x] Read the enclosing subshell of a reachable operation and collect the directory changes that precede it inside that same subshell.
- [x] Resolve a relative installed-workflow command word against the settled operand of a single preceding directory change, and keep it unproven when the subshell holds no directory change, more than one, or an operand that does not settle.
- [x] Add regression tests covering the settled subshell form, a subshell with two directory changes, a directory change whose operand carries an unsettled expansion, and a relative command word with no enclosing subshell.
- [x] Confirm the two wrapper self-update lanes of the committed fixture no longer report an alternate path when the fixture is read as a transition, without editing the fixture.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- `_subshell_directory` places a relative installed-workflow command word only when its subshell holds exactly two operations, the word and one directory change written before it on a prefix enclosure path, the change is a two-word `cd` with an empty call path whose operand settles to one anchored path, and the word sits in no loop region.
- `_workflow_destinations` gained the settled directory as a second argument. The branch that reads a path writing nothing above the installed workflow directory now returns that directory, and still returns an unproven empty set when none settles.
- Independent review round 1 reported one High. A directory change carried by a called function runs in the same shell and moved the subshell into the sanctioned child while the model settled a decoy directory. Reproduced verbatim, then repaired by counting every operation of the subshell rather than only the directory changes.
- Independent review round 2 reported a second High through a different mechanism. A loop back edge runs an operation written after the word before the word on the second turn, so an offset-ordered reading settled a decoy directory. Reproduced verbatim, then repaired by reading the whole subshell at any offset and refusing to place a repeated word.
- Independent review round 3 returned no High and no Medium. It exercised roughly thirty constructs, including background and guarded decoys, brace groups, pipelines, nested subshells, transitive function calls, and a planted symlink alias, and found no remaining way a relative word reaches the sanctioned child unrejected.
- The round 3 Low proposed adding the branch-condition enclosure kind to the repeat guard. That exact change would reject the committed fixture lanes, because the execution graph gives a branch condition and a loop condition the same enclosure kind. The guard was instead made self-contained by reading the loop regions the operation model already carries, which rejects a loop condition and a loop body while keeping a branch condition placeable.
- Differential evidence against the committed validator: a corpus parity harness over 409 samples reports 0 loosened and 0 tightened readings, and a targeted probe of subshell shapes loosens exactly the chartered lane.
- The committed tests/copier-update.sh was neither edited nor executed. Its reproduction as a transition fell from 5 findings to 3, and all 3 are Plan 227 runtime work.
- Authoritative validation run once: 327 tests pass, `--check tests/copier-update.sh` passes, `scripts/lint-project-workflow.sh` exits 0, `tests/smoke.sh` passes, `git diff --check` is clean.
