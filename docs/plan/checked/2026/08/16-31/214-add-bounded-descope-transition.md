# Add the bounded descope transition

status: checked
checked_summary_ja: 指摘が多いプランを作り直さずに受け入れ条件だけを絞り込める `descope_required` 停止状態を追加した。元の受け入れ条件は保持分と backlog への繰り延べ分に必ず分割され、欠落・重複・並べ替え・追加は拒否する。スコープ、仕様、セキュリティ境界、不変条件の逸脱は従来の再構築理由へ昇格する。あわせて変更を Tier 0/1/2 に分類する規定を導入し、Tier 0 と Tier 1 を再構築契約から外した。
implementation_tier: 1
implementation_tier_baseline: 2
implementation_tier_authorization: user-authorized bootstrap exemption so the first tiered change does not have to pass through the machinery it replaces
primary_invariant: one bounded acceptance reduction stops an execution run as `descope_required` while every source acceptance digest stays either retained or deferred to an exact backlog plan
task_types:
  - template_workflow
review_class: B
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/214-add-bounded-descope-transition.md
  - docs/plan/plan.md
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Record a bounded acceptance reduction as `descope_required` without creating a replan contract or successor lineage, reject any partition that loses, duplicates, reorders, or adds a source acceptance digest, and escalate scope, specification, security, or invariant drift to the existing hard replan reasons.

## Decisions

- Model `descope_classification` on the existing `repair_classification` event so evidence stays parent-owned, canonical, and bound to one independent-review receipt.
- Derive `descope_required` from events rather than storing it directly, and order it after `replan_required` and before `repair_required`.
- Keep `descope_reason_codes` disjoint from replan and repair reason codes so a descope can never be recorded alongside a hard stop.
- Bump the execution-state schema to 5 because ledgers live outside the repository and carry no committed history.
- Keep the root and generated `plan-execution-state.py` byte-identical, which the Copier static check already enforces.

## Tasks

- [x] Add the `descope_classification` event, evidence schema, and classifier.
- [x] Derive and validate the `descope_required` state and its reason codes.
- [x] Open only the `descope_plan` gate while a run is stopped for a descope.
- [x] Document implementation tiers and the bounded descope transition.
- [x] Cover the happy path, partition rejections, and drift escalation with tests.

## Validation Notes

- `python3 tests/test-plan-execution-state.py`: 70 tests passed.
- `python3 scripts/check-copier-template.py`: passed.
- `python3 scripts/check-root-agent-policy.py`: passed.
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed.
- `git diff --check`: clean.

## Follow-up

- Route review reason codes automatically to descope, continued correction, or replan. Not included here.
- Mirror the tier and descope policy text into `template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md`. Not included here.
