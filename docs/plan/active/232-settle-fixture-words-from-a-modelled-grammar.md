# Settle fixture words from a modelled grammar

status: replan_required
primary_invariant: the bounded fixture checker settles a written word into comparable destination text only when every part of that word is written in the grammar the checker enumerates, reports the word unproven otherwise, and proves two settled texts separate only when no modelled expansion can make them name one path, while every existing rule keeps rejecting and accepting exactly the operations it rejects and accepts today
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
  - docs/plan/active/232-settle-fixture-words-from-a-modelled-grammar.md
  - docs/plan/active/233-collect-fixture-aliases-from-a-modelled-grammar.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/230-resolve-fixture-destinations-fail-closed.md
replan_contract: docs/plan/replanned/contracts/230-resolve-fixture-destinations-fail-closed.json
integration_gates:
  - do not edit tests/copier-update.sh in this plan; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not change which operations any existing rule reports in this plan; the model is added, not applied
  - Plan 233 must start only after this plan is checked and its exact checked archive path replaces the active dependency
replan_reason_codes:
  - multiple_independent_invariants
  - parent_remediation_budget_exhausted
checked_summary_ja: fixture checkerの語の解決を列挙した文法だけに限定し、外れた綴りは未証明として扱う。

## Decisions

- Enumerate what the model reads and report everything else unproven. Ten independent review rounds across the stopped plans each found another written spelling that a modelled-then-corrected reader settled, so the reader must accept only the forms it enumerates and must never fall through to a literal reading of a form it does not enumerate.
- Read a word as one unit. A word is settled only when its quoting, its literal characters, and each expansion it writes are all enumerated forms, because a reader that settles the parts it knows and copies the rest reports text the shell never produces.
- Settle a name against the environment the operation runs in, not the offset it is written at, and report unproven for a name that any assignment written in front of a command, or any command the checker does not model as assigning, may set.
- Prove separation only over settled texts. Two settled texts are separate only when both are anchored, every expansion fills whole path segments, and no expansion is written at or after the segment where they first differ, so no expansion can remove the written difference.
- Bound the settlement. A fixture may assign a name from its own value, so expand each name at most once per text lineage under a fixed text budget instead of seeking a fixed point.
- Reuse the recorded spellings as coverage. The stopped plans record every spelling an independent review found, and the preserved local branch plan-230-candidate holds the reader those rounds were run against, so each recorded spelling becomes a unit case rather than a later finding.
- Keep every existing rule unchanged. The model is proven by its own unit coverage, so the committed fixture check and the full test suite must report exactly what they report before the plan.

## Tasks

- [ ] Enumerate the word grammar the checker settles: the quoting forms, the literal path characters, and the expansion forms it models, and report unproven for any word that writes anything else.
- [ ] Settle each modelled expansion against the environment its operation runs in, following call sites outward under a visited set, and report unproven for every name a prefix assignment or a modelled assigning command may set.
- [ ] Prove two settled texts separate only when both are anchored, every expansion fills whole segments, and no expansion is written at or after the first differing segment.
- [ ] Cover every spelling the stopped plans recorded, including a quoted expansion the shell never performs, a special parameter, an expansion that carries separators, a value taken from a command, and repeated or upward segments.
- [ ] Confirm the committed tests/copier-update.sh check and the full test suite report exactly what they report before this plan, and that every existing rule stays byte-identical.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The Plan 230 archive records the three review rounds and the spellings each round found.
- The modelled word grammar was implemented and carried through three independent review rounds. The suite ran at 156 tests passing, `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh` passed, `scripts/lint-project-workflow.sh` passed, `git diff --check` was clean, and all fifteen existing rule functions stayed byte-identical to the committed rule, so no existing rule changed what it reports.
- Round one reported seven High findings and one Medium and one Low finding: an unquoted expansion settled although the shell splits it into fields, one substitution spelling written twice read as one anchor, a parent segment reduced above a link, a value settled where it is read rather than where it is written, a function body's assignment never reaching its caller, a loop head and other binding commands missing from the mutation surfaces, several assignments written in front of one command bypassing prefix detection, an unbounded settlement walk, and a committed-fixture assertion that read a name the fixture never writes.
- Round two reported seven High findings and one Medium and two Low findings after every round-one finding was remediated: a second assignment written as one command never recorded, a quoted value hiding a prefix run, a quoted name hiding an assigning command, `unset` missing from the mutation surfaces, a continued loop head, shell-kept names such as `PWD` read as stable, a relative anchor compared across a working-directory change, one written substitution re-evaluated in a loop, and two tests that proved less than they claimed.
- Round three reported five High findings after every round-two finding was remediated, and reported no Medium and no Low findings. Every round-three finding fell in one place: the surfaces that decide which names a fixture binds are still read from raw fixture text and from one level of dispatch expansion rather than from the lexical tokens and the settled bindings. The enumerated absolute-substitution list accepted a newline and a redirection, a declared `command` or `cd` forged an anchored substitution, a first conditional assignment discarded the inherited value, a command substitution written in a prefix run defeated the separator test, and a command word settled from another name never reached the assigning-command reading.
- The word grammar itself drew no round-three finding, which separates two invariants this plan bundled: settling a written word from an enumerated grammar, and deriving from lexical tokens every surface that binds or shadows a name. Two parent-direct remediation rounds therefore left High findings open, which exhausts the remediation budget this repository sets, so the work is stopped for restructuring rather than iterated further. The candidate is preserved on the local branch `plan-232-candidate` and is not committed to `dev`.
