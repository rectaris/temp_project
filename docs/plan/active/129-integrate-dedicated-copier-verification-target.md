# Integrate the dedicated Copier verification target

status: in_progress
primary_invariant: prove the dedicated helper target and preserved Plan 119 candidate through the complete required-Copier fixture
replan_source: docs/plan/active/127-repair-temporary-copier-cli-shim.md
replan_contract: docs/plan/replanned/contracts/127-repair-temporary-copier-cli-shim.json
integration_gates:
  - Plan 128 must be checked before the complete required-Copier fixture runs.
  - Plan 126 resumes only after this plan is checked with zero unresolved High or Medium findings.
successor_plans:
  - docs/plan/active/128-create-dedicated-copier-verification-target.md
  - docs/plan/active/129-integrate-dedicated-copier-verification-target.md
inherited_acceptance_digests:
  - sha256:19f10740345a851660c9252d126b8993c147ec88bd4dd978f6368a0d94edeb97
  - sha256:23927a40b08493abd3e56b029f315358cc2ac2ef3cfad2e794c30647141f0e17
  - sha256:3df8b90dc12615e26c1a311aee943650fe2be5649b99c36b389bd70720a054f2
  - sha256:8fadf3cf17624de7fb55099e7414f5b81170a3bf4482bb202d3d08aa48841f25

task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - tests/copier-update.sh
  - tests/smoke.sh
  - .codex/skills/verify-copier-update/
  - template/.agents/skills/verify-copier-update/
  - template/.project-agent-workflow/skills/verify-copier-update/
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/active/126-integrate-generated-verify-helper-compilation.md
  - docs/plan/active/128-create-dedicated-copier-verification-target.md
  - docs/plan/replanned/2026/08/16-31/127-repair-temporary-copier-cli-shim.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-verify-copier-update.py
  - python3 scripts/check-copier-template.py
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
checked_summary_ja: helper専用targetを実Copier fixtureへ統合し、元repositoryと既存更新targetの不変性を確認する。

## Decisions

- Treat Plan 128 as the only product edit and use this plan as its complete behavioral integration gate.
- Require the existing target to remain unchanged before its ordinary update and the dedicated helper target to reach verified through direct_supported_v1.
- Preserve temporary cache and environment isolation, locked dependencies, helper safety, validation authority, and Plan 119 acceptance.
- Require independent read-only review before the one authoritative required-Copier run.

## Tasks

- [ ] Confirm Plan 128 is checked and inspect the combined preserved candidate.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the complete required-Copier fixture once and require success.
- [ ] Archive and commit this integration, then resume Plan 126 with a fresh execution identity.

## Validation Notes

- Plan 127 A/B evidence disproved the launcher hypothesis and the user approved dedicated target separation.
