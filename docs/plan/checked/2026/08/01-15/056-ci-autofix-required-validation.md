# Enforce required validation before CI autofix pushes

status: checked
task_types:
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .github/workflows/codex-ci-autofix.yml
  - docs/agent/CODEX_CI_AUTOFIX.md
  - docs/plan/active/056-ci-autofix-required-validation.md
  - scripts/check-copier-template.py
  - template/.github/workflows/codex-ci-autofix.yml.jinja
  - template/.project-agent-workflow/docs/agent/CODEX_CI_AUTOFIX.md
  - tests/smoke.sh
context_files:
  - .github/codex/prompts/ci-autofix.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/scripts/validate-changes.py
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
  - A `validate-patch` job with `contents: read` applies the artifact to the exact PR HEAD and must pass enforced repository validation before a write-capable job can start.
  - The root workflow runs the root repository's required lint and smoke checks in the read-only validation job after applying the patch.
  - The generated workflow runs the managed change-aware validator in the read-only validation job and stops when a configured validation command cannot run.
  - `validate-patch` exposes the patch SHA-256, and `apply-patch` refuses any downloaded artifact whose digest differs.
  - The `apply-patch` job runs only checkout/download, digest verification, `git apply --index`, hook-disabled commit creation, push, and the existing PR comment; it runs no dependency installer or repository script.
  - Patch-only mode continues to upload a reviewable artifact without granting branch write access to the generation job.
  - The workflow uses a trusted prompt source or rejects PR modifications to the prompt before Codex execution.
checked_summary_ja: CI 自動修正 patch を clean checkout で必須検証し、成功した場合だけ PR branch へ commit と push を行う。

## Context

The CI autofix workflow must enforce repository validation before any direct push.

The current workflow validates patch boundaries but does not deterministically run required repository checks before the write-capable job pushes the patch.

Required validation must not execute PR-controlled dependencies or repository scripts in a job that holds branch write permission.

## Decisions

- Keep patch generation read-only with respect to the branch.
- Add `validate-patch` after `generate-fix`; give it `actions: read` and `contents: read`, check out the exact prepared HEAD without persisted credentials, download the patch, apply it staged, and run required validation.
- Publish `sha256sum` of the validated patch as a `validate-patch` job output.
- Make `apply-patch` depend on `validate-patch`, download the same named artifact, and compare its digest before `git apply --index`.
- Keep `apply-patch` limited to trusted workflow commands and use `git -c core.hooksPath=/dev/null commit` before push.
- Do not claim credential isolation that official OpenAI documentation does not establish.
- Prevent PR-controlled prompt changes from becoming Codex instructions in the privileged workflow.

## Required Job Graph

1. `prepare` resolves the immutable PR HEAD and mode.
2. `generate-fix` produces and uploads a patch without branch write permission.
3. `validate-patch` runs only for direct-push with a patch, applies it to the same HEAD with read-only repository permission, runs root or generated validation, and outputs the patch SHA-256.
4. `apply-patch` starts only after `validate-patch` succeeds, verifies the SHA-256, applies the patch to the same HEAD, commits with hooks disabled, and pushes.
5. `patch-only-notice` remains independent of `validate-patch` and never grants branch write permission to generation.

## Tasks

- [x] Add deterministic assertions for the exact job graph, job permissions, immutable HEAD checkout, digest handoff, and hook-disabled commit.
- [x] Implement root and generated `validate-patch` jobs with their required validation commands.
- [x] Restrict root and generated `apply-patch` jobs to digest verification and trusted Git operations.
- [x] Keep patch-only behavior and attempt limits unchanged.
- [x] Use or verify trusted prompt content before Codex execution.
- [x] Align root and generated documentation with the enforced checks.
- [x] Run the required validation commands.

## Validation Notes

- Accepted sandbox candidate `e7027b9bc935f1b67a94e348d79024576b4cc230aa2a7e1924cdcf5b91700bcb` after independent review-clone validation.
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed with the fallback backend.
- `python3 scripts/check-yaml.py .`: passed for 29 YAML files.
- `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .`: passed with actionlint 1.7.12 installed outside the repository.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Root and generated job-graph, permission, digest, prompt-source, and write-job command-boundary checks passed.
- A live GitHub Actions execution remains operational verification, not an implementation blocker.
