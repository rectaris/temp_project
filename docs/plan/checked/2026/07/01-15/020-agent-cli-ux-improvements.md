# Improve agent-facing CLI UX

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - scripts/validate-changes.py
  - scripts/plan_validation_commands.py
  - template/scripts/validate-changes.py
  - template/scripts/search-plan-archive.py
  - template/scripts/workflow-status.sh
  - template/scripts/plan_validation_commands.py
  - template/scripts/check-agent-completion.sh
  - template/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/smoke.sh
target_json:
  - CLI JSON output contracts for validation, archive search, and workflow status.
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Agent-facing scripts keep existing human-readable defaults.
  - Selected scripts expose JSON output without changing default behavior.
  - Common failure paths include concise next-action guidance.
expected_output: full-implementation
checked_summary_ja: AIエージェント向けCLI出力とエラー誘導を改善した。

## Summary

Added explicit JSON modes for selected agent-facing lifecycle scripts while preserving default text output. Improved common validation and completion failure messages with next-action guidance.

## Decisions

- Preserve existing human-readable defaults; add explicit JSON modes instead of changing default output.
- Improve only common, local failure paths with next-action guidance.
- Do not expand `SKILL.md`; the existing split between the skill entrypoint and detailed docs remains correct.

## Completed Work

- Added `--json` to `scripts/validate-changes.py` and `template/scripts/validate-changes.py`.
- Added generated-project JSON modes for `scripts/search-plan-archive.py --text <term> --json` and `scripts/workflow-status.sh --json`.
- Allowlisted common JSON variants of `python3 scripts/validate-changes.py` in validation command parsing.
- Added `Next:` remediation guidance for validation command parsing errors and completion gate blockers.
- Documented machine-readable lifecycle commands in generated `SPEC_PLAN_WORKFLOW.md`.
- Added smoke coverage for JSON output parsing and the new completion guidance.

## Validation Notes

- `python3 scripts/validate-changes.py --all` passed.
- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
