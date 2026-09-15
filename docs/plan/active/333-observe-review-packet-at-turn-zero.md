# Record a review packet arrival from the reviewer session's own prompt hook

status: in_progress
implementation_mode: parent_direct
primary_invariant: A review packet-start record exists only when the reviewer session's own prompt hook observed that exact packet as the session's first submitted prompt, and the hook keeps the packet digest without the prompt body.
task_types:
  - agent_logging
  - validation_tools
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Measured at dev 9eddf74: the execution ledgers for plans 355, 358, 359, 360 and 377 hold only execution_epoch_started and adversarial_preflight events. None holds a parent_review that binds a review target, so no staged review has ever been admitted in this checkout.","kind":"reproduced_defect"}
  - {"evidence":"Measured on the newest Codex rollout files under ~/.codex/sessions/2026/09: the first response_item message with role user carries the injected AGENTS.md instructions rather than the submitted prompt, so record order alone cannot establish that a reviewer session started at turn zero.","kind":"reproduced_defect"}
  - {"evidence":"review_turn_zero_from_manifest in scripts/plan-execution-state.py admits a staged review only when the bound runtime evidence holds exactly one ReviewPacketStart or review_packet_start record whose session id digest, packet digest and inherited turn count match the review receipt.","kind":"existing_mechanism"}
  - {"evidence":"The user-prompt-submit.command.input schema embedded in the installed Codex binary lists prompt, session_id, cwd, model, turn_id and transcript_path as required fields, so the prompt hook already receives the exact submitted prompt and the session identity.","kind":"existing_mechanism"}
  - {"evidence":"The committed .codex/hooks.json already runs .project-agent-workflow/hooks/agent_log_event.py for UserPromptSubmit, and that hook already validates and persists review_packet_digest and inherited_turns for an event named ReviewPacketStart.","kind":"existing_mechanism"}
completion_conditions:
  - The prompt hook appends one packet-start record when a session's first submitted prompt declares a review packet whose recomputed canonical digest equals the digest the prompt declares.
  - A later prompt in the same session appends no packet-start record, so a resumed or continued session cannot claim that it started at turn zero.
  - A prompt whose declared digest differs from the recomputed canonical digest of the packet it carries appends no packet-start record.
  - The hook stores the packet digest and the inherited turn count and stores no prompt body, in the packet-start record and in every other record it writes for that prompt.
  - The root hook and the template hook write the same record for the same payload.
  - The agent logging specification states that a prompt-hook observation of the packet may establish review turn zero, that a session-start record alone may not, and that the prompt body is never stored.
completion_witness_map:
  - {"condition_sha256":"sha256:fb28aab3b67787fa8d1e0c3154634d9f68471fb2d94340af2aa38d3b3e1b9b8f","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:25167f7bc8c2e94999efcc010888c1e5c435f1496b254868f2ab06bbf31d0a57","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:b5b9062ecc09413504201286b8d7de2e2ef36faf2212b1c159c479f5e5fe8f2e","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:621e63e793700c03d1ca4e3d57c2bc87f0f6382f8a0be346aa42b33eea779df3","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:e57f480f31a452d0c3f17e1136634f8bacc98957617cc6366fe2ab4e6d5a2087","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:f682dfd5fea3c3720099dde0d713b9ff02459f83c6bd050810b101f711ddf115","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .project-agent-workflow/hooks/agent_log_event.py
  - template/.project-agent-workflow/hooks/agent_log_event.py
  - tests/hooks/logging.py
  - docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - .codex/hooks.json
  - scripts/plan-execution-state.py
  - scripts/check-agent-log-manifest.py
required_specs:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A reviewer session whose first submitted prompt declares a review packet produces one packet-start record carrying that packet digest and zero inherited turns.
  - A later prompt in the same session produces no packet-start record.
  - A prompt whose declared packet digest does not match the packet it carries produces no packet-start record.
  - No record written for that prompt contains the prompt body.
  - The root and template hooks write the same record for the same payload.
  - The authoritative suite passes with the packet-start record in place.
  - The root and template copies of the agent logging specification state the same admissible turn-zero observation.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7bb9f5a81e789a433e3131f5e0cc98a444b9d0350bc3dc5d7eaad4d58a27f84a","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:820d95816a1b05854b782a9decc29fb91d9569c387ac109ea55b30950d182d2f","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:eebb67d8a04debb737f522b425ac6dab8f9af7aaef1fba8e4dcc5d82ff8559ed","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:c7981006045beb1e39b803184e4a2342b04b507094d529efb3aeda48045e1547","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:0c4a1f8795ddef0310247ee352bad8c3b35f870d80ff1453a49b4828b19bc4b4","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:c9f2e9636810cd2858606e21bf9ddd7b85239f91b76873c0272867ab42790fcc","authoritative_only_reason":"The generated-project hook wiring is only exercised by a full generated project, which no narrower command builds.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:ee19edf144387171af579e9f2454a4ae731d3ab6a71cd0cd20199c9eebefd5eb","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: レビュー包の到着を、レビューア自身のプロンプトフックが記録する。

## Decisions

- Observe the packet in the reviewer session's own prompt hook rather than deriving it from the rollout transcript. The newest Codex rollout carries the injected AGENTS.md instructions as its first user message, so message order does not identify the submitted prompt, while the prompt hook receives that prompt directly.
- Require the reviewer prompt itself to declare the packet: one marker line carrying the declared sha256 digest, followed by the canonical review packet JSON. The hook recomputes the canonical digest from the carried JSON and refuses a mismatch, so the parent cannot name a digest the prompt does not contain.
- Derive the inherited turn count from the prompt records this run already holds for that session id, and write the packet-start record only when that count is zero. A session-start record alone stays insufficient, as the current specification already requires.
- Store the packet digest and the inherited turn count only. The prompt body carries the review target and must not enter the log, so the hook keeps the existing allowlist behaviour and adds no prompt field.
- Change no admission rule in scripts/plan-execution-state.py. That command already accepts this record shape, so this plan supplies the missing producer and leaves the evidence contract untouched.

## Tasks

- [ ] Confirm the write scope and the current required specifications, then record the observed payload shape of one UserPromptSubmit event before changing the hook.
- [ ] Add the packet declaration parser to the root hook: read the marker line, recompute the canonical digest of the carried packet JSON, and refuse a mismatch without writing a record.
- [ ] Count the prompt records this run already holds for that session id, and append the packet-start record only when that count is zero.
- [ ] Keep the prompt body out of every stored record, and confirm that the existing redaction and allowlist behaviour is unchanged.
- [ ] Add the hook logging cases for the accepted record, the later prompt, the digest mismatch, and the absent prompt body, and confirm each fails when its production line is reverted.
- [ ] Mirror the change into the template hook and record the rule in both copies of the agent logging specification.
- [ ] Run the focused validation, then run the authoritative suite once on the final candidate.

## Validation Notes

- This plan supplies the producer that scripts/plan-execution-state.py already requires. Until it is checked, no staged review can be admitted in this checkout, and the plan 376 candidate stays uncommitted for that reason.
- This plan's own independent review cannot use the record it introduces, because the producer does not exist while the plan is being implemented. Use the plain record --event-type parent_review route once, state the missing preflight binding, registry admission and epoch budget in the completion report, and treat that as a single bootstrap exception rather than a precedent.
- Use bounded parent-direct implementation for this high-risk hook and validation-authority change. Preserve the declared scope and acceptance gates; an independent read-only review remains required under the single bootstrap exception above.
