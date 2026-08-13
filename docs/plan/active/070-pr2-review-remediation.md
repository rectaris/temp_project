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
  - CHANGELOG.md
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.github/workflows/codex-ci-autofix.yml.jinja
  - template/.project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
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
  - Keep generated CI autofix patch generation and validation jobs read-only and keep branch credentials out of every dependency installer, project build, and test process.
  - In generated direct-push mode, install declared Python and Node dependencies in validate-patch after applying the exact digest-bound patch, then run change-aware validation as a floor plus the trusted primary-language validation commands rendered by Copier.
  - For TypeScript, require both npm run build and npm run test; for Python, require python3 -m pytest; for mixed projects, require all three. Missing commands, missing dependencies, or failed validation must stop before apply-patch.
  - Treat dependency manifests, lockfiles, test sources, test-runner configuration, package build/test definitions, and other validation-contract paths as protected direct-push inputs; reject an autofix patch that changes one instead of executing candidate-controlled validation definitions.
  - Use a non-mutating locked dependency operation when a lockfile exists, run Python tests through the same environment populated by the installer, and fail if dependency setup or validation changes tracked files.
  - After required validation, reproduce the staged candidate diff and require its SHA-256 to match the downloaded artifact before publishing the digest used by apply-patch.
  - Keep apply-patch limited to checkout, artifact download, digest verification, patch application, hook-disabled commit, push, and the existing PR comment.
  - Add deterministic template and rendered-project fixtures proving that setup, dependency installation, and required build/test commands occur only in the read-only validation job, failed build/test blocks apply-patch, candidate changes to validation-contract paths are rejected, and tracked-state mutation fails the digest check.
  - Resolve the source Git object directory through Git rather than assuming .git/objects, use a temporary object directory while deriving changed paths, and expose the source object directory only as an alternate for base-object reads.
  - Encode each alternate object path with Git-compatible C-style quoting so a legal colon or non-ASCII byte cannot become an alternate-list separator.
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
- Render a fixed trusted full-validation set from Copier's `primary_language` instead of trusting validation commands or package-script selection introduced by the candidate patch.
- Reject direct-push candidates that modify the trusted dependency, build, test, or validation definitions consumed by that fixed validation set.
- Keep managed change-aware validation as an additional floor rather than replacing it.
- Duplicate dependency setup in the read-only validation job; do not move any installer or repository test into the write-capable apply job.
- Preserve Git's patch and path semantics by isolating object writes with `GIT_OBJECT_DIRECTORY` and reading base objects through `GIT_ALTERNATE_OBJECT_DIRECTORIES`.
- Keep the published v1.3.0 tag immutable and apply these corrections only to dev and PR 2.

## Tasks

- [ ] Enforce primary-language build and test validation before generated direct-push.
- [ ] Isolate candidate object writes during changed-path derivation.
- [ ] Add deterministic regression coverage for both findings.
- [ ] Run every required validation command and record results.
- [ ] Archive and commit the accepted correction before updating PR 2.

## Validation Notes

- Pending implementation.
- Rejected candidate `/tmp/sandboxed-plan-worker-output-kiaFUi/manifest.json`, source HEAD `2b83d73f0e9489fc191b82af8ed4eb8b29c54db2`. GPT-5.3-Codex-Spark medium returned bounded `usage_limit`; GPT-5.6-Luna max generated the candidate in a fresh isolated attempt.
- Parent review-clone validation passed 34 runner tests, runner self-test, template static checks, workflow lint, and smoke, but read-only security review found three acceptance failures: candidate-controlled validation definitions could still bypass build/test, the uv test interpreter did not use the synced environment, and an unquoted colon in an alternate object path broke legal repository paths. The patch was not applied.
