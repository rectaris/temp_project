# Extended Generic Rules

## Summary

Added the remaining generic workflow candidates from `supportcard-status` while keeping external-service dependent behavior optional.

## Changes

- Added generated human-facing plan README files and optional helper prompt/custom-agent notes.
- Added local-only lifecycle helpers for plan context selection, handoff cleanup, and shell wrapper entrypoints.
- Expanded active/backlog manifest metadata for review class, human approval, structured context, expected output, acceptance focus, and Japanese checked summaries.
- Added validation guidance and change-aware checks for plan formatting and Codex hook/config parsing.
- Updated Copier static, smoke, and update tests so new generated files are required and update-safe.

## Validation

- `scripts/lint-project-workflow.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/smoke.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/copier-update.sh`
- `git diff --check`
