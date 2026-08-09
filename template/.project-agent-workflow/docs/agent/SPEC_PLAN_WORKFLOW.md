# Plan Workflow

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: open executable tasks, including started tasks that are explicitly deferred while an unresolved condition remains.
- `docs/plan/backlog/*.md`: future or condition-waiting work.
- `docs/plan/checked.md`: completed-work index.
- `docs/plan/checked/YYYY/MM/01-15/*.md`: durable completion records completed in the first half of a month.
- `docs/plan/checked/YYYY/MM/16-31/*.md`: durable completion records completed in the second half of a month.
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
- Use handoff files only for real staged transfer.
- Use a single numeric namespace across active, backlog, and checked files.
- Treat checked archives as historical completion records, not current implementation guidance.
- Search `docs/plan/checked.md` or use `.project-agent-workflow/scripts/search-plan-archive.py` before opening full checked archives.
- Preserve durable decisions, validation outcomes, and fallback impact in active or checked records before deleting handoff files.
- Keep README files human-facing; do not put required agent routing policy only in README files.
- Keep raw log bodies outside `docs/plan`; reference local run manifests instead.
- Keep active plans executable. Use `## Decisions` for final accepted decisions, not full decision-audit output.
- Keep active-plan operational prose in English by default.

## Manifest Contract

Required active/backlog fields:

- `status`
- `task_types`
- `review_class`
- `human_design_required`
- `human_approval_status`
- `write_scope`
- `context_files`
- `required_specs`
- `validation`
- `acceptance`
- `checked_summary_ja`

Optional active/backlog fields:

- `target_json`
- `acceptance_focus`
- `completion_deferred_reason`

Rules:

- `review_class` is `A`, `B`, or `C`.
- Class C work requires explicit human approval before implementation.
- `human_design_required` is `yes` only when material architecture, product frame, story, or visual philosophy is in scope.
- `human_approval_status` is `not_required`, `pending`, or `approved`.
- Class C plans must use `pending` or `approved`; backlog or deferred plans may remain `pending`, but promotion to active implementation requires `approved`.
- Every open-plan `task_types` entry must match a route key in `.project-agent-workflow/docs/agent/spec-index.yaml`.
- When work crosses categories, list every matching route in `task_types`.
- `required_specs` must contain `default_reads` plus the union of every listed route's `required` entries.
- Add matching conditional specs when the task or touched paths satisfy their conditions.
- `write_scope` lists paths the implementing agent may edit.
- `context_files` lists additional read-only paths needed to perform the work; use `none` when no additional paths are needed.
- A path must not appear in both `write_scope` and `context_files`.
- `target_json` is optional structured context. JSON edit targets must also appear in `write_scope`.
- `validation` should list commands needed for completion.
- Validate plan command lists with `python3 .project-agent-workflow/scripts/plan_validation_commands.py check-plan <plan>` when plan validation entries are edited manually.
- Validate one manifest and its routed required-spec union with `python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest <plan>`.
- Keep validation entries as single commands, not shell pipelines or compound commands.
- `acceptance_focus` is optional and should stay to one to three short points.
- `checked_summary_ja` is the human-facing Japanese one-line completion summary.
- Keep active-plan bodies parseable by agents. English is preferred for manifest values and operational detail; Japanese is fine for user-facing summaries, domain terms, and `checked_summary_ja`.
- `completion_deferred_reason` is required when `status` is `deferred` and records the unresolved condition that keeps the plan open.
- `human_design_required: yes` requires `review_class: C`.

Lifecycle states:

- Use `status: in_progress` for ongoing work and `status: deferred` for intentionally postponed work.
- A deferred plan remains open and cannot transition to `ready_to_archive`; return it to `in_progress` only after its deferred condition is resolved.
- Use `status: ready_to_archive` only after acceptance and validation evidence are recorded.
- `ready_to_archive` is the only active-plan state that blocks the completion gate.
- Set `ready_to_archive` with `.project-agent-workflow/scripts/complete-plan.sh`, then use `.project-agent-workflow/scripts/finalize-active-plan.sh` as the only archive transition.
- `complete-plan.sh` fails while the manifest is invalid, task checkboxes remain unchecked, or `Validation Notes` are empty or pending.
- `finalize-active-plan.sh` writes `status: checked` into the archived record.
- Archive lint accepts legacy `completed` and `ready_to_archive` values created before terminal-status enforcement; new archives must use `checked`.
- Finalization requires a non-empty `checked_summary_ja`, a non-empty `Validation Notes` section, a matching active index row, and a non-colliding date-based archive path.
- Checked archives using the manifest field names generated before `task_types`, `write_scope`, and `context_files` remain readable as legacy history; open plans must use the current manifest.
- Full plan lint preserves checked archives as historical records without applying the current route keys, required-spec union, or validation-command allowlist retroactively.
- Explicit `check-plan` remains strict, and `run-plan` accepts only a numbered file directly under `docs/plan/active/`; checked validation records are never execution targets.
- After a recorded pre-v1 Copier adoption, open plans may retain the preserved root routing contract and old generic CLI paths only while the migration manifest proves the pre-v1 source and every referenced CLI is an unmodified compatibility bridge to the managed helper.
- A mixed root and managed routing contract, a modified legacy CLI, or an unverified legacy CLI requires manual plan integration.

## Handoff Queue

- Use direct prompts for short-lived helper tasks whose result can be consumed immediately.
- Use `docs/plan/handoffs/<plan-id>-<slug>/` only for staged transfer, cross-session continuity, write-capable work, or structured review.
- Each handoff directory should contain `request.md`; use `result.json` for implementation metadata and `findings.md` for review or research output when useful.
- Assign parallel handoffs only when write scopes do not overlap.
- Preserve durable decisions, validation outcomes, and fallback impact in the active or checked plan before cleaning handoff directories.

## Lifecycle Commands

- Next plan id: `python3 .project-agent-workflow/scripts/lint-plan-docs.py --next-id`
- Next plan id wrapper: `.project-agent-workflow/scripts/next-plan-id.sh`
- Create plan: `.project-agent-workflow/scripts/create-plan.sh active <slug>`
- Promote backlog: `.project-agent-workflow/scripts/promote-plan.sh docs/plan/backlog/NNN-slug.md`
- Mark plan ready to archive: `.project-agent-workflow/scripts/complete-plan.sh docs/plan/active/NNN-slug.md`
- Finalize before final report: `.project-agent-workflow/scripts/finalize-active-plan.sh docs/plan/active/NNN-slug.md`
- Linear sync dry-run: `.project-agent-workflow/scripts/sync-plan-to-linear.sh docs/plan/active/NNN-slug.md --dry-run`
- Completion gate: `.project-agent-workflow/scripts/check-agent-completion.sh`
- Select minimal active-plan context: `.project-agent-workflow/scripts/select-task-context.sh docs/plan/active/NNN-slug.md`
- Machine-readable validation selection: `python3 .project-agent-workflow/scripts/validate-changes.py --print-only --json`
- Machine-readable archive search: `.project-agent-workflow/scripts/search-plan-archive.py --text <term> --json`
- Machine-readable workflow status: `.project-agent-workflow/scripts/workflow-status.sh --json`
- Preview handoff cleanup: `.project-agent-workflow/scripts/clean-handoffs.sh --dry-run`
- Apply handoff cleanup after durable records are saved: `.project-agent-workflow/scripts/clean-handoffs.sh --apply`
- Single-plan manifest check: `python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest docs/plan/active/NNN-slug.md`
- Plan lint wrapper: `.project-agent-workflow/scripts/lint-plan-docs.sh`
- Plan format wrapper: `.project-agent-workflow/scripts/format-plan-docs.sh --check`

These scripts are local-only. External service sync belongs to `SPEC_EXTERNAL_SERVICES.md`.

`.project-agent-workflow/scripts/sync-plan-to-linear.sh` is a generic policy gate. It can render a local dry-run draft without external reads or writes, but read-capable and write-capable modes require `docs/agent/external-services.yaml` plus a project-specific adapter before side effects are possible.
