# Complete the bounded Copier fixture runtime

status: backlog
primary_invariant: the committed fixture runtime preserves the unique synthetic transition, bounded before-stage synchronization, update-child ownership release, ordered provenance states, and guardian cleanup without relying on unaccepted checker changes
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
  - scripts/check-copier-template.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/141-separate-synthetic-copier-version-tags.md
  - docs/plan/active/205-integrate-bounded-copier-fixture-validator.md
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
  - docs/plan/active/205-integrate-bounded-copier-fixture-validator.md
replan_source: docs/plan/active/183-build-bounded-copier-transition-fixture.md
replan_contract: docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
integration_gates:
  - Plan 205 must be checked and its exact checked archive path must replace this active predecessor before implementation
  - in the same parent-owned activation update, add scripts/project_workflow/copier_fixture_validator.py emitted by checked Plan 205 as exact read-only context
  - preserve the dirty scripts/check-copier-template.py candidate through preservation_scope without editing, staging, or committing it in this slice
  - Plan 186 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
successor_plans:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: Copier fixtureの固有version、bounded同期、子process回収、provenance順序、guardian cleanupを確定する。

## Decisions

- bounded Copier fixture runtime slice means the proposed successor that owns only tests/copier-update.sh, creates one unique ordered v1.4.5 commit, emits the ready event after the before migration returns, bounds the wrapper release poll and parent ready poll, asserts pending before release, releases the before stage in normal, ready-failure, and cleanup paths, terminates and reaps the update child through a 30-second wait plus TERM, five-second grace, KILL, and final wait, clears its PID after reap, asserts consumed after the update and guardian capability exchange, validates a positive guardian PID, and stops the detached guardian.
- Validate the runtime only with the checked bounded_copier_fixture_validator from Plan 205 and do not use the dirty broad checker as acceptance authority.
- Preserve the committed v1.4.4 downstream active plan, its replanned source archive, and its replan contract as the pre-schema compatibility input captured by the v1.4.5 migration.
- This slice is not sufficient to satisfy Plan 183 alone; Plan 187 retains the combined acceptance gate.
- Use bounded parent implementation because this high-risk process lifecycle cannot use the writable runner.
- Treat the two stopped Plan 183 reviews as advisory inputs and start a fresh ledger and independent review budget.

## Tasks

- [ ] Re-admit only the preserved tests/copier-update.sh candidate against checked Plans 141, 180, and 182.
- [ ] Confirm the synthetic v1.4.5 tag has its own ordered commit and the fixture selects v1.4.4 then v1.4.5 through Copier without invoking the snapshot script directly.
- [ ] Confirm the downstream project commits the v1.4.4 pre-schema active plan, replanned source archive, and replan contract before the update begins and that the consumed record captures that active plan.
- [ ] Confirm the ready emission, two bounded polling loops, three release paths, update-child TERM/grace/KILL/final reap, PID clear, pending then consumed assertions, positive guardian PID, and guardian cleanup.
- [ ] Complete fresh independent review and focused validation through the checked bounded validator with zero unresolved High or Medium findings.
- [ ] Archive and commit only tests/copier-update.sh plus parent-owned lifecycle files while preserving the checker candidate.

## Validation Notes

- The stopped Plan 183 ledger and reviews cannot authorize this successor.
- The current checker candidate is unaccepted read-only input and remains owned by Plan 186.
- Do not execute tests/copier-update.sh in this slice.
