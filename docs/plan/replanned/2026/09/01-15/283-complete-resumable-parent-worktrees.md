# Complete resumable parent-owned development worktrees

status: replanned
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
  - {"kind":"existing_mechanism","evidence":"The preserved parent-direct candidate already passes validation-tools, sandboxed-worker and Copier parity tests; reconstruction starts from the committed baseline and reuses only reviewed design evidence."}
  - {"kind":"reproduced_defect","evidence":"Independent review reproduced committed checkout filters hidden by dirty attributes, external diff-driver execution, registered-worktree allowed roots and writable target-parent races."}
  - {"kind":"existing_mechanism","evidence":"Git check-attr --source, no-ext-diff/no-textconv, registered-worktree enumeration and owner-private directory identity checks provide bounded corrections for the four remaining defects."}
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
  - docs/plan/replanned/2026/09/01-15/278-create-resumable-parent-worktrees.md
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
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/283-complete-resumable-parent-worktrees.md
replan_contract: docs/plan/replanned/contracts/283-bootstrap-same-plan-continuation.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/287-complete-resumable-parent-worktrees.md
inherited_acceptance_digests:
  - sha256:73b12f9939519cef986a89097913978fd8cd5fa852848ffcd85d88f8ce85c0c6
  - sha256:91debfddfa563272121fb95a5f5924bc6d286130501351ee2788caa2d2bba294
  - sha256:964fb466ff6e6b9581d97e9d3c9673463ea37efe21664bcb0f45b2084db9d2db
checked_summary_ja: 親エージェント用作業ツリーの作成と再開を、単一所有と安全な checkout 境界を含めて完成させる。

## Decisions

- Reimplement from the committed baseline instead of applying the stopped candidate.
- Keep one integration successor because the remaining corrections share the same manager command, fixtures and acceptance boundary.
- Store ownership records in one canonical user-private state directory keyed by repository common-directory identity and plan.
- Reject checkout filters and unsafe existing directory ancestry before `git worktree add`; the manager never executes repository-configured conversion or diff commands.

## Tasks

- [ ] Reimplement create, inspect and resume with canonical ownership, raw history and worktree-administration identity checks.
- [ ] Add regression fixtures for dirty committed attributes, external diff drivers, registered-worktree roots, unsafe target parents, replacement refs and recreated registrations.
- [ ] Restore root/generated guidance, inventory, smoke assertions and linked-parent worker coverage.
- [ ] Run focused validation, independent review, authoritative validation, completion and archival.

## Validation Notes

- Owner continuation authorization: 「継続して開発せよ。」
- The rejected Plan 278 candidate is preserved outside the repository in the parent session state. It is not product acceptance evidence.
- Plan 278 stopped after the second review left Medium findings; this successor receives a fresh execution ledger and review budget under the immutable schema-4 reconstruction contract.
- Plan 283 stopped after its second independent review left Medium findings. Its external ledger remains terminal at `descope_pending` with `parent_remediation_budget_exhausted`.
- Owner bootstrap authorization: 「提案の方針で進める。」 The owner approved one final reconstruction to install bounded same-plan continuation epochs and deterministic adversarial preflight; later review-budget exhaustion must not create another numbered successor merely to reset review.
- The uncommitted Plan 283 candidate was preserved outside the repository with a SHA-256 manifest, then the repository was restored to the committed source baseline before this lifecycle transition.
