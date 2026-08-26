# Rebind referrer context on archive

status: in_progress
implementation_tier: 2
primary_invariant: a transaction that archives a plan leaves no live plan naming that plan's former active path in context_files
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/plan/checked/2026/08/16-31/220-resolve-active-plan-context-references.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
acceptance:
  - Rebind every live plan's context_files entry that names an archived plan's former active path, inside the transaction that archives it, and then reject any surviving entry of that shape.
predecessor_plans: []

## Decisions

- Plan 220 rejects a `context_files` entry whose plan was moved to `docs/plan/backlog/`, but tolerates an entry whose plan was archived to `docs/plan/checked/` or `docs/plan/replanned/`.
- That tolerance never closes for a plan outside a replan contract. `validate_activation_reference_transition` rebinds only `kind: activation` rebindings, and `validate_rebinding_specs` restricts those to live contract successors, so an ungoverned plan such as Plan 210 keeps its archived context entries indefinitely.
- Closing the tolerance without a rebinding mechanism is unsafe. A referring plan is not in the archiving transaction's write scope, so any immediate rejection would abort that transaction, and a post-commit rejection leaves a mutated repository that neither verification nor recovery can clear.
- Build the rebinding first, then close the tolerance. Do not reverse that order.

## Tasks

- [ ] Rebind referring live plans' `context_files` entries inside the archiving transaction.
- [ ] Close the archived-path tolerance once rebinding is in place.
- [ ] Add transaction tests covering governed and ungoverned referring plans.
