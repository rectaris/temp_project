# Template Operations Hardening

## Summary

Added CI, hook behavior tests, Copier update regression coverage, and clearer GitHub/tag documentation for long-term template operation.

## Changes

- Added GitHub Actions CI for lint, smoke, hook tests, update tests, and whitespace checks.
- Added deterministic hook behavior tests.
- Added Copier update regression test from a tagged generated project to `HEAD`.
- Updated README guidance for GitHub installation, tags, updates, and validation.
- Localized generated README template to Japanese.

## Validation

- `scripts/lint-project-workflow.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/smoke.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/copier-update.sh`
- `git diff --check`
