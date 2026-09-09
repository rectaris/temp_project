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

## Active Plan Index

- Write `docs/plan/plan.md` in exactly one of two representations. The empty index is the `# Active Plan` title, one blank line, and `No active development items.`, closed by one trailing newline. The populated index is the same title, one blank line, the actual-tab `id path status` header, and one or more actual-tab rows, closed by one trailing newline.
- Treat every other nonempty document as invalid. Literal backslash-t text, a blank file, a header without rows, rows without the header, content before or after the selected representation, repeated empty markers, and an empty marker mixed with a header or a row are rejected, never read as an empty index.
- Validate each row for a three-digit id, a normalized active plan path, an id that matches its file name, an allowed status, and unique ids and paths. A reader that resolves the repository also requires the referenced plan file and a manifest status equal to the row status.
- Parse the complete index before the first repository mutation of a create, promotion, status-change, completion, finalization, or restructuring operation. Report the first concrete fault and leave plan, index, archive, and checked-index bytes unchanged.
- Never auto-repair or partially parse an invalid index. A canonical writer accepts fully parsed rows only and emits the single canonical representation of its row set.

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

## Plan Admission Contract

A numbered plan is implementation-start authorization. Admission decides whether that authorization may be granted, and it is checked before the plan becomes an active implementation instruction.

- `plan_purpose` records the repository-changing implementation purpose authorized for one numbered plan. The only admitted value is `implementation`.
- `feasibility_evidence` records the bounded pre-activation evidence that the selected implementation method can finish within the declared scope. Each entry is a JSON object with exactly `kind` and `evidence`. The admitted kinds are `reproduced_defect`, `existing_mechanism`, `bounded_prototype`, and `mechanical_transformation`. Record between one and eight entries, each at most 400 bytes.
- `completion_conditions` records the plan-specific behavior predicates this numbered plan must establish. Record between one and eight entries, each at most 400 bytes. Inherited `acceptance` items stay unchanged, and completion conditions never replace them.
- `completion_witness_map` maps each completion condition to its witness. Each entry is a JSON object with exactly `condition_sha256` and `witness`. The entries appear in source order and cover every condition exactly once, bound by the SHA-256 digest of the condition text. Each `witness` must be a command already declared in `focused_validation`; an authoritative-only witness is refused.
- Reject a placeholder value such as `TBD`, `TODO`, `none`, or an empty string in any admission field, and reject feasibility evidence that only promises a separate numbered feasibility plan.
- Refuse admission when `write_scope` declares no path outside plan-lifecycle records. A scope confined to `docs/plan/`, `.agent-logs/`, or `.agent-artifacts/` is not implementation work.
- Keep investigation, feasibility discovery, value evaluation, re-verification, stopping, candidate preservation, and execution-context reset outside numbered plans. They remain unnumbered evidence or lifecycle operations.
- Do not add the admission fields to the globally required manifest field set. Pre-policy active, backlog, checked, replanned, and shelved plans stay readable without a migration, because admission is enforced at the creation, promotion, and reconstruction boundaries instead of by changing historical bytes.

## Checked Authoring Input

A plan file is a rendering of one authoring input, not a document assembled by hand. The input is a single UTF-8 JSON object of at most 256 KiB that names, with explicit identifiers, every requirement the plan serves, the write paths it may touch, the completion conditions it must establish, the acceptance items it inherits, and the witness command claimed for each condition and each acceptance item.

- Author a plan with `python3 scripts/create-root-plan.py` in this repository and with `.project-agent-workflow/scripts/create-plan.sh` in a generated project. Both commands render through one shared library, so the two profiles differ only in the plan schema they emit.
- `check` reads the input, reports the complete requirement-to-scope-to-condition-to-witness correspondence with every derived digest, and performs no repository write. `write` accepts the digest that `check` printed and refuses to render when the input bytes have changed since they were checked, so the rendered plan is always the plan that was reviewed.
- Every requirement claims at least one write path, at least one completion condition, and at least one acceptance item, and every declared write path, completion condition, and acceptance item is claimed by exactly one requirement. An unclaimed entry and a doubly claimed entry are both refused, so `write_scope`, `focused_validation`, `completion_witness_map`, and `validation_witness_map` are derived from the same coverage rather than restated.
- All digests are derived from the input text. A caller-supplied `condition_sha256` or `acceptance_sha256` is refused, because a plan whose digests can be asserted rather than computed cannot bind its own conditions.
- The check is deterministic and structural. It proves references, bounds, uniqueness, and derived digests; it never decides whether a witness command establishes the condition it is claimed for. The report states that boundary, and its `claimed-witness-behavior` lines are caller text that still requires human or reviewer judgment. Two inputs that differ only in claim wording therefore reach the same structural decision.
- Rendering reads the active plan index before it writes, and a malformed index stops the operation with no plan file and no index change. When the index write fails after the plan file exists, the plan file is removed, so a rendered plan and its index row appear together or not at all.
- The argument interface is preserved as a conversion. The legacy arguments are converted into the same checked input, so the older interface gains the same digest binding and produces the same bytes it produced before. Which interface produced an input is a parameter of the conversion, never a field of the input, so a hand-written input cannot claim the legacy relaxations; only a converted input may carry placeholders, and only in the sections the legacy interface never populated.
- The conversion narrows the argument interface in two recorded ways, because both previously produced a plan the repository would reject later. A `--write-scope` value that is absolute, repeated, or otherwise not a repository-relative path is refused, and both plan titles are bounded at 400 bytes and stripped of surrounding whitespace rather than rendered into a trailing-whitespace line.
- A declared write path, context file, or target JSON path whose existing components include a symlink is refused, because the declared path and the path actually written would otherwise be two different locations and the checked scope would not bound the write.

## Implementation Tiers

Classify every change into exactly one tier before creating plan artifacts. Plan weight, review depth, and available stop transitions follow from that tier. Tier selection is a bounded parent decision recorded as `implementation_tier` in the active plan; when two tiers are defensible, choose the higher one.

- Tier 0: one file, reversible, already covered by an existing validation command, with no new external effect and an unchanged security boundary. Implement directly and commit without a plan file.
- Tier 1: bounded multi-file change whose security boundary, validation authority, and external-effect authority are unchanged. Use a short active plan carrying `primary_invariant`, `write_scope`, `validation`, and exactly one `acceptance` item. New admission accepts exactly one item and rejects zero or several; a plan that needs several acceptance items is Tier 2.
- Tier 2: security-boundary change, irreversible effect, external write authority, lifecycle or validation-authority change, or a write scope that cannot be enumerated as exact paths. Use the full manifest contract, review gates, and restructuring contract.

Count one exact mirrored pair as one Tier 0 file. A single mechanical edit and the same edit in that file's established counterpart, such as a source document and its generated copy, stay Tier 0 together when every remaining Tier 0 condition holds for both files.

- Admit the pair only on a counterpart relation that already exists and is already checked mechanically. A correspondence asserted for this change, or a human claim that two files are the same, is not evidence.
- Require both files to stay covered by an existing validation command, with an unchanged security boundary, unchanged validation authority, and unchanged meaning. A typo fix, a comment fix, and a formatting fix that leaves meaning unchanged are the qualifying examples.
- Exclude a behavior change, two independent edits carried in one change, an edit that reaches only one side or differs in shape between the sides, a change to a counterpart-only branch, a change to a validation definition, and a change to what a rule means.
- Escalate every excluded case to the tier it already takes. The pair exception widens no other Tier 0 condition and lowers no review, validation, or security requirement.

- Escalate a tier as soon as new evidence crosses its boundary, and treat the escalation as a plan update rather than a stop.
- Never lower a recorded tier without explicit user authorization.
- Do not route Tier 0 or Tier 1 work through the restructuring contract.
- A Tier 1 plan carries one acceptance item, so it cannot partition that item and cannot take a bounded descope. When such work must stop, stop it for the owner with its single requirement intact: keep the existing stopped or deferred state and its evidence, and never split, rewrite, or drop the requirement to make a descope look feasible.

## Parallel Execution Groups

Serial execution stays the default. An explicitly admitted execution group is the only way two numbered plans may be `in_progress` at once, and it grants isolated candidate generation only; it never grants product publication by itself.

- Declare membership in one committed project-owned description under `docs/plan/execution-groups/<slug>.json` with `schema_version: 1`, one `group_id`, one exact local `target_ref`, bounded `declared_independence`, and exactly two members. Each member records `plan_id`, `plan_path`, `plan_digest`, and `write_scope_digest`.
- The description carries no runtime authority. It never contains its own containing commit or a digest of itself, and no record is trusted because of its path or origin URL.
- Reference the description from a member plan with the optional `execution_group` manifest field. The reference must name the same validated description that enrolls that plan.
- An enrolled member remains a numbered implementation plan and keeps its normal purpose, feasibility, completion witness, scope, approval, specification, and predecessor checks.
- Reject known write-scope overlap between members, a member write scope that reaches validation or specification authority, member-to-member predecessor edges, and a declared dependence on unfinished member output. Distinct paths alone never prove semantic independence.
- Commit the complete member plans and the group description first. Parent admission then captures the containing clean `HEAD` as the common executable start commit and records it only in the external runtime record.
- Own mutable runtime authority in one parent-owned record outside the repository, created and advanced with `scripts/parallel-plan-state.py`. It binds repository identity, group identity, and the start commit, and it owns exclusive member permits, one upstream claim, one publication lease, per-member budgets, and per-member stop state.
- Each logical member, not the group, owns its one initial generation, one correction, and two independent reviews. A source-baseline transfer consumes the exact prior member permit and carries the counters, stop state, and reviewer-registry proof to the new baseline identity without resetting them.
- Reserve the single parent-adjustment slot before a substantive parent edit of assembled candidate bytes and close it against the resulting patch digest. A reserved adjustment blocks a second adjustment and a later worker correction, and an interrupted adjustment stays spent until exact same-attempt recovery or an owner stop.
- Keep member stop states terminal for that member execution. Transfer, regrouping, or another workspace never clears them.
- Integrate members with the grouped execution adapter `scripts/run-parallel-plans.py`. It dispatches at most one isolated candidate per open member permit, and each member generates against the start commit it was admitted on.
- Keep assembly, review, validation, and publication parent-owned and serial. Assemble one candidate at a time against the current group target commit, refuse an assembly whose permit baseline no longer equals that target until the member takes its single source-baseline transfer, and confine the assembled change to that member's declared write scope.
- Publish only under the publication lease, only the exact reviewed commit whose full diff against the recorded base equals the assembled patch, and only by a checked fast-forward of the group target ref. Write the publication journal before the ref moves so an interrupted publication is replayed or reported, never silently repeated.
- Refuse an enrolled member on every legacy run, correction, validation, and apply path without its verified open permit and the live group execution state, and refuse the completion, finalization, and archive paths until that member's publication is recorded and reachable from the group target. A missing adapter or a missing group authority module keeps every one of these paths closed.
- Pin member plan bytes while a member can still generate, adjust, or publish. After its verified publication that member's own plan takes its ordinary completion and archive transitions, and a committed removal from `docs/plan/active/` retires it without blocking its partner or any ungrouped plan. Ungrouped plans keep their existing behavior unchanged.

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
- `reserved_plan_ids` is an optional list of three-digit plan ids that a live plan will create later. Entries are unique, ascending, and never the declaring plan's own id. A plan is live when its id appears in `docs/plan/plan.md` or when its file resides in `docs/plan/backlog/`.
- `reserved_by` is the optional three-digit id of the plan that reserved this plan's id.
- Reject two live plans that reserve the same id, any plan file that uses an id reserved by a live plan without the matching `reserved_by`, and any restructuring transaction that creates such an id without the matching `reserved_by`.
- Treat `reserved_by` as historical lineage text once the named plan is no longer live, so an archived reserving plan releases its reserved ids. A manifest that declares neither field stays valid.
- Treat both reservation fields as rebind-protected. No rebind or activation record may add, remove, or change them.
- Carry an owner-authorized `write_scope` or `preservation_scope` change only through one durable `reservation` record that names its authorizing commit. Accept the record only when that commit is an ancestor of `HEAD`, exactly one reservation field changes, and the record's original and updated content equal the plan bytes at that commit's first parent and at that commit. Reject a change to a contract-bound `preservation_scope`, and require the record to preserve validation authority and every other protected field.
- Require every `context_files` entry of a plan listed in `docs/plan/plan.md` to be a repository-relative path with no absolute prefix, no `..` segment, and no symlinked component. The `none` sentinel stays valid.
- Reject such an entry when it names no existing repository file, so a relocated plan never leaves a dangling context reference.
- Reject an entry that names an archived plan's former active path in every live plan, whichever command performed the archival. A live plan is a plan listed in `docs/plan/plan.md` or a file under `docs/plan/backlog/`. No exemption remains for an entry whose plan id has a checked or replanned archive with the same id and file name.
- Rebind every pre-existing live plan that names an archived plan's former active path in `context_files` inside the restructuring transaction that performs the archival, and reject that transaction when such an entry would survive it.
- Rebind the same entries in `scripts/finalize-active-plan.sh` when it archives an active plan to `docs/plan/checked/`. Refusing to finalize instead would deadlock the ordinary lifecycle, because a deferred successor names its predecessor's active path and that predecessor cannot be checked before the successor activates.
- Treat the exclusive archive creation as that script's commit point. Rebind the referrers immediately after it and before the source plan is removed, and restore every rewritten referrer and remove the new archive when the rebinding fails. The remaining steps stay unjournaled, so a later interruption is repaired from Git as before.
- Read a referrer entry exactly as the manifest parser does, so an entry written with unusual list spacing is rebound too. Keep finalization a single-writer command. Its exclusive archive creation still admits exactly one writer per plan, and finalizing two different plans at once can lose a referrer rewrite the same way it can already lose an active-index row.
- Rebind a lifecycle-protected contract successor like any other referrer. Lifecycle comparison first projects both compared sides through the canonical relocation that replaces a context entry naming a missing active plan path with that plan's single checked or replanned archive, so the rewrite changes no compared byte and keeps the same plan file as the referent.
- Never rewrite the `context_files` of a plan the same transaction creates. A created plan declares its own context, and rewriting it would silently overrule the specification the transaction verified.
- Apply the same rules to every active plan file a restructuring transaction writes, before the transaction mutates the repository, and treat the paths that transaction writes as present. Enforcing a created plan's context only after the commit point would leave a mutated repository that neither verification nor recovery can clear.
- Apply both rules to `context_files` entries only, never to body prose. A plan body may name a plan that its own transaction will create.
- Repair a stale `context_files` entry by rebinding it to the current location of the same plan file. Leave `predecessor_plans` to the active predecessor rules.
- Keep raw log bodies outside `docs/plan`; reference local run manifests instead.
- Keep active plans executable. Use `## Decisions` for final accepted decisions, not full decision-audit output.
- Keep active-plan operational prose in English by default.
- Record completed task checkboxes and non-pending validation evidence, then run `scripts/complete-plan.sh` before `scripts/finalize-active-plan.sh`.
- Treat `status: checked` as the terminal state written by finalization.
- Enforce the numbered-plan admission contract for every root active or backlog plan whose identifier is 264 or higher through `scripts/check-root-agent-policy.py`. Lower-numbered durable plans stay readable unchanged.

## Task Worktree Boundary

Every repository-changing task performs its writes in one exact task-bound linked worktree. A success response requires that task's accepted commit published to its exact source branch, with the task worktree and its temporary local branch absent.

- Prepare the bound checkout with `scripts/manage-plan-worktrees.py prepare`. It creates or resumes the same checkout for one task identity without a second owner prompt, derives the directory and branch from that identity, and places a new checkout below the operating-system account home rather than inside the pre-existing checkout.
- Select exactly one task identity. A committed active plan names a plan task. `--direct-task <id>` names a bounded direct task for work that has no plan identifier yet, such as authoring a plan. The two identities never share ownership-record key material, so a direct task never acquires a plan's implementation authority.
- Publish an authored plan before implementing it. Plan bytes written in a direct-task worktree are provisional until publication, and plan implementation starts from the published active plan.
- Finish a successful task with `scripts/manage-plan-worktrees.py publish`. It journals its intent, refuses a dirty task worktree, refuses a dirty or drifted source checkout and preserves that state unchanged, fast-forwards the expected source checkout to the exact accepted commit, relocates ignored local evidence, and only then removes that exact task worktree and its temporary branch. Retirement runs from the pre-existing checkout, never from the directory it deletes.
- Allocate plan identifiers under the lock every linked worktree of one repository shares. Allocation reads the exact published source state plus live reservations, binds the checked authoring input to its reserved identifier, and consumes that reservation only when the plan is written, so two checkouts never allocate the same number and an unpublished plan does not lose its identifier to a later allocation.
- Governed surfaces refuse a write outside its bound worktree before the first repository effect: plan authoring, the governed lifecycle commands, `scripts/restructure-plan.py`, the sandboxed runner, grouped dispatch, the pre-tool hook, the `.githooks/pre-commit` hook, and the Stop adapter. Each names the exact preparation or publication command needed.
- Read-only modes stay outside the gate, including `scripts/create-plan.sh --check`, `scripts/complete-plan.sh --check-completion-evidence`, and `scripts/restructure-plan.py --verify`.
- A repository that cannot be named by a canonical `remote.origin.url` can never hold an ownership record, so it stays outside enforcement. `PROJECT_AGENT_WORKFLOW_REQUIRE_TASK_WORKTREE=1` raises enforcement there; no variable lowers it.
- A repository that ships no guard keeps its previous behavior. A shipped guard that refuses or fails blocks the write.

## Completion Gate Boundaries

`scripts/check-agent-completion.sh --plans-only` is the only plan-completion judgment. Every layer runs that same command against the tree its own boundary owns and adds no predicate of its own.

- CI judges the checked-out commit tree and is the repository-shipped enforcement boundary.
- The committed `.githooks/pre-commit` hook judges the exact staged tree. It expands the complete index into a disposable directory with `git checkout-index`, resolves the gate inside that directory, and never reads unstaged plan bytes, mutates the index, or runs a lifecycle transition.
- The staged expansion copies staged bytes. It includes `skip-worktree` entries, so a sparse selection cannot hide a plan record, and it disables line-ending conversion and every configured filter driver, so no repository-configured command runs and no record is rewritten before the gate reads it.
- Supported main-agent Stop hooks judge the current working tree through the shared adapter `.project-agent-workflow/hooks/stop_review_gate.py`. One adapter serves the Codex `Stop` event and the Copilot `agentStop` event configured in `.github/hooks/plan-lifecycle.json`. A missing gate, a failing gate, or an empty gate diagnostic returns exactly one `block` decision with exit code zero, and `stop_hook_active` limits the forced continuation to one turn. The gate is never attached to `subagentStop`, so helpers gain no plan-finalization authority.
- Activate the local hooks manually with `git config core.hooksPath .githooks`. No script, hook, Copier task, or migration sets, overwrites, or unsets `core.hooksPath`. Root mandatory validation only reports an inactive selection and the command to run.
- Local reach is bounded. `git commit --no-verify`, a changed `core.hooksPath`, a non-executable hook file, and a fresh clone before activation stay outside local enforcement, and repository files do not configure branch protection.
- A `ready_to_archive` staged tree directs the reader to finalization. A fully finalized staged tree commits without a hook exception or bypass.

## Candidate Preflight Boundary

`scripts/run-sandboxed-plan-worker.py preflight` gives the parent bounded diagnostic feedback on an admitted candidate. It is not validation and never becomes validation.

- It runs after the parent has reviewed the candidate diff and the critical invariants, and before independent review.
- It runs exactly one command already declared in the plan's `focused_validation`, selected by index. It accepts no free-form command, no new plan field, and no permission to edit a validation definition.
- The clone is fresh, credential-free, and network-isolated, and the source checkout, admitted patch, worker receipt, validation authority, and every focused and authoritative counter stay unchanged.
- One preflight per candidate is claimed atomically in a mode-0600 parent-owned record outside the repository, bound to the attempt id, candidate manifest and patch digests, command digest, and execution genesis. A duplicate, concurrent, stale, or replayed request cannot start a second process, and a crashed preflight leaves the candidate closed rather than granting a retry.
- Execution is bounded to 60 seconds by default and 120 at most, with captured stdout plus stderr capped at 64 KiB. Reaching either bound kills the process group and is never an automatic retry.
- A stopped run, an exhausted budget, and a `diagnosis_required` state each refuse the operation, and preflight lifts none of them.
- Its result is recorded only in a separate bounded diagnostic artifact. It never appears in `completion_witness_map` or `validation_witness_map`, never counts as focused or authoritative success, and never satisfies the mandatory adversarial-preflight review-order event.
- A failing preflight may inform only the one correction the run already allows. The next candidate still needs independent review, focused validation, and one authoritative run.

## Bounded Descope

A bounded descope reduces the acceptance set of the current plan without restructuring it. Use it when review findings show that the plan is too wide, not that its design is wrong.

- Record `descope_required` in the parent-owned execution ledger through one `descope_classification` event bound to an independent-review receipt, the unchanged plan path, plan digest, source HEAD, primary invariant, and the current candidate lifecycle.
- Classification requires a bounded write scope and unchanged source scope, validation authority, invariant boundaries, primary invariant, safety conditions, and external-effect authority, with exactly one independent invariant. Any drift escalates to the matching hard replan reason instead of authorizing a descope.
- Partition every source acceptance digest exactly once into `retained_acceptance_digests` and `deferred_acceptance_digests`, preserving source order. Retain at least one item and defer at least one item. Losing, duplicating, reordering, or adding an acceptance digest is rejected.
- A descope therefore applies only to a genuinely partitionable acceptance set of at least two items. An acceptance set that cannot be split into two nonempty sides is not descopable, and no rewording, splitting, or restatement of its requirement may manufacture a partition.
- Move the deferred acceptance items to the exact `deferred_backlog_path` backlog plan. A descope never deletes a requirement; it only changes when that requirement is executed.
- `descope_required` stops candidate generation, correction, validation, apply, completion, and archival for that execution run. Only the `descope_plan` gate stays open, and the stopped run is never reopened.
- A descope creates no replan contract, no successor lineage, and no additional active plan. Keep it as the default exit for a Tier 1 plan whose acceptance set is partitionable. Tier 0 work has no plan file, so it has no descope exit at all.
- Indivisible Tier 1 work leaves the ledger in its existing stopped owner-decision state with its recorded reason and evidence preserved, and its single acceptance item unchanged. Refuse the descope because no nonempty partition exists; do not reopen the run, restart it as unstarted backlog work, fabricate an exhaustion or drift reason, or create a descope, repair, or reconstruction successor to obtain another execution budget. Only an already checked same-plan continuation policy may apply, on its own eligibility conditions.
- `descope_pending` is a stopped owner-decision state. Create the exact deferred backlog plan only after the owner authorizes the descope and the deferred work independently satisfies the numbered-plan admission contract; otherwise leave the run stopped or shelve the source through the owner-directed lifecycle. No worker, correction, review, or classification effect may bypass that stop.

### Review-Finding Budgets

- Classify review findings before selecting a stop state: implementation findings are `acceptance_unmet`, `focused_validation_failed`, and `evidence_incomplete`; boundary findings are `out_of_scope_change`, `required_spec_missed`, and `integration_contract_mismatch`; the design finding is `multiple_invariants_coupled`.
- `independent_review_limit` is two for one execution epoch: one initial independent review and one bounded rereview. A changed candidate digest, a parent-direct revision, a model-access fallback taken before a candidate is admitted, and a resumed session all leave the epoch count unchanged, and a third review request in that epoch is an explicit refusal rather than a new review identity.
- Initialize one mode-0600 append-only continuation registry outside the repository with `plan-execution-state.py continuation-registry-init`. New high-risk or correction-capable executions start epoch 0 with `plan-execution-state.py init --require-adversarial-preflight --continuation-registry <path>`, which binds that registry's path-bound identity into the ledger. Legacy ledgers remain readable but do not gain same-plan continuation retroactively.
- Before the first formal review of an exact target, and again after that target changes, record one passing `adversarial_preflight` event bound to the plan digest, review-target digest, review-identity digest, current required-specification digests, and one or more bounded case-evidence digests. The later review must bind the same specification digest list. Preflight is ordering evidence only; it does not count as independent review, focused validation, authoritative validation, or acceptance evidence.
- A review-budget-exhausted `descope_pending` run with reason `parent_remediation_budget_exhausted`, no open writable attempt, and exactly one or two prior formal reviews may receive one owner-authorized same-plan continuation. Never reopen or modify the stopped ledger. Create a fresh ledger with `plan-execution-state.py continue`, bind the complete predecessor-ledger digest and event-chain leaf, exact unchanged plan path and digest, source HEAD, primary invariant, implementation mode, and a mode-0600 authorization record.
- Consume each stopped execution's immutable plan/run/genesis identity once under the bound registry's lock, while recording its current event-chain leaf, canonical state-file digest, authorization digest, child run id, child state path, and child genesis. Recheck the bound registry identity after acquiring that lock. Permit only exact idempotent crash recovery for that same child identity, and reject forks, replay, reserialized predecessors, replacement or copied registries, changed plan bytes, changed source baselines, and every stop reason other than the eligible parent-review exhaustion.
- The first continuation policy permits only epoch 1. Each epoch retains two formal reviews and the numbered plan has a cumulative maximum of four. No later owner quotation, session restart, candidate change, or new registry replenishes that fixed bound; further continuation requires a future policy change.
- Derive every finding budget from that limit. One bounded correction round fits inside it, so the execution ledger refuses a second correction attempt at `writable_attempt_started`, before any worker effect.
- Implementation findings have a budget of 2 correction-requested or rejected attempt closures. Boundary findings have a budget of 1 correction-requested or rejected attempt closure. Accepted closures do not count.
- A `parent_review` event carries finding severities but no review reason code, so one parent-direct remediation round that still leaves a High or Medium finding records `descope_pending` with `parent_remediation_budget_exhausted` instead of asserting a finding class. The owner may authorize the one same-plan continuation above when all immutable boundaries remain unchanged.
- Exhausting an implementation or boundary finding budget records `descope_pending`, with `implementation_finding_budget_exhausted` or `boundary_finding_budget_exhausted`. Only `descope_classification` or a hard drift event may follow.
- `multiple_invariants_coupled` remains an immediate `replan_required` reason. Any scope, spec, security-boundary, or post-authoritative design drift still escalates to `replan_required`.
- An exhausted budget stops the current epoch for an owner decision. Do not create a repair, descope, or reconstruction successor merely to reset review. Use the one bounded same-plan continuation only for eligible parent-review exhaustion; otherwise retain the stopped state or use the existing independently justified repair, descope, reconstruction, or shelving transition.

## Restructuring Contract

Plan restructuring changes execution boundaries, ordering, implementation methods, or validation methods. It does not change the user requirement baseline. The baseline consists of the user requirements, accepted safety conditions, and every normalized `acceptance` item in the source plan.

- Use `status: replan_required` when the current plan must stop before further implementation, candidate generation or correction, validation, apply, completion, or archival.
- A canonically stopped plan carries `status: replan_required`, a non-empty unique bounded `replan_reason_codes` list, and no `completion_deferred_reason`. Reject a missing, empty, duplicate, unknown, or non-string reason value with a bounded lifecycle error.
- Require every durable schema-1, schema-2, and schema-3 contract `reason_codes` list to be bounded and to equal its canonical source manifest `replan_reason_codes` exactly. Apply the same checks to nested historical contracts and to schema-3 prerequisite plans.
- Compare lifecycle evolution by removing only the parsed lifecycle field bytes: the exact scalar line, or the exact list field header and its parsed list-item lines. Treat comments, blank-line placement, unknown instructions, and every other unparsed byte as protected, both when comparing and when deriving a stopped source.
- Keep the legacy compatibility route for historical lineage shape only. It never exempts a plan from canonical stopped metadata.
- Compare the parsed manifest fields as well as the projected bytes when validating lifecycle evolution, and reject any change to a non-lifecycle field. Byte equality alone does not prove that a protected field kept its parsed value.
- Apply the canonical stopped rules to a durable contract's embedded source content with no grandfather clause. A contract that records a noncanonical stopped state has always been invalid. Because committed contract bytes and the committed replanned index prefix are both immutable, such a contract has no in-band repair: it can only be corrected by rewriting the affected history outside this workflow. Never weaken verification to accept it.
- Restructuring is mandatory after scope, required-spec, or security-boundary drift; discovery of multiple independently validatable invariants; or a discovery after authoritative validation that requires changing source-plan boundaries, implementation or validation methods, validation authority, or acceptance mapping. Review-budget exhaustion alone does not justify restructuring when the bounded same-plan continuation remains eligible.
- Reconstruction specification and contract schema 4 adds `owner_continuation_authorization`: a bounded, non-placeholder quotation of at most 400 bytes recording the owner instruction to continue implementation by creating successors. It is persisted in the immutable schema-4 contract. Schema-1 through schema-3 contracts keep their exact historical shape and verify unchanged.
- Validate the numbered-plan admission contract for every successor and prerequisite plan a schema-4 specification creates, before any repository write. Refuse a successor whose declared write scope is confined to plan-lifecycle records, and refuse a successor used only for investigation, re-verification, stopping, candidate preservation, or execution-context reset.
- Make a product-changing successor own final integration verification whenever it can run it, instead of creating a separate integration-only plan.
- Keep a source that needs reconstruction live at `status: replan_required` until the owner supplies continuation authorization or explicitly shelves the work. Dependent plans stay deferred while that live source remains unresolved.
- Elapsed time is telemetry and a checkpoint signal only. It can prompt review of the plan boundary, but it cannot prove semantic failure or authorize requirement changes.
- Preserve the exact source plan path, source HEAD, source-plan digest, and digest of every normalized source acceptance item in the parent-owned replan contract.
- Map every source acceptance digest to at least one successor plan or integration gate. The integration plan must retain the source acceptance text exactly and prove the combined successors against it.
- A successor may change plan boundaries, ordering, implementation methods, and validation methods. Replacing, weakening, deleting, or adding a user requirement or accepted safety condition requires explicit user authorization recorded separately from the restructuring operation.
- Preserve committed work. Do not reset, stash, delete, commit, or apply product changes as part of restructuring.
- Record every dirty product path exactly once across successor `preservation_scope` fields, except for a schema-4 `promoted_dirty_paths` entry that is covered by exactly one created plan's `write_scope`. Each path is one normalized exact path, not a directory prefix.
- Use dirty-path promotion only when the successor must continue editing an already-dirty path. Bind every created plan to one live, worktree-local shared ID reservation obtained with `restructure-plan.py --reserve-successor-id`, and record those bindings in `successor_id_reservations`.
- Keep ordinary `preservation_scope` disjoint from every successor `write_scope`. Preservation proves retention only and never authorizes candidate generation, validation, apply, staging, or commit effects. Promotion transfers the complete dirty product set, without changing its bytes during reconstruction, to exactly one successor whose manifest declares `implementation_mode: parent_direct`; partial or multi-successor promotion is refused.
- After a promoted reconstruction completes, commit only its journal-declared plan-lifecycle operations and publish that transition with `scripts/manage-plan-worktrees.py publish --retain-worktree --transition-journal <journal>`. The command must reproduce the exact dirty snapshot, verify the committed transition contains no promoted product bytes, fast-forward the source checkout, and retain the source task worktree and branch for the published successor's parent-direct execution. Candidate workers remain unavailable for such a successor. Finish with ordinary publication only after the promoted implementation is reviewed, validated, and committed.
- Reject missing, duplicate, overlapping, non-normalized, or silently dropped preservation entries. Continue verifying schema-1 contracts created before `preservation_scope` without reinterpreting their historical write scopes as the new preservation authority.
- After an atomic restructuring transition, archive the source with terminal `status: replanned`. This state means “replaced while preserving requirements”; it is distinct from successful `checked` completion and prerequisite-based `deferred` work.
- Keep full option analysis and decision matrices outside active plans. Active successors contain only accepted decisions, bounded lineage fields, executable scope, validation, and acceptance.

### Successor Backlog Deferral

- A replan successor may be deferred to `docs/plan/backlog/` with `status: backlog` instead of being restructured again. Deferral changes location and priority only; it never changes lineage.
- Keep the successor path recorded in the replan contract exactly as created. That path is immutable identity, so backlog residence never rewrites it and no new contract is required.
- Keep `acceptance`, `inherited_acceptance_digests`, `replan_sources`, `replan_contract`, `write_scope`, and `preservation_scope` byte-identical to the contract. Remove `completion_deferred_reason` and `replan_reason_codes`, which describe a stopped active lifecycle.
- Resolve every successor to exactly one of the active index, `docs/plan/backlog/`, `docs/plan/shelved/`, the checked archive, or the replanned archive. Presence in two locations, or in none, is rejected.
- Reactivate a deferred successor by moving it back under `docs/plan/active/`, restoring an active status, and re-adding its active index row.

### Shelved Plans

- Use `docs/plan/shelved/` with `status: shelved` for a plan the owner decided not to implement. Shelving is an owner decision, not an agent one. `docs/plan/backlog/` means "not started yet"; `shelved` means "decided against for now". Keeping them apart is what makes an untouched plan readable as a decision rather than as neglect.
- Require `shelved_reason` and `shelved_at` as `YYYY-MM-DD` on every shelved plan, and reject a missing or blank value. Without them the location becomes a place where work stops for reasons nobody can reconstruct.
- Write `status: shelved` only under `docs/plan/shelved/`, and keep every shelved plan resolvable in exactly one lifecycle location, the same way a backlog successor is.
- Shelve only an unstarted backlog plan. Work that has started is stopped through `deferred`, `replan_required`, or `descope_required`, which carry the evidence a stopped run requires.
- Keep `acceptance`, `inherited_acceptance_digests`, `replan_sources`, `replan_contract`, `write_scope`, and `preservation_scope` byte-identical to the contract. A replan contract resolves a shelved successor exactly as it resolves a backlog one, so shelving never deletes a requirement and needs no new contract.
- Treat shelving as reversible. Return a shelved plan to `docs/plan/backlog/` or promote it directly to the active index; `shelved` is not a terminal state and is neither `checked` completion nor `replanned` replacement.
- Shelve a plan only on an explicit owner instruction to stop pursuing it. Propose a shelving candidate with its evidence and wait; never move a plan to `docs/plan/shelved/` on your own judgment that the work looks unnecessary, and never shelve a plan merely to shorten the backlog. Name the instruction in `shelved_reason` so a later reader can tell an owner decision from an agent assumption.
- Treat a shelved plan as no longer required. An `integration_gates` entry, a predecessor reference, or an ordering note that names a shelved plan does not block the plan that depends on it, because a shelved plan is one nobody intends to run and a prerequisite that can never be met would let shelving stop unrelated work.
- Never edit a gate to drop the shelved reference. The gate is written history and only `rebind_lineage` may rewrite it, and then only to move an exact path. Record the waiver in the dependent plan's Validation Notes before it starts, naming the shelved plan and the assurance the waiver skips, so a reader can see what was accepted without it.
- Restore the obligation when the plan returns. A gate naming a plan that moves back to `docs/plan/backlog/` or into the active index binds again, so a waiver recorded earlier stops applying.
- Move a stranded reference to the shelved plan instead of leaving it stopped. Shelving a plan that live plans still name by its former active path would otherwise make those plans unactivatable forever, because activation refuses any unresolved active path and a shelved plan has no checked archive to resolve to. Restate the reference as the same plan id's `docs/plan/shelved/` path with `rebind_lineage`, then record the waiver the shelved prerequisite requires.
- Move a plan with `scripts/shelve-plan.sh`, which writes the required fields and refuses a plan that has started. Reverse it with `--restore`, or promote it with the ordinary promotion command.

### Predecessor Lineage Rebinding

- A plan whose `predecessor_plans`, `context_files`, `integration_gates`, or body still names an active path it can no longer resolve is stopped, because activation resolves an active path only to the checked archive carrying the same plan id, and a backlog successor cannot record an activation at all. Move that reference with the `rebind_lineage` operation instead of restructuring the referring plan.
- Run the operation with `python3 scripts/restructure-plan.py <lineage-spec.json>` using `operation: rebind_lineage` and only `kind: lineage_rebind` records. It appends to the same immutable rebind record chain and is verified with every other record.
- Rebind only a plan that has not started: the live successor must carry `status: deferred`, `status: backlog`, or `status: shelved`, and it must resolve in the active index, under `docs/plan/backlog/`, or under `docs/plan/shelved/`.
- Admit exactly three replacement classes, and reject every other target.
- Replanned source class: the reference names a plan that was replanned, so it has no checked archive of its own. Admit it only when the replan contract that consumed the source already records a checked successor. A path replacement must name exactly one replanned source and resolve to one checked successor of that same contract; an identifier replacement must restate exactly one such source id as one of its checked successor ids.
- Checked archive class: the reference names a plan that was archived as checked. Admit a path replacement that names exactly one such reference and restates it as the same plan id's checked archive, resolved by the same rule the activation route uses: one unambiguous archive of that plan id and file name whose `status` is `checked`, with no file remaining at the former active path. This class is admitted for any unstarted referrer, `deferred` or `backlog`, because the resolution evidence is the same in both.
- Shelved plan class: the reference names a plan the owner shelved. Admit a path replacement that names exactly one such reference and restates it as the same plan id's flat `docs/plan/shelved/` path, whose `status` is `shelved`, with no file remaining at the former active path. Reject a reference that also resolves as a replanned source or a checked archive, because two resolutions mean the repository does not know which plan the reference meant.
- Treat a shelved predecessor as resolved, not as pending. A `predecessor_plans` entry naming an existing `docs/plan/shelved/` plan no longer holds the referring plan in `deferred`, because the owner decided that plan will not run and waiting for it would never end.
- A backlog referrer is why this class exists. Successor Backlog Deferral removes `completion_deferred_reason`, an activation record requires a `deferred` baseline that still carries it, and `backlog` cannot re-enter `deferred`, so a backlog successor has no activation route at all. Rebinding resolves the reference; it never starts the plan, and a `deferred` referrer still cannot enter `in_progress` directly without its activation record.
- Reject a reference that both classes claim, and rebind only the reference; the plan keeps its status, so reactivation stays a separate act.
- Restrict manifest edits to `predecessor_plans`, `context_files`, and `integration_gates`. Preserve `status`, `completion_deferred_reason`, acceptance, inherited digests, write scope, preservation scope, contract identity, and every other byte.
- A backlog successor's live bytes may already differ from its rebind chain by lifecycle fields alone. Keep the record chain on the projected content, apply the same exact replacements to the live file, and check the lifecycle relation on both sides of the rebinding.
- Lifecycle evolution accepts a `backlog` baseline, so a rebound backlog successor can still be reactivated, stopped, or completed.
- A legacy successor whose contract never enforced projection semantics may start its chain from its own committed live bytes, which must equal the committed bytes at `HEAD`. Every later record is then bound by the immutable chain, so the rebinding only adds enforcement.
- Lineage rebinding never changes `successor_plans`, `replan_sources`, or `replan_contract`. Those fields are contract identity, not resolvable references.

### Pre-Boundary Lifecycle Reconciliation

- Leaving `status: deferred` requires a durable activation record. A plan that left `deferred` by direct edit and then reached an immutable checked archive has no in-band correction, because a rebinding targets one live active successor. Such a plan freezes lineage verification and therefore every restructuring operation.
- Close exactly those historical cases with the write-once registry `docs/plan/replanned/baselines/pre-boundary-lifecycle-reconciliations-v1.json`. Each entry binds the plan path, the expected chain-final baseline digest, the checked archive path, the archive bytes digest, and a reason.
- The registry names one `boundary_commit` that must be an ancestor of `HEAD`, and every reconciled archive must already exist with those exact bytes at that commit. A defect introduced after the boundary can never be admitted.
- Every entry must resolve to a `checked` archive of the same plan id whose active path no longer exists, whose live bytes match the recorded digest, and whose rebind-chain baseline matches the recorded baseline digest. Any drift rejects.
- The registry is write-once: once committed, its live bytes must equal its committed bytes and it must have exactly one commit in history. It admits nothing else and weakens no other lifecycle rule.
- Do not use the registry for new work. A plan that leaves `deferred` after the boundary must record an activation record.

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
- Maintain `docs/plan/replanned/baselines/live-validation-successors-v1.json` inside the reconstruction transaction. Archiving a live schema-1 contract successor removes it from the derived companion records, so the transaction publishes the projected records as one journaled write covered by the same rollback, roll-forward, and prospective verification. The projection removes only the successors the transaction archives and removes a record only when it retains no live successor; every other record, successor, and field keeps its published bytes, so a disagreement the transaction did not cause still rejects.
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
- Bind the exact target mode to every journaled replacement before its temporary file is created, reject a transaction whose target path carries a mode outside that bound before any journal is created, and reject a journal whose target mode is not a bounded, non-world-writable permission value.
- Record each transaction-created temporary file's regular-file type, device, inode, mode, link count, and content digest before any rename, and persist that identity with the journal.
- Require a renamed target to keep the recorded temporary identity through applying, commit point, replay, and completion. Byte-identical content at a different inode, a drifted mode, or a missing temporary is an external replacement, not idempotent completion.
- Record each transaction-created rollback restoration identity separately and reverify it when an interrupted rollback resumes. Content equality alone never proves restoration ownership.
- Reject a missing, stale, impossible, externally replaced, or malformed identity with a bounded error at every apply, rollback, roll-forward, and durable completion boundary.
- Keep this guarantee bounded to transaction-created file identity under the existing same-user threat model. It does not defend against an actor that can replace every local process and file.
- Run a coupled transaction with `python3 scripts/restructure-plan.py <schema-3-spec.json>`. Recover only with `python3 scripts/restructure-plan.py --recover <journal-path> --journal-id <sha256-identity>`.

#### Acceptance Clauses

Decompose the coupled reconstruction requirement into these seven clauses. `tests/test-plan-restructure.py` binds each clause id to its enforcing functions and to the regression tests that cover it, so deleting an enforcement function or a bound test fails the focused suite instead of silently widening the operation.

- `atomic_transaction`: one coupled reconstruction applies every plan, contract, archive, index, and overlay write as a single all-or-nothing transaction under the repository lifecycle lock.
- `fail_closed_preflight`: every specification, repository, lineage, and prospective-state check runs and rejects before the first repository write and before any journal exists.
- `stopped_source_replacement`: the first source is replaced only from canonical `replan_required` bytes and is archived with terminal `status: replanned`.
- `immutable_dependent_replacement`: each dependent source depends on an earlier source, is stopped by lifecycle-field derivation alone, and is replaced in the same transaction.
- `bounded_dependent_rebinding`: a live dependent rebinding changes only exact authorized reference tokens in permitted fields and is appended to the immutable rebind record chain.
- `historical_preservation`: existing contract bytes, acceptance items, write scopes, and validation authority stay unchanged for every affected and unaffected plan.
- `predecessor_graph_preservation`: the complete active predecessor graph stays resolvable, acyclic, and free of stale, cross-id, or dangling edges after the transaction.

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
