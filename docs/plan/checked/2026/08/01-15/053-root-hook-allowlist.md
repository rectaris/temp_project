# Restrict the root Hook log to allowlisted metadata

status: checked
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .project-agent-workflow/hooks/agent_log_event.py
  - docs/plan/active/053-root-hook-allowlist.md
  - scripts/check-copier-template.py
  - tests/test-hooks.py
context_files:
  - .codex/hooks.json
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/hooks/agent_log_event.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
required_specs:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-hooks.py
  - scripts/lint-project-workflow.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The implementation invoked by root `.codex/hooks.json` persists only allowlisted operational metadata.
  - Prompt text, tool input, tool output, response content, and arbitrary payload fields are not written to root Hook event logs.
  - Root and generated Hook behavior share one maintained implementation or an enforced semantic parity check.
  - A regression test exercises the implementation reached through the root Hook path.
checked_summary_ja: ルートで実配線された Hook ログを許可済みメタデータだけに制限し、prompt と tool 内容の保存を防ぐ。

## Context

The root Hook implementation wired by .codex/hooks.json must persist only allowlisted metadata.

The root Hook path currently uses an older implementation that records the complete Hook payload, while the generated template implementation already filters operational metadata.

## Decisions

- Reuse the safe generated implementation or enforce equivalent behavior instead of maintaining divergent payload filters.
- Keep automatic redaction marked as pending review.
- Do not change transcript import behavior in this plan.

## Tasks

- [x] Add a regression test that reaches the root-wired implementation and proves arbitrary payload content is excluded.
- [x] Replace or synchronize the root implementation with the allowlisted implementation.
- [x] Add deterministic root/template drift coverage for the logging Hook.
- [x] Run the required validation commands.

## Validation Notes

- `python3 tests/test-hooks.py` passed with 30 tests.
- `scripts/lint-project-workflow.sh` passed, including the root/template Hook parity check.
- `python3 scripts/validate-changes.py --all` passed for all changed Python paths.
- `git diff --check` passed.
- Main-session review accepted the worker diff because it excludes arbitrary payload content through the root-wired implementation and adds direct runtime coverage without touching later plans.
