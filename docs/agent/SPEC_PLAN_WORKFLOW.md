# Plan Workflow

This repository root is a template development repository. It is not a Copier-generated project, so root plan files intentionally use a lighter structure than generated-project plan lifecycle files.

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: active executable tasks.
- `docs/plan/checked.md`: completed-work index.
- `docs/plan/checked/*.md`: durable completion records.

## Agent Log Boundary

- Keep `docs/plan` as the durable summary, decision, validation, and follow-up record.
- Do not store raw agent logs, full command transcripts, large stdout/stderr captures, or compression transcripts inside plan files.
- If log evidence matters, record the run id, manifest path, short summary, and relevant excerpt path.
- Treat `.agent-logs/` runs referenced from `docs/plan` as pinned local evidence.
- Use `SPEC_AGENT_LOGGING.md` and `SPEC_CONTEXT_COMPRESSION.md` when raw logs, run manifests, or large compressed views are in scope.

## Decision Audit Preflight

- Before creating or materially updating an active plan, run decision audit when meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open.
- Use `SPEC_DECISION_AUDIT.md` for trigger rules, output format, and artifact boundaries.
- Keep full decision-audit output in chat, raw logs, handoff research artifacts, dedicated decision artifacts, or `.agent-artifacts/decision-audits/`.
- Do not copy approach matrices, debate transcripts, or long recommendation rationale into `docs/plan/active`.
- After the direction is settled, record only final accepted decisions in the active plan.
- Skip the preflight for small, mechanical, or already-determined changes.

## Active Plan Authoring

- Write active plans as executable instructions for the next agent.
- Prefer English for operational sections, implementation instructions, task lists, file paths, validation notes, and manifest values.
- Use Japanese only for user-facing summaries, `checked_summary_ja`, domain terms, quoted user requirements, or tasks whose scope is Japanese prose.
- Record final accepted decisions in `## Decisions`.
- Do not store alternatives, recommendation matrices, debate transcripts, or long rationale blocks in active plans.
- Put detailed option analysis in chat, raw logs, handoff research artifacts, dedicated decision artifacts, or `.agent-artifacts/decision-audits/`.
- Keep enough context for implementation and validation without preserving the full discussion that produced the plan.

## Rules

- Create or update an active plan before non-trivial edits.
- Keep `plan.md` short.
- Archive completed work to `checked/`.
- Treat checked archives as historical completion records, not current implementation guidance.
- Keep raw log bodies outside `docs/plan`; reference local run manifests instead.
- Keep active plans executable. Use `## Decisions` for final accepted decisions, not full decision-audit output.
- Keep active-plan operational prose in English by default.
