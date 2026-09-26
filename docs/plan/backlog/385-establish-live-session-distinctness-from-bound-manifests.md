# Establish live-session distinctness from bound run manifests instead of report strings

status: backlog
primary_invariant: A live-evidence report establishes each of its two member sessions from a bound run-manifest session observation, and a report whose claimed session identity has no such observation, or whose two members resolve to one observed session, refuses.
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"validate_report at scripts/verify-parallel-plan-sessions.py:616-622 accepts distinct_session_ids as caller strings and admits a report carrying session_count 2 with fewer than two distinct ids, so the only condition that makes the evidence live is unverified.","kind":"reproduced_defect"}
  - {"evidence":"implementation_intervals at scripts/verify-parallel-plan-sessions.py:623-641 is optional and compared lexically, so a report omitting it skips the overlap check entirely.","kind":"reproduced_defect"}
  - {"evidence":"Every remaining report field is already re-derived from Git by verify_member_evidence: commit existence, publication ancestry and order, result trees, patch digests, changed paths, retention and worktree or branch retirement.","kind":"existing_mechanism"}
  - {"evidence":"A run manifest records resource_observations.root_session_identity as an observed digest of the runtime session id, produced by the repository hooks rather than by the reporting caller.","kind":"existing_mechanism"}
  - {"evidence":"No test calls validate_report directly; the twenty-eight LiveMemberEvidenceTests call verify_member_evidence, so the session-identity change reaches new tests only.","kind":"existing_mechanism"}
completion_conditions:
  - Each reported member session identity must be backed by a bound run manifest whose observed root-session identity matches it, and an identity with no such manifest refuses.
  - The two members must resolve to two different observed sessions, and a session count declared without two distinct observed identities no longer satisfies the gate.
  - The overlap check reads the bound manifests rather than caller interval strings, and a report that supplies no manifest-derived interval refuses instead of skipping the check.
  - The generated verify-parallel-plan-sessions.py stays byte-identical to the root script.
completion_witness_map:
  - {"condition_sha256":"sha256:9411772490283b01db4661092992a1643257bb67fcda0dd26c4a17aff4470021","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:48184bfda023a7aee19af1bf2a0e8457d9fc79e73eb247d24c4f72d5f71ee743","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:2d1aec1a5e119164d80a0a22272246e3da5f2553d4cd2bb2091f27b86d9c624c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:9784f10623be49b66d8a0dec22af3aacc432fd765ccba8f1c6bb9726740ff578","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - tests/test-sandboxed-plan-worker.py
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/plan-execution-state.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A live-evidence report is admitted only when both member sessions resolve to two distinct observed run-manifest identities with overlapping manifest-derived implementation intervals; a caller-declared session id, a declared session count, and an omitted interval each refuse.
  - The generated verify-parallel-plan-sessions.py stays byte-identical to the root script.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:80306bdc239ef05a16573d5d0b5983e79cc2b2ce487600ba724f899fb5e4a5a2","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:9784f10623be49b66d8a0dec22af3aacc432fd765ccba8f1c6bb9726740ff578","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 実地セッションの別個性を、報告書の文字列ではなく拘束済み実行マニフェストから確立する

## Decisions

- The invariant binds a reported identity to an observed record. It does not claim that a same-user caller cannot write a manifest, because docs/agent/SPEC_SECURITY.md places arbitrary same-user replacement outside the task worktree boundary. The property gained is that a report claiming two sessions that never ran no longer passes by assertion alone.
- The Git-derived half of the verifier is left unchanged. Commit ancestry, publication order, result trees, patch digests, changed paths and retirement are already re-derived and were never the weak part.
- Interval overlap is derived from the bound manifests rather than kept as an optional caller field, because an optional check that a report can omit provides no gate.
- The live two-member demonstration remains outside numbered plans. It requires no new execution-path code, only a committed group description and two real sessions, and a plan whose write scope is confined to docs/plan is refused by the admission contract. Running the demonstration before this plan lands would prove nothing, because the distinctness it demonstrates would still rest on caller strings.

## Tasks

- [ ] Require each reported member session to name its run manifest, and resolve the observed root-session identity from that manifest.
- [ ] Refuse a reported identity with no matching observed manifest identity, and refuse when both members resolve to one observed session.
- [ ] Derive the implementation interval of each member from its bound manifest and require the two to overlap, refusing when a manifest supplies no interval.
- [ ] Remove the session_count fallback so a declared count cannot stand in for two observed identities.
- [ ] Add validate_report tests covering an unbacked identity, one shared session, a declared count without identities, and absent manifest intervals.
- [ ] Mirror the change into template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py and run the focused witnesses.

## Validation Notes

- This plan is the second of two that close what plan 374 never closed. The first is the recorded review outcome in plan-execution-state.py. The two are kept apart because they are independently validatable; coupling independent invariants is the condition that stops a plan for reconstruction, and it is what happened to 374.
- 374 acceptance items one through three are already carried by working code, with forty passing tests at the planning baseline covering stale evidence, target drift, the reserved review slot, interrupted and duplicate publication, retirement authority, and root-to-generated identity. Neither this plan nor its predecessor reimplements that work.
