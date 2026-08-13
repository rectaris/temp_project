# Route delegated implementation by value and implementation profile

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
  - .codex/agents/fast_scoped_worker.toml
  - .codex/agents/scoped_worker.toml
  - .codex/agents/change_reviewer.toml
  - docs/agent/spec-index.yaml
  - docs/plan/checked/2026/08/01-15/052-proactive-bounded-subagents.md
  - docs/plan/checked/2026/08/01-15/066-sequential-worker-model-fallback.md
  - docs/plan/checked/2026/08/01-15/070-pr2-review-remediation.md
  - template/.codex/agents/fast_scoped_worker.toml
  - template/.codex/agents/scoped_worker.toml
  - template/.codex/agents/change_reviewer.toml
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
  - Define an admissible implementation slice as one invariant that can be reviewed and validated independently while preserving an explicit later integration gate; route sequential workers to one slice rather than assuming one broad plan is one candidate.
  - Replace category-only proactive delegation with a delegation value gate that requires independently useful output and expected context-reduction, parallelism, or review value greater than coordination cost.
  - Preserve independent security and regression review, parent acceptance, explicit write scope, read-only context, secret and external-write exclusions, and final ownership in the main session.
  - Add separate optional active-plan implementation risk and implementation ambiguity fields with low, ordinary, and high values; use Spark medium only when both inputs are low, use Terra medium when neither is high and at least one is ordinary, and refuse writable sequential delegation when either input is high.
  - Preserve explicit CLI model and reasoning overrides for writable profiles, reserve Sol high for independent security or regression review, reject Sol as a writable sequential override, and keep semantic, implementation, validation, sandbox, authentication, and unclassified failures outside model fallback eligibility.
  - Keep runtime availability fallback separate from correction of rejected work; availability-state persistence and bounded execution telemetry are implemented by later plans after this routing slice is accepted.
  - Extend deterministic orchestration scenarios so repository breadth alone is insufficient and independent value, plan-selected Spark and Terra, both high-input refusals, explicit override, and writable-Sol rejection are executable requirements.
  - Require unique requirement and scenario identifiers in fixed orchestration fixtures, and provide concrete risk, ambiguity, override, and expected-routing inputs for every routing case.
  - Keep root and generated policy, Skill, runner, and plan parsing semantically aligned, and preserve byte-identical root/template runner implementations.
  - Preserve non-destructive Copier updates and add negative coverage proving orchestration updates do not accept rejection files, unresolved conflicts, or unclassified tracked-file deletion.
  - Add executable tests for plan-selected Spark and Terra, each high-input refusal, explicit nonblank model and reasoning override, explicitly supplied empty override rejection, writable Sol rejection for preferred and fallback profiles, and nonavailability failures that remain ineligible for fallback.
checked_summary_ja: 委譲の価値判定と作業の曖昧さ・リスク別モデル選択を追加し、広さだけを理由にした委譲と不適格な書込profileを防いだ。

## Context

Plans 062, 064, and 067 required multiple complete candidate generations before acceptance.

Plan 070 repeatedly started an unavailable Spark worker before Luna max generated each candidate, and broad validation completed before review found semantic and security omissions.

The current orchestration fixture proves that broad work delegates safely but does not measure discarded work, repeated unavailable starts, candidate generations, or duplicate full validation.

## Decisions

- An admissible implementation slice is a set of changes that establishes one invariant, can be reviewed and validated independently, and has an explicit dependency on later integration checks.
- An isolated correction is a parent-authorized action that verifies a prior candidate, repairs it only in a fresh isolated clone, and emits a new aggregate patch without mutating the source repository.
- The delegation value gate is satisfied only when assigned helper output is independently useful and its expected context reduction, parallelism, or review value exceeds coordination cost.
- Focused validation means the plan-declared deterministic commands that exercise only the changed implementation slice after mechanical admission and semantic review.
- Authoritative validation means the complete parent-owned validation command set executed for a candidate that has passed admission, review, and focused validation.
- The correction budget is a maximum of two isolated corrections after one initial candidate for the same admissible implementation slice.
- A strategy-change decision occurs after the second rejected isolated correction and selects slice splitting, another qualified implementation profile, or parent implementation with independent review.
- The separate task-ambiguity and task-risk classifications, each with low, ordinary, or high values, used together before selecting a writable implementation profile.
- A parent-authorized operation after mechanical admission and parent diff approval that applies the verified candidate only in a fresh review clone and runs plan-declared focused validation there.
- Use an admissible implementation slice rather than a whole broad plan as the writable delegation unit.
- Require the delegation value gate before helper creation.
- Select the default writable implementation profile from separate plan ambiguity and risk inputs and keep runtime availability fallback separate from correction of rejected work.
- Keep runtime availability fallback state and candidate correction separate from this routing slice.
- Keep authoritative validation and each strategy-change decision parent-owned.

## Tasks

- [ ] Update root and generated orchestration policy and sequential Skill guidance.
- [ ] Add separate plan ambiguity and risk parsing, joint defaults, and routing tests.
- [ ] Add deterministic runner, policy, template, generated-project, and Copier update coverage.
- [ ] Run all required validation, archive, and commit before plan 072.

## Validation Notes

- Rejected initial candidate `/tmp/orchestration-plan-071-9UJZcX/manifest.json`, source HEAD `701d8a60aea8d7412c6ab640e7bb4507c0e74dd5`. One GPT-5.6-Terra medium attempt generated the candidate without fallback.
- Parent review-clone validation passed 37 runner tests, runner self-test, root policy, Copier static checks, workflow lint, smoke, non-destructive Copier update, full managed validation, root/template runner parity, Python compilation, and diff checks.
- The candidate was not applied because total runner duration ended before patch collection and admission, availability state had no run identity and did not validate schema version, and executable coverage did not exercise known-unavailable skip, writable Sol rejection, telemetry, or malformed and symlinked state paths.
- Rejected correction candidate `/tmp/orchestration-plan-071-correction-4lwWPM/manifest.json`, source HEAD `05d1c11c412da3e382312ae4549d12489cc82f6d`. One GPT-5.6-Terra medium attempt generated the candidate without fallback.
- The correction candidate was not applied because its runner suite failed `test_writable_profile_selection_and_sol_refusal`, availability-state replacement still depended on path rechecks rather than directory-file-descriptor operations that close parent-directory swap races, and executable coverage still omitted the same-run known-unavailable skip, both high-input refusals, plan-selected Terra, state-path symlink cases, fallback availability failure, and bounded telemetry counters and duration boundary.
- Rejected second correction candidate `/tmp/orchestration-plan-071-correction2-2zqL0z/manifest.json`, source HEAD `ac4ba934ca921de861a2fe50c560d2f3602cdbe0`. One GPT-5.6-Terra medium attempt generated the candidate without fallback.
- The second correction candidate was not applied because manifest telemetry omitted required generation and full-validation counters and its integration tests still omitted same-run availability skipping and telemetry boundaries. The correction budget is exhausted, so the implementation strategy changed: plan 071 is narrowed to value-gated delegation and writable-profile routing; availability state and initial telemetry move to plan 072, correction becomes plan 073, and staged validation and performance evaluation become plan 074.
- Rejected routing-slice candidate `/tmp/orchestration-plan-071-routing2-jhwx5n/manifest.json`, source HEAD `d8c33d65c1d0eb15e7f86e5eaf1ca7aa44248267`. One GPT-5.6-Terra medium attempt generated the candidate without fallback.
- Review-clone validation passed 39 runner tests, runner self-test, root policy, Copier static checks, workflow lint, smoke, non-destructive Copier update, full managed validation, root/template runner parity, Python compilation, and diff checks. The candidate was not applied because the orchestration fixture reused requirement identifier `R5` without executable routing inputs and explicit empty model or reasoning overrides silently selected plan defaults instead of failing closed.
