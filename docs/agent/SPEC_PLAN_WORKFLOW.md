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
- Record `implementation_tier` in every active plan.
- Keep `plan.md` short.
- Archive completed work under `checked/YYYY/MM/01-15/` or `checked/YYYY/MM/16-31/` based on completion date.
- Keep `checked.md` as the machine-readable index for all checked archives, including nested paths.
- Treat checked archives as historical completion records, not current implementation guidance.
- Treat replanned archives as historical replacement records, not successful completion evidence.
- Treat `predecessor_plans` as operational execution order and `successor_plans` only as immutable restructuring lineage.
- Keep a dependent plan `deferred` while any declared predecessor still uses an active-plan path.
- Before changing a dependent plan to `in_progress`, replace every active predecessor path with the exact checked archive path recorded in `docs/plan/checked.md`.
- Reject missing, duplicate, non-normalized, stale checked, cross-id, or cyclic active predecessor edges.
- Keep raw log bodies outside `docs/plan`; reference local run manifests instead.
- Keep active plans executable. Use `## Decisions` for final accepted decisions, not full decision-audit output.
- Keep active-plan operational prose in English by default.
- Record completed task checkboxes and non-pending validation evidence, then run `scripts/complete-plan.sh` before `scripts/finalize-active-plan.sh`.
- Treat `status: checked` as the terminal state written by finalization.

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

- Use `status: replan_required` when the current plan must stop before further implementation, candidate generation or correction, validation, apply, completion, or archival.
- A canonically stopped plan carries `status: replan_required`, a non-empty unique bounded `replan_reason_codes` list, and no `completion_deferred_reason`. Reject a missing, empty, duplicate, unknown, or non-string reason value with a bounded lifecycle error.
- Require every durable schema-1, schema-2, and schema-3 contract `reason_codes` list to be bounded and to equal its canonical source manifest `replan_reason_codes` exactly. Apply the same checks to nested historical contracts and to schema-3 prerequisite plans.
- Compare lifecycle evolution by removing only the parsed lifecycle field bytes: the exact scalar line, or the exact list field header and its parsed list-item lines. Treat comments, blank-line placement, unknown instructions, and every other unparsed byte as protected, both when comparing and when deriving a stopped source.
- Keep the legacy compatibility route for historical lineage shape only. It never exempts a plan from canonical stopped metadata.
- Compare the parsed manifest fields as well as the projected bytes when validating lifecycle evolution, and reject any change to a non-lifecycle field. Byte equality alone does not prove that a protected field kept its parsed value.
- Apply the canonical stopped rules to a durable contract's embedded source content with no grandfather clause. A contract that records a noncanonical stopped state has always been invalid. Because committed contract bytes and the committed replanned index prefix are both immutable, such a contract has no in-band repair: it can only be corrected by rewriting the affected history outside this workflow. Never weaken verification to accept it.
- Restructuring is mandatory after scope, required-spec, or security-boundary drift; discovery of multiple independently validatable invariants; a discovery after authoritative validation that requires changing source-plan boundaries, implementation or validation methods, validation authority, or acceptance mapping; or exhaustion of the initial candidate plus two correction rounds.
- Elapsed time is telemetry and a checkpoint signal only. It can prompt review of the plan boundary, but it cannot prove semantic failure or authorize requirement changes.
- Preserve the exact source plan path, source HEAD, source-plan digest, and digest of every normalized source acceptance item in the parent-owned replan contract.
- Map every source acceptance digest to at least one successor plan or integration gate. The integration plan must retain the source acceptance text exactly and prove the combined successors against it.
- A successor may change plan boundaries, ordering, implementation methods, and validation methods. Replacing, weakening, deleting, or adding a user requirement or accepted safety condition requires explicit user authorization recorded separately from the restructuring operation.
- Preserve committed work. Do not reset, stash, delete, commit, or apply product changes as part of restructuring.
- Record every dirty product path exactly once across successor `preservation_scope` fields. Each entry is one normalized exact path, not a directory prefix.
- Keep `preservation_scope` disjoint from every successor `write_scope`. Preservation proves retention only and never authorizes candidate generation, validation, apply, staging, or commit effects.
- Reject missing, duplicate, overlapping, non-normalized, or silently dropped preservation entries. Continue verifying schema-1 contracts created before `preservation_scope` without reinterpreting their historical write scopes as the new preservation authority.
- After an atomic restructuring transition, archive the source with terminal `status: replanned`. This state means “replaced while preserving requirements”; it is distinct from successful `checked` completion and prerequisite-based `deferred` work.
- Keep full option analysis and decision matrices outside active plans. Active successors contain only accepted decisions, bounded lineage fields, executable scope, validation, and acceptance.

### Successor Backlog Deferral

- A replan successor may be deferred to `docs/plan/backlog/` with `status: backlog` instead of being restructured again. Deferral changes location and priority only; it never changes lineage.
- Keep the successor path recorded in the replan contract exactly as created. That path is immutable identity, so backlog residence never rewrites it and no new contract is required.
- Keep `acceptance`, `inherited_acceptance_digests`, `replan_sources`, `replan_contract`, `write_scope`, and `preservation_scope` byte-identical to the contract. Remove `completion_deferred_reason` and `replan_reason_codes`, which describe a stopped active lifecycle.
- Resolve every successor to exactly one of the active index, `docs/plan/backlog/`, the checked archive, or the replanned archive. Presence in two locations, or in none, is rejected.
- Reactivate a deferred successor by moving it back under `docs/plan/active/`, restoring an active status, and re-adding its active index row.

### Coupled Lineage Reconstruction

- Use a schema-3 contract when one stopped source plan and one or more immutable dependent plans must be replaced together. Keep `sources` ordered and non-empty, and bind each source's live content digest, deterministically derived `replan_required` digest, acceptance records, archive path, reason codes, and, for a contract-successor source, its owning historical contract path and digest.
- Derive a dependent source's stopped bytes only by changing `status`, `completion_deferred_reason`, and `replan_reason_codes`. Preserve every other manifest field and body byte.
- Require the first source to already carry canonical `replan_required` bytes, and require each source after the first to depend directly or transitively on an earlier source in the same transaction.
- Declare each source's route with an explicit `source_kind` of `contract_successor` or `direct_active`, and validate the source only against that declared route. Never infer the direct-active route after contract-successor verification fails.
- Validate a `contract_successor` source as one exact live successor of an already verified immutable contract.
- Validate a `direct_active` source as one exact active plan that appears once in the active index, is unclaimed by every verified contract, resolves to no other lifecycle location, and carries no replan lineage field. A direct-active source binds no owning contract path or digest.
- Allow contract-successor and direct-active sources in one ordered transaction only when each source independently satisfies its declared route and no plan path is claimed twice.
- Emit `source_kind` in every newly created schema-3 contract, and keep verifying a committed schema-3 source record that predates the discriminant as a contract successor in its committed shape.
- Use one ordered successor graph. Schema-3 successors declare `replan_sources`, `replan_contract`, per-source acceptance mappings, and `integration_source_ids`; each source must have exactly one integration successor, while one integration successor may cover several sources.
- Require the designated integration successor for each source to map that source's complete acceptance digest list in source order. Reject missing, duplicate, reordered, foreign, or partial mappings even when other successors collectively cover the omitted acceptance.
- Separately authorized prerequisite plans are not contract successors and carry no inherited source acceptance digest. Keep them ordered, allow each prerequisite to depend only on an earlier prerequisite, require every prerequisite to reach a mapped successor, and bind their lifecycle and validation projection to the schema-3 contract.
- Permit `kind: rebind` only in the creating reconstruction transaction and `kind: activation` only in a later standalone operation. Initial rebindings may target only exact reference tokens owned by the source lineage and replace them with exact transaction-created plan, contract, archive, or write-scope tokens; reject prose, field-header, arbitrary checked-plan, or unrelated-path replacement.
- Permit validation and witness path rebinding only for a repository-admitted semantic path pair. Preserve every non-path command argument, retain every transformed focused and authoritative command as an ordered minimum, reproduce each witness exactly, and reject an otherwise allowlisted but unadmitted substitute.
- Initial rebindings must preserve status, primary invariant, acceptance, write scope, preservation scope, task types, required specs, implementation classifications, review class, human approval fields, lineage fields, and every byte outside the declared token replacements.
- Append rebind records to `docs/plan/replanned/baselines/live-successor-rebinds-v1.json`. Each record binds the owning contract digest, plan path, original and updated content, prior effective validation projection, exact replacements, resulting validation projection, and its own digest. The committed record sequence is an immutable prefix.
- Re-authorize every durable activation record during repository verification; reproducing its replacement bytes is not sufficient. Recheck same-id checked-archive resolution across manifest and body references before accepting the record.
- Compute effective live validation authority from the verified schema-1 companion or schema-2/schema-3 contract projection, then apply one gap-free and fork-free rebind chain in record order. After the final record, permit only the reachable status lifecycle, existing task markers changing from `[ ]` to `[x]`, and a bounded append-only final `Validation Notes` section; preserve every other byte.
- Apply the same exact lifecycle evolution to unrebound active or checked schema-2/schema-3 successors and prerequisites. Preserve legacy verification only for an exact committed already-stopped source while an older single-source nested replan consumes it.
- Canonical `replan_required` state requires bounded `replan_reason_codes` and must not retain `completion_deferred_reason`.
- A later activation record may replace active predecessor, context, integration-gate, or body path tokens only with the same plan id's exact checked archive and must resolve every remaining active plan path before entering `in_progress`. It may move one exact path from `preservation_scope` to the end of `context_files` only when exactly one checked predecessor owns the path in `write_scope`, its checked commit adds or changes the blob, and the clean worktree and index bytes equal that commit.
- Treat the committed replanned index bytes as an immutable canonical prefix and every committed contract and archive as immutable bytes. Reject any noncanonical index header, row framing, or unbound text; bind the current index and historical file identities into validation and the journal, then recheck them before the journal, before the commit point, and during recovery.
- Under the repository lifecycle lock, verify the current repository, build and durably verify the complete prospective repository state in isolation, bind every transaction original, and recheck the source HEAD plus the exact dirty candidate status, index, type, mode, link count, identity, and content before any write and before the commit point.
- Serialize Git-aware ref and index mutation across the transaction. Persist a mode-0600 Git-local journal that binds the source HEAD, specification digest, exact dirty snapshot, every original and target byte digest, deterministic operation order, phase, commit point, and journal identity.
- Before the commit point, recovery durably enters `rolling_back`, records reverse-operation progress after every restored path, resumes interrupted rollback idempotently, restores every original byte, and removes and fsyncs transaction temporaries. At or after the commit point, recovery uses only monotonic `commit_point`, `replaying`, `verifying`, and `complete` phases, enforces phase-specific content and progress invariants, completes target writes idempotently, and reruns durable verification. Reject stale HEAD or candidates, impossible phase state, ambiguous content, non-confined journal identity, symlinks, hard links, and unsafe file modes.
- Run a coupled transaction with `python3 scripts/restructure-plan.py <schema-3-spec.json>`. Recover only with `python3 scripts/restructure-plan.py --recover <journal-path> --journal-id <sha256-identity>`.

## Independent Repair Prerequisite

An authoritative validation failure does not itself authorize a repair plan.

- Record the failed authoritative validation as `diagnosis_required` in the parent-owned execution ledger before performing any further lifecycle operation.
- Bind the failure record to the unchanged plan and source HEAD, execution-lifecycle digest, validation-report digest, exact failed-operation digest, and observed exit status. In candidate mode, also bind the exact failed candidate lifecycle, manifest, patch, and writable-attempt identity; parent-direct mode must not claim candidate artifacts.
- While `diagnosis_required` is active, permit only bounded parent-owned read-only reproduction and append-only diagnosis evidence. Reject worker, correction, validation, apply, completion, archive, and repair-plan operations before their prerequisites or repository effects.
- Require each diagnosis result to be `confirmed`, `inconclusive`, or `disputed`, bind it to a fresh independent-review receipt and reproduction-evidence digest, and store no command body, raw output, environment value, or credential in the ledger.
- Only a `confirmed` result may name exactly one affected invariant and proceed to the existing repair classification. `inconclusive` and `disputed` results remain stopped, and diagnosis attempts are bounded.
- After confirmation, classify the unchanged boundary evidence through the existing `repair_required` or `replan_required` path. Never create or authorize a numbered repair plan directly from the failure report or an unconfirmed diagnosis.

- Use the execution-ledger state `repair_required` only for one observed defect whose write and validation scope is bounded, whose repair can be accepted independently, and whose classification evidence proves unchanged source-plan scope, unchanged validation authority, unchanged invariant boundaries, unchanged source acceptance, unchanged safety conditions, and unchanged external-effect authority.
- `repair_required` stops candidate generation, correction, validation, apply, completion, and archival for that execution run. It never authorizes reuse or reopening of the stopped run.
- Keep the source plan and active index at `status: deferred` with a concrete prerequisite. Create a separate numbered active repair plan without copying or rewriting source acceptance, and do not create a replan contract.
- After the repair plan is checked, revalidate the unchanged requirements, safety conditions, scope, validation authority, and external-effect authorization. Return the source plan and index to `in_progress` and initialize a fresh source-plan digest, source HEAD, candidate lifecycle, and execution ledger.
- Requirement, authority, or security-boundary change is not an independent repair and requires the applicable hard replan or explicit user-authorization path.
