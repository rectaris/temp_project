# Integrate the generated verify-copier-update helper compilation boundary

status: in_progress
primary_invariant: prove the exact generated-helper authority and preserved Plan 119 candidate through the real Copier direct lane
replan_source: docs/plan/active/124-forward-current-generated-validation-authority.md
replan_contract: docs/plan/replanned/contracts/124-forward-current-generated-validation-authority.json
integration_gates:
  - Plan 125 must be checked before the authoritative real-Copier lane runs.
  - The deterministic rejected-argv regression must pass before the real-Copier lane runs.
  - Plan 119 resumes only after this plan is checked with zero unresolved High or Medium findings.
successor_plans:
  - docs/plan/active/125-authorize-generated-verify-helper-compilation.md
  - docs/plan/active/126-integrate-generated-verify-helper-compilation.md
inherited_acceptance_digests:
  - sha256:bd9dfaf6c8e20384e5d251985bad4c4e7444b353b01bc56c490329b5f94ff138
  - sha256:e26ad0ca7604e5feccfc97c2adae918a14371df6dd63ce243166bb3e218285dc
  - sha256:91fd9de002f93bf994927a87c2337b016347ebe6560adfa4c30fb943ff9a2101
  - sha256:460a6d4c213598f409b07f96cf991d0969845996c01e3526430add6463c08431

task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: no
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - tests/copier-update.sh
  - tests/smoke.sh
  - .codex/skills/verify-copier-update/
  - template/.agents/skills/verify-copier-update/
  - template/.project-agent-workflow/skills/verify-copier-update/
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/active/125-authorize-generated-verify-helper-compilation.md
  - docs/plan/replanned/2026/08/16-31/124-forward-current-generated-validation-authority.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-verify-copier-update.py
  - python3 scripts/check-copier-template.py
  - sh -n tests/copier-update.sh
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-verify-copier-update.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Add the existing `template/.project-agent-workflow/scripts/plan_validation_commands.py` to both the fixture copy list and its exact Git staging list.
  - Modify the generated validation-command allowlist only to accept `.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py` as a `python3 -m py_compile` argument; do not modify the root allowlist, Plan 119 acceptance, Copier safety conditions, or external-effect authorization.
  - Prove the wrapperless v1 real-Copier lane reaches `verified` through `direct_supported_v1` with the current generated validator and preserves the original repositories.
  - Finish with zero unresolved High or Medium independent-review findings before returning Plan 119 to a fresh execution run.
checked_summary_ja: 生成helperの限定的なコンパイル権限を実Copier経路へ統合し、元repositoryを変更せずPlan 119を再開可能にする。

## Decisions

- Forward the current generated validation-command module in both exact fixture lists.
- Validate the path-exact parser behavior before consuming the one authoritative real-Copier integration run.
- Treat the existing uncommitted Plan 119 candidate as preserved input; do not change its acceptance or safety boundary.
- Require independent read-only review before returning Plan 119 to a fresh execution identity.

## Tasks

- [ ] Confirm Plan 125 is checked and the deterministic authority regression passes.
- [ ] Confirm the fixture copies and stages the matching generated validation-command module.
- [ ] Review the combined preserved candidate for scope, authority, original-repository preservation, and exact generated parity.
- [ ] Run the real Copier lane once and require verified through direct_supported_v1.
- [ ] Archive and commit this integration, then resume Plan 119 with a fresh ledger.

## Validation Notes

- Plan 124's authoritative attempt established the exact rejected argv before this user-authorized authority change.
