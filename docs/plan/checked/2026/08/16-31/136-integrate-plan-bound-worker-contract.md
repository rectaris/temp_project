# Integrate and evaluate the plan-bound worker contract

status: checked
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: accept the combined worker-contract path only when unchanged preimplementation scenarios and all source acceptance items pass without protected-input or authority regression
write_scope:
  - CHANGELOG.md
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/worker-contract-evidence.json
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/134-freeze-worker-contract-scenarios.md
  - docs/plan/checked/2026/08/16-31/135-enforce-plan-bound-worker-contract.md
  - docs/plan/replanned/2026/08/16-31/113-generate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - references/orchestration.md
  - references/validation.md
  - tests/fixtures/orchestration/worker-contract-scenarios.json
  - tests/fixtures/orchestration/worker-contract-holdout.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Generate one versioned worker execution contract deterministically from the exact committed active-plan bytes admitted for one initial or correction attempt; bind it to the repository identity, source HEAD, plan path, plan digest, orchestration run identifier, and attempt lineage.
  - Include only the plan's primary invariant, normalized write scope, context files, required specifications, acceptance items, focused-validation commands, explicit exclusions, and hard stop conditions needed by that attempt.
  - Require every writable delegated plan to declare exactly one nonblank `primary_invariant`, reject a missing or ambiguous invariant before worker start, and preserve compatibility for plans that are parsed or archived without writable delegation.
  - Keep the active plan and directly read normative specifications as the implementation source of truth; require the worker to read them, and treat the generated record as a supplemental bounded projection that cannot override, omit as satisfied, or amend source requirements.
  - Validate the record schema, size, normalized repository-relative paths, digests, identity, lineage, and exact equality to a fresh derivation immediately before worker invocation; fail closed on any mismatch, unknown field, duplicate item, symlink escape, or plan change.
  - Mount or copy the record into the isolated worker boundary as read-only input and prevent the worker from changing the active plan, generated record, runner, validation authority, source worktree, or parent-owned execution state.
  - Do not include prompts, worker output, environment values, credentials, host-specific absolute paths, raw logs, or undeclared repository files in the record.
  - Build the worker prompt from fixed repository policy plus the verified structured record instead of a separately maintained restatement of plan details; do not create a second manual source that can drift from the plan.
  - Preserve existing isolated-clone, no-hardlink, clean-source, object-database, model-routing, correction-budget, candidate-admission, validation-order, and external-effect boundaries.
  - Add deterministic median, edge, negative, and untuned holdout cases for exact derivation, source-plan mutation, digest and lineage mismatch, missing primary invariant, duplicate and unknown fields, path traversal and symlink escape, oversized input, attempted contract mutation, and attempted authority widening.
  - Keep root and generated runner behavior byte-identical, keep root and generated orchestration policy and Skill semantics aligned after path normalization, and preserve project-owned files through supported Copier copy and update paths.
  - Record the behavior under Unreleased, run focused validation only after parent diff and critical-invariant review, run the authoritative suite exactly once for an otherwise acceptable candidate, and finish with zero unresolved High or Medium independent-review findings.
replan_source: docs/plan/active/113-generate-plan-bound-worker-contract.md
replan_contract: docs/plan/replanned/contracts/113-generate-plan-bound-worker-contract.json
integration_gates:
  - plans 134 and 135 must be checked and their exact archive paths must replace active context paths before evaluation
  - tuned scenarios must equal sha256:ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf and holdout must equal sha256:a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27 before any evaluation command starts
  - Plan 114 may start only after this integration plan is checked as the accepted Plan 113 successor
successor_plans:
  - docs/plan/checked/2026/08/16-31/134-freeze-worker-contract-scenarios.md
  - docs/plan/checked/2026/08/16-31/135-enforce-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
inherited_acceptance_digests:
  - sha256:018029e6bdbccfad54ba0fbff30086b4b44b66a7aaf6f5594bd83888f5001774
  - sha256:4c502f3bd90348bdc59aac577a337138d2aa6cf0271e3ec48031d2065005cf25
  - sha256:4a6fac9ef3c6aab2d6bae45781039ac3ebda91510a3bcd90d5bfd5154bef50d9
  - sha256:8906a81c8ab0aef8c31d4302d17f9123c291d2c70a9514dbae13046985bce018
  - sha256:7f7246745d04b98585178c14b1e9ba9a8f34ef100d1dbdb517ef008472467313
  - sha256:eafceb41a6a90a1ec5824d8e199e4dcccbf080384ef9d322459f66e8f5ec14f8
  - sha256:3f7161430933f10ffcd7c9cc644455f883cbeb0a0dc4048bbba8538f0e05a6bc
  - sha256:fbd0c6713ded62fe841a3bf84241e307f5a5c294838c784c2c1ba8b04a95646e
  - sha256:9b5f72cb26b3b91826edda511243eecc9f0e5c62034524576d94dda1e28f16ec
  - sha256:ba6dde8e1485e27de30d5dafbf57d39b619e63557aea73ef8fe29d65700515a7
  - sha256:bfa8cb8b800056e0282e4d34f739d40f36cd5957f884d7638c9bc8fe03435473
  - sha256:12d75a4567202438fa26035648ffeb23ead6ce2b0cd83483d63833776f706a3f
checked_summary_ja: 事前に固定したcaseと全受入条件でworker契約を統合検証し、保護対象と検証権限を守る場合だけ後続planへ進める。

## Decisions

- Treat plans 134 and 135 as immutable predecessors; stop for replan rather than changing either design in this integration scope.
- Execute the frozen holdout only after tuned checks, parent diff review, and critical-invariant review pass.
- Keep the default worker test command tuned-only and use `python3 scripts/check-root-agent-policy.py --include-holdout` as the sole holdout behavior selector.
- Record digest-linked observed outcomes without copying raw command output into the repository evidence file.
- Interpret this checked integration as the accepted successor for Plan 114's Plan 113 dependency.
- Use bounded parent implementation and independent review because integration evidence and checks are validation authority.

## Tasks

- [x] Refresh predecessor context paths to their exact checked archives and verify frozen fixture digests.
- [x] Execute the generic evaluator across every unchanged scenario class and record bounded digest-linked outcomes.
- [x] Verify all twelve source acceptance items, root/template parity, non-destructive Copier behavior, and unchanged safety gates.
- [x] Record the accepted behavior under Unreleased without overstating evidence.
- [x] Review the complete diff, obtain independent review, run the authoritative suite exactly once, and archive this plan before Plan 114 starts.

## Validation Notes

- This integration plan preserves every normalized Plan 113 acceptance item exactly.
- Any fixture drift or predecessor design change requires replan rather than in-scope repair.
- The frozen tuned and holdout fixture digests were copied from Plan 134 before implementation.
- Plans 134 and 135 are checked at `docs/plan/checked/2026/08/16-31/134-freeze-worker-contract-scenarios.md` and `docs/plan/checked/2026/08/16-31/135-enforce-plan-bound-worker-contract.md`.
- The tuned fixture remained `sha256:ff31f769bc13867be4eb3c66a86decff44c31d58aa6d523515c3ec0b19f55ebf`; the sealed holdout remained `sha256:a3f6fba464ecb20f6505a0537e37457d4f41783bb6ca2616158c1de69cedaa27` until its sole explicit execution after tuned checks and parent review.
- `tests/fixtures/orchestration/worker-contract-evidence.json` records all 15 tuned cases, the one holdout case, and all 12 inherited acceptance digests as passed; its digest is `sha256:4f0cdcf2c109b5515c2c526b9027034f5bbf7ea9f2f7e00296f6cad72b9dea42`.
- Focused validation passed with 82 worker-runner tests, the Copier-template policy check, and `git diff --check`.
- Independent read-only review reported zero High, Medium, or Low findings.
- The authoritative suite ran exactly once for the accepted candidate and passed every declared command, including the explicit holdout selector, lint, smoke, and real Copier update checks.
- No unresolved risk or deferred work remains in this plan.
