# Validation

## Baseline

- Validate every non-trivial change.
- Choose the smallest complete command set for the files changed.
- Record commands that could not run and why.

## Matrix

- Docs-only: `git diff --check`.
- Shell scripts: `sh -n <script>` and a smoke run when possible.
- Python scripts: `python3 -m py_compile <files>` and tests when available.
- JavaScript/TypeScript: project build, unit tests, and lint when available.
- Agent workflow docs or hooks: structure lint plus syntax checks.

## Completion

Before final report:

1. Run required validation.
2. Inspect `git status --short`.
3. Commit coherent changes unless the user requested otherwise.
4. Report touched repositories, link changes, validation, and commit hash.

