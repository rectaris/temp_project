# Stage candidate review and bound orchestration escalation

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
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan_validation_commands.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
  - tests/test-validation-tools.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_VALIDATION.md
  - docs/plan/checked/2026/08/01-15/056-ci-autofix-required-validation.md
  - docs/plan/checked/2026/08/01-15/062-filtered-write-scope-sandbox.md
  - docs/plan/checked/2026/08/01-15/064-browser-task-routing.md
  - docs/plan/checked/2026/08/01-15/067-root-external-write-policy.md
  - docs/plan/checked/2026/08/01-15/070-pr2-review-remediation.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Extend bounded telemetry with parent-review rejection, correction-round, focused-validation, and authoritative-validation events without storing prompts, output bodies, environment values, or credentials.
  - Define focused validation as plan-declared deterministic checks for one admissible implementation slice and authoritative validation as the complete parent-owned acceptance suite.
  - Perform candidate admission and parent diff and critical-invariant review before focused validation, then run authoritative validation only for a candidate that is otherwise acceptable.
  - Keep candidate-controlled dependency, build, test, hook, Git configuration, and validation definitions outside any immutable admission authority; final validation strength and configured fail-closed behavior must not be weakened.
  - Add an optional focused-validation plan manifest list while preserving validation as the authoritative command list and preserving compatibility for existing plans without a focused list.
  - Change candidate generation so it does not run plan validation, then add a separate parent-authorized post-admission validation operation that creates a fresh review clone, applies the verified candidate only there, and runs focused validation only after parent diff and critical-invariant approval.
  - Keep focused-validation command definitions in the parent-owned committed plan, run them without credentials or external-write authority, and prevent the candidate from changing the active plan or the runner that selects those commands.
  - After the second rejected isolated correction, require a strategy-change decision rather than a fourth generation of the same slice.
  - Allow parent implementation only for high-judgment work or after correction-budget exhaustion, with an explicit bounded write scope, clean-worktree checks, no external or destructive authority expansion, independent change review, and the same authoritative validation.
  - Preserve the prohibition on helper-owned final interpretation, authorization, external writes, destructive operations, validation acceptance, commit, release, and completion reporting.
  - Add deterministic event-count fixtures for historical plan shapes equivalent to 062, 064, and 070; require no more than three implementation generations, one known-unavailable preferred-model start per orchestration run, and one authoritative full-suite execution per accepted candidate.
  - Add executable boundary tests for every telemetry counter and duration, including custom workers and correction lineage, and require schema-bounded numeric values that cannot be supplied by candidate-controlled files.
  - Use fixed median, edge, negative, and holdout scenario sets; keep the holdout set outside reusable implementation prompts and fail evaluation when any scenario class is absent.
  - Add evaluation criteria requiring at least 30 percent lower median model starts and time-to-accepted-patch against a versioned recorded representative baseline, while keeping p95 time-to-accepted-patch no more than 10 percent worse than that baseline and leaving zero unresolved High or Medium independent-review findings.
  - Keep root and generated plan parsing, validation policy, orchestration policy, Skills, tests, and Copier update behavior aligned.
  - Preserve non-destructive Copier updates and add negative coverage for rejection files, unresolved conflicts, and unclassified tracked-file deletion.
checked_summary_ja: 候補reviewを全検証より前へ移し、局所検証と最終検証を分離し、固定scenarioでtelemetryと速度改善を評価して3世代後の再設計または親実装を義務化した。

## Context

Several rejected candidates completed broad tests before parent or independent review found acceptance failures.

The current worker prompt runs every validation command, while the parent must still inspect and validate the candidate before acceptance.

## Decisions

- The user explicitly authorized parent-session implementation for plans 071 through 075; do not start another writable sequential worker for this sequence.
- Parent implementation remains bounded by this plan's write scope and all declared validation and lifecycle gates.
- Review admission, diff, and critical invariants before starting the post-admission review-clone validation operation.
- Keep focused validation distinct from authoritative validation and keep the complete suite parent-owned.
- End automatic candidate work after one initial generation and two isolated corrections.
- Permit bounded parent implementation only as an explicit high-judgment or exhausted-budget escalation with independent review.
- Evaluate throughput using event counts and relative representative-scenario measurements instead of unsupported absolute wall-clock thresholds.
- Keep bounded telemetry parent-produced and sufficient to distinguish generation, correction, review rejection, focused validation, and authoritative validation events.

## Tasks

- [ ] Add focused-validation plan parsing and staged worker/parent guidance.
- [ ] Add bounded strategy-change and parent-implementation policy with negative coverage.
- [ ] Add fixed median, edge, negative, and holdout event-count fixtures and relative-performance evaluation.
- [ ] Extend bounded manifest telemetry for correction, review, and validation events and add executable boundary tests.
- [ ] Run all required validation, archive, and commit.

## Validation Notes

- Pending implementation.
