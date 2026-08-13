# Address PR 2 validation and sandbox artifact findings

status: in_progress
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .github/workflows/codex-ci-autofix.yml
  - CHANGELOG.md
  - copier.yml
  - docs/agent/CODEX_CI_AUTOFIX.md
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.github/workflows/codex-ci-autofix.yml.jinja
  - template/.project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/copier-update.sh
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/046-sandboxed-plan-worker.md
  - docs/plan/checked/2026/08/01-15/056-ci-autofix-required-validation.md
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja
  - template/.project-agent-workflow/scripts/validate-changes.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
validation:
  - python3 -m pytest tests/test-sandboxed-plan-worker.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Fail closed in both this repository's CI autofix workflow and every generated workflow by using patch-only behavior until an isolated, immutable validation contract exists that candidate code cannot rewrite directly or indirectly.
  - Remove the manual direct-push input, validation-to-write job graph, branch write permission, patch commit, push, and automated PR comment from the generated workflow; keep patch generation read-only and artifact-only.
  - Preserve the Copier `direct_push` answer value for non-destructive update compatibility, but label and document that it currently falls back to patch-only without external writes.
  - Add deterministic root-workflow, template, and rendered-project fixtures proving that a stored `direct_push` answer still renders only patch-only mode and that no root or generated job has repository write permission, pushes a branch, comments on a PR, or applies a candidate patch in a write-capable job.
  - Reject any tracked, staged, or non-ignored untracked change produced by dependency setup before Codex runs, so the uploaded artifact has an auditable Codex-only provenance; exercise the rejection with an executable installer-mutation fixture.
  - Remove the obsolete commit-count `max_attempts` input, outputs, and guard because artifact-only runs do not create commits and therefore cannot use commit subjects as an artifact-attempt counter.
  - Prove non-destructive Copier update from an earlier `direct_push` answer: keep the stored answer, replace the old write graph with artifact-only behavior, and leave no rejection files, conflicts, or unrelated deletion.
  - Reject every job-level or workflow-level `write` permission generically rather than enumerating only contents and pull requests.
  - Keep the root and generated CI autofix documentation accurate for their patch-only behavior, with no stale instructions for direct-push mode, validate-patch, apply-patch, generated commits, or manual mode selection.
  - Resolve the source Git object directory through Git rather than assuming .git/objects, use a temporary object directory while deriving changed paths, and expose the source object directory only as an alternate for base-object reads.
  - Encode each alternate object path with Git-compatible C-style quoting so a legal colon or non-ASCII byte cannot become an alternate-list separator.
  - Resolve the source object directory under the same sanitized Git environment used by temporary-index operations, ignoring ambient `GIT_*` overrides, and cover that condition deterministically.
  - Prove that successful path derivation, manifest generation without apply, and rejected apply preflight do not add a unique candidate blob to the source object database, including repositories under a colon-containing path, linked worktrees using a common object directory, and a source object database with an existing alternate.
  - Preserve existing changed-path semantics, accepted patch application, source worktree cleanliness, exact write-scope enforcement, and root/template runner byte parity.
  - Record both review corrections under the unreleased changelog without moving or rewriting v1.3.0.
checked_summary_ja: CI 自動修正の必須 build/test 検証と候補 patch の一時 object 隔離を追加し、PR #2 の未解決指摘を修正した。

## Context

PR 2 has two unresolved review threads at reviewed commit `c80629a560`.

The generated direct-push workflow applies a patch and runs only change-aware managed checks before a write-capable job pushes it. A staged TypeScript application fixture selected whitespace and managed Python compilation but did not select the declared package build or tests.

The sandboxed runner directs only its index to a temporary path while `git apply --cached` still writes candidate blobs to the source Git object database. An isolated reproduction confirmed that a unique candidate blob was absent before path derivation and present afterward.

## Decisions

- Treat both review findings as valid.
- Do not execute candidate-controlled build or test code as a prerequisite to an automatic repository write in the current generic GitHub runner. Fixed command names are insufficient because candidate source can rewrite indirect runners, Git metadata, and GitHub command files.
- Preserve the existing `direct_push` Copier answer for update compatibility, but use artifact-only patch behavior in both the root and rendered workflows and remove every write-capable autofix path until a separately isolated and immutable validation contract is designed.
- Preserve Git's patch and path semantics by isolating object writes with `GIT_OBJECT_DIRECTORY` and reading base objects through `GIT_ALTERNATE_OBJECT_DIRECTORIES`.
- Keep the published v1.3.0 tag immutable and apply these corrections only to dev and PR 2.

## Tasks

- [ ] Disable generated direct-push and retain patch-only artifact output.
- [ ] Isolate candidate object writes during changed-path derivation.
- [ ] Add deterministic regression coverage for both findings.
- [ ] Run every required validation command and record results.
- [ ] Archive and commit the accepted correction before updating PR 2.

## Validation Notes

- Pending implementation.
- Rejected candidate `/tmp/sandboxed-plan-worker-output-kiaFUi/manifest.json`, source HEAD `2b83d73f0e9489fc191b82af8ed4eb8b29c54db2`. GPT-5.3-Codex-Spark medium returned bounded `usage_limit`; GPT-5.6-Luna max generated the candidate in a fresh isolated attempt.
- Parent review-clone validation passed 34 runner tests, runner self-test, template static checks, workflow lint, and smoke, but read-only security review found three acceptance failures: candidate-controlled validation definitions could still bypass build/test, the uv test interpreter did not use the synced environment, and an unquoted colon in an alternate object path broke legal repository paths. The patch was not applied.
- Rejected candidate `/tmp/sandboxed-plan-worker-output-f137XK/manifest.json`, source HEAD `6f743e7a3c847b6bf9360b1daf8fab6491961b66`. GPT-5.3-Codex-Spark medium returned bounded `usage_limit`; GPT-5.6-Luna max generated the candidate in a fresh isolated attempt.
- Parent review-clone validation passed 35 runner tests, runner self-test, template static checks, workflow lint with the pinned local actionlint binary, smoke, full managed validation, and diff checks. Read-only security review nevertheless found that indirect validation runners and GitHub command files remained candidate-controlled, the required executable negative fixtures were absent, and Python dependency installation downgraded after a declared dev-extra failure. The patch was not applied.
- Rejected candidate `/tmp/sandboxed-plan-worker-output-third-ohMrEE/manifest.json`, source HEAD `1cc3beda169596efa84f0b645f057be0b40b466b`. GPT-5.3-Codex-Spark medium returned bounded `usage_limit`; GPT-5.6-Luna max generated the candidate in a fresh isolated attempt.
- Parent review-clone validation passed 34 runner tests, runner self-test, template static checks, workflow lint, smoke, full managed validation, and diff checks. Parent inspection found that the candidate removed writes only from the template while the root workflow retained direct-push; its partial root documentation update then contradicted the still-active root jobs. The patch was not applied.
- Independent review of that rejected candidate also found that dependency setup could contaminate the patch artifact, the old commit-count attempt guard no longer represented artifact attempts, update compatibility lacked an executable prior-`direct_push` fixture, permission checks were not generic, and object-directory resolution did not sanitize ambient Git overrides. These findings are accepted into the final fail-closed scope.
