# Route delegated implementation by value and implementation profile

status: checked
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
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/plan/checked/2026/08/01-15/052-proactive-bounded-subagents.md
  - docs/plan/checked/2026/08/01-15/066-sequential-worker-model-fallback.md
  - docs/plan/checked/2026/08/01-15/070-pr2-review-remediation.md
  - .codex/agents/fast_scoped_worker.toml
  - .codex/agents/scoped_worker.toml
  - .codex/agents/change_reviewer.toml
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
  - Define an admissible implementation slice as one invariant that can be reviewed and validated independently while preserving an explicit later integration gate.
  - Route the writable sequential worker to one admissible implementation slice rather than treating one broad active plan as one candidate, and add a focused policy assertion for that routing boundary.
  - Replace category-only proactive delegation with a value gate requiring independently useful output and expected context reduction, parallelism, or review value greater than coordination cost; repository breadth alone is insufficient.
  - Preserve independent security and regression review, parent acceptance, explicit write scope, read-only context, secret and external-write exclusions, final ownership, and final-report transparency.
  - Add separate optional implementation risk and ambiguity fields; use Spark medium only when both are low, Terra medium when neither is high and one is ordinary, and refuse either high input.
  - Default only absent classification fields to ordinary; reject present blank, whitespace-only, list-valued, or unknown values.
  - Preserve explicit nonblank model and reasoning overrides, reserve Sol for independent review, reject preferred and fallback writable-Sol overrides, and keep nonavailability failures outside fallback eligibility.
  - Add runner tests for Spark, Terra, both high refusals, successful override, empty override rejection, preferred and fallback Sol refusal, and nonavailability failure.
  - Add fixed scenarios for the value gate and every routing case with unique identifiers and exact input/result checking; preserve every established critical requirement including helper-use disclosure, role, write scope, and acceptance path.
  - Keep root and generated policy, Skill, parser, runner, static checks, fixture, smoke checks, and generated update assertions aligned; preserve byte-identical runner copies.
  - Use plan 071's committed Copier harness to exercise every changed generated artifact and retain conflict, rejection-file, tracked-deletion, and project-owned-state protections.
  - Keep availability state and telemetry out of this slice; plans 073 through 075 own those later event changes.
checked_summary_ja: 委譲の価値判定と曖昧さ・risk別model選択を追加し、固定評価とCopier更新を含む統合条件で検証した。

## Context

Plan 071 commits the Copier harness needed to expose uncommitted generated changes during this plan's validation.

Earlier candidates showed that routing code, fixed evaluation, and generated update assertions must be accepted together after the harness exists.

## Decisions

- The user explicitly authorized parent-session implementation for plans 071 through 075; do not start another writable sequential worker for this sequence.
- Parent implementation remains bounded by this plan's write scope and all declared validation and lifecycle gates.
- Treat value-gated routing and its fixed evaluation as one independently acceptable invariant.
- Keep runtime availability fallback state, candidate correction, and validation ordering in later plans.
- Preserve all established fixture safeguards while extending the routing matrix.

## Tasks

- [x] Update root and generated orchestration policy and sequential Skill guidance.
- [x] Assert that one admissible implementation slice, not one broad plan, is the writable delegation unit.
- [x] Add strict plan classifications, writable-profile selection, overrides, and runner tests.
- [x] Add complete fixed value/routing evaluation without removing established critical requirements.
- [x] Update generated Copier assertions through the committed plan 071 harness.
- [x] Run all required validation, archive, and commit before plan 073.

## Validation Notes

- Parent-session implementation replaced breadth-only delegation with the independently-useful-output value gate and defined an admissible writable slice as one independently reviewable invariant with a later integration gate.
- The managed parser now preserves optional scalar risk and ambiguity declarations, including present blank or list-valued inputs for fail-closed runner rejection. The runner selects Spark medium for low/low, Terra medium for ordinary without high, refuses either high, and rejects preferred or fallback writable Sol while preserving strict nonblank overrides.
- Fixed evaluation preserves R1 through R5, adds slice and routing requirements, retains median/edge/negative/untuned-holdout cases, and checks exact value-gate and routing inputs/results under unique identifiers.
- Runner root/template copies are byte-identical. Parent-session validation passed all declared commands: 39 runner tests, runner self-test, root policy check, Copier template check, workflow lint, smoke, required Copier update, change-aware validation, and diff checks.
