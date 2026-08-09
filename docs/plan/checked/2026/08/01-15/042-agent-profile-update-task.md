# Enforce fixed agent profiles during Copier updates

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: yes
human_approval_status: approved
write_scope:
  - copier.yml
  - docs/plan/
  - scripts/
  - tests/
context_files:
  - none
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Run a deterministic post-render task on Copier copy and update to enforce the fixed model and reasoning fields for generated built-in agents.
  - Preserve project-owned agent instructions and any unrelated fields while changing only model and model_reasoning_effort.
  - Prove that a v1.1.1 generated project receives current fixed profiles through copier update.
checked_summary_ja: Copier の更新後タスクで既存生成先の組み込み agent 設定を固定モデルへ正規化し、プロジェクト固有の指示本文を保持した。

## Decisions

- Use a post-render Copier task because it runs after both initial copy and update and does not depend on a future release tag.
- Treat model and model_reasoning_effort as template-fixed fields while preserving the rest of each seeded project-owned agent file.
- Fail on missing or invalid built-in agent files instead of reporting a successful update with incomplete model policy.

## Tasks

- [x] Add the deterministic agent-profile updater and Copier task wiring.
- [x] Add focused unit and v1.1.1 update regression coverage.
- [x] Run completion validation and archive this plan.

## Validation Notes

- `scripts/update_agent_model_profiles.py` preserves agent instructions and unrelated TOML fields, changes only model and model_reasoning_effort, writes atomically, and refuses missing, invalid, duplicate-field, or symlinked built-in profiles.
- Copier runs the updater after both copy and update through `_tasks`; project workflows and tests now pass `--trust` when invoking this repository template.
- `scripts/lint-project-workflow.sh` passed, including four focused profile-normalization unit tests.
- `tests/smoke.sh` passed all generated profiles; GitHub Actions lint was skipped because actionlint is not installed.
- `COPIER_UPDATE_TARGET_REF=f2192c16f9f1dfc919f07abbb55360560b72075c REQUIRE_COPIER=1 tests/copier-update.sh` passed and proved fixed profiles on v1.1.1 update while preserving other project-owned settings.
- `tests/copier-minimum.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed.
