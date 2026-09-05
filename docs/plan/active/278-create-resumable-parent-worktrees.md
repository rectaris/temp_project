# Create and resume parent-owned development worktrees

status: replan_required
replan_reason_codes:
  - parent_remediation_budget_exhausted
primary_invariant: Managed worktree creation and resumption bind one parent development checkout to one exact plan and committed baseline while preserving the ordinary checkout, existing Git state and retained work; delegated implementation keeps the existing independent clone and sandbox.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"run-sandboxed-plan-worker.py detect_repo_root and clone_at_head resolve the current checkout and clone an exact HEAD with --no-hardlinks; ensure_clean_worktree can therefore apply to a dedicated parent checkout."}
  - {"kind":"bounded_prototype","evidence":"A disposable Git fixture created two linked worktrees from one commit while the ordinary checkout had tracked and untracked edits, cloned one linked worktree with --no-hardlinks, and verified that the original dirty bytes and status were unchanged."}
  - {"kind":"existing_mechanism","evidence":"retire-merged-worktrees.py already validates canonical allowed-root paths, registered worktree identity and explicit removal eligibility; its existing policy excludes automatic deletion and force removal."}
completion_conditions:
  - Parent-only create binds an exact committed plan, canonical repository and common Git directory, start commit, unique local branch and external allowed root; tracked and untracked changes in the ordinary checkout remain unchanged.
  - Resume verifies the bound worktree, branch, plan, start history and ownership record, preserves retained dirty work, rejects ambiguous or replaced evidence, and refuses a second active owner.
  - Creating a parent worktree does not copy secrets, share writable dependencies or caches, run setup commands, publish refs remotely, or automatically remove worktrees or branches.
  - The existing worker can use a clean linked parent worktree while retaining independent no-hardlinks clones, exact write scope, protected Git metadata, original source preservation and unchanged sandbox failure behavior.
  - Root and generated commands, operational guidance and install inventories remain mechanically aligned without changing the existing explicit retirement policy.
completion_witness_map:
  - {"condition_sha256":"sha256:e74e9646cd80925092fe2fc73004e6062deb194dafb24b6034aab31e32e7a3b0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f2ad4f4bce71693075f1ba618bcbceeb65c7f08b843effa0349cfbc8b9c9a18d","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:aa412b0585b67be5381949e8489d452866c3426c1ac3afd36ed40c81bcf9485d","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d8b32bd2eb231efc6ccba2f77144ce6eb9e95a54b4dfc142cbacacec9ef06cce","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:59bbd711e56024640737ebf6abc1b0bfaf1c54e22d8e43d28e5c43daa91b0dfe","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - tests/validation_tools/worktrees.py
  - tests/test-validation-tools.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/plan-execution-state.py
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/planlib.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - scripts/retire-merged-worktrees.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Implement parent-owned create, inspect and resume operations that preserve the ordinary checkout and retained results, confine their local effects to the exact managed branch/worktree and ownership record, and reject stale, unsafe or duplicate ownership.
  - Run the existing worker from a clean linked parent worktree without replacing its disposable clones, widening its write or credential access, or changing candidate acceptance and retirement authority.
  - Register the same root/generated command and operational guidance in the deterministic install inventory and parity checks.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:73b12f9939519cef986a89097913978fd8cd5fa852848ffcd85d88f8ce85c0c6","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:91debfddfa563272121fb95a5f5924bc6d286130501351ee2788caa2d2bba294","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:964fb466ff6e6b9581d97e9d3c9673463ea37efe21664bcb0f45b2084db9d2db","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Implement this first; plans 279 and 280 remain deferred until their declared predecessors are checked. This plan does not enable simultaneous writable plans.
  - Use bounded parent implementation with an external execution ledger and independent read-only review because this scope changes orchestration and validation authority; do not dispatch this plan to a writable worker.
  - The ownership record is runtime-only, bounded, mode 0600 and outside the repository. Bind a canonical common-Git-directory identity in addition to the credential-free canonical origin identity; origin alone cannot distinguish clones.
  - The ordinary checkout may be dirty, but the selected start commit and plan must already be committed. Do not stash, reset, copy uncommitted files, change the ordinary branch/index, replace an existing branch, or infer a base from a moving ref after admission.
  - Require an explicit external allowed root and exact branch name. Reject symlinked paths, unsafe roots, existing unowned paths, branch reuse and ambiguous worktree registration before mutation. Managed Git changes are limited to the new branch and registration, which worktrees necessarily share.
  - Use a parent-owned lock/lease and journal around create and resume. An interrupted create preserves its exact owned directory and reports or resumes the partial operation after identity verification; never delete unknown or useful work to recover.
  - Resume allows retained modifications in the managed checkout but does not relax the runner clean-source gate. Verify branch ancestry against the recorded start and bound accepted commits; reject an unexplained branch switch or unrelated history.
  - Keep credentials and ignored local files out of automatic copying. Reuse the existing parent dependency snapshot for worker validation; the manager itself runs no package installer, setup hook, database migration or arbitrary shell command.
  - Start the parent session explicitly from the managed checkout. Test repository-root resolution when .git is a file and document that ordinary Git worktrees do not sandbox an unrestricted parent process or isolate host ports.
  - Preserve SPEC_GIT_RETIREMENT and git-retirement.yaml unchanged. There is no remove subcommand or automatic cleanup, and no upstream or remote push prerequisite for create/resume. Existing explicit retirement may leave detached, unmerged or upstream-less work in place.
  - Register new root/generated scripts in the existing Copier inventory, syntax/parity checks and generated smoke assertions. The root-only test module is imported by the existing test-validation-tools entrypoint; do not add a new free-form validation-command escape.
checked_summary_ja: 親エージェント用の作業場所を安全に作成して再開し、元の未コミット変更と既存の実装用 clone の隔離を維持する。

## Decisions

- A separate Git checkout owned by the parent, bound to an exact repository, plan and committed starting revision, preserving the ordinary checkout and retained work.
- Use a dedicated parent worktree for sustained development or coexistence with ordinary-checkout edits; retain the existing lightweight path for small work that needs no isolation.
- Implement create, inspect and resume in scripts/manage-plan-worktrees.py and its generated counterpart. A managed checkout is a parent working location, not a replacement worker sandbox.
- Keep the committed baseline, plan identity and exact ownership explicit. Existing uncommitted user work is preserved where it is and is not silently included in the task.
- Provide common repository commands, not product-specific Codex, Claude or Cursor hooks. Product adapters and automatic deletion are outside this plan.

## Tasks

- [ ] Add disposable-repository fixtures for dirty ordinary checkouts, root versus linked checkout invocation, branch/path collisions, symlinks, replaced ownership, duplicate owners, interrupted creation and retained dirty resume.
- [ ] Implement bounded record validation and create/inspect/resume with exact Git command arguments and source-state preservation checks; never execute the fixture against live developer worktrees.
- [ ] Extend worker fixtures to exercise a linked parent checkout, source-root resolution and no-hardlinks candidate isolation; make only the minimum runner compatibility changes those fixtures require.
- [ ] Add aligned command guidance and register the new installable file in Copier inventory/parity and generated smoke checks.
- [ ] Run the declared focused suites, obtain independent review, and run the unchanged authoritative suites once for the acceptable implementation.

## Validation Notes

- Planning baseline: `56dd79a2461acd9880f27cf7c75f62a1dad877a5` in `temp_project`.
- Owner authorization: 「この方針でプランを docs/plan/active に作成せよ。」 The owner selected the preceding proposal and A/B conflict-resolution explanation; the accepted design is approved for this bounded plan. This turn creates plans only and does not execute their product changes.
- These are new plans, not a reconstruction of a stopped source, so no historical restructuring contract, acceptance set or owner-continuation record is fabricated or changed.
- Feasibility is bounded source inspection and, where named, a disposable Git prototype run during planning. It is not a claim that the new runtime behavior or future completion witnesses already pass.
- Full decision audit and planning prototype are local evidence under `.agent-artifacts/decision-audits/parallel-plan-worktrees/`; final decisions needed for execution are stated here.
- Plan-authoring validation passed: scripts/lint-project-workflow.sh and tests/smoke.sh (exit 0). Smoke ran the generated-project scenarios; its optional GitHub Actions lint was skipped because actionlint was unavailable. These results validate plan creation and the existing repository, not the future implementation tasks.
- Parent checks passed for numbered-plan admission, actual TSV index/status/dependency mapping, exact condition/acceptance digests, declared command grammar, context existence and diff whitespace. After the final witness-only clarification, the parent reran the affected policy/manifest checks.
- Two read-only document-review rounds found authority bypass, completion-scope, accounting, baseline-self-reference and witness-boundary issues. The parent incorporated the bounded corrections and verified the final mechanical witness split; no product execution ledger was opened and no runtime implementation review is claimed.
- Implementation task checkboxes remain open, and implementation completion witnesses have not yet been established.
- Recheck the current committed baseline and exact scope before implementation; read applicable directory AGENTS.md and required specifications directly. Preserve any intervening owner changes.
- The parent owns scope admission, validation acceptance, independent-review acceptance, lifecycle, commits and reporting. Read-only helpers may supply bounded evidence; no writable helper is authorized by this planning turn.
- No measured speedup or resource saving is claimed. Root plan files describe this repository's implementation work and are not copied as product-specific plans into the reusable template.
- The first parent-direct implementation passed the declared focused tests, but the second independent review still found four Medium safety defects after the one permitted remediation round. The execution ledger stopped at `descope_pending` with `parent_remediation_budget_exhausted`; authoritative validation and commit were not attempted.
- Owner continuation authorization: 「継続して開発せよ。」 The rejected implementation is preserved outside the repository under the parent session state and the worktree was restored to the committed baseline before reconstruction.
