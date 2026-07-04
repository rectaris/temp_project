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

## Merge Boundaries

Treat these paths as generic by default:

- `.codex/agents/*.toml`
- `.codex/hooks/*.py`
- `.github/codex/prompts/*.md`
- baseline `docs/agent/SPEC_*.md` files from this template
- `scripts/` workflow helpers

Treat these paths as project-specific unless the project says otherwise:

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
