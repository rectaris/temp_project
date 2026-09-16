# Check the review evidence route before an execution run edits product files

status: in_progress
implementation_mode: parent_direct
primary_invariant: An epoch-enabled execution run reaches its first writable operation only after the ledger holds one recorded review-route check whose probe evidence satisfies the same conditions a real review admission requires.
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
  - {"evidence":"Measured in the plan 376 session: the parent edited five files in the bound worktree and only then found that no admissible independent review could be obtained. That candidate is still uncommitted, and no execution ledger was ever created for plan 376.","kind":"reproduced_defect"}
  - {"evidence":"check_gate in scripts/plan-execution-state.py already refuses an operation from recorded ledger state, and every runner operation already receives the ledger through --plan-execution-state, so the refusal point this plan needs already exists.","kind":"existing_mechanism"}
  - {"evidence":"execution_epoch already separates epoch-enabled runs from legacy ledgers, so a new precondition can apply to an epoch-enabled run without reaching a legacy ledger that never gained the epoch route.","kind":"existing_mechanism"}
  - {"evidence":"resource_observations_from_manifest and review_turn_zero_from_manifest already verify a run manifest end to end, so a probe manifest can be checked by the same code that admits a real review rather than by a second implementation.","kind":"existing_mechanism"}
completion_conditions:
  - An epoch-enabled run is refused at its first writable operation while the ledger holds no recorded review-route check.
  - The review-route check is recorded only from a probe run manifest that carries a packet-start observation for the declared probe packet and observes at least one reviewer tool call.
  - A probe manifest that carries no packet-start observation, or that observes no reviewer tool call, is refused and leaves no recorded check behind.
  - A legacy ledger that holds no execution epoch keeps its existing behaviour, and every execution ledger the repository already holds keeps verifying without being edited.
  - The template copy of the execution state command stays aligned with the root copy.
  - The plan workflow specification states that an epoch-enabled run records a review-route check before its first writable operation, and the root and template copies stay aligned.
completion_witness_map:
  - {"condition_sha256":"sha256:d35b2bd245ddfadc2a8fb26534dfe44a6bb8d8d2b371a7fd4733fd107c3b590a","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:b6e983e0421cf15f6d0aacd1df2fb2d63f46e9ac221759e0d7a746748f974407","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:d28696e2cf25f564e2247bd29390a7b51a65067d399eaa7330a71592146e8200","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:b1875bc1fd5eeb281557fac58bf5b4972740f1fd6d0d42d8a78941645ae18c72","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:82520db89dd050db33055d16295bd4022d35a8b4390c1ed3c3e7fa8855444e75","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:450dd1759d3dab4c93a5949312cd1b05cb1babeced2836440e56efcdfb4061dd","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - references/orchestration.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An epoch-enabled run without a recorded review-route check is refused before its first writable operation.
  - A probe manifest that satisfies both review admission conditions records the check and releases the refusal.
  - A probe manifest that fails either condition is refused and records nothing.
  - Legacy ledgers and every existing execution ledger are unchanged.
  - The root and template copies of the command stay aligned.
  - The authoritative suite passes with the added precondition in place.
  - Both copies of the plan workflow specification state the review-route check requirement.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b0a659d17d6b077075238304d86a30e63ea4d56eae51372568b30f087d1d6d74","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:9f3439dbf45849124e71c55c38bb03502b8f14fec62ed973aa65022a0310c25a","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:ddfd9fcc0003fec34e38bd0b89cceb50ee72864badcf1a7d1ea6308d7cb433b0","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:ab0eb9a458f320f749632dcc0faae60f7731b551b39d9a10197c227a8df84408","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:14adefe88021f6d209181bb6bc0da6db7630cf2bdc240c55f96a0c6dcc5fddb0","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:6f1cdf581fb83d6dece17d0aef488ded2b7d96494fe2585a0d38f63e855a163f","authoritative_only_reason":"The generated project's own copy of the command is only executed by a full generated project, which no narrower command builds.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:c7536cbbdf13709db9ac1b4f5cbd2ae220b567858c8fb665b600c6109662e323","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start this plan only after the packet-start producer plan and the reviewer tool-call plan are checked. Its probe verifies exactly the two conditions those plans introduce, so an earlier start would check a route that cannot yet succeed.
checked_summary_ja: 実行が製品ファイルを変更する前に、レビュー証拠の経路を検査する。

## Decisions

- Verify the probe with the same functions that admit a real review, rather than with a separate capability report. A second implementation could pass while the admission path still refuses, which is the failure this plan exists to prevent.
- Place the refusal at the first writable operation rather than at ledger creation. Creating a ledger costs nothing and is reversible, while a product edit is what left plan 376 with an uncommitted candidate.
- Apply the precondition only to epoch-enabled runs. Legacy ledgers never gained the staged review route, so requiring a route check from them would refuse work that was never going to take that route.
- Record the check as ledger state rather than as a separate file. The refusal must read it under the same lock as every other gate, and a file beside the ledger could be replaced between the check and the operation.
- Keep the probe packet distinct from any real review packet. The probe proves the route works; it is not a review and must not be usable as one.

## Tasks

- [ ] Confirm the write scope and the current required specifications, then reproduce an epoch-enabled writable operation that proceeds today with no review-route evidence.
- [ ] Record the review-route check from a probe manifest, verifying it with the same functions that admit a real review, and refuse a probe that fails either condition.
- [ ] Refuse the first writable operation of an epoch-enabled run while no check is recorded, and leave legacy ledgers untouched.
- [ ] Add the refusal, accepted probe, rejected probe and legacy cases, and confirm each fails when its production line is reverted.
- [ ] Mirror the command into the template and record the rule in both copies of the plan workflow specification.
- [ ] Run the focused validation, then run the authoritative suite once on the final candidate.

## Validation Notes

- This plan is the last of the three and is the only one that cannot be checked before its predecessors. Its probe asserts the two conditions the earlier plans introduce, so running it first would assert a route that no producer can satisfy.
- The refusal is a precondition, not a guarantee that a later review will be admitted. A route that worked at probe time can still fail later, and this plan makes no claim about that case.
- Plans 333 and 335 are checked and published. Use bounded parent-direct implementation for this high-risk execution-gate and validation-authority change, preserving the exact scope and all normal staged-review and validation gates.
