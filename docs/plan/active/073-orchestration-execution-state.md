# Record run-local availability and bounded execution telemetry

status: in_progress
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
write_scope:
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/copier-update.sh
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/plan/checked/2026/08/01-15/046-sandboxed-plan-worker.md
  - docs/plan/checked/2026/08/01-15/062-filtered-write-scope-sandbox.md
  - docs/plan/checked/2026/08/01-15/066-sequential-worker-model-fallback.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add an explicit orchestration-run availability-state path outside the repository; after a bounded availability error, record only model and reason code and skip another start of that model while the same state is reused.
  - Bind availability state to an explicit nonblank orchestration run identifier, validate its schema version and exact bounded field shape, and reject reuse with a different run identifier.
  - Keep availability state ephemeral, reject malformed or oversized state, reject target and ancestor symlinks, and write atomically through directory-file-descriptor operations without following a swapped target or parent.
  - Bound state bytes, entry count, model length, and run-identifier length; require one reason per model and never store raw output, prompts, environment values, or credentials.
  - Skip both preferred and fallback models already recorded unavailable in the same run; remembered unavailability must not become a semantic or validation result.
  - Record parent-produced bounded manifest telemetry for every initial candidate: all attempt durations, total runner duration after candidate collection and admission checks, model starts, availability failures, skipped known-unavailable starts, candidate generations, full-validation count, and selected implementation risk and ambiguity.
  - Include custom-worker attempt duration while counting zero model starts, and emit numeric values with finite nonnegative bounds.
  - Add executable tests for first availability recording, same-run preferred and fallback skips, run-id mismatch, malformed schema and fields, size and count bounds, duplicate model rejection, target and ancestor symlink rejection, target and parent swap attempts, fallback availability failure, custom attempts, and every telemetry counter and duration boundary.
  - Keep root and generated policy, Skill, runner, and static checks aligned and keep root/template runner implementations byte-identical.
  - Preserve non-destructive Copier updates and rejection of unresolved conflicts, rejection files, and unclassified tracked-file deletion.
checked_summary_ja: 同一実行内の利用不能model再起動を防ぎ、候補生成・検証回数と所要時間を秘密情報なしで計測できるようにした。

## Context

Plans 071 and 072 establish value-gated delegation, writable-profile routing, fixed evaluation, and Copier integration.

Availability state and execution telemetry must exist before correction and staged validation change the event sequence being measured.

## Decisions

- Keep availability memory ephemeral, explicitly run-bound, size-bounded, and independent from semantic candidate acceptance.
- Produce telemetry in the parent-controlled runner rather than candidate-controlled files.
- Establish the initial-generation telemetry schema before plans 074 and 075 add correction, review, and validation events.

## Tasks

- [ ] Add bounded run-local availability state and preferred and fallback skip behavior.
- [ ] Add parent-produced initial-candidate telemetry and exact schema bounds.
- [ ] Add executable positive, edge, race, negative, custom-worker, and telemetry-boundary coverage.
- [ ] Align root/generated policy, Skill, runner, checks, and documentation.
- [ ] Run all required validation, archive, and commit before plan 074.

## Validation Notes

- Pending implementation.
