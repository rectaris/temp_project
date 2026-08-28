# Collect fixture aliases from a modelled grammar

status: deferred
completion_deferred_reason: Plan 232 must be checked so a word settles only from the modelled grammar before aliases are collected from it
primary_invariant: the bounded fixture checker collects the alias paths a reachable operation may create only from commands whose name, options, and operands are all written in the grammar the checker enumerates, reports the alias set unplaced for every other spelling, and leaves every existing rule rejecting and accepting exactly the operations it rejects and accepts today
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
  - docs/plan/checked/2026/08/16-31/235-settle-fixture-words-from-a-modelled-grammar.md
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
  - docs/plan/active/235-settle-fixture-words-from-a-modelled-grammar.md
successor_plans:
  - docs/plan/active/232-settle-fixture-words-from-a-modelled-grammar.md
  - docs/plan/active/233-collect-fixture-aliases-from-a-modelled-grammar.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/230-resolve-fixture-destinations-fail-closed.md
replan_contract: docs/plan/replanned/contracts/230-resolve-fixture-destinations-fail-closed.json
integration_source_ids:
  - 230
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not change which operations any existing rule reports in this plan; the model is added, not applied
  - Plan 232 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - Plan 231 must start only after this plan is checked and its exact checked archive path replaces the active dependency
checked_summary_ja: 別名の収集を列挙したコマンド文法だけに限定し、読めない綴りは配置不明として扱う。

## Decisions

- Enumerate what the model reads and report everything else unproven. Ten independent review rounds across the stopped plans each found another written spelling that a modelled-then-corrected reader settled, so the reader must accept only the forms it enumerates and must never fall through to a literal reading of a form it does not enumerate.
- Read a command as one unit. A link or a relocation is read only when its command word, every option written with it, and its operand count are all enumerated, and any other spelling leaves the alias set unplaced rather than silently carrying no alias.
- Read the operation as written in addition to every projected dispatch, because the execution graph drops the arguments of a launched command and scripts/project_workflow/shell_execution.py is outside this write scope.
- Record both readings of a written destination. A second operand may name a directory, so a link or a relocation places its alias at the written path and inside it, and an operand this checker cannot settle leaves the alias unplaced.
- Follow a tracked alias through modelled relocations under a fixed round budget, and treat a relocation whose source cannot be settled as one that may move any tracked alias.
- Reuse the recorded spellings as coverage. The stopped plans record every spelling an independent review found, and the preserved local branch plan-230-candidate holds the reader those rounds were run against, so each recorded spelling becomes a unit case rather than a later finding.
- Keep every existing rule unchanged. The model is proven by its own unit coverage, so the committed fixture check and the full test suite must report exactly what they report before the plan.

## Tasks

- [ ] Enumerate the command grammar the checker reads for aliases: the command names, the option forms including accepted long-option abbreviations, and the operand counts, and leave every other spelling unplaced.
- [ ] Read every reachable operation as written and through each projected dispatch, and locate the effective command behind the enumerated launcher prefixes and launcher options.
- [ ] Collect the alias paths of each modelled link, record both the written and the directory reading of its destination, and mark the alias set unplaced when an operand is unsettled.
- [ ] Follow tracked aliases through modelled relocations under a fixed round budget, distinguishing a move from a copy that keeps a link, and mark the set unplaced for a relocation this checker cannot read.
- [ ] Cover every spelling the stopped plans recorded, including a launched link, an unread command word, a target-directory option, an ordinary move option, an unread copy option, and a relocation into a directory.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 230 archive records the three review rounds and the alias spellings each round found.
