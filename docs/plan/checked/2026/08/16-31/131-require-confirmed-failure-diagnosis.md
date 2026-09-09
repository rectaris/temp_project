# Require confirmed failure diagnosis before repair planning

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
primary_invariant: permit repair planning only after bounded read-only evidence confirms the failed operation and one affected invariant
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/115-classify-review-outcomes-and-sequence-writes.md
  - docs/plan/replanned/2026/08/16-31/116-evaluate-plan-worker-orchestration.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - docs/plan/checked/2026/08/16-31/121-bind-repair-classification-to-unchanged-boundaries.md
  - docs/plan/checked/2026/08/16-31/122-integrate-bounded-repair-lifecycle.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-execution-state.py
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
  - After an authoritative failure, enter a parent-owned no-write condition that permits only bounded read-only reproduction and classification evidence; do not create a numbered repair plan until the exact failed operation and affected invariant are confirmed, then transition only to the existing independent-repair or hard-replan path.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f01ccfa44e09342cbfeb4599282afbed2286a3e43524757881dd3163bb3b93e7","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
replan_source: docs/plan/active/116-evaluate-plan-worker-orchestration.md
replan_contract: docs/plan/replanned/contracts/116-evaluate-plan-worker-orchestration.json
integration_gates:
  - plan 115 must be checked before implementation starts
  - plan 133 must prove that unconfirmed hypotheses cannot create or authorize repair work
successor_plans:
  - docs/plan/active/130-map-acceptance-validation-witnesses.md
  - docs/plan/active/131-require-confirmed-failure-diagnosis.md
  - docs/plan/active/132-checkpoint-plan-session-resources.md
  - docs/plan/active/133-evaluate-resource-bounded-orchestration.md
inherited_acceptance_digests:
  - sha256:f01ccfa44e09342cbfeb4599282afbed2286a3e43524757881dd3163bb3b93e7
checked_summary_ja: 権威検証の失敗後は読取専用の再現証拠で原因を確定し、推測から修復planを作らない。

## Decisions

- Define `diagnosis_required` as a no-write execution condition, not a successful plan status or a repair authorization.
- Permit only bounded parent-owned reproduction and classification evidence while the condition is active.
- Bind evidence to the plan, source HEAD, failed operation identity, observed exit status, affected invariant, and reviewer receipt without storing raw output bodies or credentials.
- Transition only to the existing `repair_required` or `replan_required` paths after evidence is complete; an inconclusive result remains stopped.
- Use bounded parent implementation and independent review because this plan changes the execution ledger and runner gates.

## Tasks

- [x] Define the diagnosis evidence schema and append-only ledger transitions.
- [x] Reject worker, correction, validation, apply, completion, archive, and repair-plan operations while diagnosis is incomplete.
- [x] Add exact confirmed, inconclusive, disputed, replay, mutation, and authority-drift tests.
- [x] Align root and generated policy, ledger, runner, fixtures, and Copier behavior.
- [x] Review the bounded parent diff, run focused validation, obtain independent review, run the authoritative suite once, and archive the accepted plan.

## Validation Notes

- The user approved the confirmed-diagnosis boundary on 2026-08-21.
- The source Plan 116 acceptance text is preserved exactly.
- Focused validation passed: the execution-ledger tests, sandboxed-runner tests, root-policy check, Copier static check, and `git diff --check`.
- Independent review first identified High and Medium defects in the repair-plan gate, parent-direct admission, report sequence, lifecycle binding, and setup-failure persistence. The bounded parent remediation resolved them; the final review reported High 0 and Medium 0.
- The authoritative validation suite ran exactly once on 2026-08-22 and passed all declared commands. `actionlint` was unavailable, so the repository lint and smoke scripts applied their existing documented skip behavior; both scripts still passed.
