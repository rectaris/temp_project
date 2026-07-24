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

## Template Package Syntax Checks

- `python3 scripts/check-yaml.py .`: parses root and rendered YAML with the PyYAML version pinned in `uv.lock`.
- `scripts/install-actionlint.sh <temporary-directory>`: downloads actionlint 1.7.12 and verifies the release archive checksum.
- `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh <repository>`: validates GitHub Actions workflows and fails if the pinned actionlint is unavailable.

## Generated Selectors

Generated repositories may include:

- `scripts/validate-changes.py`: selects validation commands from staged or unstaged paths.
- `scripts/security-static-check.py`: scans common high-signal static risks.
- `scripts/skillspector-scan.sh`: optional NVIDIA SkillSpector wrapper for AI agent skill scans.
- `scripts/structure-map.py --check`: verifies basic agent workflow structure.
- `scripts/format-plan-docs.py --check`: verifies plan Markdown whitespace.
- Codex hook Python should compile with `python3 -m py_compile`.
- `.codex/config.toml` and `.codex/agents/*.toml` should parse as TOML.

These scripts provide a baseline. Project-specific builds, unit tests, browser tests, package audits, and domain contract checks should be added locally.
