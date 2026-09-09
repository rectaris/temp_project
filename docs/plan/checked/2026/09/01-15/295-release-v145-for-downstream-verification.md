# Release v1.4.5 so downstream projects can adopt the Copier update verification skill and the update preflight

status: checked
primary_invariant: The repository never presents a fixed stable template version that disagrees with the newest released version recorded in the change log.
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"scripts/check-copier-template.py already reads CHANGELOG.md and README.md and already fails on missing required markers, and scripts/lint-project-workflow.sh and tests/smoke.sh already run it, so a version-agreement check needs no new validation authority.","kind":"existing_mechanism"}
  - {"evidence":"The v1.4.4 release edited CHANGELOG.md by dating the 未リリース section and left an empty one behind, and pinned README.md copy and update examples to the new tag. This release repeats that exact transformation for v1.4.5.","kind":"mechanical_transformation"}
  - {"evidence":"On 2026-09-09 README.md pinned v1.4.4 in three places while copier.yml already declared v1.4.5 migrations, and every existing validation command passed, so no check currently observes a stale documented pin.","kind":"reproduced_defect"}
completion_conditions:
  - CHANGELOG.md records the accumulated unreleased entries under a dated v1.4.5 heading and retains an empty 未リリース section for the next cycle.
  - README.md pins v1.4.5 in every fixed stable-version copy and update example, and its external link targets are unchanged.
  - scripts/check-copier-template.py refuses a README fixed-version pin that names any version other than the newest dated release heading in CHANGELOG.md.
completion_witness_map:
  - {"condition_sha256":"sha256:4ef4a7efedad42037ab22d37213878dfb5a5442bd22803dcfc3ee43c3a75796d","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:b120ac2c0db72d9c42f917fc0f7a19ff10cd9c6fce638eeac73384a9e2234e01","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:12a769b2b1a332d0507c51fc2c6ef1703f8f21cb78165c652249eefdb9c77b04","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - CHANGELOG.md
  - README.md
  - scripts/check-copier-template.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/08/01-15/110-release-v144.md
  - copier.yml
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
  - The repository documents v1.4.5 as the version a downstream project pins for a fixed copy or update, so the released ref that carries the update verification skill and the update preflight is the one the documentation names.
  - The shipped changes appear under a dated v1.4.5 heading and the next cycle starts from an empty 未リリース section.
  - A README fixed-version pin left at a superseded version fails repository validation instead of shipping.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:969803e690464b130c6c0cda1ce05679e787dfa1236fff4f6bdd2a31dc54f6e4","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:13a773dd27e627c6ded7f6e9d1d2873d1ea04b66d21e5b09eec3dc40b9d3a4fa","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:8baff672504a0be879441d03944a120feddedef8be775d0293a85b33a0cfc68a","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 下流が更新検証スキルと事前検査を採用できるよう v1.4.5 を公開する

## Decisions

- Release the accumulated dev work as v1.4.5 because copier.yml already declares v1.4.5 migrations, so any other number would leave the migration lane unreachable.
- Keep branch push, pull request, tag creation, and any GitHub Release outside this plan, matching the v1.4.4 release decision that publication is a post-plan operation.
- Add the README-to-CHANGELOG version agreement check to scripts/check-copier-template.py rather than to a new script, because that checker already reads both files and is already run by the authoritative suite.
- Derive the expected version from the newest dated release heading in CHANGELOG.md rather than from a separate constant, so a release cannot forget to update a second source of truth.
- Leave the empty 未リリース section in place, because scripts/check-copier-template.py already requires that marker and the next cycle appends to it.

## Tasks

- [x] Date the accumulated 未リリース entries as the v1.4.5 release heading and leave an empty 未リリース section above it.
- [x] Pin every fixed stable-version README example to v1.4.5 without changing external link targets.
- [x] Extend scripts/check-copier-template.py to refuse a README fixed-version pin that disagrees with the newest dated CHANGELOG release heading.
- [x] Run the focused witness, then the authoritative suite once.

## Validation Notes

- Owner release authorization on 2026-09-09 selected `authorize_push_and_tag`, release version v1.4.5, and the existing dev to main pull-request route. Publication itself stays outside this plan.
- The release number is fixed by `copier.yml`, which already declares v1.4.5 before-stage and after-stage migrations. Any other number would leave that migration lane unreachable from a released ref.
- The new check derives the current version from the newest dated release heading in CHANGELOG.md and binds it to the two README anchors that document a fixed stable version. Historical version references, such as the v1.1.2 legacy adoption instructions, stay outside the anchored blocks and are not flagged.
- Focused witness passed: `python3 scripts/check-copier-template.py`.
- Negative cases confirmed to fail: a stale declared version, a stale `--vcs-ref` pin, a removed pin, and a `--vcs-ref HEAD` pin under an anchor that must name a fixed version. The equivalent `--vcs-ref=v1.4.5` spelling is accepted.
- Independent read-only Sol review reported one Medium and one Low finding. The Medium finding was that a block with no pin, an `=` spelling, or a `HEAD` pin passed vacuously; the Low finding was that an info-string fence was treated as a closing fence. Both were fixed and re-verified before authoritative validation.
- Authoritative validation passed once after the review fixes: `scripts/lint-project-workflow.sh` and `tests/smoke.sh`. Optional actionlint was unavailable and skipped by the existing smoke command.
