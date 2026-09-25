# Resume retained implementation after a verified committed acceptance partition

status: shelved
shelved_reason: Owner instruction 2026-09-25: 374 以外の関連プランはすべて棚上げして良い. Plan 374 is being reconstructed directly, so this retained-work resumption mechanism is superseded.
shelved_at: 2026-09-25
primary_invariant: A stopped descope execution can authorize at most one owner-approved retained-work child, bound to the exact committed partition and inherited implementation, without rewriting evidence, resetting review accounting or widening acceptance authority.
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
  - {"evidence":"At ae5b9f9, plan 374 execution check refuses descope_required and descope_plan refuses the changed source HEAD. Ordinary continue explicitly accepts only descope_pending with parent_remediation_budget_exhausted, not a committed acceptance partition.","kind":"reproduced_defect"}
  - {"evidence":"A read-only Git/record probe reproduced the source acceptance digests, the exact retained 374 and deferred 378 partitions, original reservation binding and source ancestry. The canonical predecessor contains one formal review and no open writable attempt.","kind":"bounded_prototype"}
  - {"evidence":"plan-execution-state.py already verifies canonical stopped ledgers, one-time continuation-registry consumption, reviewer admissions, descendant source adoption, exact parent-direct review targets and private owner authorization. Extend these shared predicates rather than create a parallel authority.","kind":"existing_mechanism"}
completion_conditions:
  - A separately owner-authorized retained-work child is admitted only from an eligible canonical stopped parent-direct descope ledger, a verified committed source-ordered partition, unchanged invariant and authority, descendant Git history and verified obligation transfers.
  - One-time registry consumption preserves all predecessor formal reviews and correction accounting, grants no more than its unused review capacity, and rejects forks, replay, exhausted capacity, missing ancestry or evidence and replacement registries.
  - The child review and lifecycle identity covers inherited in-scope implementation from the original reviewed baseline plus new corrections; an empty child diff, dropped inherited changes or changed target cannot substitute for acceptance of the final implementation.
  - The child remains subject to route proof, exact-target adversarial preflight, clearing formal review, focused and authoritative validation, task-bound publication and retirement; stopped and historical executions keep their prior behavior.
  - Root/generated ledger commands and policy remain aligned, and existing ordinary, terminal and owner-resolution routes retain their eligibility and cumulative limits.
completion_witness_map:
  - {"condition_sha256":"sha256:f112921cd0d3cf22d484e6a5c946782ad693fdc99f38d2f7ca3c225f96862381","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:1d07f4dd4bccfebb86d48688ef89f311881de69df759cb20d0db8666c64a8cd5","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:37a7139a2cd3c303a0c897b4e841c3e578b13c04e3614b1c6abd4d70eacc050b","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:ad038576a6ba70db1d54d30b1ba7adedb9bfe53e2a9c2be1f879ddff897af981","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:c81f8962a8b0785cf031c79d3211f45fd2b88fa2ed2de5a0cf7ed58e955aeb96","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - tests/validation_tools/worktrees.py
  - tests/validation_tools/plan.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - scripts/check-root-agent-policy.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/verify-parallel-plan-sessions.py
  - scripts/manage-plan-worktrees.py
  - scripts/project_workflow/worktree_guard.py
  - docs/plan/replanned/2026/09/16-31/370-preserve-live-evidence-obligations-across-descope.md
  - docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md
  - docs/plan/backlog/378-verify-live-parallel-session-results.md
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Only an explicitly owner-authorized, ungrouped parent-direct child of a verified descope partition may begin retained implementation; missing or changed requirements, invariant, authority, source history, obligation transfer or original evidence refuse before effects.
  - The original stopped ledger and registries remain historically verifiable, one predecessor is consumed once, every prior review remains counted and neither the recorded review ceiling nor unused capacity grows through descope, restart or descendant adoption.
  - Review and completion bind the complete inherited implementation plus the exact child correction, not merely changes made since the child started; changed or omitted inherited work and stale review evidence refuse.
  - An admitted child can finish only through the unchanged review, validation and managed publication gates; this prerequisite never reopens plan 374 itself and never retrospectively accepts its already published implementation.
  - Root/generated controls agree and regression coverage preserves legacy ledgers, ordinary continuation, terminal continuation, fourth-review and owner-resolution restrictions.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7d73822ce2c725cf325ef62e39a761424ee45e6c671c5ac2e55279d2cce8a1b8","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:e9daa4cbdbd14391ed3dc8179fcaded532889839205500c8d3e4a51f0f0f0364","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:a58f0bd6358432b7c7d60e1c39d9b3324cda8325767f1c7d39c9e7e74fcf31a7","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:10a85e371c5d2926864ff03a4d8c2b021df9f6fee09b274a6fe9f95fe161cb99","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:f1fad1c20c6800c28015801d3f6cec7509257c2728a564099c86a58ac132e4a4","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after docs/plan/active/370-preserve-live-evidence-obligations-across-descope.md is checked; rebind this reference to its exact archive before activation.
  - Implement through an independent parent-direct prerequisite execution under existing controls; this new continuation path must not implement or accept itself.
  - Do not edit plans 374 or 378 or mutate their stopped ledger, continuation registry, reviewer registry or required-evidence record. All transition effects in this prerequisite use isolated fixtures.
  - After both prerequisites are checked, a separate owner-authorized application must bind the actual transfer, align live plan instructions and activate 374 through the checked path; no status-only activation or fresh unbound epoch-zero ledger is permitted.
checked_summary_ja: 分離後の残作業を、停止記録とレビュー回数を保ったまま再開できるようにする。

## Decisions

- Owner approved A/A: implement retained-work continuation separately from evidence-obligation transfer, preserve the stopped source and accepted requirements, and never increase cumulative review capacity.
- One owner-authorized child execution after a verified committed acceptance partition, consuming the stopped predecessor once and retaining its review history, is the only new execution authority. Leave the existing continue and all historical ledger schemas unchanged.
- Require a canonical descope_required ungrouped parent-direct predecessor with no open writable attempt, its exact descope classification, original reviewer and continuation registries, and owner authorization binding the current descendant, source and destination plan bytes and partition commit.
- Prove the partition from committed Git objects against the original source acceptance list. Permit only the approved split and necessary lifecycle/instruction alignment; reject requirement loss, reworded acceptance, invariant drift, validation weakening or expanded external effects.
- Use the existing one-time predecessor consumption and exact recovery mechanism. A second child, a missing consumed child or replacement evidence must refuse rather than recreate implementation authority.
- Carry actual historical formal-review count and reviewer admissions into the child. Do not raise the predecessor recorded ceiling or grant more than its unused capacity; permit one explicitly authorized bounded parent correction and no worker attempt. Further continuation is not granted by this route.
- Bind the child target to the original inherited implementation baseline and exact current descendant, not just the child's new diff. Required-specification digests and final review cover all inherited in-scope changes plus corrections; published-but-unaccepted code remains unaccepted.
- Do not import old lifecycle JSON as new validation evidence. Materialize the new exact target at the new private child identity only after admission, preserving old ledger and lifecycle bytes.
- A required live obligation must already have a verified transfer to the exact deferred plan. This path cannot delete or satisfy an obligation and cannot make absent primary evidence appear present.
- Preserve all existing failure diagnosis, review stop, focused and authoritative validation, task worktree and publication restrictions. Document the refusal when the remaining review capacity is insufficient rather than silently allocating more.
- Keep real plan 374 deferred during prerequisite implementation. Only a later application of the checked controls may activate it; this plan supplies no retrospective acceptance for ae5b9f9 or its ancestors.

## Tasks

- [ ] Activate only after the evidence-transfer prerequisite is checked, then initialize this prerequisite's own parent-direct ledger and pass the existing review-route and execution gates.
- [ ] Add isolated positive and negative fixtures using the observed historical descope shape, one recorded formal review and a committed acceptance partition.
- [ ] Implement exact owner authorization, partition/obligation verification and one-time child consumption using existing ledger readers and registry locks.
- [ ] Bind inherited implementation into review and lifecycle target identities while retaining historical budgets and unchanged legacy routes.
- [ ] Cover partition drift, missing records, duplicated child consumption, crash recovery, review exhaustion, stale descendant targets and lifecycle/publication refusal.
- [ ] Mirror policy and command changes, review the full target, pass adversarial preflight and independent review, then run focused and authoritative validation.
- [ ] Publish and archive this prerequisite without applying it to plan 374 or altering its stopped evidence.

## Validation Notes

- Owner authorization on 2026-09-23: approve_bounded_prerequisites. This plan changes executable controls, not merely plan-lifecycle files, and is not a successor introduced to reset plan 374 review limits.
- The bounded read-only probe at ae5b9f9 found one prior formal review, no open attempt, exact preserved acceptance partitions, a valid original reserved-evidence record and descendant Git history. It did not establish cleared findings or completed live acceptance.
- The original plan 374 execution remains plan-374-parent-direct-001 at descope_required. Its canonical ledger byte digest is sha256:6854364ec8ae2911ab916adea7ed0361b26eb7ff65d5dfe735e854011db732bf; preserve it unchanged.
