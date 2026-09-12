# Optional Harness Profiles

## Purpose

Optional harness profiles pin supplemental instructions without changing governing policy, model routing, permissions, validation, or plan lifecycle.

The checker reads only explicit local files, performs no network access, writes no repository file, and never claims that a host loaded rendered instructions.

## Catalog And Selection

`docs/agent/harness-instructions.json` inventories governing sources and optional supplemental revisions.

Every governing source is bound to its repository-relative path and SHA-256 digest and cannot be selected as supplemental advice.

Every supplemental revision has a stable id, exact revision, content digest, applicability, introduction reason, failure-case references, review evidence, and an `active` or `retired` status.

Unclassified instructions remain governing.

`docs/agent/harness-profile.json` is project owned and starts with an empty selection.

Each selection binds one catalog id, revision, digest, and explicit project-local asset path.

Unknown, missing, changed, unsafe, or duplicate selections fail without fallback.

A retired revision remains reproducible for an existing selection and rollback, but cannot be newly adopted.

## Commands

Use `scripts/check-harness-profile.py check` to validate a catalog and selection.

Use `render` to emit only selected supplemental text and a manifest stating that runtime activation is not observed.

Use `check-adoption` to recompute the harness comparison report from its explicit inputs and verify an exact adoption or keep-current record.

A record digest binds the exact bytes of its input: `comparison_report_digest` is the SHA-256 of the recomputed `compare-harness-runs.py --format json` output, and each evidence digest is the SHA-256 of that evidence file.

A newly selected revision must carry catalog review evidence equal to those recomputed digests, so an unmeasured or changed revision cannot be adopted.

Use `check-rollback` to verify the exact prior selection.

Changed governing inputs produce `reassessment_required`; they never select a substitute revision.

No command rewrites the project selection.

## Copier Ownership

Copier creates the empty project-owned selection on the initial copy only.

Updates exclude that path, preserving an existing selection and leaving an intentionally missing selection absent.

The catalog, checker, and this policy are managed files.

Project-local supplemental assets and decision records remain project owned.
