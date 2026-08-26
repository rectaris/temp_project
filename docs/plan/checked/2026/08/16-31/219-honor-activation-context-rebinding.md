# Honor activation context rebinding

status: checked
implementation_tier: 2
primary_invariant: an activation record may replace context_files active plan references only with the same plan id's exact checked archive, and every other context or preservation change stays rejected
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/active/219-honor-activation-context-rebinding.md
  - docs/plan/plan.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/spec-index.yaml
  - docs/plan/active/215-enforce-canonical-lifecycle-verification.md
  - docs/plan/checked/2026/08/16-31/213-reconstruct-stopped-lifecycle-chain.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Accept an activation record that replaces context_files active plan references with the same plan id's exact checked archive, and keep rejecting every other context or preservation change.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b4c991261345c38ce1cedc234dfbd120fd9163b69d5f8a1205850503ff5bbec6","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans: []
checked_summary_ja: activation recordがcontext_filesのactive参照を同一IDのchecked archiveへ置換できるようにし、それ以外のcontext変更は拒否したままにする。

## Decisions

- `docs/agent/SPEC_PLAN_WORKFLOW.md` already authorizes an activation record to replace active predecessor, context, integration-gate, and body path tokens with the same plan id's exact checked archive. This plan repairs the implementation to match that normative rule; it does not widen the rule.
- `validate_activation_promotion` compared `context_files` byte-for-byte whenever no preservation promotion occurred, so an authorized context rebinding was rejected.
- `validate_activation_reference_transition` already contains a `context_files` active-to-checked branch and already rejects any activation that leaves an active plan path in `predecessor_plans`, `context_files`, `integration_gates`, or the body. Under the previous promotion check that branch was unreachable, and every deferred plan that lists its predecessor in `context_files` was permanently unactivatable.
- Resolve the recorded `context_files` values through the same `activation_checked_pairs` index before comparing, and fail closed when a referenced active plan has no same-id checked archive.
- Keep the comparison exact. An entry that carries no active reference must still match byte-for-byte, so unrelated context edits, additions, removals, and reordering stay rejected.
- `validate_activation_reference_transition` runs before `validate_activation_promotion` at both call sites, so the no-promotion comparison is redundant defense in depth for a spec-shaped transaction. Two independent reviews found no admissible specification that reaches it across the enumerated bypass classes: field-confined replacement ranges, injected duplicate headers, a removed `context_files` field, and the disabled promotion escape. That is an absence of counterexamples, not a proof. Retain the guard and pin it with a direct guard test rather than an end-to-end transaction.
- Apply the same resolution in the promotion branch so a promotion may accompany an authorized rebinding without loosening the single-append rule.
- Leave `preservation_scope` byte-equal outside the existing promotion path; it holds product paths, not plan references.
- Change no specification text. The specification is already correct.
- Use bounded parent implementation with fresh independent review because this plan changes fail-closed validation authority.

## Tasks

- [x] Resolve authorized active-to-checked context references before the activation promotion comparison and fail closed on a missing same-id archive.
- [x] Keep unrelated context and preservation changes rejected in both the promotion and no-promotion branches.
- [x] Mirror the root command into the generated template byte-for-byte.
- [x] Add a passing activation test that rebinds a context reference and a rejecting test for an unrelated context change.
- [x] Pin the no-promotion guard directly so a mutation that drops the context comparison fails the suite.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- The repaired comparison resolves recorded `context_files` values through `activation_checked_pairs` and then compares exactly, so an authorized same-id rebinding is accepted and every other context or preservation change is still rejected.
- `test_activation_rebinds_context_references_to_the_checked_archive` fails against the unrepaired command with `activation changes preservation or context without promotion`, so it pins the repair.
- `test_activation_promotion_rejects_context_drift` pins the guard in both directions. Deleting the context comparison fails its `stale active reference`, `added context entry`, and `removed context entry` cases; reverting the resolution step fails its acceptance case.
- `test_activation_rejects_unrelated_context_changes` confirms that a context replacement carrying no active reference is still rejected before the promotion validator runs.
- The root command and its generated template counterpart are byte-identical at 241038 bytes.
- Independent review returned zero High and zero Medium findings after one remediation round. The Decisions entry records the absence of counterexamples rather than a proof, at the reviewer's request.
