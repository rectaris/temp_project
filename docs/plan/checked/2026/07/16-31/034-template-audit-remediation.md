# Implement accepted template audit recommendations

status: checked
task_types:
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - .codex/
  - .github/
  - copier.yml
  - pyproject.toml
  - uv.lock
  - README.md
  - .codex/skills/
  - docs/agent/
  - docs/plan/
  - template/.codex/
  - template/.github/
  - template/AGENTS.md.jinja
  - template/docs/agent/
  - template/scripts/
  - scripts/
  - tests/
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - tests/root-plan-lifecycle.sh
  - git diff --check
acceptance:
  - Generated plan manifests support route unions, separate write and context paths, enforced human-design approval, and an unambiguous active deferred state.
  - Generated external-service records represent no-authentication, environment, and platform credentials and enforce write authorization before external writes.
  - Copier updates prefer current answers over legacy booleans and remove only an unchanged known legacy SkillSpector script.
  - Validation covers staged and unstaged whitespace, safe declarative command forms, CI commit ranges, semantic pairwise output, defaults, and generated YAML syntax.
  - Generated helper agents inherit an available model, preserve main-session commit ownership, and follow one external-service gate.
  - Generated profile, skill policy, and Codex configuration describe actual runtime behavior without duplicated or unsupported settings.
checked_summary_ja: テンプレート監査で採用した計画、外部サービス、Copier更新、検証、CI、補助エージェントの修正を実装した。

## Problem

The template passes its current checks while several generated contracts remain ambiguous or untested, including plan routing, write ownership, deferred work, external authentication, legacy Copier answers, staged whitespace, CI ranges, and helper-agent availability.

## Goal

Implement the accepted audit recommendations as deterministic generated-project contracts with migration and regression coverage.

## Terms

task_types means the list of spec-index route keys whose required specifications jointly govern the plan.

write_scope means the repository paths that the plan permits implementation to create or modify.

context_files means repository paths needed for understanding or validation but not granted as implementation write targets.

authentication means the selected credential mechanism for one external service: none, environment, or platform.

credential_reference means the environment-variable name or platform secret identifier interpreted by the service authentication setting.

automatic_hook_capture means whether the generated hook configuration records Codex lifecycle events for the selected hooks mode.

## Decisions

- Keep conditional migration support from `v0.4.1`; remove a legacy generated file only when it still matches known historical template content, and otherwise preserve it with a conflict report.
- Replace one `task_type` with a `task_types` list and lint the union of routed required specifications.
- Replace mixed `target_files` with `write_scope` and `context_files`.
- Require `human_design_required: yes` plans to use Class C approval and require approval before implementation.
- Keep `deferred` plans active; only completed work may transition to `ready_to_archive` and then `checked`.
- Represent external authentication with `authentication: none|environment|platform` and `credential_reference`, and validate write authorization as a separate gate.
- Use declarative argument-vector validation rules and remove the unused `expected_output` manifest field.
- Validate CI whitespace over the event base/head range and validate both staged and unstaged changes locally.
- Use semantic pairwise and default-answer assertions instead of rendering every answer combination; add pinned YAML and workflow syntax validation.
- Let helper agents inherit the parent model, keep the sequential worker fixed until a configuration need exists, and make the shared MCP policy the common external-service gate.
- Keep detailed decision-audit policy in the specification and keep the Skill operational and concise.
- Use the canonical `max_concurrent_threads_per_session` setting and omit unsupported `max_depth`.
- Separate installed logging support from automatic hook capture in the generated project profile.

## Implementation Instructions

1. Add focused regression coverage for every confirmed defect and accepted contract.
2. Update generated plan manifest parsing, creation, linting, lifecycle scripts, orchestration policy, and related docs.
3. Update external-service configuration, policy, and shared/specialized external-service Skills.
4. Update Copier answer precedence and safe legacy-file migration behavior.
5. Update local validation, CI whitespace validation, generated configuration, helper-agent prompts, and generated profile wording.
6. Expand semantic Copier, YAML, workflow, and default-answer checks without replacing focused tests with exhaustive generation.
7. Run the complete validation matrix, record evidence, complete the plan, archive it, and commit the scoped change.

## Tasks

- [x] Repair and test generated plan manifest and lifecycle contracts.
- [x] Repair and test external-service authentication and write authorization contracts.
- [x] Repair and test Copier answer precedence and legacy-file migration.
- [x] Repair and test local validation, CI ranges, generated configuration, and helper agents.
- [x] Expand semantic generation, default-answer, and syntax validation.
- [x] Align generated policy and Skill wording.
- [x] Run validation, archive the plan, and commit the completed work.

## Validation Notes

- `python3 scripts/validate-changes.py --all`: passed.
- `scripts/lint-project-workflow.sh`: passed, including 26 hook tests, 8 referent-contract tests, and 8 validation-tool tests.
- `PATH=/tmp/project-agent-workflow-actionlint:$PATH REQUIRE_ACTIONLINT=1 tests/smoke.sh`: passed.
- `REQUIRE_COPIER=1 tests/copier-update.sh`: passed.
- `tests/copier-minimum.sh`: passed.
- `tests/root-plan-lifecycle.sh`: passed.
- `UV_CACHE_DIR=.uv-cache uv run python scripts/check-yaml.py .`: passed for 28 YAML files.
- `PATH=/tmp/project-agent-workflow-actionlint:$PATH REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh`: passed.
- `git diff --check`: passed.
- Hosted GitHub Actions and writes to a live external-service provider were not executed locally.
- Copier update cleanup is intentionally explicit: the generated migration helper removes only the unchanged known legacy SkillSpector file and reports modified legacy content for manual review.
