# Remediate actionable Codex review findings from PR 3

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - docs/plan/
  - scripts/restructure-plan.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/copier-update.sh
  - tests/test-plan-restructure.py
  - tests/test-sandboxed-plan-worker.py
  - tests/test-validation-tools.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/orchestration.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - docs/plan/checked/2026/08/01-15/077-atomic-plan-restructuring.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Bind validate, apply, and finalize-apply execution-state admission to the exact plan path verified from their candidate manifest.
  - Keep focused validation parseable and optional for checked archives that use the pre-v1 legacy manifest.
  - Require dirty product paths to be covered by exact-file or trailing-slash directory scopes with the same semantics as the sandboxed runner.
  - Let finalize-apply recover an exactly verified patch-created symlink while continuing to reject symlink ancestors and any worktree that differs from the verified patch bytes.
  - Keep root and generated runner and restructuring implementations aligned and preserve supported Copier update behavior.
  - Finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: PR 3のCodex reviewで指摘されたplan ledger、旧archive、dirty path scope、symlink復旧の不整合を修正した。

## Decisions

- Gate manifest-backed operations only after manifest verification supplies the trusted plan path, while retaining the operation-wide execution-state lease.
- Remove `focused_validation` only from legacy required fields; retain it as an optional parsed list field.
- Reuse exact-file and trailing-slash directory scope semantics across restructuring and worker admission.
- Permit an applied symlink only at the changed target during finalize recovery; never permit a symlink ancestor or skip exact patch comparison.

## Tasks

- [x] Add failing regression coverage for all four review findings.
- [x] Implement the bounded root and generated fixes.
- [x] Run focused validation and independent High/Medium review.
- [x] Run the authoritative suite, archive the plan, and commit the remediation.

## Validation Notes

- All four unresolved PR 3 threads were reproduced against the current implementation and accepted as valid findings before edits.
- The execution gate now runs once before prerequisites for every operation and again with the verified manifest plan for validate, apply, and finalize-apply.
- Legacy checked archives no longer require `focused_validation`; the field remains an optional parsed list for current plans.
- Dirty path coverage uses exact-file and trailing-slash directory semantics in both root and generated restructuring commands.
- Finalize recovery permits only the changed symlink target itself, rejects a symlink ancestor, and rejects a changed link target through exact patch comparison.
- Focused results: execution ledger 12 tests, plan restructuring 17 tests, sandboxed runner 67 tests, and validation tools 31 tests passed; runner self-test, root policy, Copier static check, root/template parity, and `git diff --check` also passed.
- Independent change review reported zero unresolved High or Medium findings.
- Authoritative `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `tests/copier-update.sh --require-copier`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed. Actionlint was unavailable and skipped by the unchanged smoke behavior; no GitHub Actions workflow changed.
