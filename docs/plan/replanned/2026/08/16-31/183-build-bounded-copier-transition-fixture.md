# Build the bounded v1.4.4-to-v1.4.5 Copier transition fixture

status: replanned
replan_reason_codes:
  - parent_remediation_budget_exhausted
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/replanned/2026/08/16-31/178-wire-validation-witness-copier-transition.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - tests/test-copier-migration.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/183-build-bounded-copier-transition-fixture.md
replan_contract: docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 実際のv1.4.4からv1.4.5へのfixtureでpendingとconsumedをboundedに確認しprocessを残さない。

## Decisions

- bounded Copier transition fixture slice means the successor that constructs the committed v1.4.4 downstream project, drives the v1.4.5 update, and bounds the fixture synchronization sequence, update-process lifecycle, and guardian lifecycle.
- fixture before-stage synchronization sequence means the test-only ready event emitted after the before migration returns and the parent release event that permits Copier to continue; it is distinct from the guardian capability challenge-response.
- update-process ownership condition means the parent still holds the live child PID and must wait or terminate and reap that child; the condition ends only when the PID field is cleared after reap.
- Use bounded parent implementation because the stopped Plan 178 run exhausted its parent-direct remediation budget and this inseparable two-file high-risk scope cannot use the writable runner; initialize a fresh execution ledger and retain the unchanged independent-review and acceptance gates.
- Use one 30-second update-process wait bound in normal, ready-failure, and cleanup paths, followed by TERM, a 5-second grace period, KILL when still live, and final reap.
- Clear the owned update PID immediately after reap so later fixture cleanup cannot act on a reused PID.
- Require the checker to bind the ready failure, release, normal waiter call, cleanup waiter call, consumed assertion, and guardian stop as one connected fixture contract.
- Never invoke the snapshot script directly; Copier must select both migration stages from the checked Plan 182 source.

## Tasks

- [ ] Rework the preserved fixture candidate so every update wait path uses the same bound and releases PID ownership after reap.
- [ ] Preserve the committed v1.4.4 pre-schema plan and contract, synthetic v1.4.5 target, the assertion that provenance is `pending` before the fixture release event, the fixture ready/release synchronization sequence, the guardian capability challenge-response, consumed record assertions, and cleanup of the detached guardian.
- [ ] Extend the checker with connected exact fixture-construction checks that fail when any fixture synchronization, wait, release, or cleanup edge is removed or bypassed.
- [ ] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the checker, fixture, and parent-owned lifecycle files.

## Validation Notes

- All Plan 178 review findings remain advisory inputs; this plan starts with a fresh ledger and independent review budget.
- Do not run tests/copier-update.sh in this slice; Plan 179 retains the sole genuine authoritative update execution.
