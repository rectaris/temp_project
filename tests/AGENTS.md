# Test Sources

This file adds directory-local guidance to the repository root `AGENTS.md`.

## Layout

- Keep aggregate commands and independently executed integration tests in `tests/`.
- Put imported Hook test domains under `tests/hooks/`.
- Put imported validation-tool test domains under `tests/validation_tools/`.
- Keep test input data under `tests/fixtures/` and shared Copier shell helpers in `tests/lib-copier.sh`.

## Routing

- Change Hook fixtures and repository paths in `hooks/support.py`.
- Change one Hook behavior domain in the matching module under `hooks/`.
- Change validation-tool fixtures and module loading in `validation_tools/support.py`.
- Change one validation behavior domain in the matching module under `validation_tools/`.
- Import each test class exactly once from its aggregate entrypoint.
- Avoid `test*.py` names for imported domain modules so generic discovery does not duplicate aggregate tests.

## Validation

- Run `python3 tests/test-hooks.py` after a Hook test change.
- Run `python3 tests/test-validation-tools.py` after a validation-tool test change.
- Run the repository-required lint and smoke suites after focused tests pass.
