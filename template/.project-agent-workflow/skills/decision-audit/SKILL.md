---
name: decision-audit
description: Identify important unstated decisions before implementation or plan updates. Use when Codex is explicitly asked for decision-audit, unstated important decisions, missing issues, approach comparisons, recommendations with reasons, or when creating or materially updating an active implementation plan where meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open.
---

# Decision Audit

1. Read the user request, the relevant active plan when one exists, `.project-agent-workflow/docs/agent/spec-index.yaml`, and its routed project specs.
2. Read `.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md` directly.
3. Read `.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` when plan lifecycle files are in scope.
4. Separate explicit requirements from inferred gaps.
5. Include only choices that can materially affect implementation, validation, lifecycle, storage, security, or artifact boundaries.
6. Compare viable approaches and recommend a direction when the available context supports one.
7. Preserve unresolved decisions when user input or external facts are required.

Follow `SPEC_DECISION_AUDIT.md` for output language and format, skip conditions, artifact boundaries, and active-plan conversion.

Do not invent requirements or copy the full audit into `docs/plan/active`.
