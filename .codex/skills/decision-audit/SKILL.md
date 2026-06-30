---
name: decision-audit
description: Identify important unstated decisions before implementation or plan updates. Use when Codex is explicitly asked for decision-audit, unstated important decisions, missing issues, approach comparisons, recommendations with reasons, or when creating or materially updating an active implementation plan where meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open.
---

# Decision Audit

Use this skill to surface meaningful choices before work is committed into an implementation plan or code change.

## Workflow

1. Read the user request.
2. Read the relevant active plan when one exists.
3. Read routed project docs, especially `docs/agent/SPEC_DECISION_AUDIT.md` and `docs/agent/SPEC_PLAN_WORKFLOW.md` when plan lifecycle files are in scope.
4. Separate explicit requirements from inferred gaps.
5. Produce only decision items that can affect implementation, validation, lifecycle, storage, security, or artifact boundaries.
6. Recommend a direction for each item when enough context exists.

Do not invent requirements when context is insufficient. State the missing context and why the decision cannot be resolved.

## Output

Use the user's language for the response. When the user is using Japanese, respond in Japanese.

Use this format:

```text
1. Decision Item
   Explain why this matters.

   A: Approach description.
   B: Approach description.

   Recommended: A
   Reason: Explain the reason.
```

Use `Recommended: Needs user decision` when no approach can be recommended from the available context.

## Plan Boundary

Do not copy the full audit into `docs/plan/active`.

After the user or agent settles the direction, record only final accepted decisions in the active plan. Store the full audit in chat, raw logs, handoff research artifacts, dedicated decision artifacts, or `.agent-artifacts/decision-audits/` when a durable artifact is needed.
