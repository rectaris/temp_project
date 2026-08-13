# Prepare Copier coverage for orchestration changes

status: checked
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: yes
human_approval_status: approved
implementation_risk: low
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - tests/copier-update.sh
context_files:
  - AGENTS.md
  - scripts/check-copier-template.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add the generated orchestration policy, plan parser, sandboxed runner, and sequential-orchestrator Skill to the simulated Copier update source copy and stage lists before those artifacts change in plan 072.
  - Assert the currently committed orchestration ownership, runner fallback, parser, and Skill semantics in generated output so the harness fails when an artifact is omitted.
  - Preserve project-owned product code, policy, configuration, plan history, and validation behavior during supported copy and update paths.
  - Retain negative coverage that rejects unresolved conflicts, rejection files, and unclassified tracked-file deletion.
  - Keep this plan limited to update-harness construction; routing policy and behavior remain read-only until plan 072.
checked_summary_ja: orchestration生成物を変更前からCopier更新元へ取り込み、更新安全性を各commitで検証できるharnessを準備した。

## Context

Repeated routing candidates passed Copier tests while their uncommitted generated changes were absent from the simulated update source.

The update harness must be committed before plan 072 changes generated orchestration artifacts.

## Decisions

- The user explicitly authorized parent-session implementation for plans 071 through 075; do not start another writable sequential worker for this sequence.
- Parent implementation remains bounded by this plan's write scope and all declared validation and lifecycle gates.
- Prepare update-source coverage as an independently acceptable prerequisite.
- Assert current semantics in plan 071; plan 072 updates those assertions together with routing behavior.
- Do not change routing policy, the runner, generated artifacts, or fixed evaluation fixtures in this slice.

## Tasks

- [x] Add all four generated orchestration artifacts to simulated Copier source copy and stage lists.
- [x] Assert current generated orchestration semantics without weakening update negatives.
- [x] Run all required validation, archive, and commit before plan 072.

## Validation Notes

- Plans were redesigned after two broad-candidate rejections and two routing-slice correction rejections. Rejected manifests remain local under `/tmp/orchestration-plan-071-*` and were never applied to the source repository.
- Independent review required this harness to precede the generated routing changes so every committed slice preserves the non-destructive Copier invariant.
- Rejected harness candidate `/tmp/orchestration-plan-071-copier-harness-VFsTnd/manifest.json`, source HEAD `cb481334e1474d0b8de0cbe6d0873da31bda0716`. One GPT-5.3-Codex-Spark medium attempt generated it without fallback, and all required validation passed in a review clone.
- The harness implementation was acceptable, but the candidate was not applied because it marked parent-owned archive and commit work complete. Plan lifecycle metadata is removed from the writable implementation scope for the correction.
- The fresh correction run at source HEAD `c7cb3b64b03e4637265e35eb574943795c978ea9` was stopped after more than 20 minutes without output or CPU progress while the Codex CLI remained pending. It emitted no manifest. This was not a classified availability error, so no fallback or retry was started and the source repository remained unchanged.
- Parent-session implementation added the four generated orchestration artifacts to both the simulated update-source copy and Git stage lists, then asserted their current ownership, model fallback, parser, and Skill semantics without changing the existing negative update cases.
- Parent-session acceptance validation passed: `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `REQUIRE_COPIER=1 tests/copier-update.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check`.
