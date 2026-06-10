# External Service Integration Docs

## Summary

Added practical documentation for optional MCP, Linear, and graph memory integration while keeping all external service dependency optional.

## Changes

- Expanded generated `SPEC_EXTERNAL_SERVICES.md` with setup checklists, credential boundaries, dry-run/read/write classifications, and fallback behavior.
- Added enabled-state guidance for MCP server metadata, Linear issue sync, and graph memory write review.
- Added disabled-state guidance that explains what must be documented before each service can become required.
- Added generated README guidance that points users to `docs/agent/SPEC_EXTERNAL_SERVICES.md`.
- Updated package README, skill guidance, orchestration reference, and Copier smoke/update tests.

## Validation

- `scripts/lint-project-workflow.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/smoke.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/copier-update.sh`
- `git diff --check`
