# Copier Adoption

## Purpose

This spec defines how a mature repository should adopt this template without losing stronger project-local rules.

## Layering Model

- Copier-managed files provide the generic workflow entrypoint, reusable scripts, common Codex helper configuration, and baseline policy docs.
- Project-specific specs hold domain rules, deployment facts, data contracts, external-service identifiers, and stronger local lifecycle behavior.
- If project-specific rules are stricter or more concrete than the generic template, keep the project-specific rule and document the boundary here or in the matching `SPEC_*.md` file.
- Do not store project-specific facts only in `AGENTS.md`; keep them in routed `docs/agent/SPEC_*.md` files so the root entrypoint can remain updateable.

## Initial Adoption Protocol

For a repository that already has agent policy files:

1. Render the template into a temporary directory first.
2. Diff generated files against the target repository.
3. Copy new generic files directly when they do not conflict.
4. Manually merge same-path files that already contain project-specific rules.
5. Preserve or create `.copier-answers.yml` so future updates have a stable source.
6. Keep a project-specific adoption spec listing protected local files and merge rules.
7. Run repository-local validation before committing.

Do not run a direct overwrite copy into a mature repository unless the same-path files have already been made intentionally replaceable.

## Conflict Handling

Copier may report a conflict by placing conflict markers inside a managed file or by creating a `*.rej` file.
Treat both forms as unresolved changes.

Before committing an adoption or update:

1. Run `python3 scripts/migrate-legacy-template-files.py` after `copier update`.
2. If the migration helper reports a conflict, keep the modified legacy file and review it manually.
3. Search changed files for `<<<<<<<`, `=======`, and `>>>>>>>` markers.
4. Inspect every `*.rej` file and compare it with the destination file.
5. Preserve stronger project-owned rules and protected files while merging generic template changes.
6. Remove a reject file only after its useful content has been merged or explicitly declined.
7. Run `git diff --check` and the repository validation matrix.

For direct adoption into a mature repository, render into a temporary directory, review a recursive diff against the repository, and copy or merge only accepted paths.
Do not use a force-copy command as a substitute for this review.

Existing open plans are project-owned and are not rewritten by Copier or the legacy-file migration helper.
When adopting the current plan schema, manually replace `task_type` with a `task_types` list, split `target_files` into non-overlapping `write_scope` and `context_files` lists, remove `expected_output`, and include the required-spec union for every listed route.

## Merge Boundaries

Treat these paths as generic by default:

- `.codex/agents/*.toml`
- `.codex/hooks/*.py`
- `.github/codex/prompts/*.md`
- baseline `docs/agent/SPEC_*.md` files from this template
- `scripts/` workflow helpers

Treat these paths as project-specific unless the project says otherwise:

- `docs/agent/PROJECT_ENVIRONMENT.md`
- `docs/agent/PROJECT_UI_DESIGN.md`
- product, domain, data-contract, deployment, or runtime specs
- external-service connection identifiers and write policy
- project-specific Codex skills
- repository-specific validation adapters
- active and checked plan history

## External Services

Generated external-service state is documentation-only by default. A project may enable read or write behavior only by filling `docs/agent/external-services.yaml` and adding any required project-specific spec or adapter.

`documented` does not authorize external reads or writes.

## Validation

- Docs-only adoption planning: `git diff --check`.
- Plan or spec-index edits: add plan formatting and linting.
- Script, hook, CI, or validation-adapter edits: run the repository validation matrix for those files.
