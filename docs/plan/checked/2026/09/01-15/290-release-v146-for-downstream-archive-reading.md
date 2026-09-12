# Release v1.4.6 so downstream projects receive the plan index and archive vintage fixes

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
  - {"evidence":"scripts/check-copier-template.py already carries require_documented_release_version(), which derives the expected version from the newest dated CHANGELOG heading and refuses a disagreeing README --vcs-ref pin. scripts/lint-project-workflow.sh already runs it, so this release needs no new validation authority.","kind":"existing_mechanism"}
  - {"evidence":"The v1.4.5 release dated the accumulated 未リリース section, left an empty one behind, and rewrote the three README fixed-version pins. This release repeats that exact transformation for v1.4.6.","kind":"mechanical_transformation"}
completion_conditions:
  - CHANGELOG.md records the work released since v1.4.5 under a dated v1.4.6 heading and retains an empty 未リリース section for the next cycle.
  - README.md pins v1.4.6 in every fixed stable-version copy and update example, and its external link targets are unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:f2bcd001997c603587b3a84bfdedd3ca26a9ba55aca780538fcbe8abcd69d606","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:d5fefadc0cdcd339238f6cb5d1072c2611e10f9031bc85308ad1f30e16da35bf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - CHANGELOG.md
  - README.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/289-read-archives-older-than-the-schema.md
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
  - The repository documents v1.4.6 as the version a downstream project pins for a fixed copy or update, so the released ref that reads a pre-schema checked archive and judges a plan index one way is the one the documentation names.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4c7224e78fbbe1497841b7926f1d153ec68bc4e63bbbc7e4761cc2b93464be76","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 計画索引と旧世代アーカイブの修正を配布先へ届けるため v1.4.6 を公開する

## Decisions

- Release the accumulated dev work as v1.4.6 because a served project holds 277 checked records older than the current manifest schema and cannot update until the template reads them.
- Keep the tag itself outside this plan, matching the v1.4.4 and v1.4.5 release decisions that publication is a post-plan operation.
- Leave the empty 未リリース section in place, because scripts/check-copier-template.py already requires that marker and the next cycle appends to it.

## Tasks

- [x] Date the work released since v1.4.5 as the v1.4.6 release heading and leave an empty 未リリース section above it.
- [x] Pin every fixed stable-version README example to v1.4.6 without changing external link targets.

## Validation Notes

検証結果:

- `python3 scripts/check-copier-template.py` — 通過。README の3か所の固定版指定が、CHANGELOG の最新の日付付き見出し v1.4.6 と一致することを確認した。
- `scripts/lint-project-workflow.sh` — 通過。
- 配布先検証: `scripts/verify-downstream-baselines.py --source-ref dev` を実行し、`curiretas-gakumas-portal` と `supportcard-status` が `verified`、`gakumasu-timeline` が `blocked (target_dirty)` であることを確認した。最後の1件は対象リポジトリに未コミットの変更があるためで、所有はプロジェクト側にある。
