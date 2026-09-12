# Use the canonical active-index parser in read-only plan overviews

status: backlog
primary_invariant: A read-only plan overview parses the whole present active index through the existing canonical parser and never reports a malformed index as a successful empty result.
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
  - {"evidence":"At f07616d, render-plan-overview.py --root <fixture> --json returns exit 0 and [] for both a blank plan.md and an empty-marker index with trailing content. planlib.parse_active_index rejects both exact inputs.","kind":"reproduced_defect"}
  - {"evidence":"template/.project-agent-workflow/scripts/planlib.py already provides the canonical parser. Root render-plan-overview.py dynamically loads template-owned plan_overview.py, so one adapter can serve both entrypoints.","kind":"existing_mechanism"}
completion_conditions:
  - For a present active index, root and generated overview commands agree with planlib.parse_active_index on canonical empty/populated input and malformed, duplicate, mismatched, unadopted or trailing-content input.
  - Requested ids still resolve to exactly one existing lifecycle document with matching status, and Markdown links remain relative to the explicit report path; valid empty backlog output remains supported.
  - A malformed or unadopted index produces a nonzero diagnostic without a success payload or file rewrite; overview display remains optional and adds no commit, completion or activation gate.
completion_witness_map:
  - {"condition_sha256":"sha256:18f733c7843557432a1daaaa58aca7cf09e77cd50add6a3ae039f14c54ab9965","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:faab71e93d724fef5eae5553fff3660021f668db639fabfd2ee94e3242509235","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:5a4e7a699f628f33566b42a4b38f9be8343596e965a288ea7a90f1fc90db6dd1","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/plan_overview.py
  - tests/validation_tools/plan.py
  - tests/test-validation-tools.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/planlib.py
  - docs/plan/checked/2026/09/01-15/298-derive-plan-overviews-from-lifecycle-files.md
  - docs/plan/checked/2026/09/01-15/109-judge-one-plan-index-one-way.md
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
  - For a present active index, root and generated overview commands agree with planlib.parse_active_index on canonical empty/populated input and malformed, duplicate, mismatched, unadopted or trailing-content input.
  - Requested ids still resolve to exactly one existing lifecycle document with matching status, and Markdown links remain relative to the explicit report path; valid empty backlog output remains supported.
  - A malformed or unadopted index produces a nonzero diagnostic without a success payload or file rewrite; overview display remains optional and adds no commit, completion or activation gate.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:18f733c7843557432a1daaaa58aca7cf09e77cd50add6a3ae039f14c54ab9965","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:faab71e93d724fef5eae5553fff3660021f668db639fabfd2ee94e3242509235","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:5a4e7a699f628f33566b42a4b38f9be8343596e965a288ea7a90f1fc90db6dd1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Select this backlog plan for implementation, publish its active bytes, and prepare its exact plan-bound worktree before product edits.
  - Use parent-owned implementation and independent read-only review because the scope includes test registration or validation tooling. Preserve existing review budgets and all acceptance gates.
  - Execute serially. These plans share the validation test entrypoint; do not enroll them as an independent parallel group.
checked_summary_ja: プラン一覧の表示と実行前検査で、同じ一覧文書を同じ規則で判定する。

## Decisions

- Remove the independent active-index grammar in plan_overview.py and adapt rows from the adjacent shared planlib parser. Load that same implementation for root and generated entrypoints without depending on the caller working directory.
- Preserve the existing missing-index behavior for repositories that do not have an active index; once the file is present, validate its complete text. Keep unadopted-project diagnostics and never rewrite project-owned plan documents.
- Keep manifest/file consistency and exact id resolution in the overview layer. Preserve existing output format, relative-link option and lifecycle distinctions; do not infer readiness, approval or dependencies from displayed status.
- Reuse checked Plan 298 and the canonical parser already used by lifecycle tooling. Do not modify planlib, lifecycle semantics, archive history or approval policy.
- Add behavioral coverage to the aggregate suite and test both CLI entrypoints in temporary fixtures. Keep the display optional, as Plan 298 explicitly requires; stale explanatory Markdown does not become a gate.

## Tasks

- [ ] Add a registered PlanOverviewTest class in tests/validation_tools/plan.py and import it from tests/test-validation-tools.py; existing searches find no overview-specific behavioral tests.
- [ ] Assert the reproduced empty-file and empty-marker-plus-trailing-content cases fail. Compare both overview entrypoints with planlib on canonical empty and populated documents, CRLF, missing final newline, header-only input, duplicate rows, wrong ids, invalid status, literal backslash-t and unadopted prose.
- [ ] Test missing-index compatibility separately from a present invalid index. Exercise status disagreement, missing requested ids, duplicate lifecycle files, checked/replanned/shelved resolution, empty backlog and relative Markdown links.
- [ ] Use temporary fixtures and before/after file snapshots to prove no rewrite; require nonzero failure and no success JSON or table on invalid input. Keep correct canonical input as positive controls.
- [ ] Replace the local grammar with the shared parser adapter and update entrypoint loading only if necessary. Run the registered focused suite, independent review and mandatory validation.

## Validation Notes

- Planning baseline: f07616d02f8db6c6df55c2fa6dfedfd046e87c4f in temp_project.
- Owner instruction: これまでのこのプロジェクトでの開発作業について改善できる部分を探し、改善するためのプランとして作成せよ。
- This task authorizes plan authoring only. No implementation, stopped-run continuation, remote publication or performance claim is included.
- Planning evidence and reproduction steps: docs/plan/development-improvements-20260912.md. Regression assertions described here must be added and exercised during implementation; their future success is not claimed now.
