# Refuse a restructuring that would release a live-evidence obligation by omission

status: in_progress
primary_invariant: A restructuring of a source plan that declares a live-evidence obligation refuses unless one successor declares the same live_evidence_contract and the same live_evidence_acceptance_sha256, and no successor declares an obligation that no source held; the obligation is never released by omission and never invented.
task_types:
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Plan 374 declared live_evidence_contract: parallel_sessions_v1 and its archive at docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md still holds the field, but of the four successors the reconstruction created only plan 382 carries it, and only because the author copied the field by hand. No check reported the other three.","kind":"reproduced_defect"}
  - {"evidence":"grep -c live_evidence scripts/restructure-plan.py reports 0, and the generated mirror at template/.project-agent-workflow/scripts/restructure-plan.py reports 0. Neither live_evidence_contract nor live_evidence_acceptance_sha256 is read on any restructuring path, so the obligation lapses with no refusal and no report.","kind":"reproduced_defect"}
  - {"evidence":"Both restructuring paths already parse every source and successor manifest and already hold them side by side: validate_schema_three_integration_coverage at scripts/restructure-plan.py:2837 is called at :4901 and :8458 with successors and source_infos, and the schema-1 path builds the same successors list. The carry check reads fields that are already parsed.","kind":"existing_mechanism"}
  - {"evidence":"scripts/complete-plan.sh:46, scripts/finalize-active-plan.sh:36 and scripts/check-agent-completion.sh:138 already read live_evidence_contract with the same awk field expression, so the obligation has one established textual form and this plan adds no new one.","kind":"existing_mechanism"}
completion_conditions:
  - A schema-1 restructuring whose source declares live_evidence_contract refuses unless its successor declares the same contract and the same live_evidence_acceptance_sha256, and the refusal names the source plan and the field that reached no successor.
  - A schema-3 or schema-4 restructuring refuses unless, for every source that declares live_evidence_contract, at least one successor declares the same contract and the same live_evidence_acceptance_sha256.
  - A successor that declares a live-evidence obligation no source held is refused, and a source that declares no obligation restructures exactly as it does today.
  - Root and generated restructure-plan.py bytes stay identical after the change.
completion_witness_map:
  - {"condition_sha256":"sha256:328370477af9e21b83e214d7464eff37087304c8760511a90218aaa0220aaf61","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:04ade591a53e50d44093b6e6ece2e8b1a7f421b535008b65089a3a2d4c4bba23","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:3d02088c4de698dc8130a5aad164e803b1eb4c650daec4b38a2ae166a427eac2","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:7b46632b566eea591a55185edad0fcdf36e00d03f6e4e0e1fb5e542bbc9951c8","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - scripts/project_workflow/plan_authoring.py
  - docs/plan/replanned/2026/09/16-31/374-publish-and-verify-separate-session-plan-results.md
  - docs/plan/replanned/2026/09/16-31/370-preserve-live-evidence-obligations-across-descope.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Schema-1 restructuring refuses to release a declared live-evidence obligation and names the source plan and field in the refusal.
  - Schema-3 and schema-4 restructuring refuse unless every declaring source reaches a successor that carries the same contract and acceptance digest.
  - An invented successor obligation is refused and a source without an obligation keeps its current restructuring behavior unchanged.
  - The generated restructure-plan.py stays byte-identical to the root script.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b14271aa9d9d8d935dcc2705cbc2f0501ca39b06b530c06879087b7848d79b30","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:518505e29829c1f4149e24d42e3ba70b287c860df50bef34198537c865beab55","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:f3179d1bb2a0db0a23621a030439a3e91ff605867ab0b270f01ad0030c4ea8ca","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:c6a35bc09a92fb2725e0617808a7efa9e0111debead880dea6d0bf5184702fbc","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: live evidence 義務を引き継がない再構成を拒否し、義務が黙って消えないようにする。

## Decisions

- The obligation is carried, not released. A restructuring refuses when a declaring source reaches no successor that repeats the same contract and acceptance digest. There is no opt-out argument, because an opt-out would let the calling side decide its own gate, which is the shape four independent reviews rejected on plans 370 and 379.
- An owner who wants to stop pursuing the demonstrated work already has a path that does not run through this check: shelving the plan on an explicit instruction, as plans 378 and 382 were shelved. Shelving stays outside this refusal.
- The check compares live_evidence_acceptance_sha256 for equality rather than re-verifying the demonstration. The verifier scripts/verify-parallel-plan-sessions.py still owns that decision at completion and finalization; this plan only stops the obligation from disappearing before it.
- Both restructuring paths are covered. Schema 1 carries one source and one successor set and schema 3 and 4 carry several sources, so a check placed on only one path would leave the other open.
- A successor may not declare an obligation no source held, so the check refuses in both directions and a restructuring cannot be used to attach a demonstration requirement that no owner accepted.

## Tasks

- [ ] Add failing tests in tests/test-plan-restructure.py for a released obligation on the schema-1 path, a released obligation on the schema-3 and schema-4 path, an invented successor obligation, and an unchanged source that declares none.
- [ ] Read live_evidence_contract and live_evidence_acceptance_sha256 from the already parsed source and successor manifests and refuse an uncarried or invented obligation, naming the source plan and the field.
- [ ] Mirror the change into template/.project-agent-workflow/scripts/restructure-plan.py so root and generated bytes stay identical.
- [ ] Run the focused witnesses, then review the candidate and run the authoritative validation suite once.

## Validation Notes

- Plans 370, 374 and 379 pursued this requirement through a parent-owned session authority mechanism. Eight independent review epochs rejected that mechanism on one recurring ground: the parent and the member run as one OS principal and the mechanism holds no keyed authentication, so a record cannot be shown to be unforgeable by the calling session. docs/agent/SPEC_SECURITY.md already places arbitrary same-user replacement outside the task worktree boundary, so those invariants asserted a property this repository does not claim.
- This plan asserts no such property. Its invariant is an equality between two committed plan manifests, which the restructuring tool already reads. Plans 379 through 382 are shelved on owner instruction and the parallel-session mechanism is not pursued here.
