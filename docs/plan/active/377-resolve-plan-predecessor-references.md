# Refuse a live plan that names a plan path which does not exist, so a predecessor reference cannot silently point at nothing.

status: in_progress
implementation_mode: parent_direct
primary_invariant: Every docs/plan path a plan in active or backlog names must resolve to a file that exists in the repository.
task_types:
  - validation_tools
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Changing the first integration gate of docs/plan/backlog/372 from 287-complete-resumable-parent-worktrees.md to the nonexistent 999-a-plan-that-does-not-exist.md left scripts/restructure-plan.py --verify, scripts/lint-project-workflow.sh and tests/smoke.sh all passing.","kind":"reproduced_defect"}
  - {"evidence":"The same tamper applied to docs/plan/backlog/356, which carries a lineage_rebind record, was refused by scripts/restructure-plan.py --verify with 'rebind baseline final projection: ... changes protected manifest field: context_files'. Protection exists only for a plan that already has a record.","kind":"reproduced_defect"}
  - {"evidence":"restructure-plan.py already enumerates live plans through live_plan_records() and already parses these paths with PLAN_PATH_RE and LIVE_PLAN_PATH_RE, and --verify already runs inside lint-project-workflow.sh, tests/smoke.sh and tests/root-plan-lifecycle.sh.","kind":"existing_mechanism"}
  - {"evidence":"docs/plan/backlog/README.md already states the rule as a manual step: a reference to prerequisite work must resolve to an existing completion record from docs/plan/checked.md before the plan is promoted.","kind":"existing_mechanism"}
completion_conditions:
  - Verification refuses a plan in docs/plan/active or docs/plan/backlog that names a docs/plan path with no file behind it, and names both the plan and the unresolved path.
  - A plan under docs/plan/checked, docs/plan/replanned or docs/plan/shelved keeps passing unchanged, because an archive records the paths that were true when it was written.
  - Every plan currently in docs/plan/active and docs/plan/backlog satisfies the new rule without editing any of them.
  - The template copy of the restructure module stays byte-identical to the root copy and the two specification copies stay aligned.
  - The authoritative suite passes with the new refusal in place.
completion_witness_map:
  - {"condition_sha256":"sha256:8fb0a7d75a0f499dc01cbb7e20642306b25589b6680fbc066a85be55bdb5c587","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:76c2727e2d6de62a340681081eef86876ccead6ddb368fb76ce0324c24c89998","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:553d4dd8d6fc9ad7c436516dbd253d2e25532ac8ffbb7a281fe8969b256c19a2","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:f6618e4974a56458eb856f2042bfd7f8b89e371706a5dbcfb33820313bbc9ea9","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:717b1d27cdc4fad6880fa5880cb27006f24f7193483aceb90e430252d7dbeac3","witness":"tests/smoke.sh"}
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/360-resolve-multigeneration-lineage-rebinding.md
  - docs/plan/checked/2026/08/16-31/243-admit-lineage-rebinding-for-checked-predecessors.md
  - docs/plan/backlog/README.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
  - tests/smoke.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A live plan naming a docs/plan path that does not exist is refused, and the message names the plan and the unresolved path.
  - A completed, replanned or shelved plan naming a path that no longer exists is still admitted.
  - The repository's own live plans pass the new rule with no plan edited to satisfy it.
  - The root and template copies stay aligned.
  - The authoritative suite passes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:ca90a29fe5000ed27142f265f6781b9e0a374abb7963c36794827d07ebb1844e","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:f98930392a17d2fc30b27b87dcf041b7d14edc6bb37cd356e41e2d9b7ffd481c","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:f192b35aa8a062fac1228b62c5fc655da1a579b19d780ed7dc4269a078563071","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:6e6877c40696cb0307bd554ab16076229fa9cb253bf8ffe0073d990d966d2557","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:252f87d8e7c97ba898346eb03524eb23885ffa17b44e04e6f707710ba47ea36e","stage":"focused","witness":"tests/smoke.sh"}
checked_summary_ja: 実在しないプランのパスを書いた未完了プランを拒否し、先行プランへの参照が何も指さない状態を残さないようにする。

## Decisions

- Check that the referenced path exists, and do not try to decide whether it is the correct predecessor. Correctness is not recoverable from the file alone once a plan has no rebind record.
- Apply the rule only to plans in docs/plan/active and docs/plan/backlog. An archive under checked, replanned or shelved records the paths that were true when it was written, and must not be invalidated by later moves.
- Put the check inside scripts/restructure-plan.py --verify rather than a new command, because that command already walks the live plan records and is already run by lint-project-workflow.sh, tests/smoke.sh and tests/root-plan-lifecycle.sh.
- Name the plan and the unresolved path in the refusal, so the operator can fix the reference without searching for it.
- Mirror the module byte-for-byte into the template instead of writing a separate generated-project check, so generated projects gain the same rule with no second implementation.

## Tasks

- [ ] Confirm the write scope and the current required specifications, and record the exact evidence bytes that show a dangling reference passing today.
- [ ] Collect the docs/plan paths that each live plan names, and refuse a plan whose named path has no file behind it.
- [ ] Keep archives outside the rule, and add a test that a completed plan naming a moved path is still admitted.
- [ ] Add tests for the refusal, for the admitted cases, and for the exact message, and confirm each one fails when its production line is reverted.
- [ ] Mirror the module into the template byte-for-byte and record the rule in both copies of the plan workflow specification.
- [ ] Run the focused validation, then run the authoritative suite once on the final candidate.

## Validation Notes

- The gap was measured on the published dev state at commit bcb646a. Rewriting the first integration gate of docs/plan/backlog/372 to docs/plan/checked/2026/09/01-15/999-a-plan-that-does-not-exist.md left --verify, lint-project-workflow.sh and tests/smoke.sh all passing.
- The same tamper on docs/plan/backlog/356 was refused, because plan 360 wrote a lineage_rebind record for it and the rebind baseline protects context_files. That protection covers only a plan that already carries a record, so it is not a substitute for this rule.
- Plan 360 repaired the sanctioned rebinding path. It did not add a check that a reference resolves, and this plan does not change any behaviour plan 360 introduced.
