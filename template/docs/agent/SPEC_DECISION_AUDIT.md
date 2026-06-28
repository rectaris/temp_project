# Decision Audit

Decision audit identifies important choices that are not explicit in the request, plan, or routed project docs.

It is analysis for deciding direction. It is not an implementation plan and must not be copied in full into `docs/plan/active`.

## When To Run

Run a decision audit when the user explicitly asks for any of:

- `decision-audit`
- unstated important decisions
- missing decisions or unresolved issues
- multiple approaches with a recommendation
- recommendation reasons before implementation

Run a decision audit automatically before creating or materially updating an active plan when meaningful choices remain open in any of these areas:

- architecture or design boundaries
- storage, retention, or artifact location
- validation scope or acceptance gates
- lifecycle and ownership
- security, privacy, secrets, or access
- generated-file or template boundaries
- raw logs, summaries, compressed views, or evidence paths

## When To Skip

Skip decision audit when the task is small, mechanical, and already determined.

Examples:

- fix a typo
- run a named command
- apply a clearly specified single-file edit
- implement an active plan whose decisions are already complete
- answer a narrow factual question without changing repository artifacts

## Method

1. Read the user request.
2. Read the relevant active plan when one exists.
3. Read `docs/agent/spec-index.yaml` and the routed required specs.
4. List explicit requirements before inferred gaps.
5. Include only decisions that can change implementation, validation, lifecycle, storage, security, or artifact boundaries.
6. Compare viable approaches for each decision.
7. Recommend a direction when enough context exists.
8. Mark unresolved items clearly when user input or external facts are required.

Do not infer a decision only because more detail could exist. Include it only when choosing differently would materially change the work.

## Output Format

Use the user's language for the audit response. English labels are acceptable in reusable prompts, but Japanese output is allowed when the user communicates in Japanese.

Use numbered decision items:

```text
1. Decision Item
   Explain why this matters.

   A: Approach description.
   B: Approach description.

   Recommended: A
   Reason: Explain the reason.
```

Use `Recommended: Needs user decision` when available context is insufficient.

## Artifact Boundary

Full decision-audit output belongs in one of:

- chat
- raw agent logs
- handoff research artifacts
- dedicated decision artifacts
- `.agent-artifacts/decision-audits/`

Full decision-audit output does not belong in `docs/plan/active`.

After the direction is accepted, write only final decisions into the active plan. Do not preserve approach matrices, debate transcripts, or long recommendation rationale in active plans.

## Active Plan Conversion

When audit outcomes affect an active plan:

1. Keep the plan written as executable agent instructions.
2. Add only final decisions to the `## Decisions` section.
3. Convert recommendations into direct instructions when accepted.
4. Link or reference a durable audit artifact only when later agents need the full analysis.
5. Do not require later agents to read the full audit unless it contains necessary evidence not captured by final decisions.
