# Demonstrate live parallel sessions end to end

status: shelved
shelved_reason: Owner instruction 2026-09-25: E で進める（379〜382 は棚上げ）. The parallel-session authority mechanism is no longer pursued. Plan 370's actual requirement, that a descope or restructure must not silently drop a live-evidence obligation, is an exact static gap in scripts/restructure-plan.py and is taken up there instead.
shelved_at: 2026-09-25
implementation_mode: parent_direct
primary_invariant: The live-evidence gate passes only on evidence that two distinct real sessions actually produced, derived from parent-owned session records rather than from caller-declared roles, digests or intervals; two synthetic records never satisfy it.
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
  - sha256:4f7453fc0e59e3ccda836275d66739d8568b487ff2def2db542e550e784841cd
  - sha256:405a824fe0f24376c2ce7a8275ef41575cc19ddb95b3d66029a3600aba97a1d2
integration_source_ids:
  - 374
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: high
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The epoch-0 review of plan 374 recorded one High finding here: the live-session evidence gate accepts a tool record carrying only a role, a session digest and a timestamp, and computes overlap from caller-declared intervals, so two synthetic records satisfy the acceptance item.","kind":"reproduced_defect"}
  - {"evidence":"`validate_report` in `scripts/verify-parallel-plan-sessions.py` reads `implementation_intervals` directly from the submitted report and derives overlap from those declared start and end strings, which is the exact code path the finding names.","kind":"reproduced_defect"}
  - {"evidence":"The verifier already resolves parent-owned group state, session bindings and required-evidence records on its bind path, so the repair routes report validation through records that already exist instead of introducing a new evidence store.","kind":"existing_mechanism"}
  - {"evidence":"The two-session run itself is unproven. Plan 374 deferred it repeatedly and no live report has ever passed this gate, so this plan records high ambiguity and treats a failed live run as a stop for the owner rather than as a finding to correct in place.","kind":"reproduced_defect"}
completion_conditions:
  - Live report validation derives session identity and implementation overlap from parent-owned session records, so a report whose only evidence is a caller-declared role, digest, timestamp or interval refuses.
  - Two real sessions overlap implementation in distinct task worktrees, publish A then B with both changes retained and completed tasks retired, and their report passes the gate without the report environment variable.
  - The pre-implementation required-evidence record is bound to this plan and its live acceptance digest before implementation starts, and completion refuses while that record is absent.
  - Root and generated verifier bytes stay aligned after the change.
completion_witness_map:
  - {"condition_sha256":"sha256:bac0e9d7dbd438b74a5849877a3f8b90a19e9f2a64f35338a05cf7b6aee66262","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:5b8f034f41e1250daa912e215c81e4b0973e6f135e43fe3b7643e99701bca9be","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:56748ebd01dccbc93f4b2caf6c6b43f127f6cfd329c39e22d48b053849f4660e","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:eeba784c38e060314ba956533e568d0628bbf2986fa771090ed29615f67c2113","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md
  - docs/agent/spec-index.yaml
  - scripts/parallel-plan-state.py
  - scripts/plan-execution-state.py
  - scripts/manage-plan-worktrees.py
  - docs/plan/shelved/378-verify-live-parallel-session-results.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Integration assembles either handoff mode at the current target with original evidence retained and one review slot reserved from member execution; incompatible scope, stale evidence, target drift and spent review/correction allowances refuse.
  - Checked publication and serialized lifecycle updates retire only exact completed-member worktrees/branches; interruptions, dirty state or failed B retain accepted A and recoverable B without duplicate publication or false completion.
  - Root/generated commands and guidance expose matching start, handoff, integration and retirement behavior and register preservation fixtures for project plans, groups, configuration and history.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fa8fd07e674da2c9bc560061a17191a7336705b5f4da25a281060af350aff6e4","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:4f7453fc0e59e3ccda836275d66739d8568b487ff2def2db542e550e784841cd","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:405a824fe0f24376c2ce7a8275ef41575cc19ddb95b3d66029a3600aba97a1d2","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
live_evidence_contract: parallel_sessions_v1
live_evidence_acceptance_sha256: sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411
integration_gates:
  - Start only after plans 379, 380 and 381 are checked and published. This plan verifies their assembled result and must not repair their code; a defect found here stops this plan and is classified against the plan that owns it.
  - Reserve the required-evidence record bound to this plan and to live acceptance digest `sha256:78d5a40d` before implementation begins, not after the live run.
  - The live two-session run is the unproven part of this reconstruction. If it cannot be produced, stop for the owner with the requirement intact; never satisfy the gate with fabricated session records or by relaxing the verifier.
  - Plan 378 held this live acceptance item and is shelved on owner instruction. This plan therefore declares `live_evidence_contract` and `live_evidence_acceptance_sha256` directly, because `scripts/restructure-plan.py` never carries either field to a successor.
checked_summary_ja: 実セッション二つの結果だけが live ゲートを通るようにし、その実証を実際に行う。

## Decisions

- This plan is the integration successor, so it carries every acceptance item of plan 374 and verifies the assembled result rather than implementing a separate part of it.
- The live obligation lands here rather than on an earlier successor because the demonstration requires plans 379, 380 and 381 to be finished; placing it earlier would make it unsatisfiable.
- The verifier repair and the live run stay in one plan because a demonstration against an unhardened gate proves nothing, and a hardened gate with no demonstration leaves the original requirement open.
- Ambiguity is recorded as high. Plan 374 deferred this run repeatedly and it has never succeeded, so the plan is written to stop rather than to improvise if the run cannot be produced.

## Tasks

- [ ] Reserve the required-evidence record bound to this plan and to the live acceptance digest before any implementation.
- [ ] Reproduce the synthetic-record bypass as a failing case.
- [ ] Derive session identity and implementation overlap from parent-owned session records.
- [ ] Mirror the verifier into `template/.project-agent-workflow/scripts/`.
- [ ] Run two real sessions in distinct task worktrees, publish A then B, and retire both completed tasks.
- [ ] Verify the live report without the report environment variable.
- [ ] Run the focused commands, then the authoritative suite once.

## Validation Notes

- This plan is the integration successor of plan 374 and inherits all three of its acceptance items, in source order.
- The live acceptance digest `sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411` was previously held by plan 378, which is shelved on owner instruction. It is declared here through `live_evidence_contract` and `live_evidence_acceptance_sha256`, because `scripts/restructure-plan.py` reads neither field and would otherwise let the obligation lapse without any check reporting it.
- Waiver: plans 370, 371 and 378 are shelved. The assurance they would have added is a verified owner-authorized transfer of this live item to a separate destination plan and a bounded resumption path for retained work. This plan skips both: the item stays here, and a stopped run goes to the owner.
