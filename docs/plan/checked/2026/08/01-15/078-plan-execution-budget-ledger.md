# Enforce plan execution and review budgets

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
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
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/077-atomic-plan-restructuring.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add a locked parent-owned plan execution ledger outside the repository, bound to a plan path, plan digest, source HEAD, run identifier, and primary-invariant digest.
  - Record bounded implementation mode, candidate generations, correction rounds, parent-direct remediation rounds, affected-invariant digests, focused-validation events, authoritative-validation events, and replan reason codes without prompts, output bodies, environment values, or credentials.
  - Set `replan_required` after the existing initial-plus-two-corrections budget, after two parent-direct remediation rounds that still leave High or Medium findings, or immediately when one review reports findings for more than one independent invariant.
  - Set `replan_required` immediately for scope/spec/security-boundary drift or a design change after authoritative validation.
  - Reject further runner starts, corrections, validation, apply, or successful completion after a hard trigger.
  - Require an independent-review receipt for parent-direct remediation and prevent the same execution from replaying or rewriting an earlier review event.
  - Keep elapsed time bounded and monotonic as telemetry only; it must not clear or create semantic findings.
  - Keep candidate lifecycle and plan execution ledger cross-linked by digests while preserving existing candidate admission and exactly-once validation.
checked_summary_ja: 委譲と親直接実装に共通する実行予算を記録し、再構成条件で継続を停止するようにした。

## Decisions

- Plans 076 and 077 must be accepted before this plan starts.
- Store the execution ledger outside the repository and store only bounded codes, counters, digests, identifiers, and durations.
- Hard budget triggers cannot be cleared by the same implementation run.
- Reuse the existing candidate lifecycle for candidate-level order and cross-link it to the plan-level ledger.

## Tasks

- [x] Add exact locked execution-ledger storage and event transitions.
- [x] Integrate delegated and parent-direct review budgets with runner admission.
- [x] Add replay, tampering, multi-invariant, scope-drift, and post-authoritative negative tests.
- [x] Run required validation, independent review, archive, and commit before plan 079.

## Validation Notes

- `python3 tests/test-plan-execution-state.py`: 9 tests passed.
- `python3 tests/test-sandboxed-plan-worker.py`: 65 tests passed.
- `python3 scripts/run-sandboxed-plan-worker.py self-test`: passed.
- `python3 scripts/check-root-agent-policy.py`: passed.
- `python3 scripts/check-copier-template.py`: passed.
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed with the documented actionlint-unavailable skip and fallback backend.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Independent `change_reviewer` found two High and two Medium issues in gate optionality, concurrent trigger admission, lifecycle content binding, and valid-shape history rewriting. The final event-derived state fix closed the last bypass; final rereview reported zero unresolved High or Medium findings.
