# Generic Rule Modules

## Summary

Added generic workflow modules derived from `supportcard-status` while keeping external-service integrations optional.

## Changes

- Added Copier options for plan lifecycle, change-aware validation, static security checks, structure scanning, MCP policy, Linear sync policy, and graph-memory policy.
- Expanded generated agent specs for file management, plan lifecycle, validation selection, orchestration, and external-service side-effect boundaries.
- Added generated local-only scripts for plan creation, promotion, completion, archive search, plan lint/format, completion gating, validation selection, static security checks, and structure scanning.
- Extended static, smoke, hook, and Copier update tests to cover the new generated modules.
- Updated package references and README with core/optional module guidance.

## Validation

- `scripts/lint-project-workflow.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/smoke.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/copier-update.sh`
- `git diff --check`
