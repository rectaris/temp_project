# Forward current generated validation authority in the Copier fixture

status: replanned
replan_reason_codes:
  - post_authoritative_design_change
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: no
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - tests/copier-update.sh
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/checked/2026/08/16-31/123-authorize-verify-copier-update-plan-validation.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Add the existing `template/.project-agent-workflow/scripts/plan_validation_commands.py` to both the fixture copy list and its exact Git staging list.
  - Modify the generated validation-command allowlist only to accept `.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py` as a `python3 -m py_compile` argument; do not modify the root allowlist, Plan 119 acceptance, Copier safety conditions, or external-effect authorization.
  - Prove the wrapperless v1 real-Copier lane reaches `verified` through `direct_supported_v1` with the current generated validator and preserves the original repositories.
  - Finish with zero unresolved High or Medium independent-review findings before returning Plan 119 to a fresh execution run.
repair_source: docs/plan/active/119-integrate-verify-copier-update-skill.md
repair_reason: the real-Copier fixture copied validate-changes.py without its matching current plan_validation_commands.py
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/124-forward-current-generated-validation-authority.md
replan_contract: docs/plan/replanned/contracts/124-forward-current-generated-validation-authority.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/125-authorize-generated-verify-helper-compilation.md
  - docs/plan/active/126-integrate-generated-verify-helper-compilation.md
inherited_acceptance_digests:
  - sha256:bd9dfaf6c8e20384e5d251985bad4c4e7444b353b01bc56c490329b5f94ff138
  - sha256:e26ad0ca7604e5feccfc97c2adae918a14371df6dd63ce243166bb3e218285dc
  - sha256:91fd9de002f93bf994927a87c2337b016347ebe6560adfa4c30fb943ff9a2101
  - sha256:460a6d4c213598f409b07f96cf991d0969845996c01e3526430add6463c08431
checked_summary_ja: 実Copier fixtureへ現在の生成検証コマンド定義を欠落なく含める。

## Decisions

- The user explicitly authorized replacing the prior no-authority-change acceptance item with one exact generated-helper compilation path on 2026-08-21.
- Keep the generated authority expansion path-exact; do not authorize arbitrary files below `.project-agent-workflow/skills/` and do not change the root allowlist.
- Reproduce the rejected helper argv in a deterministic parser test before rerunning the real Copier lane.
- Use bounded parent implementation because the repair applies inside the preserved uncommitted Plan 119 fixture, then require independent read-only review.
- Run the real Copier lane once for this repair; Plan 119 will use a separate fresh authoritative run after the repair is checked.

## Tasks

- [ ] Add the generated validation-authority file to the copy and stage lists.
- [ ] Confirm no validation allowlist or Plan 119 acceptance changed.
- [ ] Complete independent review, focused checks, and the real-Copier repair validation.
- [ ] Archive and commit the repair before resuming Plan 119 with a new execution identity.

## Validation Notes

- The stopped Plan 119 ledger recorded `repair_required` with all unchanged-boundary predicates true and one affected invariant.
- Independent classification review reported High 0 and Medium 0 for this one-file repair.
- The one permitted real-Copier validation run proved that copying the current generated authority file is insufficient: its `is_python_compile` rule rejects Python files below `.project-agent-workflow/skills/`.
- Continuing requires an explicit generated validation-authority expansion or a different user-approved validation design. The execution ledger is `replan_required`; do not run another worker, validation, completion, or archive operation for this plan.
