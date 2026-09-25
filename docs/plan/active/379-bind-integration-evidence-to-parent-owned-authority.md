# Bind integration evidence to parent-owned authority

status: in_progress
implementation_mode: parent_direct
primary_invariant: Every value that decides an integration assembly, meaning the reserved review result, the retained original evidence and the handoff target, is read from a parent-owned record that the calling session cannot author, relocate or replay; a caller-supplied digest never decides an assembly outcome.
replan_sources:
  - docs/plan/active/374-publish-and-verify-separate-session-plan-results.md
replan_contract: docs/plan/replanned/contracts/374-publish-and-verify-separate-session-plan-results.json
successor_plans:
  - docs/plan/active/379-bind-integration-evidence-to-parent-owned-authority.md
  - docs/plan/active/380-retire-and-publish-members-without-false-completion.md
  - docs/plan/active/381-align-root-and-generated-parallel-session-surfaces.md
  - docs/plan/active/382-demonstrate-live-parallel-sessions-end-to-end.md
inherited_acceptance_digests:
  - sha256:fa8fd07e674da2c9bc560061a17191a7336705b5f4da25a281060af350aff6e4
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The epoch-0 independent review of plan 374 recorded two High findings on this boundary: publication requires only a recorded review event and `record-review` accepts caller-supplied digests without a receipt, findings or validation result; and retention evidence binds to caller-supplied baseline, result tree and patch digests rather than to the authoritative handoffs.","kind":"reproduced_defect"}
  - {"evidence":"The `record-review` subparser at `scripts/parallel-plan-state.py:3252` declares only the caller-supplied digest arguments and no receipt, findings or validation argument, so the missing authority is an exact locatable gap rather than a redesign.","kind":"reproduced_defect"}
  - {"evidence":"`scripts/parallel-plan-state.py` already stores parent-owned member handoff records under `PARENT_DIRECT_HANDOFF_SCHEMA_VERSION` and already authenticates the integration session by recorded identity and process incarnation, so both findings close by routing the two gates through records that already exist.","kind":"existing_mechanism"}
  - {"evidence":"The published candidate for plan 374 reached `dev` at commit `09a9815`, so this plan repairs code that is already present and covered by `tests/test-sandboxed-plan-worker.py` rather than reconstructing an unpublished prototype.","kind":"existing_mechanism"}
completion_conditions:
  - Recording a member review requires the reviewer receipt, the finding severities and the validation result, and a call that omits any of them refuses instead of recording a review event that publication would later accept.
  - Integration retention verification reads the baseline, result tree and patch digests from the authoritative parent-owned handoff records, so a caller-supplied replacement tree refuses instead of verifying as the retained one.
  - Integration assembly refuses on incompatible scope, stale evidence, target drift and a spent review or correction allowance, and each refusal names the exact parent-owned record that failed.
  - Root and generated `parallel-plan-state.py` and `run-parallel-plans.py` bytes stay aligned after the change.
completion_witness_map:
  - {"condition_sha256":"sha256:193ff311c681567aef6c92df7c57753f9308168a86bc0bfe1274ff65bd274e61","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:8a5bd7ab84749b662907446a3c2d6e610d0e4657f178c7210fb7d2b390a8d6af","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:efbf6a0e5da5141d6f2bdf917f6230af1c4d7e47c3c7eff758be0be7dd315c14","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3d3a48eaaef315c82c24ee5941c5c8e2614258f28149d6160fc9813c1166d0b1","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - tests/test-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md
  - docs/agent/spec-index.yaml
  - scripts/verify-parallel-plan-sessions.py
  - scripts/manage-plan-worktrees.py
  - scripts/plan-execution-state.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Integration assembles either handoff mode at the current target with original evidence retained and one review slot reserved from member execution; incompatible scope, stale evidence, target drift and spent review/correction allowances refuse.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fa8fd07e674da2c9bc560061a17191a7336705b5f4da25a281060af350aff6e4","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
integration_gates:
  - Start a fresh parent-direct execution ledger. The stopped plan 374 ledger `plan-374-parent-direct-001` is at `descope_required` and cannot reopen, and no operation in this plan may read, rewrite or resume it.
  - Change only the two integration scripts, their generated counterparts and the worker test file. Leave publication, retirement and lifecycle repair to plan 380, root and generated guidance to plan 381, and the live-evidence verifier to plan 382.
  - Plans 361, 371, 375 and 378 are shelved on owner instruction, so no prerequisite mechanism arrives from them. This plan's write scope already contains the records it needs; treat a value that still decides a gate from caller input as a stop condition rather than a finding to defer.
  - Plan 374 constrained its prerequisites so they could not apply their own controls to it, which is what stopped plan 361 at `security_boundary_drift`. That constraint is not inherited here.
checked_summary_ja: 統合の判定に使う値を親所有の記録だけから読み、呼び出し側が渡した digest が結果を決めないようにする。

## Decisions

- The two High findings in this boundary share one invariant: an authenticated caller must not be able to supply the value that decides its own gate. They are repaired together rather than as two plans.
- `record-review` gains required receipt, findings and validation-result arguments instead of an optional verification flag, so an existing caller that omits them fails loudly rather than silently keeping the old behavior.
- Retention verification resolves the authoritative handoff record first and compares the caller's claim against it, rather than accepting the claim when the record is missing.

## Tasks

- [ ] Reproduce both findings as failing cases in `tests/test-sandboxed-plan-worker.py` before changing behavior.
- [ ] Require the reviewer receipt, finding severities and validation result on `record-review`, and refuse a call that omits any of them.
- [ ] Resolve the authoritative handoff record before retention verification and refuse when the record is absent.
- [ ] Refuse assembly on incompatible scope, stale evidence, target drift and a spent review or correction allowance, naming the failing record.
- [ ] Mirror both scripts into `template/.project-agent-workflow/scripts/`.
- [ ] Run the focused commands, then the authoritative suite once.

## Validation Notes

- This plan is a reconstruction successor of plan 374, which stopped at `replan_required` with reason codes `multiple_independent_invariants` and `parent_remediation_budget_exhausted` after its epoch-0 review returned four High and five Medium findings.
- Waiver: plans 370, 371 and 378 are shelved on owner instruction, so the resumption mechanism and the separate live-evidence destination they were to provide do not arrive. The assurance those plans would have added is a separate bounded execution-resumption path and an independent live destination; this plan skips both and relies instead on a fresh ledger and on plan 382 holding the live obligation.
