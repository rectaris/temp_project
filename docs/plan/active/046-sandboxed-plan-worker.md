# Enforce physical isolation for delegated plan implementation

status: in_progress
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - AGENTS.md
  - .codex/agents/sequential_plan_worker.toml
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/plan/active/046-sandboxed-plan-worker.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.codex/agents/sequential_plan_worker.toml
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - template/docs/plan/sub-agents/custom-agents.md
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/scripts/planlib.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - A Bubblewrap integration test proves a delegated command can write inside its isolated temporary clone but cannot write to the source repository or another host path.
  - The runner exits nonzero before delegation when Bubblewrap, Git, or Codex CLI is unavailable, when the source repository is dirty, or when the active plan is invalid.
  - Delegated Codex execution receives a temporary Git clone as its working repository while the host filesystem and source repository are mounted read-only.
  - The runner emits a candidate patch and manifest without mutating the source repository and rejects changed paths outside the active plan write_scope.
  - Patch application requires a matching source HEAD, a clean source worktree, a matching patch digest, an allowed-path recheck, and a successful git apply preflight.
  - The built-in sequential_plan_worker profile is read-only so writable plan implementation uses only the sandboxed runner.
  - Root and generated-project orchestration policy require the sandboxed runner and never fall back to advisory-only write scoping.
  - Root and template runner implementations remain deterministically aligned.
checked_summary_ja: 委任実装を一時クローン内へ隔離し、許可範囲の候補パッチだけを親が検証して取り込む。

## Context

The current delegated `write_scope` is an instruction rather than a filesystem boundary.

A worker with workspace-wide write access created diagnostic files outside its assigned plan scope, so writable delegation must move behind an operating-system-enforced boundary before plan 054 resumes.

The source repository is the Git repository whose accepted history and user changes must remain read-only during delegated execution.

The isolated worker workspace is the temporary Git clone that receives every delegated write.

The sandboxed plan worker is a delegated Codex CLI process executed by Bubblewrap with the source repository read-only and only its temporary clone and scratch directory writable.

Candidate patch admission is the parent-side path check that rejects edits outside the active plan write_scope before a patch can be applied.

The term candidate patch admission identifies that check in the remaining tasks.

If Bubblewrap, Git, or Codex CLI prerequisites are unavailable, the runner exits nonzero before starting a writable worker.

The root scripts and orchestration policy plus the template managed scripts and generated orchestration policy implement semantically aligned behavior.

## Decisions

- Use Bubblewrap as the initial physical isolation backend and fail closed when it is unavailable.
- Mount the host filesystem and source repository read-only, and expose only a temporary Git clone and temporary scratch storage as writable.
- Run non-interactive Codex CLI inside Bubblewrap instead of granting the built-in sequential_plan_worker direct repository writes.
- Keep the built-in sequential_plan_worker profile read-only.
- Require a clean source repository before starting or applying a sandboxed run.
- Emit a candidate patch and manifest first; apply them only through a separate parent-owned command after deterministic admission checks.
- Reject candidate changes outside the active plan write_scope rather than importing a partial subset.
- Do not add an unsafe non-sandboxed fallback on platforms without Bubblewrap.
- Keep the root implementation and the Copier-managed generated implementation semantically aligned.

## Tasks

- [ ] Add the root sandboxed plan-worker runner with run, apply, and self-test commands.
- [ ] Add deterministic plan-scope parsing, candidate-patch admission, base revision, digest, and clean-worktree checks.
- [ ] Add Bubblewrap isolation tests that attempt writes inside and outside the isolated workspace.
- [ ] Make the built-in sequential_plan_worker read-only and route writable sequential implementation through the runner.
- [ ] Add the equivalent generated runner, agent profile, Skill instructions, and orchestration policy under template/.
- [ ] Add root/template parity and generated-project smoke coverage.
- [ ] Run every required validation command.

## Validation Notes

- Pending.
