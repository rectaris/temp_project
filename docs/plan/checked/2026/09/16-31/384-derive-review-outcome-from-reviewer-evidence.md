# Derive a recorded review outcome from the reviewer session's own bound evidence

status: checked
primary_invariant: A bounded review records only the finding severities that the final assistant message of the reviewer transcript bound by its review resource manifest states in one fixed verdict line, and a bounded review whose bound evidence carries no such line refuses, before any registry, group or ledger effect, instead of recording an empty finding set.
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
  - {"evidence":"Of 104 local runs under .agent-logs that carry ReviewPacketStart, 89 bind raw/transcript.jsonl and 15 older ones do not. All 89 end their message records with an assistant message; the largest final message is 7,879 characters and the largest transcript 203 KB against the 1 MiB bound at scripts/plan-execution-state.py:721.","kind":"existing_mechanism"}
  - {"evidence":"template/.project-agent-workflow/scripts/import-codex-transcript.py:64 replaces any string over 12,000 characters with a JSON object that keeps only a 12,000-character head, and both plan 374 reviewer final messages end with the AGENTS.md report footer, so a verdict placed on the last line is lost or displaced.","kind":"reproduced_defect"}
  - {"evidence":"In record_event the bounded review path calls admit_reviewer_session at scripts/plan-execution-state.py:6426 and spend_group_member_review at :6436 after review_turn_zero_from_manifest at :6260, and the group spend is documented as staying spent after an interruption.","kind":"existing_mechanism"}
  - {"evidence":"review_turn_zero_from_manifest at scripts/plan-execution-state.py:787 is shared with review-route-check at :5927, and the manifest it verifies is already bound to the receipt through the reviewer session digest and the packet digest, so the verdict can be read from that manifest without changing the receipt or the shared check.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-plan-execution-state.py builds every review manifest through one resource_manifest helper at :286, so a bound verdict transcript reaches every existing review test from one place; about ten review calls that pass a severity also need a matching verdict.","kind":"existing_mechanism"}
  - {"evidence":"scripts/run-sandboxed-plan-worker.py:1650 refuses any write_scope entry under scripts/, tests/, template/ or docs/agent/ before worker start, and every entry of this plan lies there, so this plan runs parent-direct as plans 335, 344 and 383 did.","kind":"existing_mechanism"}
completion_conditions:
  - Recording a bounded review reads the external transcript that the review resource manifest binds and refuses when that evidence is absent, is not observed, or the first non-empty line of its final assistant message is not exactly one verdict line in the fixed grammar; a message the importer truncated is read from its retained head.
  - The recorded finding severities must equal the severity set the bound verdict states; a recorded set that adds, drops, or contradicts a stated severity refuses, and an empty recorded set is admitted only against a verdict that states no findings.
  - Every verdict refusal happens before reviewer-registry admission, group review spending and ledger mutation, so the reviewer registry, the group state and the execution ledger are unchanged after a refused review.
  - The review-verdict-instructions subcommand prints the exact reviewer instruction block whose verdict line the parser accepts, and every example verdict line in that block parses.
  - The review receipt format is unchanged, and review-route-check accepts the same evidence it accepted before.
  - The generated plan-execution-state.py stays byte-identical to the root script, and the Review-Finding Budgets section of SPEC_PLAN_WORKFLOW.md stays identical to its generated counterpart.
completion_witness_map:
  - {"condition_sha256":"sha256:18a3c217726f3c3f04863a924327fb3d0b6d9735ab7def6906b41e798500e2db","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:11492edcd26691677c70c5d9f60987ec5bdd90edf8afe4f9a7fc64ab9566c9fa","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:0d760a3ba3643b088b44f40989cdd97a835e3ee1ed52998f531b5e822605a70f","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:9f389598cae9741765bd50fad0a161ee0beef11a24de2960b692bacc39058ee2","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:f4b6a6d201c2db866694a281f50cfaa30959bc8b3ef8fecbe06e176e68e918c6","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:9e9f652ab37cd0890e8f9e85f6763d57bee1bac722ef19ffab76ab9bcecd5e6b","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
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
  - A bounded review is recorded only when the first non-empty line of the final assistant message of the bound reviewer transcript is one verdict line in the grammar that review-verdict-instructions prints and the recorded severity set equals that verdict; missing evidence, an unparsable verdict and a contradicting set each refuse before any registry, group or ledger effect, while the receipt format and review-route-check are unchanged.
  - The generated plan-execution-state.py stays byte-identical to the root script, and the Review-Finding Budgets section of SPEC_PLAN_WORKFLOW.md stays identical to its generated counterpart.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:03c0c266a95f663d54b79c5280d56aa917cfdede27eb3917088b46d2efd01d8f","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:9e9f652ab37cd0890e8f9e85f6763d57bee1bac722ef19ffab76ab9bcecd5e6b","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 記録するレビュー結果を、レビュアセッション自身の拘束済み証拠から導出する

## Decisions

- The invariant binds a recorded value to observed evidence. It does not claim that a same-user caller cannot replace that evidence, because docs/agent/SPEC_SECURITY.md places arbitrary same-user replacement outside the task worktree boundary. The property gained is that a recorded outcome which diverges from the reviewer's own words becomes detectable by any later reader, which is the standard ReviewPacketStart already established and the repository already accepted.
- The verdict is read from the external transcript rather than from a hook event, because the Stop hook payload carries no assistant message while raw/transcript.jsonl carries the reviewer final message verbatim. Hooks stay unchanged, so no other session type is affected.
- The verdict message is the last transcript record whose record_type is message and whose role is assistant. Its first non-empty line must be exactly `REVIEW-VERDICT: none`, or `REVIEW-VERDICT: ` followed by a comma-separated list without spaces of High, Medium and Low, each at most once and in that order, such as `REVIEW-VERDICT: High,Low`. A first line of any other shape, a second line in that message that starts with `REVIEW-VERDICT:`, or an empty message refuses. Earlier assistant messages are never parsed, so a quoted instruction block cannot supply the verdict.
- The verdict comes first, not last, for two observed reasons. A reviewer session reads AGENTS.md, whose Reports rule makes the final message end with the touched repository, validation and commit footer, and both plan 374 reviewer final messages end that way. The importer also replaces any content over 12,000 characters with a JSON object that keeps only the head. A first-line verdict survives both and matches SPEC_USER_COMMUNICATION.md, which asks for the outcome first.
- When the message content is a JSON object with exactly the keys head, length, sha256 and truncated, and truncated is true, the parser reads head as the message text. Any other content is read as it is. The retained head is what a later reader can inspect, so no verdict can hide in the discarded tail.
- The message is attributed to the reviewer by file, not by record. Assistant records carry no session_id, and the existing identity check already requires the whole bound transcript to resolve to the one reviewer session.
- The review receipt and the event shape stay unchanged. The transcript is the one bound by the manifest passed to the review command, which the existing turn-zero check already ties to the receipt through the reviewer session and packet digests. A later reader reaches the transcript through the event's receipt digest, the receipt's reviewer session and that session's manifest. A receipt field naming the transcript digest was considered and dropped: it adds no record-time check, and it would force a schema change whose historical receipts checkpoint issuance and legacy migration must still read.
- Verdict parsing lives in the bounded review path of record_event only. review_turn_zero_from_manifest keeps its name, signature and behavior, because review-route-check shares it and a route probe states no verdict, and the policy checkers require that marker.
- Verdict parsing and the severity comparison run immediately after review_turn_zero_from_manifest and before admit_reviewer_session and spend_group_member_review. A refusal after either call would leave a registry admission for an unrecorded review or a group review budget that stays spent. This follows the rule in the Review-Finding Budgets section of SPEC_PLAN_WORKFLOW.md that a staged-review refusal happens before reviewer-registry admission or ledger mutation.
- `record --event-type parent_review` stays unchanged and outside this invariant. Accepted closure at scripts/plan-execution-state.py:2694 and checked parent-direct commit at :5274 both require the deciding review to carry the exact review target digest, which only the bounded review path assigns at :6439, so a record-path review cannot satisfy either gate. Its severities still feed stop-reason accounting, which this plan leaves as it is.
- An absent or not_observed transcript refuses the review instead of falling back to the caller argument. This follows the existing rule that a staged review requires observed zero inherited turns rather than an unavailable-evidence path.
- A new review-verdict-instructions subcommand prints the reviewer instruction block the parser accepts, in the same form as review-route-packet. A verdict grammar that the parent must reconstruct by hand fails only after a full reviewer session has been spent, which plan 383 already observed when a reviewer prompt lacked the ReviewPacket line. The block contains no `ReviewPacket:` line, so it can follow the packet line in the reviewer's first prompt.
- The Review-Finding Budgets section of docs/agent/SPEC_PLAN_WORKFLOW.md and its generated counterpart state the verdict admission rule and name the subcommand, because that section already holds the staged-review admission rules and review-route-packet, and plans 335 and 344 documented the same kind of change there. The section is enforced identical after the path rewrite, so both files change together. references/orchestration.md is not changed.
- Discarding a reviewer session before it is recorded, and starting another one, is outside this invariant. An unrecorded session leaves no ledger or registry trace, and preventing a same-user parent from choosing not to record a review is the unforgeability claim that SPEC_SECURITY.md places outside the boundary and on which plans 370, 374 and 379 were rejected. This plan guarantees only that a recorded outcome equals the bound reviewer's own words.
- This plan runs parent-direct, because the writable runner refuses every entry of its write scope as validation authority. Its own review is therefore recorded by the changed script. The parent appends the block printed by the candidate's review-verdict-instructions to the reviewer's first prompt, after the ReviewPacket line. The stricter check then applies to this plan's own review; it grants this plan no weaker path.
- Live-session distinctness in verify-parallel-plan-sessions.py is the same class of defect and is deliberately left out of this plan, because the two invariants are independently validatable and coupling them is the condition that stops a plan for reconstruction. That work is held by plan 385, which was shelved on the owner instruction of 2026-09-26 because no plan is gated by that verifier.

## Tasks

- [x] In the bounded review path, immediately after review_turn_zero_from_manifest, read the bound external transcript through read_bound_resource_evidence, take the last assistant message, unwrap the exact truncation object to its head, and parse the first non-empty line as the fixed verdict line; refuse on absent or not_observed evidence, no assistant message, an unparsable first line, or a second verdict line.
- [x] Require the recorded finding severities to equal the parsed severity set, and refuse an empty recorded set unless the verdict is `REVIEW-VERDICT: none`, still before admit_reviewer_session and spend_group_member_review.
- [x] Add the review-verdict-instructions subcommand that prints the exact reviewer instruction block, and state the verdict admission rule and the subcommand in the Review-Finding Budgets section of docs/agent/SPEC_PLAN_WORKFLOW.md and template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md.
- [x] Extend the resource_manifest fixture once so every existing review test supplies a bound transcript with a verdict, give each severity-bearing review call a matching verdict, then add refusal tests covering a last-line-only verdict, a truncated message whose head carries the verdict, and a refused review that leaves the reviewer registry, group state and ledger bytes unchanged, plus a test that review-route-check still accepts its probe evidence.
- [x] Mirror the change into template/.project-agent-workflow/scripts/plan-execution-state.py and run the focused witnesses.

## Validation Notes

- Plans 370, 374 and 379 pursued related requirements through invariants asserting that a calling session could not author, relocate or replay a parent-owned record. Eight independent review epochs rejected that shape on one recurring ground, and docs/agent/SPEC_SECURITY.md already places arbitrary same-user replacement outside the boundary. This plan asserts no such property.
- 374 acceptance items one through three are already carried by working code: forty tests across GroupedExecutionAdapterTests, ParentDirectMemberSessionTests and LiveMemberEvidenceTests pass at the planning baseline and cover stale evidence, target drift, the reserved review slot, interrupted and duplicate publication, retirement authority, and root-to-generated identity. What 374 never closed is the caller-declared review outcome, which this plan addresses, and live-session distinctness, which shelved plan 385 holds.
- 374's live acceptance obligation, sha256:78d5a40ddf9da07975330961711334ee747e8bdf119961e1373ab28b57c42411 under parallel_sessions_v1, was last held by plan 382, which was shelved on the owner instruction of 2026-09-25. Under the shelving rule it is no longer required, no active or backlog plan declares live_evidence_contract, and this plan neither carries nor re-acquires that obligation.
- The live two-member demonstration is deliberately not a numbered plan. It needs no new execution-path code, only a committed group description and two real sessions, and a plan whose write scope is confined to docs/plan is refused by the admission contract.
- Owner instruction 2026-09-26, 「すべての修正項目を反映して良い。」, accepted a pre-start review of this plan whose findings are folded in above: first-line verdict and truncation handling, refusal before registry and group effects, the SPEC_PLAN_WORKFLOW.md documentation pair, the unrecorded-session boundary, parent-direct self-application, and the corrected transcript counts.
- The same instruction fixes how this plan stops. It carries one invariant, and acceptance item 2 has no value apart from item 1, so neither bounded descope nor reconstruction applies to it. If a formal review leaves a High or Medium finding after the permitted remediation, or the work needs a path outside write_scope, stop at the existing owner-decision state with the evidence retained and report. Do not create a repair, descope, backlog or reconstruction successor without a new owner instruction.
- Apply every edit to this plan before the execution ledger is initialized. The ledger binds the plan digest at init, and a later plan edit leaves the run unable to resume, which is how plan 374's ledger became unreopenable.
- The Decisions text says the verdict block can follow the ReviewPacket line. That is wrong. `.project-agent-workflow/hooks/agent_log_event.py` parses everything after the `ReviewPacket:` marker as the packet JSON, so trailing text suppresses ReviewPacketStart. A pre-review probe session showed this. The specification bullet and every reviewer prompt of this run therefore place the block before the ReviewPacket line. The plan file is digest-bound by the execution ledger, so the deviation is recorded here rather than in Decisions.
- That probe session could not be recorded as a formal review and is retained under `plan-384-parent-direct/review-1/`. It also reported a Low finding: deeply nested JSON content raised RecursionError. The parser now treats that content as plain text. The same remediation made the review refuse when the manifest bytes change during verdict reading, and dropped the reviewer's line text from the grammar refusal message.
- Formal review round 1 under run `plan-384-parent-direct-001` returned `REVIEW-VERDICT: Medium`. The finding: a reviewer-authored literal JSON with the truncation-object keys was unwrapped, so its head could supply the verdict. Recording that review without `--finding-severity` was refused and left the ledger and registry bytes unchanged, which demonstrated the invariant on this plan's own review. The review was recorded with Medium, and the run stopped with `parent_remediation_budget_exhausted`.
- Owner instruction 2026-09-26, 「継続して実装作業をせよ。」, authorized a same-plan continuation, run `plan-384-parent-direct-epoch1`. The parser now unwraps the truncation object only when its head has exactly 12,000 characters and its length is an integer greater than 12,000, the only shape the importer produces. A reviewer-authored object that satisfies both is longer than 12,000 characters and is truncated again by the importer. A test runs the real importer to confirm this. This narrows the Decisions rule on truncation-object shape, and the specification bullet's "retained head when the importer truncated it" stays accurate.
- Formal review round 1 of the continuation returned `REVIEW-VERDICT: none` and was recorded with no finding severities. Focused validation (267 tests and the copier template check), `tests/smoke.sh` and the completion check passed. The first `scripts/lint-project-workflow.sh` run stopped at the Python lint step because Ruff was not installed in the default Python environment. It was rerun once with the tools from `tools/python-quality/requirements.txt` on PATH and passed. No helper agents were used; the reviewers were independent Codex sessions started by the parent.
