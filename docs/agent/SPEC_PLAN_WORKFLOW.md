# Plan Workflow

This repository root is a template development repository. It is not a Copier-generated project, so root plan files intentionally use a lighter structure than generated-project plan lifecycle files.

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: active executable tasks.
- `docs/plan/checked.md`: completed-work index.
- `docs/plan/checked/YYYY/MM/01-15/*.md`: durable completion records completed in the first half of a month.
- `docs/plan/checked/YYYY/MM/16-31/*.md`: durable completion records completed in the second half of a month.
- `docs/plan/replanned/YYYY/MM/01-15/*.md` and `16-31/*.md`: historical records of plans replaced by an accepted restructuring contract; these records are not completion evidence.
- `docs/plan/replanned/contracts/*.json`: exact requirement-preservation and successor-mapping contracts for restructured plans.

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
- Archive completed work under `checked/YYYY/MM/01-15/` or `checked/YYYY/MM/16-31/` based on completion date.
- Keep `checked.md` as the machine-readable index for all checked archives, including nested paths.
- Treat checked archives as historical completion records, not current implementation guidance.
- Treat replanned archives as historical replacement records, not successful completion evidence.
- Keep raw log bodies outside `docs/plan`; reference local run manifests instead.
- Keep active plans executable. Use `## Decisions` for final accepted decisions, not full decision-audit output.
- Keep active-plan operational prose in English by default.
- Record completed task checkboxes and non-pending validation evidence, then run `scripts/complete-plan.sh` before `scripts/finalize-active-plan.sh`.
- Treat `status: checked` as the terminal state written by finalization.

## Restructuring Contract

Plan restructuring changes execution boundaries, ordering, implementation methods, or validation methods. It does not change the user requirement baseline. The baseline consists of the user requirements, accepted safety conditions, and every normalized `acceptance` item in the source plan.

- Use `status: replan_required` when the current plan must stop before further implementation, candidate generation or correction, validation, apply, completion, or archival.
- Restructuring is mandatory after scope, required-spec, or security-boundary drift; discovery of multiple independently validatable invariants; a design change after authoritative validation has started; exhaustion of the initial candidate plus two correction rounds; or two parent-direct remediation rounds that still leave a High or Medium independent-review finding.
- Elapsed time is telemetry and a checkpoint signal only. It can prompt review of the plan boundary, but it cannot prove semantic failure or authorize requirement changes.
- Preserve the exact source plan path, source HEAD, source-plan digest, and digest of every normalized source acceptance item in the parent-owned replan contract.
- Map every source acceptance digest to at least one successor plan or integration gate. The integration plan must retain the source acceptance text exactly and prove the combined successors against it.
- A successor may change plan boundaries, ordering, implementation methods, and validation methods. Replacing, weakening, deleting, or adding a user requirement or accepted safety condition requires explicit user authorization recorded separately from the restructuring operation.
- Preserve committed work. Do not reset, stash, delete, commit, or apply product changes as part of restructuring. Record dirty paths and cover each one with a successor write scope before implementation resumes.
- After an atomic restructuring transition, archive the source with terminal `status: replanned`. This state means “replaced while preserving requirements”; it is distinct from successful `checked` completion and prerequisite-based `deferred` work.
- Keep full option analysis and decision matrices outside active plans. Active successors contain only accepted decisions, bounded lineage fields, executable scope, validation, and acceptance.
