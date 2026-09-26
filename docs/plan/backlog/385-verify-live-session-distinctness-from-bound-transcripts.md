# Verify live-session distinctness and overlap from bound member transcripts instead of report strings

status: backlog
primary_invariant: A live-evidence report is admitted only when each of its two members names a private runtime transcript outside the repository whose bytes match the reported digest, whose session metadata names exactly that member's reported session, and which holds a tool record inside that member's implementation interval, and when the two sessions differ and the two intervals overlap; a caller-declared session list, session count or interval list never satisfies the gate.
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"validate_report at scripts/verify-parallel-plan-sessions.py:602 takes distinct_session_ids as caller strings at :616-622 and admits a report carrying session_count 2 with fewer than two distinct ids, so the only condition that makes the evidence live is unverified.","kind":"reproduced_defect"}
  - {"evidence":"implementation_intervals at scripts/verify-parallel-plan-sessions.py:623-641 is optional and compared as strings, so a report omitting it skips the overlap check entirely.","kind":"reproduced_defect"}
  - {"evidence":"docs/agent/SPEC_AGENT_LOGGING.md:233-235 and its generated counterpart at :239-241 already require one transcript per member outside the project with its absolute path and SHA-256 digest in the report, re-reading those bytes, and a tool record inside each member's interval, while scripts/verify-parallel-plan-sessions.py contains no transcript handling at all.","kind":"reproduced_defect"}
  - {"evidence":"A Codex rollout under ~/.codex/sessions has a session_meta record naming payload.session_id and response_item tool records of payload.type function_call or custom_tool_call with a UTC timestamp but no session id. Local rollouts since 2026-09-01 have a median of 1.6 MB and a maximum of 56 MB and are written with mode 0664.","kind":"existing_mechanism"}
  - {"evidence":"read_private_bytes at scripts/verify-parallel-plan-sessions.py:298 already reads a bounded, non-symlinked, single-link, mode-0600 regular file, and require_outside_repository at :287 already refuses a path inside the repository.","kind":"existing_mechanism"}
  - {"evidence":"Every remaining report field is already re-derived from Git by verify_member_evidence: commit existence, publication ancestry and order, result trees, patch digests, changed paths, retention and worktree or branch retirement.","kind":"existing_mechanism"}
  - {"evidence":"validate_report runs in verify, bind at :1216 and require via :1105. tests/root-plan-lifecycle.sh:574, run by scripts/lint-project-workflow.sh, holds the only positive live report and uses distinct_session_ids strings, so it must change with the verifier. The eight LiveMemberEvidenceTests call verify_member_evidence and are unaffected.","kind":"existing_mechanism"}
completion_conditions:
  - Each report member names session_digest, transcript_path, transcript_sha256 and implementation_interval; the verifier reads the transcript as a private mode-0600 file outside the repository and outside both member worktrees within a 64 MiB bound, and refuses a missing file, a digest mismatch, or a transcript whose session metadata does not name exactly the member's session.
  - The two members must report two different session digests, and the top-level distinct_session_ids, session_ids, session_count and implementation_intervals fields are refused rather than read.
  - Each member interval must be two parsed UTC timestamps with start before end, must contain at least one tool record timestamp from that member's transcript, and must overlap the other member's interval; an absent, unparsable or non-overlapping interval refuses.
  - The root lifecycle fixture builds its positive live report from two private member transcripts, and verify, bind and require still pass on it.
  - The generated verify-parallel-plan-sessions.py stays byte-identical to the root script.
completion_witness_map:
  - {"condition_sha256":"sha256:a9b0d8ff5fdaa9b285a45f1fb272a947783c8000b223d71e1271d9e75bbb498a","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0df3640809df2a297c51f27bcefdd097c825b5f7e2ca810992cdc74e02baa518","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:f5769dbf805065679f1bee29928a369a761c6f743e4b8544908ab57347c74b24","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:2a06e923fcb666b8c1798d6c0fe90819e6538ca3f2e2daa7d427204ba4539dcf","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:9784f10623be49b66d8a0dec22af3aacc432fd765ccba8f1c6bb9726740ff578","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/verify-parallel-plan-sessions.py
  - template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py
  - tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A live-evidence report is admitted only when both members resolve, through private transcripts whose digests match, to two distinct sessions whose parsed implementation intervals each contain one of their own tool records and overlap; a caller-declared session list, session count or interval list, a missing or altered transcript, and an omitted interval each refuse, and the root lifecycle fixture still passes on transcript-backed evidence.
  - The generated verify-parallel-plan-sessions.py stays byte-identical to the root script.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a61dd5f323d1a7c0482ba4de3f49b0e8aef78d7fe17b1541c995d3b89a01375e","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:9784f10623be49b66d8a0dec22af3aacc432fd765ccba8f1c6bb9726740ff578","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 実地セッションの別個性と重なりを、報告書の文字列ではなく拘束済みのメンバートランスクリプトから確認する

## Decisions

- The invariant binds a reported identity to observed runtime bytes. It does not claim that a same-user caller cannot write a transcript, because docs/agent/SPEC_SECURITY.md places arbitrary same-user replacement outside the task worktree boundary. The property gained is that a report claiming two sessions that never ran no longer passes by assertion alone.
- The verifier implements the Parallel Session Evidence rules SPEC_AGENT_LOGGING.md already states rather than a new run-manifest binding. Run manifests live under .agent-logs inside a checkout, move to .agent-logs/retired-tasks when a member retires, and are refused by the existing manifest reader at that depth, while the specification already requires transcripts outside the project.
- The accepted transcript format is the Codex runtime rollout. The session is the payload.session_id of its session_meta records, which must name exactly one session. Tool records are response_item records whose payload.type is function_call or custom_tool_call, and their timestamp is the top-level timestamp field. Any other format refuses, and no transcript format is inferred.
- A tool record carries no session id, so it is attributed to the one session its transcript names. The implementation revises the SPEC_AGENT_LOGGING.md sentence that says a tool record carries the member's session digest to state this file-level attribution, and makes the same edit in the generated counterpart.
- The operator supplies each transcript as a private mode-0600 copy under the account home, because runtime rollouts are written with mode 0664 and read_private_bytes requires 0600. The transcript_sha256 binds the copied bytes. The read bound is 64 MiB, which covers every local rollout since 2026-09-01.
- The member interval stays a declared value, but it is no longer self-certifying: it must contain one of that member's own tool records and must overlap the partner interval under parsed timestamp comparison. Terminal lifetimes and manifest created_at and updated_at values are not used.
- The Git-derived half of the verifier is left unchanged. Commit ancestry, publication order, result trees, patch digests, changed paths and retirement are already re-derived and were never the weak part.
- The live two-member demonstration remains outside numbered plans. It requires no new execution-path code, only a committed group description and two real sessions, and a plan whose write scope is confined to docs/plan is refused by the admission contract.

## Tasks

- [ ] Add the per-member session_digest, transcript_path, transcript_sha256 and implementation_interval fields, and refuse the top-level distinct_session_ids, session_ids, session_count and implementation_intervals fields.
- [ ] Read each transcript through read_private_bytes with a 64 MiB bound after require_outside_repository and a check that it lies outside both reported member worktrees, then verify its digest and its single session_meta session against the member's session_digest.
- [ ] Parse both intervals as UTC timestamps, require one of the member's tool records inside its own interval, and require the two intervals to overlap.
- [ ] Revise the tool-record attribution sentence in docs/agent/SPEC_AGENT_LOGGING.md and template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md identically, and state the mode-0600 private copy there.
- [ ] Add validate_report tests covering an altered transcript, a transcript inside the repository, one shared session, a declared count or id list, an interval without its own tool record, and non-overlapping or absent intervals.
- [ ] Rebuild the positive live report in tests/root-plan-lifecycle.sh from two private fixture transcripts outside the fixture repository, keeping its existing verify, bind and require assertions.
- [ ] Mirror the change into template/.project-agent-workflow/scripts/verify-parallel-plan-sessions.py and run the focused witnesses.

## Validation Notes

- This plan is the second of two that close what plan 374 never closed. The first is the recorded review outcome in plan-execution-state.py. The two are kept apart because they are independently validatable; coupling independent invariants is the condition that stops a plan for reconstruction, and it is what happened to 374. The two plans share no written file.
- 374 acceptance items one through three are already carried by working code, with forty passing tests at the planning baseline covering stale evidence, target drift, the reserved review slot, interrupted and duplicate publication, retirement authority, and root-to-generated identity. Neither this plan nor its predecessor reimplements that work.
- 374's live acceptance obligation, sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411 under parallel_sessions_v1, was last held by plan 382, which was shelved on the owner instruction of 2026-09-25. No active or backlog plan declares live_evidence_contract, so no plan is gated by this verifier today. The owner chose on 2026-09-26 to keep this plan so the verifier matches its specification before any later plan reserves a live demonstration.
