# Bind review to candidate leaf

status: checked
task_types:
  - planning_docs
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: each review round is counted against one immutable writable-attempt admitted-manifest and admitted-patch identity that still matches the accepted candidate
write_scope:
  - AGENTS.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/test-plan-execution-state.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/168-verify-runtime-session-resource-evidence.md
  - docs/plan/checked/2026/08/16-31/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Give an independent reviewer only the unchanged plan, admitted diff, bounded receipts, and applicable specifications after the candidate is otherwise review-ready; permit one initial review and one bounded rereview per candidate before the existing strategy-change path, and do not reuse an accumulated general-purpose reviewer history across numbered plans.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
replan_source: docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
replan_contract: docs/plan/replanned/contracts/170-bind-review-context-to-candidate-lifecycle.json
integration_gates:
  - Plans 168 and 169 checked archives are normative context
  - Plan 173 consumes the immutable candidate leaf identity when binding runtime turn-zero evidence
  - Plan 175 revalidates the complete source acceptance
successor_plans:
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
  - docs/plan/active/173-record-runtime-review-turn-zero.md
  - docs/plan/active/174-linearize-reviewer-session-registry.md
  - docs/plan/active/175-integrate-candidate-review-boundaries.md
inherited_acceptance_digests:
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: review対象と回数上限を不変な候補leafへ結合する。

## Decisions

- candidate-review-leaf-identity means the immutable writable-attempt, admitted-manifest, and admitted-patch identity used for review counting and accepted-candidate matching.
- Store lifecycle phase evidence separately; admitted-to-applied phase changes and JSON reserialization must not change review identity.
- For parent-direct implementation, bind review to the exact write-scope diff and require the checked commit to contain that reviewed diff.

## Tasks

- [x] Replace raw lifecycle-file review identity with the immutable candidate leaf identity.
- [x] Enforce one initial review and one rereview per candidate leaf, including same-patch correction leaves.
- [x] Require the accepted candidate or checked parent-direct commit to match the reviewed target.
- [x] Add phase-change, reserialization, target-reset, and post-review mutation rejection tests.
- [x] Align root and generated policy and Skill guidance.
- [x] Run focused validation, independent review, authoritative validation once, archive, and commit.

## Validation Notes

- Plan 170 was restructured after its bounded rereview found unresolved candidate identity, runtime evidence, and reviewer-history boundaries.
- Focused validation passed with 56 execution-state tests plus root policy, Copier template, and diff checks.
- Independent review found candidate admission, close, lock, checkpoint, packet-binding, and unresolved-finding gaps; two bounded remediation rounds closed them.
- Authoritative validation passed once with every declared command.
