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
  - {"evidence":"validate_review_receipt at scripts/plan-execution-state.py:917 also reads historical receipts during checkpoint issuance at :5206 and legacy checkpoint migration at :5379 and :5403, and review_turn_zero_from_manifest is shared with review-route-check at :5927, so the schema-1 read path and the shared turn-zero check must stay unchanged.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-plan-execution-state.py builds every review through one review_receipt helper at :431 and one resource_manifest helper at :286, so the fixture change reaches every existing review test from two places.","kind":"existing_mechanism"}
completion_conditions:
  - Recording a bounded review reads the external transcript that the review resource manifest binds and refuses when that evidence is absent, is not observed, differs from the transcript digest the receipt names, or its final assistant message does not end with exactly one verdict line in the fixed grammar.
  - The recorded finding severities must equal the severity set the bound verdict states; a recorded set that adds, drops, or contradicts a stated severity refuses, and an empty recorded set is admitted only against a verdict that states no findings.
  - The review-verdict-instructions subcommand prints the exact reviewer instruction block whose verdict line the parser accepts, and every example verdict line in that block parses.
  - Schema-1 review receipts stay readable for checkpoint issuance and legacy checkpoint migration, the bounded review command admits only schema-2 receipts, and review-route-check accepts the same evidence it accepted before.
  - The generated plan-execution-state.py stays byte-identical to the root script.
completion_witness_map:
  - {"condition_sha256":"sha256:b90f45c273f6af826d690d0cd62d72772ce6810423429643ca48ac4125acc0b3","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:11492edcd26691677c70c5d9f60987ec5bdd90edf8afe4f9a7fc64ab9566c9fa","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:9f389598cae9741765bd50fad0a161ee0beef11a24de2960b692bacc39058ee2","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:5e2e8cc2c526146a650f9102ab89d1a0184298fc099e8a765aa022c9ed806125","witness":"python3 tests/test-plan-execution-state.py"}
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
  - A bounded review is recorded only when the final assistant message of the bound reviewer transcript ends with one verdict line in the grammar that review-verdict-instructions prints and the recorded severity set equals that verdict; missing evidence, an unparsable verdict and a contradicting set each refuse, while schema-1 receipts stay readable and review-route-check is unchanged.
  - The generated plan-execution-state.py stays byte-identical to the root script.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b0677a037230ec4b8fd96301f07c8a3d3a927a4bceb818859f43f26ae33d87d6","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:73a96182b0a5521c5ea2122a2e524ee84d3cfebdc52f8944c96143e07c243445","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 記録するレビュー結果を、レビュアセッション自身の拘束済み証拠から導出する

## Decisions

- The invariant binds a recorded value to observed evidence. It does not claim that a same-user caller cannot replace that evidence, because docs/agent/SPEC_SECURITY.md places arbitrary same-user replacement outside the task worktree boundary. The property gained is that a recorded outcome which diverges from the reviewer's own words becomes detectable by any later reader, which is the standard ReviewPacketStart already established and the repository already accepted.
- The verdict is read from the external transcript rather than from a hook event, because the Stop hook payload carries no assistant message while raw/transcript.jsonl carries the reviewer final message verbatim. Hooks stay unchanged, so no other session type is affected.
- The verdict message is the last transcript record whose record_type is message and whose role is assistant. Its last non-empty line must be exactly `REVIEW-VERDICT: none`, or `REVIEW-VERDICT: ` followed by a comma-separated list without spaces of High, Medium and Low, each at most once and in that order, such as `REVIEW-VERDICT: High,Low`. A final line of any other shape, a second line in that message that starts with `REVIEW-VERDICT:`, or an empty message refuses. Earlier assistant messages are never parsed, so a quoted instruction block cannot supply the verdict.
- The message is attributed to the reviewer by file, not by record. Assistant records carry no session_id, and the existing identity check already requires the whole bound transcript to resolve to the one reviewer session.
- Review receipt schema 2 adds exactly one field, verdict_evidence_digest, which must equal the manifest's external_transcript digest. validate_review_receipt keeps accepting the exact schema-1 key set, so checkpoint issuance and legacy checkpoint migration still read historical receipts. Only the bounded review command requires schema 2. The event shape is unchanged, because the event already records the receipt digest as independent_review_receipt_digest.
- Verdict parsing lives in the bounded review path of record_event only. review_turn_zero_from_manifest keeps its name, signature and behavior, because review-route-check shares it and a route probe states no verdict, and the policy checkers require that marker.
- `record --event-type parent_review` stays unchanged and outside this invariant. Accepted closure at scripts/plan-execution-state.py:2694 and checked parent-direct commit at :5274 both require the deciding review to carry the exact review target digest, which only the bounded review path assigns at :6439, so a record-path review cannot satisfy either gate. Its severities still feed stop-reason accounting, which this plan leaves as it is.
- An absent or not_observed transcript refuses the review instead of falling back to the caller argument. This follows the existing rule that a staged review requires observed zero inherited turns rather than an unavailable-evidence path.
- A new review-verdict-instructions subcommand prints the reviewer instruction block the parser accepts, in the same form as review-route-packet. A verdict grammar that the parent must reconstruct by hand fails only after a full reviewer session has been spent, which this repository already observed once. references/orchestration.md and the generated SPEC_ORCHESTRATION.md name that subcommand in the staged-review procedure so the documented steps match the command.
- Live-session distinctness in verify-parallel-plan-sessions.py is the same class of defect and is deliberately left out of this plan, because the two invariants are independently validatable and coupling them is the condition that stops a plan for reconstruction. That work is held by plan 385, which was shelved on the owner instruction of 2026-09-26 because no plan is gated by that verifier.

## Tasks

- [ ] Add review receipt schema 2 with verdict_evidence_digest, keep the schema-1 key set readable in validate_review_receipt, and require schema 2 only in the bounded review command.
- [ ] In the bounded review path, read the bound external transcript through read_bound_resource_evidence, take the last assistant message, and parse the fixed verdict line; refuse on absent or not_observed evidence, a digest that differs from verdict_evidence_digest, no assistant message, or an unparsable verdict.
- [ ] Require the recorded finding severities to equal the parsed severity set, and refuse an empty recorded set unless the verdict is `REVIEW-VERDICT: none`.
- [ ] Add the review-verdict-instructions subcommand that prints the exact reviewer instruction block, and name it in references/orchestration.md and template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md.
- [ ] Extend the resource_manifest and review_receipt fixtures once so every existing review test supplies a bound transcript with a verdict, then add refusal tests plus tests that a schema-1 receipt still passes checkpoint issuance and legacy migration and that review-route-check still accepts its probe evidence.
- [ ] Mirror the change into template/.project-agent-workflow/scripts/plan-execution-state.py and run the focused witnesses.

## Validation Notes

- Plans 370, 374 and 379 pursued related requirements through invariants asserting that a calling session could not author, relocate or replay a parent-owned record. Eight independent review epochs rejected that shape on one recurring ground, and docs/agent/SPEC_SECURITY.md already places arbitrary same-user replacement outside the boundary. This plan asserts no such property.
- 374 acceptance items one through three are already carried by working code: forty tests across GroupedExecutionAdapterTests, ParentDirectMemberSessionTests and LiveMemberEvidenceTests pass at the planning baseline and cover stale evidence, target drift, the reserved review slot, interrupted and duplicate publication, retirement authority, and root-to-generated identity. What 374 never closed is the caller-declared review outcome, which this plan addresses, and live-session distinctness, which shelved plan 385 holds.
- 374's live acceptance obligation, sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411 under parallel_sessions_v1, was last held by plan 382, which was shelved on the owner instruction of 2026-09-25. Under the shelving rule it is no longer required, no active or backlog plan declares live_evidence_contract, and this plan neither carries nor re-acquires that obligation.
- The live two-member demonstration is deliberately not a numbered plan. It needs no new execution-path code, only a committed group description and two real sessions, and a plan whose write scope is confined to docs/plan is refused by the admission contract.
