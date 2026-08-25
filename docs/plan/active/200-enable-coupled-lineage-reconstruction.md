# Enable coupled lineage reconstruction

status: deferred
completion_deferred_reason: Plan 199 must be checked and its exact checked archive path must replace the active predecessor before implementation.
primary_invariant: one durable locked transaction can replace a stopped active successor and its immutable dependent successor while applying only exact authorized reference projections in later dependents and leaving every historical contract byte, acceptance item, write scope, and unaffected predecessor edge unchanged
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - scripts/project_workflow/copier_fixture.py
  - tests/test-copier-fixture.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/197-freeze-bounded-shell-structure-parser.md
  - docs/plan/active/198-integrate-bounded-copier-fixture-validator.md
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/replanned/contracts/191-freeze-bounded-copier-fixture-validator.json
  - docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 -m py_compile scripts/restructure-plan.py template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Provide one atomic, fail-closed lifecycle operation that reconstructs a stopped successor with its immutable dependent successor and exact bounded dependent rebindings while preserving existing contract bytes, acceptance, write scopes, validation authority, and the complete active predecessor graph.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:3cc1064bb989622dab9eaca79fc89afaba85b8aabd7191dd4935882d8ba797ef","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/199-admit-decomposed-shell-validation.md
integration_gates:
  - preserve the rejected Plan 197 candidate paths without editing, staging, committing, importing, or accepting them
  - keep root and generated restructure commands byte-identical
  - Plan 201 remains deferred until this plan is checked and its exact checked archive path replaces the active predecessor
checked_summary_ja: 停止planとimmutable dependentの置換および後続metadata rebindを単一transactionで行えるようにする。

## Decisions

- coupled_lineage_reconstruction means one atomic lifecycle transition that replaces a stopped successor and each immutable active dependent that would otherwise retain its archived predecessor path.
- Extend the restructuring specification with an ordered non-empty source set, one shared successor graph, and zero or more exact live dependent rebindings.
- Require every dependent source to be an exact live successor of a verified contract and to depend directly or transitively on another source in the same transaction.
- Permit the transaction to derive the dependent source's `replan_required` bytes only by replacing its status and lifecycle reason fields; bind both the original live content digest and derived stopped content digest in the new durable contract.
- Emit one schema-3 multi-source contract with ordered `sources`, one archive path per source, one mapped successor list, per-source acceptance mappings, and explicit `integration_source_ids` on every integration successor.
- Permit the same transaction to create separately authorized prerequisite plans that are not contract successors, carry no inherited source acceptance digest, and can only appear as active predecessors of mapped successors.
- Add `replan_sources` and `replan_contract` to schema-3 successor manifests; reject singular ownership, missing sources, reordered sources, more than one integration successor for one source, or conflicting acceptance mappings.
- Permit exact live dependent rebindings to change only `completion_deferred_reason`, `context_files`, `focused_validation`, `validation`, `validation_witness_map`, `predecessor_plans`, integration-gate references, and explicitly enumerated body path or plan-name references needed to replace paths created by the same transaction.
- Require each body replacement to declare the exact old string, exact new string, and exact occurrence count; reject substring overmatch, missing occurrence, added prose, acceptance changes, task changes unrelated to the replacement, or any unlisted byte difference.
- Require initial reconstruction rebindings to preserve status, primary invariant, acceptance text and digest, write scope, preservation scope, task types, required specs, implementation classifications, review class, and every unrelated manifest and body byte.
- Store rebindings in append-only `docs/plan/replanned/baselines/live-successor-rebinds-v1.json` records keyed by owning contract digest, plan path, original content digest, prior effective projection digest, updated content digest, exact replacement map, and resulting validation projection.
- Compute effective live validation authority by verifying the immutable `live-validation-successors-v1.json` baseline first and then applying a unique digest-linked rebind chain in record order; reject forks, gaps, stale originals, weakened or removed validation, unadmitted commands, witness drift, or changed historical baseline bytes.
- Permit later parent-owned activation records in the same overlay only when they replace active predecessor or context paths with their exact checked archives, preserve every command and witness, and transition one deferred plan to `in_progress` after all of its active references are resolved.
- Permit an activation record to remove one exact product path from `preservation_scope` and add the same path once to `context_files` only after the path's owning predecessor is checked, the checked commit contains that path, the activating plan has no write authority over it, and every unrelated preservation and context entry remains byte-identical.
- Reject activation promotion when the path changes, the producer is not an exact checked predecessor, the checked bytes are missing, the path remains writable, more than one destination entry is added, or the promotion weakens validation or a lifecycle gate.
- Validate the complete active predecessor graph, all verified contracts, all replan and rebind projections, exact dirty-path preservation, and destination nonexistence under one lock before the first write.
- Persist a mode-0600 Git-local transaction journal before repository writes with the source HEAD, every original and target digest, ordered operations, phase, and commit point.
- Apply temp-file writes, file and directory fsync, atomic renames, and index replacements in deterministic order; before the commit point recovery restores every original byte, and after the commit point recovery completes the remaining idempotent renames and verification.
- Add an explicit recovery command that accepts only the exact journal identity and refuses stale HEAD, changed paths, symlinks, hard links, unsafe modes, unknown phases, or ambiguous completion.
- Add crash-at-each-phase, stale-HEAD, stale-content, partial-source, overbroad-field, acceptance-drift, write-scope-drift, validation-weakening, overlay-fork, dirty-path, duplicate-successor, cycle, rollback, and roll-forward tests.
- Require byte identity only for root and generated `restructure-plan.py`; keep the new coupled-reconstruction policy section semantically aligned between root and generated Plan Workflow specifications while preserving their intentional repository-role differences.
- Use bounded parent implementation and independent review because this plan changes lifecycle and validation-authority code under protected paths.

## Tasks

- [ ] Define and validate the schema-3 multi-source specification, archive identities, mapped successors, separately authorized prerequisite plans, and exact rebind overlay schema.
- [ ] Implement fail-closed preflight over source identity, contract lineage, allowed exact replacements, validation overlays, dirty preservation, and the complete active graph.
- [ ] Implement the Git-local journal, locked fsync and atomic-rename transaction, rollback, roll-forward recovery, and deterministic indexes.
- [ ] Extend durable verification to reproduce dependent stopping, multi-source ownership, shared integration successors, effective validation overlays, and unchanged historical contract bytes.
- [ ] Keep root and generated restructuring scripts byte-identical, keep the new policy section semantically aligned, and add positive, negative, hold-out, crash, recovery, overlay, and cross-contract tests.
- [ ] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite once, archive, commit, and activate Plan 201 with this plan's exact checked archive as predecessor.

## Validation Notes

- This plan adds lifecycle capability only and must not restructure Plans 197 or 198 itself.
- Exact live dependent rebinding is narrower than replanning and cannot change requirements, implementation authority, product scope, or validation strength.
