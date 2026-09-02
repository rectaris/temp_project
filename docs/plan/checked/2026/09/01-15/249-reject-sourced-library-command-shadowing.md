# Reject command shadowing in sourced fixture libraries

status: checked
primary_invariant: the focused checker reads every file the transition fixture sources and rejects a redefinition of an observed command or of the Copier wrapper wherever it is written, so no bound observation can be made vacuous from outside the fixture file
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - scripts/check-copier-template.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
  - tests/copier-update.sh
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh or tests/lib-copier.sh in this plan; both are read-only subjects under test
  - keep the committed fixture and the committed library passing the checker unchanged
  - Plan 248 must be checked before this plan starts, so the validator carries one settled inventory rule
  - Plan 247 must not resume until this plan is checked
checked_summary_ja: fixtureがsourceするlibraryまで読み、observed commandとCopier wrapperの再定義をどこに書かれても拒否する。

## Decisions

- Read what the fixture executes, not only the file it is named after. `tests/copier-update.sh` sources `tests/lib-copier.sh` into the current shell before every bound observation, and the gate never reads that file, so a one-line declaration there rebinds a name for every observation while the gate stays green.
- Treat the Copier wrapper as an observed name. A no-op `run_copier` leaves every bound needle intact while no Copier run happens at all, which is the same defect class checked Plan 244 named.
- Bind the sourced set in the gate rather than by following arbitrary runtime paths, so the checker keeps its text-only boundary and its refusal stays decidable.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [x] Reproduce both admissions read-only: a `grep` declaration added to `tests/lib-copier.sh`, and a `run_copier() { return 0; }` declaration added to the fixture after the source line.
- [x] Feed every file the fixture sources through the shadowing rule and reject a redefinition of the Copier wrapper, keeping the committed fixture and library accepted unchanged.
- [x] Add mutation coverage for a shadowed observed command in the sourced library, for a shadowed Copier wrapper, and for an unbound sourced path.
- [x] Complete one fresh independent read-only review and focused validation, closing every High finding and every Medium finding this plan's reading covers. One Medium on reachability of the wrapper body was deferred by owner decision to `docs/plan/backlog/257-require-a-reached-copier-dispatch.md`.
- [x] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Both reproductions were confirmed read-only against the committed gate, with `tests/copier-update.sh` and `tests/lib-copier.sh` left byte-identical: a `grep() { :; }` declaration added to the library, and a `run_copier() { return 0; }` declaration added to the fixture, were both accepted by the gate as committed.
- The checker now reads every file the fixture sources. Sources are taken from the checked execution graph rather than from raw command runs, because the run splitter treats a `case` arm such as `.|..|./*)` as a command word and would read `.` there as a source.
- Only a bound library is read. The sourced path must be written as `$root/<bound path>`, `root` must carry exactly one written value, and that value must be one of the bound anchor spellings. Changing the anchor line in the fixture therefore means binding the new spelling in the checker; anything else is rejected as unread.
- A Copier wrapper is an observed name. A declaration whose name mentions Copier is rejected in the fixture, and in a bound library it must dispatch Copier when the fixture runs it as a Copier operation, or at least name Copier otherwise. A body reduced to `command -v copier`, or one that delegates to a declaration that only asks, is rejected.
- Focused validation, all passing: `python3 tests/test-copier-fixture-validator.py` (526 tests), `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh`, `python3 scripts/check-copier-template.py`, `git diff --check`. Repository validation, all passing: `./scripts/lint-project-workflow.sh` and `./tests/smoke.sh`.
- `tests/test-human-report.py` failed once inside one `lint-project-workflow.sh` run and then passed in eight consecutive runs, five of them standalone. It exercises `template/.project-agent-workflow/scripts/human-report.py`, which this plan does not touch, so the failure is recorded as a transient rather than resolved here.
- Three independent read-only reviews were run by a bounded helper with no write scope; every finding was accepted or rejected in the main session. Round 1 reported one High, that any single expansion was read as the library anchor, and one Medium, that a Copier wrapper written in the library was unchecked. Round 2 reported one High, that an anchor value which merely mentions a positional parameter can still expand to a directory the fixture fills, and one Medium, that `command -v copier` was counted as running Copier. All four are closed and were re-verified rejected. The main session additionally closed delegation laundering, where a wrapper called the availability predicate to inherit its Copier name.
- Round 3 reported one remaining Medium: a wrapper whose only Copier dispatch sits behind a guard that never holds, such as `if [ -n "${COPIER_ENABLED:-}" ]; then copier "$@"; fi`, still satisfies the dispatch requirement. Closing it needs a path-sensitive reading that no terminating path through the body avoids a Copier operation, which is a different analysis from the redefinition reading this plan delivers. The owner chose a bounded deferral, so the requirement is carried unchanged into `docs/plan/backlog/257-require-a-reached-copier-dispatch.md` rather than dropped.
- Plan 247 is shelved at `docs/plan/shelved/247-verify-plan187-successor-acceptance.md`, so the gate `Plan 247 must not resume until this plan is checked` is waived. The skipped assurance is the confirmation that the Plan 187 successor acceptance mapping still holds against this checker change; if Plan 247 returns to backlog or active, that confirmation becomes binding again.
- Plan 248 is checked at `docs/plan/checked/2026/08/16-31/248-bind-fixture-editing-to-the-inventory.md`, so the validator carries one settled inventory rule as its gate requires.
