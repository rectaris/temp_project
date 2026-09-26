# Derive a recorded review outcome from the reviewer session's own bound evidence

status: in_progress
primary_invariant: A bounded review records only the finding severities that the final assistant message of the reviewer transcript bound by its review resource manifest states in one fixed verdict line, and a bounded review whose bound evidence carries no such line refuses instead of recording an empty finding set.
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
  - {"evidence":"finding_severities comes from the bare --finding-severity argument at scripts/plan-execution-state.py:6223 and decides accepted closure at :2694 and checked parent-direct commit at :5275, so omitting the argument records an empty finding set that passes both gates.","kind":"reproduced_defect"}
  - {"evidence":"A review manifest binds raw/transcript.jsonl under evidence_digests.external_transcript. Assistant records carry no session_id, but validate_resource_identity_evidence at scripts/plan-execution-state.py:752 requires every session_id in that file to resolve to one observed session, and review_turn_zero_from_manifest at :787 requires it to be the reviewer.","kind":"existing_mechanism"}
  - {"evidence":"All 45 local review transcripts under .agent-logs end their message records with an assistant message, and the largest is 203 KB against the 1 MiB bound of read_bound_resource_evidence at scripts/plan-execution-state.py:721.","kind":"existing_mechanism"}
  - {"evidence":"review_turn_zero_from_manifest at scripts/plan-execution-state.py:787 is shared with review-route-check at :5927, and the manifest it verifies is already bound to the receipt through the reviewer session digest and the packet digest, so the verdict can be read from that manifest without changing the receipt or the shared check.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-plan-execution-state.py builds every review manifest through one resource_manifest helper at :286, so a bound verdict transcript reaches every existing review test from one place; about ten review calls that pass a severity also need a matching verdict.","kind":"existing_mechanism"}
completion_conditions:
  - Recording a bounded review reads the external transcript that the review resource manifest binds and refuses when that evidence is absent, is not observed, or its final assistant message does not end with exactly one verdict line in the fixed grammar.
  - The recorded finding severities must equal the severity set the bound verdict states; a recorded set that adds, drops, or contradicts a stated severity refuses, and an empty recorded set is admitted only against a verdict that states no findings.
  - The review-verdict-instructions subcommand prints the exact reviewer instruction block whose verdict line the parser accepts, and every example verdict line in that block parses.
  - The review receipt format is unchanged, and review-route-check accepts the same evidence it accepted before.
  - The generated plan-execution-state.py stays byte-identical to the root script.
completion_witness_map:
  - {"condition_sha256":"sha256:db14f2aaceeddc72d81b3a9b76735a5076787234a382f951e76cf01df257f461","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:11492edcd26691677c70c5d9f60987ec5bdd90edf8afe4f9a7fc64ab9566c9fa","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:9f389598cae9741765bd50fad0a161ee0beef11a24de2960b692bacc39058ee2","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:f4b6a6d201c2db866694a281f50cfaa30959bc8b3ef8fecbe06e176e68e918c6","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:73a96182b0a5521c5ea2122a2e524ee84d3cfebdc52f8944c96143e07c243445","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A bounded review is recorded only when the final assistant message of the bound reviewer transcript ends with one verdict line in the grammar that review-verdict-instructions prints and the recorded severity set equals that verdict; missing evidence, an unparsable verdict and a contradicting set each refuse, while the receipt format and review-route-check are unchanged.
  - The generated plan-execution-state.py stays byte-identical to the root script.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:cbf21e3d3531f9b01431100865a6653f9c93ef3f8ba0a1d59261509b7e280c82","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:73a96182b0a5521c5ea2122a2e524ee84d3cfebdc52f8944c96143e07c243445","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 記録するレビュー結果を、レビュアセッション自身の拘束済み証拠から導出する

## Decisions

- The invariant binds a recorded value to observed evidence. It does not claim that a same-user caller cannot replace that evidence, because docs/agent/SPEC_SECURITY.md places arbitrary same-user replacement outside the task worktree boundary. The property gained is that a recorded outcome which diverges from the reviewer's own words becomes detectable by any later reader, which is the standard ReviewPacketStart already established and the repository already accepted.
- The verdict is read from the external transcript rather than from a hook event, because the Stop hook payload carries no assistant message while raw/transcript.jsonl carries the reviewer final message verbatim. Hooks stay unchanged, so no other session type is affected.
- The verdict message is the last transcript record whose record_type is message and whose role is assistant. Its last non-empty line must be exactly `REVIEW-VERDICT: none`, or `REVIEW-VERDICT: ` followed by a comma-separated list without spaces of High, Medium and Low, each at most once and in that order, such as `REVIEW-VERDICT: High,Low`. A final line of any other shape, a second line in that message that starts with `REVIEW-VERDICT:`, or an empty message refuses. Earlier assistant messages are never parsed, so a quoted instruction block cannot supply the verdict.
- The message is attributed to the reviewer by file, not by record. Assistant records carry no session_id, and the existing identity check already requires the whole bound transcript to resolve to the one reviewer session.
- The review receipt and the event shape stay unchanged. The transcript is the one bound by the manifest passed to the review command, which the existing turn-zero check already ties to the receipt through the reviewer session and packet digests. A later reader reaches the transcript through the event's receipt digest, the receipt's reviewer session and that session's manifest. A receipt field naming the transcript digest was considered and dropped: it adds no record-time check, and it would force a schema change whose historical receipts checkpoint issuance and legacy migration must still read.
- Verdict parsing lives in the bounded review path of record_event only. review_turn_zero_from_manifest keeps its name, signature and behavior, because review-route-check shares it and a route probe states no verdict, and the policy checkers require that marker.
- `record --event-type parent_review` stays unchanged and outside this invariant. Accepted closure at scripts/plan-execution-state.py:2694 and checked parent-direct commit at :5274 both require the deciding review to carry the exact review target digest, which only the bounded review path assigns at :6439, so a record-path review cannot satisfy either gate. Its severities still feed stop-reason accounting, which this plan leaves as it is.
- An absent or not_observed transcript refuses the review instead of falling back to the caller argument. This follows the existing rule that a staged review requires observed zero inherited turns rather than an unavailable-evidence path.
- A new review-verdict-instructions subcommand prints the reviewer instruction block the parser accepts, in the same form as review-route-packet. A verdict grammar that the parent must reconstruct by hand fails only after a full reviewer session has been spent, which this repository already observed once. references/orchestration.md and the generated SPEC_ORCHESTRATION.md name that subcommand in the staged-review procedure so the documented steps match the command.
- Live-session distinctness in verify-parallel-plan-sessions.py is the same class of defect and is deliberately left out of this plan, because the two invariants are independently validatable and coupling them is the condition that stops a plan for reconstruction. That work is held by plan 385, which was shelved on the owner instruction of 2026-09-26 because no plan is gated by that verifier.

## Tasks

- [ ] In the bounded review path, read the bound external transcript through read_bound_resource_evidence, take the last assistant message, and parse the fixed verdict line; refuse on absent or not_observed evidence, no assistant message, or an unparsable verdict.
- [ ] Require the recorded finding severities to equal the parsed severity set, and refuse an empty recorded set unless the verdict is `REVIEW-VERDICT: none`.
- [ ] Add the review-verdict-instructions subcommand that prints the exact reviewer instruction block, and name it in references/orchestration.md and template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md.
- [ ] Extend the resource_manifest fixture once so every existing review test supplies a bound transcript with a verdict, give each severity-bearing review call a matching verdict, then add refusal tests and a test that review-route-check still accepts its probe evidence.
- [ ] Mirror the change into template/.project-agent-workflow/scripts/plan-execution-state.py and run the focused witnesses.

## Validation Notes

- Plans 370, 374 and 379 pursued related requirements through invariants asserting that a calling session could not author, relocate or replay a parent-owned record. Eight independent review epochs rejected that shape on one recurring ground, and docs/agent/SPEC_SECURITY.md already places arbitrary same-user replacement outside the boundary. This plan asserts no such property.
- 374 acceptance items one through three are already carried by working code: forty tests across GroupedExecutionAdapterTests, ParentDirectMemberSessionTests and LiveMemberEvidenceTests pass at the planning baseline and cover stale evidence, target drift, the reserved review slot, interrupted and duplicate publication, retirement authority, and root-to-generated identity. What 374 never closed is the caller-declared review outcome, which this plan addresses, and live-session distinctness, which shelved plan 385 holds.
- 374's live acceptance obligation, sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411 under parallel_sessions_v1, was last held by plan 382, which was shelved on the owner instruction of 2026-09-25. Under the shelving rule it is no longer required, no active or backlog plan declares live_evidence_contract, and this plan neither carries nor re-acquires that obligation.
- The live two-member demonstration is deliberately not a numbered plan. It needs no new execution-path code, only a committed group description and two real sessions, and a plan whose write scope is confined to docs/plan is refused by the admission contract.
