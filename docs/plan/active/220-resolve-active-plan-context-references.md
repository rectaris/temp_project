# Resolve active plan context references

status: in_progress
implementation_tier: 2
primary_invariant: every context_files entry of a plan listed in the active index resolves to an existing repository file
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - docs/plan/active/220-resolve-active-plan-context-references.md
  - docs/plan/plan.md
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/200-enable-coupled-lineage-reconstruction.md
  - docs/plan/active/201-reconstruct-shell-parser-lineage.md
  - docs/plan/active/210-reconstruct-coupled-capability-lineage.md
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/plan/checked/2026/08/16-31/217-enforce-plan-id-reservations.md
  - docs/plan/checked/2026/08/16-31/219-honor-activation-context-rebinding.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
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
  - Reject before any mutation an active or created plan whose context_files entry is not repository relative or resolves to no existing repository file and no same-id plan archive, keep every restructuring transaction and activation able to archive or rebind a referenced plan, and repair the stale references in Plans 200, 201, and 210 without changing any other plan bytes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:ee5eee1683c71e0f99c7937b60f434771e9aefcbc9a5748f06727e2d437bfc81","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
predecessor_plans: []
checked_summary_ja: active indexに載るプランのcontext_filesが必ず実在ファイルへ解決されるよう検証し、Plans 200/201/210のstale参照を修復する。

## Decisions

- A stale context reference means a `context_files` entry that names no existing repository file. Commit b69056e moved Plans 166, 185, 186, 197, and 198 from `docs/plan/active/` to `docs/plan/backlog/` without updating the plans that referenced them, and Plans 213, 215, and 216 have since moved to their checked archives.
- Nothing rejected the resulting dangling entries, so they accumulated silently across fourteen entries in three active plans. An agent that loads `context_files` therefore loses required context without any signal.
- Enforce resolution only for plans listed in `docs/plan/plan.md`. Those are the plans an agent executes now, and a backlog plan is checked when it is promoted into the active index.
- Separate two referents that both look like a stale entry. An entry whose plan was moved to `docs/plan/backlog/` names a file that no longer exists anywhere under that name, and nothing will ever repair it. An entry whose plan was archived still identifies that plan through its same-id checked or replanned archive. Only the first is the defect.
- Exempt the archived case. Rejecting it would make every deferred successor unverifiable between its predecessor's archival and its own activation, which two existing activation tests proved, and it would abort any restructuring transaction that archives a plan another live plan lists as context. `verify_prospective_repository` runs a full verification on a clone before the journal exists, so such a transaction fails closed with no recovery path.
- Reject an exemption whose archive row names a file that does not exist. An index row alone is not evidence that the plan is still readable.
- Do not close the exemption at `in_progress`. Plan 210 lists Plans 200 and 201 as context and archives both in its own transaction while it is `in_progress`, so that closure would forbid the transaction this plan exists to unblock.
- Enforce created and rewritten plan context before the transaction mutates anything. A pre-transaction `verify_repository_contracts` sees only plans that already exist, so a created plan's context would first be enforced by the post-commit verification, whose handler rolls back only at `prepared`, `temps_prepared`, and `applying`. The prospective clone is not equal to the worktree, because `overlay_current_worktree` never unlinks a path that was staged for deletion, so a divergence there would leave a mutated repository that neither verification nor `--recover` can clear.
- Treat the paths a transaction writes as present during that pre-transaction check, so a created plan may name a sibling the same transaction creates.
- Resolve the exemption directly from the checked and replanned index rows instead of through `matching_checked_paths`. That helper raises `predecessor identity mismatch` when the same id carries a different file name, which would attribute a context defect to the predecessor subsystem and hide a valid replanned archive.
- Accept that the archived-path tolerance never closes for a plan outside a replan contract, and defer the closure to `docs/plan/backlog/221-rebind-referrer-context-on-archive.md`. Closing it needs the archiving transaction to rebind its referrers, because a referring plan is outside that transaction's write scope and a post-commit rejection is unrecoverable.
- Validate entry shape before resolution. `ROOT / entry` silently accepts an absolute path, `..` escapes the repository, and `is_file` follows symlinks, so an unchecked entry could name a file outside the repository. Reuse `reject_symlink_ancestors` and the containment rule that `normalized_path` already applies elsewhere.
- Enforce resolution on `context_files` entries only, never on body prose. Plan 210's body names Plans 211 and 212, which that plan will create, and a forward reference in prose is legitimate.
- Keep the `none` sentinel valid, because it records a deliberate absence of context rather than a path.
- Repair each stale entry to the single existing file that carries the same basename. Every one of the fourteen entries has exactly one such file, so the repair is determined rather than chosen.
- Change no other plan bytes, no acceptance text, no acceptance digest, no validation authority, and no write scope.
- Leave `predecessor_plans` alone. `validate_active_predecessors` already governs it, and this plan must not duplicate or weaken that rule.
- Use bounded parent implementation with fresh independent review because this plan changes fail-closed validation authority.

## Tasks

- [x] Reject an active-index plan whose `context_files` entry is not repository relative or resolves to no existing repository file and no same-id plan archive.
- [x] Mirror the root command into the generated template byte-for-byte.
- [x] Document the rule in the root and generated plan workflow specifications.
- [x] Repair the fourteen stale entries in Plans 200, 201, and 210.
- [x] Add rejecting and accepting tests, including the `none` sentinel, a body-only forward reference, a transaction that archives a referenced plan, a created plan checked before any mutation, and the containment rules.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, then archive and commit this plan.

## Validation Notes

- This plan changes no product runtime behavior outside plan lifecycle verification.
- Commit b69056e left fourteen dangling `context_files` entries across Plans 200, 201, and 210. Each repaired entry is the single existing file that carries the same file name, and no other byte of those three plans changed.
- Independent review ran three rounds. The first found that rejecting every unresolved entry aborts a restructuring transaction that archives a referenced plan, and that enforcing a created plan's context only after the commit point leaves a repository that neither verification nor `--recover` can clear. Both are fixed by the archived-plan exemption and by `validate_prospective_plan_context_files`, which runs on the real repository before the transaction mutates anything. The final round returned zero High and zero Medium findings.
- Mutation testing used a null control that correctly survived. Fifteen non-equivalent mutants were detected, covering both call sites, the prospective plan filter's written-path set, both index branches of `archived_plan_locations`, the archive-existence filter, the checked-branch identity conjunct, the containment and symlink rules, the `none` sentinel, the existence skip, and the active-path branch.
- Three surviving mutants are equivalent. Dropping either conjunct of the replanned branch is indistinguishable, because `verify_repository_contracts` already binds every replanned row's id and file name to its source. Dropping the `PLAN_PATH_RE` filter in `validate_prospective_plan_context_files` is indistinguishable, because every other written path either carries no `context_files` field or is derived from a plan that the pre-transaction verification already accepted.
- The archived-path tolerance never closes for a plan outside a replan contract. That is recorded as a deliberate descope and deferred to `docs/plan/backlog/221-rebind-referrer-context-on-archive.md`.
- The root command and its generated template counterpart are byte-identical.
