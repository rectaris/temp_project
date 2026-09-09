# Accept a bounded fixture construct set

status: checked
primary_invariant: the bounded fixture checker enumerates the shell constructs it accepts, reports every name in the fixture unsettled as soon as the fixture writes any construct outside that set, decides from the lexical tokens alone which names each accepted construct may bind, and leaves every existing rule rejecting and accepting exactly the operations it rejects and accepts today
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
  - docs/plan/replanned/2026/08/16-31/232-settle-fixture-words-from-a-modelled-grammar.md
  - docs/plan/replanned/2026/08/16-31/234-derive-fixture-name-bindings-from-tokens.md
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
  - docs/plan/active/236-accept-a-bounded-fixture-construct-set.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/234-derive-fixture-name-bindings-from-tokens.md
replan_contract: docs/plan/replanned/contracts/234-derive-fixture-name-bindings-from-tokens.json
integration_source_ids:
  - 234
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not change which operations any existing rule reports in this plan; the model is added, not applied
  - Plan 235 must start only after this plan is checked and its exact checked archive path replaces the active dependency
checked_summary_ja: 受理する構文そのものを列挙し、列挙外を書いた時点で全名称を未解決にする。

## Decisions

- Enumerate the accepted constructs, not the binding ones. Sixteen findings across four stopped attempts were each one construct the reader did not enumerate, and every one of them was found by asking what the reader failed to look at rather than what it looked at wrongly. A union of binder detectors cannot answer that question, because a construct no detector reads is silently absent from every set it would have joined.
- Report every name unsettled as soon as one unaccepted construct is written, rather than reporting only the names that construct appears to touch. The reason a construct is unaccepted is that the checker does not know what it does, so it cannot know which names it leaves alone either.
- Keep the accepted set small enough to state and prove. The committed fixture is the only text the checker must settle, so the accepted set has to cover what that fixture writes and nothing more, and every widening of it is a reviewed change rather than a correction.
- Read the accepted set from the lexical tokens the fixture is already parsed into, never from its raw text. A quoted span, a command substitution, a here-document body, and a continued line each hid a separator from a pattern matched over raw text in an earlier round, and the tokens carry those boundaries exactly.
- Keep every binding surface the stopped plan proved. The preserved reader already reports a name unsettled for a prefix assignment, an assigning command, an unresolvable or shadowed command word, a launcher, a loop head, an assignment a shell detaches into a subshell, a pipeline, or the background, an assigning parameter expansion, an arithmetic expansion, a here-document expansion, and a name the two readings disagree about, so those surfaces are carried forward rather than rebuilt.
- Reuse the preserved candidate as coverage. The local branch plan-234-candidate holds the reader three independent review rounds were run against, and the stopped plan records all sixteen findings, so each recorded construct becomes a unit case rather than a later finding.
- Keep every existing rule unchanged. The model is proven by its own unit coverage, so the committed fixture check and the full test suite must report exactly what they report before the plan.

## Tasks

- [x] Enumerate the token kinds, the operators, the reserved words, the redirection forms, the quoting forms, and the expansion forms the checker accepts, and report every name unsettled as soon as the fixture writes anything outside that enumeration.
- [x] Prove the enumeration is total over the committed fixture by reporting, for that fixture, that no unaccepted construct is written and that the names the later plans read stay settled.
- [x] Carry forward every binding surface the stopped plan proved, keeping each one derived from the lexical tokens and keeping the reported set a union no branch subtracts from.
- [x] Cover the constructs the stopped rounds recorded, including a descriptor-variable redirection, an attached named option, an expansion written inside a here-document body, a redirection written between a closing brace and the operator that detaches its group, and a continued assignment name.
- [x] Prove the rejecting default by writing a fixture that uses an accepted construct in an unaccepted spelling and asserting that every name it writes is reported unsettled.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 234 archive records the three review rounds, the twelve defects closed before review, and the descriptor-variable redirection that remained open.
- Implemented the acceptance enumeration (`ACCEPTED_TOKEN_KINDS`, `ACCEPTED_OPERATORS`, `ACCEPTED_SEGMENT_KINDS`, and the unquoted-brace rule) with a rejecting default: any unaccepted construct reports every written name unsettled.
- Self-review before independent review found and fixed twelve High defects carried in from the stopped plan's candidate.
- Independent review round 1 reported one High: an operand this checker could not read was silently dropped, so `export $x`, `read $ptr`, and `printf -v "$ptr"` bound a name in real dash and bash while the checker settled it.
- Remediation round 1 replaced the drop with an escalation and narrowed it with forking launchers, command words carrying a literal slash, and declared function names. The committed fixture reports no unaccepted construct and fifty-seven unsettled names, and the names the later plans read stay settled.
- Independent review round 2 reported no High and no Medium finding, and confirmed the reported set stays a union no branch subtracts from. Two Low observations recorded `DIRSTACK` and the coprocess names as unmodeled bash side effects; both were closed by naming them as always unsettled.
- Authoritative validation ran once: 188 checker tests passed, `--check tests/copier-update.sh` passed, `scripts/lint-project-workflow.sh` passed, and `tests/smoke.sh` passed.
