# Stop indivisible Tier 1 work without an impossible descope

status: checked
primary_invariant: A Tier 1 plan keeps its single acceptance requirement intact when it must stop; it cannot fabricate a retained/deferred partition or obtain another execution budget through descope.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"SPEC_PLAN_WORKFLOW.md requires exactly one Tier 1 acceptance item but Bounded Descope requires nonempty retained and deferred acceptance sets."}
  - {"kind":"existing_mechanism","evidence":"scripts/plan-execution-state.py validate_descope_classification rejects empty retained or deferred sets, and existing stopped-run rules already prohibit reopening or automatic successors."}
completion_conditions:
  - New Tier 1 admission accepts exactly one acceptance item and rejects zero or multiple items without rewriting historical plans.
  - The root and generated policy restrict bounded descope to genuinely partitionable acceptance sets and route indivisible Tier 1 work to existing stopped owner-decision handling without deleting its requirement.
  - The existing descope implementation still rejects an empty side and preserves stopped execution budgets; no ledger schema or state transition is relaxed.
  - Generated plan creation and promotion apply the new Tier 1 admission condition while pre-policy durable plans remain readable.
completion_witness_map:
  - {"condition_sha256":"sha256:2deec3531d0595c22285b291895b1f8e0a32ab4ff04e95006c5d304044bcbdd0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:3b1d61d6e5d2179015983e3757d12dfef2862ab63ff494102b0690dbb6363aa5","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:8ee991a91a0f2a54382be315c376b365ff4e1b4c5ed1c672b6db497d03a6c68d","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:c2d690b9b29ba9c0497d80eb7eba395de1c922ae9bfd23c76ef65eb2fc2af757","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - AGENTS.md
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - tests/test-plan-execution-state.py
  - tests/test-validation-tools.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Preserve one indivisible Tier 1 acceptance item and explicitly stop for the owner when execution cannot continue; do not create a descope, repair, or reconstruction successor or reopen a stopped run.
  - Enforce the one-item condition only at new admission boundaries and preserve historical readability and all existing nonempty descope partition checks.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:8f81d7caa063a1d269739b4529c25ae5876d205204ea77d60f28b141a6b9f460","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:b5cf95e85d51e255202e487562463f43366a553060fbbd85f29a6cc42d514a93","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Start only after plan 268 is checked so the large-suite baseline is already green; this is execution order, not a reconstruction successor of 268.
  - Use bounded parent implementation and independent read-only review for the admission and policy changes.
  - Keep Tier 1 at exactly one acceptance item; do not split, rewrite, or silently remove its original requirement to make descope feasible.
  - Do not change scripts/plan-execution-state.py, its template copy, ledger schemas, review budgets, or correction limits.
  - An unstarted plan may remain backlog; started work retains the applicable existing stopped/deferred state and evidence, never a fresh unstarted identity.
  - After an existing budget-exhaustion transition, an indivisible Tier 1 ledger remains descope_pending with its recorded exhaustion reason; preserve the deferred source and all evidence, and refuse descope because no nonempty partition exists.
  - This plan adds no continuation, successor, reset, or reopening route. If the separately implemented same-plan continuation policy is already checked, an otherwise eligible `parent_remediation_budget_exhausted` run may use that one fresh epoch without partitioning or deleting the Tier 1 acceptance item; every other stopped state remains stopped.
  - Before budget exhaustion, a parent may stop scheduling and defer the unchanged source under existing policy; do not fabricate an exhaustion event or hard-drift reason merely because the acceptance item cannot be divided.
checked_summary_ja: 完了条件が一つの Tier 1 に分割不能な縮小手続を要求せず、条件を保持したまま停止する規則と新規受入時の件数検査を整える。

## Decisions

- 対象は、acceptance が一項目だけの Tier 1 が作業範囲を縮小できない場合の停止手順である。
- 前回の指摘は、Tier 1 の完了条件一件を、空でない二つの集合へ分割できないことである。
- Tier 1 の一件制約を維持し、分割不能な作業を止める既存手順を明記する。
- 未着手の作業と、実行記録を持つ停止済みの作業を区別する。
- 停止済みの実行記録を消してバックログからやり直す操作は認めない。
- 予算上限に達して descope_pending になった実行は、その状態に残す。
- 本プランでは、その実行を再開する新しい遷移を追加しない。別途導入済みの同一プラン継続条件を満たす場合だけ、その既存経路を妨げない。
- Tier 0 にはプラン自体がないため、bounded descope を既定の出口として案内しない。
- 新規作成と昇格の受入処理で件数を検査し、過去のプランに新しい大域的 lint 制約を遡及適用しない。

## Tasks

- [x] Add new-admission fixtures for zero, one, and two Tier 1 acceptance items plus a historical plan that remains readable.
- [x] Update root admission checking and the generated planlib admission path without changing historical manifest parsing.
- [x] Update root/template tier and descope wording and the corresponding AGENTS instruction; preserve every existing owner-decision and stopped-run guarantee.
- [x] Verify the existing nonempty partition behavior and generated create/promote behavior using the declared witnesses.
- [x] Obtain independent review and run authoritative validation once; do not reuse an implementation check as the final authoritative witness.

## Validation Notes

- Planning baseline: `987ed43` in `temp_project`.
- Owner request: 「指摘事項についてそれぞれプランを作成せよ。」
- This request authorizes preparing the backlog scope; it does not activate this plan, authorize product implementation now, or continue an unrelated stopped run.
- Feasibility evidence above is source inspection, not a claim that the proposed implementation or its future tests have passed.
- At activation, resolve every dependency to its unique checked record, confirm that the current source still supports this scope, and record the baseline before implementation.
- The parent owns policy interpretation, write-scope admission, review acceptance, validation, lifecycle changes, and commits; helpers have no write authority.
- No measured resource saving is claimed; completion of this plan requires its declared correctness witnesses, not an assumed productivity gain.

- 2026-09-09 activation: Owner instruction 「@docs/plan/backlog/ にあるそれぞれのプランついて、実装作業をせよ。」 selected this backlog plan for implementation. Activation baseline: `b5cac7c` in `temp_project`. The declared source mechanisms are still present.

- 2026-09-09 implementation: New Tier 1 admission now requires exactly one acceptance item in `scripts/check-root-agent-policy.py` (`check_plan_admission`, gated by the existing 264 boundary) and in `template/.project-agent-workflow/scripts/planlib.py` (`validate_admission_record`, gated by `has_admission_record`). The tier and descope policy in `docs/agent/SPEC_PLAN_WORKFLOW.md`, its generated mirror, `AGENTS.md`, and `template/.project-agent-workflow/AGENTS.md.jinja` now state that a single acceptance item cannot be partitioned, so indivisible Tier 1 work stops for the owner with its requirement, stopped state, and evidence intact. `TIER_ZERO_SECTION_DIGEST` was re-pinned because that guard deliberately forces a tier-policy re-review.
- 2026-09-09 focused validation: `python3 tests/test-validation-tools.py` (237 tests OK), `python3 scripts/check-root-agent-policy.py` (passed), `python3 tests/test-plan-execution-state.py` (137 tests OK), `python3 scripts/check-copier-template.py` (passed), `git diff --check` (clean).
- 2026-09-09 independent review: one bounded read-only review reported no finding and accepted the change. It reproduced admission enforcement on both the root and generated paths, confirmed that all six existing Tier 1 plans still pass and that a synthetic pre-264 plan is skipped, confirmed `scripts/plan-execution-state.py` and its template copy are untouched with their nonempty partition checks intact, and mutation-tested the new tests in throwaway copies outside the worktree.
- 2026-09-09 authoritative validation: `scripts/lint-project-workflow.sh` and `REQUIRE_COPIER=1 tests/smoke.sh` on commit `187ddad`.
- 2026-09-09 scope note: no continuation, successor, reset, or reopening route was added, and no ledger schema, review budget, or correction limit was changed.
