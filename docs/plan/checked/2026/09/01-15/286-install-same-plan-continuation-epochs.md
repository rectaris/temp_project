# Install bounded same-plan continuation epochs

status: checked
primary_invariant: Review-budget exhaustion may authorize one fresh execution epoch for the same unchanged numbered plan, but never reopen a stopped ledger, reset cumulative authority, bypass exact-target preflight, or create an unbounded continuation loop.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"plan-execution-state.py already validates exact external ledgers, immutable hash chains, bounded review receipts, reviewer registries and stopped-state gates."}
  - {"kind":"existing_mechanism","evidence":"The stopped Plan 283 ledger and preserved candidate demonstrate that review-budget exhaustion can occur with an unchanged acceptance and security boundary."}
  - {"kind":"bounded_prototype","evidence":"The existing exact event variants and append-only reviewer registry demonstrate the required hash-chain and one-time-consumption primitives without changing legacy top-level state shape."}
completion_conditions:
  - A stopped review-budget ledger remains byte-identical while one fresh same-plan continuation ledger binds its exact digest, run identity, event-chain leaf, unchanged plan baseline and bounded owner authorization.
  - One numbered plan receives at most one continuation epoch, two formal reviews per epoch and four formal reviews cumulatively; no authorization, restart, candidate change or session change can replenish those limits.
  - A passing adversarial-preflight record bound to the exact current review target and applicable specifications is required before the first review and after any target change, without counting as review or validation evidence.
  - Legacy execution ledgers, review receipts, checkpoints and ordinary accepted-successor behavior retain their historical interpretation, while replay, fork, cross-plan and ineligible-stop continuation attempts fail closed.
  - Root and generated policy, commands, tests and install inventory remain aligned, and the conflicting backlog guidance is revised without deleting its still-valid Tier 1 and isolated diagnostic requirements.
completion_witness_map:
  - {"condition_sha256":"sha256:eff5c21f1f7f2b4a542d51953baa8c9e38040329b339349e6d8c5f1ae0c83791","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:35f7d09d703e169bf78ac0570a35acaa22e6c37627880251aa72329fe0748225","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:820e3788f2cb7b0ee12f5843b6333c7e7538e23a70ff0c0ef1a1ba5b26df2230","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:c5c9a1ff53a05bfa93f1f1bf8901ce71fe90ef1e4c604813f43bf0400aa22089","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:8eba1662f1de152499280193de31ed92b896b08878637bcf43739eaedda80d02","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
  - docs/plan/backlog/273-stop-indivisible-tier-one-work-without-descope.md
  - docs/plan/backlog/276-run-bounded-parent-owned-candidate-preflight.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Implement one owner-authorized same-plan continuation epoch from a review-budget-exhausted stopped ledger without reopening or modifying that ledger, changing the committed plan baseline, or creating another numbered implementation successor.
  - Keep two formal reviews per epoch and four cumulatively for the numbered plan, with atomic replay-resistant continuation authorization and no renewable continuation loop.
  - Require exact-target deterministic adversarial preflight before formal review and after target changes, while preserving independent review, focused validation and authoritative validation as separate mandatory gates.
  - Preserve historical ledger, checkpoint, receipt and accepted-successor behavior and keep root/generated lifecycle policy and tooling mechanically aligned.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c4a7370b35421bf7be8c900f7b050efeeea91535d1a030819e4b437aa690a279","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:461d8d917b618d2e8df0945652a1c1467e2f045bd44efa1bd4a5eb73bf69cd2d","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:0acafcc0eb23d94412287374b79cdea6a536278afa0aca1edf000ab87fd43198","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:5905ba541d0f0baa41d666217f6964aa162f2287063adbde27a29c2b3af06391","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Implement this prerequisite under the existing parent-owned workflow; the new continuation path cannot authorize its own implementation.
  - Keep the stopped predecessor ledger byte-identical. A continuation registry outside the repository atomically consumes one exact predecessor-ledger digest and permits idempotent recovery only for the same child identity.
  - Permit continuation only from `descope_pending` with `parent_remediation_budget_exhausted`, no open writable attempt and exactly two formal reviews. Hard drift, diagnosis, repair, rejection and accepted completion remain ineligible.
  - Keep execution-state schema 6 readable. Represent continuation and adversarial preflight with new exact event variants rather than adding required top-level keys to historical ledgers.
  - Bind the new epoch to the same plan path and digest, source HEAD, primary invariant, implementation mode and candidate-lifecycle identity class. A changed committed plan or source baseline requires ordinary reconstruction.
  - Set the first release limit to epoch 1, two formal reviews per epoch and four cumulative reviews. Do not add a command that raises or renews this bound.
  - Require an external mode-0600 authorization object that quotes the owner instruction and binds the predecessor state digest, next epoch, child run id and cumulative review limit.
  - Record adversarial preflight only from an exact-shape mode-0600 evidence object whose passing cases, current diff target, candidate lifecycle and applicable specification digests match the later review.
  - A preflight pass is ordering evidence only. It never counts as independent review, focused validation, authoritative validation or an acceptance witness.
  - Revise Plans 273 and 276 only where their future instructions conflict with this accepted policy. Preserve Tier 1 admission constraints and the separately scoped isolated diagnostic executor.
checked_summary_ja: 停止済み台帳を変更せず、同じプランに一度だけ継続実行枠を与え、正式レビュー前の対象固定 preflight を必須にする。

## Decisions

- Create a fresh execution ledger for epoch 1 and leave epoch 0 byte-identical.
- Use one external append-only continuation registry to prevent forks and replay.
- Keep two reviews per epoch and cap the numbered plan at four cumulative reviews.
- Require a passing preflight for the exact review target before round one and after target changes.
- Preserve schema-6 top-level state compatibility by adding exact event variants.

## Tasks

- [x] Add continuation authorization, registry, fresh-ledger creation and replay-safe recovery fixtures.
- [x] Add continuation and preflight event validation, cumulative review accounting and review-order gates.
- [x] Update root/generated lifecycle policy, orchestration guidance, AGENTS rules, inventories and smoke assertions.
- [x] Reconcile the conflicting future instructions in Plans 273 and 276 without deleting their independent requirements.
- [x] Run focused validation, independent review and the authoritative suite, then archive this prerequisite.

## Validation Notes

- Owner bootstrap choice: `one_time_reconstruction`.
- Full decision audit: `.agent-artifacts/decision-audits/283-same-plan-continuation-bootstrap.md`.
- Plan 283 remains stopped externally; this prerequisite does not reopen or mutate its ledger.
- The first implementation of continuation is intentionally non-renewable. Another epoch requires a future policy change, not another ordinary owner quote.
- Focused validation passed: `python3 tests/test-plan-execution-state.py` (79 tests), `python3 scripts/check-root-agent-policy.py`, `python3 scripts/check-copier-template.py`, `python3 scripts/restructure-plan.py --verify`, and `git diff --check`.
- The initial independent review found renewable-registry, predecessor-identity, pre-consumption validation, specification-binding, event-shape, crash-recovery, and hard-link defects. The bounded correction fixed them; the final rereview reported no High or Medium findings.
- Authoritative validation passed once in the parent workflow: `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.
- The implementation keeps schema 6 readable, requires epoch-enabled ledgers to bind their continuation registry at initialization, and intentionally does not grant legacy ledgers the new continuation route retroactively.
