# Settle fixture words from a modelled grammar

status: checked
primary_invariant: the bounded fixture checker settles a written word into comparable destination text only when every part of that word is written in the grammar the checker enumerates, reports the word unproven otherwise, proves two settled texts separate only when both are anchored at the root and no modelled expansion can make them name one path, and leaves every existing rule rejecting and accepting exactly the operations it rejects and accepts today
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
  - docs/plan/checked/2026/08/16-31/236-accept-a-bounded-fixture-construct-set.md
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
  - docs/plan/checked/2026/08/16-31/236-accept-a-bounded-fixture-construct-set.md
successor_plans:
  - docs/plan/replanned/2026/08/16-31/234-derive-fixture-name-bindings-from-tokens.md
  - docs/plan/active/235-settle-fixture-words-from-a-modelled-grammar.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/232-settle-fixture-words-from-a-modelled-grammar.md
replan_contract: docs/plan/replanned/contracts/232-settle-fixture-words-from-a-modelled-grammar.json
integration_source_ids:
  - 232
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not change which operations any existing rule reports in this plan; the model is added, not applied
  - Plan 236 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - Plan 233 must start only after this plan is checked and its exact checked archive path replaces the active dependency
checked_summary_ja: 語の解決を列挙した文法だけに限定し、根から辿れる語だけを比較する。

## Decisions

- Enumerate what the model reads and report everything else unproven. Thirteen independent review rounds across the stopped plans each found another written spelling that a modelled-then-corrected reader settled, so the reader must accept only the forms it enumerates and must never fall through to a literal reading of a form it does not enumerate.
- Read a word as one unit. A word is settled only when its quoting, its literal characters, and each expansion it writes are all enumerated forms, because a reader that settles the parts it knows and copies the rest reports text the shell never produces.
- Read a command substitution only where one binding runs it once. A substitution written in a command word runs again each time that command runs, so the checker names the value of a bound substitution and never names one written in a command word.
- Settle each name at the offset its own binding is written, not at the offset a later word reads it, and report unproven for every name the binding surfaces report unsettled.
- Compare only paths anchored at the root. A fixture may change its working directory between two readers, so a path the checker cannot anchor names a directory no written text decides, and a parent segment is never modelled because the segment above it may be a link.
- Anchor a substitution only through a command list read from lexical tokens, or report the path unanchored. A pattern matched over the text inside a substitution accepted a further command whose output joins the path, so the anchor must be read as a parsed list and withdrawn wherever the fixture may shadow one of its command names.
- Prove separation only over settled texts, and state the link precondition the caller must meet. Two settled paths are separate only when both are anchored, they start from one anchor, and no expansion is written at or after the segment where they first differ, and a caller that needs directory separation must also prove that no tracked alias lies on either path.
- Reuse the preserved candidate as coverage. The local branch plan-232-candidate holds the reader that three independent review rounds were run against, and the stopped plan records every finding those rounds reported, so each recorded spelling becomes a unit case rather than a later finding.
- Keep every existing rule unchanged. The model is proven by its own unit coverage, so the committed fixture check and the full test suite must report exactly what they report before the plan.

## Tasks

- [x] Enumerate the word grammar the checker settles: the quoting forms, the literal path characters, and the expansion forms it models, and report unproven for any word that writes anything else.
- [x] Settle each modelled name against the bindings Plan 236 derives, resolving each binding where it is written and following call sites outward under a visited set, under a fixed settlement bound.
- [x] Anchor a path only from written text that starts at the root or from a substitution the checker reads as one parsed command list, and report every other path unanchored.
- [x] Prove two anchored paths separate only when they start from one anchor and no expansion is written at or after the first differing segment, and record the alias precondition the caller must meet.
- [x] Cover every spelling the stopped plan recorded, including an unquoted expansion the shell splits, a special parameter, a substitution written in a command word, a value read where it is written, a parent segment, and a substitution list that writes more than one command.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Ported the word grammar the preserved branch `plan-232-candidate` proved, and rebuilt it on the Plan 236 binding surfaces: a word settles only when its quoting, its literal characters, and each expansion it writes are all enumerated forms, and every other spelling is unproven by construction.
- Changed one behaviour from the candidate: a name Plan 236 reports unsettled now leaves the word unproven instead of settling to the union of its branch values. Independent review confirmed the change is correctly over-strict, because a union may omit the value the branch does not write.
- Added coverage for the spellings the stopped plan recorded and for the two the port left uncovered: a special parameter, and a substitution list writing more than one command. The committed fixture anchors only its modelled `pwd` list and leaves its nested substitution unproven.
- Independent review round 1 reported no High, no Medium, and no Low finding, and confirmed the grammar is a total whitelist, that a mis-parsed substitution degrades to unproven, that path normalization keeps the directory a shell names, and that an anchor read from a substitution can never manufacture a separation.
- Authoritative validation ran once: 222 checker tests passed, `--check tests/copier-update.sh` passed, `scripts/lint-project-workflow.sh` passed, `tests/smoke.sh` passed, and `git diff --check` reported nothing.
