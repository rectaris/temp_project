# Read activation checked archives of every closed vintage

status: in_progress
primary_invariant: An activation reference resolves against its checked archive through the shared closed-vintage rule, so an archive written before the checked status value is read rather than reported as stale.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"activation_checked_pairs in scripts/restructure-plan.py accepts an archive only when its manifest status is exactly checked. Pointing the 23 flat index rows at their existing dated archives makes restructure-plan.py --verify exit 1 at docs/plan/checked/2026/07/01-15/001-initial-package.md, whose vintage declares status: completed.","kind":"reproduced_defect"}
  - {"evidence":"Of the 23 archives those rows name, 001 and 002 declare status: completed and 003 through 019 carry no status field at all. CHECKED_PATH_RE skips a flat row, so the stale paths kept this whole vintage out of activation checking instead of exercising it.","kind":"reproduced_defect"}
  - {"evidence":"planlib.archived_status already reads a checked archive that predates the status field, and lint-plan-docs.py already accepts CLOSED_STATUS_VALUES of checked, completed and ready_to_archive. Only restructure-plan.py compares the raw scalar, at four sites in each of its mirrored copies.","kind":"existing_mechanism"}
completion_conditions:
  - Activation and successor archive checks in both mirrored copies of restructure-plan.py decide closed status through the shared vintage rule, so an archive declaring checked, completed or no status at all resolves while an open or absent archive is still refused.
  - Restructuring verification passes against this repository's real archive with the repaired vintage rule in place, and this plan changes no archive file, no checked index row, no row order, no id and no completion claim.
completion_witness_map:
  - {"condition_sha256":"sha256:7f0c50364636ab9ea093865fca6971f2f85ba48f2324c0e83eb73d98baa5b2f4","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:1ced8850b1c8fd55b2ba92374771d5b7c6af9dd385b675c94d6103f88a509d87","witness":"python3 scripts/restructure-plan.py --verify"}
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/active/312-check-root-archive-index-targets.md
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - docs/plan/checked/2026/07/01-15/001-initial-package.md
  - docs/plan/checked/2026/07/01-15/003-template-operations-hardening.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/validation.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/restructure-plan.py --verify
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Activation and successor archive checks in both mirrored copies of restructure-plan.py decide closed status through the shared vintage rule, so an archive declaring checked, completed or no status at all resolves while an open or absent archive is still refused.
  - Restructuring verification passes against this repository's real archive with the repaired vintage rule in place, and this plan changes no archive file, no checked index row, no row order, no id and no completion claim.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7f0c50364636ab9ea093865fca6971f2f85ba48f2324c0e83eb73d98baa5b2f4","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:1ced8850b1c8fd55b2ba92374771d5b7c6af9dd385b675c94d6103f88a509d87","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
checked_summary_ja: 起動参照が読む完了記録を、どの版でも同じ規則で判定する。

## Decisions

- Reuse the closed-vintage rule the repository already owns rather than inventing a second one. Read the archive status through the shared helper that treats a checked-archive record without a status field as checked, and accept the same closed values the generated linter already accepts.
- Repair every site in restructure-plan.py that compares an archive status to the literal checked for an already archived record. Leave comparisons that describe a target lifecycle state, a live plan or an expected post-transition status unchanged.
- Keep the two mirrored copies of restructure-plan.py identical. Do not change docs/plan/checked.md, any archive, planlib.py or lint-plan-docs.py in this plan; the index repair itself stays with plan 312.
- Do not relax the refusal for an archive that is missing, is not a file, or declares an open status. The repair widens only which closed vintages are readable.

## Tasks

- [ ] Add fixtures to tests/validation_tools/plan.py that build an activation reference against an archive declaring checked, one declaring completed and one carrying no status field, plus negative fixtures for an absent archive and one declaring an open status.
- [ ] Find every site in scripts/restructure-plan.py that judges an already archived record by comparing its status to the literal checked, and record which of them belong to activation and successor resolution.
- [ ] Route those sites through the shared closed-vintage rule and mirror the exact change into template/.project-agent-workflow/scripts/restructure-plan.py.
- [ ] Run the focused suite, then an independent read-only review, then the authoritative lint and smoke suites.
- [ ] Report that plan 312 may resume through a fresh run once this repair is checked.

## Validation Notes

- This plan exists because authoritative validation stopped the plan 312 execution run with repair_required. It does not restate or replace any plan 312 acceptance item.
- The stopped plan 312 candidate is preserved locally at .agent-artifacts/stopped-runs/312-checked-index-candidate.patch and is not authorization to reapply that work here.
