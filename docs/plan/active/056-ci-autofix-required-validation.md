# Enforce required validation before CI autofix pushes

status: in_progress
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
  - A direct-push patch is applied to a clean checkout with read-only repository permissions and must pass enforced repository validation before a write-capable job can start.
  - The root workflow runs the root repository's required lint and smoke checks in the read-only validation job after applying the patch.
  - The generated workflow runs the managed change-aware validator in the read-only validation job and stops when a configured validation command cannot run.
  - The write-capable job verifies the validated patch digest and runs no dependency installer, repository validation script, or other PR-controlled executable code before commit and push.
  - Patch-only mode continues to upload a reviewable artifact without granting branch write access to the generation job.
  - The workflow uses a trusted prompt source or rejects PR modifications to the prompt before Codex execution.
checked_summary_ja: CI 自動修正 patch を clean checkout で必須検証し、成功した場合だけ PR branch へ commit と push を行う。

## Context

The CI autofix workflow must enforce repository validation before any direct push.

The current workflow validates patch boundaries but does not deterministically run required repository checks before the write-capable job pushes the patch.

Required validation must not execute PR-controlled dependencies or repository scripts in a job that holds branch write permission.

## Decisions

- Keep patch generation read-only with respect to the branch.
- Run enforced validation in a separate clean-checkout job with `contents: read` after `git apply --index`.
- Pass the validated patch SHA-256 to the write-capable job and require an exact digest match before applying it.
- Keep the write-capable job limited to patch application, hook-disabled commit creation, and push; do not execute PR-controlled dependencies or repository scripts there.
- Do not claim credential isolation that official OpenAI documentation does not establish.
- Prevent PR-controlled prompt changes from becoming Codex instructions in the privileged workflow.

## Tasks

- [ ] Add deterministic workflow assertions for read-only validation, digest handoff, and validation-before-write ordering.
- [ ] Apply and validate the patch in a read-only job using root or generated required validation.
- [ ] Verify the validated patch digest in the write-capable job, then apply, commit with repository hooks disabled, and push without executing repository code.
- [ ] Keep patch-only behavior and attempt limits unchanged.
- [ ] Use or verify trusted prompt content before Codex execution.
- [ ] Align root and generated documentation with the enforced checks.
- [ ] Run the required validation commands.

## Validation Notes

- Rejected sandbox candidate `0fa19a0a85edb07af1bd00fa0204d49e3be2ec571cdffd915354fff2af3bc133`: it ran PR-controlled dependency installation and repository validation scripts inside the job holding `contents: write`.
- Implementation remains pending with the revised read-only validation and digest-handoff boundary.
