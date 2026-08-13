# Seal successor acceptance authority

status: checked
primary_invariant: accept only the exact source texts mapped to a successor plan
replan_source: docs/plan/active/079-plan-restructuring-integration.md
replan_contract: docs/plan/replanned/contracts/079-plan-restructuring-integration.json
integration_gates:
  - reject added, weakened, reordered, or clarification-labelled acceptance text without separate user authorization
  - keep root and generated restructure commands byte-identical
successor_plans:
  - docs/plan/active/080-successor-acceptance-authority.md
  - docs/plan/active/081-plan-restructuring-integration.md
inherited_acceptance_digests:
  - sha256:f63ec861469ec27fe14daef2ba73dc1cdeadae80e5a35395c09f35abfe486c57
  - sha256:675856f8d05166ebfc9efa5b4fffc5199d404792bf648a919f094bd3e9ea2c8e
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/plan_validation_commands.py
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - tests/test-validation-tools.py
  - docs/plan/
context_files:
  - docs/plan/replanned/2026/08/01-15/079-plan-restructuring-integration.md
  - docs/plan/replanned/contracts/079-plan-restructuring-integration.json
  - docs/plan/checked/2026/08/01-15/077-atomic-plan-restructuring.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-validation-tools.py
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - git diff --check
acceptance:
  - Prove that requirement changes remain pending until explicit user authorization and cannot be disguised as clarification or successor mapping.
  - Keep root and generated policy, schemas, commands, Skills, tests, indexes, and lifecycle behavior aligned.
checked_summary_ja: 後続planの受入れ条件を元planから割り当てた本文だけに制限した。

## Decisions

- Treat any additional successor acceptance item as a requirement change outside restructuring authority.
- Preserve mapped source acceptance text exactly and in source order.

## Tasks

- [x] Enforce exact successor acceptance equality for each mapped digest.
- [x] Add conflicting clarification, added requirement, and ordering rejection tests.
- [x] Run focused validation, independent review, archive, and commit before plan 081.

## Validation Notes

- `python3 tests/test-plan-restructure.py`: 15 tests passed.
- `python3 tests/test-validation-tools.py`: 30 tests passed.
- Python compilation, root/template restructure parity, `git diff --check`, and durable contract verification passed.
- Independent final review reported zero unresolved High or Medium findings.
