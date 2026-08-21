# Gate sequential writable plan execution on parent review outcomes

status: in_progress
task_types:
  - planning_docs
  - referent_first
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: permit the next dependent writable start only after an append-only parent ledger transition closes the current attempt and accepts its candidate
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/136-integrate-plan-bound-worker-contract.md
  - docs/plan/active/114-validate-structured-worker-completion.md
  - docs/plan/checked/2026/08/01-15/074-isolated-candidate-correction.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - docs/plan/checked/2026/08/01-15/077-atomic-plan-restructuring.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - references/orchestration.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
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
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - git diff --check
acceptance:
  - Require plan 136, the accepted successor for plan 113, and plan 114 to be checked and archived before implementation starts; bind scheduling and review records to their verified worker execution contract and worker completion receipt digests.
  - After plans 136 and 114 are archived, replace their active `context_files` entries with the exact checked archive paths before implementation; treat these as dependency-path refreshes only, rerun plan checks, and do not change accepted requirements or broaden scope.
  - Route this high-risk lifecycle change to bounded parent implementation with the declared write scope, clean-worktree checks, no external or destructive authority expansion, an independent change review, and unchanged candidate and authoritative-validation acceptance gates; do not start a writable sequential-plan worker for this plan.
  - Assign one accepted active plan with one primary invariant to one fresh isolated writable worker attempt, admit or reject that candidate before starting the next dependent writable plan, and prevent two writable attempts in the same dependency chain from overlapping.
  - Permit concurrent helper work only when it is independent, read-only, bounded, and admitted by the existing delegation value gate; do not introduce a global task lock, shared writable branch, shared mutable worker checkout, or permission for helpers to integrate one another's work.
  - Extend the locked parent-owned execution ledger outside the repository with predecessor plan and accepted-candidate digests sufficient to prove the next dependent writable start is eligible and based on admitted state.
  - Define the review outcome reason as a parent-authored bounded value attached to a rejected candidate or correction decision while preserving the concrete finding and parent acceptance authority.
  - Use exactly these initial reason codes: `acceptance_unmet`, `out_of_scope_change`, `required_spec_missed`, `integration_contract_mismatch`, `focused_validation_failed`, `evidence_incomplete`, and `multiple_invariants_coupled`; reject unknown or worker-authored reason codes.
  - Store only bounded reason codes, review-evidence digests, affected-invariant digests, attempt and candidate identifiers, predecessor digests, counters, and existing sanitized timing fields in the ledger; do not store findings, prompts, output bodies, environment values, credentials, patches, or repository content.
  - Keep the concrete parent finding outside the bounded ledger code, and never allow a reason code to waive acceptance, clear a hard trigger, rewrite history, reset correction count, or authorize a new worker start.
  - Preserve one initial generation and at most two isolated correction rounds; when the same reason recurs, the correction budget is exhausted, multiple independent invariants are coupled, or any existing hard replan condition occurs, require the existing strategy-change or `replan_required` path rather than regenerating the complete plan.
  - Make predecessor acceptance and reason events locked, append-only, replay-resistant, run-bound, digest-cross-linked, and fail-closed across crashes and concurrent start attempts.
  - Add deterministic median, edge, negative, and untuned holdout cases for an accepted two-plan chain, rejected predecessor, overlapping starts, independent read-only helper, repeated and changed reason, unknown or worker-authored code, missing review-evidence digest, replay and history rewrite, crash recovery, stale digest, exhausted correction budget, multi-invariant coupling, and attempted global locking or shared writes.
  - Keep root and generated ledger and runner files byte-identical, keep root and generated policy and Skill semantics aligned after path normalization, preserve non-destructive Copier updates, record the behavior under Unreleased, run the authoritative suite exactly once, and finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 依存する書き込みplanを前planの親受理後に一件ずつ開始し、却下と修正の理由を親所有の限定codeで記録する。

## Context

Isolating a worker reduces prompt breadth, but concurrent workers that modify shared or dependent state create integration conflicts and stale assumptions.

The scheduling condition assigns one accepted active plan to one fresh isolated writable worker attempt, admits or rejects that candidate before starting the next dependent writable plan, and permits concurrency only for independent read-only helper work under the existing delegation cost gate.

The review outcome reason is a parent-authored bounded reason value attached to a rejected candidate or correction decision. It supplements the concrete review finding and cannot be authored by the worker as an acceptance decision.

## Decisions

- Use one append-only parent ledger transition to close the current attempt; admit the next dependent writable start only when that transition accepts the candidate.
- Attach a small fixed reason-code vocabulary and review-evidence digest to rejected or correction transitions.
- Preserve concrete review evidence separately and do not let codes change authority or budgets.
- Keep all current correction and hard-replan triggers and fail closed on stale, concurrent, or replayed transitions.
- Use bounded parent implementation and independent review because this plan changes high-risk lifecycle gates.

## Tasks

- [ ] Extend the execution ledger with one attempt-closing transition that binds predecessor admission, candidate acceptance, and bounded rejection or correction evidence.
- [ ] Gate dependent writable starts on the exact accepted closing transition and prevent overlapping writable attempts in one chain.
- [ ] Align root and generated policy, Skill, ledger, runner, inventories, and Copier behavior.
- [ ] Add deterministic sequencing, classification, replay, crash, concurrency, budget, authority, and holdout coverage.
- [ ] Perform bounded parent implementation, inspect all critical lifecycle invariants, obtain independent review, run the authoritative suite once, and archive the accepted plan before plan 116 starts.

## Validation Notes

- Decision audit selected sequential writable execution and bounded read-only parallelism instead of shared-branch writable parallelism.
- The advisory referent contract kept the scheduling condition concrete and sealed the review outcome reason as a parent-authored value, not an event, finding, or worker decision.
- High implementation risk makes this plan ineligible for the writable runner under current routing policy.
- The parent must refresh Plan 136 and Plan 114 context paths after archival before bounded parent implementation begins.
