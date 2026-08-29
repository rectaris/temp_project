# Complete the bounded Copier fixture runtime

status: in_progress
primary_invariant: the committed fixture runtime preserves the unique synthetic transition, bounded before-stage synchronization, update-child ownership release, ordered provenance states, and guardian cleanup under the checked destination-aware checker
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/141-separate-synthetic-copier-version-tags.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - tests/test-copier-migration.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - git diff --check
validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/239-resolve-relative-update-wrapper-subshell-directory.md
successor_plans:
  - docs/plan/replanned/2026/08/16-31/226-scope-fixture-alternate-path-rule.md
  - docs/plan/active/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/228-verify-plan185-runtime-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
replan_contract: docs/plan/replanned/contracts/185-complete-bounded-copier-fixture-runtime.json
integration_gates:
  - Plan 231 is checked at docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md and supplies the destination-aware alternate-path rule this plan validates against
  - Plan 237 is checked at docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md and made the resolution model the single update authority
  - Plan 239 is checked at docs/plan/checked/2026/08/16-31/239-resolve-relative-update-wrapper-subshell-directory.md and resolves the two relative wrapper self-update lanes
  - do not edit scripts/project_workflow/copier_fixture_validator.py in this plan
  - Plan 228 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: Copier fixtureの固有version、bounded同期、子process回収、provenance順序、guardian cleanupを確定する。

## Decisions

- Keep the original Plan 185 runtime requirement unchanged. Only its blocking validation method moved to the Plan 226 lineage, which was restructured and finished as checked Plan 231.
- Validate the runtime only with the checked bounded fixture validator and do not use a broad checker as acceptance authority.
- Preserve the committed v1.4.4 downstream active plan, its replanned source archive, and its replan contract as the pre-schema compatibility input captured by the v1.4.5 migration.
- Use bounded parent implementation because this high-risk process lifecycle cannot use the writable runner.

## Tasks

- [ ] Re-admit only the preserved tests/copier-update.sh candidate against checked Plans 141, 180, and 182.
- [ ] Confirm the synthetic v1.4.5 tag has its own ordered commit and the fixture selects v1.4.4 then v1.4.5 through Copier without invoking the snapshot script directly.
- [ ] Confirm the downstream project commits the v1.4.4 pre-schema active plan, replanned source archive, and replan contract before the update begins and that the consumed record captures that active plan.
- [ ] Confirm the ready emission, two bounded polling loops, three release paths, update-child TERM/grace/KILL/final reap, PID clear, pending then consumed assertions, positive guardian PID, and guardian cleanup.
- [ ] Complete fresh independent review and focused validation through the checked bounded validator with zero unresolved High or Medium findings.

## Validation Notes

- The stopped Plan 183 and Plan 185 ledgers and reviews cannot authorize this successor.
- Task 1 reproduction, read-only and with no file modified: appending the accepted transition sample to the committed fixture returns 40 findings. Binding the sanctioned destination to a written anchored path (`project="$tmp/v145-project"`) reduces that to 24: 22 `alternate_path`, one `release_path`, and one `guardian`. The two cleanup findings are this plan's own work.
- Seventeen of the 22 rejections are `run_copier copy` operations for which `_dispatches_update` is true and `_runs_an_update` is false. The blanket substring detector fires because the command word `run_copier` carries the substring `copier` and the operand path names carry the substring `update`, while the checked resolution model proves the copier subcommand is `copy`. The rule then reads the proved non-update as an unreadable update, because `_update_destinations` returns an empty set in both cases.
- A read-only probe that used the modelled reader as the only alternate-path trigger, with no file modified, reduced the 22 rejections to four. The probe is kept at `.agent-artifacts/review/sim227b.py` with the reproduction at `.agent-artifacts/review/repro227b.py` and the classification at `.agent-artifacts/review/diag227d.py`.
- Of the remaining four, the `prepare_lane` update at line 691 is this plan's own fixture work, because the dispatch sits under `if [ "$lane" = "earliest-supported" ]` and can write that literal destination. The `context-compress.sh` operation at line 897 is covered by Plan 237, which reads the final segment of a settled installed-workflow path. The two relative `run-copier-update.sh` self-update lanes at lines 569 and 574 are covered by neither and are classified separately.
- The fixture-only alternative was measured and rejected. Removing the substring `update` from the fixture's own directory and variable names reduces the 22 rejections to eight, silences a substring detector without changing behavior, and is the bypass shape Plan 186 is chartered to reject.
- Independent review co-signed the `repair_required` classification for the resolution-model defect and confirmed the diagnosis mechanically. It declined to co-sign bundling the two relative wrapper self-update lanes into the same repair, because their destination is genuinely unanchored, the checked Plan 231 decision that no working-directory model exists must stay unchanged, and their only remaining fix changes what `_check_unresolved_dispatch` admits, which is a second independently validatable invariant.
- Execution stopped as `repair_required`. This plan keeps its unchanged write scope, acceptance digest, validation authority, invariant boundary, and safety conditions, and resumes through a fresh run after Plan 237 is checked.
- Execution resumed after Plan 237 and Plan 239 were checked. Reproducing the transition with the same read-only command now returns 3 findings rather than 24: the `release_path` and `guardian` findings at line 21 and the `alternate_path` finding at line 691, all of which are this plan's own runtime work.
