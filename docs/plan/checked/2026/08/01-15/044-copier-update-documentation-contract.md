# Document the non-destructive Copier update contract

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: yes
human_approval_status: approved
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - README.md
  - docs/plan/
  - references/template-development.md
  - scripts/check-copier-template.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - template/.project-agent-workflow/ownership.yaml
  - template/README.md.jinja
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - git diff --check
acceptance:
  - State that template development must preserve project-owned files, product behavior, local policy, plan history, and validation viability across Copier copy and update.
  - Require `--trust` in documented copy and update commands because the template always runs a post-render agent-profile task.
  - Document the field-level ownership exception for `model` and `model_reasoning_effort` in seeded `.codex/agents/*.toml` files.
  - Add deterministic checks that prevent the documented trust and ownership contract from silently regressing.
  - Record the unreleased agent-profile changes and the v1.1.2 Copier safety fixes in a user-facing change history.
checked_summary_ja: Copier の copy/update で生成先の製品コード、プロジェクト固有規則、計画履歴、検証可能性を損なわない開発契約を明文化し、trust と agent profile の所有境界を実装に合わせた。

## Decisions

- Define non-destructive behavior in terms of repository-owned content and behavior, not as a promise that no generated file changes.
- Treat `model` and `model_reasoning_effort` as template-fixed fields while preserving all other content in seeded helper-agent files.
- Require trust for every documented copy and update command because `_tasks` executes after both operations.
- Enforce the documentation contract through the existing deterministic template checker.

## Tasks

- [x] Update root and generated user instructions.
- [x] Add a user-facing release history for the recent Copier and agent-profile changes.
- [x] Update template-maintainer and generated adoption specifications.
- [x] Extend machine-readable ownership metadata and deterministic checks.
- [x] Run required validation and archive this plan.

## Validation Notes

- `scripts/lint-project-workflow.sh` passed, including the static template contract checks, 71 Python tests, and the root plan lifecycle test.
- `REQUIRE_COPIER=1 tests/smoke.sh` passed across generated fixture combinations; actionlint was unavailable and skipped, and no GitHub Actions file changed in this work.
- `REQUIRE_COPIER=1 tests/copier-update.sh` passed across the supported pre-v1 adoption and namespaced update lanes.
- `git diff --check` passed before plan finalization.
