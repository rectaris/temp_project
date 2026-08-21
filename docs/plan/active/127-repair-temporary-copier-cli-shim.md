# Repair the temporary Copier CLI shim

status: in_progress
primary_invariant: keep Copier fixture dependency execution self-contained while preserving Git-tracked local template copy-to-update behavior
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: ordinary
write_scope:
  - tests/copier-update.sh
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/active/126-integrate-generated-verify-helper-compilation.md
  - pyproject.toml
  - tests/lib-copier.sh
  - uv.lock
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - git diff --check
validation:
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Before editing, use a repository-external temporary A/B reproduction to distinguish the current copied-project shim from a variant that keeps cache and environment writes temporary while restoring the original Git-root project context; stop for hard replan if the comparison does not isolate this one shim invariant.
  - Keep the uv cache, virtual environment, and every generated dependency artifact below the fixture temporary root, retain locked dependency resolution, and do not write the root `.venv`, `.uv-cache`, lockfile, ignored files, or either original repository.
  - Change only the temporary Copier launcher in `tests/copier-update.sh`; do not bypass Copier's Git-tracked-template check, weaken `_src_path` handling, or modify helpers, validators, validation allowlists, Plan 119 acceptance, safety conditions, or external-effect authority.
  - Pass the complete required-Copier fixture and finish with zero unresolved High or Medium independent-review findings before returning Plan 126 to a fresh execution run.
checked_summary_ja: 一時uv環境の書込分離を維持したまま、Git管理templateのCopier copyからupdateまでを再現可能にする。

## Decisions

- Treat the failed location as confirmed and the copied-project relocation cause as a hypothesis until the A/B reproduction distinguishes it.
- Use bounded parent implementation because the shim is embedded in the preserved uncommitted Plan 119 fixture; require independent read-only review before authoritative validation.
- If the repair needs another file, a new validation command, dependency changes, or weaker Git and repository-preservation checks, mark this plan `replan_required` instead of expanding it.
- After this plan is checked, revalidate Plan 126's unchanged boundaries and resume it with a fresh source HEAD, plan digest, lifecycle, and execution ledger.

## Tasks

- [ ] Reproduce the current failure and the bounded alternative in repository-external temporary fixtures.
- [ ] Apply a one-file shim repair only if the A/B result confirms the hypothesis.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative required-Copier fixture once, archive and commit this repair, then resume Plan 126 fresh.

## Validation Notes

- Plan 126's authoritative run stopped before the new direct helper lane and recorded one `independent_repair_required` invariant.
- Classification review fixed `tests/copier-update.sh` as the only write scope and left all source-plan, authority, invariant, acceptance, safety, and external-effect boundaries unchanged.
