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
  - A direct-push patch is applied to a clean checkout and must pass enforced repository validation before commit and push.
  - The root workflow runs the root repository's required lint and smoke checks after applying the patch.
  - The generated workflow runs the managed change-aware validator and stops when a configured validation command cannot run.
  - Patch-only mode continues to upload a reviewable artifact without granting branch write access to the generation job.
  - The workflow uses a trusted prompt source or rejects PR modifications to the prompt before Codex execution.
checked_summary_ja: CI 自動修正 patch を clean checkout で必須検証し、成功した場合だけ PR branch へ commit と push を行う。

## Context

The CI autofix workflow must enforce repository validation before any direct push.

The current workflow validates patch boundaries but does not deterministically run required repository checks before the write-capable job pushes the patch.

## Decisions

- Keep patch generation read-only with respect to the branch.
- Move enforced validation into the clean apply job after `git apply --index` and before commit.
- Do not claim credential isolation that official OpenAI documentation does not establish.
- Prevent PR-controlled prompt changes from becoming Codex instructions in the privileged workflow.

## Tasks

- [ ] Add deterministic workflow assertions for validation-before-commit ordering.
- [ ] Apply the patch in the write-capable job and run root or generated required validation before commit.
- [ ] Keep patch-only behavior and attempt limits unchanged.
- [ ] Use or verify trusted prompt content before Codex execution.
- [ ] Align root and generated documentation with the enforced checks.
- [ ] Run the required validation commands.

## Validation Notes

- Pending.
