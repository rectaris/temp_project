# Release v1.4.8 so downstream projects receive the ownership-record retirement path

status: checked
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
  - {"evidence":"scripts/check-copier-template.py carries require_documented_release_version(), which derives the expected version from the newest dated CHANGELOG heading and refuses a disagreeing README --vcs-ref pin. scripts/lint-project-workflow.sh runs it, so this release needs no new validation authority.","kind":"existing_mechanism"}
  - {"evidence":"The v1.4.7 release dated the accumulated 未リリース section, left an empty one behind, and rewrote the three README fixed-version pins. This release repeats that exact transformation for v1.4.8.","kind":"mechanical_transformation"}
completion_conditions:
  - CHANGELOG.md records the work released since v1.4.7 under a dated v1.4.8 heading and retains an empty 未リリース section for the next cycle.
  - README.md pins v1.4.8 in every fixed stable-version copy and update example, and its external link targets are unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:ec2ae21b77e2996f773d7215017b6547a42607abd7c9f03ca2ce08b404ae6652","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:5e01f67825682d28d6eef8f568b10539772b43506eb2afc539aa81f6ce6daba8","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - CHANGELOG.md
  - README.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/332-retire-unreachable-worktree-records.md
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
  - The repository documents v1.4.8 as the version a downstream project pins for a fixed copy or update, so the released ref that carries the local text hygiene check, the test-owned record cleanup, and the unreachable record retirement command is the one the documentation names.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b625cb85ab911a17016868b37ce2b29e1326b75d0bd737b16cae49b89e957abb","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 到達不能な所有記録を退避できる経路を配布先へ届けるため v1.4.8 を公開する

## Decisions

- Release the accumulated dev work as v1.4.8 because a served project cannot retire an ownership record whose repository is gone until the template ships the retirement command, and its record directory eventually reaches the count at which the guard refuses to read it.
- Keep the tag itself outside this plan, matching the v1.4.4 through v1.4.7 release decisions that publication is a post-plan operation.
- Leave the empty 未リリース section in place, because scripts/check-copier-template.py requires that marker and the next cycle appends to it.

## Tasks

- [x] Date the work released since v1.4.7 as the v1.4.8 release heading and leave an empty 未リリース section above it.
- [x] Pin every fixed stable-version README example to v1.4.8 without changing external link targets.

## Validation Notes

- `python3 scripts/check-copier-template.py` passes, so the dated `v1.4.8` heading in `CHANGELOG.md` and every `README.md` version anchor agree.
- `./scripts/lint-project-workflow.sh` and `./tests/smoke.sh` both pass on the release commit content.
- `python3 .codex/skills/natural-japanese/scripts/check-japanese-prose.py --json CHANGELOG.md` reports no finding inside the new release section; the remaining findings are pre-existing older entries.
