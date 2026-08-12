# Preserve TOML strings while normalizing agent model fields

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/active/055-agent-profile-toml-aware.md
  - scripts/update_agent_model_profiles.py
  - tests/test-agent-model-profiles.py
context_files:
  - copier.yml
  - references/template-development.md
  - template/.codex/agents/
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-agent-model-profiles.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Only syntactically top-level `model` and `model_reasoning_effort` assignments are normalized.
  - Field-like lines inside basic or literal multiline strings remain byte-for-byte unchanged.
  - Nested-table fields are not mistaken for root profile fields.
  - Existing comments, instructions, whitespace, and unrelated project-owned fields remain preserved.
checked_summary_ja: agent profile のトップレベル model 項目だけを正規化し、複数行文字列や下位 table 内の同名文字列を保持する。

## Context

The profile updater must edit only top-level TOML model fields and preserve field-like text inside strings.

The current line-based matcher counts field-looking text inside a valid multiline TOML string as a duplicate top-level model field.

## Decisions

- Preserve formatting rather than serializing the complete TOML document.
- Use a TOML-aware lexical scan sufficient to distinguish top-level assignments from strings and tables.

## Tasks

- [x] Add failing coverage for basic and literal multiline strings plus nested tables.
- [x] Restrict replacement and duplicate detection to root-level TOML assignments.
- [x] Retain the existing atomic write and fixed-value checks.
- [x] Run the required validation commands.

## Validation Notes

- Accepted sandbox candidate `0a5a7fb937368d579e8cf9c12498467b9273f040fc9cf88df5b85520bdaf1aa5` after independent review-clone validation.
- `python3 tests/test-agent-model-profiles.py`: passed (12 tests).
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed with the fallback backend.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- No unresolved risks or deferred work remain for this plan.
