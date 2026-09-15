# Consume the last review slot after an owner-authorized parent stop

status: in_progress
primary_invariant: One stopped epoch-one parent-direct execution may consume its sole remaining cumulative review slot once through explicit owner authorization, preserving immutable stopped evidence and exact plan identity.
task_types:
  - validation_tools
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Plan 344 has stopped epoch-zero and epoch-one ledgers with two and one formal reviews respectively. Both verify unchanged; the epoch-one stop is solely parent_remediation_budget_exhausted, with no open attempt and one unused slot under the cumulative limit of four.","kind":"reproduced_defect"}
  - {"evidence":"continue_state already verifies a private owner authorization, locks the stopped ledger, consumes its immutable genesis once under the bound continuation registry lock, and constructs a fresh ledger. Reuse that transaction rather than reopening stopped state.","kind":"existing_mechanism"}
  - {"evidence":"validate_state already combines predecessor_review_count with local formal reviews and refuses the cumulative limit. A versioned terminal epoch carrying three predecessor reviews can retain the existing maximum of four.","kind":"existing_mechanism"}
  - {"evidence":"The task-worktree manager permits descendant history and publishes only a fast-forward containing the source tip. A separately published policy can be adopted without rewriting the task binding; continuation must explicitly bind the old and adopted source HEADs.","kind":"existing_mechanism"}
completion_conditions:
  - Only an ungrouped parent-direct epoch-one run stopped solely for parent_remediation_budget_exhausted, with no open attempt and exactly three cumulative formal reviews, can create one terminal continuation.
  - The final authorization binds the exact stopped ledger, chain leaf, plan, invariant, mode, child identity, same continuation registry and adopted source HEAD; replay, copies and competing children are refused.
  - The terminal continuation carries all three prior reviews, permits at most one fresh staged review, keeps the cumulative limit at four, and permits neither a worker attempt nor another continuation.
  - Only the exact owner-authorized descendant source HEAD with byte-identical plan and invariant is admitted; the ordinary epoch-zero continuation retains its unchanged-source requirement.
  - Existing ledger and authorization schemas remain readable with unchanged historical limits; the new path never rewrites either stopped predecessor ledger or reuses an admitted reviewer session.
  - Root and template commands and workflow specifications describe and enforce the same bounded terminal continuation.
  - Existing root policy, routing and required workflow checks pass after the entrypoint wording changes.
completion_witness_map:
  - {"condition_sha256":"sha256:e449d96f2700f29ff6cdd2d808c4c51d0d10bfca6e7c24c8223574a853fba712","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:68ab0283651a2190d94a519e5f5edcbc141dbd452dd1fb023b31ad39be084b7d","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:db106b374de6a7cb8060f1a9a522a53fc3ddfed967a7024800f2ceb598702525","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:8f31b27467d337eb52170284e78ee3d8974f03ebcbe2f26a95774a92c6a50c8a","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:f5d9555d89d3da17fe56fd5cc4e7156678552c7af77c13a08c0c6e4a34fb754e","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:07c311237e722e9e39a6b0667cba5d367250fd3c8c5ba6f3300276402b877b96","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:b0c2717334b80b908372bb75a7e68669e80573ad41cdd46b1696fa09660841a3","witness":"python3 scripts/check-root-agent-policy.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - AGENTS.md
  - template/AGENTS.md.jinja
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/manage-plan-worktrees.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An explicitly authorized eligible stopped parent-direct run consumes its remaining review slot exactly once without changing stopped evidence, plan identity or the cumulative four-review limit.
  - Wrong state, mode, epoch, count, registry, owner binding, source lineage or plan bytes cannot grant the final allowance; old continuation and historical-reader behavior stay unchanged.
  - The root and generated command and governing specifications implement the same rule.
  - The changed agent entrypoints continue to satisfy the existing root policy and workflow checks.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:8e1071ae22522a2c6f78c9c70ecfe8cbfc16a0dbb04ab8046ee03fd88f1c133c","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:a0dd99a14176599929a48e36525fd77b39e1967ff9d01553f3f800c8d7a1cde6","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:caa90999e0932224f30c9f092284500d18c2c900cb916db4a26e746c413cd977","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:c274172da89e4834fb47e60d22c20b2892b0d3b6971d3c072a30cf2223248c7c","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
integration_gates:
  - This is a separate owner-authorized policy implementation, not a successor that resets plan 344's budgets. Keep plan 344's stopped ledgers and dirty task worktree intact; do not continue its product implementation before this policy is checked and published.
  - Serial implementation requires plan 344 to be deferred in the source active index while this plan runs. Preserve its original exact plan bytes and restore its executable status only after publication and before authorizing the final continuation.
checked_summary_ja: 停止記録を保持し、所有者の承認で残る1回のレビューを使う。

## Decisions

- Keep the cumulative formal-review limit at four. Admit a terminal epoch two only from an eligible epoch one with exactly three cumulative reviews; carry the complete prior count and refuse every later continuation.
- Use a separately named final-continuation command with versioned authorization and epoch evidence. Preserve the exact historical schemas and ordinary epoch-zero-to-one behavior; do not globally widen their limits.
- Reuse the stopped-ledger lock and the same continuation registry's atomic consumption protocol. Preserve both stopped ledgers byte for byte and reuse the same reviewer registry so previously admitted sessions remain unavailable.
- Permit parent-direct correction only, with no worker attempt allowance. Require an exact-target adversarial preflight and the one remaining independent review to clear High and Medium findings before the unchanged focused and authoritative gates.
- The final authorization may bind an exact descendant source HEAD after the separately reviewed policy update is published. Verify ancestry, the historical and current exact plan bytes, and the unchanged invariant. Parent adoption preserves the existing uncommitted product patch; conflicts stop rather than authorize dropping or force-applying changes.
- Use bounded parent-direct implementation for this high-risk authority change. This plan neither implements plan 344's late-route correction nor changes the unrelated sandboxed runner.

## Tasks

- [ ] Reproduce refusal of the eligible epoch-one stopped fixture and capture its exact historical bytes and cumulative count.
- [ ] Implement the bounded final authorization and terminal epoch through the existing lock and registry consumption path, retaining old schema behavior.
- [ ] Bind approved descendant policy adoption without relaxing exact plan identity or the ordinary continuation baseline gate.
- [ ] Cover successful final consumption, all eligibility and binding refusals, repeated and concurrent consumption, legacy byte preservation, reviewer reuse, the fifth review and further continuation refusal.
- [ ] Mirror the implementation and governing policy across all declared root and generated surfaces.
- [ ] Run independent review of the exact target, focused validation and the authoritative suite once, then publish this policy separately from plan 344.

## Validation Notes

- Owner instruction: 344の修正に必要な再開条件の仕様変更を、別の作業として扱うことを承認する。既存の停止記録は改変せず、無制限の継続は認めない。
- The original plan 344 candidate remains uncommitted in its exact task worktree. Its existing runner-authority omission is pre-existing and outside this policy plan's scope.
- The decision audit is retained locally in the authoring session. Unknown applicability of the later policy commit to the dirty candidate remains an explicit stop condition, not permission to discard changes.
