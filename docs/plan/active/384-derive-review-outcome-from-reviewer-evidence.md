# Derive a recorded review outcome from the reviewer session's own bound evidence

status: in_progress
primary_invariant: A recorded review outcome states only the finding severities that the bound reviewer-session transcript itself reports under one fixed verdict grammar, and a review whose bound evidence carries no parsable verdict refuses instead of recording an empty finding set.
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
  - {"evidence":"A real reviewer run wrote its verdict verbatim into raw/transcript.jsonl as an assistant message with a bound session_id, and the manifest already binds that file digest under resource_observations.evidence_digests.external_transcript.","kind":"existing_mechanism"}
  - {"evidence":"read_bound_resource_evidence at scripts/plan-execution-state.py:721 already reads a manifest-declared evidence file safely against a bound digest, and RESOURCE_EVIDENCE_SOURCES at :299 already maps external_transcript to transcript_log.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-plan-execution-state.py builds every review through one review_receipt helper at :431 and one resource_manifest helper at :286, so the fixture change reaches every existing review test from two places.","kind":"existing_mechanism"}
completion_conditions:
  - Recording a review reads the reviewer transcript that the review resource manifest binds, and refuses when that evidence is absent, is not observed, or carries no final assistant verdict line in the fixed grammar.
  - The recorded finding severities must equal the severity set the bound verdict states; a recorded set that adds, drops, or contradicts a stated severity refuses, and an empty recorded set is admitted only against a verdict that states no findings.
  - The command prints the exact reviewer instruction block whose verdict grammar the check parses, so a parent never has to reconstruct the required shape by hand.
  - The generated plan-execution-state.py stays byte-identical to the root script.
completion_witness_map:
  - {"condition_sha256":"sha256:ee98af052f343d2a21e6d0f17f1d416052fc2ae198c0b0d1ad09fea14d6dc37f","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:11492edcd26691677c70c5d9f60987ec5bdd90edf8afe4f9a7fc64ab9566c9fa","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:aebdfb8a5878914a81b5c504ae354ea3c9afacf6656ff532dae19543b1d89f22","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:73a96182b0a5521c5ea2122a2e524ee84d3cfebdc52f8944c96143e07c243445","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/verify-parallel-plan-sessions.py
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
  - A recorded review outcome is admitted only when the bound reviewer transcript states a parsable verdict whose severity set equals the recorded one; missing evidence, an unparsable verdict, and a contradicting severity set each refuse rather than recording no findings.
  - The reviewer instruction block that produces the parsed grammar is printed by the command itself, and the generated plan-execution-state.py stays byte-identical to the root script.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:2a1c70f253a1128cb199e1c44ec83c8a15a8f1b42604c29166eb2a7b9775f8bd","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:0d5dd77410707a35f7d92f003901e26b5e04afd642182afc05965ace02f75621","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 記録するレビュー結果を、レビュアセッション自身の拘束済み証拠から導出する

## Decisions

- The invariant binds a recorded value to observed evidence. It does not claim that a same-user caller cannot replace that evidence, because docs/agent/SPEC_SECURITY.md places arbitrary same-user replacement outside the task worktree boundary. The property gained is that a recorded outcome which diverges from the reviewer's own words becomes detectable by any later reader, which is the standard ReviewPacketStart already established and the repository already accepted.
- The verdict is read from the external transcript rather than from a hook event, because the Stop hook payload carries no assistant message while raw/transcript.jsonl carries the reviewer final message verbatim. Hooks stay unchanged, so no other session type is affected.
- An absent or not_observed transcript refuses the review instead of falling back to the caller argument. This follows the existing rule that a staged review requires observed zero inherited turns rather than an unavailable-evidence path.
- The command prints the reviewer instruction block it parses. A verdict grammar that the parent must reconstruct by hand fails only after a full reviewer session has been spent, which this repository already observed once.
- Live-session distinctness in verify-parallel-plan-sessions.py is the same class of defect and is deliberately left to a separate backlog plan, because the two invariants are independently validatable and coupling them is the condition that stops a plan for reconstruction.

## Tasks

- [ ] Extend the review receipt so it binds the reviewer transcript evidence digest alongside the existing inheritance evidence digest, and bump the receipt schema version.
- [ ] Read the bound transcript through read_bound_resource_evidence, take the final assistant message, and parse the fixed verdict grammar; refuse on absent evidence, no final assistant message, or an unparsable verdict.
- [ ] Require the recorded finding severities to equal the parsed severity set, and refuse an empty recorded set unless the verdict states no findings.
- [ ] Add the command output that prints the exact reviewer instruction block whose grammar the parser accepts.
- [ ] Extend the resource_manifest and review_receipt fixtures once so every existing review test supplies a bound transcript, then add the refusal tests.
- [ ] Mirror the change into template/.project-agent-workflow/scripts/plan-execution-state.py and run the focused witnesses.

## Validation Notes

- Plans 370, 374 and 379 pursued related requirements through invariants asserting that a calling session could not author, relocate or replay a parent-owned record. Eight independent review epochs rejected that shape on one recurring ground, and docs/agent/SPEC_SECURITY.md already places arbitrary same-user replacement outside the boundary. This plan asserts no such property.
- 374 acceptance items one through three are already carried by working code: forty tests across GroupedExecutionAdapterTests, ParentDirectMemberSessionTests and LiveMemberEvidenceTests pass at the planning baseline and cover stale evidence, target drift, the reserved review slot, interrupted and duplicate publication, retirement authority, and root-to-generated identity. What 374 never closed is the caller-declared review outcome, which this plan addresses, and live-session distinctness, which a separate backlog plan addresses.
- The live two-member demonstration is deliberately not a numbered plan. It needs no new execution-path code, only a committed group description and two real sessions, and a plan whose write scope is confined to docs/plan is refused by the admission contract.
