# Repair root logging CLI delegation paths

status: checked
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/plan/active/057-root-log-cli-paths.md
  - scripts/check-agent-log-manifest.py
  - scripts/context-compress.sh
  - scripts/import-codex-transcript.py
  - scripts/lint-project-workflow.sh
  - tests/test-hooks.py
context_files:
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - template/.project-agent-workflow/scripts/context-compress.sh
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
required_specs:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/import-codex-transcript.py --self-test
  - python3 scripts/check-agent-log-manifest.py --self-test
  - python3 tests/test-hooks.py
  - scripts/lint-project-workflow.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Root transcript import and manifest validation delegate to existing namespaced template implementations.
  - Root context compression records its output through the existing namespaced manifest helper.
  - Root CLI self-tests are part of the repository lint and fail when delegation paths drift.
  - Root documentation names the existing managed implementation paths.
checked_summary_ja: ルートの transcript、manifest、context compression CLI を現存する名前空間実装へ接続し、self-test を必須化する。

## Context

The root logging and compression CLIs must delegate to existing namespaced implementations.

Three root CLIs still reference the removed `template/scripts/` layout and fail after the namespaced template migration.

## Decisions

- Keep thin root delegates and use `template/.project-agent-workflow/scripts/` as the root repository's implementation source.
- Test the public root commands rather than only the template implementation.

## Tasks

- [x] Add failing root CLI runtime tests.
- [x] Update all three delegation paths and stale documentation paths.
- [x] Add root CLI self-tests to package lint.
- [x] Run the required validation commands.

## Validation Notes

- Accepted sandbox candidate `722840a4478002644a6ad516a4db620b3dcdce2a4f6c10ea81cc8d1309063fe3` after independent review-clone validation.
- Root transcript importer and manifest checker self-tests passed.
- `python3 tests/test-hooks.py`: passed (32 tests), including root compression manifest recording.
- `scripts/lint-project-workflow.sh`: passed with both root CLI self-tests enforced.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- No stale `template/scripts/` logging-helper path remains in the changed root docs, scripts, or test.
- No unresolved risks or deferred work remain for this plan.
