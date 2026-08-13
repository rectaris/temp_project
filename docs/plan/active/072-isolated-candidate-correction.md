# Correct a rejected candidate in a fresh isolated clone

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
  - docs/plan/checked/2026/08/01-15/054-copier-update-fail-closed.md
  - docs/plan/checked/2026/08/01-15/062-filtered-write-scope-sandbox.md
  - docs/plan/checked/2026/08/01-15/070-pr2-review-remediation.md
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
  - Add an isolated correction command that accepts an in-progress plan, a prior candidate manifest, and a bounded parent-authored correction brief.
  - Verify the prior manifest schema, source HEAD, plan path and digest, allowed write scope, patch path and digest, normalized changed paths, symlink ancestry, clone refs, and clean source before starting a correction.
  - Start every correction from a fresh isolated clone at the verified source HEAD, apply the verified prior patch only inside that clone, and provide the correction brief through a read-only input boundary.
  - Never apply the rejected patch to the source worktree, write candidate objects to the source object database, or expose prior attempt caches, Git configuration, logs, scratch files, staged authentication, or last-message artifacts to the correction worker.
  - Emit one aggregate candidate patch against the original source HEAD and pass it through the same scope, symlink, ref, digest, clean-source, object-isolation, and apply-preflight admission checks as an initial candidate.
  - Record lineage using bounded manifest fields for the prior manifest digest, prior patch digest, correction round, and correction brief digest without embedding the brief or worker output.
  - Enforce a correction budget of at most two isolated corrections after the initial candidate; reject missing lineage, skipped rounds, a third correction, changed source HEAD, changed plan digest, widened scope, and tampered artifacts.
  - Keep model availability fallback limited to bounded model availability errors during the correction start; a parent rejection itself must not trigger model fallback or complete-plan regeneration.
  - Add deterministic tests for tampered lineage, fresh-clone isolation, absent prior state, source and object-database cleanliness, malicious path and Git metadata changes, correction failure cleanup, and successful aggregate-patch application.
  - Keep root and generated policy, Skill, and runner behavior aligned and keep root/template runner implementations byte-identical.
  - Preserve non-destructive Copier updates and reject correction behavior that leaves rejection files, unresolved conflicts, or unclassified tracked-file deletion during a supported update.
checked_summary_ja: 却下候補をsourceへ適用せず、新しい隔離clone内で最大2回まで局所修正して統合patchを再生成できるようにした。

## Context

The runner currently supports only initial generation and final application.

When parent review rejects one part of a candidate, the only available implementation path regenerates the complete plan and discards correct work.

## Decisions

- Define isolated correction as verified prior-patch repair in a fresh clone that emits a new aggregate patch.
- Use manifest lineage and a parent-authored correction brief instead of editing the active plan after every local rejection.
- Keep the source repository and prior attempt state outside the correction worker's writable and readable boundaries.
- Limit one candidate lineage to two correction rounds.

## Tasks

- [ ] Add the isolated correction lifecycle and manifest lineage.
- [ ] Add deterministic positive, tampering, isolation, cleanup, and budget coverage.
- [ ] Align root/generated policy, Skill, runner, checks, and documentation.
- [ ] Run all required validation, archive, and commit before plan 073.

## Validation Notes

- Pending implementation.
