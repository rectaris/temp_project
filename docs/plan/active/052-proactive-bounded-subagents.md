# Use bounded subagents proactively for repository-wide work

status: in_progress
task_types:
  - template_workflow
review_class: B
human_design_required: yes
human_approval_status: approved
write_scope:
  - AGENTS.md
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
context_files:
  - .codex/agents/
  - docs/plan/checked/2026/08/01-15/041-spark-worker-policy.md
  - docs/plan/checked/2026/08/01-15/043-luna-xhigh-evidence-synthesis.md
  - template/.codex/agents/
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Allow the main agent to delegate without a per-task user instruction and require proactive bounded delegation for repository-wide investigations when independent work is available and materially useful.
  - Define positive triggers for multiple independent areas, large or dense sources, cross-spec reconciliation, and validation, security, or orchestration review.
  - Retain local execution for short deterministic work and avoid delegation when coordination cost exceeds its expected value.
  - Preserve non-overlapping write scopes, read-only context boundaries, advisory helper output, and main-agent ownership of integration, validation acceptance, planning, commits, and final reporting.
  - Keep secrets, external writes, destructive actions, authorization decisions, and final high-risk judgment outside delegated authority unless a separate explicit policy grants that authority.
  - Verify the proactive-use rule and its safety boundaries in both the root repository and Copier-generated projects.
  - Pass every critical requirement in fixed median and edge scenarios and preserve the same requirements in a hold-out scenario evaluated by fresh independent subagents.
checked_summary_ja: リポジトリ全体調査では明示指定がなくても境界付きサブエージェントを積極利用し、統合と最終判断は主担当に保持する。

## Context

Repository-wide work must use bounded subagents proactively when independent exploration or review provides material value.

The user explicitly authorized subagent use without a per-task request and requested active use for broad repository work.

## Decisions

- Implement this plan after plans 050 and 051 so orchestration policy and validation use the corrected paths and final Skill content.
- Apply the rule to both the root repository and generated-project orchestration policy.
- Treat repository-wide investigation, independent multi-area analysis, cross-spec reconciliation, and security or regression review as positive delegation triggers.
- Preserve the existing cost gate, role boundaries, concurrency limit, descendant-delegation restrictions in helper profiles, and main-agent ownership.
- Require the final report to state whether subagents were used, their bounded roles, and how the main agent accepted their results.
- Do not modify helper-agent model profiles or add a new helper role for this policy change.
- Keep fixed median, edge, negative-trigger, and hold-out scenarios separate from the policy text, and keep full evaluator output under ignored local artifacts while recording only accepted evidence in the plan.

## Tasks

- [ ] Add the proactive bounded-delegation rule to root and generated agent entrypoints and orchestration guidance.
- [ ] Define positive delegation triggers and explicit cases where local execution remains appropriate.
- [ ] Preserve write-scope, read-only context, external-write, secret, destructive-action, and final-judgment boundaries.
- [ ] Add deterministic root and generated checks for both proactive use and retained safety constraints.
- [ ] Extend smoke and Copier update assertions for the generated policy.
- [ ] Define fixed median, edge, negative-trigger, and hold-out scenarios with a requirements checklist containing critical delegation and non-delegation boundaries.
- [ ] Run fresh independent subagent evaluations, correct one policy theme at a time, and confirm critical requirements pass without hold-out regression.
- [ ] Run required repository, generated-project, and update validation.

## Validation Notes

Pending implementation.
