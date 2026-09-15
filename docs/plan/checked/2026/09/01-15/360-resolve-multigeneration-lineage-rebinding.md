# Let the sanctioned rebind reach an unstarted plan stranded by more than one reconstruction

status: checked
primary_invariant: A reference that a contract chain resolves to exactly one checked successor can be restated only through rebind_lineage, and an ambiguous or unfinished chain still refuses.
task_types:
  - validation_tools
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"replan_lineage_pairs() returns an entry for docs/plan/active/358 and none for docs/plan/active/355, because it maps a source only when its direct successor is checked and 358 is replanned.","kind":"reproduced_defect"}
  - {"evidence":"A rebind_lineage specification naming docs/plan/backlog/356 fails with 'invalid rebindings[1].plan_path', and the same specification using an active-shaped path fails with 'rebindings[1] must target one exact unstarted contract successor'.","kind":"reproduced_defect"}
  - {"evidence":"validate_lineage_reference_transition already admits a replanned source moving to a checked successor with a different plan id, and already accepts status backlog as an unstarted plan, so the replacement class needed here exists and only its reach is missing.","kind":"existing_mechanism"}
  - {"evidence":"Reconstruction contracts record their successors and preserve acceptance items across generations, so a chain walk reads recorded facts rather than inferring them.","kind":"existing_mechanism"}
completion_conditions:
  - replan_lineage_pairs resolves a source through a chain of reconstructions to its checked leaf, and refuses a chain that yields more than one leaf, that has an unfinished branch, or that repeats a plan.
  - A rebind_lineage record can name an unstarted plan that lives outside the active directory and owns no reconstruction contract, and binds that record to the contract whose chain made the reference unresolvable.
  - The activation route, the checked-archive class and the shelved class keep their current admissions and refusals, and a hand-written reference change is still refused.
  - Plans 356 and 357 name the checked archive of plan 359 through rebind records rather than through an edit, and the root plan lifecycle accepts the result.
  - The root and template restructure modules and the two plan workflow specifications stay aligned under the existing checker.
completion_witness_map:
  - {"condition_sha256":"sha256:8f0b91d90057b9e499f33000a80f77e26282f05f55cdbc640d7c32a0fec7ce8c","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:7724dc5de7fa3b0dc0ca77ae04a988b1e3d18c6fb35fde0dda0e40d702d79fe8","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:b7ae5d8a8dfa90302c57af6c962d57e2fb59940cb2a877a7ba389e1c71412064","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:ee679c4cdeba8db9e9c84e9179b44db5d7c391dbb6083f54349eaa9cf3510520","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:880b71b94edadf84960db80ee1e441116a06f76ea7bea4c4cc6ef3a7d2682156","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/plan/backlog/356-delegate-read-only-tasks-to-opencode-go.md
  - docs/plan/backlog/357-delegate-candidate-implementation-to-opencode-go.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md
  - docs/plan/checked/2026/08/16-31/243-admit-lineage-rebinding-for-checked-predecessors.md
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A replanned source whose successor was itself replanned resolves to the checked plan that carries its work, and an ambiguous, unfinished or cyclic chain is refused with a message naming the reason.
  - A rebind_lineage specification names an unstarted plan that is not a reconstruction successor, is addressed where that plan actually lives, and records the contract that authorizes the move.
  - Every refusal the rebinding and activation routes make today is still made, including a replacement that extends a reference into a longer path token and one that changes protected plan identity or status.
  - The integration gate and context reference in plans 356 and 357 name the checked archive of plan 359, written by the rebind operation and verified with every other record.
  - The root and generated counterparts of the restructure module and the plan workflow specification stay aligned under the existing template checker.
  - The unchanged authoritative suites keep passing.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:51994cb6ae5fa59cb2d64e69309c598351fe0ed5d9fe41e663e92ea4158553d1","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:7dadcf69e0a39cfa98b30616272f8e748bbdfdbf3da184abfd6aa1ebb4541f50","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:803041e5c4919a73e785f00849caa83b638f64fdcc1827f36f0736e48af280a8","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:090832c70e8ccf866e1cb4c9e44598f6bcdc09db892562b7790e8e999878985c","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:eb86c16e9bf8040e6ced02ce5473816599e4619db54ddd03c86a8c3b34282361","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:6bd6bfd13e8603871d30c9c5abc47994880ecb76f5d3db567d02660fa18ae4d0","authoritative_only_reason":"No narrower preflight runs the generated-project lifecycle end to end, which is where a rebinding regression would surface.","stage":"authoritative","witness":"tests/smoke.sh"}
checked_summary_ja: 複数世代の再構築で座礁した未着手プランを、認可された rebind_lineage で解決できるようにする。

## Decisions

- Follow the reconstruction chain transitively to its checked leaves rather than one generation. A source whose successor was itself replanned is stranded permanently today, and the contracts already record every generation, so the walk reads recorded facts. Reconstruction preserves acceptance items across generations, so every leaf carries the source's requirements by construction.
- Refuse a chain that yields more than one checked leaf, that still has an unresolved branch, or that repeats a plan. Resolving to one plausible successor silently would be worse than staying stranded, because a gate naming the wrong successor asserts an assurance nobody obtained, and an early resolution would release a dependent plan before its prerequisite is finished.
- Address the plan where it actually lives instead of requiring an active-shaped path for a plan that is not a reconstruction successor. validate_lineage_reference_transition already accepts status backlog, so the missing piece is reach, not policy.
- Bind a rebind record for a contract-less plan to the reconstruction contract whose chain made the reference unresolvable. The authority for the move then comes from the same document that caused it, and the immutable record chain stays fully keyed. Do not add a contract-less record form, which would create rebind records that nothing binds.
- Implement parent-direct in the task-bound worktree because scripts/restructure-plan.py carries validation authority. Do not delegate these edits to a candidate worker.
- Keep the activation route, the checked-archive replacement class and the shelved replacement class unchanged. Only the two observed gaps open; every existing refusal stays a refusal.
- Rebind plans 356 and 357 in this plan rather than leaving the mechanism without a user, because the end-to-end witness is what proves the repair.
- Treat a plan sweep as a task rather than an assumption. Only 356 and 357 are known to be stranded, and the implementation confirms that before relying on it.

## Tasks

- [x] Before edits, confirm the exact write scope and the current required specifications, and record the unchanged baseline. Sweep every live plan for an unresolvable active reference and confirm the affected set.
- [x] Make replan_lineage_pairs walk the reconstruction chain to its checked leaves, refusing an ambiguous chain, an unfinished branch and a repeated plan with a message that names which one applied.
- [x] Let a rebinding name an unstarted plan that owns no reconstruction contract, addressed where that plan lives, and bind its record to the contract whose chain made the reference unresolvable.
- [x] Add tests for the multi-generation resolution, the new reach, the ambiguity and unfinished-branch refusals, and every refusal that must stay unchanged. Mutation-test each new test on its own.
- [x] Rebind plans 356 and 357 to the checked archive of plan 359 with the rebind_lineage operation, and verify the record chain with the existing verification path.
- [x] Update the plan workflow specification in both layouts to state the multi-generation resolution, the refusals and the contract binding for a plan that owns no contract.
- [x] Obtain independent review against the exact changed files, resolve findings within the existing budget, then run focused validation and the unchanged authoritative suites. Publish through manage-plan-worktrees.py; do not push.

## Validation Notes

- Plan 355 was reconstructed into 358 and 358 into 359. Plans 356 and 357 still name docs/plan/active/355, which no longer exists, so neither can be activated.
- Commit e3ebbfa repaired that by hand and was reverted in b1c909a, because a gate is written history and only rebind_lineage may rewrite it. This plan restores the sanctioned path instead.
- Both refusals were observed by running the command rather than by reading it, and both messages are quoted in the feasibility evidence.
- Measurement retracted an early alarm. Every reconstruction marks exactly one integration successor, the successor that inherits the source's whole acceptance list, so a chain is single-valued even though a contract has several successors. All 65 replanned sources have exactly one, none is degenerate, 54 resolve to a checked leaf, 11 are unfinished, and 9 chains span more than one generation. The acceptance was therefore implementable as written, as a pure widening.
- The operation writes docs/plan/replanned/baselines/live-successor-rebinds-v1.json, which this plan's write_scope does not name. That file is a plan-lifecycle record the sanctioned operation appends to, in the same sense as the active index every completion touches, so it was treated as lifecycle rather than product scope. The adversarial preflight asserts the change set stays inside write_scope plus exactly that one record.
- Commit b344e96 was required before any rebinding. validate_current_plan_rules runs on the updated plan, and plans 356 and 357 predated two default reads in docs/agent/spec-index.yaml, so the operation refused them. enforce_projection_semantics is False for a plan no contract owns, which forces live bytes to equal committed bytes, so the required_specs correction had to be committed first. It changes conformance only, not requirements.
- Independent review ran four rounds and reported one High and four Medium findings. All were reproduced before being accepted, and each fix carries a test that was mutation-checked to fail when its production line is reverted.
- Authoritative validation caught a defect the focused suite could not. tests/smoke.sh failed because register_stranded_reference_plans built the resolution map unconditionally, which made plain verification demand that every indexed checked archive be closed, and a repository finalizing a plan legitimately holds one open. The map is now built lazily, and lineage resolution reads the checked index leniently. Because the candidate was corrected, the authoritative suites ran more than once; the recorded results are those of the final candidate.
- Known gap, accepted by the owner. A plan that was rebound and is later reconstructed leaves its record keyed at a path that no longer resolves, and verification then refuses it as an unknown live successor. A fix was attempted and withdrawn on review evidence that it verified the archive wrapper rather than the reconstruction contract's stopped source. Reaching that state needs promotion, stopping and reconstruction of a rebound plan, so it is latent; it belongs to a follow-up plan, not to this one.
- This runtime cannot record parent_review, focused_validation or check --operation completion in the plan execution ledger, because those require a Codex ReviewPacketStart manifest that is never emitted here. Epoch and budget accounting for this run is therefore reported rather than ledger-proven.
- Focused validation on the final candidate: python3 tests/test-plan-restructure.py (199 tests), tests/root-plan-lifecycle.sh, python3 scripts/check-copier-template.py, python3 scripts/restructure-plan.py --verify. Authoritative validation: scripts/lint-project-workflow.sh and tests/smoke.sh. A nine-case adversarial preflight passed, including that every resolution the previous rule admitted still resolves.
