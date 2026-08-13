# Define plan restructuring policy and schema

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/
  - references/orchestration.md
  - references/planning.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/smoke.sh
  - tests/test-validation-tools.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Define `replan_required` as a nonterminal active state that blocks implementation, validation, apply, and completion until the plan is reconstructed or a user-authorized requirement change is recorded.
  - Define `replanned` as a terminal historical state distinct from successful `checked` completion and external-prerequisite `deferred` work.
  - Preserve user requirements, accepted safety conditions, and every source acceptance item while allowing only plan boundaries, ordering, implementation methods, and validation methods to change without user authorization.
  - Add optional exact-schema fields for a primary invariant, integration gates, replan source and contract, successor plans, inherited acceptance digests, and bounded replan reason codes while preserving legacy plan parsing.
  - Require mandatory replanning after scope/spec/security-boundary drift, multiple independently validatable invariants, a post-authoritative design change, exhausted candidate corrections, or two parent-direct remediation rounds that still leave High or Medium findings.
  - Treat elapsed time only as bounded telemetry and a checkpoint signal.
  - Keep full decision matrices outside active plans and keep root/generated policy, parser, lint, Skill, and tests aligned.
checked_summary_ja: 要件を変更せずplan境界だけを再構成する状態、schema、停止条件を定義した。

## Decisions

- Parent-session implementation is required because this slice changes high-judgment lifecycle and policy authority.
- Preserve the accepted requirement baseline by exact normalized acceptance digests rather than semantic self-certification.
- Reserve lifecycle values and manifest fields in this plan; plan 077 owns the mutating transition command.
- Keep new fields optional for legacy plans and required only for plans created by restructuring.

## Tasks

- [x] Define lifecycle, requirement-preservation, trigger, and authority policy.
- [x] Add optional parser fields and generated-plan lint rules without performing transitions.
- [x] Add fixed positive and negative schema coverage.
- [x] Run required validation, independent review, archive, and commit before plan 077.

## Validation Notes

- `python3 tests/test-validation-tools.py`: 29 tests passed.
- `python3 scripts/check-root-agent-policy.py`: passed.
- `python3 scripts/check-copier-template.py`: passed.
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed with the documented actionlint-unavailable skip and fallback backend.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Independent `change_reviewer` review found four Medium issues in recursive historical discovery, historical-policy isolation, mandatory lineage, and test coverage; all were corrected. Final rereview reported zero unresolved High or Medium findings.
