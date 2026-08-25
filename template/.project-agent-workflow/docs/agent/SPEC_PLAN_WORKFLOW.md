# Plan Workflow

## Files

- `docs/plan/plan.md`: short active-work index.
- `docs/plan/active/*.md`: open executable tasks, including started tasks that are explicitly deferred while an unresolved condition remains.
- `docs/plan/backlog/*.md`: future or condition-waiting work.
- `docs/plan/checked.md`: completed-work index.
- `docs/plan/checked/YYYY/MM/01-15/*.md`: durable completion records completed in the first half of a month.
- `docs/plan/checked/YYYY/MM/16-31/*.md`: durable completion records completed in the second half of a month.
- `docs/plan/replanned/YYYY/MM/01-15/*.md` and `16-31/*.md`: historical records of plans replaced by an accepted restructuring contract; these records are not completion evidence.
- `docs/plan/replanned/contracts/*.json`: exact requirement-preservation and successor-mapping contracts for restructured plans.
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

## Implementation Tiers

Classify every change into exactly one tier before creating plan artifacts. Plan weight, review depth, and available stop transitions follow from that tier. Tier selection is a bounded parent decision recorded as `implementation_tier` in the active plan; when two tiers are defensible, choose the higher one.

- Tier 0: one file, reversible, already covered by an existing validation command, with no new external effect and an unchanged security boundary. Implement directly and commit without a plan file.
- Tier 1: bounded multi-file change whose security boundary, validation authority, and external-effect authority are unchanged. Use a short active plan carrying `primary_invariant`, `write_scope`, `validation`, and exactly one `acceptance` item.
- Tier 2: security-boundary change, irreversible effect, external write authority, lifecycle or validation-authority change, or a write scope that cannot be enumerated as exact paths. Use the full manifest contract, review gates, and restructuring contract.

- Escalate a tier as soon as new evidence crosses its boundary, and treat the escalation as a plan update rather than a stop.
- Never lower a recorded tier without explicit user authorization.
- Do not route Tier 0 or Tier 1 work through the restructuring contract. Use the bounded descope transition or stop them instead.

## Rules

- Create or update an active plan before non-trivial edits, except for Tier 0 changes.
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
- `implementation_tier`
- `acceptance_focus`
- `completion_deferred_reason`
- `preservation_scope`
- `primary_invariant`
- `integration_gates`
- `predecessor_plans`
- `replan_source`
- `replan_sources`
- `replan_contract`
- `successor_plans`
- `inherited_acceptance_digests`
- `integration_source_ids`
- `replan_reason_codes`

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
- `preservation_scope` lists exact dirty product paths that restructuring must retain without granting edit, validation, apply, staging, or commit authority. Use `none` when no dirty product path must be retained.
- `context_files` lists additional read-only paths needed to perform the work; use `none` when no additional paths are needed.
- A path must not appear in both `write_scope` and `context_files`.
- A `preservation_scope` entry must be normalized, exact, unique across all restructuring successors, and disjoint from every successor `write_scope`.
- `target_json` is optional structured context. JSON edit targets must also appear in `write_scope`.
- `implementation_tier` is optional for plans authored before tiers existed and is `0`, `1`, or `2` for every new plan. It selects plan weight and the available stop transitions.
- `validation` should list commands needed for completion.
- Validate plan command lists with `python3 .project-agent-workflow/scripts/plan_validation_commands.py check-plan <plan>` when plan validation entries are edited manually.
- Validate one manifest and its routed required-spec union with `python3 .project-agent-workflow/scripts/lint-plan-docs.py --check-manifest <plan>`.
- Keep validation entries as single commands, not shell pipelines or compound commands.
- `acceptance_focus` is optional and should stay to one to three short points.
- `checked_summary_ja` is the human-facing Japanese one-line completion summary.
- Keep active-plan bodies parseable by agents. English is preferred for manifest values and operational detail; Japanese is fine for user-facing summaries, domain terms, and `checked_summary_ja`.
- `completion_deferred_reason` is required when `status` is `deferred` and records the unresolved condition that keeps the plan open.
- `predecessor_plans` lists exact active or checked plan paths whose checked lifecycle state is required before the dependent plan may become `in_progress`.
- Keep a dependent plan `deferred` while any predecessor entry is an active path, including an active path whose matching plan has already moved to the checked archive but has not yet been refreshed in the dependent manifest.
- Before changing a dependent plan to `in_progress`, replace every active predecessor path with the exact checked archive path recorded in `docs/plan/checked.md`.
- Reject missing, duplicate, non-normalized, stale checked, cross-id, or cyclic active predecessor edges.
- `successor_plans` records immutable restructuring lineage and does not define operational execution order.
- Schema-1 and schema-2 successor plans use singular `replan_source`. Schema-3 coupled successors use ordered `replan_sources` and explicit `integration_source_ids`. Both forms use `primary_invariant`, `integration_gates`, `replan_contract`, `successor_plans`, and `inherited_acceptance_digests` as exact lineage contracts. Legacy plans may omit them.
- `replan_reason_codes` is a bounded list and is required when `status` is `replan_required`.
- `human_design_required: yes` requires `review_class: C`.

Lifecycle states:

- Use `status: in_progress` for ongoing work and `status: deferred` for intentionally postponed work.
- Use `status: replan_required` when the current plan must stop before further implementation, candidate generation or correction, validation, apply, completion, or archival.
- A deferred plan remains open and cannot transition to `ready_to_archive`; return it to `in_progress` only after its deferred condition is resolved.
- An authoritative validation failure enters the parent-owned `diagnosis_required` execution state before any repair classification. Bind it to the unchanged plan and source HEAD, execution-lifecycle and validation-report digests, exact failed-operation digest, and observed exit status. Candidate mode also binds the exact failed candidate lifecycle, manifest, patch, and writable-attempt identity; parent-direct mode must not claim candidate artifacts.
- While `diagnosis_required` is active, permit only bounded parent-owned read-only reproduction and append-only `confirmed`, `inconclusive`, or `disputed` diagnosis evidence. Reject worker, correction, validation, apply, completion, archive, and repair-plan operations before prerequisites or effects.
- Require a fresh independent-review receipt and reproduction-evidence digest for each diagnosis result, store no raw output or credential, and let only `confirmed` evidence name exactly one affected invariant. Inconclusive or disputed evidence remains stopped; a confirmed diagnosis proceeds only through the existing `repair_required` or `replan_required` classification.
- When one independently repairable defect has bounded write and validation scope and leaves unchanged source-plan scope, unchanged validation authority, unchanged invariant boundaries, unchanged source acceptance, unchanged safety conditions, and unchanged external-effect authority, record `repair_required` in the execution ledger, stop that run, keep the source plan `deferred`, and create a separate bounded repair plan.
- Never reopen a `repair_required` execution run. After the repair plan is checked, revalidate the unchanged inputs, return the source plan and index to `in_progress`, and initialize a fresh plan digest, source HEAD, candidate lifecycle, and execution ledger.
- Do not use independent repair for requirement, authority, scope, specification, security-boundary, or acceptance-mapping change. Route those changes through explicit user authorization or `replan_required` as applicable.
- Use `status: ready_to_archive` only after acceptance and validation evidence are recorded.
- `ready_to_archive` records that the completion gate passed and is the only active state eligible for checked finalization.
- `replan_required` cannot transition to `ready_to_archive`; it must be replaced through the restructuring lifecycle or returned to execution only after the trigger is disproved and the reversal is recorded.
- Set `ready_to_archive` with `.project-agent-workflow/scripts/complete-plan.sh`, then use `.project-agent-workflow/scripts/finalize-active-plan.sh` as the only archive transition.
- `complete-plan.sh` fails while the manifest is invalid, task checkboxes remain unchecked, or `Validation Notes` are empty or pending.
- `finalize-active-plan.sh` writes `status: checked` into the archived record.
- Archive lint accepts legacy `completed` and `ready_to_archive` values created before terminal-status enforcement; new archives must use `checked`.
- Finalization requires a non-empty `checked_summary_ja`, a non-empty `Validation Notes` section, a matching active index row, and a non-colliding date-based archive path.
- Checked archives using the manifest field names generated before `task_types`, `write_scope`, and `context_files` remain readable as legacy history; open plans must use the current manifest.
- Full plan lint preserves checked archives as historical records without applying the current route keys, required-spec union, or validation-command allowlist retroactively.
- Explicit `check-plan` remains strict, and `run-plan` accepts only a numbered file directly under `docs/plan/active/`; checked validation records are never execution targets.
- `status: replanned` is a terminal historical replacement state, not successful completion evidence. Replanned records live under the date-partitioned `docs/plan/replanned/` archive and cannot be execution targets.
- After a recorded pre-v1 Copier adoption, open plans may retain the preserved root routing contract and old generic CLI paths only while the migration manifest proves the pre-v1 source and every referenced CLI is an unmodified compatibility bridge to the managed helper.
- A mixed root and managed routing contract, a modified legacy CLI, or an unverified legacy CLI requires manual plan integration.

## Bounded Descope

A bounded descope reduces the acceptance set of the current plan without restructuring it. Use it when review findings show that the plan is too wide, not that its design is wrong.

- Record `descope_required` in the parent-owned execution ledger through one `descope_classification` event bound to an independent-review receipt, the unchanged plan path, plan digest, source HEAD, primary invariant, and the current candidate lifecycle.
- Classification requires a bounded write scope and unchanged source scope, validation authority, invariant boundaries, primary invariant, safety conditions, and external-effect authority, with exactly one independent invariant. Any drift escalates to the matching hard replan reason instead of authorizing a descope.
- Partition every source acceptance digest exactly once into `retained_acceptance_digests` and `deferred_acceptance_digests`, preserving source order. Retain at least one item and defer at least one item. Losing, duplicating, reordering, or adding an acceptance digest is rejected.
- Move the deferred acceptance items to the exact `deferred_backlog_path` backlog plan. A descope never deletes a requirement; it only changes when that requirement is executed.
- `descope_required` stops candidate generation, correction, validation, apply, completion, and archival for that execution run. Only the `descope_plan` gate stays open, and the stopped run is never reopened.
- A descope creates no replan contract, no successor lineage, and no additional active plan. Keep it as the default exit for Tier 0 and Tier 1 work.

### Review-Finding Budgets

- Classify review findings before selecting a stop state: implementation findings are `acceptance_unmet`, `focused_validation_failed`, and `evidence_incomplete`; boundary findings are `out_of_scope_change`, `required_spec_missed`, and `integration_contract_mismatch`; the design finding is `multiple_invariants_coupled`.
- Implementation findings have a budget of 4 correction-requested or rejected attempt closures. Boundary findings have a budget of 2 correction-requested or rejected attempt closures. Accepted closures do not count.
- A `parent_review` event carries finding severities but no review reason code, so two parent-direct remediation rounds that still leave a High or Medium finding record `descope_pending` with `parent_remediation_budget_exhausted` instead of asserting a finding class.
- Exhausting an implementation or boundary finding budget records `descope_pending`, with `implementation_finding_budget_exhausted` or `boundary_finding_budget_exhausted`. Only `descope_classification` or a hard drift event may follow.
- `multiple_invariants_coupled` remains an immediate `replan_required` reason. Any scope, spec, security-boundary, or post-authoritative design drift still escalates to `replan_required`.

## Restructuring Contract

Plan restructuring changes execution boundaries, ordering, implementation methods, or validation methods. It does not change the user requirement baseline. The baseline consists of the user requirements, accepted safety conditions, and every normalized `acceptance` item in the source plan.

- Restructuring is mandatory after scope, required-spec, or security-boundary drift; discovery of multiple independently validatable invariants; a design change after authoritative validation has started; or exhaustion of the initial candidate plus two correction rounds.
- Elapsed time is telemetry and a checkpoint signal only. It cannot prove semantic failure or authorize requirement changes.
- Preserve the exact source plan path, source HEAD, source-plan digest, and digest of every normalized source acceptance item in a parent-owned replan contract.
- Map every source acceptance digest to at least one successor plan or integration gate. The integration plan retains the source acceptance text exactly and proves the combined successors against it.
- Successors may change plan boundaries, ordering, implementation methods, and validation methods. Replacing, weakening, deleting, or adding a user requirement or accepted safety condition requires explicit user authorization recorded separately from restructuring.
- Preserve committed work. Do not reset, stash, delete, commit, or apply product changes during restructuring.
- Record every dirty product path exactly once across successor `preservation_scope` fields. Preservation proves retention only and never authorizes candidate generation, validation, apply, staging, or commit effects.
- Reject missing, duplicate, overlapping, non-normalized, or silently dropped preservation entries. Continue verifying schema-1 contracts created before `preservation_scope` without reinterpreting their historical write scopes as the new preservation authority.
- Keep full option analysis outside active plans. Active successors contain only accepted decisions and executable instructions.

### Coupled Lineage Reconstruction

- Use a schema-3 contract when one stopped contract successor and one or more immutable dependent successors must be replaced together. Keep `sources` ordered and non-empty, and bind each source's live content digest, deterministically derived `replan_required` digest, acceptance records, archive path, reason codes, and owning historical contract path and digest.
- Derive a dependent source's stopped bytes only by changing `status`, `completion_deferred_reason`, and `replan_reason_codes`. Preserve every other manifest field and body byte.
- Require each source after the first to depend directly or transitively on an earlier source in the same transaction. Validate every source as one exact live successor of an already verified immutable contract.
- Use one ordered successor graph. Schema-3 successors declare `replan_sources`, `replan_contract`, per-source acceptance mappings, and `integration_source_ids`; each source must have exactly one integration successor, while one integration successor may cover several sources.
- Require the designated integration successor for each source to map that source's complete acceptance digest list in source order. Reject missing, duplicate, reordered, foreign, or partial mappings even when other successors collectively cover the omitted acceptance.
- Separately authorized prerequisite plans are not contract successors and carry no inherited source acceptance digest. Keep them ordered, allow each prerequisite to depend only on an earlier prerequisite, require every prerequisite to reach a mapped successor, and bind their lifecycle and validation projection to the schema-3 contract.
- Permit `kind: rebind` only in the creating reconstruction transaction and `kind: activation` only in a later standalone operation. Initial rebindings may target only exact reference tokens owned by the source lineage and replace them with exact transaction-created plan, contract, archive, or write-scope tokens; reject prose, field-header, arbitrary checked-plan, or unrelated-path replacement.
- Permit validation and witness path rebinding only for a project-admitted semantic path pair. Preserve every non-path command argument, retain every transformed focused and authoritative command as an ordered minimum, reproduce each witness exactly, and reject an otherwise allowlisted but unadmitted substitute.
- Initial rebindings must preserve status, primary invariant, acceptance, write scope, preservation scope, task types, required specs, implementation classifications, review class, human approval fields, lineage fields, and every byte outside the declared token replacements.
- Append rebind records to `docs/plan/replanned/baselines/live-successor-rebinds-v1.json`. Each record binds the owning contract digest, plan path, original and updated content, prior effective validation projection, exact replacements, resulting validation projection, and its own digest. The committed record sequence is an immutable prefix.
- Re-authorize every durable activation record during project verification; reproducing its replacement bytes is not sufficient. Recheck same-id checked-archive resolution across manifest and body references before accepting the record.
- Compute effective live validation authority from the verified schema-1 companion or schema-2/schema-3 contract projection, then apply one gap-free and fork-free rebind chain in record order. After the final record, permit only the reachable status lifecycle, existing task markers changing from `[ ]` to `[x]`, and a bounded append-only final `Validation Notes` section; preserve every other byte.
- Apply the same exact lifecycle evolution to unrebound active or checked schema-2/schema-3 successors and prerequisites. Preserve legacy verification only for an exact committed already-stopped source while an older single-source nested replan consumes it.
- Canonical `replan_required` state requires bounded `replan_reason_codes` and must not retain `completion_deferred_reason`.
- A later activation record may replace active predecessor, context, integration-gate, or body path tokens only with the same plan id's exact checked archive and must resolve every remaining active plan path before entering `in_progress`. It may move one exact path from `preservation_scope` to the end of `context_files` only when exactly one checked predecessor owns the path in `write_scope`, its checked commit adds or changes the blob, and the clean worktree and index bytes equal that commit.
- Treat the committed replanned index bytes as an immutable canonical prefix and every committed contract and archive as immutable bytes. Reject any noncanonical index header, row framing, or unbound text; bind the current index and historical file identities into validation and the journal, then recheck them before the journal, before the commit point, and during recovery.
- Under the project lifecycle lock, verify the current project, build and durably verify the complete prospective project state in isolation, bind every transaction original, and recheck the source HEAD plus the exact dirty candidate status, index, type, mode, link count, identity, and content before any write and before the commit point.
- Serialize Git-aware ref and index mutation across the transaction. Persist a mode-0600 Git-local journal that binds the source HEAD, specification digest, exact dirty snapshot, every original and target byte digest, deterministic operation order, phase, commit point, and journal identity.
- Before the commit point, recovery durably enters `rolling_back`, records reverse-operation progress after every restored path, resumes interrupted rollback idempotently, restores every original byte, and removes and fsyncs transaction temporaries. At or after the commit point, recovery uses only monotonic `commit_point`, `replaying`, `verifying`, and `complete` phases, enforces phase-specific content and progress invariants, completes target writes idempotently, and reruns durable verification. Reject stale HEAD or candidates, impossible phase state, ambiguous content, non-confined journal identity, symlinks, hard links, and unsafe file modes.
- Run a coupled transaction with `python3 .project-agent-workflow/scripts/restructure-plan.py <schema-3-spec.json>`. Recover only with `python3 .project-agent-workflow/scripts/restructure-plan.py --recover <journal-path> --journal-id <sha256-identity>`.

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
