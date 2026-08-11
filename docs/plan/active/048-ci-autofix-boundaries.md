# Harden root CI autofix artifact and write boundaries

status: in_progress
task_types:
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .github/workflows/codex-ci-autofix.yml
  - docs/plan/
  - scripts/check-copier-template.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_SECURITY.md
  - template/.github/workflows/codex-ci-autofix.yml.jinja
  - tests/smoke.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/check-yaml.py .
  - REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Keep the rendered prompt, Codex output, and patch outside the Git worktree so internal run artifacts cannot enter the proposed change or make has_patch true by themselves.
  - Generate and apply the patch against the pull-request head SHA captured by the prepare job, and let a concurrent branch update stop the push rather than applying the patch to a newer revision.
  - Reject whitespace failures, static-security findings, protected-path changes, and deleted tests before uploading a write-capable patch artifact or writing to the pull-request branch.
  - Preserve the existing direct-push, patch-only, attempt-limit, same-repository, and pull-request notification behavior.
  - Add deterministic checks that fail when the root workflow loses these boundaries.
checked_summary_ja: ルート CI 自動修正の一時成果物、対象 SHA、保護パス検査を固定し、検査前の PR branch 書き込みを防止する。

## Context

The root CI autofix workflow must keep generated artifacts outside the Git worktree and validate the patch before writing to a pull-request branch.

The generated workflow template already implements the intended controls, while the root workflow still creates the prompt and output in the checkout, diffs untracked checkout files, and checks out a movable branch name.

## Decisions

- Change only the root workflow because the generated workflow template already contains the intended controls.
- Use `needs.prepare.outputs.head_sha` for both patch generation and patch application.
- Store the prompt, Codex output, and patch below `runner.temp`.
- Run `python3 template/.project-agent-workflow/scripts/security-static-check.py --changed` from the root checkout, followed by explicit protected-path and deleted-test checks, before patch upload.
- Extend the existing deterministic template checker instead of introducing a second workflow checker.

## Tasks

- [ ] Add root-workflow regression assertions for exact-SHA checkout, temporary artifact paths, boundary validation, protected paths, and test-deletion rejection.
- [ ] Port the established generated-workflow controls into the root workflow with the root repository's available security-checker path.
- [ ] Confirm that every boundary failure prevents patch upload and the write-capable apply job.
- [ ] Run required workflow and repository validation.

## Validation Notes

Pending implementation.
