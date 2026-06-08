# Validation Selection

Validation must match the files changed and the behavior at risk.

## Baseline

- Docs-only: `git diff --check`.
- Shell scripts: `sh -n <script>` plus a smoke run when possible.
- Python hooks/scripts: `python3 -m py_compile <files>`.
- TypeScript/JavaScript app code: project build, unit tests, and lint if available.
- Data contracts: schema or contract checks plus targeted tests.
- Agent routing or planning docs: structure lint plus `git diff --check`.

## Completion

Before reporting completion:

1. Confirm required validation passed or record why it could not run.
2. Check `git status --short`.
3. Commit coherent changes unless the user requested otherwise.
4. Report touched repositories and link changes.

## Principle

Prefer checks that prove the rule directly. Do not use a green broad command as evidence unless it covers the changed behavior.

