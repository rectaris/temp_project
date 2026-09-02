# Enforce executable admission for numbered plans

status: in_progress
primary_invariant: a numbered plan authorizes only bounded repository-changing implementation whose method is supported by recorded feasibility evidence and whose plan-local completion is testable before activation, while review exhaustion and lifecycle recovery stop for an owner decision instead of manufacturing procedural successors
task_types:
  - planning_docs
  - template_workflow
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
implementation_tier: 2
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"template/.project-agent-workflow/scripts/planlib.py already parses and validates active and backlog manifests at plan admission boundaries."}
  - {"kind":"existing_mechanism","evidence":"scripts/check-root-agent-policy.py already validates root active-plan records and can bind a repository-local plan-ID admission boundary without changing historical plan bytes."}
  - {"kind":"existing_mechanism","evidence":"scripts/plan-execution-state.py already records independent-review events and immutable review identities in the parent-owned execution ledger."}
  - {"kind":"existing_mechanism","evidence":"scripts/restructure-plan.py already preflights successor manifests and fixed reconstruction contracts before repository writes."}
completion_conditions:
  - Root policy validation and generated-project official creation or promotion reject a newly admitted numbered plan unless plan_purpose is implementation, feasibility_evidence is bounded and non-placeholder, and every completion condition has exactly one focused witness, while pre-policy durable plans remain readable.
  - The execution ledger and writable runner refuse any correction or review event that would require a third independent review in one execution, even when the candidate digest or parent-direct review identity has changed.
  - Schema-4 reconstruction preflight requires owner_continuation_authorization, preserves schema-1 through schema-3 contracts unchanged, refuses a new successor whose declared write scope is confined to plan-lifecycle records, and permits integration verification to remain in the product-changing successor.
completion_witness_map:
  - {"condition_sha256":"sha256:f250454ca08a164dc3e6650aa29a72559d90f55c9a5d0570a47aa7ae9f163dd7","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:58189fdffbadadbcfba68a04c509aba1bda9dac9c51641cef804894507acc19d","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:f532a28c200a650fec7cf6eb67f238e27b43e9bc9b180e9bd5f8fb4f3051b318","witness":"python3 tests/test-plan-restructure.py"}
write_scope:
  - AGENTS.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - scripts/restructure-plan.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/create-plan.sh
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/promote-plan.sh
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - template/docs/plan/README.md
  - template/docs/plan/backlog/README.md
  - tests/root-plan-lifecycle.sh
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-plan-restructure.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/backlog/251-place-fixture-words-and-alias-sources.md
  - docs/plan/checked/2026/08/16-31/248-bind-fixture-editing-to-the-inventory.md
  - docs/plan/shelved/262-defer-unbounded-copier-dispatch-proof.md
  - docs/plan/shelved/263-replan-reachable-fixture-constructions.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - tests/root-plan-lifecycle.sh
  - python3 tests/test-validation-tools.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Require root plan IDs at or above the admission boundary and generated-project official plan creation or backlog-to-active promotion to admit only bounded implementation work with recorded feasibility evidence and plan-local completion conditions, while leaving pre-policy durable plans readable.
  - Permit at most one initial independent review and one rereview for a numbered-plan execution, counting across candidate and parent-direct revisions.
  - Require explicit owner continuation authorization before reconstruction creates new successors, preserve pre-policy reconstruction contracts unchanged, reject new successors used only for investigation, re-verification, stopping, preservation, or execution-context reset, and make an implementation successor own final integration verification when possible.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f3601efd88b01cad8e53122186df7d8c0b9cf3c0b1066ab1c5bfd919327af1df","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:cf05bca7e82c65ede9236ad4a4fd56e6f432a3e19169dddc3a1071614c8a93af","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:bbf2812bb132eb43266fa66e17b390d8c7c5f4f8d5c1df3cc31b192de65be4bb","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
integration_gates:
  - preserve existing active, backlog, checked, replanned, shelved, and schema-1 through schema-3 reconstruction contract records without requiring a Copier migration; enforce the admission contract at the root plan-ID boundary, generated official creation or promotion, and schema-4 reconstruction rather than by changing historical bytes or the globally required manifest field set
  - do not create a numbered investigation, feasibility, integration-only, stop-recording, candidate-preservation, or execution-context-reset plan
  - do not create a successor for Plan 251; leave it in backlog until its own implementation method and local completion witnesses are revised in place
  - keep root and template policy, execution ledger, reconstruction preflight, and generated plan commands aligned in this change
  - count independent review events against the whole execution run rather than a mutable candidate identity, and reject review budget reset through parent-direct implementation or reconstruction
  - require reconstruction to preserve source requirements but stop before successor creation until the owner has explicitly authorized continued implementation
  - run the authoritative validation suite exactly once after the candidate diff and both independent review opportunities are acceptable
checked_summary_ja: 番号付きplanを実装開始の許可に限定し、実行可能性と固有の完了判定を着手前に要求して、レビューや手続きだけの後続plan生成を止める。

## Decisions

- plan_purpose means the repository-changing implementation purpose authorized for one numbered plan.
- feasibility_evidence means the bounded pre-activation records supporting that the selected implementation method can finish within the declared scope.
- completion_conditions means the plan-specific behavior predicates that this numbered plan must establish.
- completion_witness_map means the exact one-to-one mapping from plan-local completion-condition digests to focused validation commands.
- independent_review_limit means the fixed maximum number of independent review events admitted for one numbered-plan execution.
- owner_continuation_authorization means the bounded quotation that records the owner instruction to continue implementation by creating reconstruction successors.
- Treat a numbered plan as implementation-start authorization. `plan_purpose: implementation` means the plan must change at least one repository artifact outside plan-lifecycle records; investigation, feasibility discovery, value evaluation, re-verification, stopping, candidate preservation, and execution-context reset remain unnumbered evidence or lifecycle operations.
- Use `feasibility_evidence` for bounded pre-activation evidence that the selected method can finish within the declared scope. Admit only a small fixed set of evidence kinds: a reproduced defect, an existing enforcement mechanism, a bounded prototype, or a mechanical transformation. Reject placeholders, unsupported kinds, unbounded prose, and evidence created by a separate numbered feasibility plan.
- Preserve inherited `acceptance` during reconstruction and add `completion_conditions` for the behavior one numbered plan itself must establish. `completion_witness_map` maps each condition digest exactly once, in source order, to an exact command already declared in `focused_validation`; it cannot use an authoritative-only witness.
- Enforce the root compatibility boundary in `scripts/check-root-agent-policy.py`: root active or backlog plan IDs at or above 264 require the admission record, while lower IDs remain readable. In generated projects, `create-plan.sh`, `promote-plan.sh --add-active`, and reconstruction preflight require the record; ordinary lint keeps pre-policy active, backlog, checked, replanned, and shelved plans readable, and the new fields are not added to the global `REQUIRED_FIELDS` set.
- Require `create-plan.sh` to receive complete admission inputs for both active and backlog creation. Do not generate a numbered placeholder whose feasibility or completion conditions remain unknown.
- Keep Plan 251 in its current backlog location. Do not create a successor or edit it merely to satisfy this policy plan; the promotion command must explain that its feasibility evidence and local completion witnesses need an in-place revision before activation.
- Set `independent_review_limit` to two for the entire execution run: one initial independent review and one rereview. Candidate digest changes, parent-direct revisions, fallback attempts, and session changes do not reset the count. A third review request is an explicit refusal, not a new review identity.
- Reduce the review-bearing correction path to one bounded correction followed by the single rereview. Derive the correction, parent-remediation, and implementation/boundary finding budgets from that limit in both ledgers and writable runners, and refuse a second correction at `writable_attempt_started` before worker effects. Amend every conflicting AGENTS, Plan Workflow, orchestration, and sequential-plan skill rule so a post-rereview patch or any candidate requiring a third independent review cannot be accepted in that run; model-access fallback before a candidate is admitted does not consume a review.
- After the review budget is exhausted, stop with the existing lifecycle state appropriate to the accepted diagnosis and return the unresolved implementation choice to the owner. Do not automatically create a repair, descope, or reconstruction successor from a finding.
- Keep `descope_pending` as a stopped owner-decision state. Create its exact deferred backlog plan only after the owner authorizes descope and the deferred work independently satisfies the same implementation admission contract; otherwise leave the run stopped or shelve the source through the owner-directed lifecycle. Update the ledger transitions so no worker, correction, review, or classification effect can bypass that stop.
- Keep a source that needs reconstruction live at `status: replan_required` until the owner either supplies continuation authorization or explicitly shelves the work through the existing owner-directed lifecycle. Dependent plans remain deferred while that live source remains unresolved.
- Introduce reconstruction specification and contract schema 4 for `owner_continuation_authorization`. It must be a bounded, non-placeholder quotation of the owner instruction to continue implementation through successors and is persisted in the immutable schema-4 contract; schema-1 through schema-3 contracts keep their exact historical shape and verify unchanged.
- Reject a reconstruction successor whose write scope is empty outside `docs/plan/` and local evidence directories, or whose admission record identifies only investigation, re-verification, stopping, preservation, or execution-boundary recovery. When a product-changing successor can run final integration validation, make that successor the integration owner rather than creating a separate integration-only plan.
- Grandfather existing contract-bound shelved plans as historical records. The existing explicit owner restore operation may return them without retroactively changing their immutable reconstruction contract, but the new admission contract governs every newly created successor and every ordinary backlog promotion after this policy lands.
- Implement the admission checks in the existing plan parser, promotion command, execution ledger, and reconstruction preflight. Do not introduce a new plan lifecycle, database, daemon, or migration subsystem.
- Treat admission evidence, finite review, and authorized successor creation as one implementation-start invariant for this execution. Manifest admission alone is falsified when review exhaustion can manufacture a procedural successor; the review limit alone is falsified when creation or reconstruction can admit infeasible work; successor authorization alone is falsified when initial creation or repeated review can still produce non-implementation plans. All three entry paths must change atomically or the primary invariant remains defeatable.
- Mirror root policy and tooling changes into the Copier template in the same candidate, and extend the existing alignment checks so the admission, review-limit, and successor-authorization rules cannot drift.
- Use bounded parent implementation because plan lifecycle and validation-authority machinery may not be delegated writable. Independent helpers, if any, remain read-only and advisory.

## Tasks

- [ ] Reproduce the three current admission gaps in focused tests: root or generated official creation or promotion accepts a newly admitted plan without bounded feasibility or local completion witnesses, independent review can restart after its mutable review identity changes, and reconstruction can create a plan-lifecycle-only successor without owner continuation authorization.
- [ ] Define the numbered-plan admission contract in root and template policy, including the compatibility boundary for untouched legacy backlog records and the categories that remain outside numbered plans.
- [ ] Add `plan_purpose`, bounded `feasibility_evidence`, `completion_conditions`, and `completion_witness_map` parsing and validation to the generated plan library and lint path.
- [ ] Update the generated plan scaffold, human-facing plan documentation, and promotion command so newly created plans expose the admission fields and no plan enters active implementation without valid values.
- [ ] Add the same admission validation to schema-4 root and template reconstruction preflight, persist `owner_continuation_authorization` in new contracts, keep schema-1 through schema-3 verification unchanged, and refuse plan-lifecycle-only or otherwise non-implementation successors before any repository write.
- [ ] Enforce two independent reviews across the entire parent execution run in root and template ledgers and writable runners, including candidate, parent-direct, fallback, correction, and resumed-session paths, and refuse a second correction before worker start.
- [ ] Amend Implementation Tiers, Bounded Descope, Review-Finding Budgets, Restructuring Contract, `AGENTS.md`, orchestration policy, and the sequential-plan skill so only one review-bearing correction fits in a run, `descope_pending` waits for an admission-ready owner decision, and no accepted closure can require a third review.
- [ ] Extend root/template alignment checks for every new normative admission and review-limit rule.
- [ ] Add positive, negative, mutation, legacy-active/backlog compatibility, Copier-update, and no-partial-write tests for plan creation, promotion, lint, review accounting, and reconstruction.
- [ ] Confirm root Plan 251 remains readable in backlog, and confirm a generated-project legacy backlog plan with the same missing admission fields is refused at ordinary promotion without creating or requiring a successor.
- [ ] Complete no more than two independent read-only review events, resolve every High or Medium finding within this plan or stop for the owner, and never create a procedural follow-up plan.
- [ ] Run focused validation, run the authoritative suite exactly once for an otherwise acceptable candidate, archive the checked plan, and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending.
