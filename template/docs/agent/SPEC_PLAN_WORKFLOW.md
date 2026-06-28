# Plan Workflow

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: active executable tasks.
- `docs/plan/backlog/*.md`: future or condition-waiting work.
- `docs/plan/checked.md`: completed-work index.
- `docs/plan/checked/*.md`: durable completion records.
- `docs/plan/handoffs/`: temporary transfer queue.
- `docs/plan/README.md`: human-facing plan overview.
- `docs/plan/backlog/README.md`: human-facing backlog overview.
- `docs/plan/handoffs/README.md`: human-facing handoff overview.

## Agent Log Boundary

- Keep `docs/plan` as the durable summary, decision, validation, and follow-up record.
- Do not store raw agent logs, full command transcripts, large stdout/stderr captures, or compression transcripts inside plan files.
- If log evidence matters, record the run id, manifest path, short summary, and relevant excerpt path.
- Treat `.agent-logs/` runs referenced from `docs/plan` as pinned local evidence.
- Use `SPEC_AGENT_LOGGING.md` and `SPEC_CONTEXT_COMPRESSION.md` when raw logs, run manifests, or large compressed views are in scope.

## README Boundary

- Keep README files human-facing.
- Keep agent-facing operational policy in `docs/agent/SPEC_*.md`.
- If a reusable operational rule appears only in a README, move or mirror it into `docs/agent/` before relying on it.

## Decision Audit Preflight

- Before creating or materially updating an active plan, run decision audit when meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open.
- Use `SPEC_DECISION_AUDIT.md` for trigger rules, output format, and artifact boundaries.
- Keep full decision-audit output in chat, raw logs, handoff research artifacts, dedicated decision artifacts, or `.agent-artifacts/decision-audits/`.
- Do not copy approach matrices, debate transcripts, or long recommendation rationale into `docs/plan/active`.
- After the direction is settled, record only final accepted decisions in the active plan.
- Skip the preflight for small, mechanical, or already-determined changes.

## Rules

- Create or update an active plan before non-trivial edits.
- Keep `plan.md` short.
- Archive completed work to `checked/`.
- Use handoff files only for real staged transfer.
- Use a single numeric namespace across active, backlog, and checked files.
- Treat checked archives as historical completion records, not current implementation guidance.
- Search `docs/plan/checked.md` or use `scripts/search-plan-archive.py` before opening full checked archives.
- Preserve durable decisions, validation outcomes, and fallback impact in active or checked records before deleting handoff files.
- Keep README files human-facing; do not put required agent routing policy only in README files.
- Keep raw log bodies outside `docs/plan`; reference local run manifests instead.
- Keep active plans executable. Use `## Decisions` for final accepted decisions, not full decision-audit output.

## Manifest Contract

Recommended active/backlog fields:

- `status`
- `task_type`
- `review_class`
- `human_design_required`
- `human_approval_status`
- `target_files`
- `target_json`
- `required_specs`
- `validation`
- `acceptance`
- `acceptance_focus`
- `expected_output`
- `checked_summary_ja`
- `completion_deferred_reason`

Rules:

- `review_class` is `A`, `B`, or `C`.
- Class C work requires explicit human approval before implementation.
- `human_design_required` is `yes` only when material architecture, product frame, story, or visual philosophy is in scope.
- `human_approval_status` is `not_required`, `pending`, or `approved`; Class C work must use `approved` before implementation.
- `target_files` should list planned edit or context paths.
- `target_json` is optional structured context. JSON edit targets must also appear in `target_files`.
- `validation` should list commands needed for completion.
- `acceptance_focus` is optional and should stay to one to three short points.
- `checked_summary_ja` is the human-facing Japanese one-line completion summary.
- Keep active-plan bodies parseable by agents. English is preferred for manifest values and operational detail; Japanese is fine for user-facing summaries, domain terms, and `checked_summary_ja`.
- `completion_deferred_reason` is only for intentionally incomplete work or concrete external blockers.

## Handoff Queue

- Use direct prompts for short-lived helper tasks whose result can be consumed immediately.
- Use `docs/plan/handoffs/<plan-id>-<slug>/` only for staged transfer, cross-session continuity, write-capable work, or structured review.
- Each handoff directory should contain `request.md`; use `result.json` for implementation metadata and `findings.md` for review or research output when useful.
- Assign parallel handoffs only when write scopes do not overlap.
- Preserve durable decisions, validation outcomes, and fallback impact in the active or checked plan before cleaning handoff directories.

## Lifecycle Commands

- Next plan id: `python3 scripts/lint-plan-docs.py --next-id`
- Next plan id wrapper: `scripts/next-plan-id.sh`
- Create plan: `scripts/create-plan.sh active <slug>`
- Promote backlog: `scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`
- Complete plan: `scripts/complete-plan.sh docs/plan/active/NNN-slug.md`
- Finalize before final report: `scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`
- Completion gate: `scripts/check-agent-completion.sh`
- Select minimal active-plan context: `scripts/select-task-context.sh docs/plan/active/NNN-slug.md`
- Preview handoff cleanup: `scripts/clean-handoffs.sh --dry-run`
- Apply handoff cleanup after durable records are saved: `scripts/clean-handoffs.sh --apply`
- Plan lint wrapper: `scripts/lint-plan-docs.sh`
- Plan format wrapper: `scripts/format-plan-docs.sh --check`

These scripts are local-only. External service sync belongs to `SPEC_EXTERNAL_SERVICES.md`.
