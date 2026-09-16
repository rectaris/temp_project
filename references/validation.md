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

## Pinned Python Correctness Checks

Run `uv sync --locked` to install the root development environment, then
`uv run --locked python -I scripts/lint-python.py`.
`uv sync` does not activate the shell's Python environment. Run the required
root checks in that same environment with
`uv run --locked scripts/lint-project-workflow.sh` and
`uv run --locked tests/smoke.sh`; run the update suite with
`uv run --locked tests/copier-update.sh --require-copier`.
Alternatively, activate `.venv` with `. .venv/bin/activate` before invoking the
bare validation commands. The wrappers deliberately use the caller's Python
environment rather than selecting or installing another one.
The required root lint and change-aware selector run the same check.
Ruff 0.15.7 checks Python files under `scripts/`, `tests/` and
`template/.project-agent-workflow/scripts/`, excluding dependency/cache directories.
The explicit rules are `E9,F541,F631,F634,F821,F822,F823`, with preview disabled.
These rules detect selected I/O, assertion, condition and name errors; they are
not full bug coverage or type checking.

Check mode never fixes files or writes a Ruff cache.
The wrapper removes Ruff-specific environment overrides (`RUFF_*`), including
`RUFF_OUTPUT_FILE`, so Ruff diagnostics go to stdout rather than creating or
overwriting another file. Other caller environment settings are retained.
Missing tools, another Ruff version, altered managed settings, empty scope and
symlinked targets fail rather than silently skipping checks.
Every required caller launches the wrapper with `-I`. Interpreter startup runs
before the wrapper selects Ruff, so a `sitecustomize` module on an inherited
`PYTHONPATH` could otherwise exit successfully and leave the lint check green
without any file being checked. Isolated mode costs nothing here because the
wrapper imports only the standard library.
The dedicated `tools/python-quality/ruff.toml` is used instead of product settings
or nested project configuration.

Automatic fixes require a live task-bound worktree and explicit file operands:
`uv run python -I scripts/lint-python.py --fix scripts/example.py`.
Only safe `F541` fixes are allowed; unsafe fixes and other rules remain disabled
for automatic repair.
Every operand is admitted before Ruff writes, and a directory, duplicate,
out-of-scope path, symlink or hard-linked file refuses the whole request.
The caller still owns the task's per-file authority; the guard proves worktree
ownership, not a direct task's write scope.
Validation manifests admit only the isolated no-argument check: never `--fix`,
and never a launch that omits `-I`.

Generated projects install the pinned requirements from
`.project-agent-workflow/tools/python-quality/requirements.txt` explicitly in CI
and run `python3 -I .project-agent-workflow/scripts/lint-python.py`.
Their lint scope contains only `.project-agent-workflow/scripts/`; product code,
dependencies and project-owned configuration are not adopted or overwritten.

## Template Package Syntax Checks

- `python3 scripts/check-yaml.py .`: parses root and rendered YAML with the PyYAML version pinned in `uv.lock`.
- `scripts/install-actionlint.sh <temporary-directory>`: downloads actionlint 1.7.12 and verifies the release archive checksum.
- `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh <repository>`: validates GitHub Actions workflows and fails if the pinned actionlint is unavailable.

## Generated Selectors

Generated repositories may include:

- `.project-agent-workflow/scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.
- `.project-agent-workflow/scripts/security-static-check.py`: scans common high-signal static risks.
- `.project-agent-workflow/scripts/skillspector-scan.sh`: optional NVIDIA SkillSpector wrapper for AI agent skill scans.
- `.project-agent-workflow/scripts/structure-map.py --check`: verifies basic agent workflow structure.
- `.project-agent-workflow/scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.
- Codex hook Python should compile with `python3 -m py_compile`.
- `.codex/config.toml` and `.codex/agents/*.toml` should parse as TOML.

These scripts provide a baseline. Project-specific builds, unit tests, browser tests, package audits, and domain contract checks should be added locally.
