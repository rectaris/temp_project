# Separate the helper-specific Copier target fixture

status: replanned
replan_reason_codes:
  - spec_drift
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
  - In `tests/copier-update.sh`, create one dedicated committed target clone for the verification helper, set the sibling-relative `_src_path` only in that clone, and leave the existing target unchanged for its later ordinary update; do not modify the launcher, helpers, validators, validation allowlists, Plan 119 acceptance, safety conditions, or external-effect authority.
  - Pass the complete required-Copier fixture and finish with zero unresolved High or Medium independent-review findings before returning Plan 126 to a fresh execution run.
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/127-repair-temporary-copier-cli-shim.md
replan_contract: docs/plan/replanned/contracts/127-repair-temporary-copier-cli-shim.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/128-create-dedicated-copier-verification-target.md
  - docs/plan/active/129-integrate-dedicated-copier-verification-target.md
inherited_acceptance_digests:
  - sha256:19f10740345a851660c9252d126b8993c147ec88bd4dd978f6368a0d94edeb97
  - sha256:23927a40b08493abd3e56b029f315358cc2ac2ef3cfad2e794c30647141f0e17
  - sha256:3df8b90dc12615e26c1a311aee943650fe2be5649b99c36b389bd70720a054f2
  - sha256:8fadf3cf17624de7fb55099e7414f5b81170a3bf4482bb202d3d08aa48841f25
checked_summary_ja: 一時uv環境の書込分離を維持したまま、Git管理templateのCopier copyからupdateまでを再現可能にする。

## Decisions

- The user explicitly authorized replacing the launcher-only acceptance item with the dedicated committed target-clone design on 2026-08-21.
- Keep the existing target unchanged for later ordinary update and apply the sibling-relative `_src_path` only to the helper-specific clone.
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
- A minimal local-template A/B reproduction passed with both project contexts and did not isolate the shim hypothesis.
- A repository-external reproduction of the exact first existing fixture copy-to-update segment also passed with both project contexts.
- The authoritative failure therefore occurred after that segment; the remaining command order identifies reuse of the helper-specific relative `_src_path` in a later ordinary update as the next concrete referent.
- The user approved replacing the disproven launcher-only acceptance item with the helper-specific committed target clone.
- Stopped execution evidence: `/tmp/plan127-execution.T9Y8UD/execution.json`.
