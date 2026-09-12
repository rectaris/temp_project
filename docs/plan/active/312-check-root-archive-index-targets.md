# Validate root checked-index targets through the shared archive check

status: in_progress
primary_invariant: Every indexed checked plan resolves to its existing same-id archive, and root validation applies the shared checked-index rules without rewriting historical archive content.
task_types:
  - template_workflow
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At f07616d, 23 of 244 docs/plan/checked.md rows name absent paths; every missing basename has one existing archive under 2026/07/01-15. Calling the existing lint_checked_index function from the root exits 1 at plan 001, while root policy validation passes.","kind":"reproduced_defect"}
  - {"evidence":"Generated lint-plan-docs.py already has a narrow lint_checked_index check for missing, duplicate, mismatched or out-of-archive targets. Extracting those rules into adjacent planlib.py lets root policy validation reuse them without generated manifest validation.","kind":"existing_mechanism"}
  - {"evidence":"The existing narrow checked-index check exits 0 for a same-id target reached through docs/plan/checked/../../../outside/ and for a checked/ symlink to an outside file. Isolated fixtures confirm both resolve outside checked/. Tighten these path checks during extraction.","kind":"reproduced_defect"}
completion_conditions:
  - Root policy validation and generated plan lint use the same checked-index validation rules and reject a missing target, duplicate id/path, mismatched filename id or target outside the checked archive.
  - The 23 stale root index rows resolve to their unique existing dated archive paths; row ids, row ordering and every historical archive file remain unchanged.
  - The shared check accepts valid empty and populated indexes and historical archives without new manifest fields; invoking it never rewrites source documents or reapplies the generated active-plan schema to root archives.
completion_witness_map:
  - {"condition_sha256":"sha256:9f41857b619cf38b69ad39be5b4e69bfdb7d91cfb8cf73c0a05f5d6b47438afe","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:32671c88f07668eaf9e1c5090f390a7b8c8431b556451a5e942a9acfc317f6fc","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:22adfaddc5f8da154592afa34a52f45a9ec241b5ade337cb1ff5450610cc2acb","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - tests/validation_tools/plan.py
  - docs/plan/checked.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/lint-project-workflow.sh
  - tests/test-validation-tools.py
  - docs/plan/checked/2026/07/01-15/024-half-month-checked-archive.md
  - docs/plan/checked/2026/09/01-15/289-read-archives-older-than-the-schema.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/validation.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Root policy validation and generated plan lint use the same checked-index validation rules and reject a missing target, duplicate id/path, mismatched filename id or target outside the checked archive.
  - The 23 stale root index rows resolve to their unique existing dated archive paths; row ids, row ordering and every historical archive file remain unchanged.
  - The shared check accepts valid empty and populated indexes and historical archives without new manifest fields; invoking it never rewrites source documents or reapplies the generated active-plan schema to root archives.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:9f41857b619cf38b69ad39be5b4e69bfdb7d91cfb8cf73c0a05f5d6b47438afe","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:32671c88f07668eaf9e1c5090f390a7b8c8431b556451a5e942a9acfc317f6fc","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:22adfaddc5f8da154592afa34a52f45a9ec241b5ade337cb1ff5450610cc2acb","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Select this backlog plan for implementation, publish its active bytes, and prepare its exact plan-bound worktree before product edits.
  - Use parent-owned implementation and independent read-only review because the scope includes test registration or validation tooling. Preserve existing review budgets and all acceptance gates.
  - Execute serially. These plans share the validation test entrypoint; do not enroll them as an independent parallel group.
checked_summary_ja: 完了記録の索引に残る古い保存先を直し、既存の検査で再発を防ぐ。

## Decisions

- Extract the existing checked-index validation from generated lint-plan-docs.py into adjacent planlib.py. Keep the generated entrypoint as an adapter and invoke the same narrow check from scripts/check-root-agent-policy.py, already called by required root lint.
- Normalize checked-index targets as repository-relative paths before checking them. Reject absolute paths, dot or parent traversal components and symlink components; verify the resolved regular-file target remains inside the checked archive. Do not preserve lexical-containment escapes while sharing the old checker.
- Do not run the entire generated plan linter against the root repository. Validate index structure and archive references only; preserve the root historical manifest format and Plan 289 vintage compatibility.
- Correct only the 23 index paths whose absent basenames each resolve to one existing dated archive. Preserve ids, ordering, archive bytes, dates and completion claims; refuse ambiguity rather than guessing or creating another completion record.
- Keep replanned history and contracts outside write scope; their existing verification remains in force. Do not add a new archive catalog, automatic lifecycle updater or human-summary freshness gate.
- Use the shared implementation as the root/generated counterpart. Add regression cases to the already imported PlanValidationCommandsTest class in tests/validation_tools/plan.py so the existing focused suite executes them.

## Tasks

- [ ] Add isolated checked-index fixtures for empty and populated valid indexes, missing target, duplicate id/path, wrong filename id and a path outside checked/. Run the same cases through the root policy entry and generated index adapter. Include parent-traversal paths, absolute paths, a symlinked file and a symlinked directory leading outside checked/, plus a valid nested dated path as the positive control.
- [ ] Add a legacy archive fixture with no new manifest fields and prove the shared check only validates the index relationship. Snapshot fixture bytes before and after both successful and rejected reads.
- [ ] Extract the existing checked-index rules into a shared planlib function with an explicit repository root, adapt generated lint, and call it from the ordinary root policy path and its self-test path.
- [ ] Resolve each stale row by exact id and basename to its unique dated archive before editing docs/plan/checked.md. Assert only those paths change and that every archive retains its original bytes.
- [ ] Use the already registered validation test class; demonstrate that removing the root call makes the stale-index regression fail. Review the root/generated boundary and run focused validation, independent review and mandatory lint/smoke.

## Validation Notes

- Planning baseline: f07616d02f8db6c6df55c2fa6dfedfd046e87c4f in temp_project.
- Owner instruction: これまでのこのプロジェクトでの開発作業について改善できる部分を探し、改善するためのプランとして作成せよ。
- This task authorizes plan authoring only. No implementation, stopped-run continuation, remote publication or performance claim is included.
- Planning evidence and reproduction steps: docs/plan/development-improvements-20260912.md. Regression assertions described here must be added and exercised during implementation; their future success is not claimed now.
- Implementation baseline: a30119e in temp_project. Owner instruction: 310 312 を順に実装せよ。
- implementation_mode: parent_direct. This run is stopped at repair_required; no plan 312 product change is committed.
- Defect reproduced before the change: 23 of 246 rows in docs/plan/checked.md named absent flat paths while root validation passed, because only the generated linter carried a checked-index check. The old narrow check also exited 0 for a same-id target reached through docs/plan/checked/../../../outside/ and for a checked/ symlink leaving the archive.
- A candidate implementation reached focused validation (python3 tests/test-validation-tools.py, 296 tests, OK) and one independent read-only review. That review reported no Critical or High findings, one Medium and three Low, and every one of them was addressed in the candidate.
- Authoritative validation then failed: scripts/lint-project-workflow.sh stops at python3 scripts/restructure-plan.py --verify with "activation checked archive is missing or stale: docs/plan/checked/2026/07/01-15/001-initial-package.md".
- Diagnosis: activation_checked_pairs in scripts/restructure-plan.py skips an index row whose path has no dated subdirectory, so the 23 stale rows kept that code path unexercised. Once the rows name their real archives the function applies, and it accepts only a manifest status of exactly checked. Archives 001 and 002 declare status: completed and 003 through 019 carry no status field, all vintages that planlib.archived_status and the generated linter already read as closed.
- Classification: repair_required. The defect is independently repairable, its files are scripts/restructure-plan.py and its mirrored template copy, and both lie outside this plan's write_scope. This plan's scope, invariant, acceptance items and validation authority are unchanged.
- Owner decision on the stop: repair_plan. Plan 313 was created in docs/plan/backlog/ for the bounded repair. This plan stays deferred and resumes only through a fresh run after plan 313 is checked.
- The stopped candidate is preserved locally at .agent-artifacts/stopped-runs/312-checked-index-candidate.patch. It is evidence, not authorization to reapply.
- Resumed in a fresh run after plan 313 was checked at f71c311. The repair is docs/plan/checked/2026/09/01-15/313-read-activation-archives-of-every-vintage.md; this plan's scope, acceptance items and validation authority are unchanged.
