# Release v1.4.7 so downstream projects receive the improvement-to-direction flow

status: in_progress
primary_invariant: The repository never presents a fixed stable template version that disagrees with the newest released version recorded in the change log.
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"scripts/check-copier-template.py already carries require_documented_release_version(), which derives the expected version from the newest dated CHANGELOG heading and refuses a disagreeing README --vcs-ref pin. scripts/lint-project-workflow.sh already runs it, so this release needs no new validation authority.","kind":"existing_mechanism"}
  - {"evidence":"The v1.4.6 release dated the accumulated 未リリース section, left an empty one behind, and rewrote the three README fixed-version pins. This release repeats that exact transformation for v1.4.7.","kind":"mechanical_transformation"}
completion_conditions:
  - CHANGELOG.md records the work released since v1.4.6 under a dated v1.4.7 heading and retains an empty 未リリース section for the next cycle.
  - README.md pins v1.4.7 in every fixed stable-version copy and update example, and its external link targets are unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:70e6e45a0ffa073390e5c76bed5293151b518483bb75e2f835e9ca94c31ce00c","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:5345a5bf72a5938945e334db51e99908b22b65ec4025c60a66aee6ff601e44ea","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - CHANGELOG.md
  - README.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/324-derive-development-direction-from-accepted-requirements.md
  - docs/downstream-baselines.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The repository documents v1.4.7 as the version a downstream project pins for a fixed copy or update, so the released ref that carries the improvement report, requirement collection, and development direction commands is the one the documentation names.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6737f396bac69ee68e77aabb48789651cbd040c1e52ea80470622577ca208309","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 配布先の改善報告を開発方針まで運ぶ流れを届けるため v1.4.7 を公開する

## Decisions

- Release the accumulated dev work as v1.4.7 because a served project cannot report a template improvement, collect it as a requirement, or read the resulting direction until the template ships those commands.
- Keep the tag itself outside this plan, matching the v1.4.4, v1.4.5, and v1.4.6 release decisions that publication is a post-plan operation.
- Leave the empty 未リリース section in place, because scripts/check-copier-template.py already requires that marker and the next cycle appends to it.

## Tasks

- [ ] Date the work released since v1.4.6 as the v1.4.7 release heading and leave an empty 未リリース section above it.
- [ ] Pin every fixed stable-version README example to v1.4.7 without changing external link targets.

## Validation Notes
