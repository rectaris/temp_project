# Authorize the generated verify-copier-update helper for compilation

status: checked
primary_invariant: accept only the exact generated verify-copier-update helper path in Python compilation validation
replan_source: docs/plan/active/124-forward-current-generated-validation-authority.md
replan_contract: docs/plan/replanned/contracts/124-forward-current-generated-validation-authority.json
integration_gates:
  - Plan 126 must recheck this exact authority boundary in the real Copier fixture before Plan 119 resumes.
successor_plans:
  - docs/plan/active/125-authorize-generated-verify-helper-compilation.md
  - docs/plan/active/126-integrate-generated-verify-helper-compilation.md
inherited_acceptance_digests:
  - sha256:e26ad0ca7604e5feccfc97c2adae918a14371df6dd63ce243166bb3e218285dc
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
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/replanned/2026/08/16-31/124-forward-current-generated-validation-authority.md
  - scripts/plan_validation_commands.py
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - git diff --check
acceptance:
  - Modify the generated validation-command allowlist only to accept `.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py` as a `python3 -m py_compile` argument; do not modify the root allowlist, Plan 119 acceptance, Copier safety conditions, or external-effect authorization.
checked_summary_ja: 生成projectの検証コマンドで、Copier更新検証helperの正確な一パスだけをPythonコンパイル対象として許可する。

## Decisions

- Permit only the exact managed helper path as a python3 -m py_compile argument.
- Keep the root validation-command policy and every other generated Skill path unauthorized.
- Add the rejected argv as a deterministic regression before changing the validator.
- Use bounded parent implementation because this plan changes validation authority, then require independent read-only review.

## Tasks

- [x] Add a failing regression for the exact helper path and neighboring unauthorized paths.
- [x] Implement the path-exact generated compilation allowance without broadening root authority.
- [x] Run focused validation and obtain zero unresolved High or Medium review findings.
- [x] Archive and commit this authority change before Plan 126 integration.

## Validation Notes

- The user explicitly authorized this exact generated validation-authority expansion on 2026-08-21.
- The reproduce-first test failed on the exact helper path before implementation, then all 32 validation-tool tests passed after the path-exact allowance was added.
- Independent read-only review reported High 0 and Medium 0; the reviewer made no file changes.
- Authoritative validation passed: `python3 tests/test-validation-tools.py` and `git diff --check`.
- Parent execution evidence: `/tmp/plan125-execution.YDtlQ0/execution.json`.
